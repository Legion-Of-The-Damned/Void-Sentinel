import discord
from discord.ext import commands
from discord import app_commands
import yt_dlp
import asyncio

# yt_dlp настройки (без cookies, публичный поиск)
ytdl_format_options = {
    'format': 'bestaudio/best',
    'quiet': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'no_warnings': True,
    'default_search': 'ytsearch5',  # поиск первых 5 результатов
    'source_address': '0.0.0.0',
}

ffmpeg_options = {'options': '-vn'}

ytdl = yt_dlp.YoutubeDL(ytdl_format_options)


class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title')
        self.url = data.get('webpage_url')

    @classmethod
    async def from_info(cls, data, *, stream=True):
        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)

    @classmethod
    async def search(cls, query):
        loop = asyncio.get_running_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(query, download=False))
        if not data or 'entries' not in data:
            raise Exception("Нет результатов поиска")
        return data['entries'][:5]  # возвращаем первые 5 результатов


class SelectResultView(discord.ui.View):
    def __init__(self, results, timeout=60):
        super().__init__(timeout=timeout)
        self.results = results
        self.selected = None

        for i, entry in enumerate(results):
            label = entry.get('title', 'Без названия')[:80]
            self.add_item(ResultButton(label=label, index=i, parent_view=self))

    async def on_timeout(self):
        if self.selected is None:
            for child in self.children:
                child.disabled = True
            await self.message.edit(view=self)

    async def wait_for_selection(self):
        await self.wait()
        return self.selected


class ResultButton(discord.ui.Button):
    def __init__(self, label, index, parent_view):
        super().__init__(label=f"{index + 1}. {label}", style=discord.ButtonStyle.secondary)
        self.index = index
        self.parent_view = parent_view

    async def callback(self, interaction: discord.Interaction):
        self.parent_view.selected = self.index
        for child in self.parent_view.children:
            child.disabled = True
        await interaction.response.edit_message(view=self.parent_view)
        self.parent_view.stop()


class Music(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.queue = asyncio.Queue()
        self.current = None
        self.play_next_song = asyncio.Event()

    async def cog_load(self):
        asyncio.create_task(self.player_loop())

    async def ensure_voice(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        if vc is None:
            if interaction.user.voice:
                vc = await interaction.user.voice.channel.connect()
            else:
                await interaction.response.send_message("❗ Вы не находитесь в голосовом канале.", ephemeral=True)
                return None
        return vc

    async def player_loop(self):
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            self.play_next_song.clear()
            self.current = await self.queue.get()
            vc = self.current["vc"]

            def after_playing(error):
                if error:
                    print(f"[playback error] {error}")
                self.bot.loop.call_soon_threadsafe(self.play_next_song.set)

            vc.play(self.current["source"], after=after_playing)

            await self.current["interaction"].followup.send(
                embed=discord.Embed(
                    title=f"🎶 Сейчас играет: {self.current['source'].title}",
                    url=self.current['source'].url,
                    color=discord.Color.blue()
                ),
                view=None
            )
            await self.play_next_song.wait()

    @app_commands.command(name="играть", description="Играет песню по ссылке или поиску с выбором")
    @app_commands.describe(запрос="Ссылка или поисковый запрос для песни")
    async def play(self, interaction: discord.Interaction, запрос: str):
        vc = await self.ensure_voice(interaction)
        if vc is None:
            return

        await interaction.response.defer()

        if запрос.startswith("http"):
            # Обрабатываем как прямую ссылку
            try:
                info = await self.extract_info(запрос)
                player = await YTDLSource.from_info(info)
                await self.queue.put({"source": player, "vc": vc, "interaction": interaction})
                if not vc.is_playing():
                    self.play_next_song.set()
                else:
                    await interaction.followup.send(f"✅ Трек **{player.title}** добавлен в очередь.")
                return
            except Exception as e:
                await interaction.followup.send(f"❌ Ошибка при загрузке трека:\n```{e}```", ephemeral=True)
                return

        # Иначе — поиск с выбором из 5 вариантов
        try:
            results = await YTDLSource.search(запрос)
        except Exception as e:
            await interaction.followup.send(f"❌ Ошибка поиска:\n```{e}```", ephemeral=True)
            return

        view = SelectResultView(results)
        message = await interaction.followup.send(
            "🎵 Найдено несколько результатов, выберите один:", view=view, ephemeral=True
        )
        view.message = message

        selected_index = await view.wait_for_selection()
        if selected_index is None:
            await interaction.followup.send("⌛ Время выбора истекло.", ephemeral=True)
            return

        selected_entry = results[selected_index]
        try:
            player = await YTDLSource.from_info(selected_entry)
            await self.queue.put({"source": player, "vc": vc, "interaction": interaction})
            if not vc.is_playing():
                self.play_next_song.set()
                await interaction.followup.send(f"▶️ Начинаю воспроизведение: **{player.title}**", ephemeral=True)
            else:
                await interaction.followup.send(f"✅ Трек **{player.title}** добавлен в очередь.", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Ошибка при загрузке трека:\n```{e}```", ephemeral=True)

    async def extract_info(self, url):
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=False))

    async def skip_song(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        if vc and vc.is_playing():
            vc.stop()
            await interaction.response.send_message("⏭️ Текущий трек пропущен.", ephemeral=True)
        else:
            await interaction.response.send_message("❗ Музыка не воспроизводится.", ephemeral=True)

    async def stop_song(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        if vc:
            while not self.queue.empty():
                try:
                    self.queue.get_nowait()
                    self.queue.task_done()
                except asyncio.QueueEmpty:
                    break
            vc.stop()
            await vc.disconnect()
            await interaction.response.send_message("⏹️ Воспроизведение остановлено и очередь очищена.", ephemeral=True)
        else:
            await interaction.response.send_message("❗ Бот не подключён.", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Music(bot))

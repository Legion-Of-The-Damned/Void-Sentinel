import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import wavelink

class ControlView(discord.ui.View):
    def __init__(self, music_cog, interaction):
        super().__init__(timeout=None)
        self.music_cog = music_cog
        self.interaction = interaction

    @discord.ui.button(emoji="⏸️", style=discord.ButtonStyle.gray)
    async def pause_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        player: wavelink.Player = interaction.guild.voice_client
        if player.is_playing():
            await player.pause()
            await interaction.response.send_message("⏸️ Пауза.", ephemeral=True)
        elif player.is_paused():
            await player.resume()
            await interaction.response.send_message("▶️ Продолжение.", ephemeral=True)
        else:
            await interaction.response.send_message("❗ Музыка не воспроизводится.", ephemeral=True)

    @discord.ui.button(emoji="⏭️", style=discord.ButtonStyle.gray)
    async def skip_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.music_cog.skip_song(interaction)

    @discord.ui.button(emoji="⏹️", style=discord.ButtonStyle.gray)
    async def stop_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.music_cog.stop_song(interaction)

    @discord.ui.button(emoji="🔁", style=discord.ButtonStyle.gray)
    async def repeat_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.music_cog.repeat = not self.music_cog.repeat
        status = "включен" if self.music_cog.repeat else "выключен"
        await interaction.response.send_message(f"🔁 Повтор {status}.", ephemeral=True)


class Music(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.queue = asyncio.Queue()
        self.current = None
        self.play_next_song = asyncio.Event()
        self.repeat = False
        self.node = None
        asyncio.create_task(self.player_loop())
        asyncio.create_task(self.connect_node())

    async def connect_node(self):
        # создаём Node без аргумента bot
        self.node = wavelink.Node(
            host='127.0.0.1',
            port=2333,
            password='youshallnotpass'
        )
        await self.node.wait_until_ready()

    async def ensure_voice(self, interaction: discord.Interaction):
        vc: wavelink.Player = interaction.guild.voice_client
        if vc is None:
            if interaction.user.voice:
                vc = await interaction.user.voice.channel.connect(cls=wavelink.Player)
                vc.node = self.node  # привязываем Node
            else:
                await interaction.response.send_message(
                    "❗ Вы не находитесь в голосовом канале.", ephemeral=True
                )
                return None
        return vc

    async def player_loop(self):
        await self.bot.wait_until_ready()
        while True:
            self.play_next_song.clear()
            self.current = await self.queue.get()
            player: wavelink.Player = self.current['player']
            track: wavelink.Track = self.current['track']

            await player.play(track)
            await self.current["interaction"].followup.send(
                embed=discord.Embed(
                    title=f"🎶 Сейчас играет: {track.title}",
                    url=track.uri,
                    color=discord.Color.blue()
                ),
                view=ControlView(self, self.current["interaction"])
            )

            await self.play_next_song.wait()
            if self.repeat:
                await self.queue.put(self.current)

    @app_commands.command(name="играть", description="Играет песню по ссылке или поиску")
    @app_commands.describe(запрос="Ссылка или поисковый запрос для песни")
    async def play(self, interaction: discord.Interaction, запрос: str):
        player = await self.ensure_voice(interaction)
        if player is None:
            return

        await interaction.response.defer()

        if запрос.startswith("http"):
            track = await wavelink.YouTubeTrack.from_url(запрос)
        else:
            track = await wavelink.YouTubeTrack.search(запрос, return_first=True)

        if track is None:
            await interaction.followup.send("❌ Трек не найден.", ephemeral=True)
            return

        await self.queue.put({"track": track, "player": player, "interaction": interaction})
        if not player.is_playing():
            self.play_next_song.set()
            await interaction.followup.send(f"▶️ Начинаю воспроизведение: **{track.title}**", ephemeral=True)
        else:
            await interaction.followup.send(f"✅ Трек **{track.title}** добавлен в очередь.", ephemeral=True)

    async def skip_song(self, interaction: discord.Interaction):
        player: wavelink.Player = interaction.guild.voice_client
        if player and player.is_playing():
            await player.stop()
            await interaction.response.send_message("⏭️ Текущий трек пропущен.", ephemeral=True)
        else:
            await interaction.response.send_message("❗ Музыка не воспроизводится.", ephemeral=True)

    async def stop_song(self, interaction: discord.Interaction):
        player: wavelink.Player = interaction.guild.voice_client
        if player:
            while not self.queue.empty():
                try:
                    self.queue.get_nowait()
                    self.queue.task_done()
                except asyncio.QueueEmpty:
                    break
            await player.stop()
            await player.disconnect()
            await interaction.response.send_message("⏹️ Воспроизведение остановлено и очередь очищена.", ephemeral=True)
        else:
            await interaction.response.send_message("❗ Бот не подключён.", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Music(bot))

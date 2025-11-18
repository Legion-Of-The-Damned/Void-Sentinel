import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import yt_dlp

FFMPEG_OPTIONS = {'options': '-vn'}

YTDL_OPTIONS = {
    'format': 'bestaudio/best',
    'noplaylist': False,
    'quiet': True,
    'extract_flat': False,
    'default_search': 'scsearch',
}


class ControlView(discord.ui.View):
    def __init__(self, music_cog, guild_id):
        super().__init__(timeout=None)
        self.music_cog = music_cog
        self.guild_id = guild_id

    @discord.ui.button(emoji="⏸️", style=discord.ButtonStyle.green)
    async def pause_resume(self, interaction, button):
        queue_data = self.music_cog.guild_queues.get(self.guild_id)
        if not queue_data or not queue_data.get('vc'):
            await interaction.response.defer()
            return

        vc = queue_data['vc']

        if vc.is_playing():
            vc.pause()
            button.emoji = "▶️"
            button.style = discord.ButtonStyle.gray
        elif vc.is_paused():
            vc.resume()
            button.emoji = "⏸️"
            button.style = discord.ButtonStyle.green

        await interaction.response.edit_message(view=self)

    @discord.ui.button(emoji="⏭️", style=discord.ButtonStyle.blurple)
    async def skip(self, interaction, button):
        queue_data = self.music_cog.guild_queues.get(self.guild_id)
        if not queue_data:
            await interaction.response.defer()
            return

        # Помечаем skip и удаляем текущий трек немедленно.
        # Это гарантирует, что repeat не вернёт трек обратно.
        queue_data['skip_requested'] = True
        if queue_data.get('queue'):
            try:
                queue_data['queue'].pop(0)
            except Exception:
                pass

        vc = queue_data.get('vc')
        if vc and (vc.is_playing() or vc.is_paused()):
            vc.stop()

        await interaction.response.defer()

    @discord.ui.button(emoji="⏹️", style=discord.ButtonStyle.red)
    async def stop(self, interaction, button):
        queue_data = self.music_cog.guild_queues.get(self.guild_id)
        if queue_data:
            queue_data['queue'].clear()
            queue_data['skip_requested'] = False
            queue_data['after_running'] = False
            # сигналим after_event чтобы player_loop не висел
            ae = queue_data.get('after_event')
            if ae:
                try:
                    ae.set()
                except Exception:
                    pass

            if queue_data.get('vc'):
                try:
                    await queue_data['vc'].disconnect()
                except Exception:
                    pass

            if queue_data.get('msg'):
                try:
                    await queue_data['msg'].edit(embed=discord.Embed(title="🎵 Очередь очищена"), view=None)
                except Exception:
                    pass

            self.music_cog.guild_queues.pop(self.guild_id, None)

        await interaction.response.defer()

    @discord.ui.button(emoji="🔁", style=discord.ButtonStyle.gray)
    async def repeat(self, interaction, button):
        queue_data = self.music_cog.guild_queues.get(self.guild_id)
        if queue_data:
            queue_data['repeat'] = not queue_data.get('repeat', False)

            if queue_data['repeat']:
                button.style = discord.ButtonStyle.green
            else:
                button.style = discord.ButtonStyle.gray

            # Перерисуем сообщение чтобы кнопка визуально обновилась
            try:
                await interaction.response.edit_message(view=self)
            except Exception:
                # fallback — просто ответим и позволим update_queue_embed обновить view позже
                try:
                    await interaction.response.send_message("🔁 Toggle repeat", ephemeral=True)
                except Exception:
                    pass


class TrackSelect(discord.ui.Select):
    def __init__(self, music_cog, guild_id, tracks):
        self.music_cog = music_cog
        self.guild_id = guild_id

        options = [
            discord.SelectOption(
                label=track['title'][:100],
                description=f"{track.get('uploader', 'Неизвестен')} | {track.get('duration_str', '??:??')}"[:100],
                value=str(idx)
            )
            for idx, track in enumerate(tracks[:25])
        ]

        super().__init__(
            placeholder="Выберите трек",
            min_values=1,
            max_values=1,
            options=options
        )

        self.tracks = tracks

    async def callback(self, interaction):
        idx = int(self.values[0])
        track = self.tracks[idx]

        queue_data = self.music_cog.guild_queues.get(self.guild_id)
        queue_data['queue'].append(track)

        await interaction.response.send_message(
            f"✅ Трек **{track['title']}** добавлен в очередь!",
            ephemeral=True
        )

        msg = await interaction.original_response()
        await asyncio.sleep(3)
        try:
            await msg.delete()
        except Exception:
            pass

        if len(queue_data['queue']) == 1:
            asyncio.create_task(self.music_cog.player_loop(self.guild_id))


class TrackSelectView(discord.ui.View):
    def __init__(self, music_cog, guild_id, tracks):
        super().__init__(timeout=60)
        self.add_item(TrackSelect(music_cog, guild_id, tracks))


class Music(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.guild_queues = {}
        self.guild_locks = {}

    async def ensure_voice(self, interaction):
        if interaction.user.voice and interaction.user.voice.channel:
            return interaction.user.voice.channel

        await interaction.response.send_message("❌ Вы не находитесь в голосовом канале.", ephemeral=True)
        return None

    def format_duration(self, duration):
        try:
            total = int(float(duration))
            m, s = divmod(total, 60)
            return f"{m}:{s:02}"
        except Exception:
            return "??:??"

    async def update_queue_embed(self, guild_id):
        queue_data = self.guild_queues.get(guild_id)
        if not queue_data or not queue_data.get('queue') or not queue_data.get('msg'):
            return

        current = queue_data['queue'][0]
        embed = discord.Embed(title=f"🎶 Сейчас играет: {current['title']}", color=discord.Color.orange())
        embed.add_field(name="Источник:", value="SoundCloud", inline=True)
        embed.add_field(name="Автор:", value=current.get('uploader', 'Неизвестен'), inline=True)
        embed.add_field(name="Длительность:", value=current.get('duration_str', '??:??'), inline=True)

        if current.get('thumbnail'):
            embed.set_thumbnail(url=current['thumbnail'])

        next_tracks = queue_data['queue'][1:6]
        if next_tracks:
            value = "\n".join(f"{idx}. {t['title']} ({t.get('duration_str','??:??')})"
                              for idx, t in enumerate(next_tracks, start=1))
            embed.add_field(name=f"Следующие {len(next_tracks)} трек(а):", value=value, inline=False)
        else:
            embed.add_field(name="Следующие треки:", value="🎵 Очередь пуста", inline=False)

        try:
            await queue_data['msg'].edit(embed=embed, view=ControlView(self, guild_id))
        except Exception:
            pass

    async def after_song_and_next(self, guild_id):
        """
        Обработка окончания трека. Защищаемся от параллельных вызовов.
        В конце — ставим after_event, чтобы player_loop продолжил цикл.
        """
        queue_data = self.guild_queues.get(guild_id)
        if not queue_data:
            return

        # защита от параллельных вызовов
        if queue_data.get('after_running', False):
            # если уже выполняется — просто set event, чтобы player_loop не ждём вечно
            ae = queue_data.get('after_event')
            if ae:
                try:
                    ae.set()
                except Exception:
                    pass
            return

        queue_data['after_running'] = True
        try:
            async with self.guild_locks[guild_id]:
                # если skip был — при нажатии skip трек уже удалили, просто сбрасываем флаг
                if queue_data.get('skip_requested', False):
                    queue_data['skip_requested'] = False
                else:
                    # обычное завершение — удаляем трек только если repeat выключен
                    if queue_data.get('queue') and not queue_data.get('repeat', False):
                        try:
                            queue_data['queue'].pop(0)
                        except Exception:
                            pass

            # обновляем embed / view
            if queue_data.get('msg') and queue_data.get('queue'):
                await self.update_queue_embed(guild_id)
            elif queue_data.get('msg'):
                try:
                    await queue_data['msg'].edit(embed=discord.Embed(title="🎵 Очередь пуста"), view=None)
                except Exception:
                    pass
        finally:
            # сигналим player_loop что обработка завершена
            ae = queue_data.get('after_event')
            if ae:
                try:
                    ae.set()
                except Exception:
                    pass
            queue_data['after_running'] = False

    async def player_loop(self, guild_id):
        """
        Цикл воспроизведения. После окончания воспроизведения ждём завершения after_song_and_next
        через asyncio.Event (after_event) — это устраняет гонки и делает repeat стабильным.
        """
        queue_data = self.guild_queues.get(guild_id)
        if not queue_data:
            return

        vc = queue_data['vc']
        lock = self.guild_locks.setdefault(guild_id, asyncio.Lock())

        while queue_data.get('queue'):
            # защитная проверка
            if not queue_data.get('queue'):
                break

            try:
                current = queue_data['queue'][0]
            except Exception:
                break

            url = current.get('url')
            if not url:
                async with lock:
                    try:
                        queue_data['queue'].pop(0)
                    except Exception:
                        pass
                continue

            # подготовим after_event для синхронизации
            queue_data['after_event'] = asyncio.Event()
            # source создаём прямо перед play
            source = discord.FFmpegPCMAudio(url, **FFMPEG_OPTIONS)

            def after_play(error):
                # запускаем обработку окончания в event loop
                try:
                    asyncio.run_coroutine_threadsafe(self.after_song_and_next(guild_id), self.bot.loop)
                except Exception:
                    pass

            try:
                vc.play(source, after=after_play)
            except Exception:
                # если play упал — убираем трек и продолжаем
                async with lock:
                    try:
                        queue_data['queue'].pop(0)
                    except Exception:
                        pass
                await asyncio.sleep(0.5)
                continue

            # создаём/обновляем сообщение статуса если нужно
            if queue_data.get('msg') is None:
                try:
                    msg = await current['interaction'].followup.send(embed=discord.Embed(title="🎶 Загружается..."),
                                                                    view=ControlView(self, guild_id))
                    queue_data['msg'] = msg
                except Exception:
                    pass

            await self.update_queue_embed(guild_id)

            # ждём пока ffmpeg не завершит проигрывание (или пока не будет паузы/стоп)
            while vc.is_playing() or vc.is_paused():
                await asyncio.sleep(1)

            # ждем, пока after_song_and_next сделает свою работу (упадёт флаг after_event)
            ae = queue_data.get('after_event')
            if ae:
                try:
                    # ждём до небольшого таймаута — на случай проблем
                    await asyncio.wait_for(ae.wait(), timeout=5.0)
                except asyncio.TimeoutError:
                    # если after_song завис — продолжим, но это не должно обычно случаться
                    pass
                finally:
                    # очищаем поле, чтобы в следующей итерации повесить новый Event
                    queue_data['after_event'] = None

            # цикл повторится и возьмёт уже актуальный первый элемент очереди

        # очистка после окончания очереди
        try:
            if vc.is_connected():
                await vc.disconnect()
        except Exception:
            pass

        # удаляем гильдийные данные
        try:
            self.guild_queues.pop(guild_id, None)
            self.guild_locks.pop(guild_id, None)
        except Exception:
            pass

    @app_commands.command(name="играть", description="Играет песню или плейлист (только SoundCloud)")
    @app_commands.describe(запрос="Название песни или ссылка на SoundCloud")
    async def play(self, interaction, запрос: str):
        channel = await self.ensure_voice(interaction)
        if not channel:
            return

        await interaction.response.defer(thinking=True)

        guild_id = interaction.guild.id
        queue_data = self.guild_queues.get(guild_id)

        if not queue_data:
            vc = await channel.connect()
            self.guild_queues[guild_id] = {
                'queue': [],
                'vc': vc,
                'repeat': False,
                'msg': None,
                'skip_requested': False,
                'after_running': False,
                'after_event': None
            }
            queue_data = self.guild_queues[guild_id]
        else:
            vc = queue_data['vc']
            if not vc.is_connected():
                vc = await channel.connect()
                queue_data['vc'] = vc

        try:
            search_str = f"scsearch:{запрос}" if not запрос.startswith("http") else запрос
            with yt_dlp.YoutubeDL(YTDL_OPTIONS) as ydl:
                info = ydl.extract_info(search_str, download=False)

            entries = info['entries'] if 'entries' in info else [info]
            tracks = []
            for entry in entries:
                tracks.append({
                    'url': entry.get('url'),
                    'title': entry.get('title', 'Неизвестная песня'),
                    'interaction': interaction,
                    'uploader': entry.get('uploader', 'Неизвестен'),
                    'duration_str': self.format_duration(entry.get('duration', 0)),
                    'thumbnail': entry.get('thumbnail')
                })
        except Exception as e:
            await interaction.followup.send(f"❌ Ошибка при поиске: {e}", ephemeral=True)
            return

        if len(tracks) > 1:
            await interaction.followup.send("🔎 Выберите трек из результатов:", view=TrackSelectView(self, guild_id, tracks), ephemeral=True)
            return

        track = tracks[0]
        queue_data['queue'].append(track)

        msg = await interaction.followup.send(f"✅ Трек **{track['title']}** добавлен в очередь!", ephemeral=True)
        await asyncio.sleep(3)
        try:
            await msg.delete()
        except Exception:
            pass

        if queue_data.get('msg'):
            await self.update_queue_embed(guild_id)
        else:
            asyncio.create_task(self.player_loop(guild_id))


async def setup(bot):
    await bot.add_cog(Music(bot))

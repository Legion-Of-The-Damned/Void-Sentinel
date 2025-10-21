import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import yt_dlp
import os

FFMPEG_OPTIONS = {
    'options': '-vn'
}

YTDL_OPTIONS = {
    'format': 'bestaudio/best',
    'noplaylist': True,
    'quiet': True,
    'extract_flat': False,
    'default_search': 'ytsearch',
    'cookiefile': 'cogs/cookies.txt',  # Твой файл cookies
}

class ControlView(discord.ui.View):
    def __init__(self, music_cog, user_id):
        super().__init__(timeout=None)
        self.music_cog = music_cog
        self.user_id = user_id

    @discord.ui.button(emoji="⏸️", style=discord.ButtonStyle.gray)
    async def pause_resume(self, interaction: discord.Interaction, button: discord.ui.Button):
        queue_data = self.music_cog.user_queues.get(self.user_id)
        if queue_data and queue_data['vc']:
            vc = queue_data['vc']
            if vc.is_playing():
                vc.pause()
                await interaction.response.send_message("⏸ Музыка на паузе.", ephemeral=True)
            elif vc.is_paused():
                vc.resume()
                await interaction.response.send_message("▶️ Музыка продолжена.", ephemeral=True)
            else:
                await interaction.response.send_message("❌ Музыка не воспроизводится.", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Музыка не воспроизводится.", ephemeral=True)

    @discord.ui.button(emoji="⏭️", style=discord.ButtonStyle.gray)
    async def skip(self, interaction: discord.Interaction, button: discord.ui.Button):
        queue_data = self.music_cog.user_queues.get(self.user_id)
        if queue_data and queue_data['vc'] and queue_data['vc'].is_playing():
            queue_data['vc'].stop()
            await interaction.response.send_message("⏭ Трек пропущен.", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Музыка не воспроизводится.", ephemeral=True)

    @discord.ui.button(emoji="⏹️", style=discord.ButtonStyle.gray)
    async def stop(self, interaction: discord.Interaction, button: discord.ui.Button):
        queue_data = self.music_cog.user_queues.get(self.user_id)
        if queue_data:
            queue_data['queue'].clear()
            if queue_data['vc']:
                await queue_data['vc'].disconnect()
            self.music_cog.user_queues.pop(self.user_id, None)
            await interaction.response.send_message("⏹ Музыка остановлена и очередь очищена.", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Музыка не воспроизводится.", ephemeral=True)

    @discord.ui.button(emoji="🔁", style=discord.ButtonStyle.gray)
    async def repeat(self, interaction: discord.Interaction, button: discord.ui.Button):
        queue_data = self.music_cog.user_queues.get(self.user_id)
        if queue_data:
            queue_data['repeat'] = not queue_data['repeat']
            status = "включен" if queue_data['repeat'] else "выключен"
            await interaction.response.send_message(f"🔁 Повтор {status}.", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Музыка не воспроизводится.", ephemeral=True)


class Music(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.user_queues = {}  # ключ: user_id, значение: {queue, vc, repeat, current}

    async def ensure_voice(self, interaction: discord.Interaction):
        if interaction.user.voice and interaction.user.voice.channel:
            return interaction.user.voice.channel
        else:
            await interaction.response.send_message("❌ Вы не находитесь в голосовом канале.", ephemeral=True)
            return None

    async def player_loop(self, user_id):
        queue_data = self.user_queues[user_id]
        while queue_data['queue']:
            current = queue_data['queue'][0]
            vc = queue_data['vc']

            def after_play(error):
                fut = self.bot.loop.create_task(self.after_song(user_id))
                try:
                    fut.result()
                except:
                    pass

            vc.play(current['source'], after=after_play)

            # Embed с текущим и 5 следующими треками
            embed = discord.Embed(title=f"🎶 Сейчас играет: {current['title']}", color=discord.Color.blue())
            next_tracks = queue_data['queue'][1:6]
            if next_tracks:
                embed.add_field(name="Следующие треки:", value="\n".join([t['title'] for t in next_tracks]), inline=False)

            # Отправляем или редактируем сообщение, чтобы видеть обновленную очередь
            if queue_data.get('msg') is None:
                msg = await current['interaction'].followup.send(embed=embed, view=ControlView(self, user_id))
                queue_data['msg'] = msg
            else:
                try:
                    await queue_data['msg'].edit(embed=embed, view=ControlView(self, user_id))
                except:
                    # Если сообщение удалено, отправляем новое
                    msg = await current['interaction'].followup.send(embed=embed, view=ControlView(self, user_id))
                    queue_data['msg'] = msg

            await asyncio.sleep(1)
            while vc.is_playing() or vc.is_paused():
                await asyncio.sleep(1)
            if not queue_data['repeat']:
                queue_data['queue'].pop(0)

        # Очередь пустая — отключаемся
        if vc.is_connected():
            await vc.disconnect()
        self.user_queues.pop(user_id, None)

    async def after_song(self, user_id):
        queue_data = self.user_queues.get(user_id)
        if queue_data and queue_data['queue']:
            if queue_data['repeat']:
                # Если повтор включен, не убираем первый трек
                return
            queue_data['queue'].pop(0)
            # Обновляем embed с очередью после каждого трека
            if queue_data['queue'] and queue_data.get('msg'):
                next_tracks = queue_data['queue'][:5]
                embed = discord.Embed(title=f"🎶 Сейчас играет: {queue_data['queue'][0]['title']}", color=discord.Color.blue())
                if next_tracks[1:]:
                    embed.add_field(name="Следующие треки:", value="\n".join([t['title'] for t in next_tracks[1:]]), inline=False)
                try:
                    await queue_data['msg'].edit(embed=embed, view=ControlView(self, user_id))
                except:
                    pass

    @app_commands.command(name="играть", description="Играет песню по названию или ссылке")
    @app_commands.describe(запрос="Название песни или ссылка")
    async def play(self, interaction: discord.Interaction, запрос: str):
        channel = await self.ensure_voice(interaction)
        if not channel:
            return

        await interaction.response.defer()

        if not os.path.isfile(YTDL_OPTIONS['cookiefile']):
            await interaction.followup.send("❌ Файл cookies не найден!", ephemeral=True)
            return

        user_id = interaction.user.id
        queue_data = self.user_queues.get(user_id)

        if not queue_data:
            vc = await channel.connect()
            self.user_queues[user_id] = {
                'queue': [],
                'vc': vc,
                'repeat': False,
                'current': None,
                'msg': None
            }
            queue_data = self.user_queues[user_id]
        else:
            vc = queue_data['vc']
            if not vc.is_connected():
                vc = await channel.connect()
                queue_data['vc'] = vc

        # Загружаем трек
        try:
            with yt_dlp.YoutubeDL(YTDL_OPTIONS) as ydl:
                info = ydl.extract_info(запрос, download=False)
                if 'entries' in info:
                    info = info['entries'][0]
                url = info['url']
                title = info.get('title', 'Неизвестная песня')
        except Exception as e:
            await interaction.followup.send(f"❌ Ошибка загрузки трека: {e}", ephemeral=True)
            return

        source = discord.FFmpegPCMAudio(url, **FFMPEG_OPTIONS)
        queue_data['queue'].append({'source': source, 'title': title, 'interaction': interaction})

        if len(queue_data['queue']) == 1:
            # Запускаем player loop
            asyncio.create_task(self.player_loop(user_id))
        else:
            await interaction.followup.send(f"✅ Трек **{title}** добавлен в очередь.", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Music(bot))

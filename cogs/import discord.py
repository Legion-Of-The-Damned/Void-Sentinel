import discord
from discord.ext import commands
import asyncio
import yt_dlp
import logging

logger = logging.getLogger("music")

class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.queues = {}  # хранение очередей по guild.id

    def get_queue(self, guild_id):
        if guild_id not in self.queues:
            self.queues[guild_id] = {"queue": [], "now_playing": None, "loop": False}
        return self.queues[guild_id]

    async def play_next(self, interaction):
        queue_data = self.get_queue(interaction.guild.id)
        try:
            if queue_data["loop"] and queue_data["now_playing"]:
                queue_data["queue"].append(queue_data["now_playing"])

            if queue_data["queue"]:
                next_song = queue_data["queue"].pop(0)
                await self.play_song(interaction, next_song)
            else:
                vc = interaction.guild.voice_client
                if vc and vc.is_connected():
                    await vc.disconnect()
                queue_data["now_playing"] = None
                logger.info(f"🎵 Очередь пуста, бот отключён от {interaction.guild.name}")
        except IndexError:
            # Очередь пуста, безопасно игнорируем
            queue_data["now_playing"] = None
            vc = interaction.guild.voice_client
            if vc and vc.is_connected():
                await vc.disconnect()
            logger.info(f"🎵 Очередь пуста, бот отключён от {interaction.guild.name}")

    async def play_song(self, interaction, url):
        queue_data = self.get_queue(interaction.guild.id)
        ydl_opts = {
            "format": "bestaudio",
            "quiet": True,
            "default_search": "ytsearch",
            "noplaylist": True
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                if "entries" in info:
                    info = info["entries"][0]
                url2 = info["url"]
                title = info["title"]
        except yt_dlp.utils.DownloadError as e:
            await interaction.followup.send(f"❌ Ошибка при загрузке видео: {e}", ephemeral=True)
            logger.error(f"Ошибка yt-dlp для {url}: {e}")
            await self.play_next(interaction)
            return
        except Exception as e:
            await interaction.followup.send(f"❌ Произошла ошибка: {e}", ephemeral=True)
            logger.error(f"Ошибка воспроизведения {url}: {e}")
            await self.play_next(interaction)
            return

        vc = interaction.guild.voice_client
        if not vc:
            if interaction.user.voice and interaction.user.voice.channel:
                vc = await interaction.user.voice.channel.connect()
            else:
                await interaction.followup.send("❌ Ты должен быть в голосовом канале!", ephemeral=True)
                return

        ffmpeg_opts = {
            "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
            "options": "-vn"
        }

        try:
            source = await discord.FFmpegOpusAudio.from_probe(url2, **ffmpeg_opts)
            vc.play(
                source, 
                after=lambda e: asyncio.run_coroutine_threadsafe(self.play_next(interaction), self.bot.loop)
            )
            queue_data["now_playing"] = title
            await interaction.followup.send(f"🎶 Сейчас играет: **{title}**")
        except Exception as e:
            await interaction.followup.send(f"❌ Ошибка при воспроизведении аудио: {e}", ephemeral=True)
            logger.error(f"Ошибка ffmpeg для {url}: {e}")
            await self.play_next(interaction)

    @commands.command(name="play")
    async def play_command(self, ctx, *, url: str):
        """Проигрывает музыку с YouTube"""
        queue_data = self.get_queue(ctx.guild.id)
        queue_data["queue"].append(url)
        vc = ctx.guild.voice_client
        if not vc or not vc.is_playing():
            await self.play_next(ctx)
        else:
            await ctx.send(f"➕ Трек добавлен в очередь: {url}")

    @commands.command(name="skip")
    async def skip_command(self, ctx):
        """Пропускает текущий трек"""
        vc = ctx.guild.voice_client
        if vc and vc.is_playing():
            vc.stop()
            await ctx.send("⏭ Пропущено.")
        else:
            await ctx.send("⚠ Нечего пропускать.")

    @commands.command(name="stop")
    async def stop_command(self, ctx):
        """Останавливает музыку и очищает очередь"""
        vc = ctx.guild.voice_client
        if vc:
            await vc.disconnect()
        self.queues.pop(ctx.guild.id, None)
        await ctx.send("🛑 Музыка остановлена и очередь очищена.")


async def setup(bot):
    """Асинхронная точка входа для cogs"""
    await bot.add_cog(Music(bot))

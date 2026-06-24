import discord
from discord.ext import commands
import logging

# получаем логгер для этого модуля
logger = logging.getLogger("voice")
logger.setLevel(logging.DEBUG)
logger.propagate = True


class TempVoice(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        # ⚙️ НАСТРОЙКИ
        self.JOIN_CHANNEL_ID = 1501702045449846950  # канал-триггер
        self.CATEGORY_ID = 1281549728026198017     # категория для временных каналов

        # хранение каналов
        self.temp_channels = {}  # channel_id: owner_id

    # ---------- VOICE EVENT ----------
    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        try:
            # ---------- JOIN TRIGGER ----------
            if after.channel and after.channel.id == self.JOIN_CHANNEL_ID:
                guild = member.guild

                category = guild.get_channel(self.CATEGORY_ID)
                if not category:
                    logger.error("Категория не найдена")
                    return

                # чистим имя
                username = member.display_name.replace("|", "").strip()[:20]
                channel_name = f"- |🔊Вокс {username}🔊| -"

                # создаём канал
                channel = await guild.create_voice_channel(
                    name=channel_name,
                    category=category
                )

                self.temp_channels[channel.id] = member.id

                logger.success(f"Создан временный войс: {channel.name} ({member})")

                # переносим пользователя
                await member.move_to(channel)

            # ---------- DELETE IF EMPTY ----------
            if before.channel:
                channel = before.channel

                if channel.id in self.temp_channels:
                    if len(channel.members) == 0:
                        await channel.delete()
                        self.temp_channels.pop(channel.id, None)

                        logger.success(f"Удалён пустой войс: {channel.id}")

        except Exception as e:
            logger.critical(f"Ошибка TempVoice: {e}")


async def setup(bot):
    await bot.add_cog(TempVoice(bot))
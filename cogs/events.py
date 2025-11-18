import discord
import logging
from discord.ext import commands

# --- Настройка логгера для этого кога ---
logger = logging.getLogger("Events")

class Events(commands.Cog):
    def __init__(self, bot, avatar_url, image_url):
        self.bot = bot
        self.avatar_url = avatar_url
        self.image_url = image_url

    async def send_welcome_message(self, member, webhook):
        guild = member.guild
        message_content = f"Добро пожаловать на сервер {guild.name}, {member.mention}!"
        embed = discord.Embed(
            color=0xEDC93D,
            title="Мы рады видеть тебя в нашем сообществе! Надеемся, что тебе здесь понравится!"
        )

        guild_icon_url = guild.icon.url if guild.icon else None
        if guild_icon_url:
            embed.set_thumbnail(url=guild_icon_url)

        embed.add_field(
            name="Пожалуйста, ознакомься с правилами, чтобы избежать недоразумений!",
            value="",
        )
        embed.set_image(url=self.image_url)

        try:
            await webhook.send(
                content=message_content,
                embed=embed,
                avatar_url=self.avatar_url
            )
            logger.info(f"✅ Отправлено приветственное сообщение для {member} ({member.id})")
        except Exception as e:
            logger.error(f"❌ Не удалось отправить приветственное сообщение для {member} ({member.id}): {e}")

    async def send_farewell_message(self, member, webhook):
        guild = member.guild
        message_content = f"{member.name} покинул сервер {guild.name}."
        embed = discord.Embed(
            color=0xFF0000,
            title="Участник покинул сервер",
            description=f"{member.name} больше не с нами."
        )

        guild_icon_url = guild.icon.url if guild.icon else None
        if guild_icon_url:
            embed.set_thumbnail(url=guild_icon_url)

        try:
            await webhook.send(
                content=message_content,
                embed=embed,
                avatar_url=self.avatar_url
            )
            logger.info(f"✅ Отправлено сообщение об уходе {member} ({member.id})")
        except Exception as e:
            logger.error(f"❌ Не удалось отправить сообщение об уходе для {member} ({member.id}): {e}")

    async def create_webhook_and_send_message(self, channel, member, message_func):
        try:
            webhook = await channel.create_webhook(name="Void Sentinel")
            logger.info(f"Webhook создан в канале: {channel.name} ({channel.id})")
            await message_func(member, webhook)
            await webhook.delete()
            logger.info(f"Webhook удалён из канала: {channel.name} ({channel.id})")
        except Exception as e:
            logger.error(f"❌ Не удалось создать вебхук или отправить сообщение в канале {channel.name} ({channel.id}): {e}")

    @commands.Cog.listener()
    async def on_member_join(self, member):
        guild = member.guild
        welcome_channel = guild.system_channel or next(
            (channel for channel in guild.text_channels if channel.permissions_for(guild.me).send_messages),
            None
        )

        if welcome_channel:
            logger.info(f"{member} ({member.id}) присоединился к серверу {guild.name}")
            await self.create_webhook_and_send_message(welcome_channel, member, self.send_welcome_message)
        else:
            logger.error(f"❌ Нет доступного канала на сервере {guild.name} для приветственного сообщения")

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        guild = member.guild
        farewell_channel = guild.system_channel or next(
            (channel for channel in guild.text_channels if channel.permissions_for(guild.me).send_messages),
            None
        )

        if farewell_channel:
            logger.info(f"{member} ({member.id}) покинул сервер {guild.name}")
            await self.create_webhook_and_send_message(farewell_channel, member, self.send_farewell_message)
        else:
            logger.error(f"❌ Нет доступного канала на сервере {guild.name} для сообщения об уходе")

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        """Отслеживает получение клановой роли и пишет игроку в ЛС"""
        clan_role_id = 1418038359129063585  # 🔹 замени на ID роли клана
        clan_role = after.guild.get_role(clan_role_id)
        if not clan_role:
            logger.warning(f"Роль с ID {clan_role_id} не найдена на сервере {after.guild.name}")
            return

        # Проверяем: раньше роли не было, теперь появилась
        if clan_role not in before.roles and clan_role in after.roles:
            try:
                await after.send(
                    f"Привет, {after.display_name}! ✅ "
                    f"Вы успешно верифицированы на сервере.\n\n"
                    f"Если вы хотите полноценно вступить в клан, введите команду `/заявка`."
                )
                logger.info(f"💬 Отправлено ЛС пользователю {after.display_name} о вступлении в клан.")
            except discord.Forbidden:
                logger.debug(f"Не удалось отправить ЛС пользователю {after.display_name} — личка закрыта.")
            except Exception as e:
                logger.error(f"Ошибка при отправке ЛС пользователю {after.display_name}: {e}")

async def setup(bot):
    from config import load_config
    config = load_config()
    await bot.add_cog(Events(bot, config["AVATAR_URL"], config["IMAGE_URL"]))
import discord
import logging
from discord.ext import commands
from discord import AuditLogAction

# получаем логгер для этого модуля
logger = logging.getLogger("Events")


class Events(commands.Cog):
    def __init__(self, bot, avatar_url, banner_url):
        self.bot = bot
        self.avatar_url = avatar_url
        self.banner_url = banner_url

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
            value=""
        )

        embed.set_image(url=self.banner_url)

        try:
            await webhook.send(
                content=message_content,
                embed=embed,
                avatar_url=self.avatar_url
            )
            logger.info(f"✅ Отправлено приветствие {member} ({member.id})")

        except Exception as e:
            logger.error(f"❌ Ошибка приветствия {member}: {e}")

    async def send_farewell_message(self, member, webhook, reason_type="leave", moderator=None):
        guild = member.guild

        if reason_type == "kick":
            title = "Участник был кикнут"
            description = f"{member.name} был исключён с сервера."
            color = 0xFFA500
            extra = f"\nМодератор: {moderator}" if moderator else ""

        elif reason_type == "ban":
            title = "Участник был забанен"
            description = f"{member.name} получил бан."
            color = 0x8B0000
            extra = f"\nМодератор: {moderator}" if moderator else ""

        else:
            title = "Участник вышел"
            description = f"{member.name} покинул сервер."
            color = 0xFF0000
            extra = ""

        message_content = f"{member.name} покинул сервер {guild.name}."

        embed = discord.Embed(
            color=color,
            title=title,
            description=description + extra
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
            logger.info(f"✅ Уход {member} ({member.id}) [{reason_type}]")

        except Exception as e:
            logger.error(f"❌ Ошибка ухода {member}: {e}")

    async def create_webhook_and_send_message(self, channel, member, message_func):
        try:
            webhook = await channel.create_webhook(name="Void Sentinel")
            logger.info(f"Webhook создан: {channel.name} ({channel.id})")

            await message_func(member, webhook)

            await webhook.delete()
            logger.info(f"Webhook удалён: {channel.name} ({channel.id})")

        except Exception as e:
            logger.error(f"❌ Ошибка webhook в {channel.name}: {e}")

    @commands.Cog.listener()
    async def on_member_join(self, member):
        guild = member.guild

        welcome_channel = guild.system_channel or next(
            (
                channel for channel in guild.text_channels
                if channel.permissions_for(guild.me).send_messages
            ),
            None
        )

        if not welcome_channel:
            logger.error(f"❌ Нет канала для приветствия на сервере {guild.name}")
            return

        logger.info(f"{member} ({member.id}) зашёл на сервер {guild.name}")

        await self.create_webhook_and_send_message(
            welcome_channel,
            member,
            self.send_welcome_message
        )

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        guild = member.guild

        farewell_channel = guild.system_channel or next(
            (
                channel for channel in guild.text_channels
                if channel.permissions_for(guild.me).send_messages
            ),
            None
        )

        if not farewell_channel:
            logger.error(f"❌ Нет канала для ухода на сервере {guild.name}")
            return

        reason_type = "leave"
        moderator = None

        try:
            async for entry in guild.audit_logs(limit=5):

                # используем timezone-aware время
                if (discord.utils.utcnow() - entry.created_at).total_seconds() > 10:
                    continue

                if entry.target.id != member.id:
                    continue

                if entry.action == AuditLogAction.kick:
                    reason_type = "kick"
                    moderator = entry.user
                    break

                elif entry.action == AuditLogAction.ban:
                    reason_type = "ban"
                    moderator = entry.user
                    break

        except Exception as e:
            logger.error(f"Ошибка аудит логов: {e}")

        logger.info(f"{member} ({member.id}) вышел [{reason_type}]")

        await self.create_webhook_and_send_message(
            farewell_channel,
            member,
            lambda m, w: self.send_farewell_message(
                m,
                w,
                reason_type,
                moderator
            )
        )

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        clan_role_id = 1418038359129063585
        clan_role = after.guild.get_role(clan_role_id)

        if not clan_role:
            logger.warning(f"Роль {clan_role_id} не найдена на {after.guild.name}")
            return

        if clan_role not in before.roles and clan_role in after.roles:
            try:
                await after.send(
                    f"Привет, {after.display_name}! ✅\n\n"
                    f"Вы успешно верифицированы.\n"
                    f"Для вступления в клан используй `/заявка`."
                )

                logger.info(f"ЛС отправлено {after.display_name}")

            except discord.Forbidden:
                logger.debug(f"ЛС закрыто у {after.display_name}")

            except Exception as e:
                logger.error(f"Ошибка ЛС {after.display_name}: {e}")


async def setup(bot):
    from config import load_config

    config = load_config()

    await bot.add_cog(
        Events(
            bot,
            config["AVATAR_URL"],
            config["BANNER_URL"]
        )
    )
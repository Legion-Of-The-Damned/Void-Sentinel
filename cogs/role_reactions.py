import discord
from discord.ext import commands
import os
import logging

logger = logging.getLogger("role_reactions")

class RoleReactionsWebhook(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.role_channel_id = 1273350157257146388  # ID канала для выбора ролей

        # === Роли-секции ===
        self.section_roles = [
            "ㅤㅤㅤㅤㅤㅤㅤИгры: ㅤㅤㅤㅤㅤㅤㅤㅤ",
            "ㅤㅤㅤㅤㅤㅤㅤДругое:ㅤㅤㅤㅤㅤㅤㅤ"
        ]

        # === Секции с ролями ===
        self.sections = {
            "🎮 Игры:": {
                "⚔️": ("ECR", "Warhammer 40,000 Eternal Crusade Resurrection"),
                "💀": ("DWC", "Warhammer 40,000 Deathwatch Chronicles"),
                "🎯": ("TF2", "Team Fortress 2"),
                "🌎": ("WOW", "World Of Warcraft Sirus"),
                "🏜️": ("Arizona", "Arizona Kingman"),
                "🧟": ("L4D2", "Left 4 Dead 2"),
            },
            "📦 Другое:": {
                "🤖": ("Техножрец", "Техножрец (Открывает доступ к ктегории по разработке программ и бота)"),
                "👽": ("Киноман", "Киноман"),
            }
        }

        # Плоский словарь для выдачи ролей по эмодзи
        self.emoji_roles = {
            emoji: short for section in self.sections.values() for emoji, (short, _) in section.items()
        }

        # Путь к файлу с ID сообщения
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        data_folder = os.path.join(base_path, "data")
        os.makedirs(data_folder, exist_ok=True)
        self.role_message_file = os.path.join(data_folder, "role_message_id.txt")

        self.role_message_id = None
        self.load_role_message_id()

    def load_role_message_id(self):
        """Загрузка ID сообщения из файла"""
        if os.path.exists(self.role_message_file):
            try:
                with open(self.role_message_file, "r") as f:
                    self.role_message_id = int(f.read().strip())
                    logger.success(f"Загружен ID сообщения для ролей: {self.role_message_id}")
            except Exception as e:
                logger.warning(f"Не удалось загрузить ID сообщения: {e}")

    def save_role_message_id(self):
        """Сохранение ID сообщения в файл"""
        try:
            with open(self.role_message_file, "w") as f:
                f.write(str(self.role_message_id))
            logger.success(f"Сохранён ID сообщения: {self.role_message_id}")
        except Exception as e:
            logger.error(f"Не удалось сохранить ID сообщения: {e}")

    async def ensure_section_roles(self, guild):
        """Создаёт недостающие роли-секции"""
        for role_name in self.section_roles:
            if not discord.utils.get(guild.roles, name=role_name):
                await guild.create_role(name=role_name, hoist=False, mentionable=False)
                logger.info(f"Создана недостающая роль-секция: {role_name}")

    async def create_role_message(self, channel):
        """Создание нового сообщения с ролями"""
        description_lines = ["✠ **Выберите свою роль, чтобы указать во что вы играете и чтобы открыть доступ к каналам** ✠\n"]
        for section_title, roles in self.sections.items():
            description_lines.append(f"\n{section_title}")
            for emoji, (short, full) in roles.items():
                description_lines.append(f"{emoji} — **{short}** 〰️ *{full}*")

        embed = discord.Embed(
            title="⚔️ Панель выбора ролей ⚔️",
            description="\n".join(description_lines),
            color=discord.Color.red()
        )
        embed.set_footer(text="Нажмите на реакцию ниже, чтобы получить или убрать роль.")

        webhooks = await channel.webhooks()
        webhook = webhooks[0] if webhooks else await channel.create_webhook(name="Role Reactions Webhook")

        message = await webhook.send(
            embed=embed,
            wait=True,
            username=self.bot.user.name,
            avatar_url=str(self.bot.user.display_avatar.url)
        )

        for emoji in self.emoji_roles:
            await message.add_reaction(emoji)

        self.role_message_id = message.id
        self.save_role_message_id()
        logger.success(f"Создано новое сообщение для ролей с ID {self.role_message_id}")

    @commands.Cog.listener()
    async def on_ready(self):
        channel = self.bot.get_channel(self.role_channel_id)
        if not channel:
            logger.error(f"Канал для выбора ролей с ID {self.role_channel_id} не найден!")
            return

        guild = channel.guild
        await self.ensure_section_roles(guild)

        message = None
        if self.role_message_id:
            try:
                message = await channel.fetch_message(self.role_message_id)
                logger.info(f"Используем существующее сообщение с ID {self.role_message_id}")
            except discord.NotFound:
                logger.warning("Старое сообщение не найдено, создаём новое.")

        if not message:
            await self.create_role_message(channel)

    async def modify_member_role(self, payload, add=True):
        """Выдача или снятие роли с пользователя вместе с ролью-секцией"""
        if payload.user_id == self.bot.user.id:
            return

        guild = self.bot.get_guild(payload.guild_id)
        member = guild.get_member(payload.user_id)
        if not member:
            logger.warning(f"Пользователь с ID {payload.user_id} не найден в гильдии {guild.name}")
            return

        # Получаем выбранную роль
        role_name = self.emoji_roles.get(str(payload.emoji))
        if not role_name:
            return

        role = discord.utils.get(guild.roles, name=role_name)
        if not role:
            logger.warning(f"Роль {role_name} не найдена в гильдии {guild.name}")
            return

        # Находим секцию, к которой принадлежит эта роль
        section_role_name = None
        for section_title, roles in self.sections.items():
            if any(role_name == short for short, _ in roles.values()):
                if section_title == "🎮 Игры:":
                    section_role_name = "ㅤㅤㅤㅤㅤㅤㅤИгры: ㅤㅤㅤㅤㅤㅤㅤㅤ"
                elif section_title == "📦 Другое:":
                    section_role_name = "ㅤㅤㅤㅤㅤㅤㅤДругое:ㅤㅤㅤㅤㅤㅤㅤ"
                break

        section_role = discord.utils.get(guild.roles, name=section_role_name) if section_role_name else None

        try:
            if add:
                await member.add_roles(role)
                if section_role:
                    await member.add_roles(section_role)
                logger.success(f"Выдана роль {role_name} пользователю {member}")
            else:
                await member.remove_roles(role)
                # Проверяем, есть ли другие роли из этой секции — если нет, убираем секцию
                if section_role:
                    still_has_role_in_section = any(
                        discord.utils.get(guild.roles, name=short) in member.roles
                        for short, _ in self.sections[section_title].values()
                    )
                    if not still_has_role_in_section:
                        await member.remove_roles(section_role)
                logger.success(f"Убрана роль {role_name} у пользователя {member}")
        except discord.Forbidden:
            logger.error(f"Нет прав для изменения роли {role_name} у {member}")

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        if payload.message_id != self.role_message_id:
            return
        await self.modify_member_role(payload, add=True)

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload):
        if payload.message_id != self.role_message_id:
            return
        await self.modify_member_role(payload, add=False)


async def setup(bot):
    await bot.add_cog(RoleReactionsWebhook(bot))

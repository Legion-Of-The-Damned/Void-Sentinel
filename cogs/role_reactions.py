import discord
from discord.ext import commands
import os
import logging

logger = logging.getLogger("role_reactions")

class RoleReactionsWebhook(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.role_channel_id = 1460790284261658851  # ID канала для выбора ролей

        # === Роль-секция ===
        self.section_role_name = "ㅤㅤㅤㅤㅤㅤㅤКлассы:ㅤㅤㅤㅤㅤㅤㅤ"

        # === Секция с ролями ===
        self.sections = {
            "🛡️ Классы:": {
                # SCX
                "🟥": ("SCX Ралик", "SCX Ралик"),
                "🟦": ("SCX Штурма", "SCX Штурма"),
                "🟩": ("SCX Био-штурма", "SCX Био-штурма"),

                # TF2
                "🏃": ("TF2 Разведчик", "TF2 Разведчик"),
                "🎖️": ("TF2 Солдат", "TF2 Солдат"),
                "🔥": ("TF2 Поджигатель", "TF2 Поджигатель"),
                "💣": ("TF2 Подрывник", "TF2 Подрывник"),
                "🔫": ("TF2 Пулемётчик", "TF2 Пулемётчик"),
                "🔧": ("TF2 Инженер", "TF2 Инженер"),
                "💉": ("TF2 Медик", "TF2 Медик"),
                "🎯": ("TF2 Снайпер", "TF2 Снайпер"),
                "🕵️": ("TF2 Шпион", "TF2 Шпион"),

                # ECR
                "⚔️": ("ECR Тактик", "ECR Тактик"),
                "🛡️": ("ECR Авангард", "ECR Авангард"),
                "🦅": ("ECR Раптор", "ECR Раптор"),
                "🤖": ("ECR Антитех", "ECR Антитех"),
                "🧬": ("ECR Апотекарий", "ECR Апотекарий"),
                "💥": ("ECR Хавок", "ECR Хавок"),
            }
        }

        # Плоский словарь: эмодзи -> название роли
        self.emoji_roles = {
            emoji: short
            for roles in self.sections.values()
            for emoji, (short, _) in roles.items()
        }

        # Файл с ID сообщения
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        data_folder = os.path.join(base_path, "data")
        os.makedirs(data_folder, exist_ok=True)
        self.role_message_file = os.path.join(data_folder, "role_message_id.txt")

        self.role_message_id = None
        self.load_role_message_id()

    # ---------- Работа с файлом ----------
    def load_role_message_id(self):
        if os.path.exists(self.role_message_file):
            try:
                with open(self.role_message_file, "r") as f:
                    self.role_message_id = int(f.read().strip())
                logger.info(f"Загружен ID сообщения для ролей: {self.role_message_id}")
            except Exception as e:
                logger.warning(f"Не удалось загрузить ID сообщения: {e}")

    def save_role_message_id(self):
        try:
            with open(self.role_message_file, "w") as f:
                f.write(str(self.role_message_id))
            logger.info(f"Сохранён ID сообщения: {self.role_message_id}")
        except Exception as e:
            logger.error(f"Не удалось сохранить ID сообщения: {e}")

    # ---------- Подготовка ролей ----------
    async def ensure_section_role(self, guild):
        if not discord.utils.get(guild.roles, name=self.section_role_name):
            await guild.create_role(
                name=self.section_role_name,
                hoist=False,
                mentionable=False
            )
            logger.info(f"Создана роль-секция: {self.section_role_name}")

    # ---------- Сообщение с ролями ----------
    async def create_role_message(self, channel):
        description_lines = []

        for section_title, roles in self.sections.items():
            description_lines.append(f"\n{section_title}")
            for emoji, (short, full) in roles.items():
                description_lines.append(f"{emoji} — **{short}**")

        embed = discord.Embed(
            title="⚔️ Выбор классов ⚔️",
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
        logger.info(f"Создано сообщение для ролей с ID {self.role_message_id}")

    # ---------- on_ready ----------
    @commands.Cog.listener()
    async def on_ready(self):
        channel = self.bot.get_channel(self.role_channel_id)
        if not channel:
            logger.error(f"Канал для выбора ролей с ID {self.role_channel_id} не найден!")
            return

        guild = channel.guild
        await self.ensure_section_role(guild)

        message = None
        if self.role_message_id:
            try:
                message = await channel.fetch_message(self.role_message_id)
                logger.info(f"Используем существующее сообщение: {self.role_message_id}")
            except discord.NotFound:
                logger.warning("Старое сообщение не найдено, создаём новое.")

        if not message:
            await self.create_role_message(channel)

    # ---------- Выдача/снятие ролей ----------
    async def modify_member_role(self, payload, add=True):
        if payload.user_id == self.bot.user.id:
            return

        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return

        member = guild.get_member(payload.user_id)
        if not member:
            return

        role_name = self.emoji_roles.get(str(payload.emoji))
        if not role_name:
            return

        role = discord.utils.get(guild.roles, name=role_name)
        if not role:
            logger.warning(f"Роль {role_name} не найдена в гильдии {guild.name}")
            return

        section_role = discord.utils.get(guild.roles, name=self.section_role_name)

        try:
            if add:
                await member.add_roles(role)
                if section_role and section_role not in member.roles:
                    await member.add_roles(section_role)

                logger.info(f"Выдана роль {role_name} пользователю {member}")

            else:
                await member.remove_roles(role)

                # Проверяем: остались ли у него ещё роли из списка классов
                still_has_any_class = any(
                    discord.utils.get(guild.roles, name=r) in member.roles
                    for r in self.emoji_roles.values()
                )

                if section_role and not still_has_any_class:
                    await member.remove_roles(section_role)

                logger.info(f"Убрана роль {role_name} у пользователя {member}")

        except discord.Forbidden:
            logger.error(f"Нет прав для изменения роли {role_name} у {member}")

    # ---------- Реакции ----------
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

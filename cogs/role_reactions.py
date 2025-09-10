import discord
from discord.ext import commands
import os
import logging

logger = logging.getLogger("discord")

class RoleReactionsWebhook(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.role_channel_id = 1273350157257146388  # ID канала для выбора ролей

        # === Роли-секции (для красивого отображения в списке ролей на сервере) ===
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
                "🤖": ("Техножрец", "Техножрец"),
                "👽": ("Киноман", "Киноман"),
            }
        }

        # Плоский словарь для выдачи ролей
        self.emoji_roles = {
            emoji: short for section in self.sections.values() for emoji, (short, full) in section.items()
        }

        # Путь к файлу с ID сообщения
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        data_folder = os.path.join(base_path, "data")
        os.makedirs(data_folder, exist_ok=True)
        self.role_message_file = os.path.join(data_folder, "role_message_id.txt")

        self.role_message_id = None
        if os.path.exists(self.role_message_file):
            with open(self.role_message_file, "r") as f:
                self.role_message_id = int(f.read().strip())
                logger.info(f"Загружен ID сообщения для ролей: {self.role_message_id}")

    @commands.Cog.listener()
    async def on_ready(self):
        guild = self.bot.get_channel(self.role_channel_id).guild

        # Проверяем, что роли-секции существуют, иначе создаём
        for role_name in self.section_roles:
            role = discord.utils.get(guild.roles, name=role_name)
            if not role:
                await guild.create_role(name=role_name, hoist=False, mentionable=False)
                logger.info(f"Создана недостающая роль-секция: {role_name}")

        channel = self.bot.get_channel(self.role_channel_id)
        if not channel:
            logger.error(f"Канал для выбора ролей с ID {self.role_channel_id} не найден!")
            return

        message = None
        if self.role_message_id:
            try:
                message = await channel.fetch_message(self.role_message_id)
                logger.info(f"Используем существующее сообщение с ID {self.role_message_id}")
            except discord.NotFound:
                logger.warning("Старое сообщение не найдено, создаём новое.")

        if not message:
            description_lines = ["✠ **Выберите свою роль, чтобы открыть доступ к каналам** ✠\n"]
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
            with open(self.role_message_file, "w") as f:
                f.write(str(self.role_message_id))

            logger.info(f"Создано новое сообщение для ролей с ID {self.role_message_id}")

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        if payload.message_id != self.role_message_id or payload.user_id == self.bot.user.id:
            return

        guild = self.bot.get_guild(payload.guild_id)
        member = guild.get_member(payload.user_id)
        if not member:
            return

        role_name = self.emoji_roles.get(str(payload.emoji))
        if role_name:
            role = discord.utils.get(guild.roles, name=role_name)
            if role:
                await member.add_roles(role)
                logger.info(f"Выдана роль {role_name} пользователю {member.name}")

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload):
        if payload.message_id != self.role_message_id or payload.user_id == self.bot.user.id:
            return

        guild = self.bot.get_guild(payload.guild_id)
        member = guild.get_member(payload.user_id)
        if not member:
            return

        role_name = self.emoji_roles.get(str(payload.emoji))
        if role_name:
            role = discord.utils.get(guild.roles, name=role_name)
            if role:
                await member.remove_roles(role)
                logger.info(f"Убрана роль {role_name} у пользователя {member.name}")


async def setup(bot):
    await bot.add_cog(RoleReactionsWebhook(bot))

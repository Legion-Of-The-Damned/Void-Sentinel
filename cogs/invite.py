import discord
from discord import app_commands
from discord.ext import commands
from config import load_config
import asyncio
import logging
from typing import Optional, List, Tuple

config = load_config()

# Константы
QUESTIONS: List[str] = [
    "Какой стиль игры тебе больше всего нравится (агрессивный, стратегический, поддержка и т. д.)?",
    "Есть ли у тебя опыт командной работы и как ты решаешь конфликты в команде?",
    "Как ты предпочитаешь получать информацию о клановых активностях и новостях?",
    "Как часто ты планируешь быть активным в клане?",
    "Как ты обычно справляешься с агрессией или неудачами в игре?",
    "Ты предпочитаешь играть в одиночку или в команде? Почему?",
    "Как ты относишься к критике и каким образом ты обычно её воспринимаешь?",
    "Какие у тебя ожидания от общения с другими членами клана?",
    "В какое время тебе удобно играть?",
    "Боитесь ли вы незнакомых людей и тревожит ли вас это?",
    "Ваша цель вступления в клан?",
    "Какая ваша страна проживания и какой у вас часовой пояс?"
]

APPROVE_EMOJI = "✅"
DECLINE_EMOJI = "❌"

TIMEOUT_MESSAGE = "⏱ Время на ответ истекло. Пожалуйста, начните заново с команды `/заявка`."
ERROR_GUILD_MESSAGE = "❌ Не удалось определить сервер. Попробуйте позже."
ERROR_CHANNEL_MESSAGE = "❌ Канал для заявок не настроен!"


class Applications(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.APPLICATIONS_CHANNEL_ID: int = config.get("APPLICATIONS_CHANNEL_ID")
        self.MEMBER_ROLE_ID: int = config.get("MEMBER_ROLE_ID")
        self.STAFF_ROLE_NAME: str = config.get("STAFF_ROLE_NAME", "Модератор")
        self.OLD_ROLE_ID: Optional[int] = config.get("FRIEND_ROLE_ID")
        self.GUILD_ID: int = config.get("GUILD_ID")
        self.logger = logging.getLogger("Applications")

    def is_staff_member(self, member: discord.Member) -> bool:
        """Проверка, является ли участник модератором/админом."""
        return member.guild_permissions.administrator or discord.utils.get(
            member.guild.roles, name=self.STAFF_ROLE_NAME
        ) in member.roles

    async def get_user_from_embed(
        self, embed: discord.Embed, guild: discord.Guild
    ) -> Optional[discord.Member]:
        """Получение участника по footer embed."""
        try:
            if not embed.footer or not embed.footer.text:
                return None
            user_id = int(embed.footer.text.replace("ID:", "").strip())
            return guild.get_member(user_id)
        except Exception as e:
            self.logger.error(f"Ошибка при извлечении пользователя из embed: {e}")
            return None

    async def ask_questions(
        self, member: discord.Member
    ) -> Optional[List[Tuple[str, str]]]:
        """Сбор ответов через ЛС."""
        if member.bot:
            self.logger.warning(f"Нельзя собирать ответы у бота {member}")
            return None

        answers: List[Tuple[str, str]] = []
        try:
            dm = await member.create_dm()
            self.logger.info(f"Начат процесс сбора ответов у {member}")

            for question in QUESTIONS:
                await dm.send(question)

                def check(m: discord.Message) -> bool:
                    return m.author == member and isinstance(m.channel, discord.DMChannel)

                try:
                    msg = await self.bot.wait_for("message", check=check, timeout=300)
                except asyncio.TimeoutError:
                    await dm.send(TIMEOUT_MESSAGE)
                    self.logger.warning(f"{member} не успел ответить на все вопросы в ЛС")
                    return None

                if not msg.content.strip():
                    await dm.send("⚠ Ответ не может быть пустым. Попробуйте заново.")
                    return None

                answers.append((question, msg.content.strip()))

            self.logger.info(f"{member} успешно ответил на все вопросы")
            return answers

        except discord.Forbidden:
            self.logger.warning(f"Не удалось открыть ЛС с {member}")
            return None
        except Exception as e:
            self.logger.error(f"Ошибка при сборе ответов у {member}: {e}")
            return None

    async def safe_dm(self, member: discord.Member, message: str) -> None:
        """Отправка ЛС с защитой от Forbidden и проверки на бота."""
        if member.bot:
            self.logger.warning(f"Попытка отправить ЛС боту: {member}")
            return
        try:
            await member.send(message)
        except discord.Forbidden:
            self.logger.warning(f"Не удалось отправить ЛС {member}")
        except Exception as e:
            self.logger.error(f"Ошибка при отправке ЛС {member}: {e}")

    @app_commands.command(
        name="заявка",
        description="Подать заявку на вступление в клан"
    )
    async def application(self, interaction: discord.Interaction):
        member = interaction.user

        # Проверка, что это не бот
        if member.bot:
            await interaction.response.send_message(
                "⚠ Боты не могут подавать заявки.", ephemeral=True
            )
            return

        # Сообщение пользователю о начале процесса
        if isinstance(interaction.channel, discord.DMChannel):
            await interaction.response.send_message(
                "Начинаю сбор ответов через ЛС...", ephemeral=True
            )
            self.logger.info(f"{member} начал подачу заявки через ЛС")
        else:
            await interaction.response.send_message(
                "📩 Void Sentinel ждёт ваших ответов на все вопросы в ЛС...",
                ephemeral=True
            )
            self.logger.info(f"{member} начал подачу заявки через сервер")

        # Сбор ответов
        answers = await self.ask_questions(member)
        if not answers:
            return

        # Получение гильдии
        guild = self.bot.get_guild(self.GUILD_ID)
        if not guild:
            await self.safe_dm(member, ERROR_GUILD_MESSAGE)
            return

        # Получение канала для заявок
        application_channel = self.bot.get_channel(self.APPLICATIONS_CHANNEL_ID)
        if not isinstance(application_channel, discord.TextChannel):
            await self.safe_dm(member, ERROR_CHANNEL_MESSAGE)
            return

        # Создание embed с заявкой
        embed = discord.Embed(
            title="📄 Новая заявка",
            description=f"**Пользователь:** {member.mention}",
            color=discord.Color.blue()
        )
        for q, ans in answers:
            embed.add_field(name=q, value=ans, inline=False)
        embed.set_footer(text=f"ID:{member.id}")

        # Отправка заявки в канал
        msg = await application_channel.send(embed=embed)
        await msg.add_reaction(APPROVE_EMOJI)
        await msg.add_reaction(DECLINE_EMOJI)
        self.logger.info(f"Заявка от {member} отправлена в {application_channel.name}")

        # Уведомление модераторов
        for guild_member in guild.members:
            if self.is_staff_member(guild_member) and not guild_member.bot:
                await self.safe_dm(
                    guild_member,
                    f"📌 Новая заявка от {member.mention} в {application_channel.mention}"
                )

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if payload.channel_id != self.APPLICATIONS_CHANNEL_ID:
            return

        guild = self.bot.get_guild(self.GUILD_ID)
        if not guild:
            self.logger.error("Не удалось получить сервер для реакции")
            return

        member = guild.get_member(payload.user_id)
        if not member or member.bot or not self.is_staff_member(member):
            return

        channel = self.bot.get_channel(payload.channel_id)
        if not isinstance(channel, discord.TextChannel):
            return

        try:
            message = await channel.fetch_message(payload.message_id)
        except Exception as e:
            self.logger.error(f"Не удалось получить сообщение: {e}")
            return

        if not message.embeds:
            return

        target_member = await self.get_user_from_embed(message.embeds[0], guild)
        if not target_member:
            return

        role = guild.get_role(self.MEMBER_ROLE_ID)
        old_role = guild.get_role(self.OLD_ROLE_ID) if self.OLD_ROLE_ID else None

        try:
            if str(payload.emoji) == APPROVE_EMOJI:
                if old_role and old_role in target_member.roles:
                    await target_member.remove_roles(old_role)
                if role:
                    await target_member.add_roles(role)
                await self.safe_dm(target_member, "🎉 Ваша заявка была одобрена! Добро пожаловать на сервер!")
                await message.delete()
                self.logger.info(f"Заявка {target_member} одобрена модератором {member}")

            elif str(payload.emoji) == DECLINE_EMOJI:
                await self.safe_dm(target_member, "😕 Ваша заявка была отклонена модератором.")
                await message.delete()
                self.logger.info(f"Заявка {target_member} отклонена модератором {member}")

        except Exception as e:
            self.logger.error(f"Ошибка при обработке заявки {target_member}: {e}")


async def setup(bot: commands.Bot):
    await bot.add_cog(Applications(bot))

import os
import discord
from discord import app_commands
from discord.ext import commands
from supabase import create_client, Client
import logging

# Логгер
logger = logging.getLogger("Applications")

# Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

QUESTIONS = [
    "Какой стиль игры тебе ближе: агрессивный, стратегический, поддержка или что-то уникальное?",
    "Есть ли у тебя опыт командной работы? Как обычно решаешь конфликты в команде?",
    "Как предпочитаешь получать информацию о клановых активностях и новостях?",
    "Сколько часов в неделю ты готов посвящать клану?",
    "Как обычно справляешься с поражениями и стрессовыми ситуациями в игре?",
    "В какое время суток тебе удобнее всего участвовать в клановых событиях?",
    "Какая твоя главная цель при вступлении в клан?",
    "В какой стране и часовом поясе ты находишься?",
    "Ваша дата рождения"
]

COLUMNS = [
    "Игроки",
    "Стиль игры",
    "Опыт командной работы",
    "Получение информации",
    "Время для клана",
    "Стресс и поражения",
    "Удобное время для активностей",
    "Цель вступления",
    "Страна и часовой пояс",
    "Дата рождения"
]

def push_to_supabase(user_name, answers):
    try:
        data = {col: ans for col, ans in zip(COLUMNS, [user_name] + answers)}
        response = supabase.table("applications").insert(data).execute()
        if response.data:
            logger.info(f"Заявка {user_name} успешно сохранена в Supabase")
        else:
            logger.error(f"Ошибка при сохранении заявки {user_name}: пустой ответ")
    except Exception as e:
        logger.error(f"Ошибка при подключении к Supabase: {e}")


class Applications(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.APPLICATIONS_CHANNEL_ID = 1464448287733059634
        self.MEMBER_ROLE_NAME = "💀Легион Проклятых🔥"
        self.OLD_ROLE_NAME = ["🤝Друг клана🚩", "💀Неофит🌱"]
        self.active_applications = set()
        self.STAFF_ROLES = ["🔥Огненный Магистр🎩", "💀Заместитель Магистра🔥", "☠️Капитан🔸"]
        self.NOTIFY_ROLE_IDS = [828749920411713588, 1429978575347519610]

    # -------- Проверка стаффа --------
    async def is_staff(self, interaction: discord.Interaction):
        if interaction.user.guild_permissions.administrator:
            return True
        if any(discord.utils.get(interaction.guild.roles, name=r) in interaction.user.roles for r in self.STAFF_ROLES):
            return True
        raise app_commands.MissingPermissions(["administrator"])

    # -------- Команда заявки --------
    @app_commands.command(name="заявка", description="Подать заявку на вступление")
    async def application(self, interaction: discord.Interaction):
        user_id = interaction.user.id

        if user_id in self.active_applications:
            return await interaction.response.send_message(
                "⏳ У тебя уже есть активная заявка. Заверши её перед новой.",
                ephemeral=True
            )

        self.active_applications.add(user_id)

        try:
            answers = []

            # создаём ЛС
            try:
                channel = await interaction.user.create_dm()
            except discord.Forbidden:
                self.active_applications.remove(user_id)
                return await interaction.response.send_message(
                    "❌ Не удалось написать в ЛС. Разреши личные сообщения от участников сервера.",
                    ephemeral=True
                )

            await interaction.response.send_message(
                "📩 Я отправил тебе вопросы в личные сообщения!",
                ephemeral=True
            )

            await channel.send("Привет! Начнём заполнение заявки 👇")

            for question in QUESTIONS:
                await channel.send(question)

                def check(m):
                    return m.author == interaction.user and isinstance(m.channel, discord.DMChannel)

                try:
                    msg = await self.bot.wait_for("message", check=check, timeout=300)
                    answers.append(msg.content)
                except:
                    await channel.send("⏰ Время на ответ истекло. Запусти /заявка ещё раз.")
                    return

            # канал заявок
            application_channel = self.bot.get_channel(self.APPLICATIONS_CHANNEL_ID)
            if not isinstance(application_channel, discord.TextChannel):
                return await channel.send("❌ Канал для заявок не найден.")

            embed = discord.Embed(
                title="📄 Новая заявка",
                description=f"**Пользователь:** {interaction.user.mention}",
                color=discord.Color.blue()
            )

            for q, a in zip(QUESTIONS, answers):
                embed.add_field(name=q, value=a, inline=False)

            embed.set_footer(text=f"ID пользователя: {interaction.user.id}")

            msg = await application_channel.send(embed=embed)
            await msg.add_reaction("✅")
            await msg.add_reaction("❌")

            await channel.send("✅ Заявка отправлена на рассмотрение!")

            # -------- уведомления --------
            guild = interaction.guild
            if not guild:
                guild = next((g for g in self.bot.guilds if g.get_member(interaction.user.id)), None)

            if guild:
                notified_users = set()  # уникальность уведомлений
                for role_id in self.NOTIFY_ROLE_IDS:
                    notify_role = guild.get_role(role_id)
                    if not notify_role:
                        continue

                    for member in notify_role.members:
                        if member.bot or member.id in notified_users:
                            continue
                        try:
                            dm = await member.create_dm()
                            await dm.send(
                                f"📩 Новая заявка от {interaction.user.mention}: {msg.jump_url}"
                            )
                            logger.info(f"Уведомление отправлено {member}")
                            notified_users.add(member.id)
                        except discord.Forbidden:
                            logger.warning(f"Не удалось отправить ЛС {member}")
                        except Exception as e:
                            logger.error(f"Ошибка при отправке ЛС {member}: {e}")

            push_to_supabase(str(interaction.user), answers)

        except Exception as e:
            logger.error(f"Ошибка в команде заявка: {e}")

            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "❌ Произошла ошибка при отправке заявки.",
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    "❌ Произошла ошибка при отправке заявки.",
                    ephemeral=True
                )

        finally:
            self.active_applications.discard(user_id)

    # -------- Реакции --------
    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        try:
            if payload.channel_id != self.APPLICATIONS_CHANNEL_ID:
                return

            guild = self.bot.get_guild(payload.guild_id)
            if not guild:
                return

            member = guild.get_member(payload.user_id)
            if not member or member.bot:
                return

            channel = self.bot.get_channel(payload.channel_id)
            if not channel:
                return

            message = await channel.fetch_message(payload.message_id)
            if not message.embeds:
                return

            if not (member.guild_permissions.administrator or any(role.name in self.STAFF_ROLES for role in member.roles)):
                return

            embed = message.embeds[0]
            if not embed.footer or not embed.footer.text:
                return

            try:
                user_id = int(embed.footer.text.split("ID пользователя: ")[1])
            except:
                return

            target_member = guild.get_member(user_id)
            if not target_member:
                return

            old_roles = [discord.utils.get(guild.roles, name=r) for r in self.OLD_ROLE_NAME]
            new_role = discord.utils.get(guild.roles, name=self.MEMBER_ROLE_NAME)

            if str(payload.emoji) == "✅":
                for role in old_roles:
                    if role in target_member.roles:
                        await target_member.remove_roles(role)
                if new_role:
                    await target_member.add_roles(new_role)

                # Добавление тега клана к нику
                clan_tag = "[LOTD]"
                current_nick = target_member.nick or target_member.name
                if not current_nick.startswith(clan_tag):
                    try:
                        new_nick = f"{clan_tag} {current_nick}"
                        await target_member.edit(nick=new_nick)
                        logger.info(f"Тег клана добавлен к {target_member}: {new_nick}")
                    except discord.Forbidden:
                        logger.warning(f"Не удалось изменить ник {target_member} — недостаточно прав")
                    except Exception as e:
                        logger.error(f"Ошибка при изменении ника {target_member}: {e}")

                try:
                    await target_member.send("🎉 Заявка одобрена! Добро пожаловать в клан!")
                    logger.info(f"Заявка одобрена: {target_member}")
                except discord.Forbidden:
                    logger.warning(f"Не удалось отправить ЛС {target_member}")

            elif str(payload.emoji) == "❌":
                try:
                    await target_member.send("😕 К сожалению, заявка была отклонена.")
                    logger.info(f"Заявка отклонена: {target_member}")
                except discord.Forbidden:
                    logger.warning(f"Не удалось отправить ЛС {target_member}")

        except Exception as e:
            logger.error(f"Ошибка в обработке реакций: {e}")


# -------- setup --------
async def setup(bot):
    await bot.add_cog(Applications(bot))

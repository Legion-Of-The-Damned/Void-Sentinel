import os
import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime
from supabase import create_client, Client
import logging

# Логгер
logger = logging.getLogger("Applications")

# Supabase
SUPABASE_URL = ("https://jqphrrikzkntcyzsrbrc.supabase.co")
SUPABASE_KEY = ("sb_secret_lIVKGhCjIqyeC9WmVO5Q-g_wZOqmUsv")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Вопросы для заявок
QUESTIONS = [
    "Какой стиль игры тебе ближе: агрессивный, стратегический, поддержка или что-то уникальное?",
    "Есть ли у тебя опыт командной работы? Как обычно решаешь конфликты в команде?",
    "Как предпочитаешь получать информацию о клановых активностях и новостях?",
    "Сколько часов в неделю ты готов посвящать клану?",
    "Как обычно справляешься с поражениями и стрессовыми ситуациями в игре?",
    "Ты предпочитаешь действовать в одиночку или в команде? Почему?",
    "Как воспринимаешь критику и умеешь ли извлекать из неё пользу?",
    "Какие ожидания у тебя от общения с другими членами клана?",
    "В какое время суток тебе удобнее всего участвовать в клановых событиях?",
    "Что для тебя страшнее: неожиданные противники или неожиданные задания?",
    "Какая твоя главная цель при вступлении в клан?",
    "В какой стране и часовом поясе ты находишься?",
    "Если бы Legion Of The Damned была видеоигрой, кем бы ты хотел быть в её истории?",
    "Придумай свой позывной, которым тебя будут называть в клане.",
    "Расскажи о самой эпичной победе в своей игровой истории."
]

# Список колонок таблицы
COLUMNS = [
    "Игроки",
    "Стиль игры",
    "Опыт командной работы",
    "Получение информации",
    "Время для клана",
    "Стрессовые ситуации в играх",
    "Одиначка или командный игрок",
    "Восприятие критики",
    "Ожидание от соклановцев",
    "Время для матчей",
    "Что страшнее",
    "Цель вступления в клан",
    "Место положения",
    "Кем ты был бы",
    "Новый позывной в клане",
    "Самая эпичная победа в истории"
]

def push_to_supabase(user_name, answers):
    """
    Сохраняет заявку в Supabase в таблицу 'applications'.
    Работает с последней версией supabase-py (v2+)
    """
    try:
        data = {col: ans for col, ans in zip(COLUMNS, [user_name] + answers)}

        # Вставка в таблицу
        response = supabase.table("applications").insert(data).execute()

        # В новых версиях SDK проверяем response.data
        if response.data:
            logger.info(f"Заявка {user_name} успешно сохранена в Supabase")
        else:
            logger.error(f"Ошибка при сохранении заявки {user_name}: пустой ответ")

    except Exception as e:
        logger.error(f"Ошибка при подключении к Supabase: {e}")

class Applications(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.APPLICATIONS_CHANNEL_ID = 1362357361863295199
        self.MEMBER_ROLE_NAME = "💀Легион Проклятых🔥"
        self.OLD_ROLE_NAME = "🤝Друг клана🚩"
        self.active_applications = set()

    async def is_staff(self, interaction: discord.Interaction):
        if interaction.user.guild_permissions.administrator:
            return True
        staff_role = discord.utils.get(interaction.guild.roles, name="Модератор")
        if staff_role and staff_role in interaction.user.roles:
            return True
        raise app_commands.MissingPermissions(["administrator"])

    @app_commands.command(name="заявка", description="Подать заявку на вступление")
    async def application(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        if user_id in self.active_applications:
            return await interaction.response.send_message(
                "⏳ У вас уже открыта активная заявка. Завершите её перед началом новой.",
                ephemeral=True
            )
        self.active_applications.add(user_id)

        try:
            answers = []
            if isinstance(interaction.channel, discord.DMChannel) or interaction.guild is None:
                channel = interaction.channel
                await interaction.response.send_message(
                    "📩 Я отправил тебе вопросы для заявки в этом чате!", ephemeral=True
                )
            else:
                try:
                    channel = await interaction.user.create_dm()
                except:
                    self.active_applications.remove(user_id)
                    return await interaction.response.send_message(
                        "❌ Не удалось отправить ЛС. Разрешите личные сообщения от участников сервера.",
                        ephemeral=True
                    )
                await interaction.response.send_message(
                    "📩 Я отправил тебе личные сообщения с вопросами для заявки!", ephemeral=True
                )
                await channel.send("Привет! Начнём заполнение заявки. Ниже будут вопросы для тебя.")

            # Задаём вопросы
            for question in QUESTIONS:
                await channel.send(f"{question}")

                def check(m):
                    return m.author == interaction.user and isinstance(m.channel, discord.DMChannel)

                try:
                    msg = await self.bot.wait_for('message', check=check, timeout=300)
                    answers.append(msg.content)
                except:
                    await channel.send("⏰ Время на ответ истекло. Пожалуйста, попробуй снова командой /заявка.")
                    return

            # Отправка заявки в канал Discord
            application_channel = self.bot.get_channel(self.APPLICATIONS_CHANNEL_ID)
            if not isinstance(application_channel, discord.TextChannel):
                return await channel.send("❌ Ошибка: канал для заявок не настроен!")

            embed = discord.Embed(
                title="📄 Новая заявка",
                description=f"**Пользователь:** {interaction.user.mention}",
                color=discord.Color.blue()
            )

            for question, answer in zip(QUESTIONS, answers):
                embed.add_field(name=question, value=answer, inline=False)
            embed.set_footer(text=f"ID пользователя: {interaction.user.id}")

            msg = await application_channel.send(embed=embed)
            await msg.add_reaction('✅')
            await msg.add_reaction('❌')

            await channel.send("✅ Ваша заявка отправлена на рассмотрение!")

            # Уведомление администраторов
            guild = interaction.guild
            if guild:
                try:
                    async for member in guild.fetch_members(limit=None):
                        if member.bot:
                            continue
                        perms = member.guild_permissions
                        if perms.administrator or perms.manage_guild or perms.manage_roles:
                            try:
                                dm_channel = member.dm_channel or await member.create_dm()
                                await dm_channel.send(
                                    f"📩 Новая заявка от {interaction.user.mention} готова к рассмотрению: {msg.jump_url}"
                                )
                                logger.info(f"Уведомление отправлено {member} с правами {perms}")
                            except discord.Forbidden:
                                logger.warning(f"Не удалось отправить ЛС {member}: запрещено писать пользователю")
                            except Exception as e:
                                logger.error(f"Ошибка при отправке ЛС {member}: {e}")
                except Exception as e:
                    logger.error(f"Ошибка при получении участников сервера: {e}")

            # Сохраняем заявку в Supabase
            push_to_supabase(str(interaction.user), answers)

        except Exception as e:
            logger.error(f"Ошибка в команде заявка: {e}")
            await interaction.response.send_message(
                "❌ Произошла ошибка при отправке заявки.", ephemeral=True
            )

        finally:
            self.active_applications.discard(user_id)

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
            if not (member.guild_permissions.administrator or 
                   any(role.name == "Модератор" for role in member.roles)):
                return
            embed = message.embeds[0]
            if not embed.footer or not embed.footer.text:
                return
            footer_parts = embed.footer.text.split("ID пользователя: ")
            if len(footer_parts) < 2:
                return
            try:
                user_id = int(footer_parts[1])
            except ValueError:
                return
            target_member = guild.get_member(user_id)
            if not target_member:
                return
            old_role = discord.utils.get(guild.roles, name=self.OLD_ROLE_NAME)
            new_role = discord.utils.get(guild.roles, name=self.MEMBER_ROLE_NAME)
            if str(payload.emoji) == '✅':
                if old_role in target_member.roles:
                    await target_member.remove_roles(old_role)
                if new_role:
                    await target_member.add_roles(new_role)
                await message.delete()
                try:
                    await target_member.send('🎉 Ваша заявка была одобрена! Добро пожаловать в клан!')
                except:
                    pass
            elif str(payload.emoji) == '❌':
                try:
                    await target_member.send('😕 Ваша заявка была отклонена модератором.')
                except:
                    pass
        except Exception as e:
            logger.error(f"Ошибка в обработке реакций: {e}")


async def setup(bot):
    await bot.add_cog(Applications(bot))

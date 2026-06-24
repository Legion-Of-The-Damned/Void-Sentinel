import discord
from discord import app_commands
from discord.ext import commands
import logging

# 🔥 твоя система логов
logger = logging.getLogger("bot.applications")
logger.setLevel(logging.DEBUG)
logger.propagate = True


QUESTIONS = [
    "Есть ли у тебя опыт командной работы? Как обычно решаешь конфликты в команде?",
    "Как предпочитаешь получать информацию о клановых активностях и новостях?",
    "Сколько часов в неделю ты готов посвящать клану?",
    "Как обычно справляешься с поражениями и стрессовыми ситуациями в игре?",
    "В какое время суток тебе удобнее всего участвовать в клановых событиях?",
    "Какая твоя главная цель при вступлении в клан?",
    "В какой стране и часовом поясе ты находишься?",
    "Ваша дата рождения"
]


class Applications(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        self.APPLICATIONS_CHANNEL_ID = 1464448287733059634

        self.MEMBER_ROLE_IDS = [
            1151988594148376709,
            1472318342663507988,
            1482835938076786718
        ]

        self.OLD_ROLE_IDS = [
            1151988812151521431,
            1418038359129063585
        ]

        self.STAFF_ROLE_IDS = [
            828749920411713588,
            1491133532796354581,
            1491133766448578570
        ]

        self.NOTIFY_ROLE_IDS = [
            828749920411713588,
            1429978575347519610
        ]

        self.active_applications = set()

    # ---------- STAFF CHECK ----------
    async def is_staff(self, interaction: discord.Interaction):
        if interaction.user.guild_permissions.administrator:
            return True

        if any(r.id in self.STAFF_ROLE_IDS for r in interaction.user.roles):
            return True

        raise app_commands.MissingPermissions(["administrator"])

    # ---------- COMMAND ----------
    @app_commands.command(name="заявка", description="Подать заявку на вступление")
    async def application(self, interaction: discord.Interaction):
        user_id = interaction.user.id

        if user_id in self.active_applications:
            logger.warning(f"Попытка повторной заявки: {interaction.user}")
            return await interaction.response.send_message(
                "⏳ У тебя уже есть активная заявка.",
                ephemeral=True
            )

        self.active_applications.add(user_id)
        logger.info(f"📩 Заявка начата: {interaction.user} ({user_id})")

        try:
            answers = []

            try:
                dm = await interaction.user.create_dm()
            except discord.Forbidden:
                logger.warning(f"DM закрыт: {interaction.user}")
                self.active_applications.discard(user_id)
                return await interaction.response.send_message(
                    "❌ Включи личные сообщения.",
                    ephemeral=True
                )

            await interaction.response.send_message(
                "📩 Вопросы отправлены в ЛС!",
                ephemeral=True
            )

            await dm.send("Привет! Начинаем заявку 👇")

            for question in QUESTIONS:
                await dm.send(question)

                def check(m):
                    return (
                        m.author.id == interaction.user.id
                        and isinstance(m.channel, discord.DMChannel)
                    )

                try:
                    msg = await self.bot.wait_for("message", check=check, timeout=300)
                    answers.append(msg.content)
                    logger.debug(f"Ответ получен: {msg.content}")
                except:
                    logger.warning(f"Таймаут заявки: {interaction.user}")
                    await dm.send("⏰ Время истекло. Запусти /заявка снова.")
                    return

            channel = self.bot.get_channel(self.APPLICATIONS_CHANNEL_ID)
            if not isinstance(channel, discord.TextChannel):
                logger.critical("Канал заявок не найден!")
                return await dm.send("❌ Канал заявок не найден.")

            embed = discord.Embed(
                title="📄 Новая заявка",
                description=f"**Пользователь:** {interaction.user.mention}",
                color=discord.Color.blue()
            )

            for q, a in zip(QUESTIONS, answers):
                embed.add_field(name=q, value=a, inline=False)

            embed.set_footer(text=f"ID пользователя: {interaction.user.id}")

            msg = await channel.send(embed=embed)
            await msg.add_reaction("✅")
            await msg.add_reaction("❌")

            logger.success(f"📨 Заявка отправлена: {interaction.user}")

            await dm.send("✅ Заявка отправлена!")

            guild = interaction.guild or next(
                (g for g in self.bot.guilds if g.get_member(user_id)),
                None
            )

            if guild:
                notified = set()

                for role_id in self.NOTIFY_ROLE_IDS:
                    role = guild.get_role(role_id)
                    if not role:
                        logger.warning(f"Роль не найдена: {role_id}")
                        continue

                    for member in role.members:
                        if member.bot or member.id in notified:
                            continue

                        try:
                            dm_member = await member.create_dm()
                            await dm_member.send(
                                f"📩 Новая заявка: {interaction.user.mention}\n{msg.jump_url}"
                            )
                            notified.add(member.id)
                            logger.info(f"📢 Уведомлён: {member}")
                        except Exception as e:
                            logger.warning(f"Не удалось уведомить {member}: {e}")

        except Exception as e:
            logger.error(f"Ошибка заявки: {e}")

            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "❌ Ошибка при отправке заявки.",
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    "❌ Ошибка при отправке заявки.",
                    ephemeral=True
                )

        finally:
            self.active_applications.discard(user_id)

    # ---------- REACTIONS ----------
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

            if not (
                member.guild_permissions.administrator
                or any(r.id in self.STAFF_ROLE_IDS for r in member.roles)
            ):
                return

            embed = message.embeds[0]
            if not embed.footer:
                return

            try:
                user_id = int(embed.footer.text.split("ID пользователя: ")[1])
            except:
                logger.error("Не удалось распарсить ID пользователя")
                return

            target = guild.get_member(user_id)
            if not target:
                logger.warning("Пользователь не найден")
                return

            old_roles = list(filter(None, [
                guild.get_role(rid) for rid in self.OLD_ROLE_IDS
            ]))

            member_roles = list(filter(None, [
                guild.get_role(rid) for rid in self.MEMBER_ROLE_IDS
            ]))

            emoji = str(payload.emoji)

            # ---------- APPROVE ----------
            if emoji == "✅":

                for role in old_roles:
                    if role in target.roles:
                        await target.remove_roles(role)

                for role in member_roles:
                    await target.add_roles(role)

                clan_tag = "[LOTD]"
                nick = target.nick or target.name

                if not nick.startswith(clan_tag):
                    try:
                        await target.edit(nick=f"{clan_tag} {nick}")
                    except Exception as e:
                        logger.warning(f"Не удалось изменить ник: {e}")

                embed.color = discord.Color.green()
                embed.title = "📄 Заявка — ОДОБРЕНА"

                await message.edit(embed=embed)
                await message.clear_reactions()

                logger.success(f"Заявка одобрена: {target}")

                try:
                    await target.send("🎉 Заявка одобрена!")
                except:
                    logger.warning(f"DM закрыт: {target}")

            # ---------- REJECT ----------
            elif emoji == "❌":

                embed.color = discord.Color.red()
                embed.title = "📄 Заявка — ОТКЛОНЕНА"

                await message.edit(embed=embed)
                await message.clear_reactions()

                logger.warning(f"Заявка отклонена: {target}")

                try:
                    await target.send("😕 Заявка отклонена.")
                except:
                    logger.warning(f"DM закрыт: {target}")

        except Exception as e:
            logger.critical(f"Ошибка реакций: {e}")


async def setup(bot):
    await bot.add_cog(Applications(bot))

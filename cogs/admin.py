import discord
import logging
import traceback
from discord import app_commands
from discord.ext import commands
from datetime import timedelta
from discord.ui import Select, View
from data import active_duels, save_active_duels, update_stats, stats

# --- Настройка логгера для этого кога ---
logger = logging.getLogger("AdminCog")


class Admin(commands.Cog):
    def __init__(self, bot: commands.Bot, clan_role_ids: list[int], friend_role_id: int):
        self.bot = bot
        self.clan_role_ids = clan_role_ids
        self.friend_role_id = friend_role_id

    # --- /победа ---
    @commands.hybrid_command(name="победа", description="Выбрать дуэль и присудить победу (только для админов)")
    async def assign_winner_select(self, ctx: commands.Context):
        if not ctx.author.guild_permissions.kick_members:
            return await ctx.send("❌ У вас нет прав для назначения победителя.", ephemeral=True)

        if not active_duels:
            return await ctx.send("Нет активных дуэлей.", ephemeral=True)

        view = DuelSelectionView(ctx)
        await ctx.send("Выберите дуэль, чтобы назначить победителя:", view=view, ephemeral=True)
        logger.info(f"{ctx.author} открыл выбор дуэли для назначения победителя")

    # --- /изгнание ---
    @app_commands.command(name="изгнание", description="Изгоняет члена из клана и назначает роль 'Друг клана'")
    async def banish(self, interaction: discord.Interaction, member: discord.Member):
        if not interaction.user.guild_permissions.kick_members:
            await interaction.response.send_message("❌ У тебя нет прав использовать эту команду.", ephemeral=True)
            logger.warning(f"{interaction.user} попытался изгнать без прав")
            return

        await interaction.response.defer(thinking=True)
        try:
            await self.banish_from_clan(member)
            await interaction.followup.send(f"✅ {member.mention} был изгнан и получил роль **Друг клана**.")
            logger.info(f"{interaction.user} изгнал {member}")
        except Exception:
            logger.error(f"Ошибка при изгнании {member}:\n{traceback.format_exc()}")
            await interaction.followup.send(f"❌ Не удалось изгнать {member.mention}.")

    async def banish_from_clan(self, member: discord.Member):
        roles_to_remove = [r for r in member.roles if r.id in self.clan_role_ids]
        try:
            await member.remove_roles(*roles_to_remove, reason="Изгнан из клана (админ команда)")
            logger.info(f"С ролями {roles_to_remove} удалён у {member}")
        except discord.Forbidden:
            logger.warning(f"Не удалось снять роли с {member.display_name} — недостаточно прав")
            return

        friend_role = discord.utils.get(member.guild.roles, id=self.friend_role_id)
        if friend_role:
            await member.add_roles(friend_role, reason="Назначен как 'Друг клана'")
            logger.info(f"{member} получил роль 'Друг клана'")

        try:
            await member.send(
                f"Привет, {member.name}!\nТы был изгнан из клана, но остался на сервере как **Друг клана**."
            )
            logger.info(f"Отправлено ЛС {member} о изгнании")
        except discord.Forbidden:
            logger.info(f"Не удалось отправить ЛС участнику {member.display_name}")

    # --- /бан ---
    @app_commands.command(name="бан", description="Банит участника на сервере")
    async def ban(self, interaction: discord.Interaction, member: discord.Member, reason: str = "Без указания причины"):
        if not interaction.user.guild_permissions.ban_members:
            await interaction.response.send_message("❌ У тебя нет прав использовать эту команду.", ephemeral=True)
            logger.warning(f"{interaction.user} попытался забанить без прав")
            return

        try:
            try:
                await member.send(
                    f"Ты был **забанен** на сервере **{interaction.guild.name}**.\n"
                    f"Причина: {reason}\nМодератор: {interaction.user.display_name}"
                )
            except discord.Forbidden:
                logger.info(f"Не удалось отправить ЛС {member} перед баном")

            await member.ban(reason=f"Забанен модератором {interaction.user} — Причина: {reason}")
            await interaction.response.send_message(f"⛔ {member.mention} был забанен. Причина: {reason}")
            logger.info(f"{interaction.user} забанил {member} — Причина: {reason}")
        except Exception as e:
            logger.error(f"Ошибка при бане {member}: {e}")
            await interaction.response.send_message("❌ Не удалось забанить участника.", ephemeral=True)

    # --- /разбан ---
    @app_commands.command(name="разбан", description="Разбанивает участника по выбору из списка банов")
    @app_commands.describe(user_id="Выберите пользователя из списка забаненных")
    async def unban(self, interaction: discord.Interaction, user_id: str, reason: str = "Без указания причины"):
        if not interaction.user.guild_permissions.ban_members:
            await interaction.response.send_message("❌ У тебя нет прав использовать эту команду.", ephemeral=True)
            logger.warning(f"{interaction.user} попытался разбанить без прав")
            return

        try:
            user = await self.bot.fetch_user(int(user_id))
        except Exception:
            await interaction.response.send_message("❌ Не удалось найти пользователя.", ephemeral=True)
            logger.warning(f"Не удалось найти пользователя с ID {user_id}")
            return

        try:
            await interaction.guild.unban(user, reason=f"Разбанен модератором {interaction.user} — Причина: {reason}")
            try:
                await user.send(
                    f"Ты был **разбанен** на сервере **{interaction.guild.name}**.\n"
                    f"Модератор: {interaction.user.display_name}\nПричина: {reason}"
                )
            except discord.Forbidden:
                logger.info(f"Не удалось отправить ЛС пользователю {user.name} после разбана")

            await interaction.response.send_message(f"✅ Пользователь {user.name} был разбанен.")
            logger.info(f"{interaction.user} разбанил {user} — Причина: {reason}")
        except discord.NotFound:
            await interaction.response.send_message("❌ Этот пользователь не забанен.", ephemeral=True)
            logger.warning(f"{interaction.user} попытался разбанить незабаненного пользователя {user}")
        except Exception as e:
            logger.error(f"Ошибка при разбане {user}: {e}")
            await interaction.response.send_message("❌ Не удалось разбанить пользователя.", ephemeral=True)

    @unban.autocomplete("user_id")
    async def unban_autocomplete(self, interaction: discord.Interaction, current: str):
        bans = []
        async for ban_entry in interaction.guild.bans():
            bans.append(ban_entry)

        choices = []
        for entry in bans:
            user = entry.user
            display = f"{user.name}#{user.discriminator} ({user.id})"
            if current.lower() in display.lower():
                choices.append(app_commands.Choice(name=display[:100], value=str(user.id)))
            if len(choices) >= 20:
                break
        return choices

    # --- /кик ---
    @app_commands.command(name="кик", description="Кикает участника с сервера")
    async def kick(self, interaction: discord.Interaction, member: discord.Member, reason: str = "Без указания причины"):
        if not interaction.user.guild_permissions.kick_members:
            await interaction.response.send_message("❌ У тебя нет прав использовать эту команду.", ephemeral=True)
            logger.warning(f"{interaction.user} попытался кикнуть без прав")
            return

        try:
            try:
                await member.send(
                    f"Ты был кикнут с сервера **{interaction.guild.name}**.\nПричина: {reason}"
                )
            except discord.Forbidden:
                logger.info(f"Не удалось отправить ЛС {member} перед киком")

            await member.kick(reason=f"Кикнут модератором {interaction.user} — Причина: {reason}")
            await interaction.response.send_message(f"👢 {member.mention} был кикнут с сервера. Причина: {reason}")
            logger.info(f"{interaction.user} кикнул {member} — Причина: {reason}")
        except Exception as e:
            logger.error(f"Ошибка при кике {member}: {e}")
            await interaction.response.send_message("❌ Не удалось кикнуть участника.", ephemeral=True)

    # --- /мут ---
    @app_commands.command(name="мут", description="Выдаёт мут участнику на указанное количество минут")
    async def mute(self, interaction: discord.Interaction, member: discord.Member, minutes: int):
        if not interaction.user.guild_permissions.moderate_members:
            await interaction.response.send_message("❌ У тебя нет прав использовать эту команду.", ephemeral=True)
            logger.warning(f"{interaction.user} попытался замутить без прав")
            return

        try:
            duration = timedelta(minutes=minutes)
            try:
                await member.send(
                    f"Ты получил мут на **{minutes} минут** на сервере **{interaction.guild.name}**.\n"
                    f"Модератор: {interaction.user.display_name}"
                )
            except discord.Forbidden:
                logger.info(f"Не удалось отправить ЛС {member} перед мутом")

            await member.timeout(duration, reason=f"Мут на {minutes} минут (выдан модератором {interaction.user})")
            await interaction.response.send_message(f"🔇 {member.mention} получил мут на {minutes} минут.")
            logger.info(f"{interaction.user} выдал мут {member} на {minutes} минут")
        except Exception as e:
            logger.error(f"Ошибка при выдаче мута {member}: {e}")
            await interaction.response.send_message("❌ Не удалось выдать мут.", ephemeral=True)

    # --- /размут ---
    @app_commands.command(name="размут", description="Снимает мут с участника")
    async def unmute(self, interaction: discord.Interaction, member: discord.Member):
        if not interaction.user.guild_permissions.moderate_members:
            await interaction.response.send_message("❌ У тебя нет прав использовать эту команду.", ephemeral=True)
            logger.warning(f"{interaction.user} попытался размутить без прав")
            return

        try:
            await member.timeout(None, reason=f"Размут модератором {interaction.user}")
            try:
                await member.send(
                    f"Ты был размучен на сервере **{interaction.guild.name}**.\nМодератор: {interaction.user.display_name}"
                )
            except discord.Forbidden:
                logger.info(f"Не удалось отправить ЛС {member} после размута")

            await interaction.response.send_message(f"🔊 {member.mention} размучен.")
            logger.info(f"{interaction.user} размутил {member}")
        except Exception as e:
            logger.error(f"Ошибка при снятии мута с {member}: {e}")
            await interaction.response.send_message("❌ Не удалось снять мут.", ephemeral=True)


# --- Классы для выбора дуэли и победителя ---

class DuelSelectionView(View):
    def __init__(self, ctx: commands.Context):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.select = Select(placeholder="Выберите дуэль", min_values=1, max_values=1)

        for duel_id, duel in active_duels.items():
            guild = ctx.guild
            challenger = guild.get_member(duel["challenger_id"])
            opponent = guild.get_member(duel["opponent_id"])
            if challenger and opponent:
                label = f"{challenger.display_name} vs {opponent.display_name}"
                self.select.add_option(label=label, value=duel_id)

        self.select.callback = self.duel_selected
        self.add_item(self.select)

    async def duel_selected(self, interaction: discord.Interaction):
        if interaction.user != self.ctx.author:
            return await interaction.response.send_message("Только инициатор может выбрать дуэль.", ephemeral=True)

        duel_id = self.select.values[0]
        duel = active_duels.get(duel_id)
        if not duel:
            return await interaction.response.send_message("Дуэль не найдена.", ephemeral=True)

        guild = interaction.guild
        challenger = guild.get_member(duel["challenger_id"])
        opponent = guild.get_member(duel["opponent_id"])

        await interaction.response.send_message(
            f"Выбрана дуэль между {challenger.mention} и {opponent.mention}.\nКто победил?",
            view=WinnerButtonsView(duel_id),
            ephemeral=True
        )
        logger.info(f"{interaction.user} выбрал дуэль {duel_id} для назначения победителя")


class WinnerButtonsView(View):
    def __init__(self, duel_id):
        super().__init__(timeout=30)
        self.duel_id = duel_id
        duel = active_duels.get(duel_id)
        self.challenger_id = duel["challenger_id"]
        self.opponent_id = duel["opponent_id"]

        self.add_item(self.WinnerButton(duel_id, self.challenger_id, label="Победил Challenger 🟥"))
        self.add_item(self.WinnerButton(duel_id, self.opponent_id, label="Победил Opponent 🟦"))

    class WinnerButton(discord.ui.Button):
        def __init__(self, duel_id, winner_id, label):
            super().__init__(label=label, style=discord.ButtonStyle.success)
            self.duel_id = duel_id
            self.winner_id = winner_id

        async def callback(self, interaction: discord.Interaction):
            duel = active_duels.pop(self.duel_id, None)
            if not duel:
                return await interaction.response.send_message("Дуэль уже завершена.", ephemeral=True)

            loser_id = duel["opponent_id"] if self.winner_id == duel["challenger_id"] else duel["challenger_id"]

            # --- Обновляем статистику и кэш ---
            update_stats(self.winner_id, loser_id)
            await save_active_duels()

            winner = interaction.guild.get_member(self.winner_id)
            loser = interaction.guild.get_member(loser_id)

            await interaction.response.send_message(
                f"🎉 Победитель: {winner.mention if winner else self.winner_id}!\n"
                f"Проигравший: {loser.mention if loser else loser_id}.",
                ephemeral=False
            )
            logger.info(f"Дуэль {self.duel_id} завершена. Победитель: {winner}, Проигравший: {loser}")


# --- Setup ---
async def setup(bot: commands.Bot):
    from config import load_config
    config = load_config()
    await bot.add_cog(Admin(bot, config["CLAN_ROLE_IDS"], config["FRIEND_ROLE_ID"]))

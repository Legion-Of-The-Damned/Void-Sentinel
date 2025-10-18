import discord
import logging
from discord import app_commands
from discord.ext import commands
from datetime import timedelta
from discord.ui import Select, View, Button
from data import active_duels, save_active_duels, update_stats

# --- Настройка логгера ---
logger = logging.getLogger("Admin")


class Admin(commands.Cog):
    def __init__(self, bot: commands.Bot, clan_role_ids: list[int], friend_role_id: int):
        self.bot = bot
        self.clan_role_ids = clan_role_ids
        self.friend_role_id = friend_role_id

    # --- /победа ---
    @commands.hybrid_command(
        name="победа",
        description="Выбрать дуэль и присудить победу (только для админов)"
    )
    async def assign_winner_select(self, ctx: commands.Context):
        if not ctx.author.guild_permissions.kick_members:
            return await ctx.send("❌ У вас нет прав для назначения победителя.", ephemeral=True)

        # фильтруем корректные дуэли
        valid_duels = {
            duel_id: duel for duel_id, duel in active_duels.items()
            if duel.get("player1") and duel.get("player2")
        }

        if not valid_duels:
            return await ctx.send("Нет активных дуэлей для выбора.", ephemeral=True)

        view = DuelSelectionView(ctx, valid_duels)
        await ctx.send("Выберите дуэль, чтобы назначить победителя:", view=view, ephemeral=True)

    # --- /изгнание ---
    @app_commands.command(
        name="изгнание",
        description="Изгоняет члена из клана и назначает роль 'Друг клана'"
    )
    async def banish(self, interaction: discord.Interaction, member: discord.Member):
        if not interaction.user.guild_permissions.kick_members:
            await interaction.response.send_message(
                "❌ У тебя нет прав использовать эту команду.", ephemeral=True
            )
            return

        await interaction.response.defer(thinking=True)
        try:
            await self.banish_from_clan(member)
            await interaction.followup.send(
                f"✅ {member.mention} был изгнан и получил роль **Друг клана**."
            )
        except Exception as e:
            logger.error(f"Ошибка при изгнании {member}: {e}")
            await interaction.followup.send(f"❌ Не удалось изгнать {member}.")

    async def banish_from_clan(self, member: discord.Member):
        roles_to_remove = [r for r in member.roles if r.id in self.clan_role_ids]
        try:
            await member.remove_roles(*roles_to_remove, reason="Изгнан из клана (админ команда)")
        except discord.Forbidden:
            logger.warning(f"Не удалось снять роли с {member.display_name}")

        friend_role = discord.utils.get(member.guild.roles, id=self.friend_role_id)
        if friend_role:
            await member.add_roles(friend_role, reason="Назначен как 'Друг клана'")

        try:
            await member.send(f"Ты был изгнан из клана, но остался как **Друг клана**.")
        except discord.Forbidden:
            logger.warning(f"Не удалось отправить ЛС {member.display_name}")

    # --- /бан ---
    @app_commands.command(name="бан", description="Банит участника на сервере")
    async def ban(self, interaction: discord.Interaction, member: discord.Member, reason: str = "Без указания причины"):
        if not interaction.user.guild_permissions.ban_members:
            await interaction.response.send_message(
                "❌ У тебя нет прав использовать эту команду.", ephemeral=True
            )
            return

        try:
            try:
                await member.send(
                    f"Ты был **забанен** на сервере **{interaction.guild.name}**.\n"
                    f"Причина: {reason}\nМодератор: {interaction.user.display_name}"
                )
            except discord.Forbidden:
                logger.warning(f"Не удалось отправить ЛС {member.display_name}")

            await member.ban(reason=f"Забанен модератором {interaction.user} — Причина: {reason}")
            await interaction.response.send_message(f"⛔ {member.mention} был забанен. Причина: {reason}")
        except Exception as e:
            logger.error(f"Ошибка при бане {member}: {e}")
            await interaction.response.send_message("❌ Не удалось забанить участника.", ephemeral=True)

    # --- /разбан ---
    @app_commands.command(name="разбан", description="Разбанивает участника по ID")
    async def unban(self, interaction: discord.Interaction, user_id: str, reason: str = "Без указания причины"):
        if not interaction.user.guild_permissions.ban_members:
            await interaction.response.send_message(
                "❌ У тебя нет прав использовать эту команду.", ephemeral=True
            )
            return

        try:
            user = await self.bot.fetch_user(int(user_id))
        except Exception:
            await interaction.response.send_message("❌ Не удалось найти пользователя.", ephemeral=True)
            return

        try:
            await interaction.guild.unban(user, reason=f"Разбанен модератором {interaction.user} — Причина: {reason}")
            try:
                await user.send(f"Ты был **разбанен** на сервере **{interaction.guild.name}**.")
            except discord.Forbidden:
                logger.warning(f"Не удалось отправить ЛС {user.name} после разбана")

            await interaction.response.send_message(f"✅ Пользователь {user.name} был разбанен.")
        except discord.NotFound:
            await interaction.response.send_message("❌ Этот пользователь не забанен.", ephemeral=True)
        except Exception as e:
            logger.error(f"Ошибка при разбане {user}: {e}")
            await interaction.response.send_message("❌ Не удалось разбанить пользователя.", ephemeral=True)

    # --- /кик ---
    @app_commands.command(name="кик", description="Кикает участника с сервера")
    async def kick(self, interaction: discord.Interaction, member: discord.Member, reason: str = "Без указания причины"):
        if not interaction.user.guild_permissions.kick_members:
            await interaction.response.send_message(
                "❌ У тебя нет прав использовать эту команду.", ephemeral=True
            )
            return

        try:
            try:
                await member.send(f"Ты был кикнут с сервера **{interaction.guild.name}**.\nПричина: {reason}")
            except discord.Forbidden:
                logger.warning(f"Не удалось отправить ЛС {member.display_name}")

            await member.kick(reason=f"Кикнут модератором {interaction.user} — Причина: {reason}")
            await interaction.response.send_message(f"👢 {member.mention} был кикнут с сервера. Причина: {reason}")
        except Exception as e:
            logger.error(f"Ошибка при кике {member}: {e}")
            await interaction.response.send_message("❌ Не удалось кикнуть участника.", ephemeral=True)

    # --- /мут ---
    @app_commands.command(name="мут", description="Выдаёт мут участнику на указанное количество минут")
    async def mute(self, interaction: discord.Interaction, member: discord.Member, minutes: int):
        if not interaction.user.guild_permissions.moderate_members:
            await interaction.response.send_message(
                "❌ У тебя нет прав использовать эту команду.", ephemeral=True
            )
            return

        try:
            duration = timedelta(minutes=minutes)
            try:
                await member.send(f"Ты получил мут на **{minutes} минут** на сервере **{interaction.guild.name}**.")
            except discord.Forbidden:
                logger.warning(f"Не удалось отправить ЛС {member.display_name}")

            await member.timeout(duration, reason=f"Мут на {minutes} минут (выдан модератором {interaction.user})")
            await interaction.response.send_message(f"🔇 {member.mention} получил мут на {minutes} минут.")
        except Exception as e:
            logger.error(f"Ошибка при выдаче мута {member}: {e}")
            await interaction.response.send_message("❌ Не удалось выдать мут.", ephemeral=True)

    # --- /размут ---
    @app_commands.command(name="размут", description="Снимает мут с участника")
    async def unmute(self, interaction: discord.Interaction, member: discord.Member):
        if not interaction.user.guild_permissions.moderate_members:
            await interaction.response.send_message(
                "❌ У тебя нет прав использовать эту команду.", ephemeral=True
            )
            return

        try:
            await member.timeout(None, reason=f"Размут модератором {interaction.user}")
            try:
                await member.send(f"Ты был размучен на сервере **{interaction.guild.name}**.")
            except discord.Forbidden:
                logger.warning(f"Не удалось отправить ЛС {member.display_name} после размута")

            await interaction.response.send_message(f"🔊 {member.mention} размучен.")
        except Exception as e:
            logger.error(f"Ошибка при снятии мута с {member}: {e}")
            await interaction.response.send_message("❌ Не удалось снять мут.", ephemeral=True)


# --- Выбор дуэли для админов ---
class DuelSelectionView(View):
    def __init__(self, ctx: commands.Context, duels: dict):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.select = Select(placeholder="Выберите дуэль", min_values=1, max_values=1)

        for duel_id, duel in duels.items():
            player1 = duel.get("player1")
            player2 = duel.get("player2")
            if not player1 or not player2:
                continue
            label = f"{player1} vs {player2}"
            self.select.add_option(label=label, value=duel_id)

        self.select.callback = self.duel_selected
        self.add_item(self.select)

    async def duel_selected(self, interaction: discord.Interaction):
        if interaction.user != self.ctx.author:
            return await interaction.response.send_message(
                "Только инициатор может выбрать дуэль.", ephemeral=True
            )

        duel_id = self.select.values[0]
        duel = active_duels.get(duel_id)
        if not duel:
            return await interaction.response.send_message("Дуэль не найдена.", ephemeral=True)

        player1 = duel.get("player1")
        player2 = duel.get("player2")

        await interaction.response.send_message(
            f"Выбрана дуэль между {player1} и {player2}.\nКто победил?",
            view=WinnerButtonsView(duel_id, self.ctx.bot),
            ephemeral=True
        )


# --- Кнопки выбора победителя ---
class WinnerButtonsView(View):
    def __init__(self, duel_id, bot):
        super().__init__(timeout=30)
        self.duel_id = duel_id
        self.bot = bot
        duel = active_duels.get(duel_id)
        if not duel:
            return

        player1 = duel.get("player1")
        player2 = duel.get("player2")

        self.add_item(self.WinnerButton(duel_id, player1, bot, label=f"Победил {player1} 🟥"))
        self.add_item(self.WinnerButton(duel_id, player2, bot, label=f"Победил {player2} 🟦"))

    class WinnerButton(Button):
        def __init__(self, duel_id, winner_name, bot, label):
            super().__init__(label=label, style=discord.ButtonStyle.success)
            self.duel_id = duel_id
            self.winner_name = winner_name
            self.bot = bot

        async def callback(self, interaction: discord.Interaction):
            duel = active_duels.pop(self.duel_id, None)
            if not duel:
                await interaction.response.send_message("Дуэль уже завершена.", ephemeral=True)
                return

            player1 = duel.get("player1")
            player2 = duel.get("player2")
            loser_name = player2 if self.winner_name == player1 else player1

            update_stats(self.winner_name, loser_name)

            # сохраняем активные дуэли
            active_duels[self.duel_id] = duel
            await save_active_duels(self.bot)
            active_duels.pop(self.duel_id, None)

            await interaction.response.send_message(
                f"🎉 Победитель: {self.winner_name}!\nПроигравший: {loser_name}.",
                ephemeral=False
            )


# --- Setup ---
async def setup(bot: commands.Bot):
    from config import load_config
    config = load_config()
    await bot.add_cog(Admin(bot, config["CLAN_ROLE_IDS"], config["FRIEND_ROLE_ID"]))

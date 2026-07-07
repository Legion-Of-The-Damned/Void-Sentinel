import discord
import logging
import asyncio
import re

from discord import app_commands
from discord.ext import commands
from datetime import timedelta
from discord.ui import Select, View, Button

from data import active_duels, save_active_duels, update_stats


# --- логгер ---
logger = logging.getLogger("Admin")
logger.setLevel(logging.DEBUG)


SUCCESS = 25  # кастом уровень


logging.addLevelName(SUCCESS, "SUCCESS")


def success(self, msg, *args, **kwargs):
    if self.isEnabledFor(SUCCESS):
        self._log(SUCCESS, msg, args, **kwargs)


logging.Logger.success = success


# --- парсер времени ---
def parse_time_to_seconds(time_str: str) -> int:
    match = re.fullmatch(r"(\d+)([смч])", time_str.lower())
    if not match:
        raise ValueError("bad format")

    value = int(match.group(1))
    unit = match.group(2)

    logger.debug(f"parse_time: value={value}, unit={unit}")

    if unit == "с":
        return value
    if unit == "м":
        return value * 60
    if unit == "ч":
        return value * 3600

    raise ValueError("bad unit")


class Admin(commands.Cog):
    def __init__(self, bot: commands.Bot, clan_role_ids: list[int], friend_role_id: int):
        self.bot = bot
        self.clan_role_ids = clan_role_ids
        self.friend_role_id = friend_role_id

    # --- /победа ---
    @commands.hybrid_command(name="победа", description="Выбор дуэли")
    async def assign_winner_select(self, ctx: commands.Context):

        logger.info(f"/победа вызвал {ctx.author}")

        if not ctx.author.guild_permissions.kick_members:
            logger.warning("нет прав у пользователя")
            return await ctx.send("❌ Нет прав", ephemeral=True)

        valid_duels = {
            duel_id: duel for duel_id, duel in active_duels.items()
            if duel.get("player1") and duel.get("player2")
        }

        if not valid_duels:
            logger.warning("нет активных дуэлей")
            return await ctx.send("Нет дуэлей", ephemeral=True)

        logger.success("дуэли найдены")

        view = DuelSelectionView(ctx, valid_duels)
        await ctx.send("Выберите дуэль:", view=view, ephemeral=True)

    # --- /изгнание ---
    @app_commands.command(name="изгнание")
    async def banish(self, interaction: discord.Interaction, member: discord.Member):

        logger.info(f"изгнание {member}")

        if not interaction.user.guild_permissions.kick_members:
            logger.warning("нет прав")
            return await interaction.response.send_message("❌ Нет прав", ephemeral=True)

        await interaction.response.defer()

        try:
            roles = [r for r in member.roles if r.id in self.clan_role_ids]
            await member.remove_roles(*roles)

            friend = discord.utils.get(member.guild.roles, id=self.friend_role_id)
            if friend:
                await member.add_roles(friend)

            await member.send("Ты изгнан")

            logger.success(f"{member} изгнан")

            await interaction.followup.send(f"✅ {member.mention} изгнан")

        except Exception as e:
            logger.error(f"banish error: {e}")
            await interaction.followup.send("❌ ошибка")

    # --- /бан ---
    @app_commands.command(name="бан")
    async def ban(self, interaction: discord.Interaction, member: discord.Member, reason: str = "нет причины"):

        logger.info(f"бан {member}")

        if not interaction.user.guild_permissions.ban_members:
            return await interaction.response.send_message("❌ нет прав", ephemeral=True)

        try:
            await member.send(f"бан: {reason}")
        except Exception:
            logger.warning("DM не отправился")

        await member.ban(reason=reason)

        logger.success(f"{member} забанен")

        await interaction.response.send_message(f"⛔ {member} забанен")

    # --- /разбан ---
    @app_commands.command(name="разбан")
    async def unban(self, interaction: discord.Interaction, user_id: str):

        logger.info(f"разбан {user_id}")

        if not interaction.user.guild_permissions.ban_members:
            return await interaction.response.send_message("❌ нет прав", ephemeral=True)

        user = await self.bot.fetch_user(int(user_id))
        await interaction.guild.unban(user)

        logger.success(f"{user} разбанен")

        await interaction.response.send_message(f"✅ разбан {user}")

    # --- /кик ---
    @app_commands.command(name="кик")
    async def kick(self, interaction: discord.Interaction, member: discord.Member):

        logger.info(f"кик {member}")

        if not interaction.user.guild_permissions.kick_members:
            return await interaction.response.send_message("❌ нет прав", ephemeral=True)

        await member.kick()

        logger.success(f"{member} кикнут")

        await interaction.response.send_message(f"👢 {member} кикнут")

    # --- /мут ---
    @app_commands.command(name="мут")
    async def mute(self, interaction: discord.Interaction, member: discord.Member, minutes: int):

        logger.info(f"мут {member} {minutes}м")

        if not interaction.user.guild_permissions.moderate_members:
            return await interaction.response.send_message("❌ нет прав", ephemeral=True)

        await member.timeout(timedelta(minutes=minutes))

        logger.success(f"{member} мут")

        await interaction.response.send_message(f"🔇 мут {member}")

    # --- /мут гс ---
    @app_commands.command(name="мут_гс")
    async def voice_mute(self, interaction: discord.Interaction, member: discord.Member, time: str):

        logger.info(f"voice mute {member} {time}")

        if not interaction.user.guild_permissions.moderate_members:
            return await interaction.response.send_message("❌ нет прав", ephemeral=True)

        try:
            seconds = parse_time_to_seconds(time)

            if not member.voice or not member.voice.channel:
                return await interaction.response.send_message("❌ не в войсе", ephemeral=True)

            await member.edit(mute=True)

            logger.success(f"voice mute {member} {seconds}s")

            await interaction.response.send_message(f"🔇 {member} мут {time}")

            async def unmute():
                await asyncio.sleep(seconds)
                try:
                    await member.edit(mute=False)
                    logger.info(f"auto unmute {member}")
                except Exception as e:
                    logger.error(e)

            self.bot.loop.create_task(unmute())

        except ValueError:
            logger.warning("bad format")
            await interaction.response.send_message("❌ формат: 5с / 10м / 1ч", ephemeral=True)

    # --- /размут ---
    @app_commands.command(name="размут")
    async def unmute(self, interaction: discord.Interaction, member: discord.Member):

        logger.info(f"размут {member}")

        if not interaction.user.guild_permissions.moderate_members:
            return await interaction.response.send_message("❌ нет прав", ephemeral=True)

        await member.timeout(None)

        logger.success(f"{member} размучен")

        await interaction.response.send_message(f"🔊 {member} размучен")


# --- DUEL ---
class DuelSelectionView(View):
    def __init__(self, ctx, duels):
        super().__init__(timeout=60)
        self.ctx = ctx

        self.select = Select()

        for duel_id, duel in duels.items():
            self.select.add_option(
                label=f"{duel['player1']} vs {duel['player2']}",
                value=duel_id
            )

        self.select.callback = self.callback
        self.add_item(self.select)

    async def callback(self, interaction: discord.Interaction):
        duel_id = self.select.values[0]

        logger.info(f"duel selected {duel_id}")

        await interaction.response.send_message(
            "Кто победил?",
            view=WinnerButtonsView(duel_id, self.ctx.bot),
            ephemeral=True
        )


# --- WINNER ---
class WinnerButtonsView(View):
    def __init__(self, duel_id, bot):
        super().__init__()
        self.duel_id = duel_id
        self.bot = bot

        duel = active_duels.get(duel_id)
        if not duel:
            return

        p1 = duel["player1"]
        p2 = duel["player2"]

        self.add_item(self.WinnerButton(duel_id, p1))
        self.add_item(self.WinnerButton(duel_id, p2))

    class WinnerButton(Button):
        def __init__(self, duel_id, name):
            super().__init__(label=name, style=discord.ButtonStyle.success)
            self.duel_id = duel_id
            self.name = name

        async def callback(self, interaction: discord.Interaction):

            duel = active_duels.pop(self.duel_id, None)

            if not duel:
                logger.warning("duel already finished")
                return await interaction.response.send_message("уже завершено", ephemeral=True)

            p1 = duel["player1"]
            p2 = duel["player2"]

            loser = p2 if self.name == p1 else p1

            update_stats(self.name, loser)
            await save_active_duels(self.view.bot)

            logger.success(f"{self.name} победил")

            await interaction.response.send_message(
                f"🏆 {self.name} победил, {loser} проиграл"
            )


# --- setup ---
async def setup(bot: commands.Bot):
    from config import load_config
    cfg = load_config()

    await bot.add_cog(Admin(bot, cfg["CLAN_ROLE_IDS"], cfg["FRIEND_ROLE_ID"]))
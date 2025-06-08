import discord
import logging
import traceback
from discord import app_commands
from discord.ext import commands
from datetime import timedelta

class ClanGeneral(commands.Cog):
    def __init__(self, bot: commands.Bot, clan_role_ids: list[int], friend_role_id: int):
        self.bot = bot
        self.clan_role_ids = clan_role_ids
        self.friend_role_id = friend_role_id

    @app_commands.command(name="изгнание", description="Изгоняет члена из клана и назначает роль 'Друг клана'")
    async def banish(self, interaction: discord.Interaction, member: discord.Member):
        if not interaction.user.guild_permissions.kick_members:
            await interaction.response.send_message("❌ У тебя нет прав использовать эту команду.", ephemeral=True)
            return

        await interaction.response.defer(thinking=True)

        try:
            await self.banish_from_clan(member)
            await interaction.followup.send(f"✅ {member.mention} был изгнан из клана и получил роль **Друг клана**.")
        except Exception:
            logging.error("❌ Ошибка при изгнании участника:\n" + traceback.format_exc())
            await interaction.followup.send(f"❌ Не удалось изгнать {member.mention}. Произошла ошибка.")

    async def banish_from_clan(self, member: discord.Member):
        roles_to_remove = [r for r in member.roles if r.id in self.clan_role_ids]

        try:
            await member.remove_roles(*roles_to_remove, reason="Изгнан из клана (административная команда)")
        except discord.Forbidden:
            logging.warning(f"⚠️ Не удалось снять роли с {member.display_name} — недостаточно прав.")
            return

        friend_role = discord.utils.get(member.guild.roles, id=self.friend_role_id)
        if friend_role:
            await member.add_roles(friend_role, reason="Назначен как 'Друг клана' (административная команда)")

        try:
            await member.send(
                f"Привет, {member.name}!\n"
                "Ты был изгнан из клана, но остался на сервере как **Друг клана**."
            )
        except discord.Forbidden:
            logging.info(f"ℹ️ Не удалось отправить ЛС участнику {member.display_name}.")

    @app_commands.command(name="бан", description="Банит участника на сервере")
    async def ban(self, interaction: discord.Interaction, member: discord.Member, reason: str = "Без указания причины"):
        if not interaction.user.guild_permissions.ban_members:
            await interaction.response.send_message("❌ У тебя нет прав использовать эту команду.", ephemeral=True)
            return

        try:
            # Попытка отправить ЛС перед баном
            try:
                await member.send(
                    f"Ты был **забанен** на сервере **{interaction.guild.name}**.\n"
                    f"Причина: {reason}\n"
                    f"Модератор: {interaction.user.display_name}"
                )
            except discord.Forbidden:
                logging.info(f"ℹ️ Не удалось отправить ЛС участнику {member.display_name} перед баном.")

            await member.ban(reason=f"Забанен модератором {interaction.user} — Причина: {reason}")
            await interaction.response.send_message(f"⛔ {member.mention} был забанен. Причина: {reason}")
        except Exception as e:
            logging.error(f"❌ Ошибка при бане: {e}")
            await interaction.response.send_message("❌ Не удалось забанить участника.", ephemeral=True)

    @app_commands.command(name="разбан", description="Разбанивает участника по выбору из списка банов")
    @app_commands.describe(user_id="Выберите пользователя из списка забаненных")
    async def unban(self, interaction: discord.Interaction, user_id: str, reason: str = "Без указания причины"):
        if not interaction.user.guild_permissions.ban_members:
            await interaction.response.send_message("❌ У тебя нет прав использовать эту команду.", ephemeral=True)
            return

        try:
            user = await self.bot.fetch_user(int(user_id))
        except Exception:
            await interaction.response.send_message("❌ Не удалось найти пользователя. Убедись, что ID указан корректно.", ephemeral=True)
            return

        try:
            await interaction.guild.unban(user, reason=f"Разбанен модератором {interaction.user} — Причина: {reason}")

            try:
                await user.send(
                    f"Ты был **разбанен** на сервере **{interaction.guild.name}**.\n"
                    f"Модератор: {interaction.user.display_name}\n"
                    f"Причина: {reason}"
                )
            except discord.Forbidden:
                logging.info(f"ℹ️ Не удалось отправить ЛС пользователю {user.name} после разбана.")

            await interaction.response.send_message(f"✅ Пользователь {user.name} был разбанен.")
        except discord.NotFound:
            await interaction.response.send_message("❌ Этот пользователь не забанен.", ephemeral=True)
        except Exception as e:
            logging.error(f"❌ Ошибка при разбане: {e}")
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

    @app_commands.command(name="кик", description="Кикает участника с сервера")
    async def kick(self, interaction: discord.Interaction, member: discord.Member, reason: str = "Без указания причины"):
        if not interaction.user.guild_permissions.kick_members:
            await interaction.response.send_message("❌ У тебя нет прав использовать эту команду.", ephemeral=True)
            return

        try:
            # Попытка отправить ЛС перед киком
            try:
                await member.send(
                    f"Ты был кикнут с сервера **{interaction.guild.name}**.\n"
                    f"Причина: {reason}"
                )
            except discord.Forbidden:
                logging.info(f"ℹ️ Не удалось отправить ЛС участнику {member.display_name} перед киком.")

            await member.kick(reason=f"Кикнут модератором {interaction.user} — Причина: {reason}")
            await interaction.response.send_message(f"👢 {member.mention} был кикнут с сервера. Причина: {reason}")
        except Exception as e:
            logging.error(f"❌ Ошибка при кике: {e}")
            await interaction.response.send_message("❌ Не удалось кикнуть участника.", ephemeral=True)

    @app_commands.command(name="мут", description="Выдаёт мут участнику на указанное количество минут")
    async def mute(self, interaction: discord.Interaction, member: discord.Member, minutes: int):
        if not interaction.user.guild_permissions.moderate_members:
            await interaction.response.send_message("❌ У тебя нет прав использовать эту команду.", ephemeral=True)
            return

        try:
            duration = timedelta(minutes=minutes)

            # Попытка отправить ЛС перед мутом
            try:
                await member.send(
                    f"Ты получил мут на **{minutes} минут** на сервере **{interaction.guild.name}**.\n"
                    f"Модератор: {interaction.user.display_name}"
                )
            except discord.Forbidden:
                logging.info(f"ℹ️ Не удалось отправить ЛС участнику {member.display_name} перед мутом.")

            await member.timeout(duration, reason=f"Мут на {minutes} минут (выдан модератором {interaction.user})")
            await interaction.response.send_message(f"🔇 {member.mention} получил мут на {minutes} минут.")
        except Exception as e:
            logging.error(f"❌ Ошибка при выдаче мута: {e}")
            await interaction.response.send_message("❌ Не удалось выдать мут.", ephemeral=True)

    @app_commands.command(name="размут", description="Снимает мут с участника")
    async def unmute(self, interaction: discord.Interaction, member: discord.Member):
        if not interaction.user.guild_permissions.moderate_members:
            await interaction.response.send_message("❌ У тебя нет прав использовать эту команду.", ephemeral=True)
            return

        try:
            await member.timeout(None, reason=f"Размут модератором {interaction.user}")

            # Попытка отправить ЛС после размута
            try:
                await member.send(
                    f"Ты был размучен на сервере **{interaction.guild.name}**.\n"
                    f"Модератор: {interaction.user.display_name}"
                )
            except discord.Forbidden:
                logging.info(f"ℹ️ Не удалось отправить ЛС участнику {member.display_name} после размута.")

            await interaction.response.send_message(f"🔊 {member.mention} размучен.")
        except Exception as e:
            logging.error(f"❌ Ошибка при размуте: {e}")
            await interaction.response.send_message("❌ Не удалось снять мут.", ephemeral=True)

async def setup(bot: commands.Bot):
    from config import load_config
    config = load_config()
    await bot.add_cog(ClanGeneral(bot, config["CLAN_ROLE_IDS"], config["FRIEND_ROLE_ID"]))

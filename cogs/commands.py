import discord
import logging
import traceback
from discord import app_commands
from discord.ext import commands
from cogs.clan_info import send_clan_member_info

CLAN_ROLE_IDS = [
    828933676628705340, 1220385405476667442, 1272639057461121190,
    1231897102435745804, 1279150825998127134, 1240220163744337920,
    1248311771177947156, 1220297497310658570, 828750294518857758,
    1248739812492574760, 1248739005693169685, 1248739716292022345,
    1248739628677202031, 1248738074838564935, 1248743516658597979,
    1283378752327385149, 1273321385384742942,
]

FRIEND_ROLE_ID = 1151988812151521431  # "Друг клана"

class ClanCommands(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.synced = False

    @commands.Cog.listener()
    async def on_ready(self):
        if not self.synced:
            try:
                await self.bot.tree.sync()
                self.synced = True
                logging.info("Команды успешно синхронизированы.")
            except Exception as e:
                logging.error(f"Ошибка при синхронизации команд: {e}")

        try:
            await self.bot.change_presence(activity=discord.Game(name="⚔ На страже Легиона!"))
            logging.info("Статус бота установлен.")
        except Exception as e:
            logging.error(f"Ошибка при установке статуса: {e}")

    @app_commands.command(name="помощь", description="Показывает список доступных команд")
    async def help_command(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="⚔ Void Sentinel | Руководство по командам ⚔",
            description=(
                "Приветствую, воин! Я — Void Sentinel, верный страж клана Legion Of The Damned...\n\n"
                ":fire: **Основные команды:**\n"
                ":one: **Приветствие новичков**\n"
                ":two: **Уведомление об уходе**\n"
                ":three: **/помощь** — список команд\n"
                ":four: **/клан** — участники\n\n"
                "⚔ **Боевые команды:**\n"
                ":five: **/дуэль** — вызвать бой\n"
                ":six: **/победа** — назначить победу\n"
                ":seven: **/статистика** — рейтинг\n\n"
                ":rotating_light: **Админ-команды:**\n"
                ":eight: **/изгнание** — изгнать из клана"
            ),
            color=discord.Color.red()
        )
        embed.set_image(url="https://cdn.discordapp.com/attachments/1355929392072753262/1355975277930348675/ChatGPT_Image_30_._2025_._21_11_52.png")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="изгнание", description="Изгоняет члена из клана и даёт роль 'Друг клана'")
    async def banish(self, interaction: discord.Interaction, member: discord.Member):
        if not interaction.user.guild_permissions.kick_members:
            await interaction.response.send_message("❌ У тебя нет прав использовать эту команду.", ephemeral=True)
            return

        await interaction.response.defer()
        try:
            await self.banish_from_clan(member)
            await interaction.followup.send(f"{member.name} был изгнан из клана и стал другом клана!")
        except Exception:
            logging.error(traceback.format_exc())
            await interaction.followup.send(f"❌ Не удалось изгнать {member.name}. Произошла ошибка.")

    async def banish_from_clan(self, member: discord.Member):
        roles_to_remove = [r for r in member.roles if r.id in CLAN_ROLE_IDS]
        try:
            await member.remove_roles(*roles_to_remove)
            for r in roles_to_remove:
                logging.info(f"Удалена роль {r.name} у {member.name}")
        except discord.Forbidden:
            logging.warning(f"❌ Нет прав удалить роли у {member.name}")
            return

        friend_role = discord.utils.get(member.guild.roles, id=FRIEND_ROLE_ID)
        if friend_role:
            await member.add_roles(friend_role)
            logging.info(f"Добавлена роль 'Друг клана' {member.name}")
        else:
            logging.error(f"Роль 'Друг клана' не найдена!")

        try:
            await member.send(
                f"Привет, {member.name}!\n"
                "Ты был изгнан из клана, но остался на сервере как 'Друг клана'."
            )
        except discord.Forbidden:
            logging.warning(f"{member.name} закрыл личные сообщения.")

async def setup(bot: commands.Bot):
    await bot.add_cog(ClanCommands(bot))

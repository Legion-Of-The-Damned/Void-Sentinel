import discord
import logging
from discord.ext import commands
from discord import app_commands
from config import load_config

# --- Настройка логгера ---
logger = logging.getLogger("ClanInfo")


class ClanInfo(commands.Cog):
    def __init__(self, bot: commands.Bot, clan_role_names: list[str]):
        self.bot = bot
        self.clan_role_names = clan_role_names

    @commands.Cog.listener()
    async def on_ready(self):
        try:
            await self.bot.tree.sync()
            logger.success("Команды успешно синхронизированы")
        except Exception as e:
            logger.error(f"Ошибка при синхронизации команд: {e}")

    @app_commands.command(name="состав_клана", description="Отправить информацию о составе клана.")
    async def clan_info(self, interaction: discord.Interaction):
        await self.send_clan_member_info(interaction)

    async def send_clan_member_info(self, interaction: discord.Interaction):
        guild = interaction.guild
        channel = interaction.channel

        if not channel.permissions_for(guild.me).manage_webhooks:
            await interaction.response.send_message(
                "❌ У меня нет прав на создание вебхуков в этом канале.",
                ephemeral=True
            )
            logger.warning(f"Нет прав на создание вебхуков в канале {channel.name} ({guild.name})")
            return

        try:
            webhook = await channel.create_webhook(name=self.bot.user.name)

            members_by_role = {role: [] for role in self.clan_role_names}
            for member in guild.members:
                for role in member.roles:
                    if role.name in members_by_role:
                        members_by_role[role.name].append(member)

            total_members = sum(len(members) for members in members_by_role.values())

            description_lines = [f"**Количество участников клана:** {total_members}", "**Участники клана:**"]
            for role in reversed(self.clan_role_names):
                members = members_by_role[role]
                if members:
                    description_lines.append(f"\n**{role}**")
                    for member in members:
                        name = member.display_name
                        if not name.startswith("[LOTD]"):
                            name = f"[LOTD] {name}"
                        description_lines.append(f"- {name}")

            embed = discord.Embed(
                title="Информация о составе клана",
                description="\n".join(description_lines),
                color=discord.Color.red()
            )
            embed.set_footer(
                text=f"Запрошено: {interaction.user}",
                icon_url=interaction.user.avatar.url if interaction.user.avatar else None
            )
            embed.timestamp = discord.utils.utcnow()

            avatar_url = self.bot.user.avatar.url if self.bot.user.avatar else None
            await webhook.send(embed=embed, avatar_url=avatar_url)
            await webhook.delete()

            await interaction.response.send_message("✅ Информация о клане отправлена через вебхук.", ephemeral=True)
            logger.success(f"{interaction.user} отправил информацию о составе клана через вебхук")
        except Exception as e:
            logger.error(f"Ошибка при отправке информации о клане: {e}")
            await interaction.response.send_message("❌ Не удалось отправить информацию о клане.", ephemeral=True)


# --- Setup ---
async def setup(bot: commands.Bot):
    config = load_config()
    await bot.add_cog(ClanInfo(bot, config["CLAN_ROLE_NAMES"]))

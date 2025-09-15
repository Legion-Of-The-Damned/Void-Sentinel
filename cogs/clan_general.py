import discord
from discord.ext import commands
from discord import app_commands
import logging
import data

# --- Настройка логгера ---
logger = logging.getLogger("ClanGeneralCog")


class ClanGeneral(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # --- /статистика ---
    @commands.hybrid_command(name="статистика", description="Показать статистику участника")
    async def stats_command(self, ctx: commands.Context, user: discord.Member):
        try:
            stats_data = await data.get_stats()
            user_stats = stats_data.get(str(user.id), {"wins": 0, "losses": 0})

            await ctx.send(
                f"📊 Статистика {user.mention}:\n"
                f"Победы: {user_stats['wins']}\n"
                f"Поражения: {user_stats['losses']}"
            )
            logger.success(f"{ctx.author} запросил статистику для {user}")
        except Exception as e:
            logger.error(f"Ошибка при получении статистики для {user}: {e}")
            await ctx.send("❌ Не удалось получить статистику пользователя.")

    # --- /общая_статистика ---
    @app_commands.command(name="общая_статистика", description="Показать статистику по всем участникам")
    async def all_stats(self, interaction: discord.Interaction):
        try:
            stats_data = await data.get_stats()

            if not stats_data:
                await interaction.response.send_message("📉 Пока нет данных о боях.")
                logger.info(f"{interaction.user} вызвал общую статистику, но данных нет")
                return

            guild = interaction.guild
            stats_list = []
            for user_id_str, user_data in stats_data.items():
                user_id = int(user_id_str)
                member = guild.get_member(user_id)
                name = member.display_name if member else f"Пользователь {user_id}"
                wins = user_data.get("wins", 0)
                losses = user_data.get("losses", 0)
                total = wins + losses
                stats_list.append((name, wins, losses, total))

            stats_list.sort(key=lambda x: x[1], reverse=True)

            lines = ["**🏆 Общая статистика дуэлей:**\n"]
            for i, (name, wins, losses, total) in enumerate(stats_list, 1):
                lines.append(f"{i}. **{name}** — 🟢 Побед: {wins}, 🔴 Поражений: {losses}, ⚔ Всего: {total}")

            embed = discord.Embed(
                title="📊 Статистика дуэлей",
                description="\n".join(lines),
                color=discord.Color.gold()
            )
            embed.set_footer(
                text=f"Запрошено: {interaction.user.display_name}",
                icon_url=interaction.user.display_avatar.url
            )
            embed.timestamp = discord.utils.utcnow()

            await interaction.response.send_message(embed=embed)
            logger.success(f"{interaction.user} успешно вызвал общую статистику")
        except Exception as e:
            logger.error(f"Ошибка при формировании общей статистики: {e}")
            await interaction.response.send_message("❌ Не удалось получить общую статистику.", ephemeral=True)


# --- Setup ---
async def setup(bot: commands.Bot):
    await bot.add_cog(ClanGeneral(bot))

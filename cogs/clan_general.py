import discord
from discord.ext import commands
from discord import app_commands
import logging
import data

logger = logging.getLogger("ClanGeneral")


class ClanGeneral(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # --- /статистика ---
    @commands.hybrid_command(name="статистика", description="Показать статистику участника")
    async def stats_command(self, ctx: commands.Context, user: discord.Member):
        try:
            stats_data = await data.get_stats()
            user_key = data.key_from_name(user.display_name)
            user_stats = stats_data.get(user_key, {"wins": 0, "losses": 0, "display_name": user.display_name})

            display_name = user_stats.get("display_name", user.display_name)

            await ctx.send(
                f"📊 Статистика {display_name}:\n"
                f"Победы: {user_stats.get('wins', 0)}\n"
                f"Поражения: {user_stats.get('losses', 0)}"
            )
            logger.info(f"{ctx.author} запросил статистику для {user}")
        except Exception as e:
            logger.error(f"Ошибка при получении статистики для {user}: {e}")
            await ctx.send("❌ Не удалось получить статистику пользователя.")

    # --- /общая_статистика ---
    @app_commands.command(name="общая_статистика", description="Показать статистику по всем участникам")
    async def all_stats(self, interaction: discord.Interaction):
        try:
            # Откладываем ответ, чтобы безопасно отправлять followup
            await interaction.response.defer(thinking=True)
            
            stats_data = await data.get_stats()
            if not stats_data:
                await interaction.followup.send("📉 Пока нет данных о боях.")
                logger.info(f"{interaction.user} вызвал общую статистику, но данных нет")
                return

            stats_list = []
            for user_key, user_data in stats_data.items():
                display_name = user_data.get("display_name", user_key)
                wins = user_data.get("wins", 0)
                losses = user_data.get("losses", 0)
                total = wins + losses
                stats_list.append((display_name, wins, losses, total))

            # Сортируем по победам
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

            await interaction.followup.send(embed=embed)
            logger.info(f"{interaction.user} успешно вызвал общую статистику")
        except Exception as e:
            logger.error(f"Ошибка при формировании общей статистики: {e}")
            try:
                await interaction.followup.send("❌ Не удалось получить общую статистику.", ephemeral=True)
            except Exception:
                pass


# --- Setup ---
async def setup(bot: commands.Bot):
    await bot.add_cog(ClanGeneral(bot))

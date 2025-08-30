import discord
import logging
from discord import app_commands
from discord.ext import commands

class GeneralCommands(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.synced = False

    @commands.Cog.listener()
    async def on_ready(self):
        if not self.synced:
            try:
                await self.bot.tree.sync()
                self.synced = True
                logging.info("✅ Slash-команды успешно синхронизированы.")
            except Exception as e:
                logging.error(f"❌ Ошибка при синхронизации команд: {e}")

        try:
            await self.bot.change_presence(activity=discord.Game(name="Идут тех-работы"))
        except Exception as e:
            logging.warning(f"⚠️ Не удалось изменить статус: {e}")

    @app_commands.command(name="помощь", description="Показывает список доступных команд")
    async def help_command(self, interaction: discord.Interaction):
        wins = getattr(self.bot, 'total_duel_wins', None)
        losses = getattr(self.bot, 'total_duel_losses', None)
        if wins is None or losses is None:
            wins = "N/A"
            losses = "N/A"

        embed = discord.Embed(
            title="⚔ Void Sentinel | Руководство по командам ⚔",
            description=(
                "Приветствую, воин! Я — Void Sentinel, страж клана Legion Of The Damned.\n\n"

                ":fire: **Основные функции:**\n"          
                ":one: Приветствие новичков\n"
                ":two: Уведомление об уходе\n"
                ":three: `/помощь` — показать команды\n"
                ":four: `/состав_клана` — показать участников\n"
                ":five: `/информация_о_сервере` — посмотреть информацию о сервере с выбором категории\n\n"     

                "⚔ **Боевые команды:**\n"
                ":six: `/дуэль` — вызвать бой\n"
                ":seven: `/статистика` — посмотреть рейтинг\n"
                ":eight: `/общая_статистика` — общая статистика дуэлей\n\n"

                ":game_die: **Игровые мини-игры:**\n"
                ":nine: `/викторина` — пройти викторину\n"
                ":keycap_ten: `/монетка` — подбросить монетку (орёл/решка)\n"
                ":one: :one: `/камень_ножницы_бумага` — сыграть в игру КНБ\n\n"

                ":rotating_light: **Административные команды:**\n"
                ":one: :two: `/победа` — зафиксировать победу\n"
                ":one: :three: `/изгнание` — изгнать из клана и назначить роль 'Друг клана'\n"
                ":one: :four: `/бан @участник` — забанить участника\n"
                ":one: :five: `/разбан [ID пользователя]` — разбанить участника\n"
                ":one: :six: `/кик @участник` — кикнуть участника\n"
                ":one: :seven: `/мут @участник [минуты]` — выдать мут\n"
                ":one: :eight: `/размут @участник` — снять мут\n"
            ),
            color=discord.Color.red()
        )
        embed.set_image(url="https://cdn.discordapp.com/attachments/1355929392072753262/1355975277930348675/ChatGPT_Image_30_._2025_._21_11_52.png")
        await interaction.response.send_message(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(GeneralCommands(bot))

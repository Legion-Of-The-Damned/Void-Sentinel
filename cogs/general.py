import discord
import logging
from discord import app_commands
from discord.ext import commands
import platform
import psutil

# --- Настройка логгера ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s"
)
logger = logging.getLogger("discord")  # используем общий логгер

class GeneralCommands(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.synced = False

    # --- Событие готовности ---
    @commands.Cog.listener()
    async def on_ready(self):
        if not self.synced:
            try:
                await self.bot.tree.sync()
                self.synced = True
                logger.info("✅ Slash-команды успешно синхронизированы")
            except Exception as e:
                logger.error(f"❌ Ошибка при синхронизации команд: {e}")

        try:
            await self.bot.change_presence(activity=discord.Game(name="Идут тех-работы"))
            logger.info("Статус бота успешно изменён")
        except Exception as e:
            logger.warning(f"⚠️ Не удалось изменить статус: {e}")

    # --- Команда помощи ---
    @app_commands.command(name="помощь", description="Показывает список доступных команд")
    async def help_command(self, interaction: discord.Interaction):
        wins = getattr(self.bot, 'total_duel_wins', "N/A")
        losses = getattr(self.bot, 'total_duel_losses', "N/A")

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
        logger.info(f"📖 /помощь | Пользователь: {interaction.user} | Сервер: {interaction.guild.name if interaction.guild else 'ЛС'}")

    # --- Команда расширенного пинга ---
    @app_commands.command(name="пинг", description="Проверка состояния бота")
    async def ping(self, interaction: discord.Interaction):
        # Задержка
        latency_ms = round(self.bot.latency * 1000)

        # Версия Python
        python_version = platform.python_version()

        # Использование ресурсов
        process = psutil.Process()
        ram_usage_mb = process.memory_info().rss / 1024 / 1024  # в МБ
        cpu_usage_percent = psutil.cpu_percent(interval=0.5)  # за полсекунды

        # Формируем embed
        embed = discord.Embed(
            title="📊 Статистика бота",
            color=discord.Color.green()
        )
        embed.add_field(name="Задержка", value=f"`{latency_ms} ms`", inline=True)
        embed.add_field(name="Python", value=f"`{python_version}`", inline=True)
        embed.add_field(name="Использование RAM", value=f"`{ram_usage_mb:.2f} MB`", inline=True)
        embed.add_field(name="Использование CPU", value=f"`{cpu_usage_percent:.1f}%`", inline=True)

        await interaction.response.send_message(embed=embed)

        # --- Лог одной строкой ---
        logger.info(f"📶 /пинг | Пользователь: {interaction.user} | Сервер: {interaction.guild.name if interaction.guild else 'ЛС'} | Ping: {latency_ms} ms | RAM: {ram_usage_mb:.2f} MB | CPU: {cpu_usage_percent:.1f}%")

# --- Функция setup ---
async def setup(bot: commands.Bot):
    await bot.add_cog(GeneralCommands(bot))

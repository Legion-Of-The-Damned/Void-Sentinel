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

BOT_VERSION = "3.0"  # версия бота

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
    async def help_command(self, interaction):
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
                ":five: `/информация_о_сервере` — посмотреть информацию о сервере с выбором категории\n"
                ":six: `/пинг` — проверить статус бота и его ресурсы\n"
                ":seven: `/заявка` — заполнить анкету для вступления в клан\n\n"
                "⚔ **Боевые команды:**\n"
                ":eight: `/дуэль` — вызвать бой\n"
                ":nine: `/статистика` — посмотреть рейтинг\n"
                ":one: :zero: `/общая_статистика` — общая статистика дуэлей\n\n"
                ":game_die: **Игровые мини-игры:**\n"
                ":one: :one: `/викторина` — пройти викторину\n"
                ":one: :two: `/монетка` — подбросить монетку (орёл/решка)\n"
                ":one: :three: `/камень_ножницы_бумага` — сыграть в игру КНБ\n\n"
                ":rotating_light: **Административные команды:**\n"
                ":one: :four: `/победа` — зафиксировать победу\n"
                ":one: :five: `/изгнание` — изгнать из клана и назначить роль 'Друг клана'\n"
                ":one: :six: `/бан @участник` — забанить участника\n"
                ":one: :seven: `/разбан [ID пользователя]` — разбанить участника\n"
                ":one: :eight: `/кик @участник` — кикнуть участника\n"
                ":one: :nine: `/мут @участник [минуты]` — выдать мут\n"
                ":two: :zero: `/размут @участник` — снять мут\n"
            ),
            color=discord.Color.red()
        )
        embed.set_image(url="https://cdn.discordapp.com/attachments/1355929392072753262/1355975277930348675/ChatGPT_Image_30_._2025_._21_11_52.png")
        await interaction.response.send_message(embed=embed)
        logger.info(f"📖 /помощь | Пользователь: {interaction.user} | Сервер: {interaction.guild.name if interaction.guild else 'ЛС'}")

    # --- Команда расширенного пинга ---
    @app_commands.command(name="пинг", description="Проверка состояния бота")
    async def ping(self, interaction):
        latency_ms = round(self.bot.latency * 1000)
        python_version = platform.python_version()
        process = psutil.Process()
        ram_usage_mb = process.memory_info().rss / 1024 / 1024
        cpu_usage_percent = psutil.cpu_percent(interval=0.5)

        embed = discord.Embed(
            title="📊 Статистика бота",
            color=discord.Color.red()
        )
        embed.add_field(name="Задержка", value=f"{latency_ms} ms", inline=True)
        embed.add_field(name="Python", value=python_version, inline=True)
        embed.add_field(name="Версия бота", value=BOT_VERSION, inline=True)
        embed.add_field(name="Использование RAM", value=f"{ram_usage_mb:.2f} MB", inline=True)
        embed.add_field(name="Использование CPU", value=f"{cpu_usage_percent:.1f}%", inline=True)

        await interaction.response.send_message(embed=embed)

        logger.info(
            f"📶 /пинг | Пользователь: {interaction.user} | "
            f"Сервер: {interaction.guild.name if interaction.guild else 'ЛС'} | "
            f"Ping: {latency_ms} ms | RAM: {ram_usage_mb:.2f} MB | CPU: {cpu_usage_percent:.1f}% | "
            f"Версия бота: {BOT_VERSION}"
        )

# --- Функция setup ---
async def setup(bot: commands.Bot):
    await bot.add_cog(GeneralCommands(bot))

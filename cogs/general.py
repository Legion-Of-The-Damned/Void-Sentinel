import discord
import logging
from discord import app_commands
from discord.ext import commands, tasks
import platform
import psutil
import asyncio
from datetime import datetime, timedelta
import json
import os
from config import load_config

config = load_config()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s"
)
logger = logging.getLogger("discord")

BOT_VERSION = "3.7.7"

DATA_DIR = "data"
REMINDERS_FILE = os.path.join(DATA_DIR, "reminders.json")

user_reminders = {}

def save_reminders():
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(REMINDERS_FILE, "w", encoding="utf-8") as f:
        json.dump({
            str(user_id): [(dt.isoformat(), msg) for dt, msg in reminders]
            for user_id, reminders in user_reminders.items()
        }, f, ensure_ascii=False, indent=4)

def load_reminders():
    global user_reminders
    try:
        with open(REMINDERS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            user_reminders = {
                int(user_id): [(datetime.fromisoformat(dt), msg) for dt, msg in reminders]
                for user_id, reminders in data.items()
            }
    except FileNotFoundError:
        user_reminders = {}

class GeneralCommands(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.synced = False
        load_reminders()
        self.check_reminders.start()

    @commands.Cog.listener()
    async def on_ready(self):
        if not self.synced:
            try:
                await self.bot.tree.sync()
                self.synced = True
                logger.info("Slash-команды синхронизированы")
            except Exception as e:
                logger.error(f"Ошибка синхронизации: {e}")

        try:
            await self.bot.change_presence(activity=discord.Game(name="Идёт бета-тестирование"))
        except Exception as e:
            logger.warning(f"Не удалось изменить статус: {e}")

    @app_commands.command(name="помощь", description="Показывает список доступных команд")
    async def help_command(self, interaction):
        embed = discord.Embed(
            title="⚔ Void Sentinel | Руководство по командам ⚔",
            description=(
                ":fire: **Основные функции:**\n"
                ":one: Приветствие новичков\n"
                ":two: Уведомление об уходе (бан / кик / выход)\n"
                ":three: `/помощь` — список команд\n"
                ":four: `/состав_клана`\n"
                ":five: `/информация_о_сервере`\n"
                ":six: `/пинг`\n"
                ":seven: `/заявка`\n\n"

                "⚔ **Система КВ:**\n"
                ":eight: Ежедневные уведомления о КВ\n"
                ":nine: Авто-рассылка в ЛС участникам\n"
                ":keycap_ten: `20:30` — старт сетки КВ\n"
                ":one::one: `20:50` — уведомление «10 минут до КВ»\n"
                ":one::two: `21:00` — уведомление о начале КВ\n"
                ":one::three: Случайные арты и embeds Legion Of The Damned\n\n"

                "⚔ **Боевые команды:**\n"
                ":one::four: `/дуэль`\n"
                ":one::five: `/статистика`\n"
                ":one::six: `/общая_статистика`\n\n"

                ":microphone2: **Голосовые и аудио функции:**\n"
                ":one::seven: `/музыка [ссылка]` — воспроизведение треков\n"
                ":one::eight: Автосоздание голосовых каналов\n\n"

                ":memo: **Личные заметки:**\n"
                ":one::nine: `/напомни [минуты] [текст]`\n\n"

                ":rotating_light: **Администрация:**\n"
                ":two::zero: `/победа`\n"
                ":two::one: `/изгнание`\n"
                ":two::two: `/бан @участник`\n"
                ":two::three: `/разбан [ID]`\n"
                ":two::four: `/кик @участник`\n"
                ":two::five: `/мут @участник`\n"
                ":two::six: `/размут @участник`\n"
            ),
            color=discord.Color.red()
        )

        embed.set_image(url=config["IMAGE_URL"])

        await interaction.response.send_message(embed=embed)

        logger.info(f"/помощь | {interaction.user} | {interaction.guild.name if interaction.guild else 'ЛС'}")

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
        embed.add_field(name="RAM", value=f"{ram_usage_mb:.2f} MB", inline=True)
        embed.add_field(name="CPU", value=f"{cpu_usage_percent:.1f}%", inline=True)

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="напомни", description="Создать напоминание")
    async def remind(self, interaction: discord.Interaction, minutes: int, message: str):
        remind_time = datetime.utcnow() + timedelta(minutes=minutes)
        user_id = interaction.user.id

        user_reminders.setdefault(user_id, []).append((remind_time, message))
        save_reminders()

        await interaction.response.send_message(
            f"⏰ Напоминание через {minutes} минут: {message}",
            ephemeral=True
        )

    @tasks.loop(seconds=30)
    async def check_reminders(self):
        now = datetime.utcnow()

        for user_id, reminders in list(user_reminders.items()):
            for remind_time, message in reminders:
                if now >= remind_time:
                    user = self.bot.get_user(user_id)
                    if user:
                        try:
                            await user.send(f"🔔 Напоминание: {message}")
                        except:
                            pass

                    reminders.remove((remind_time, message))
                    save_reminders()

            if not reminders:
                user_reminders.pop(user_id, None)
                save_reminders()

    @check_reminders.before_loop
    async def before_check_reminders(self):
        await self.bot.wait_until_ready()

async def setup(bot: commands.Bot):
    await bot.add_cog(GeneralCommands(bot))

import logging
import asyncio
from discord.ext import commands
from discord import Intents
from config import load_config
from logging_setup import setup_logging

# Настройка логирования
setup_logging()

# Загрузка конфигурации
DISCORD_TOKEN, GUILD_ID, CHANNEL_ID, WEBHOOK_URL, GIF_URL, IMAGE_URL, AVATAR_URL = load_config()
if not DISCORD_TOKEN:
    raise ValueError("❌ Discord токен не найден в конфигурации.")

# Интенты
intents = Intents.default()
intents.members = True
intents.message_content = True

# Экземпляр бота
bot = commands.Bot(command_prefix='/', intents=intents)

# Загрузка cogs
async def load_cogs():
    cogs = [
        "cogs.events",
        "cogs.commands",
        "cogs.duel",
        "cogs.clan_info",
    ]
    for cog in cogs:
        try:
            await bot.load_extension(cog)
            logging.info(f"✅ Загружен cog: {cog}")
        except Exception as e:
            logging.error(f"⚠️ Ошибка при загрузке cog {cog}: {e}")

@bot.event
async def on_ready():
    logging.info(f"✅ Бот {bot.user} успешно запущен (ID: {bot.user.id})")

# Основная функция
async def main():
    logging.info("🚀 Запуск бота...")
    async with bot:
        await load_cogs()
        await bot.start(DISCORD_TOKEN)
    logging.info("🛑 Бот завершил работу.")

# Запуск
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("❌ Запуск остановлен вручную.")
    except Exception as e:
        logging.critical(f"🔥 Критическая ошибка при запуске: {e}")

import logging
import asyncio
from discord.ext import commands
from discord import Intents
from config import load_config
from logging_setup import setup_logging

def create_bot():
    intents = Intents.default()
    intents.members = True
    intents.message_content = True
    return commands.Bot(command_prefix='/', intents=intents)

async def load_cogs(bot):
    cogs = [
        "cogs.events",
        "cogs.general",         # 🔄 Было: commands
        "cogs.duel",
        "cogs.clan_info",
        "cogs.admin"     # 🆕 Новый Cog с командой изгнания
    ]

    errors = []
    for cog in cogs:
        try:
            await bot.load_extension(cog)
        except Exception as e:
            errors.append((cog, str(e)))

    if not errors:
        logging.info("✅ Все модули (cogs) успешно загружены и работают.")
    else:
        for cog, error in errors:
            logging.error(f"⚠️ Ошибка при загрузке модуля {cog}: {error}")

async def main():
    setup_logging()
    config = load_config()

    if not config.get("DISCORD_TOKEN"):
        raise ValueError("❌ Discord токен не найден в конфигурации.")

    bot = create_bot()

    @bot.event
    async def on_ready():
        logging.info(f"✅ Бот {bot.user} успешно запущен (ID: {bot.user.id})")
        for guild in bot.guilds:
            logging.info(f"🛡 Подключён к серверу: {guild.name} (ID: {guild.id}) | Участников: {guild.member_count}")

    await load_cogs(bot)
    await bot.start(config["DISCORD_TOKEN"])

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("❌ Запуск остановлен вручную.")
    except Exception as e:
        logging.critical(f"🔥 Критическая ошибка при запуске: {e}")

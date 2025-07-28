import discord
import logging
import asyncio
from discord.ext import commands
from discord import Intents
from config import load_config
from logging_setup import setup_logging


def create_bot() -> commands.Bot:
    intents = Intents.default()
    intents.members = True
    intents.message_content = True
    return commands.Bot(command_prefix='/', intents=intents)


async def load_cogs(bot: commands.Bot):
    cogs = [
        "cogs.events",
        "cogs.general",       # Команды общего назначения
        "cogs.duel",          # Система дуэлей
        "cogs.clan_info",     # Информация о клане
        "cogs.admin",         # Админ-команды
    ]

    errors = []
    for cog in cogs:
        try:
            await bot.load_extension(cog)
        except Exception as e:
            errors.append((cog, str(e)))

    if errors:
        for cog, error in errors:
            logging.error(f"⚠️ Ошибка при загрузке модуля `{cog}`: {error}")
    else:
        logging.info("✅ Все модули успешно загружены.")


async def main():
    setup_logging()
    config = load_config()

    token = config.get("DISCORD_TOKEN")
    if not token:
        raise ValueError("❌ Discord токен не найден в конфигурации.")

    bot = create_bot()

    @bot.event
    async def on_ready():
        logging.info(f"✅ Бот `{bot.user}` успешно запущен (ID: {bot.user.id})")
        for guild in bot.guilds:
            logging.info(f"🛡 Сервер: {guild.name} | ID: {guild.id} | Участников: {guild.member_count}")

    await load_cogs(bot)
    try:
        await bot.start(token)
    except discord.LoginFailure:
        logging.critical("❌ Неверный Discord токен.")
    except Exception as e:
        logging.critical(f"🔥 Критическая ошибка при запуске: {e}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("🛑 Запуск остановлен вручную.")
    except Exception as e:
        logging.critical(f"🚨 Неожиданная ошибка: {e}")

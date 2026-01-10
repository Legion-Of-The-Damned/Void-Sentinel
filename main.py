import discord
import logging
import asyncio
from discord.ext import commands
from discord import Intents
from config import load_config
from logging_setup import setup_logging
import data  # ленивый кэш
import traceback
import os, sys

os.chdir(os.path.dirname(os.path.abspath(sys.argv[0])))

logger = logging.getLogger("main")


def create_bot() -> commands.Bot:
    """Создаёт экземпляр бота с нужными интентами."""
    intents = Intents.default()
    intents.members = True
    intents.message_content = True
    return commands.Bot(command_prefix='/', intents=intents)

async def load_cogs(bot: commands.Bot):
    """Асинхронная загрузка всех когов, включая музыкальный модуль."""
    cogs = [
        "cogs.admin",
        "cogs.applications",
        "cogs.clan_general",
        "cogs.clan_info",
        "cogs.coinflip",
        "cogs.duel",
        "cogs.events",
        "cogs.general",
        "cogs.info",
        "cogs.music",
        "cogs.quiz",
        "cogs.rps",
        "cogs.voting"
    ]

    errors = []
    for cog in cogs:
        if cog in bot.extensions:
            logger.debug(f"🔁 Ког {cog} уже загружен, пропускаем.")
            continue
        try:
            await bot.load_extension(cog)
        except Exception:
            errors.append((cog, traceback.format_exc()))

    if errors:
        failed_cogs = ", ".join([c for c, _ in errors])
        logger.critical(f"❌ Ошибки при загрузке модулей: {failed_cogs}")
        for cog, error in errors:
            logger.error(f"\n--- Ошибка в `{cog}` ---\n{error}\n--- Конец ошибки ---")
    else:
        logger.success("🎉 Все файлы cogs успешно загружены!")

async def main():
    """Главная точка входа."""
    config = load_config()
    setup_logging(config)

    token = config.get("DISCORD_TOKEN")
    if not token:
        raise ValueError("❌ Discord токен не найден в конфигурации.")

    bot = create_bot()

    @bot.event
    async def on_ready():
        logger.success(f"🤖 Бот `{bot.user}` успешно запущен (ID: {bot.user.id})")
        for guild in bot.guilds:
            logger.info(f"🛡 Сервер: {guild.name} | ID: {guild.id} | Участников: {guild.member_count}")

    # Загружаем коги (включая музыкальный)
    await load_cogs(bot)

    try:
        await bot.start(token)
    except discord.LoginFailure:
        logger.critical("❌ Неверный Discord токен.")
    except Exception as e:
        logger.critical(f"🔥 Критическая ошибка при запуске: {e}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.warning("🛑 Запуск остановлен вручную.")
    except Exception as e:
        logger.critical(f"🚨 Неожиданная ошибка: {e}")

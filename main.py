import discord
import logging
import asyncio
from discord.ext import commands
from discord import Intents
from config import load_config
from logging_setup import setup_logging
import data  # импортируем модуль с ленивым кэшем

logger = logging.getLogger("main")

def create_bot() -> commands.Bot:
    intents = Intents.default()
    intents.members = True
    intents.message_content = True
    return commands.Bot(command_prefix='/', intents=intents)

async def load_cogs(bot: commands.Bot):
    cogs = [
        "cogs.events",
        "cogs.general",
        "cogs.duel",
        "cogs.quiz",
        "cogs.voting",
        "cogs.coinflip",
        "cogs.role_reactions",
        "cogs.applications",
        "cogs.verification",
        "cogs.clan_info",
        "cogs.info",
        "cogs.rps_cog",
        "cogs.admin",
        "cogs.clan_general",
    ]

    errors = []
    for cog in cogs:
        if cog in bot.extensions:
            logger.debug(f"Ког {cog} уже загружен, пропускаем")
            continue
        try:
            await bot.load_extension(cog)
        except Exception as e:
            import traceback
            errors.append((cog, traceback.format_exc()))

    if errors:
        failed_cogs = ", ".join([c for c, _ in errors])
        logger.critical(f"❌ Ошибки при загрузке модулей: {failed_cogs}")
        for cog, error in errors:
            logger.debug(f"Причина сбоя `{cog}`: {error}")
    else:
        logger.success("🎉 Все модули успешно загружены!")

async def main():
    config = load_config()          # 1. Загружаем конфиг
    setup_logging(config)           # 2. Настраиваем логирование с GitHub-бэкапом

    token = config.get("DISCORD_TOKEN")
    if not token:
        raise ValueError("❌ Discord токен не найден в конфигурации.")

    bot = create_bot()

    # -------------------------------
    # Важная правка: загружаем кэш из GitHub перед когами
    await data.load_data()
    logger.success("📂 Кэш данных (stats и active_duels) успешно загружен")
    # -------------------------------

    @bot.event
    async def on_ready():
        logger.success(f"🤖 Бот `{bot.user}` успешно запущен (ID: {bot.user.id})")
        for guild in bot.guilds:
            logger.info(f"🛡 Сервер: {guild.name} | ID: {guild.id} | Участников: {guild.member_count}")

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

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
        "cogs.general",
        "cogs.duel",
        "cogs.quiz",
        "cogs.voting",
        "cogs.coinflip",
        "cogs.role_reactions",
        "cogs.coinflip",
        "cogs.invite",
        "cogs.verification",
        "cogs.clan_info",
        "cogs.rps_cog",
        "cogs.admin",
        "cogs.clan_general",  # убедись, что загружаешь только один раз
    ]

    errors = []
    for cog in cogs:
        if cog in bot.extensions:
            logging.info(f"Ког {cog} уже загружен, пропускаем")
            continue
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
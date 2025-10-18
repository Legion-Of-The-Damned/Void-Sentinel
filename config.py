from dotenv import load_dotenv
import os
import logging

# получаем логгер для этого модуля
logger = logging.getLogger("config")

# автоматически ищет .env в папке с main.py
if load_dotenv():
    logger.debug("Файл .env успешно загружен")
else:
    logger.warning("Файл .env не найден, используются только переменные окружения")


def getenv_int(key, default=0):
    """Помогает получать числовые переменные из окружения"""
    val = os.getenv(key, default)
    try:
        return int(val)
    except ValueError:
        logger.warning(f"⚠️ Переменная {key} должна быть числом, но получено: {val}. Используется {default}.")
        return default


def getenv_list(key):
    """Получает список чисел или строк через запятую"""
    val = os.getenv(key, "")
    if not val:
        return []
    try:
        return [int(x) for x in val.split(",")]
    except ValueError:
        result = [x.strip() for x in val.split(",")]
        logger.debug(f"ℹ️ Переменная {key} интерпретирована как список строк: {result}")
        return result


def load_config():
    config = {
        "DISCORD_TOKEN": os.getenv("DISCORD_TOKEN"),
        "GUILD_ID": getenv_int("GUILD_ID"),
        "CHANNEL_ID": getenv_int("CHANNEL_ID"),
        "VERIFY_CHANNEL_ID": getenv_int("VERIFY_CHANNEL_ID"),
        "VERIFIED_ROLE_ID": getenv_int("VERIFIED_ROLE_ID"),
        "VERIFY_EMOJI": os.getenv("VERIFY_EMOJI", "✅"),
        "WEBHOOK_URL": os.getenv("WEBHOOK_URL"),
        "IMAGE_URL": os.getenv(
            "IMAGE_URL",
            "https://cdn.discordapp.com/attachments/1355929392072753262/1370486966977691689/ChatGPT_Image_9_._2025_._22_45_29.png"
        ),
        "AVATAR_URL": os.getenv(
            "AVATAR_URL",
            "https://cdn.discordapp.com/attachments/1355929392072753262/1367553212474982420/Void_Sentinel.jpg"
        ),
        "CLAN_ROLE_NAMES": os.getenv("CLAN_ROLE_NAMES", "💀Легион Проклятых🔥").split(","),
        "APPLICATIONS_CHANNEL_ID": getenv_int("APPLICATIONS_CHANNEL_ID"),
        "MEMBER_ROLE_ID": getenv_int("MEMBER_ROLE_ID"),
        "STAFF_ROLE_NAME": os.getenv("STAFF_ROLE_NAME", "Модератор"),
        "CLAN_ROLE_IDS": getenv_list("CLAN_ROLE_IDS"),
        "FRIEND_ROLE_ID": getenv_int("FRIEND_ROLE_ID"),
        "GITHUB_TOKEN": os.getenv("MY_GITHUB_TOKEN"),
        "REPO_NAME": os.getenv("REPO_NAME", "Legion-Of-The-Damned/-VS-Data-Base"),
        "SUPABASE_URL": os.getenv("SUPABASE_URL"),
        "SUPABASE_KEY": os.getenv("SUPABASE_KEY"),

        "QUIZ_QUESTIONS_PATH": "quiz_questions.json"
    }

    return config

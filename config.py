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
        # --- Discord ---
        "DISCORD_TOKEN": os.getenv("DISCORD_TOKEN"),
        "GUILD_ID": getenv_int("GUILD_ID"),
        "CHANNEL_ID": getenv_int("CHANNEL_ID"),
        "VERIFY_CHANNEL_ID": getenv_int("VERIFY_CHANNEL_ID"),
        "VERIFIED_ROLE_ID": getenv_int("VERIFIED_ROLE_ID"),
        "VERIFY_EMOJI": os.getenv("VERIFY_EMOJI", "✅"),

        # --- Webhook ---
        "WEBHOOK_URL": os.getenv("WEBHOOK_URL"),
        "AVATAR_URL": os.getenv(
            "AVATAR_URL",
            "https://cdn.discordapp.com/attachments/1355929392072753262/1367553212474982420/Void_Sentinel.jpg"
        ),

        # --- Embed images (РАЗДЕЛЕНЫ) ---
        "HELP_IMAGE_URL": os.getenv(
            "HELP_IMAGE_URL",
            "https://cdn.discordapp.com/attachments/1355929392072753262/1355975277930348675/ChatGPT_Image_30_._2025_._21_11_52.png?ex=69751263&is=6973c0e3&hm=d10e91dc91f47c7ae0e716e3dff3a3f340e127c6a3a3923959c4d0e30da3bdca&"
        ),
        "WELCOME_IMAGE_URL": os.getenv(
            "WELCOME_IMAGE_URL",
            "https://cdn.discordapp.com/attachments/1355929392072753262/1370486966977691689/ChatGPT_Image_9_._2025_._22_45_29.png?ex=69752173&is=6973cff3&hm=0ac9cdf1bfc449494894c6ed918144cd661d05153120ff28387cf500b9bc5c3f&"
        ),

        # --- Roles / Clan ---
        "CLAN_ROLE_NAMES": os.getenv(
            "CLAN_ROLE_NAMES",
            "💀Легион Проклятых🔥"
        ).split(","),

        "CLAN_ROLE_IDS": getenv_list("CLAN_ROLE_IDS"),
        "APPLICATIONS_CHANNEL_ID": getenv_int("APPLICATIONS_CHANNEL_ID"),
        "MEMBER_ROLE_ID": getenv_int("MEMBER_ROLE_ID"),
        "FRIEND_ROLE_ID": getenv_int("FRIEND_ROLE_ID"),
        "STAFF_ROLE_NAME": os.getenv("STAFF_ROLE_NAME", "Модератор"),

        # --- GitHub ---
        "GITHUB_TOKEN": os.getenv("MY_GITHUB_TOKEN"),
        "REPO_NAME": os.getenv(
            "REPO_NAME",
            "Legion-Of-The-Damned/-VS-Data-Base"
        ),

        # --- Supabase ---
        "SUPABASE_URL": os.getenv("SUPABASE_URL"),
        "SUPABASE_KEY": os.getenv("SUPABASE_KEY"),

        # --- Quiz ---
        "QUIZ_QUESTIONS_PATH": "quiz_questions.json",
    }

    return config
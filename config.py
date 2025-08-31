from dotenv import load_dotenv
import os

load_dotenv()  # автоматически ищет .env в папке с main.py

def getenv_int(key, default=0):
    """Помогает получать числовые переменные из окружения"""
    try:
        return int(os.getenv(key, default))
    except ValueError:
        return default

def getenv_list(key):
    """Получает список чисел или строк через запятую"""
    val = os.getenv(key, "")
    if not val:
        return []
    try:
        return [int(x) for x in val.split(",")]
    except ValueError:
        return [x.strip() for x in val.split(",")]

def load_config():
    return {
        "DISCORD_TOKEN": os.getenv("DISCORD_TOKEN"),
        "GUILD_ID": getenv_int("GUILD_ID"),
        "CHANNEL_ID": getenv_int("CHANNEL_ID"),
        "VERIFY_CHANNEL_ID": getenv_int("VERIFY_CHANNEL_ID"),
        "VERIFIED_ROLE_ID": getenv_int("VERIFIED_ROLE_ID"),
        "VERIFY_EMOJI": os.getenv("VERIFY_EMOJI", "✅"),
        "WEBHOOK_URL": os.getenv("WEBHOOK_URL"),
        "IMAGE_URL": os.getenv("IMAGE_URL", "https://cdn.discordapp.com/attachments/1355929392072753262/1370486966977691689/ChatGPT_Image_9_._2025_._22_45_29.png"),
        "AVATAR_URL": os.getenv("AVATAR_URL", "https://cdn.discordapp.com/attachments/1355929392072753262/1367553212474982420/Void_Sentinel.jpg"),
        "CLAN_ROLE_NAMES": os.getenv("CLAN_ROLE_NAMES", "💀Легион Проклятых🔥").split(","),
        "CLAN_ROLE_IDS": getenv_list("CLAN_ROLE_IDS"),
        "FRIEND_ROLE_ID": getenv_int("FRIEND_ROLE_ID"),
        "GITHUB_TOKEN": os.getenv("MY_GITHUB_TOKEN"),
        "REPO_NAME": os.getenv("REPO_NAME", "Legion-Of-The-Damned/-VS-Data-Base"),
        "QUIZ_QUESTIONS_PATH": "quiz_questions.json"
    }

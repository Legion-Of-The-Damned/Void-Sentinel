import os

def load_config():
    return {
        "DISCORD_TOKEN": os.getenv("DISCORD_TOKEN"),
        "GUILD_ID": int(os.getenv("GUILD_ID", 0)),
        "CHANNEL_ID": int(os.getenv("CHANNEL_ID", 0)),
        "WEBHOOK_URL": os.getenv("WEBHOOK_URL"),
        "IMAGE_URL": os.getenv("IMAGE_URL", ""),  # можно оставить в коде, если не секрет
        "AVATAR_URL": os.getenv("AVATAR_URL", ""),
        "CLAN_ROLE_NAMES": os.getenv("CLAN_ROLE_NAMES", "💀Легион Проклятых🔥").split(","),
        "CLAN_ROLE_IDS": [int(x) for x in os.getenv("CLAN_ROLE_IDS", "").split(",") if x],
        "FRIEND_ROLE_ID": int(os.getenv("FRIEND_ROLE_ID", 0)),
        "GITHUB_TOKEN": os.getenv("GITHUB_TOKEN"),
    }

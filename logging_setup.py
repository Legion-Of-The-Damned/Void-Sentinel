import logging
import sys
import os
from logging.handlers import TimedRotatingFileHandler
from datetime import datetime, timedelta
from github import Github

class ColorFormatter(logging.Formatter):
    COLORS = {
        'DEBUG': '\033[90m',
        'INFO': '\033[94m',
        'WARNING': '\033[93m',
        'ERROR': '\033[91m',
        'CRITICAL': '\033[1;91m',
        'SUCCESS': '\033[92m',
        'RESET': '\033[0m',
    }

    def format(self, record):
        color = self.COLORS.get(record.levelname, self.COLORS['RESET'])
        reset = self.COLORS['RESET']
        message = super().format(record)
        return f"{color}{message}{reset}"

class CustomDiscordFormatter(logging.Formatter):
    def format(self, record):
        msg = record.getMessage()
        if "logging in using static token" in msg:
            record.msg = "🔑 Авторизация через токен выполнена"
            record.args = ()
        elif "has connected to Gateway" in msg:
            record.msg = "🌐 Шард успешно подключён к Gateway"
            record.args = ()
        return super().format(record)

def push_log_to_github(local_path, archive_path, config):
    """Пушим лог в GitHub, создаём или обновляем файл."""
    if not os.path.exists(local_path):
        return

    token = config.get("GITHUB_TOKEN")
    repo_name = config.get("REPO_NAME")
    if not token or not repo_name:
        return

    g = Github(token)
    repo = g.get_repo(repo_name)

    with open(local_path, "rb") as f:
        content = f.read()

    try:
        existing_file = repo.get_contents(archive_path)
        repo.update_file(archive_path, f"Обновление {os.path.basename(archive_path)}", content, existing_file.sha)
        print(f"✅ Лог обновлён в GitHub: {archive_path}")
    except Exception:
        repo.create_file(archive_path, f"Архив логов {os.path.basename(archive_path)}", content)
        print(f"✅ Лог создан в GitHub: {archive_path}")

def setup_logging(config, log_level=logging.INFO):
    log_format = "%(asctime)s | %(levelname)-8s | %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"

    os.makedirs("logs", exist_ok=True)
    os.makedirs("logs_archive", exist_ok=True)
    today_log = "logs/bot.log"

    # 🔹 Проверяем, есть ли старый лог и пушим его при запуске
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    yesterday_log = f"logs/bot-{yesterday}.log"
    if os.path.exists(yesterday_log):
        archive_path = f"logs_archive/bot-{yesterday}.log"
        push_log_to_github(yesterday_log, archive_path, config)

    # 📦 Ротационный логгер на каждый день
    file_handler = TimedRotatingFileHandler(
        today_log, when="midnight", interval=1, backupCount=7, encoding="utf-8"
    )
    file_handler.suffix = "%Y-%m-%d.log"

    # Функция пуша при ротации
    def on_rollover(handler):
        rolled_log = handler.baseFilename.replace(".log", f"-{datetime.now().strftime('%Y-%m-%d')}.log")
        archive_path = f"logs_archive/{os.path.basename(rolled_log)}"
        push_log_to_github(rolled_log, archive_path, config)

    file_handler.rotator = lambda source, dest: on_rollover(file_handler)
    file_handler.setFormatter(logging.Formatter(log_format, datefmt=date_format))

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.handlers.clear()
    root_logger.addHandler(file_handler)

    # 🎨 Консольный лог с цветом
    console_handler = logging.StreamHandler(sys.stdout)
    try:
        console_handler.stream.reconfigure(encoding="utf-8")
    except AttributeError:
        pass
    console_handler.setFormatter(ColorFormatter(log_format, datefmt=date_format))
    root_logger.addHandler(console_handler)

    # 🪵 Discord-логгер
    discord_logger = logging.getLogger("discord")
    discord_logger.setLevel(log_level)
    discord_logger.propagate = False
    discord_logger.handlers.clear()
    discord_handler = logging.StreamHandler(sys.stdout)
    try:
        discord_handler.stream.reconfigure(encoding="utf-8")
    except AttributeError:
        pass
    discord_handler.setFormatter(CustomDiscordFormatter(log_format, datefmt=date_format))
    discord_logger.addHandler(discord_handler)

    # 🔥 Кастомный уровень SUCCESS
    logging.SUCCESS = 25
    logging.addLevelName(logging.SUCCESS, "SUCCESS")
    def success(self, message, *args, **kwargs):
        if self.isEnabledFor(logging.SUCCESS):
            self._log(logging.SUCCESS, message, args, **kwargs)
    logging.Logger.success = success

import logging
import sys
import os
from logging.handlers import RotatingFileHandler
from datetime import datetime
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

def setup_logging(config, log_level=logging.INFO):
    log_format = "%(asctime)s | %(levelname)-8s | %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"

    os.makedirs("logs", exist_ok=True)
    today_log = "logs/bot.log"

    # 🔹 Архивация и пуш в GitHub только если локальный файл существует
    if os.path.exists(today_log) and os.path.getsize(today_log) > 0:
        # Переименуем в формат с датой вчерашнего дня
        yesterday = datetime.now().strftime("%Y-%m-%d")
        archive_name = f"bot-{yesterday}.log"
        temp_path = f"logs/{archive_name}"
        os.rename(today_log, temp_path)

        # Пушим в GitHub
        try:
            token = config.get("GITHUB_TOKEN")
            repo_name = config.get("REPO_NAME")
            if token and repo_name:
                g = Github(token)
                repo = g.get_repo(repo_name)

                repo_path = f"logs_archive/{archive_name}"
                with open(temp_path, "rb") as f:
                    content = f.read()

                try:
                    existing_file = repo.get_contents(repo_path)
                    repo.update_file(repo_path, f"Обновление {archive_name}", content, existing_file.sha)
                except Exception:
                    repo.create_file(repo_path, f"Архив логов {archive_name}", content)

                print(f"✅ Локальный лог {archive_name} загружен в репозиторий {repo_name}")

        except Exception as e:
            print(f"⚠️ Ошибка при загрузке лога в GitHub: {e}")

        # 🧹 Удаляем локальный архив после пуша
        os.remove(temp_path)

    # 📦 Настройка ротационного логгера для текущего дня
    file_handler = RotatingFileHandler(today_log, maxBytes=5*1024*1024, backupCount=1, encoding="utf-8")
    file_formatter = logging.Formatter(log_format, datefmt=date_format)
    file_handler.setFormatter(file_formatter)

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

    # 🔥 Добавляем кастомный уровень SUCCESS
    logging.SUCCESS = 25
    logging.addLevelName(logging.SUCCESS, "SUCCESS")
    def success(self, message, *args, **kwargs):
        if self.isEnabledFor(logging.SUCCESS):
            self._log(logging.SUCCESS, message, args, **kwargs)
    logging.Logger.success = success

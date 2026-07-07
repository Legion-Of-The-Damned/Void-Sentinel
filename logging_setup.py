import logging
import sys
import os
import threading
import time

from datetime import datetime, timedelta
from github import Github, GithubException


class ColorFormatter(logging.Formatter):
    COLORS = {
        'DEBUG': '\033[90m',
        'INFO': '\033[94m',
        'WARNING': '\033[93m',
        'ERROR': '\033[91m',
        'CRITICAL': '\033[1;91m',
        'SUCCESS': '\033[92m',
        'LOG_PUSH': '\033[95m',
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
            record.msg = "🌐 Шард подключён к Gateway"
            record.args = ()

        elif "RESUMED session" in msg:
            record.msg = "🌟 Сессия восстановлена"
            record.args = ()

        return super().format(record)


LOG_PUSH = 35
logging.addLevelName(LOG_PUSH, "LOG_PUSH")


def log_push(self, message, *args, **kwargs):
    if self.isEnabledFor(LOG_PUSH):
        self._log(LOG_PUSH, message, args, **kwargs)


logging.Logger.log_push = log_push


github_logger = logging.getLogger("github_push")
github_logger.setLevel(LOG_PUSH)
github_logger.propagate = False

github_console = logging.StreamHandler(sys.stdout)
github_console.setFormatter(
    ColorFormatter("%(asctime)s | %(levelname)-8s | %(message)s")
)

github_logger.handlers.clear()
github_logger.addHandler(github_console)


def push_log_to_github(local_path, github_path, config):
    if not os.path.exists(local_path):
        github_logger.log_push(f"❌ Файл не найден: {local_path}")
        return False

    token = config.get("GITHUB_TOKEN")
    repo_name = config.get("REPO_NAME")

    if not token or not repo_name:
        github_logger.log_push("❌ Нет токена или репозитория")
        return False

    try:
        g = Github(token)
        repo = g.get_repo(repo_name)

        with open(local_path, "rb") as f:
            content = f.read()

        github_path = f"logs/{github_path}"

        try:
            existing = repo.get_contents(github_path)

            repo.update_file(
                github_path,
                "update log",
                content,
                existing.sha
            )

            github_logger.log_push(f"🔄 Обновлён: {github_path}")

        except GithubException as e:
            if e.status == 404:
                repo.create_file(
                    github_path,
                    "create log",
                    content
                )
                github_logger.log_push(f"🆕 Создан: {github_path}")
            else:
                raise

        return True

    except Exception as e:
        github_logger.log_push(f"❌ GitHub error: {e}")
        return False


def smart_rotate_and_push(log_dir, log_name, config):
    os.makedirs(log_dir, exist_ok=True)

    today = datetime.now().strftime("%Y-%m-%d")
    today_file = os.path.join(log_dir, f"{log_name}_{today}.log")

    # Отправляем все старые логи (кроме сегодняшнего) и удаляем их
    for file in os.listdir(log_dir):
        if not (file.startswith(log_name) and file.endswith(".log")):
            continue

        file_date = file.replace(f"{log_name}_", "").replace(".log", "")

        if file_date == today:
            continue

        old_path = os.path.join(log_dir, file)

        github_logger.log_push(f"📦 Пуш старого лога: {old_path}")

        success = push_log_to_github(old_path, file, config)

        if success:
            try:
                os.remove(old_path)
                github_logger.log_push(f"🗑 Удалён: {old_path}")
            except Exception as e:
                github_logger.log_push(f"❌ Не удалось удалить: {e}")

    # Создаём файл для сегодняшних логов, если его нет
    if not os.path.exists(today_file):
        open(today_file, "a", encoding="utf-8").close()

    return today_file


def schedule_midnight_push(config):
    last_run = None

    def worker():
        nonlocal last_run

        while True:
            now = datetime.now()
            today = now.date()

            # Если наступила полночь и мы ещё не отправляли сегодня
            if now.hour == 0 and now.minute == 0 and last_run != today:
                last_run = today

                # Отправляем лог за ВЧЕРАШНИЙ день
                yesterday = (now - timedelta(days=1)).strftime("%Y-%m-%d")
                log_path = os.path.join("logs", f"bot_{yesterday}.log")

                if os.path.exists(log_path):
                    github_logger.log_push(f"🌙 Ночной пуш (вчерашний лог): {log_path}")

                    success = push_log_to_github(
                        log_path,
                        f"bot_{yesterday}.log",
                        config
                    )

                    if success:
                        try:
                            os.remove(log_path)
                            github_logger.log_push(f"🗑 Удалён после пуша: {log_path}")
                        except Exception as e:
                            github_logger.log_push(f"❌ Не удалось удалить: {e}")
                else:
                    github_logger.log_push(f"⚠️ Вчерашний лог не найден: {log_path}")

                # Небольшая задержка, чтобы не сработать повторно в ту же секунду
                time.sleep(60)

            time.sleep(1)

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()


def setup_logging(config, log_level=logging.INFO):
    log_format = "%(asctime)s | %(levelname)-8s | %(message)s"

    os.makedirs("logs", exist_ok=True)

    log_path = smart_rotate_and_push("logs", "bot", config)

    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(log_level)
    root.propagate = False

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(logging.Formatter(log_format))
    root.addHandler(file_handler)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(ColorFormatter(log_format))
    root.addHandler(console_handler)

    discord_logger = logging.getLogger("discord")
    discord_logger.handlers.clear()
    discord_logger.setLevel(log_level)
    discord_logger.propagate = False

    discord_handler = logging.StreamHandler(sys.stdout)
    discord_handler.setFormatter(CustomDiscordFormatter(log_format))
    discord_logger.addHandler(discord_handler)

    logging.SUCCESS = 25
    logging.addLevelName(logging.SUCCESS, "SUCCESS")

    def success(self, message, *args, **kwargs):
        if self.isEnabledFor(logging.SUCCESS):
            self._log(logging.SUCCESS, message, args, **kwargs)

    logging.Logger.success = success

    schedule_midnight_push(config)

    return root
import logging
import sys
import os
from datetime import datetime
from github import Github

# ---------- Цветной форматтер для консоли ----------
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

# ---------- Специальный форматтер для Discord ----------
class CustomDiscordFormatter(logging.Formatter):
    def format(self, record):
        msg = record.getMessage()

        if "logging in using static token" in msg:
            record.msg = "🔑 Авторизация через токен выполнена"
            record.args = ()
        elif "has connected to Gateway" in msg:
            record.msg = "🌐 Шард успешно подключён к Gateway"
            record.args = ()
        elif "RESUMED session" in msg:
            record.msg = "🌟 Соединение восстановлено успешно!"
            record.args = ()

        return super().format(record)

# ---------- Кастомный уровень LOG_PUSH ----------
LOG_PUSH = 35
logging.addLevelName(LOG_PUSH, "LOG_PUSH")

def log_push(self, message, *args, **kwargs):
    if self.isEnabledFor(LOG_PUSH):
        self._log(LOG_PUSH, message, args, **kwargs)

logging.Logger.log_push = log_push

# ---------- Логгер для GitHub ----------
github_logger = logging.getLogger("github_push")
github_logger.setLevel(LOG_PUSH)
github_logger.propagate = False
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(
    ColorFormatter("%(asctime)s | %(levelname)-8s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
)
github_logger.addHandler(console_handler)

# ---------- Flush всех хендлеров ----------
def flush_all_loggers():
    for handler in logging.getLogger().handlers:
        try:
            handler.flush()
        except Exception:
            pass

# ---------- Пуш логов на GitHub ----------
def push_log_to_github(local_path, github_path, config):
    flush_all_loggers()  # Важно!

    if not os.path.exists(local_path):
        github_logger.log_push(f"❌ Файл не найден: {local_path}")
        return

    token = config.get("GITHUB_TOKEN")
    repo_name = config.get("REPO_NAME")
    if not token or not repo_name:
        github_logger.log_push("❌ Нет токена или имени репозитория в конфиге")
        return

    try:
        g = Github(token)
        repo = g.get_repo(repo_name)

        with open(local_path, "r", encoding="utf-8") as f:
            content = f.read()

        github_path = f"logs/{github_path}"

        try:
            existing_file = repo.get_contents(github_path)
            repo.update_file(
                github_path,
                f"Обновление {os.path.basename(github_path)}",
                content,
                existing_file.sha
            )
            github_logger.log_push(f"✅ Лог обновлён в GitHub: {github_path}")
        except Exception:
            repo.create_file(
                github_path,
                f"Архив логов {os.path.basename(github_path)}",
                content
            )
            github_logger.log_push(f"✅ Лог создан в GitHub: {github_path}")
    except Exception as e:
        github_logger.log_push(f"❌ Ошибка при пуше в GitHub: {e}")

# ---------- Ротация логов и подготовка текущего ----------
def smart_rotate_and_push(log_dir, log_name, config):
    os.makedirs(log_dir, exist_ok=True)
    today_str = datetime.now().strftime("%Y-%m-%d")
    today_log = os.path.join(log_dir, f"{log_name}_{today_str}.log")

    # Пушим старые логи
    for file in os.listdir(log_dir):
        if file.startswith(log_name) and file.endswith(".log") and today_str not in file:
            old_log = os.path.join(log_dir, file)

            # Пропускаем пустые логи
            if os.path.getsize(old_log) == 0:
                github_logger.log_push(f"⚠️ Пропуск пустого лога: {old_log}")
                os.remove(old_log)
                continue

            github_logger.log_push(f"Ротация: пушим старый лог {old_log}")
            push_log_to_github(old_log, file, config)
            os.remove(old_log)
            github_logger.log_push(f"Удалён локально после пуша: {old_log}")

    # Создаём текущий лог, если ещё нет
    if not os.path.exists(today_log):
        open(today_log, 'a', encoding='utf-8').close()

    return today_log

# ---------- Настройка логгера ----------
def setup_logging(config, log_level=logging.INFO):
    log_format = "%(asctime)s | %(levelname)-8s | %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"

    # Получаем путь к сегодняшнему логу и пушим старые
    log_path = smart_rotate_and_push("logs", "bot", config)

    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.handlers.clear()

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(logging.Formatter(log_format, datefmt=date_format))
    root_logger.addHandler(file_handler)

    console_handler_root = logging.StreamHandler(sys.stdout)
    try:
        console_handler_root.stream.reconfigure(encoding="utf-8")
    except AttributeError:
        pass
    console_handler_root.setFormatter(ColorFormatter(log_format, datefmt=date_format))
    root_logger.addHandler(console_handler_root)

    # Discord-логгер
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

    # Кастомный уровень SUCCESS
    logging.SUCCESS = 25
    logging.addLevelName(logging.SUCCESS, "SUCCESS")

    def success(self, message, *args, **kwargs):
        if self.isEnabledFor(logging.SUCCESS):
            self._log(logging.SUCCESS, message, args, **kwargs)
    logging.Logger.success = success

    return root_logger

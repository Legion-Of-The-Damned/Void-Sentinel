import logging
import sys
from logging.handlers import RotatingFileHandler

class ColorFormatter(logging.Formatter):
    COLORS = {
        'DEBUG': '\033[90m',     # Серый
        'INFO': '\033[94m',      # Синий
        'WARNING': '\033[93m',   # Жёлтый
        'ERROR': '\033[91m',     # Красный
        'CRITICAL': '\033[1;91m',# Жирный красный
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

def setup_logging(log_level=logging.INFO):
    log_format = "%(asctime)s | %(levelname)-8s | %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"

    # 📦 Ротация логов: 5 МБ на файл, до 3 архивов
    file_handler = RotatingFileHandler(
        "bot.log", maxBytes=5 * 1024 * 1024, backupCount=3, encoding='utf-8'
    )
    file_formatter = logging.Formatter(log_format, datefmt=date_format)
    file_handler.setFormatter(file_formatter)

    # 🌲 Корневой логгер
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.handlers.clear()

    # ➕ Добавляем файловый логгер
    root_logger.addHandler(file_handler)

    # 🎨 Консольный логгер с цветом
    console_handler = logging.StreamHandler(sys.stdout)
    try:
        console_handler.stream.reconfigure(encoding='utf-8')
    except AttributeError:
        pass
    console_handler.setFormatter(ColorFormatter(log_format, datefmt=date_format))
    root_logger.addHandler(console_handler)

    # 🪵 Специальный логгер для Discord
    discord_logger = logging.getLogger("discord")
    discord_logger.setLevel(log_level)
    discord_logger.propagate = False
    discord_logger.handlers.clear()

    discord_handler = logging.StreamHandler(sys.stdout)
    try:
        discord_handler.stream.reconfigure(encoding='utf-8')
    except AttributeError:
        pass
    discord_handler.setFormatter(CustomDiscordFormatter(log_format, datefmt=date_format))
    discord_logger.addHandler(discord_handler)

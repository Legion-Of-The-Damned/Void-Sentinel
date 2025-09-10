import logging
import sys
import os
from logging.handlers import TimedRotatingFileHandler

# === ⚔️ Кастомный уровень SUCCESS ===
SUCCESS = 25
logging.addLevelName(SUCCESS, "SUCCESS")

def success(self, message, *args, **kwargs):
    self.log(SUCCESS, message, *args, **kwargs)

logging.Logger.success = success

# === ⚔️ Сообщения Discord ===
DISCORD_MESSAGES = {
    "logging in using static token": "🔑 ⚔️ Священный ключ крепости активирован",
    "has connected to gateway": "🌌 ⚔️ Брат подключился к варп-шлюзу",
    "disconnect": "💀 ⚔️ Варп пожрал соединение",
}

def transform_discord_message(msg: str) -> str:
    msg_l = msg.lower()
    for k, v in DISCORD_MESSAGES.items():
        if k in msg_l:
            return v
    return msg

# === ⚔️ Форматтер для консоли ===
class LegionFormatter(logging.Formatter):
    COLORS = {
        'DEBUG': '\033[90m',        # серый
        'INFO': '\033[96m',         # бирюзовый
        'WARNING': '\033[93m',      # жёлтый
        'ERROR': '\033[91m',        # красный
        'CRITICAL': '\033[1;91m',   # жирный красный
        'SUCCESS': '\033[92m',      # зелёный
        'RESET': '\033[0m',         # сброс
    }

    SYMBOLS = {
        'DEBUG': '👁️',
        'INFO': '📖',
        'WARNING': '⚠️',
        'ERROR': '🔥',
        'CRITICAL': '💀',
        'SUCCESS': '✠',
    }

    def format(self, record):
        record.msg = transform_discord_message(record.getMessage())
        record.args = ()
        color = self.COLORS.get(record.levelname, self.COLORS['RESET'])
        symbol = self.SYMBOLS.get(record.levelname, '✠')
        reset = self.COLORS['RESET']
        base_message = super().format(record)
        return f"{color}{symbol} {base_message}{reset}"

# === ⚔️ Форматтер для файлов (без цветов, с ограничением длины) ===
class LimitedLengthFormatter(logging.Formatter):
    MAX_LEN = 150
    def format(self, record):
        record.msg = transform_discord_message(record.getMessage())
        record.args = ()
        s = super().format(record)
        if len(s) > self.MAX_LEN:
            s = s[:self.MAX_LEN-3] + "..."
        return s

# === ⚔️ Фильтр для трансформации сообщений Discord ===
class DiscordTransformFilter(logging.Filter):
    def filter(self, record):
        record.msg = transform_discord_message(record.getMessage())
        return True

# === ⚔️ Вспомогательные функции ===
def make_stream_handler(formatter: logging.Formatter, level: int = logging.INFO) -> logging.StreamHandler:
    handler = logging.StreamHandler(sys.stdout)
    try:
        handler.stream.reconfigure(encoding='utf-8')
    except AttributeError:
        pass
    handler.setFormatter(formatter)
    handler.setLevel(level)
    return handler

def make_timed_file_handler(filename: str, formatter: logging.Formatter, backup_count: int = 7) -> TimedRotatingFileHandler:
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    handler = TimedRotatingFileHandler(
        filename,
        when="midnight",
        interval=1,
        backupCount=backup_count,
        encoding="utf-8"
    )
    handler.setFormatter(formatter)
    return handler

# === ⚔️ Настройка логирования ===
def setup_logging(log_level=logging.INFO, backup_count=7):
    LOG_FORMAT = "%(asctime)s | %(levelname)-8s | [%(name)s] | %(message)s"
    DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

    discord_filter = DiscordTransformFilter()

    # === Root logger ===
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(log_level)

    root_logger.addHandler(make_timed_file_handler("logs/logging.log", LimitedLengthFormatter(LOG_FORMAT, datefmt=DATE_FORMAT), backup_count))
    root_logger.addHandler(make_stream_handler(LegionFormatter(LOG_FORMAT, datefmt=DATE_FORMAT), log_level))
    root_logger.addFilter(discord_filter)

    # Заголовок новой сессии
    root_logger.info("="*80)
    root_logger.info("✠ Звёздная крепость Рапторус Рекс пробуждается из варпа... ✠")
    root_logger.info("="*80)

    # === Discord logger ===
    discord_logger = logging.getLogger("discord")
    discord_logger.handlers.clear()
    discord_logger.setLevel(log_level)
    discord_logger.propagate = False
    discord_logger.addHandler(make_stream_handler(LegionFormatter(LOG_FORMAT, datefmt=DATE_FORMAT), log_level))
    discord_logger.addFilter(discord_filter)

    # === Duel logger ===
    duel_logger = logging.getLogger("duel")
    duel_logger.handlers.clear()
    duel_logger.setLevel(logging.INFO)
    duel_logger.propagate = False
    duel_logger.addHandler(make_timed_file_handler(
        "logs/duels.log",
        LimitedLengthFormatter("%(asctime)s | [DUEL] ⚔️ | %(levelname)-8s | %(message)s", datefmt=DATE_FORMAT),
        backup_count
    ))
    duel_logger.addFilter(discord_filter)

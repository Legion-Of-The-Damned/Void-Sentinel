import logging
import sys

def setup_logging(log_level=logging.INFO, log_to_console=True):
    # Настраиваем обработчики
    handlers = [logging.FileHandler('bot.log', mode='a', encoding='utf-8')]

    if log_to_console:
        # Используем поток sys.stdout с кодировкой UTF-8
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.stream.reconfigure(encoding='utf-8')  # Обеспечиваем поддержку Unicode
        handlers.append(console_handler)

    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=handlers
    )

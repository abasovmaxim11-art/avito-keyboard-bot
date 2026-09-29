import sys
import logging
from bot import build_application
from config import BOT_TOKEN

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("main")

def main():
    if not BOT_TOKEN:
        logger.error("❌ ОШИБКА: BOT_TOKEN не найден! Пожалуйста, укажите BOT_TOKEN в файле .env")
        sys.exit(1)

    logger.info("🚀 Запуск Avito Keyboard Monitor Bot...")
    app = build_application()
    app.run_polling()

if __name__ == "__main__":
    main()

import os
from dotenv import load_dotenv

# Загружаем переменные из .env файла если существует
load_dotenv()

# Токен вашего Telegram бота от @BotFather
BOT_TOKEN = os.getenv('BOT_TOKEN', '')

# Настройки поиска по умолчанию (Мониторинг клавиатур по всей России)
DEFAULT_QUERY = os.getenv('DEFAULT_QUERY', 'клавиатура')
DEFAULT_LOCATION = os.getenv('DEFAULT_LOCATION', 'rossiya')

# Интервал проверки новых объявлений (в секундах). Рекомендуется от 120 до 300 сек.
CHECK_INTERVAL = int(os.getenv('CHECK_INTERVAL', '180'))

# Опциональные ключи официального Avito API (для бизнес-пользователей)
AVITO_CLIENT_ID = os.getenv('AVITO_CLIENT_ID', '')
AVITO_CLIENT_SECRET = os.getenv('AVITO_CLIENT_SECRET', '')

# Опциональный прокси для веб-скрапинга (например: http://user:pass@ip:port)
PROXY_URL = os.getenv('PROXY_URL', '')

# Настройки базы данных
DB_PATH = os.getenv('DB_PATH', 'bot_data.db')

# Максимальное число результатов при разовом поиске / уведомлении
MAX_RESULTS_PER_CHECK = int(os.getenv('MAX_RESULTS_PER_CHECK', '10'))

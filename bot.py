import logging
import html
import asyncio
from typing import Dict, List
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.request import HTTPXRequest
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes
)

from config import BOT_TOKEN, CHECK_INTERVAL, DEFAULT_QUERY, DEFAULT_LOCATION, MAX_RESULTS_PER_CHECK, PROXY_URL
from database import Database
from avito_parser import AvitoParser

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Инициализация базы данных и парсера
db = Database()
parser = AvitoParser()

def escape_text(text: str) -> str:
    """Экранирование спецсимволов для HTML формата Telegram"""
    return html.escape(str(text or ''))

def format_item_message(item: Dict) -> tuple[str, InlineKeyboardMarkup]:
    """Форматирование сообщения о новом объявлении с кнопкой прямого перехода"""
    title = escape_text(item.get('title', 'Объявление без названия'))
    price = item.get('price', 0)
    location = escape_text(item.get('location', 'Россия'))
    item_url = item.get('url', 'https://www.avito.ru')
    
    price_str = f"{price:,.0f} ₽".replace(",", " ") if price > 0 else "Цена не указана"

    message_text = (
        f"⌨️ <b>Новое объявление на Авито!</b>\n\n"
        f"📌 <b><a href='{item_url}'>{title}</a></b>\n"
        f"💰 <b>Цена:</b> {price_str}\n"
        f"📍 <b>Локация:</b> {location}\n\n"
        f"🔗 <i>Нажмите на ссылку выше или на кнопку ниже, чтобы открыть объявление.</i>"
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("👉 Открыть объявление на Авито", url=item_url)]
    ])

    return message_text, keyboard

class AvitoMonitorBot:
    def __init__(self):
        pass

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Приветственное сообщение /start"""
        chat_id = update.effective_chat.id
        db.add_subscriber(chat_id, query=DEFAULT_QUERY)

        welcome_text = (
            f"👋 <b>Привет! Я бот-монитор Avito по клавиатурам во всей России.</b>\n\n"
            f"🟢 <b>Мониторинг автоматически ВКЛЮЧЕН!</b>\n"
            f"По умолчанию отслеживаем: <code>{DEFAULT_QUERY}</code> по всей России.\n\n"
            f"📋 <b>Доступные команды:</b>\n"
            f"• /search <code>[запрос]</code> — Найти объявления прямо сейчас\n"
            f"• /filter <code>[мин_цена] [макс_цена]</code> — Установить диапазон цен (например: <code>/filter 1000 5000</code>)\n"
            f"• /query <code>[новый запрос]</code> — Изменить поисковый запрос (например: <code>/query механика logitech</code>)\n"
            f"• /status — Статус мониторинга и статистика\n"
            f"• /stop — Приостановить уведомления\n"
            f"• /help — Инструкции по использованию"
        )
        await update.message.reply_text(welcome_text, parse_mode=ParseMode.HTML)

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Справка /help"""
        help_text = (
            f"📖 <b>Инструкция по использованию Avito Parser Bot:</b>\n\n"
            f"1. <b>Автоматический мониторинг:</b>\n"
            f"Бот каждые {CHECK_INTERVAL // 60} мин. проверяет Avito во всей России и мгновенно присылает новые объявления со ссылками.\n\n"
            f"2. <b>Фильтры:</b>\n"
            f"• <code>/filter 2000 10000</code> — получать только клавиатуры от 2 000 до 10 000 руб.\n"
            f"• <code>/filter 0 0</code> — сбросить фильтр цен.\n\n"
            f"3. <b>Ручной поиск:</b>\n"
            f"• Напишите <code>/search Varmilo</code> или <code>/search кастомная клавиатура</code>, чтобы посмотреть последние предложения прямо сейчас."
        )
        await update.message.reply_text(help_text, parse_mode=ParseMode.HTML)

    async def search_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Ручной поиск объявлений /search [запрос]"""
        args = context.args
        search_query = " ".join(args) if args else DEFAULT_QUERY

        await update.message.reply_text(
            f"🔍 Ищу объявления по запросу: <b>{escape_text(search_query)}</b> по всей России...",
            parse_mode=ParseMode.HTML
        )

        items = await parser.get_latest_keyboard_items(query=search_query, location=DEFAULT_LOCATION)
        if not items:
            await update.message.reply_text("😔 По вашему запросу ничего не найдено или Avito временно ограничил доступ.")
            return

        # Показываем первые 5 результатов
        for item in items[:5]:
            msg_text, reply_markup = format_item_message(item)
            await update.message.reply_text(msg_text, parse_mode=ParseMode.HTML, reply_markup=reply_markup)

    async def filter_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Настройка фильтра цен /filter min max"""
        chat_id = update.effective_chat.id
        args = context.args

        if len(args) < 2 or not (args[0].isdigit() and args[1].isdigit()):
            await update.message.reply_text(
                "⚠️ Используйте формат: <code>/filter [мин_цена] [макс_цена]</code>\n"
                "Пример: <code>/filter 1000 5000</code>\n"
                "Сбросить: <code>/filter 0 0</code>",
                parse_mode=ParseMode.HTML
            )
            return

        min_price = int(args[0])
        max_price = int(args[1])
        db.update_subscriber_settings(chat_id, min_price=min_price, max_price=max_price)

        await update.message.reply_text(
            f"✅ Фильтр цен обновлен!\n"
            f"Диапазон: от <b>{min_price:,} ₽</b> до <b>{max_price:,} ₽</b>",
            parse_mode=ParseMode.HTML
        )

    async def query_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Изменить ключевое слово поиска /query [запрос]"""
        chat_id = update.effective_chat.id
        args = context.args

        if not args:
            await update.message.reply_text("⚠️ Укажите запрос, например: <code>/query механическая клавиатура</code>", parse_mode=ParseMode.HTML)
            return

        new_query = " ".join(args)
        db.update_subscriber_settings(chat_id, query=new_query)
        await update.message.reply_text(
            f"✅ Поисковый запрос обновлен на: <b>{escape_text(new_query)}</b>",
            parse_mode=ParseMode.HTML
        )

    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Просмотр статуса /status"""
        chat_id = update.effective_chat.id
        stats = db.get_stats()
        subs = db.get_active_subscribers()
        user_sub = next((s for s in subs if s['chat_id'] == chat_id), None)

        status_str = "🟢 АКТИВЕН" if user_sub else "🔴 ОСТАНОВЛЕН"
        query_val = user_sub['query'] if user_sub else DEFAULT_QUERY
        min_p = user_sub['min_price'] if user_sub else 0
        max_p = user_sub['max_price'] if user_sub else 0

        status_text = (
            f"📊 <b>Статус вашего мониторинга:</b> {status_str}\n\n"
            f"🔍 <b>Текущий запрос:</b> <code>{escape_text(query_val)}</code>\n"
            f"📍 <b>Регион:</b> Вся Россия\n"
            f"💰 <b>Фильтр цен:</b> {min_p} ₽ - {max_p} ₽\n"
            f"⏱ <b>Частота проверки:</b> каждые {CHECK_INTERVAL // 60} мин.\n\n"
            f"📈 <b>Общая статистика бота:</b>\n"
            f"• Активных подписчиков: {stats['active_subscribers']}\n"
            f"• Обработано объявлений: {stats['total_seen_items']}"
        )
        await update.message.reply_text(status_text, parse_mode=ParseMode.HTML)

    async def stop_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Приостановка мониторинга /stop"""
        chat_id = update.effective_chat.id
        db.remove_subscriber(chat_id)
        await update.message.reply_text("🔴 Мониторинг приостановлен. Чтобы возобновить, нажмите /start.")

    async def check_new_listings_job(self, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Периодическая фоновая задача проверки новых объявлений"""
        subscribers = db.get_active_subscribers()
        if not subscribers:
            return

        logger.info(f"Запуск периодической проверки Avito для {len(subscribers)} подписчиков...")

        search_groups: Dict[tuple, List[int]] = {}
        for sub in subscribers:
            key = (sub.get('query', DEFAULT_QUERY), sub.get('min_price', 0), sub.get('max_price', 0))
            if key not in search_groups:
                search_groups[key] = []
            search_groups[key].append(sub['chat_id'])

        for (query, min_price, max_price), chat_ids in search_groups.items():
            try:
                items = await parser.get_latest_keyboard_items(
                    query=query,
                    location=DEFAULT_LOCATION,
                    min_price=min_price,
                    max_price=max_price
                )

                if not items:
                    continue

                new_items_to_send = []
                for item in items:
                    item_id = item['id']
                    if not db.is_item_seen(item_id):
                        db.add_seen_item(item_id, item.get('title', ''), item.get('price', 0), item.get('url', ''))
                        new_items_to_send.append(item)

                if new_items_to_send:
                    logger.info(f"Найдено {len(new_items_to_send)} новых объявлений по запросу '{query}'. Рассылка...")
                    for item in new_items_to_send[:MAX_RESULTS_PER_CHECK]:
                        msg_text, reply_markup = format_item_message(item)
                        for cid in chat_ids:
                            try:
                                await context.bot.send_message(
                                    chat_id=cid,
                                    text=msg_text,
                                    parse_mode=ParseMode.HTML,
                                    reply_markup=reply_markup
                                )
                                await asyncio.sleep(0.3)
                            except Exception as send_err:
                                logger.error(f"Ошибка отправки пользователю {cid}: {send_err}")
            except Exception as e:
                logger.error(f"Ошибка при фоновой проверке по запросу '{query}': {e}")

def build_application() -> Application:
    """Сборка приложения Telegram бота с увеличенными таймаутами и поддержкой прокси"""
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN не установлен в файле .env или окружении!")

    request_kwargs = {
        "connect_timeout": 30.0,
        "read_timeout": 30.0,
        "write_timeout": 30.0
    }
    if PROXY_URL:
        request_kwargs["proxy_url"] = PROXY_URL

    request = HTTPXRequest(**request_kwargs)
    bot_instance = AvitoMonitorBot()
    app = Application.builder().token(BOT_TOKEN).request(request).build()

    # Регистрация хэндлеров команд
    app.add_handler(CommandHandler("start", bot_instance.start))
    app.add_handler(CommandHandler("help", bot_instance.help_command))
    app.add_handler(CommandHandler("search", bot_instance.search_command))
    app.add_handler(CommandHandler("filter", bot_instance.filter_command))
    app.add_handler(CommandHandler("query", bot_instance.query_command))
    app.add_handler(CommandHandler("status", bot_instance.status_command))
    app.add_handler(CommandHandler("stop", bot_instance.stop_command))

    # Регистрация фонового джоба мониторинга
    job_queue = app.job_queue
    if job_queue:
        job_queue.run_repeating(
            bot_instance.check_new_listings_job,
            interval=CHECK_INTERVAL,
            first=10
        )

    return app

if __name__ == "__main__":
    logger.info("Запуск Telegram-бота Avito Monitor Keyboard Parser...")
    application = build_application()
    application.run_polling(allowed_updates=Update.ALL_TYPES)

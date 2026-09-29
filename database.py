import sqlite3
import os
import logging
from typing import List, Dict, Optional, Set

logger = logging.getLogger(__name__)

class Database:
    def __init__(self, db_path: str = "bot_data.db"):
        self.db_path = db_path
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        """Инициализация таблиц БД"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # Таблица подписчиков/чатов
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS subscribers (
                    chat_id INTEGER PRIMARY KEY,
                    query TEXT DEFAULT 'клавиатура',
                    min_price INTEGER DEFAULT 0,
                    max_price INTEGER DEFAULT 0,
                    is_active INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            # Таблица просмотренных объявлений для предотвращения дублей
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS seen_items (
                    item_id TEXT PRIMARY KEY,
                    title TEXT,
                    price REAL,
                    url TEXT,
                    first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()
            logger.info("База данных инициализирована.")

    # Методы для работы с подписчиками
    def add_subscriber(self, chat_id: int, query: str = "клавиатура", min_price: int = 0, max_price: int = 0) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO subscribers (chat_id, query, min_price, max_price, is_active)
                VALUES (?, ?, ?, ?, 1)
                ON CONFLICT(chat_id) DO UPDATE SET
                    query = excluded.query,
                    min_price = excluded.min_price,
                    max_price = excluded.max_price,
                    is_active = 1
            """, (chat_id, query, min_price, max_price))
            conn.commit()

    def remove_subscriber(self, chat_id: int) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE subscribers SET is_active = 0 WHERE chat_id = ?", (chat_id,))
            conn.commit()

    def get_active_subscribers(self) -> List[Dict]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM subscribers WHERE is_active = 1")
            return [dict(row) for row in cursor.fetchall()]

    def update_subscriber_settings(self, chat_id: int, **kwargs) -> None:
        valid_fields = {'query', 'min_price', 'max_price', 'is_active'}
        updates = []
        params = []
        for key, value in kwargs.items():
            if key in valid_fields:
                updates.append(f"{key} = ?")
                params.append(value)
        if not updates:
            return
        params.append(chat_id)
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"UPDATE subscribers SET {', '.join(updates)} WHERE chat_id = ?", params)
            conn.commit()

    # Методы для работы с объявлениями
    def is_item_seen(self, item_id: str) -> bool:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM seen_items WHERE item_id = ?", (str(item_id),))
            return cursor.fetchone() is not None

    def add_seen_item(self, item_id: str, title: str = "", price: float = 0.0, url: str = "") -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR IGNORE INTO seen_items (item_id, title, price, url)
                VALUES (?, ?, ?, ?)
            """, (str(item_id), title, price, url))
            conn.commit()

    def add_seen_items_batch(self, items: List[Dict]) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.executemany("""
                INSERT OR IGNORE INTO seen_items (item_id, title, price, url)
                VALUES (?, ?, ?, ?)
            """, [(str(item['id']), item.get('title', ''), float(item.get('price', 0)), item.get('url', '')) for item in items])
            conn.commit()

    def get_stats(self) -> Dict:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM subscribers WHERE is_active = 1")
            active_subs = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM seen_items")
            total_seen = cursor.fetchone()[0]
            return {
                "active_subscribers": active_subs,
                "total_seen_items": total_seen
            }

import logging
import asyncio
import re
import json
import urllib.parse
from typing import List, Dict, Optional, Any
from bs4 import BeautifulSoup
import aiohttp

try:
    from curl_cffi.requests import AsyncSession
    CURL_CFFI_AVAILABLE = True
except ImportError:
    CURL_CFFI_AVAILABLE = False

from config import AVITO_CLIENT_ID, AVITO_CLIENT_SECRET, PROXY_URL

logger = logging.getLogger(__name__)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1",
]

class AvitoParser:
    def __init__(self):
        self.client_id = AVITO_CLIENT_ID
        self.client_secret = AVITO_CLIENT_SECRET
        self.access_token: Optional[str] = None
        self.proxy = PROXY_URL if PROXY_URL else None

    async def get_official_token(self) -> Optional[str]:
        """Получение OAuth токена для официального Avito API"""
        if not self.client_id or not self.client_secret:
            return None
        
        url = "https://api.avito.ru/token"
        data = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, data=data, timeout=10) as resp:
                    if resp.status == 200:
                        res = await resp.json()
                        self.access_token = res.get("access_token")
                        return self.access_token
                    else:
                        logger.warning(f"Avito Official API Token Error: status {resp.status}")
        except Exception as e:
            logger.error(f"Error fetching official Avito token: {e}")
        return None

    async def fetch_official_api(self, query: str, min_price: int = 0, max_price: int = 0) -> List[Dict]:
        """Поиск через официальный API Avito (если указаны ключи)"""
        if not self.access_token:
            await self.get_official_token()
        if not self.access_token:
            return []

        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
        url = "https://api.avito.ru/core/v1/items"
        params = {
            "query": query,
            "sort": "date",
            "limit": 30
        }
        if min_price > 0:
            params["price_from"] = min_price
        if max_price > 0:
            params["price_to"] = max_price

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, params=params, timeout=10) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        items = []
                        for raw in data.get("items", []):
                            item_id = str(raw.get("id"))
                            url_str = raw.get("url") or f"https://www.avito.ru/i{item_id}"
                            items.append({
                                "id": item_id,
                                "title": raw.get("title", "Без названия"),
                                "price": float(raw.get("price", 0)),
                                "location": raw.get("location", {}).get("name", "Россия"),
                                "url": url_str,
                                "image": raw.get("images", [{}])[0].get("url", "")
                            })
                        return items
        except Exception as e:
            logger.error(f"Error fetching official API items: {e}")
        return []

    async def fetch_web_scraping(self, query: str = "клавиатура", location: str = "rossiya", min_price: int = 0, max_price: int = 0) -> List[Dict]:
        """Парсинг публичной выдачи Avito по всей России (сортировка по дате)"""
        encoded_query = urllib.parse.quote(query)
        # s=104 означает сортировку "По дате" (самые новые объявленя первыми)
        search_url = f"https://www.avito.ru/{location}?q={encoded_query}&s=104"
        if min_price > 0:
            search_url += f"&pmin={min_price}"
        if max_price > 0:
            search_url += f"&pmax={max_price}"

        html_content = ""

        # Приоритет 1: curl_cffi с обходом TLS-fingerprint (TLS Client Impersonation)
        if CURL_CFFI_AVAILABLE:
            try:
                async with AsyncSession(impersonate="chrome120") as s:
                    headers = {
                        "User-Agent": USER_AGENTS[0],
                        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                        "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
                    }
                    resp = await s.get(search_url, headers=headers, proxy=self.proxy, timeout=12)
                    if resp.status_code == 200:
                        html_content = resp.text
                    else:
                        logger.warning(f"curl_cffi fetch returned status {resp.status_code}")
            except Exception as e:
                logger.warning(f"curl_cffi error: {e}")

        # Приоритет 2: обычный aiohttp
        if not html_content:
            try:
                headers = {
                    "User-Agent": USER_AGENTS[1],
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "ru-RU,ru;q=0.9",
                }
                async with aiohttp.ClientSession() as session:
                    async with session.get(search_url, headers=headers, proxy=self.proxy, timeout=12) as resp:
                        if resp.status == 200:
                            html_content = await resp.text()
            except Exception as e:
                logger.error(f"aiohttp fetch error: {e}")

        if not html_content:
            return []

        return self._parse_html(html_content)

    def _parse_html(self, html: str) -> List[Dict]:
        """Извлечение объявлений из HTML кода страницы Avito"""
        items = []
        soup = BeautifulSoup(html, "html.parser")

        # Способ 1: Парсинг JSON-LD структурированных данных Schema.org (самый точный способ)
        scripts = soup.find_all("script", type="application/ld+json")
        for s in scripts:
            try:
                data = json.loads(s.string)
                if isinstance(data, dict) and data.get("@type") == "ItemList":
                    for element in data.get("itemListElement", []):
                        it = element.get("item", {})
                        raw_url = it.get("url", "")
                        if raw_url:
                            item_id = self._extract_id_from_url(raw_url)
                            price = float(it.get("offers", {}).get("price", 0))
                            title = it.get("name", "Без названия")
                            location = it.get("offers", {}).get("availableAtOrFrom", {}).get("name", "Россия")
                            image = it.get("image", "")

                            full_url = raw_url if raw_url.startswith("http") else f"https://www.avito.ru{raw_url}"
                            items.append({
                                "id": item_id,
                                "title": title,
                                "price": price,
                                "location": location,
                                "url": full_url,
                                "image": image
                            })
            except Exception as e:
                logger.debug(f"JSON-LD parse skip: {e}")

        if items:
            return items

        # Способ 2: Парсинг DOM-элементов страницы (fallback)
        item_blocks = soup.find_all("div", {"data-marker": "item"}) or soup.find_all("article")
        for block in item_blocks:
            try:
                link_el = block.find("a", {"data-marker": "item-title"}) or block.find("a", href=re.compile(r'/[^/]+/[^/]+_[0-9]+'))
                if not link_el or not link_el.has_attr("href"):
                    continue

                href = link_el["href"]
                full_url = href if href.startswith("http") else f"https://www.avito.ru{href}"
                item_id = self._extract_id_from_url(full_url)

                title_el = block.find("h3", {"itemprop": "name"}) or link_el
                title = title_el.text.strip() if title_el else "Объявление"

                price_el = block.find("meta", {"itemprop": "price"}) or block.find("span", {"data-marker": "item-price"})
                price_val = 0.0
                if price_el:
                    price_str = price_el.get("content") or price_el.text.strip()
                    price_digits = re.sub(r'[^\d]', '', price_str)
                    if price_digits:
                        price_val = float(price_digits)

                geo_el = block.find("div", {"data-marker": "item-line/geo"}) or block.find("div", class_=re.compile(r'geo|location|address', re.I))
                location = geo_el.text.strip() if geo_el else "Россия"

                img_el = block.find("img")
                image_url = img_el.get("src", "") if img_el else ""

                items.append({
                    "id": item_id,
                    "title": title,
                    "price": price_val,
                    "location": location,
                    "url": full_url,
                    "image": image_url
                })
            except Exception as e:
                logger.debug(f"DOM item parse error: {e}")

        return items

    def _extract_id_from_url(self, url: str) -> str:
        """Извлекает уникальный ID объявления из ссылки Avito"""
        match = re.search(r'_(\d+)$', url.split('?')[0])
        if match:
            return match.group(1)
        match_id = re.search(r'/i(\d+)', url)
        if match_id:
            return match_id.group(1)
        # Если ID не найден обычным способом, берем хэш от URL
        return str(hash(url) & 0xffffffff)

    async def get_latest_keyboard_items(self, query: str = "клавиатура", location: str = "rossiya", min_price: int = 0, max_price: int = 0) -> List[Dict]:
        """Универсальная функция получения свежих объявлений"""
        # Попытка 1: Через официальный API (если настроен)
        items = await self.fetch_official_api(query, min_price, max_price)
        if items:
            return items

        # Попытка 2: Веб-скрапинг
        return await self.fetch_web_scraping(query, location, min_price, max_price)

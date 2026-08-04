import os
import asyncio
import logging
import json
import aiohttp
from datetime import datetime
from telegram import Bot
from telegram.error import TelegramError

# --- КОНФИГУРАЦИЯ (ВАШИ ДАННЫЕ) ---
TELEGRAM_TOKEN = "8850394642:AAHvMzqaXy3BA9DGy3C6saYCNZLA09CAuzc"
CHAT_ID = "8078921787"
MIN_YEAR = 2000
PRICE_THRESHOLD = 0.85  # 15% ниже рынка
CHECK_INTERVAL = 180  # 3 минуты

# Стоп-слова для фильтрации
EXCLUDED_WORDS = [
    'запчасть', 'двигатель', 'коробка', 'шина', 'диск', 'экскаватор', 
    'трактор', 'бульдозер', 'кран', 'газель', 'автозапчасти', 'ремонт',
    'разборка', 'масло', 'фильтр', 'тормоз', 'амортизатор', 'генератор',
    'стартер', 'сцепление', 'бампер', 'фара', 'стекло', 'зеркало'
]

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class LalafoBot:
    def __init__(self):
        self.bot = Bot(token=TELEGRAM_TOKEN)
        self.session = None
        self.seen_ads = set()
        self.last_check = None
        
    async def get_session(self):
        """Получение сессии aiohttp"""
        if not self.session:
            self.session = aiohttp.ClientSession()
        return self.session

    async def get_ads(self):
        """Получение объявлений с Lalafo"""
        session = await self.get_session()
        
        # Прямые запросы к API Lalafo
        urls = [
            "https://lalafo.kg/api/search?category_id=5830&city_id=1&sort_by=created_at&sort_order=desc&per-page=30&year[from]=2000",
            "https://lalafo.kg/api/search?category_id=5830&city_id=1&sort_by=price&sort_order=asc&per-page=20&year[from]=2000"
        ]
        
        all_ads = []
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json",
            "Accept-Language": "ru-RU,ru;q=0.9"
        }
        
        for url in urls:
            try:
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        items = data.get("items", [])
                        all_ads.extend(items)
                        logger.info(f"Получено {len(items)} объявлений с {url}")
                    else:
                        logger.warning(f"Ошибка {response.status} при запросе к {url}")
            except Exception as e:
                logger.error(f"Ошибка при запросе: {e}")
                continue
                
        return all_ads

    async def calculate_market_price(self, ad):
        """Расчет средней рыночной цены"""
        try:
            title = ad.get("title", "").lower()
            year = ad.get("year", 0)
            brand = title.split()[0] if title else ""
            
            # Базовые цены для популярных марок (примерные)
            base_prices = {
                'toyota': 800000,
                'honda': 700000,
                'nissan': 650000,
                'hyundai': 600000,
                'kia': 550000,
                'bmw': 900000,
                'mercedes': 1000000,
                'audi': 850000,
                'lexus': 1100000,
                'subaru': 700000,
                'mitsubishi': 650000,
                'ford': 600000,
                'chevrolet': 550000,
                'volkswagen': 700000,
                'skoda': 600000,
                'renault': 500000,
                'peugeot': 550000,
                'citroen': 500000
            }
            
            # Поиск марки в заголовке
            found_brand = None
            for b in base_prices:
                if b in title:
                    found_brand = b
                    break
            
            if found_brand:
                base_price = base_prices[found_brand]
                # Корректировка по году
                year_factor = 1 + (year - 2000) * 0.03  # +3% за каждый год
                return base_price * year_factor
            
            # Если марка не найдена, используем среднюю цену
            session = await self.get_session()
            search_url = f"https://lalafo.kg/api/search?category_id=5830&city_id=1&year[from]={year-2}&year[to]={year+2}&per-page=30"
            
            async with session.get(search_url) as response:
                if response.status == 200:
                    data = await response.json()
                    items = data.get("items", [])
                    if items:
                        prices = [int(item.get("price", 0)) for item in items if item.get("price", 0) > 1000]
                        if prices:
                            return sum(prices) / len(prices)
            
            return None
            
        except Exception as e:
            logger.error(f"Ошибка расчета цены: {e}")
            return None

    def is_valid_car(self, ad):
        """Проверка, является ли объявление автомобилем"""
        title = ad.get("title", "").lower()
        
        # Проверка на стоп-слова
        for word in EXCLUDED_WORDS:
            if word in title:
                return False
        
        # Проверка на наличие года
        year = ad.get("year", 0)
        if year < MIN_YEAR:
            return False
            
        # Проверка цены
        price = int(ad.get("price", 0))
        if price < 50000 or price > 5000000:  # Слишком дешево/дорого
            return False
            
        # Проверка города
        city = ad.get("city", "").lower()
        if "бишкек" not in city and "bishkek" not in city:
            return False
            
        return True

    async def check_ads(self):
        """Основная проверка объявлений"""
        logger.info("Начинаю проверку объявлений...")
        
        try:
            ads = await self.get_ads()
            if not ads:
                logger.warning("Не удалось получить объявления")
                return
            
            logger.info(f"Получено {len(ads)} объявлений для проверки")
            
            # Сортируем по цене (самые дешевые сначала)
            ads.sort(key=lambda x: int(x.get("price", 0)))
            
            new_ads = []
            for ad in ads:
                ad_id = ad.get("id")
                if ad_id not in self.seen_ads:
                    new_ads.append(ad)
                    self.seen_ads.add(ad_id)
                    
            logger.info(f"Найдено {len(new_ads)} новых объявлений")
            
            # Ограничиваем количество проверяемых объявлений
            checked_ads = new_ads[:10]  # Проверяем первые 10 новых
            
            for ad in checked_ads:
                if not self.is_valid_car(ad):
                    continue
                    
                price = int(ad.get("price", 0))
                market_price = await self.calculate_market_price(ad)
                
                if market_price:
                    discount = 1 - (price / market_price)
                    if discount >= 0.15:  # Скидка 15% и более
                        await self.send_alert(ad, price, market_price)
                        # Ждем немного между отправками
                        await asyncio.sleep(2)
                
        except Exception as e:
            logger.error(f"Ошибка в check_ads: {e}")

    async def send_alert(self, ad, price, market_price):
        """Отправка уведомления в Telegram"""
        try:
            discount_percent = int((1 - price/market_price) * 100)
            
            message = (
                f"🔔 **ВЫГОДНОЕ ПРЕДЛОЖЕНИЕ!**\n\n"
                f"🚗 {ad.get('title', 'Без названия')}\n"
                f"📅 Год: {ad.get('year', 'Не указан')}\n"
                f"💰 Цена: {price:,} сом\n"
                f"📊 Рынок: {int(market_price):,} сом\n"
                f"💚 Экономия: {int(market_price - price):,} сом ({discount_percent}%)\n"
                f"📍 {ad.get('city', 'Бишкек')}\n"
                f"📅 Найдено: {datetime.now().strftime('%H:%M %d.%m.%Y')}\n"
                f"🔗 [Смотреть объявление](https://lalafo.kg{ad.get('url', '#')})"
            )
            
            await self.bot.send_message(
                chat_id=CHAT_ID,
                text=message,
                parse_mode='Markdown'
            )
            
            logger.info(f"✅ Отправлено уведомление: {ad.get('title')[:50]}...")
            
        except TelegramError as e:
            logger.error(f"Ошибка отправки в Telegram: {e}")
        except Exception as e:
            logger.error(f"Неизвестная ошибка: {e}")

    async def run(self):
        """Запуск бота"""
        logger.info("🚀 Бот запущен с токеном: ..." + TELEGRAM_TOKEN[-6:])
        logger.info(f"📤 Отправка уведомлений в чат: {CHAT_ID}")
        logger.info(f"⏱ Интервал проверки: {CHECK_INTERVAL} секунд")
        
        # Отправляем тестовое сообщение
        try:
            await self.bot.send_message(
                chat_id=CHAT_ID,
                text="🤖 Бот запущен и начал мониторинг объявлений Lalafo!"
            )
            logger.info("✅ Тестовое сообщение отправлено")
        except Exception as e:
            logger.error(f"❌ Не удалось отправить тестовое сообщение: {e}")
        
        while True:
            try:
                await self.check_ads()
            except Exception as e:
                logger.error(f"Ошибка в основном цикле: {e}")
            
            # Ждем перед следующей проверкой
            logger.info(f"⏳ Ожидание {CHECK_INTERVAL} секунд...")
            await asyncio.sleep(CHECK_INTERVAL)

async def main():
    bot = LalafoBot()
    await bot.run()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("👋 Бот остановлен")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
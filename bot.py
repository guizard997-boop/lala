import os
import asyncio
import logging
import requests
from datetime import datetime
from telegram import Bot
import time

# КОНФИГУРАЦИЯ
TELEGRAM_TOKEN = "ВАШ_НОВЫЙ_ТОКЕН"  # ЗАМЕНИТЕ!
CHAT_ID = "8078921787"
MIN_YEAR = 2000
CHECK_INTERVAL = 180

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class LalafoBot:
    def __init__(self):
        self.bot = Bot(token=TELEGRAM_TOKEN)
        self.seen_ads = set()

    def get_ads(self):
        """Получение объявлений через requests"""
        url = "https://lalafo.kg/api/search"
        params = {
            "category_id": 5830,
            "city_id": 1,
            "sort_by": "created_at",
            "sort_order": "desc",
            "per-page": 20,
            "year[from]": MIN_YEAR
        }
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json"
        }
        
        try:
            response = requests.get(url, params=params, headers=headers, timeout=30)
            if response.status_code == 200:
                data = response.json()
                return data.get("items", [])
            else:
                logger.error(f"Ошибка API: {response.status_code}")
        except Exception as e:
            logger.error(f"Ошибка: {e}")
        return []

    def check_ads(self):
        """Проверка новых объявлений"""
        logger.info("Проверка объявлений...")
        ads = self.get_ads()
        if not ads:
            logger.warning("Нет объявлений")
            return
        
        logger.info(f"Получено {len(ads)} объявлений")
        
        for ad in ads[:5]:
            ad_id = ad.get("id")
            if ad_id not in self.seen_ads:
                self.seen_ads.add(ad_id)
                price = int(ad.get("price", 0))
                title = ad.get("title", "").lower()
                
                # Фильтр стоп-слов
                stop_words = ['запчасть', 'двигатель', 'коробка', 'шина', 
                             'экскаватор', 'трактор', 'автозапчасти', 'ремонт']
                if any(word in title for word in stop_words):
                    continue
                
                # Проверка цены (от 50,000 до 400,000 сом)
                if 50000 < price < 400000:
                    self.send_alert(ad, price)
                    time.sleep(2)  # Пауза между отправками

    def send_alert(self, ad, price):
        """Отправка уведомления"""
        try:
            year = ad.get("year", "не указан")
            message = (
                f"🚗 **{ad.get('title', 'Авто')}**\n"
                f"📅 Год: {year}\n"
                f"💰 {price:,} сом\n"
                f"📍 Бишкек\n"
                f"🔗 [Смотреть объявление](https://lalafo.kg{ad.get('url', '')})\n"
                f"🕐 {datetime.now().strftime('%H:%M')}"
            )
            
            self.bot.send_message(
                chat_id=CHAT_ID,
                text=message,
                parse_mode='Markdown'
            )
            logger.info(f"✅ Уведомление отправлено: {ad.get('title')[:30]}")
        except Exception as e:
            logger.error(f"Ошибка отправки: {e}")

    def run(self):
        """Запуск бота"""
        logger.info("🚀 Бот запущен!")
        
        # Тестовое сообщение
        try:
            self.bot.send_message(
                chat_id=CHAT_ID,
                text="✅ Бот успешно запущен и мониторит Lalafo!"
            )
            logger.info("✅ Тестовое сообщение отправлено")
        except Exception as e:
            logger.error(f"❌ Не удалось отправить тест: {e}")
        
        # Основной цикл
        while True:
            try:
                self.check_ads()
            except Exception as e:
                logger.error(f"Ошибка в цикле: {e}")
            
            logger.info(f"⏳ Ожидание {CHECK_INTERVAL} секунд...")
            time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    bot = LalafoBot()
    bot.run()
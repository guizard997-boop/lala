import os
import time
import json
import re
import statistics
import requests
from datetime import datetime

# ================== CONFIG ==================
BOT_TOKEN = "8850394642:AAFSVcUFOBE9WdAQxNVdDLzTg7GBpN8x1yc"
CHAT_ID = "8078921787"

CHECK_INTERVAL = 50
CITY_ID = 103184
# Легковые авто на Lalafo KG
CATEGORY_ID = 1501
SEEN_FILE = "seen_ads.json"
USD_KGS_RATE = 87.5

# --- Скупка ---
REQUIRED_MARGIN_PCT = 0.23
REQUIRED_MARGIN_PCT_HIGH_LIQ = 0.20
REQUIRED_MARGIN_PCT_LOW_LIQ = 0.28
MIN_PROFIT = 800
MIN_DISCOUNT = 0.18
MIN_SIMILAR_LISTINGS = 5
MIN_YEAR = 2008
STAGE1_MIN_DISCOUNT = 0.12

# Цена как фильтр релевантности (USD)
MIN_PRICE_USD = 3500
MAX_PRICE_USD = 80000

# Доп. буст, не основной фильтр
URGENT_BOOST_KEYWORDS = [
    "срочно", "торг", "уступлю", "сегодня", "торг реальному",
    "нужны деньги", "быстро продам", "цена снижена",
]

# ===========================================================

KNOWN_MAKES = {
    "toyota", "lexus", "honda", "nissan", "hyundai", "kia", "bmw", "mercedes",
    "mercedes-benz", "audi", "volkswagen", "vw", "ford", "chevrolet", "mazda",
    "subaru", "mitsubishi", "suzuki", "opel", "skoda", "renault", "peugeot",
    "citroen", "volvo", "land rover", "range rover", "jeep", "dodge", "chrysler",
    "infiniti", "acura", "genesis", "ssangyong", "daewoo", "ravon", "geely",
    "chery", "haval", "great wall", "byd", "tesla", "porsche", "mini", "daihatsu",
    "lifan", "faw", "uaz", "lada", "ваз",
}

HIGH_LIQUIDITY = {
    ("toyota", "camry"), ("toyota", "corolla"), ("toyota", "rav4"),
    ("toyota", "prado"), ("toyota", "highlander"), ("toyota", "land"),
    ("lexus", "rx"), ("lexus", "gx"), ("lexus", "es"), ("lexus", "lx"),
    ("honda", "cr"), ("honda", "accord"), ("honda", "fit"),
    ("hyundai", "tucson"), ("hyundai", "sonata"), ("hyundai", "elantra"),
    ("kia", "sportage"), ("kia", "k5"), ("kia", "sorento"),
    ("nissan", "x"), ("nissan", "patrol"),
    ("bmw", "x5"), ("bmw", "x3"), ("mercedes", "e"), ("mercedes-benz", "e"),
}

MEDIUM_LIQUIDITY_MAKES = {
    "toyota", "lexus", "honda", "nissan", "hyundai", "kia", "bmw",
    "mercedes", "mercedes-benz", "audi", "subaru", "mazda", "volkswagen", "vw",
}

# Стоп-слова: запчасти / аксессуары / услуги (title + description)
STOP_WORDS = [
    "чехол", "стекло на", "стекло для", "запчаст", "запчасти", "аксессуар",
    "коробка от", "документы на", "ремонт", "услуг", "работаю", "работы",
    "разбор", "в разборе", "контрактн", "б/у запчаст", "продаю запчаст",
    "диск", "диски", "ремень", "турбина", "бампер", "крыло", "дверь",
    "капот", "зеркало", "подшипник", "сайлент", "амортизатор", "стойка",
    "радиатор", "генератор", "стартер", "компрессор", "шины", "резина",
    "колесо", "колпак", "ключ зажиган", "магнитола", "парктроник",
    "фара", "фары", "стоп", "стопы", "фонарь", "поворотник", "коврик",
    "накидк", "оплетка", "оплётка", "щетк", "дворник", "фильтр",
    "колодк", "свеч", "аккумулятор", "аймак", "масло мотор",
]

CRITICAL_DAMAGE = [
    "битый", "битая", "битое", "после дтп", "после аварии",
    "аварийный", "аварийная", "не на ходу", "не находу",
    "на запчасти", "на запчасть", "распил", "каркас", "конструктор",
    "распилен", "только на запчасти",
]

INSTALLMENT_KEYWORDS = [
    "рассрочк", "рассрочка", "первоначальн", "в кредит", "кредит",
    "ежемесячн", "платеж", "платёж", "лизинг", "оплата частями",
    "первый взнос", "0-0-24", "0-0-12", "без первоначального",
]

ORDER_KEYWORDS = [
    "под заказ", "подзаказ", "на заказ", "заказ из", "из китая", "из кореи",
    "из японии", "из оаэ", "из дубая", "из сша", "из америки", "из европы",
    "в пути", "едет", "ожидается", "пригон", "с аукциона", "copart", "iaai",
]

NOT_CLEARED = [
    "не растаможен", "не растаможена", "не растаможено", "без растаможки",
    "без растамож", "не на учете", "временный учет", "временный учёт",
    "транзит", "без птс", "транзитные номера",
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "device": "pc",
    "language": "ru_RU",
    "country-id": "12",
}

CYRILLIC_MAKE_MAP = {
    "тойота": "toyota", "лексус": "lexus", "хонда": "honda", "ниссан": "nissan",
    "хундай": "hyundai", "хендай": "hyundai", "киа": "kia", "бмв": "bmw",
    "мерседес": "mercedes", "ауди": "audi", "фольксваген": "volkswagen",
    "мазда": "mazda", "субару": "subaru", "мицубиси": "mitsubishi", "камри": "camry",
}

# Минимально адекватная цена модели (анти-мусор)
PRICE_FLOORS = {
    ("lexus", "gx"): 40000, ("lexus", "lx"): 45000, ("lexus", "rx"): 18000,
    ("lexus", "es"): 12000, ("toyota", "prado"): 18000, ("toyota", "land"): 22000,
    ("toyota", "camry"): 7000, ("toyota", "highlander"): 15000,
    ("bmw", "x5"): 15000, ("bmw", "x7"): 35000,
    ("mercedes", "g"): 40000, ("mercedes-benz", "g"): 40000,
}


def load_seen():
    if not os.path.exists(SEEN_FILE):
        return {}
    try:
        with open(SEEN_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return {str(x): None for x in data}
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return {}


def save_seen(seen):
    items = list(seen.items())[-4000:]
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        json.dump(dict(items), f)


def send_telegram(text, photo_url=None):
    try:
        if photo_url and len(text) <= 1000:
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
            data = {
                "chat_id": CHAT_ID,
                "photo": photo_url,
                "caption": text[:1024],
                "parse_mode": "HTML",
            }
        else:
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
            data = {
                "chat_id": CHAT_ID,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": False,
            }
        r = requests.post(url, data=data, timeout=15)
        if r.status_code != 200:
            print("Telegram error:", r.text[:200])
        else:
            print("Telegram OK")
    except Exception as e:
        print("Telegram:", e)


def text_has(text, words):
    t = (text or "").lower()
    return any(w in t for w in words)


def extract_year(title):
    if not title:
        return None
    m = re.search(r"(20\d{2}|19\d{2})\s*г", title, re.I)
    if m:
        return int(m.group(1))
    m = re.search(r"\b(20\d{2}|19\d{2})\b", title)
    return int(m.group(1)) if m else None


def extract_make_model(title):
    if not title:
        return None, None
    clean = re.sub(r"[^\w\s\-]", " ", title.lower())
    clean = re.sub(r"\s+", " ", clean).strip()
    clean = re.sub(r"\b(19|20)\d{2}\b", "", clean)
    clean = re.sub(r"\s*г\.?\s*", " ", clean).strip()
    for cyr, lat in CYRILLIC_MAKE_MAP.items():
        clean = re.sub(rf"\b{cyr}\b", lat, clean)
    clean = clean.replace("камри", "camry").replace("гибрид", "hybrid")
    words = clean.split()
    if not words:
        return None, None
    make, model_parts = None, []
    for i, word in enumerate(words):
        if word in KNOWN_MAKES:
            make = word
            model_parts = words[i + 1 : i + 3]
            break
        if i + 1 < len(words):
            two = f"{word} {words[i + 1]}"
            if two in KNOWN_MAKES:
                make = two
                model_parts = words[i + 2 : i + 4]
                break
    if not make and "camry" in clean:
        make = "toyota"
        model_parts = ["camry"] + (["hybrid"] if "hybrid" in clean else [])
    if not make and words:
        make = words[0]
        model_parts = words[1:3]
    model = " ".join(model_parts).strip() if model_parts else None
    return make, model


def extract_mileage(text):
    if not text:
        return None
    for p in [
        r"пробег[:\s]*(\d{1,3}[\s]?000|\d{4,7})\s*(км|km)?",
        r"(\d{1,3}[\s]?\d{3})\s*(км|km)",
        r"(\d+)\s*тыс\.?\s*(км|km)?",
    ]:
        m = re.search(p, text.lower())
        if m:
            raw = re.sub(r"\s+", "", m.group(1))
            try:
                val = int(raw)
                if "тыс" in (m.group(0) or ""):
                    val *= 1000
                if 1000 <= val <= 900000:
                    return val
            except ValueError:
                pass
    return None


def extract_engine(text):
    if not text:
        return None
    m = re.search(r"\b([1-6][.,]\d)\s*(л|l)?\b", text.lower())
    return m.group(1).replace(",", ".") if m else None


def extract_fuel(text):
    t = (text or "").lower()
    if any(x in t for x in ["дизел", "diesel", "дизель"]):
        return "diesel"
    if any(x in t for x in ["гибрид", "hybrid"]):
        return "hybrid"
    if any(x in t for x in ["электро", "electric"]):
        return "electric"
    if any(x in t for x in ["бензин", "petrol"]):
        return "petrol"
    return None


def extract_transmission(text):
    t = (text or "").lower()
    if any(x in t for x in ["акпп", "автомат", "automatic", "cvt", "вариатор"]):
        return "auto"
    if any(x in t for x in ["мкпп", "механика", "manual"]):
        return "manual"
    return None


def extract_drive(text):
    t = (text or "").lower()
    if any(x in t for x in ["полный", "4wd", "awd", "4x4"]):
        return "awd"
    if any(x in t for x in ["передний", "fwd"]):
        return "fwd"
    if any(x in t for x in ["задний", "rwd"]):
        return "rwd"
    return None


def extract_body(text):
    t = (text or "").lower()
    for k, v in [
        ("седан", "sedan"), ("хетч", "hatch"), ("хэтч", "hatch"),
        ("универсал", "wagon"), ("внедорожник", "suv"), ("кроссовер", "suv"),
        ("минивэн", "mpv"), ("пикап", "pickup"), ("купе", "coupe"),
    ]:
        if k in t:
            return v
    return None


def price_to_usd(ad):
    price = ad.get("price")
    if price is None:
        return None
    try:
        price = float(price)
    except (ValueError, TypeError):
        return None
    currency = (ad.get("currency") or "").upper().strip()
    symbol = (ad.get("symbol") or "").upper().strip()
    if currency in ("USD", "$") or symbol in ("$", "USD"):
        usd = price
    elif currency in ("KGS", "COM", "СОМ", "SOM") or symbol in ("COM", "С", "СОМ", "SOM"):
        usd = price / USD_KGS_RATE
    else:
        usd = price / USD_KGS_RATE if price >= 80000 else price
    if usd < 1500 or usd > 120000:
        return None
    return round(usd)


def normalize(ad):
    title = ad.get("title") or ""
    desc = ad.get("description") or ""
    blob = f"{title} {desc}"
    make, model = extract_make_model(title)
    return {
        "id": ad.get("id"),
        "title": title,
        "description": desc,
        "make": make,
        "model": model,
        "year": extract_year(title),
        "engine": extract_engine(blob),
        "fuel": extract_fuel(blob),
        "transmission": extract_transmission(blob),
        "drive": extract_drive(blob),
        "body": extract_body(blob),
        "mileage": extract_mileage(blob),
        "price_usd": price_to_usd(ad),
        "url": ad.get("url") or "",
        "city": ad.get("city") or "Бишкек",
        "images": ad.get("images"),
        "raw": ad,
    }


def is_offtopic_or_blocked(title, description=""):
    """
    Фильтр мусора:
    - стоп-слова (запчасти/чехлы/услуги) в title И description
    - битые / заказ / рассрочка / нерастаможен
    """
    blob = f"{title} {description}"
    if text_has(blob, STOP_WORDS):
        return True
    if text_has(blob, CRITICAL_DAMAGE):
        return True
    if text_has(blob, INSTALLMENT_KEYWORDS):
        return True
    if text_has(blob, ORDER_KEYWORDS):
        return True
    if text_has(blob, NOT_CLEARED):
        return True
    return False


def has_urgent_marker(title, description=""):
    return text_has(f"{title} {description}", URGENT_BOOST_KEYWORDS)


def sane_min_price(make, model, year=None):
    make = (make or "").lower()
    model = (model or "").lower()
    first = model.split()[0] if model else ""
    floor = MIN_PRICE_USD
    for (m, tok), f in PRICE_FLOORS.items():
        if make == m and (tok in model or first == tok or tok in first):
            floor = max(floor, f)
            break
    if year and year >= 2022 and floor >= 15000:
        floor = int(floor * 1.35)
    elif year and year >= 2018 and floor >= 15000:
        floor = int(floor * 1.15)
    return floor


def get_liquidity_margin_pct(make, model):
    make = (make or "").lower()
    model = (model or "").lower()
    first = model.split()[0] if model else ""
    for hm, hmod in HIGH_LIQUIDITY:
        if make == hm and (hmod in model or first.startswith(hmod) or hmod in first):
            return REQUIRED_MARGIN_PCT_HIGH_LIQ, "высокая"
    if make in MEDIUM_LIQUIDITY_MAKES:
        return REQUIRED_MARGIN_PCT, "средняя"
    return REQUIRED_MARGIN_PCT_LOW_LIQ, "низкая"


def get_ads(page=1, q=None, per_page=50, year_from=None, year_to=None):
    """Только Lalafo, строго category_id = легковые."""
    params = {
        "per-page": per_page,
        "page": page,
        "expand": "url",
        "sort_by": "newest",
        "city_id": CITY_ID,
        "category_id": CATEGORY_ID,
    }
    if q:
        params["q"] = q
    if year_from:
        params["parameters[62][from]"] = year_from
    if year_to:
        params["parameters[62][to]"] = year_to
    try:
        r = requests.get(
            "https://api.lalafo.com/v3/ads/search",
            params=params,
            headers=HEADERS,
            timeout=15,
        )
        if r.status_code == 200:
            return r.json().get("items", [])
    except Exception as e:
        print("Lalafo error:", e)
    return []


def similar_match(target, cand):
    if not target.get("make") or not cand.get("make"):
        return False
    if target["make"] != cand["make"]:
        return False
    t_m = (target.get("model") or "").split()
    c_m = (cand.get("model") or "").split()
    if t_m and c_m and t_m[0] != c_m[0]:
        return False
    ty, cy = target.get("year"), cand.get("year")
    if ty and cy and abs(ty - cy) > 1:
        return False
    for key in ("engine", "fuel", "body", "transmission", "drive"):
        tv, cv = target.get(key), cand.get(key)
        if tv and cv and tv != cv:
            return False
    tm, cm = target.get("mileage"), cand.get("mileage")
    if tm and cm and tm > 0 and abs(cm - tm) / tm > 0.35:
        return False
    return True


def remove_outliers(prices):
    if len(prices) < 4:
        return prices
    med = statistics.median(prices)
    cleaned = [p for p in prices if med * 0.55 <= p <= med * 1.35]
    return cleaned if len(cleaned) >= MIN_SIMILAR_LISTINGS else prices


def find_similar_prices(car):
    make, model, year = car.get("make"), car.get("model"), car.get("year")
    if not make or not year:
        return []
    query = make
    if model:
        query += " " + model.split()[0]
    if make == "toyota" and model and "camry" in model and car.get("fuel") == "hybrid":
        query = "toyota camry hybrid"

    year_from, year_to = max(year - 1, 1985), year + 1
    items = get_ads(q=query, per_page=60, year_from=year_from, year_to=year_to)
    items += get_ads(page=2, q=query, per_page=40, year_from=year_from, year_to=year_to)

    prices = []
    for item in items:
        if is_offtopic_or_blocked(item.get("title") or "", item.get("description") or ""):
            continue
        c = normalize(item)
        if not c["price_usd"]:
            continue
        if str(c["id"]) == str(car.get("id")):
            continue
        if c["price_usd"] < MIN_PRICE_USD or c["price_usd"] > MAX_PRICE_USD:
            continue
        if not similar_match(car, c):
            continue
        prices.append(c["price_usd"])
    return remove_outliers(prices)


def stage1_rough_reject(car):
    make, model, year = car.get("make"), car.get("model"), car.get("year")
    listing = car.get("price_usd")
    if not make or not listing or not year:
        return True
    query = make + ((" " + model.split()[0]) if model else "")
    items = get_ads(
        q=query, per_page=30,
        year_from=max(year - 2, 1985), year_to=year + 2,
    )
    prices = []
    for item in items:
        if is_offtopic_or_blocked(item.get("title") or "", item.get("description") or ""):
            continue
        p = price_to_usd(item)
        if p and MIN_PRICE_USD <= p <= MAX_PRICE_USD:
            prices.append(p)
    if len(prices) < 3:
        return False
    med = statistics.median(prices)
    if med <= 0:
        return True
    discount = (med - listing) / med
    return discount < STAGE1_MIN_DISCOUNT


def deal_score(discount, potential_profit, n_similar, liq_label, urgent=False):
    score = 0.0
    score += min(55, max(0, discount * 100 * 1.6))
    if potential_profit >= 2500:
        score += 25
    elif potential_profit >= 1500:
        score += 18
    elif potential_profit >= 1000:
        score += 12
    elif potential_profit >= MIN_PROFIT:
        score += 6
    else:
        score -= 10
    if n_similar >= 10:
        score += 8
    elif n_similar >= MIN_SIMILAR_LISTINGS:
        score += 4
    if liq_label == "высокая":
        score += 8
    elif liq_label == "низкая":
        score -= 10
    if urgent:
        score += 3
    return int(max(0, min(100, round(score))))


def score_fires(discount, potential_profit):
    if discount >= 0.28 and potential_profit >= 1500:
        return "🔥🔥🔥"
    if discount >= 0.22 and potential_profit >= 1000:
        return "🔥🔥"
    return "🔥"


def analyze(ad, seen):
    ad_id = str(ad.get("id") or "")
    if not ad_id:
        return

    title = ad.get("title") or ""
    description = ad.get("description") or ""

    # 1) категория уже в API; 2) стоп-слова title+desc
    if is_offtopic_or_blocked(title, description):
        seen[ad_id] = price_to_usd(ad)
        return

    car = normalize(ad)
    listing = car["price_usd"]
    if not listing or not car["make"] or not car["year"]:
        seen[ad_id] = listing
        return
    if car["year"] < MIN_YEAR:
        seen[ad_id] = listing
        return

    # 3) цена в разумном диапазоне категории
    if listing < MIN_PRICE_USD or listing > MAX_PRICE_USD:
        print(f"  skip (цена вне диапазона ${listing}): {title[:40]}")
        seen[ad_id] = listing
        return

    floor = sane_min_price(car["make"], car["model"], car["year"])
    if listing < floor:
        print(f"  skip (ниже адекватной ${listing}<${floor}): {title[:40]}")
        seen[ad_id] = listing
        return

    if ad_id in seen and seen[ad_id] is not None and seen[ad_id] == listing:
        return

    if stage1_rough_reject(car):
        print(f"  stage1 drop: {title[:40]} | ${listing}")
        seen[ad_id] = listing
        return

    similar_prices = find_similar_prices(car)
    if len(similar_prices) < MIN_SIMILAR_LISTINGS:
        print(f"  skip (мало аналогов {len(similar_prices)}): {title[:40]}")
        seen[ad_id] = listing
        return

    market_price = statistics.median(similar_prices)
    if not market_price or market_price <= 0:
        seen[ad_id] = listing
        return

    if listing < market_price * 0.55:
        print(f"  skip (подозрительно дёшево): {title[:40]} | ${listing} vs ${market_price:.0f}")
        seen[ad_id] = listing
        return

    margin_pct, liq_label = get_liquidity_margin_pct(car["make"], car["model"])
    buy_price = round(market_price * (1 - margin_pct))
    discount = (market_price - listing) / market_price
    potential_profit = market_price - listing

    if listing >= buy_price:
        print(f"  skip (>= BUY): {title[:35]} | ${listing} buy ${buy_price}")
        seen[ad_id] = listing
        return
    if discount < MIN_DISCOUNT:
        print(f"  skip (discount {discount*100:.1f}%): {title[:40]}")
        seen[ad_id] = listing
        return
    if potential_profit < MIN_PROFIT:
        print(f"  skip (profit ${potential_profit:.0f}): {title[:40]}")
        seen[ad_id] = listing
        return

    urgent = has_urgent_marker(title, description)
    score = deal_score(discount, potential_profit, len(similar_prices), liq_label, urgent)
    if score < 70:
        print(f"  skip (score {score}): {title[:40]}")
        seen[ad_id] = listing
        return

    fires = score_fires(discount, potential_profit)
    url = "https://lalafo.kg" + (car["url"] or "")
    photo = None
    if car.get("images"):
        photo = car["images"][0].get("original_url") or car["images"][0].get("thumbnail_url")

    urgent_mark = "⚡ " if urgent else ""
    text = (
        f"🚨 <b>СКУПКА</b> {fires}\n\n"
        f"{urgent_mark}<b>{car['title']}</b>\n"
        f"Источник: Lalafo\n"
        f"Цена: <b>${listing:,.0f}</b>\n"
        f"Рынок: ~${market_price:,.0f}\n"
        f"Цена скупки: ≤${buy_price:,.0f}\n"
        f"Запас: ~${potential_profit:,.0f}\n"
        f"Оценка: {fires} ({score}/100)\n"
        f"<a href='{url}'>Ссылка</a>"
    )
    send_telegram(text, photo)
    print(f"[{datetime.now()}] SEND {fires} {score} | {title[:40]} | ${listing}")
    seen[ad_id] = listing


def main():
    print("Бот СКУПКА Lalafo-only запущен...")
    send_telegram("🎩 <b>Господин Дияр, ваш бот полностью готов служить вам.</b>")
    seen = load_seen()
    print(
        f"seen={len(seen)} | cat={CATEGORY_ID} | "
        f"price ${MIN_PRICE_USD}-{MAX_PRICE_USD} | margin={REQUIRED_MARGIN_PCT*100:.0f}%"
    )

    while True:
        try:
            print(f"\n[{datetime.now()}] Lalafo cat={CATEGORY_ID}...")
            ads = get_ads(page=1, per_page=40)
            print(f"Лента: {len(ads)}")
            for ad in ads:
                try:
                    analyze(ad, seen)
                except Exception as e:
                    print("analyze err:", e)
            save_seen(seen)
            print(f"Цикл OK, сон {CHECK_INTERVAL}с")
            time.sleep(CHECK_INTERVAL)
        except Exception as e:
            print("Ошибка:", e)
            time.sleep(20)


if __name__ == "__main__":
    main()

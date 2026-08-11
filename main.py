import os
import time
import json
import re
import statistics
import requests
from datetime import datetime

# ================== НАСТРОЙКИ ==================
BOT_TOKEN = "8850394642:AAFSVcUFOBE9WdAQxNVdDLzTg7GBpN8x1yc"
CHAT_ID = "8078921787"

CHECK_INTERVAL = 45
MIN_YEAR = 2005
CITY_ID = 103184
SEEN_FILE = "seen_ads.json"
USD_KGS_RATE = 87.5

# ---- ЭКОНОМИКА СКУПКИ ----
BASE_EXPENSES_USD = 200          # оформление, объявления, бензин
NEGOTIATION_RESERVE = 0.03       # 3% запас на торг при перепродаже
REQUIRED_PROFIT_USD = 500        # минимальная целевая прибыль
MIN_PROFIT_RATIO = 0.05          # минимум ~5% от быстрой продажи

# Рынок
MARKET_MEDIAN = True
QUICK_SELL_PERCENTILE = 35       # было 22 — слишком жёстко; 35 = реалистичная быстрая продажа
MIN_COMPARABLES = 3              # 3+ уже считаем
YEAR_TOLERANCE = 1
MILEAGE_TOLERANCE = 0.35

# Отправка
MIN_SCORE_TO_SEND = 70           # ниже 70 не кидаем
NEGOTIATE_BAND = 0.06            # до +6% выше MAX_BUY = "можно торговаться"

# Приоритет Camry Hybrid 70
PRIORITY_REQUIRED_PROFIT_USD = 400
PRIORITY_BASE_EXPENSES_USD = 150

KNOWN_MAKES = {
    "toyota", "lexus", "honda", "nissan", "hyundai", "kia", "bmw", "mercedes",
    "mercedes-benz", "audi", "volkswagen", "vw", "ford", "chevrolet", "mazda",
    "subaru", "mitsubishi", "suzuki", "opel", "skoda", "renault", "peugeot",
    "citroen", "volvo", "land rover", "range rover", "jeep", "dodge", "chrysler",
    "infiniti", "acura", "genesis", "ssangyong", "daewoo", "ravon", "geely",
    "chery", "haval", "great wall", "byd", "tesla", "porsche", "mini", "daihatsu",
    "lifan", "faw", "uaz", "lada", "ваз"
}

# Высокая ликвидность в Бишкеке
HIGH_LIQUIDITY = {
    ("toyota", "camry"), ("toyota", "corolla"), ("toyota", "rav4"),
    ("toyota", "land"), ("toyota", "prado"), ("toyota", "highlander"),
    ("lexus", "rx"), ("lexus", "gx"), ("lexus", "lx"), ("lexus", "es"),
    ("honda", "cr"), ("honda", "accord"), ("honda", "fit"),
    ("hyundai", "tucson"), ("hyundai", "sonata"), ("hyundai", "elantra"),
    ("kia", "sportage"), ("kia", "k5"), ("kia", "sorento"),
    ("nissan", "x"), ("nissan", "patrol"), ("bmw", "x5"), ("bmw", "x3"),
    ("mercedes", "e"), ("mercedes-benz", "e"),
}

MEDIUM_LIQUIDITY_MAKES = {
    "toyota", "lexus", "honda", "nissan", "hyundai", "kia", "bmw", "mercedes",
    "mercedes-benz", "audi", "subaru", "mazda", "volkswagen", "vw"
}

JUNK_KEYWORDS = [
    "запчаст", "диск", "диски", "ремень", "турбина", "бампер", "крыло",
    "дверь", "капот", "стекло", "зеркало", "подшипник", "сайлент",
    "амортизатор", "стойка", "радиатор", "генератор", "стартер",
    "компрессор", "кондиционер", "шины", "резина", "колесо", "колпак",
    "ключ", "замок", "сигнализация", "магнитола", "камера", "парктроник",
    "услуг", "работа", "разбор", "контрактн", "б/у запчаст", "продаю запчаст",
    "в разборе", "фара", "фары", "стоп", "стопы", "фонарь", "поворотник",
]

# Критические — сразу исключаем
CRITICAL_DAMAGE_KEYWORDS = [
    "битый", "битая", "битое", "после дтп", "после аварии", "серьёзн",
    "серьезн", "аварийный", "аварийная", "не на ходу", "не находу",
    "на запчасти", "на запчасть", "распил", "каркас", "конструктор",
    "распилен", "только на запчасти", "под восстановление кузова",
]

# Мелкие — НЕ исключаем, считаем расходы
MINOR_DAMAGE_KEYWORDS = [
    "вмятин", "царапин", "скол", "косметик", "мелкий ремонт",
    "требует ремонта", "нужен ремонт", "подкраска", "покраска",
    "ржавчин", "потёртост", "потертост", "бампер повреж",
    "замена расход", "требует вложений", "есть дефект",
]

INSTALLMENT_KEYWORDS = [
    "рассрочк", "рассрочка", "первоначальн", "первоначальный взнос",
    "в кредит", "кредит", "ежемесячн", "платеж", "платёж", "лизинг",
    "в месяц", "оплата частями", "частями", "первый взнос", "0-0-24", "0-0-12",
    "без первоначального", "без взноса",
]

ORDER_KEYWORDS = [
    "под заказ", "подзаказ", "на заказ", "заказ из", "заказать",
    "из китая", "из кореи", "из японии", "из оаэ", "из дубая",
    "из сша", "из америки", "из европы", "в пути", "едет",
    "ожидается", "прибудет", "доставка из", "пригон", "пригнать",
    "с аукциона", "copart", "iaai", "manheim",
]

NOT_CLEARED_KEYWORDS = [
    "не растаможен", "не растаможена", "не растаможено",
    "без растаможки", "без растамож", "не растаможенная",
    "не на учете", "не стоит на учете", "временный учет", "временный учёт",
    "транзит", "не оформлен", "без птс", "на транзите", "транзитные номера",
]

URGENT_KEYWORDS = [
    "срочно", "срочная продажа", "срочно продаю", "срочн",
    "цена снижена", "снизил цену", "торг реальному", "торг уместен",
    "ниже рынка", "отдам дешево", "отдам дёшево", "быстро продам",
    "нужны деньги", "срочный выкуп",
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


# ================================================

def load_seen():
    if os.path.exists(SEEN_FILE):
        try:
            with open(SEEN_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return set(data) if isinstance(data, list) else set()
        except Exception:
            return set()
    return set()


def save_seen(seen):
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        json.dump(list(seen)[-4000:], f)


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
            print("Telegram error:", r.text[:250])
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
        model_parts = ["camry"]
        if "hybrid" in clean:
            model_parts.append("hybrid")
    if not make and words:
        make = words[0]
        model_parts = words[1:3]
    model = " ".join(model_parts).strip() if model_parts else None
    return make, model


def extract_mileage(text):
    if not text:
        return None
    patterns = [
        r"пробег[:\s]*(\d{1,3}[\s]?000|\d{4,7})\s*(км|km)?",
        r"(\d{1,3}[\s]?\d{3})\s*(км|km)",
        r"(\d+)\s*тыс\.?\s*(км|km)?",
    ]
    for p in patterns:
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
    m = re.search(r"\b([1-6][.,]\d)\s*(л|l|cci|куб)?\b", text.lower())
    if m:
        return m.group(1).replace(",", ".")
    m = re.search(r"\b([1-6]\.\d)\b", text.lower())
    return m.group(1) if m else None


def extract_fuel(text):
    t = (text or "").lower()
    if any(x in t for x in ["дизел", "diesel", "дизель"]):
        return "diesel"
    if any(x in t for x in ["гибрид", "hybrid", "hv"]):
        return "hybrid"
    if any(x in t for x in ["электро", "electric", "ev "]):
        return "electric"
    if any(x in t for x in ["бензин", "petrol", "gas"]):
        return "petrol"
    return None


def extract_transmission(text):
    t = (text or "").lower()
    if any(x in t for x in ["акпп", "автомат", "automatic", "cvt", "вариатор", "робот"]):
        return "auto"
    if any(x in t for x in ["мкпп", "механика", "механич", "manual"]):
        return "manual"
    return None


def extract_drive(text):
    t = (text or "").lower()
    if any(x in t for x in ["полный", "4wd", "awd", "4x4", "полный привод"]):
        return "awd"
    if any(x in t for x in ["передний", "fwd"]):
        return "fwd"
    if any(x in t for x in ["задний", "rwd"]):
        return "rwd"
    return None


def extract_body(text):
    t = (text or "").lower()
    mapping = [
        ("седан", "sedan"), ("хетч", "hatch"), ("хэтч", "hatch"),
        ("универсал", "wagon"), ("внедорожник", "suv"), ("кроссовер", "suv"),
        ("suv", "suv"), ("минивэн", "mpv"), ("минивен", "mpv"),
        ("пикап", "pickup"), ("купе", "coupe"),
    ]
    for k, v in mapping:
        if k in t:
            return v
    return None


def is_priority_model(specs, title="", description=""):
    make = (specs.get("make") or "").lower()
    model = (specs.get("model") or "").lower()
    year = specs.get("year")
    blob = f"{title} {description} {model}".lower()
    if make != "toyota":
        return False
    if year and not (2017 <= year <= 2024):
        return False
    is_camry = "camry" in blob or "камри" in blob
    is_hybrid = specs.get("fuel") == "hybrid" or "hybrid" in blob or "гибрид" in blob
    return bool(is_camry and is_hybrid and year and 2017 <= year <= 2024)


def estimate_minor_repair_cost(title, description=""):
    """Ориентировочные $ на мелкие недостатки."""
    blob = f"{title} {description}".lower()
    cost = 0
    if text_has(blob, ["вмятин"]):
        cost += 150
    if text_has(blob, ["царапин", "скол", "потёртост", "потертост"]):
        cost += 80
    if text_has(blob, ["косметик", "подкраска", "покраска"]):
        cost += 200
    if text_has(blob, ["требует ремонта", "нужен ремонт", "требует вложений"]):
        cost += 250
    if text_has(blob, ["ржавчин"]):
        cost += 120
    if text_has(blob, ["замена расход", "расходник"]):
        cost += 100
    return min(cost, 800)


def get_liquidity(make, model):
    """Возвращает (уровень_строка, коэффициент 0.7–1.15)."""
    make = (make or "").lower()
    model = (model or "").lower()
    first = model.split()[0] if model else ""
    for (m, mod), _ in [((a, b), None) for a, b in HIGH_LIQUIDITY]:
        pass
    for hm, hmod in HIGH_LIQUIDITY:
        if make == hm and (hmod in model or first.startswith(hmod) or hmod in first):
            return "высокая", 1.12
    if make in MEDIUM_LIQUIDITY_MAKES:
        return "средняя", 1.0
    return "низкая", 0.82


def get_clean_price_usd(ad):
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
    if usd is None or usd < 1500 or usd > 100000:
        return None
    return round(usd)


def parse_ad_specs(ad):
    title = ad.get("title") or ""
    desc = ad.get("description") or ""
    blob = f"{title} {desc}"
    make, model = extract_make_model(title)
    return {
        "make": make,
        "model": model,
        "year": extract_year(title),
        "mileage": extract_mileage(blob),
        "engine": extract_engine(blob),
        "fuel": extract_fuel(blob),
        "transmission": extract_transmission(blob),
        "drive": extract_drive(blob),
        "body": extract_body(blob),
        "price": get_clean_price_usd(ad),
        "title": title,
        "description": desc,
        "ad": ad,
    }


def is_critical_bad(title, description=""):
    blob = f"{title} {description}"
    if text_has(title, JUNK_KEYWORDS):
        return True
    if text_has(blob, CRITICAL_DAMAGE_KEYWORDS):
        return True
    if text_has(blob, INSTALLMENT_KEYWORDS):
        return True
    if text_has(blob, ORDER_KEYWORDS):
        return True
    if text_has(blob, NOT_CLEARED_KEYWORDS):
        return True
    return False


def get_ads(page=1, q=None, per_page=50, year_from=None, year_to=None):
    params = {
        "per-page": per_page,
        "page": page,
        "expand": "url",
        "sort_by": "newest",
        "city_id": CITY_ID,
        "category_id": 1501,
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


def specs_match(target, cand):
    """Похожие авто. Если хар-ки нет у одного — не режем жёстко."""
    if not target.get("make") or not cand.get("make"):
        return False
    tm, cm = target["make"], cand["make"]
    if tm != cm and tm not in (cm or "") and (cm or "") not in tm:
        return False

    t_model = (target.get("model") or "").split()
    c_model = (cand.get("model") or "").split()
    if t_model and c_model and t_model[0] != c_model[0]:
        return False

    ty, cy = target.get("year"), cand.get("year")
    if ty and cy and abs(ty - cy) > YEAR_TOLERANCE:
        return False

    # мягко: только если ОБА указали и не совпало
    for key in ("engine", "fuel", "transmission", "body", "drive"):
        tv, cv = target.get(key), cand.get(key)
        if tv and cv and tv != cv:
            return False

    tmi, cmi = target.get("mileage"), cand.get("mileage")
    if tmi and cmi and tmi > 0:
        if abs(cmi - tmi) / tmi > MILEAGE_TOLERANCE:
            return False
    return True


def fetch_mashina_market_prices(make, model, year=None, pages=2):
    if not make:
        return []
    q = make
    if model:
        q += " " + model.split()[0]
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept-Language": "ru-RU,ru;q=0.9",
    }
    prices = []
    for page in range(1, pages + 1):
        url = f"https://www.mashina.kg/search/all/?q={requests.utils.quote(q)}&currency=2&page={page}"
        try:
            r = requests.get(url, headers=headers, timeout=20)
            if r.status_code != 200:
                continue
            html = r.text
            links = list(dict.fromkeys(re.findall(r"/details/([a-z0-9\-]+)", html)))
            raw_prices = re.findall(r"\$[\s\xa0\u00a0]?([\d\s\xa0\u00a0]+)", html)
            parsed = []
            for p in raw_prices:
                digits = re.sub(r"\D", "", p)
                if digits.isdigit():
                    val = int(digits)
                    if 1500 <= val <= 100000:
                        parsed.append(val)
            make_l = make.lower()
            model_token = (model or "").split()[0].lower() if model else ""
            for i, slug in enumerate(links):
                slug_l = slug.lower()
                if make_l not in slug_l:
                    continue
                if model_token and model_token not in ("hybrid",) and model_token not in slug_l:
                    if not (model_token == "camry" and "camry" in slug_l):
                        continue
                if i < len(parsed):
                    prices.append(parsed[i])
        except Exception as e:
            print("Mashina error:", e)
    return prices


def _mashina_slug_to_title(slug):
    if not slug:
        return "Авто Mashina"
    parts = slug.split("-")
    while parts and (len(parts[-1]) >= 10 or re.fullmatch(r"[0-9a-f]{8,}", parts[-1])):
        parts.pop()
    if not parts:
        return slug
    return " ".join(p.capitalize() for p in parts)


def fetch_mashina_feed(pages=2):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept-Language": "ru-RU,ru;q=0.9",
    }
    results = []
    seen_slugs = set()
    for page in range(1, pages + 1):
        url = f"https://www.mashina.kg/search/all/?currency=2&sort_by=upped_at+desc&page={page}"
        try:
            r = requests.get(url, headers=headers, timeout=25)
            if r.status_code != 200:
                continue
            html = r.text
            links = list(dict.fromkeys(re.findall(r"/details/([a-z0-9\-]+)", html)))
            raw_prices = re.findall(r"\$[\s\xa0\u00a0]?([\d\s\xa0\u00a0]+)", html)
            parsed = []
            for p in raw_prices:
                digits = re.sub(r"\D", "", p)
                if digits.isdigit():
                    val = int(digits)
                    if 1500 <= val <= 100000:
                        parsed.append(val)
            for i, slug in enumerate(links):
                if slug in seen_slugs:
                    continue
                seen_slugs.add(slug)
                price = parsed[i] if i < len(parsed) else None
                if not price:
                    continue
                results.append({
                    "id": f"mashina_{slug}",
                    "title": _mashina_slug_to_title(slug),
                    "description": "",
                    "price": price,
                    "currency": "USD",
                    "symbol": "$",
                    "url": f"https://www.mashina.kg/details/{slug}",
                    "city": "Бишкек",
                    "images": None,
                    "source": "mashina",
                })
        except Exception as e:
            print("Mashina feed error:", e)
    print(f"Mashina feed: {len(results)} объявлений")
    return results


def remove_price_outliers(prices):
    if len(prices) < 4:
        return prices
    med = statistics.median(prices)
    cleaned = [p for p in prices if med * 0.50 <= p <= med * 1.40]
    return cleaned if len(cleaned) >= 3 else prices


def percentile(data, percent):
    if not data:
        return None
    s = sorted(data)
    n = len(s)
    idx = (n - 1) * percent / 100
    f, c = int(idx), min(int(idx) + 1, n - 1)
    if f == c:
        return s[f]
    return s[f] * (c - idx) + s[c] * (idx - f)


def calc_market_metrics(prices):
    """
    Возвращает:
      market_median — рыночная (медиана)
      quick_sell — цена быстрой продажи (умеренный низ)
      cleaned — очищенные цены
    """
    cleaned = remove_price_outliers(prices)
    if len(cleaned) < MIN_COMPARABLES:
        return None, None, cleaned
    market = statistics.median(cleaned)
    quick = percentile(cleaned, QUICK_SELL_PERCENTILE)
    # quick_sell не выше медианы
    if quick and market and quick > market:
        quick = market * 0.95
    return market, quick, cleaned


def calc_max_buy(quick_sell, expenses, required_profit):
    if not quick_sell or quick_sell <= 0:
        return None
    after_reserve = quick_sell * (1 - NEGOTIATION_RESERVE)
    max_buy = after_reserve - expenses - required_profit
    if quick_sell > 0 and (quick_sell - max(max_buy, 0)) / quick_sell < MIN_PROFIT_RATIO:
        max_buy = quick_sell * (1 - MIN_PROFIT_RATIO) - expenses
    return max(0, round(max_buy))


def calc_deal_score(
    seller, market, quick_sell, max_buy, net_profit, n_comps,
    liquidity_coef, year, mileage, minor_cost, priority=False,
):
    """Рейтинг выгодности 0–100 для перекупа."""
    score = 50.0

    # Ниже рынка
    if market and market > 0:
        below = (market - seller) / market
        score += max(-25, min(30, below * 100 * 0.9))

    # Прибыль
    if net_profit >= 1200:
        score += 18
    elif net_profit >= 800:
        score += 12
    elif net_profit >= 500:
        score += 7
    elif net_profit >= 300:
        score += 3
    elif net_profit < 0:
        score -= 20
    else:
        score -= 5

    # Отношение к MAX_BUY
    if max_buy and max_buy > 0:
        if seller <= max_buy:
            score += 12
        elif seller <= max_buy * (1 + NEGOTIATE_BAND):
            score += 4
        else:
            score -= 15

    # Ликвидность
    score += (liquidity_coef - 1.0) * 25

    # Аналоги
    if n_comps >= 12:
        score += 6
    elif n_comps >= 6:
        score += 4
    elif n_comps >= 3:
        score += 1
    else:
        score -= 8

    # Год
    if year:
        if year >= 2018:
            score += 5
        elif year >= 2014:
            score += 2
        elif year < 2008:
            score -= 6

    # Пробег
    if mileage:
        if mileage < 80000:
            score += 4
        elif mileage < 150000:
            score += 1
        elif mileage > 250000:
            score -= 6

    # Мелкий ремонт
    if minor_cost >= 400:
        score -= 8
    elif minor_cost >= 200:
        score -= 4
    elif minor_cost > 0:
        score -= 2

    if priority:
        score += 5

    return int(max(0, min(100, round(score))))


def reliability_label(n):
    if n >= 10:
        return "высокая"
    if n >= 5:
        return "средняя"
    return "низкая"


def find_comparables(target_specs):
    make = target_specs.get("make")
    model = target_specs.get("model")
    year = target_specs.get("year")
    if not make or not year:
        return []

    query = make
    if model:
        query += " " + model.split()[0]
    blob_model = f"{model or ''} {target_specs.get('fuel') or ''}".lower()
    if make == "toyota" and "camry" in (model or ""):
        if target_specs.get("fuel") == "hybrid" or "hybrid" in blob_model:
            query = "toyota camry hybrid"

    year_from = max(year - YEAR_TOLERANCE, 1985)
    year_to = year + YEAR_TOLERANCE
    items = get_ads(q=query, per_page=60, year_from=year_from, year_to=year_to)
    items += get_ads(page=2, q=query, per_page=40, year_from=year_from, year_to=year_to)

    comps = []
    for item in items:
        if is_critical_bad(item.get("title") or "", item.get("description") or ""):
            continue
        sp = parse_ad_specs(item)
        if not sp["price"]:
            continue
        if not specs_match(target_specs, sp):
            continue
        sp["source"] = "lalafo"
        comps.append(sp)

    for p in fetch_mashina_market_prices(make, model, year):
        comps.append({
            "make": make, "model": model, "year": year, "price": p,
            "source": "mashina", "title": "", "description": "",
            "mileage": None, "engine": None, "fuel": target_specs.get("fuel"),
            "transmission": None, "drive": None, "body": None, "ad": None,
        })
    return comps


def analyze_and_notify(ad, seen):
    ad_id = ad.get("id")
    if ad_id in seen:
        return

    title = ad.get("title") or ""
    description = ad.get("description") or ""

    if is_critical_bad(title, description):
        seen.add(ad_id)
        return

    target = parse_ad_specs(ad)
    if not target["price"] or not target["make"] or not target["year"]:
        seen.add(ad_id)
        return
    if target["year"] < MIN_YEAR:
        seen.add(ad_id)
        return

    priority = is_priority_model(target, title, description)
    base_exp = PRIORITY_BASE_EXPENSES_USD if priority else BASE_EXPENSES_USD
    req_profit = PRIORITY_REQUIRED_PROFIT_USD if priority else REQUIRED_PROFIT_USD
    minor_cost = estimate_minor_repair_cost(title, description)
    total_expenses = base_exp + minor_cost

    comps = find_comparables(target)
    prices = [c["price"] for c in comps if c.get("price")]
    src_lalafo = sum(1 for c in comps if c.get("source") == "lalafo")
    src_mashina = sum(1 for c in comps if c.get("source") == "mashina")

    market, quick_sell, cleaned = calc_market_metrics(prices)
    if market is None or quick_sell is None:
        print(f"  skip (мало данных): {title[:40]} | n={len(prices)}")
        seen.add(ad_id)
        return

    max_buy = calc_max_buy(quick_sell, total_expenses, req_profit)
    if not max_buy:
        seen.add(ad_id)
        return

    seller = target["price"]
    net_profit = quick_sell - seller - total_expenses
    below_market_pct = ((market - seller) / market * 100) if market else 0

    # Статус сделки
    if seller <= max_buy:
        status = "buy"          # СКУПОЧНАЯ ЦЕНА
        status_line = "🔥 <b>СКУПОЧНАЯ ЦЕНА</b>"
    elif seller <= max_buy * (1 + NEGOTIATE_BAND):
        status = "negotiate"    # МОЖНО ТОРГОВАТЬСЯ
        status_line = "🟡 <b>МОЖНО ТОРГОВАТЬСЯ</b>"
    else:
        print(f"  skip (невыгодно): {title[:35]} | ask={seller}$ max={max_buy}$")
        seen.add(ad_id)
        return

    liq_label, liq_coef = get_liquidity(target["make"], target["model"])
    score = calc_deal_score(
        seller, market, quick_sell, max_buy, net_profit, len(cleaned),
        liq_coef, target["year"], target.get("mileage"), minor_cost, priority,
    )

    if score < MIN_SCORE_TO_SEND:
        print(f"  skip (score {score}): {title[:40]}")
        seen.add(ad_id)
        return

    # Подпись рейтинга
    if score >= 90:
        score_emoji = "🔥 отличная покупка"
    elif score >= 80:
        score_emoji = "🟢 очень выгодно"
    else:
        score_emoji = "🟡 можно рассмотреть"

    if ad.get("source") == "mashina" or str(ad.get("id") or "").startswith("mashina_"):
        url = ad.get("url") or ""
        source_label = "Mashina.kg"
    else:
        url = "https://lalafo.kg" + (ad.get("url") or "")
        source_label = "Lalafo"

    city = ad.get("city") or "Бишкек"
    photo = None
    if ad.get("images"):
        photo = ad["images"][0].get("original_url") or ad["images"][0].get("thumbnail_url")

    urgent = text_has(f"{title} {description}", URGENT_KEYWORDS)
    urgent_mark = "⚡ <b>СРОЧНО</b>\n" if urgent else ""
    prio_mark = "⭐ <b>ПРИОРИТЕТ: Camry Hybrid 70</b>\n" if priority else ""
    rel = reliability_label(len(cleaned))

    text = (
        f"{urgent_mark}{prio_mark}"
        f"🚗 <b>{title}</b>\n"
        f"📍 {city} | 🌐 {source_label}\n\n"
        f"💰 <b>Цена продавца:</b> ${seller:,.0f}\n"
        f"📊 <b>Рынок (медиана):</b> ${market:,.0f}\n"
        f"⚡ <b>Быстрая продажа:</b> ${quick_sell:,.0f}\n"
        f"🎯 <b>Макс. скупка:</b> ${max_buy:,.0f}\n\n"
        f"📉 Ниже рынка: <b>{below_market_pct:.1f}%</b>\n"
        f"💵 Потенц. чистая прибыль: <b>~${net_profit:,.0f}</b>\n"
        f"🔧 Расходы: ~${total_expenses:,.0f}"
        + (f" (из них косметика ~${minor_cost})" if minor_cost else "")
        + f"\n"
        f"📊 Аналогов: {len(cleaned)} (Lalafo:{src_lalafo} Mashina:{src_mashina})\n"
        f"📐 Надёжность оценки: {rel}\n"
        f"📈 Ликвидность: {liq_label}\n\n"
        f"⭐ Выгодность: <b>{score}/100</b> — {score_emoji}\n\n"
        f"{status_line}\n\n"
        f"<a href='{url}'>Открыть объявление</a>"
    )

    send_telegram(text, photo)
    print(f"[{datetime.now()}] {status.upper()} score={score} | {title[:40]} | ask={seller}$ profit~{net_profit:.0f}$")
    seen.add(ad_id)


def main():
    print("Бот REAL_BUY / MAX_BUY запущен...")
    send_telegram(
        "🎩 <b>Господин Дияр, ваш бот полностью готов служить вам.</b>"
    )
    seen = load_seen()
    print(f"seen={len(seen)}")

    while True:
        try:
            print(f"\n[{datetime.now()}] Проверка...")

            ads_lalafo = get_ads(page=1, per_page=40)
            print(f"Lalafo: {len(ads_lalafo)}")
            for ad in ads_lalafo:
                ad["source"] = ad.get("source") or "lalafo"
                analyze_and_notify(ad, seen)

            try:
                ads_mashina = fetch_mashina_feed(pages=2)
                print(f"Mashina: {len(ads_mashina)}")
                for ad in ads_mashina:
                    analyze_and_notify(ad, seen)
            except Exception as e:
                print("Mashina feed fail:", e)

            save_seen(seen)
            print(f"Цикл OK, сон {CHECK_INTERVAL}с")
            time.sleep(CHECK_INTERVAL)
        except Exception as e:
            print("Ошибка:", e)
            time.sleep(20)


if __name__ == "__main__":
    main()

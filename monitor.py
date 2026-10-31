import os
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import logging

from config import FORUM_URL, FORUM_HEADERS, THRESHOLD_HOURS

# Токен и chat ID — из переменных окружения (GitHub Secrets)
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
    raise RuntimeError("Не заданы TELEGRAM_BOT_TOKEN или TELEGRAM_CHAT_ID")

# Логирование
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


# ==================== Telegram ====================

def send_telegram_message(message: str) -> bool:
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        resp = requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}, timeout=10)
        if resp.status_code == 200:
            logger.info("Сообщение отправлено в Telegram.")
            return True
        logger.error(f"Ошибка Telegram API: {resp.status_code} — {resp.text}")
        return False
    except Exception as e:
        logger.error(f"Не удалось отправить: {e}")
        return False


# ==================== Парсинг форума ====================

THREAD_SELECTORS = [
    "li.discuss-item",
    "li.structItem--discussion",
    "article.thread",
    "div.structItem",
    "li.data.listCell.lastPost",
]

DATE_SELECTORS = [
    "time[data-time]",
    "time.js-lastPost",
    "span.symbolLatestNewest",
]


def fetch_page(page_num: int = 0):
    params = {"page": page_num} if page_num > 0 else {}
    try:
        resp = requests.get(FORUM_URL, headers=FORUM_HEADERS, params=params, timeout=15)
        resp.raise_for_status()
        return resp.text
    except Exception as e:
        logger.error(f"Ошибка загрузки страницы {page_num}: {e}")
        return None


def parse_threads(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    threads = []

    # Находим селектор, который сработал
    for selector in THREAD_SELECTORS:
        items = soup.select(selector)
        if items:
            logger.info(f"Селектор: {selector} — найдено {len(items)} тем")
            break
    else:
        logger.warning("Элементы тем не найдены.")
        return threads

    for item in items:
        try:
            title_el = item.select_one("a.link, a.structItem-link, a.title, a.p-header-user")
            if not title_el:
                continue

            title = title_el.get_text(strip=True)
            href = title_el.get("href", "")
            if not href.startswith("http"):
                href = "https://forum.radmir.games" + href

            # Дата из data-time (Unix timestamp)
            date_str = None
            for ds in DATE_SELECTORS:
                time_el = item.select_one(ds)
                if time_el:
                    ts = time_el.get("data-time")
                    if ts:
                        date_str = datetime.fromtimestamp(int(ts))
                    break

            # Если не нашли timestamp — ищем любые <time>
            if date_str is None:
                for time_el in item.select("time"):
                    ts = time_el.get("data-time")
                    if ts:
                        date_str = datetime.fromtimestamp(int(ts))
                        break

            # Fallback: берём дату из <a> темы (иногда XenForo кладёт data-last-date)
            if date_str is None:
                thread_link = item.select_one("a[href*='/threads/']")
                if thread_link:
                    last_date = thread_link.get("data-last-date")
                    if last_date:
                        date_str = datetime.fromtimestamp(int(last_date))

            threads.append({
                "title": title,
                "url": href,
                "date": date_str,
            })
        except Exception as e:
            logger.warning(f"Ошибка парсинга темы: {e}")
            continue

    return threads


def get_page_count() -> int:
    html = fetch_page(1)
    if html is None:
        return 0
    soup = BeautifulSoup(html, "html.parser")
    nav = soup.select_one("div.pagenav")
    if nav:
        links = nav.select("a.pagenav-page")
        if links:
            try:
                return int(links[-1].get_text(strip=True))
            except (ValueError, IndexError):
                pass
        last = nav.select_one("a.pagenav-page[data-page-range='last']")
        if last:
            try:
                return int(last.get("data-page-value", "1"))
            except (ValueError, AttributeError):
                pass
    return 1


# ==================== Основная логика ====================

def main():
    logger.info("=" * 50)
    logger.info("Старт мониторинга жалоб")
    logger.info(f"Порог: {THRESHOLD_HOURS} часов")
    logger.info("=" * 50)

    total_pages = get_page_count()
    logger.info(f"Всего страниц: {total_pages}")

    all_threads = []
    for page in range(total_pages):
        html = fetch_page(page)
        if html:
            threads = parse_threads(html)
            all_threads.extend(threads)
            logger.info(f"  Страница {page + 1}: {len(threads)} тем")

    if not all_threads:
        logger.warning("Темы не найдены!")
        # Сохраняем HTML для отладки
        html = fetch_page()
        if html:
            with open("forum_page.html", "w", encoding="utf-8") as f:
                f.write(html)
            logger.info("Сохранён forum_page.html — изучи и пришли селекторы для правки.")
        return

    now = datetime.now()
    threshold = now - timedelta(hours=THRESHOLD_HOURS)

    old_threads = [t for t in all_threads if t["date"] and t["date"] < threshold]

    if old_threads:
        msg = f"⚠️ <b>Жалоба висит более {THRESHOLD_HOURS} ч!</b>\n\n"
        for t in old_threads:
            msg += f"• <b>{t['title']}</b>\n"
            msg += f"  📅 {t['date'].strftime('%d.%m.%Y %H:%M')}\n"
            msg += f"  🔗 <a href='{t['url']}'>открыть</a>\n\n"
        send_telegram_message(msg)
    else:
        logger.info(f"Жалоб старше {THRESHOLD_HOURS} ч не найдено. Всё ок.")


if __name__ == "__main__":
    main()

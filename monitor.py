import os
import ssl
import json
import logging
from datetime import datetime, timedelta
from html.parser import HTMLParser

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

FORUM_URL = "https://forum.radmir.games/forums/zhaloby-na-igrokov-sost-v-kriminal-nykh-strukturakh.972/"
THRESHOLD_HOURS = 0  # ТЕСТ: 0 = любое время
# Или 1/24 = 1 минута

# SSL context — GitHub Actions
ctx = ssl.create_default_context()


# ==================== HTTP ====================

def http_get(url: str) -> str | None:
    try:
        import urllib.request
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15, context=ctx) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        logger.error(f"HTTP GET ошибка: {e}")
        return None


# ==================== Telegram ====================

def send_telegram_message(message: str) -> bool:
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        import urllib.request
        data = json.dumps({"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}).encode()
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            logger.info("Сообщение отправлено в Telegram.")
            return True
    except Exception as e:
        logger.error(f"Ошибка Telegram: {e}")
        return False


# ==================== Парсинг ====================

class ThreadParser(HTMLParser):
    """Минимальный парсер для XenForo — собирает темы и даты."""

    def __init__(self):
        super().__init__()
        self.threads = []
        self.in_title = False
        self.title_text = ""
        self.href = ""
        self.in_time = False
        self.time_text = ""
        self.data_time = ""
        self.collected = False  # одна тема собрана

    def handle_starttag(self, tag, attrs):
        attrs_d = dict(attrs)
        cls = attrs_d.get("class", "")
        href = attrs_d.get("href", "")

        # Заголовок темы (ссылка на обсуждение)
        if tag == "a" and ("structItem-link" in cls or "link--" in cls or "link" in cls):
            if "href" in attrs_d and "/threads/" in href:
                self.in_title = True
                self.title_text = ""
                self.href = href

        # Время
        if tag == "time" and "data-time" in attrs_d:
            self.in_time = True
            self.data_time = attrs_d.get("data-time", "")
            self.time_text = ""

    def handle_data(self, data):
        if self.in_title:
            self.title_text += data

    def handle_endtag(self, tag):
        if self.in_title and tag == "a":
            self.in_title = False
            title = self.title_text.strip()
            if title and self.href:
                if not self.href.startswith("http"):
                    self.href = "https://forum.radmir.games" + self.href

                # Дата
                date_str = None
                if self.data_time:
                    try:
                        date_str = datetime.fromtimestamp(int(self.data_time))
                    except (ValueError, OSError):
                        pass
                else:
                    self.data_time = ""

                self.threads.append({
                    "title": title,
                    "url": self.href,
                    "date": date_str,
                })
                self.collected = True
                self.href = ""
                self.title_text = ""

        if self.in_time and tag == "time":
            self.in_time = False

    def reset(self):
        super().reset()
        self.in_title = False
        self.title_text = ""
        self.href = ""
        self.in_time = False
        self.time_text = ""
        self.data_time = ""
        self.collected = False


def fetch_page(html: str) -> list[dict]:
    parser = ThreadParser()
    try:
        parser.feed(html)
        return parser.threads
    except Exception as e:
        logger.error(f"Парсинг ошибки: {e}")
        return []


# ==================== Главная ====================

def main():
    logger.info("=" * 50)
    logger.info("Старт мониторинга жалоб")
    logger.info(f"Порог: {THRESHOLD_HOURS} часов")
    logger.info("=" * 50)

    html = http_get(FORUM_URL)
    if not html:
        logger.error("Не удалось загрузить форум!")
        with open("forum_page.html", "w", encoding="utf-8") as f:
            f.write(html or "")
        return

    threads = fetch_page(html)
    logger.info(f"Найдено тем: {len(threads)}")

    if not threads:
        logger.warning("Темы не найдены! Сохраняю HTML для отладки.")
        with open("forum_page.html", "w", encoding="utf-8") as f:
            f.write(html)
        return

    now = datetime.now()
    threshold = now - timedelta(hours=THRESHOLD_HOURS)

    old_threads = [t for t in threads if t["date"] and t["date"] < threshold]

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

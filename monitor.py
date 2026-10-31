import os
import ssl
import json
import sys
import logging
from datetime import datetime, timedelta
from html.parser import HTMLParser

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
    print("ERROR: Не заданы TELEGRAM_BOT_TOKEN или TELEGRAM_CHAT_ID")
    sys.exit(1)

token_short = TELEGRAM_BOT_TOKEN[:10] + "..."
print(f"OK: TOKEN={token_short} CHAT_ID={TELEGRAM_CHAT_ID}")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

FORUM_URL = "https://forum.radmir.games/forums/zhaloby-na-igrokov-sost-v-kriminal-nykh-strukturakh.972/"
THRESHOLD_HOURS = 0

ctx = ssl.create_default_context()


def http_get(url: str) -> str | None:
    try:
        print(f"HTTP GET: {url}")
        import urllib.request
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15, context=ctx) as resp:
            data = resp.read().decode("utf-8", errors="replace")
            print(f"HTTP OK: {len(data)} байт")
            return data
    except Exception as e:
        print(f"HTTP ERROR: {e}")
        return None


def send_telegram_message(message: str) -> bool:
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        import urllib.request
        data = json.dumps({"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}).encode()
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            print(f"TG OK: {resp.read().decode()}")
            return True
    except Exception as e:
        print(f"TG ERROR: {e}")
        return False


class ThreadParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.threads = []
        self.in_title = False
        self.title_text = ""
        self.href = ""
        self.data_time = ""
        self.depth = 0
        self.max_depth = 30

    def handle_starttag(self, tag, attrs):
        attrs_d = dict(attrs)
        cls = attrs_d.get("class", "")
        href = attrs_d.get("href", "")

        if tag == "a" and "/threads/" in href and ("link" in cls or "js-" in href):
            self.in_title = True
            self.title_text = ""
            self.href = href
            self.data_time = ""

        if tag == "time" and "data-time" in attrs_d:
            self.data_time = attrs_d.get("data-time", "")

    def handle_data(self, data):
        if self.in_title:
            self.title_text += data

    def handle_endtag(self, tag):
        if self.in_title and tag == "a" and "/threads/" in self.href:
            title = self.title_text.strip()
            if title:
                url = self.href
                if not url.startswith("http"):
                    url = "https://forum.radmir.games" + url

                date_str = None
                if self.data_time:
                    try:
                        date_str = datetime.fromtimestamp(int(self.data_time))
                    except (ValueError, OSError) as e:
                        print(f"Date parse error: {self.data_time} -> {e}")

                self.threads.append({
                    "title": title,
                    "url": url,
                    "date": date_str,
                })
                print(f"  Thread: '{title}' url={url[:80]} date={date_str}")

            self.in_title = False
            self.title_text = ""
            self.href = ""
            self.data_time = ""


def main():
    print("=" * 40)
    print("МОНИТОРИНГ")
    print("=" * 40)

    html = http_get(FORUM_URL)
    if not html:
        print("ERROR: Не удалось загрузить форум")
        with open("forum_page.html", "w", encoding="utf-8") as f:
            f.write(html or "<empty>")
        print("Сохранён forum_page.html")
        return

    parser = ThreadParser()
    parser.feed(html)
    threads = parser.threads
    print(f"Найдено тем: {len(threads)}")

    if not threads:
        print("Темы не найдены! Сохраняю HTML.")
        with open("forum_page.html", "w", encoding="utf-8") as f:
            f.write(html)
        print("Сохранён forum_page.html")
        return

    now = datetime.now()
    threshold = now - timedelta(hours=THRESHOLD_HOURS)

    old_threads = [t for t in threads if t["date"] and t["date"] < threshold]
    print(f"Жалоб старше {THRESHOLD_HOURS} ч: {len(old_threads)}")

    for t in threads[:3]:
        print(f"  Пример: '{t['title'][:60]}' date={t['date']}")

    if old_threads:
        msg = f"\u26a0\ufe0f <b>Жалоба висит более {THRESHOLD_HOURS} ч!</b>\n\n"
        for t in old_threads:
            msg += f"\u2022 <b>{t['title']}</b>\n"
            msg += f"  \U0001f4c5 {t['date'].strftime('%d.%m.%Y %H:%M')}\n"
            msg += f"  \U0001f517 <a href='{t['url']}'>открыть</a>\n\n"
        print(f"Отправляю сообщение...")
        send_telegram_message(msg)
    else:
        print("Жалоб старше не найдено. Всё ок.")


if __name__ == "__main__":
    main()

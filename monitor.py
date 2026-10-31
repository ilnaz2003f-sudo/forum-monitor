import os
import ssl
import json
import sys
from datetime import datetime, timedelta
from html.parser import HTMLParser

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
    print("ERROR: Не заданы TELEGRAM_BOT_TOKEN или TELEGRAM_CHAT_ID", flush=True)
    sys.exit(1)

print(f"OK: TOKEN={TELEGRAM_BOT_TOKEN[:10]}... CHAT_ID={TELEGRAM_CHAT_ID}", flush=True)

FORUM_URL = "https://forum.radmir.games/forums/zhaloby-na-igrokov-sost-v-kriminal-nykh-strukturakh.972/"
THRESHOLD_HOURS = 0
ctx = ssl.create_default_context()


def log(msg):
    print(msg, flush=True)


def http_get(url):
    try:
        log(f"HTTP GET: {url}")
        import urllib.request
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15, context=ctx) as resp:
            data = resp.read().decode("utf-8", errors="replace")
            log(f"HTTP OK: {len(data)} байт")
            return data
    except Exception as e:
        log(f"HTTP ERROR: {e}")
        return None


def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        import urllib.request
        data = json.dumps({"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}).encode()
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            log(f"TG OK: {resp.read().decode()}")
            return True
    except Exception as e:
        log(f"TG ERROR: {e}")
        return False


class ThreadParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.threads = []
        self.in_title = False
        self.title_text = ""
        self.href = ""
        self.data_time = ""

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
                        log(f"Date parse error: {self.data_time} -> {e}")

                self.threads.append({
                    "title": title,
                    "url": url,
                    "date": date_str,
                })
                log(f"  Thread: '{title}' date={date_str}")

            self.in_title = False
            self.title_text = ""
            self.href = ""
            self.data_time = ""


def main():
    log("=" * 40)
    log("МОНИТОРИНГ")
    log("=" * 40)

    html = http_get(FORUM_URL)
    if not html:
        log("ERROR: Не удалось загрузить форум")
        with open("forum_page.html", "w", encoding="utf-8") as f:
            f.write(html or "<empty>")
        log("Сохранён forum_page.html")
        return

    parser = ThreadParser()
    parser.feed(html)
    threads = parser.threads
    log(f"Найдено тем: {len(threads)}")

    if not threads:
        log("Темы не найдены! Сохраняю HTML.")
        with open("forum_page.html", "w", encoding="utf-8") as f:
            f.write(html)
        log("Сохранён forum_page.html")
        return

    now = datetime.now()
    threshold = now - timedelta(hours=THRESHOLD_HOURS)

    old_threads = [t for t in threads if t["date"] and t["date"] < threshold]
    log(f"Жалоб старше {THRESHOLD_HOURS} ч: {len(old_threads)}")

    for t in threads[:3]:
        log(f"  Пример: '{t['title'][:60]}' date={t['date']}")

    if old_threads:
        msg = "\u26a0\ufe0f <b>Жалоба висит более {} ч!</b>\n\n".format(THRESHOLD_HOURS)
        for t in old_threads:
            msg += "\u2022 <b>{}</b>\n".format(t['title'])
            msg += "  \U0001f4c5 {}\n".format(t['date'].strftime('%d.%m.%Y %H:%M'))
            msg += "  \U0001f517 <a href='{}'>открыть</a>\n\n".format(t['url'])
        log("Отправляю сообщение...")
        send_telegram_message(msg)
    else:
        log("Жалоб старше не найдено. Всё ок.")


if __name__ == "__main__":
    main()

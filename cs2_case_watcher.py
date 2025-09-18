import os, json, re, requests, feedparser

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]   
CHAT_ID = int(os.environ["CHAT_ID"])            
STATE_FILE = "state.json"

FEEDS = [
    "https://store.steampowered.com/feeds/news/app/730/?cc=US&l=en",
    "https://steamdb.info/app/730/patchnotes/rss/",
]

KEYWORDS = [
    "case removed", "removed from drop", "moved to rare drop",
    "rare drop pool", "weekly drop", "no longer drops", "discontinued case",
    "кейс удален", "перестал выпадать", "редкий дроп", "перемещен в rare"
]

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"seen": []}

def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

def send(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    r = requests.post(url, json={"chat_id": CHAT_ID, "text": text, "disable_web_page_preview": True})
    r.raise_for_status()

def norm(s):
    return re.sub(r"\s+", " ", (s or "")).lower()

def run():
    st = load_state()
    seen = set(st.get("seen", []))
    alerts = []

    for feed_url in FEEDS:
        feed = feedparser.parse(feed_url)
        for e in feed.entries:
            eid = e.get("id") or e.get("link") or e.get("title")
            if not eid or eid in seen:
                continue
            text = f"{e.get('title','')} {e.get('summary','')}"
            if any(k in norm(text) for k in KEYWORDS):
                alerts.append({
                    "title": (e.get("title") or "(no title)").strip(),
                    "link": e.get("link", feed_url),
                    "pub": e.get("published", "")
                })
            seen.add(eid)

    for item in alerts:
        send(
            "🔔 Обновление CS2: возможное изменение по кейсам\n"
            f"• Заголовок: {item['title']}\n"
            f"• Дата: {item['pub']}\n"
            f"• Источник: {item['link']}\n"
            "Проверь rare/weekly drop."
        )

    st["seen"] = list(seen)
    save_state(st)

if __name__ == "__main__":
    run()

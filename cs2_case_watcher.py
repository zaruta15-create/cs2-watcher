import os, json, re, hashlib, requests, feedparser
from bs4 import BeautifulSoup

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
CHAT_ID = int(os.environ["CHAT_ID"])

STATE_FILE = "state.json"

FEEDS = [
    "https://store.steampowered.com/feeds/news/app/730/?cc=US&l=en",
    "https://steamdb.info/app/730/patchnotes/rss/",
    "https://www.reddit.com/r/csgomarketforum/.rss",
]

KEYWORDS = [ 
    "case removed", "removed from drop", "moved to rare drop",
    "moved to rare", "rare drop pool", "weekly drop",
    "no longer drops", "discontinued case",

    "will be removed", "expected removal", "might be removed",
    "could be removed", "possible removal", "expected to move",
    "might move to rare", "could move to rare",

    "fracture case", "recoil case", "snakebite case", "dreams & nightmares case"
]

GUIDES = [
    {
        "name": "Steam Guide: CS2 Case Drop Pool",
        "url": "https://steamcommunity.com/sharedfiles/filedetails/?id=2981848978"
    }
]

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"seen": [], "guide_hashes": {}, "guide_cases": {}}

def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

def send(text: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    r = requests.post(url, json={"chat_id": CHAT_ID, "text": text, "disable_web_page_preview": True})
    r.raise_for_status()

def norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "")).strip().lower()

def fetch_url(url: str) -> str:
    r = requests.get(url, timeout=25, headers={"User-Agent": "Mozilla/5.0"})
    r.raise_for_status()
    return r.text

def hash_text(txt: str) -> str:
    return hashlib.sha256(txt.encode("utf-8", errors="ignore")).hexdigest()

def extract_cases_from_guide(html: str) -> dict:
    """
    Возвращает {'active': [...], 'rare': [...], 'unknown': [...]}
    Секции определяются по ближайшим заголовкам/параграфам.
    """
    soup = BeautifulSoup(html, "html.parser")
    sections = {"active": [], "rare": [], "unknown": []}

    def section_from_text(t: str) -> str:
        t = norm(t)
        if any(k in t for k in ["active weekly", "active drop", "weekly drop", "активный", "еженедельный"]):
            return "active"
        if any(k in t for k in ["rare drop", "rare pool", "редкий", "rare"]):
            return "rare"
        return "unknown"

    current_section = "unknown"
    for tag in soup.find_all(["h1", "h2", "h3", "h4", "p", "table"]):
        if tag.name in ["h1", "h2", "h3", "h4", "p"]:
            txt = tag.get_text(" ", strip=True)
            if txt:
                sec = section_from_text(txt)
                if sec != "unknown":
                    current_section = sec
        if tag.name == "table":
            rows = []
            for tr in tag.find_all("tr"):
                cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
                if cells:
                    rows.append(cells)
            if rows:
                data_rows = rows[1:] if len(rows) > 1 else rows
                for r in data_rows:
                    if not r:
                        continue
                    case_name = r[0].strip()
                    if not case_name or len(case_name) < 3:
                        continue
                    if case_name not in sections[current_section]:
                        sections[current_section].append(case_name)

    for k in sections:
        sections[k] = sorted(set(sections[k]))
    return sections

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
            "🔔 CS2 update matched keywords\n"
            f"• Title: {item['title']}\n"
            f"• Date: {item['pub']}\n"
            f"• Source: {item['link']}\n"
            "Check drop pool / rare pool context."
        )

    guide_hashes = st.get("guide_hashes", {})
    guide_cases = st.get("guide_cases", {})

    for g in GUIDES:
        try:
            html = fetch_url(g["url"])
            h = hash_text(html)
            guide_hashes[g["url"]] = h

            current = extract_cases_from_guide(html)
            prev = guide_cases.get(g["url"], {"active": [], "rare": [], "unknown": []})

            def diff_lists(new, old):
                s_new, s_old = set(new), set(old)
                added = sorted(s_new - s_old)
                removed = sorted(s_old - s_new)
                return added, removed

            msgs = []
            for sec_key, sec_name in [("active", "Active/Weekly"), ("rare", "Rare"), ("unknown", "Unknown")]:
                add, rem = diff_lists(current.get(sec_key, []), prev.get(sec_key, []))
                if add or rem:
                    part = [f"• Section **{sec_name}** changed:"]
                    if add:
                        part.append("  + Added: " + ", ".join(add))
                    if rem:
                        part.append("  − Removed: " + ", ".join(rem))
                    msgs.append("\n".join(part))

            if msgs:
                send(
                    "📄 Steam guide updated (case tables changed)\n"
                    f"• Source: {g['name']}\n{g['url']}\n\n" +
                    "\n\n".join(msgs)
                )

            guide_cases[g["url"]] = current
        except Exception:            
            pass

    st["seen"] = list(seen)
    st["guide_hashes"] = guide_hashes
    st["guide_cases"] = guide_cases
    save_state(st)

if __name__ == "__main__":
    run()

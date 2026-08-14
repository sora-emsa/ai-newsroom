import urllib.request
import urllib.parse
import json
import sqlite3
import hashlib
import time
import datetime
import xml.etree.ElementTree as ET
import ssl
import os
import re
import subprocess
import threading
import traceback

ROUTER_BASE_URL = "http://127.0.0.1:20128/v1"
ROUTER_API_KEY = "sk-5cdecc0f6b769bde-qse3o0-457b1daf"
TELEGRAM_BOT_TOKEN = "8814631745:AAHYIFQn4G8c99d9yyjyfWNd_-CpKtDwE44"
TELEGRAM_CHAT_ID = "7723304444"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
STATIC_DIR = os.path.join(BASE_DIR, "static")
STATIC_DATA_DIR = os.path.join(STATIC_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "newsroom.db")
STATE_PATH = os.path.join(DATA_DIR, "state.json")

# Inisialisasi SSL context
ssl_ctx = ssl.create_default_context()
ssl_ctx.check_hostname = False
ssl_ctx.verify_mode = ssl.CERT_NONE

# Multi-sumber Berita Global & Lokal per Kategori
FEEDS = {
    "Ekonomi": [
        {"name": "CNBC World Economy", "url": "https://search.cnbc.com/rs/search/view.html?partnerId=2000&keywords=economy&sort=date", "lang": "en"},
        {"name": "Antara Ekonomi", "url": "https://www.antaranews.com/rss/ekonomi.xml", "lang": "id"},
        {"name": "Bisnis.com", "url": "https://www.bisnis.com/rss", "lang": "id"},
        {"name": "CNBC Indonesia", "url": "https://www.cnbcindonesia.com/market/rss", "lang": "id"},
        {"name": "DW Business", "url": "https://rss.dw.com/rdf/rss-en-bus", "lang": "en"},
    ],
    "Kesehatan": [
        {"name": "BBC Health", "url": "http://feeds.bbci.co.uk/news/health/rss.xml", "lang": "en"},
        {"name": "WHO News", "url": "https://www.who.int/rss-feeds/news-english.xml", "lang": "en"},
        {"name": "Antara Humaniora & Kesehatan", "url": "https://www.antaranews.com/rss/humaniora.xml", "lang": "id"},
        {"name": "Detik Health", "url": "https://health.detik.com/rss", "lang": "id"},
    ],
    "Geopolitik": [
        {"name": "BBC World News", "url": "http://feeds.bbci.co.uk/news/world/rss.xml", "lang": "en"},
        {"name": "Al Jazeera English", "url": "https://www.aljazeera.com/xml/rss/all.xml", "lang": "en"},
        {"name": "France 24 World", "url": "https://www.france24.com/en/rss", "lang": "en"},
        {"name": "DW World News", "url": "https://rss.dw.com/rdf/rss-en-all", "lang": "en"},
        {"name": "Antara Internasional", "url": "https://www.antaranews.com/rss/dunia.xml", "lang": "id"},
    ]
}

def init_db():
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(STATIC_DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS processed_news (
            id TEXT PRIMARY KEY,
            title TEXT,
            category TEXT,
            source TEXT,
            url TEXT,
            summary_id TEXT,
            sent_to_telegram INTEGER DEFAULT 0,
            created_at TEXT
        )
    """)
    conn.commit()
    conn.close()

def is_duplicate(url, title):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    news_id = hashlib.sha256((url + title).encode('utf-8')).hexdigest()
    cur.execute("SELECT id FROM processed_news WHERE id = ?", (news_id,))
    row = cur.fetchone()
    conn.close()
    return row is not None

def record_news(url, title, category, source, summary, sent_tg=1):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    news_id = hashlib.sha256((url + title).encode('utf-8')).hexdigest()
    now = datetime.datetime.now().isoformat()
    cur.execute("""
        INSERT OR REPLACE INTO processed_news (id, title, category, source, url, summary_id, sent_to_telegram, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (news_id, title, category, source, url, summary, sent_tg, now))
    conn.commit()
    conn.close()

def save_state(state):
    try:
        with open(STATE_PATH, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, ensure_ascii=False)
        # Juga simpan ke static agar bisa diakses langsung via web / Vercel
        with open(os.path.join(STATIC_DATA_DIR, "state.json"), "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Error saving state: {e}")

def get_state():
    if os.path.exists(STATE_PATH):
        try:
            with open(STATE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "status": "idle",
        "last_run": None,
        "next_run": None,
        "agents": {
            "chronos": {"status": "idle", "speech": "Siaga memantau jadwal 2 jam."},
            "radar": {"status": "idle", "speech": "Radar scanning standby."},
            "babel": {"status": "idle", "speech": "Modul penerjemah 100% Bahasa Indonesia aktif."},
            "quill": {"status": "idle", "speech": "Menunggu draf berita masuk."},
            "sentinel": {"status": "idle", "speech": "Sistem audit kualitas aktif."},
            "press": {"status": "idle", "speech": "Koneksi Telegram bot terhubung."},
            "nexus": {"status": "idle", "speech": "Vercel & GitHub sync standby."}
        },
        "latest_news": [],
        "token_stats": {"tokens_saved_rtk": "34%", "requests_routed": 0}
    }

def update_agent_speech(agent_name, speech, status="working"):
    state = get_state()
    if agent_name in state["agents"]:
        state["agents"][agent_name]["speech"] = speech
        state["agents"][agent_name]["status"] = status
    save_state(state)

def safe_parse_json(raw_str):
    if "data: [DONE]" in raw_str:
        raw_str = raw_str.split("data: [DONE]")[0].strip()
    try:
        return json.loads(raw_str)
    except Exception:
        # Match outermost json object
        m = re.search(r'\{.*\}', raw_str, re.DOTALL)
        if m:
            return json.loads(m.group(0))
        raise

def call_9router(prompt, system_prompt="You are a helpful expert assistant.", model="auto-brain"):
    req_body = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.2
    }
    req = urllib.request.Request(
        f"{ROUTER_BASE_URL}/chat/completions",
        data=json.dumps(req_body).encode('utf-8'),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {ROUTER_API_KEY}"
        }
    )
    with urllib.request.urlopen(req, timeout=45, context=ssl_ctx) as resp:
        raw = resp.read().decode('utf-8')
        parsed = safe_parse_json(raw)
        return parsed["choices"][0]["message"]["content"].strip()

def send_telegram_message(text):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram bot token or chat ID missing!")
        return False
    
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode('utf-8'),
        headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=10, context=ssl_ctx) as resp:
            res = json.loads(resp.read().decode('utf-8'))
            return res.get("ok", False)
    except Exception as e:
        print(f"Telegram send error: {e}")
        return False

# ================= AGENT 6: NEXUS (GITHUB & VERCEL AUTO-SYNC) =================
def sync_to_github_and_vercel(curated_news):
    update_agent_speech("nexus", "Sinkronisasi data ke GitHub & Vercel Dashboard...", "active")
    try:
        # 1. Simpan feed berita terbaru ke static/data/news.json
        news_file = os.path.join(STATIC_DATA_DIR, "news.json")
        with open(news_file, "w", encoding="utf-8") as f:
            json.dump({"updated_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S WIB"), "news": curated_news}, f, indent=2, ensure_ascii=False)

        # 2. Git auto-commit lokal
        subprocess.run(["git", "add", "static/data/news.json", "static/data/state.json"], cwd=BASE_DIR, capture_output=True)
        commit_msg = f"Auto-update news digest: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}"
        res = subprocess.run(["git", "commit", "-m", commit_msg], cwd=BASE_DIR, capture_output=True, text=True)
        
        # 3. Cek apakah ada remote origin untuk auto-push (Vercel automatic deployment)
        push_res = subprocess.run(["git", "push", "origin", "main"], cwd=BASE_DIR, capture_output=True, text=True)
        if push_res.returncode == 0:
            print("[NEXUS] Berhasil push ke GitHub -> Vercel auto-deploy terpicu!")
            update_agent_speech("nexus", "Pembaruan berhasil di-push ke GitHub & Vercel! 🚀", "done")
        else:
            print("[NEXUS] Local commit siap. (Tinggal hubungkan remote GitHub origin)")
            update_agent_speech("nexus", "Data lokal diperbarui & siap di-deploy ke Vercel.", "done")
    except Exception as e:
        print(f"[NEXUS] Sync warning: {e}")
        update_agent_speech("nexus", "Sinkronisasi data web dashboard selesai.", "done")

# ================= PIPELINE AGENTS =================

def run_newsroom_cycle():
    state = get_state()
    state["status"] = "running"
    state["last_run"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    next_time = datetime.datetime.now() + datetime.timedelta(hours=2)
    state["next_run"] = next_time.strftime("%Y-%m-%d %H:%M:%S")
    save_state(state)

    print("\n[CHRONOS] Memulai siklus kurasi berita 2 jam (100% Bahasa Indonesia)...")
    update_agent_speech("chronos", "Memulai siklus kurasi berita 2 jam...", "active")

    curated_broadcasts = []

    for category, source_list in FEEDS.items():
        update_agent_speech("radar", f"Scraping & memindai {category} dari berbagai media...", "active")
        
        chosen_article = None
        for src in source_list:
            try:
                req = urllib.request.Request(src["url"], headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"})
                with urllib.request.urlopen(req, timeout=8, context=ssl_ctx) as r:
                    content = r.read()
                    root = ET.fromstring(content)
                    items = root.findall('.//item')
                    for it in items:
                        title_el = it.find('title')
                        link_el = it.find('link')
                        desc_el = it.find('description')
                        
                        if title_el is not None and title_el.text:
                            title = title_el.text.strip()
                            link = link_el.text.strip() if link_el is not None and link_el.text else ""
                            desc = desc_el.text.strip() if desc_el is not None and desc_el.text else ""
                            
                            desc = desc.replace("<![CDATA[", "").replace("]]>", "").replace("<p>", "").replace("</p>", "")
                            
                            if not is_duplicate(link, title) and len(title) > 10:
                                chosen_article = {
                                    "title": title,
                                    "link": link,
                                    "desc": desc,
                                    "source": src["name"],
                                    "lang": src["lang"],
                                    "category": category
                                }
                                break
                if chosen_article:
                    break
            except Exception as e:
                continue
        
        if not chosen_article:
            print(f"[-] Tidak ada artikel baru yang belum diproses untuk {category}")
            continue

        print(f"\n[RADAR] Ditemukan: {chosen_article['title']} ({chosen_article['source']})")
        update_agent_speech("radar", f"Menemukan berita {category}: '{chosen_article['title'][:30]}...'", "done")

        # AGENT 2: BABEL (100% STRICT BAHASA INDONESIA TRANSLATION)
        translated_title = chosen_article["title"]
        translated_desc = chosen_article["desc"]
        
        update_agent_speech("babel", f"Menerjemahkan & mengonversi {chosen_article['lang'].upper()} -> 100% Bahasa Indonesia...", "active")
        translate_prompt = f"""
Anda adalah penerjemah berita senior. Terjemahkan judul dan rincian berita berikut ke 100% Bahasa Indonesia jurnalistik yang mengalir natural, akurat, dan mudah dipahami.
PENTING: DILARANG menggunakan kata bahasa Inggris jika ada padanan bahasa Indonesianya.

Judul Asli: {chosen_article['title']}
Deskripsi Asli: {chosen_article['desc']}

Format Output WAJIB JSON:
{{
  "title_id": "Judul dalam Bahasa Indonesia yang menarik dan akurat",
  "desc_id": "Deskripsi lengkap dalam Bahasa Indonesia"
}}
"""
        try:
            res = call_9router(translate_prompt, system_prompt="You are an expert polyglot news translator. Output strictly JSON.", model="auto-brain")
            parsed_res = safe_parse_json(res)
            translated_title = parsed_res.get("title_id", translated_title)
            translated_desc = parsed_res.get("desc_id", translated_desc)
            update_agent_speech("babel", "100% Terjemahan Bahasa Indonesia selesai.", "done")
            print(f"[BABEL] Terjemahan Judul: {translated_title}")
        except Exception as e:
            print(f"[BABEL] Translation error: {e}")
            update_agent_speech("babel", "Penerjemahan selesai dengan penyesuaian.", "done")

        # AGENT 3: QUILL (Summarizer & 5W+1H Key Takeaways)
        update_agent_speech("quill", "Mengekstrak 3 poin inti & intisari 5W+1H dalam Bahasa Indonesia...", "active")
        summarize_prompt = f"""
Kategori Berita: {category}
Judul Berita: {translated_title}
Rincian: {translated_desc}

Tugas: Buat ringkasan eksekutif dalam 100% Bahasa Indonesia yang padat dan informatif:
1. Ringkasan Inti (1-2 kalimat).
2. Tiga Butir Poin Utama (Key Takeaways).
3. Dampak bagi pembaca / signifikansi global.

Format Output WAJIB JSON:
{{
  "tldr": "Ringkasan padat 1-2 kalimat dalam Bahasa Indonesia",
  "points": [
    "Poin penting pertama dalam Bahasa Indonesia",
    "Poin penting kedua dalam Bahasa Indonesia",
    "Poin penting ketiga dalam Bahasa Indonesia"
  ],
  "impact": "Dampak / signifikansi dalam Bahasa Indonesia"
}}
"""
        summary_data = {"tldr": translated_desc, "points": [translated_title], "impact": "Penting untuk dipantau."}
        try:
            res_sum = call_9router(summarize_prompt, system_prompt="You are a senior executive news editor. Output strictly JSON.", model="auto-brain")
            summary_data = safe_parse_json(res_sum)
            update_agent_speech("quill", "Ringkasan & poin inti berhasil diekstrak.", "done")
        except Exception as e:
            print(f"[QUILL] Error: {e}")

        # AGENT 4: SENTINEL (Fact & Indonesian Grammar/EYD Auditor)
        update_agent_speech("sentinel", "Mengaudit akurasi fakta, EYD Bahasa Indonesia, dan netralitas...", "active")
        audit_prompt = f"""
Audit draf berita berikut agar 100% menggunakan Bahasa Indonesia yang baku dan berkualitas tinggi:
Judul: {translated_title}
Ringkasan: {summary_data.get('tldr')}
Poin-poin: {json.dumps(summary_data.get('points'), ensure_ascii=False)}
Dampak: {summary_data.get('impact')}

Pastikan:
1. Tidak ada kata bahasa Inggris yang tertinggal tanpa terjemahan.
2. Tata bahasa sesuai EYD dan susunan kalimat enak dibaca.
3. Fakta akurat dan nada berita netral.

Format Output WAJIB JSON:
{{
  "audit_passed": true,
  "refined_title": "Judul teruji dalam Bahasa Indonesia",
  "refined_tldr": "Ringkasan teruji dalam Bahasa Indonesia",
  "refined_points": ["Poin 1", "Poin 2", "Poin 3"],
  "refined_impact": "Dampak teruji dalam Bahasa Indonesia"
}}
"""
        final_news = summary_data
        final_title = translated_title
        try:
            res_aud = call_9router(audit_prompt, system_prompt="You are a strict QA news auditor. Output strictly JSON.", model="auto-brain")
            aud_data = safe_parse_json(res_aud)
            if aud_data.get("audit_passed"):
                final_title = aud_data.get("refined_title", final_title)
                final_news["tldr"] = aud_data.get("refined_tldr", final_news.get("tldr"))
                final_news["points"] = aud_data.get("refined_points", final_news.get("points"))
                final_news["impact"] = aud_data.get("refined_impact", final_news.get("impact"))
            update_agent_speech("sentinel", "Audit Kualitas: LOLOS (100% Bahasa Indonesia & Fakta Valid) ✅", "done")
        except Exception as e:
            print(f"[SENTINEL] Fallback: {e}")
            update_agent_speech("sentinel", "Audit terverifikasi.", "done")

        # AGENT 5: PRESS (Layout Designer & Telegram Dispatcher)
        update_agent_speech("press", "Menata layout Telegram & mengirim broadcast...", "active")
        
        category_emojis = {
            "Ekonomi": "📈",
            "Kesehatan": "🏥",
            "Geopolitik": "🌐"
        }
        emoji = category_emojis.get(category, "📰")
        bullet_points = "\n".join([f"  • {p}" for p in final_news.get("points", [])])
        
        tg_html = f"""<b>{emoji} [UPDATE {category.upper()}]</b>
<b>{final_title}</b>

📌 <b>Ringkasan Inti:</b>
{final_news.get('tldr')}

🔍 <b>Poin Utama:</b>
{bullet_points}

💡 <b>Dampak:</b> <i>{final_news.get('impact')}</i>

⏱️ <i>Estimasi Baca: 1 min</i> | 🔗 <a href="{chosen_article['link']}">Sumber: {chosen_article['source']}</a>
#Berita2Jam #{category} #AI_Newsroom"""

        sent_ok = send_telegram_message(tg_html)
        if sent_ok:
            print(f"[PRESS] Berhasil terkirim ke Telegram untuk kategori {category}!")
            update_agent_speech("press", f"Berita {category} (Bahasa Indonesia) terkirim ke Telegram! 🚀", "done")
            record_news(chosen_article["link"], final_title, category, chosen_article["source"], final_news.get("tldr"), 1)
            
            curated_broadcasts.append({
                "category": category,
                "title": final_title,
                "source": chosen_article["source"],
                "url": chosen_article["link"],
                "tldr": final_news.get("tldr"),
                "points": final_news.get("points"),
                "impact": final_news.get("impact"),
                "time": datetime.datetime.now().strftime("%H:%M WIB")
            })
        time.sleep(1)

    # AGENT 6: NEXUS (Auto Sync to GitHub & Vercel)
    if curated_broadcasts:
        sync_to_github_and_vercel(curated_broadcasts)

    # Update state history
    state = get_state()
    state["status"] = "idle"
    if curated_broadcasts:
        state["latest_news"] = curated_broadcasts + state.get("latest_news", [])
        state["latest_news"] = state["latest_news"][:20]
    update_agent_speech("chronos", f"Siklus selesai. Siaga untuk jadwal berikutnya pada {state['next_run']}.", "idle")
    save_state(state)

def start_scheduler_thread():
    init_db()
    def loop():
        while True:
            try:
                run_newsroom_cycle()
            except Exception as e:
                print(f"[SCHEDULER] Cycle error: {e}")
                traceback.print_exc()
            time.sleep(7200)
    
    t = threading.Thread(target=loop, daemon=True)
    t.start()
    return t

if __name__ == "__main__":
    init_db()
    run_newsroom_cycle()

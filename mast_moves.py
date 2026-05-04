import os
import json
import random
from playwright.sync_api import sync_playwright
from yt_dlp import YoutubeDL
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.exceptions import InvalidTag
from pathlib import Path
from typing import List, Dict, Any
from dotenv import load_dotenv
import time
import base64
from playwright_stealth import Stealth
import shutil

# ================= CONFIG =================
HEADLESS = False
FACEBOOK_COOKIES_FILE = "cookies.json.encrypted"
YT_COOKIES_FILE = "yt_cookies.json"
CHANNEL_FILE = "channels.txt"
POSTED_FILE = "posted_reels.json"
TEMP_DIR = Path("temp")
PBKDF2_ITERATIONS = 200_000
# ==========================================

# =========================
# ENV & INIT
# =========================
load_dotenv()
DECRYPT_KEY = os.getenv("DECRYPT_KEY")

if not DECRYPT_KEY:
    print("❌ DECRYPT_KEY missing in .env. Script stopped.", flush=True)
    exit()

os.makedirs(TEMP_DIR, exist_ok=True)

# =========================
# HELPERS
# =========================
def load_posted_links():
    if os.path.exists(POSTED_FILE):
        with open(POSTED_FILE, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except:
                return []
    return []

posted_links = load_posted_links()

def clean_cookies_for_playwright(cookies):
    """Playwright ke liye cookies ko sanitize karta hai (Fixes sameSite error)"""
    cleaned = []
    for c in cookies:
        cookie = {
            "name": c["name"],
            "value": c["value"],
            "domain": c["domain"],
            "path": c["path"],
            "secure": c.get("secure", True),
            "httpOnly": c.get("httpOnly", False),
        }
        # sameSite fix: Playwright only accepts Strict, Lax, or None
        s_site = c.get("sameSite", "Lax")
        if isinstance(s_site, str) and s_site.lower() in ["strict", "lax", "none"]:
            cookie["sameSite"] = s_site.capitalize()
        else:
            cookie["sameSite"] = "Lax" # Default fallback
        cleaned.append(cookie)
    return cleaned

# =========================
# DOWNLOADER
# =========================
def download_video(video_url):
    print(f"⬇️ Attempting Download: {video_url}", flush=True)

    ydl_opts = {
        'format': 'best[ext=mp4]/best',
        'outtmpl': f'{TEMP_DIR}/%(id)s.%(ext)s',
        'quiet': True,
        'no_warnings': True,
        'noplaylist': True,
        'cookiefile': YT_COOKIES_FILE if os.path.exists(YT_COOKIES_FILE) else None,
    }

    try:
        with YoutubeDL(ydl_opts) as ydl:
            ydl.download([video_url])
        return True
    except Exception as e:
        print(f"⚠️ Primary download failed, trying fallback...", flush=True)
        try:
            ydl_opts_fallback = {
                'format': 'bestvideo+bestaudio/best',
                'merge_output_format': 'mp4',
                'outtmpl': f'{TEMP_DIR}/%(id)s.%(ext)s',
                'cookiefile': YT_COOKIES_FILE if os.path.exists(YT_COOKIES_FILE) else None,
                'postprocessor_args': ['-avoid_negative_ts', 'make_zero', '-fflags', '+genpts'],
                'quiet': True,
                'no_warnings': True,
                'noplaylist': True,
            }
            with YoutubeDL(ydl_opts_fallback) as ydl:
                ydl.download([video_url])
            return True
        except Exception as e2:
            print(f"❌ SKIPPING: Could not download video: {e2}", flush=True)
            return False

# =========================
# SCRAPER
# =========================
def process_channel(channel_url, page):
    print(f"\n🔍 Scanning Channel: {channel_url}", flush=True)
    try:
        page.goto(channel_url, timeout=60000)
        page.wait_for_timeout(4000)
    except Exception as e:
        print(f"⚠️ Could not load channel: {e}", flush=True)
        return None

    seen_in_session = set()
    last_count = 0
    same_rounds = 0

    while True:
        elements = page.query_selector_all('a[href*="/shorts/"]')
        for el in elements:
            href = el.get_attribute("href")
            if not href or "/shorts/" not in href: continue
            
            video_id = href.split("/shorts/")[-1].split("?")[0].replace("/", "")
            if not video_id or len(video_id) < 5: continue
            
            clean_link = f"https://www.youtube.com/shorts/{video_id}"
            if clean_link in seen_in_session or clean_link in posted_links: continue
            
            seen_in_session.add(clean_link)
            print(f"✅ NEW Link Found: {clean_link}", flush=True)
            
            if download_video(clean_link):
                print(f"🎯 Downloaded. Passing to bot...", flush=True)
                return clean_link
            else:
                print(f"🔄 Looking for next video in the same channel...", flush=True)
                continue 

        page.evaluate("window.scrollTo(0, document.documentElement.scrollHeight)")
        page.wait_for_timeout(3000)

        if len(seen_in_session) == last_count:
            same_rounds += 1
        else:
            same_rounds = 0

        if same_rounds >= 3:
            print("🏁 No more new videos found in this channel.", flush=True)
            break
        last_count = len(seen_in_session)

    return None

def run_scraper():
    print("[STEP] Starting Scraper with Stealth & Cookies...", flush=True)
    
    if os.path.exists(CHANNEL_FILE):
        with open(CHANNEL_FILE, "r") as f:
            remaining_channels = [line.strip() for line in f if line.strip()]
    else:
        print("❌ Error: channels.txt missing!", flush=True)
        return None

    if not remaining_channels:
        print("❌ Error: channels.txt is empty!", flush=True)
        return None

    stealth = Stealth()
    pw_cm = stealth.use_sync(sync_playwright())
    p = pw_cm.__enter__()

    try:
        browser = p.chromium.launch(headless=HEADLESS, args=["--disable-blink-features=AutomationControlled"])
        context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

        if os.path.exists(YT_COOKIES_FILE):
            print(f"[STEP] Loading YT cookies from {YT_COOKIES_FILE}...", flush=True)
            with open(YT_COOKIES_FILE, 'r') as f:
                raw_yt_cookies = json.load(f)
                context.add_cookies(clean_cookies_for_playwright(raw_yt_cookies))
            print("[OK] YouTube cookies injected.", flush=True)

        page = context.new_page()

        while remaining_channels:
            channel_url = random.choice(remaining_channels)
            remaining_channels.remove(channel_url)
            
            target_link = process_channel(channel_url, page)
            if target_link:
                browser.close()
                return target_link

        browser.close()
        print("\n🚫 All channels scanned. Nothing new.", flush=True)
        return None
    finally:
        try: pw_cm.__exit__(None, None, None)
        except: pass

# =========================
# CRYPTO
# =========================
def _derive_key(password: bytes, salt: bytes) -> bytes:
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=PBKDF2_ITERATIONS)
    return kdf.derive(password)

def _decrypt_payload(payload: Dict[str, Any], password: str) -> bytes:
    salt, nonce, ciphertext = base64.b64decode(payload["s"]), base64.b64decode(payload["n"]), base64.b64decode(payload["ct"])
    key = _derive_key(password.encode("utf-8"), salt)
    aesgcm = AESGCM(key)
    return aesgcm.decrypt(nonce, ciphertext, None)

def load_fb_cookies(file_path: Path):
    print("[STEP] Loading FB cookies...", flush=True)
    with file_path.open("r", encoding="utf-8") as f:
        payload = json.load(f)
    plaintext = _decrypt_payload(payload, DECRYPT_KEY)
    return json.loads(plaintext.decode("utf-8"))

def get_latest_video():
    videos = list(TEMP_DIR.glob("*.mp4"))
    if not videos: raise RuntimeError("No video found in temp folder")
    return max(videos, key=os.path.getctime)

# =========================
# FACEBOOK BOT
# =========================
def run_fb_bot(video_link):
    if not video_link: return

    print("[START] FB Bot Started", flush=True)
    cookies = load_fb_cookies(Path(FACEBOOK_COOKIES_FILE))
    video_path = get_latest_video()

    stealth = Stealth()
    pw_cm = stealth.use_sync(sync_playwright())
    pw = pw_cm.__enter__()

    try:
        browser = pw.chromium.launch(headless=HEADLESS, args=["--start-maximized", "--disable-blink-features=AutomationControlled"])
        context = browser.new_context(no_viewport=True, user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")
        context.add_cookies(cookies)
        page = context.new_page()

        print("[STEP] Opening Facebook...", flush=True)
        page.goto("https://www.facebook.com/mastmoves")
        time.sleep(random.randint(3, 6))

        try:
            if page.get_by_role("button", name="Switch Now").is_visible():
                print("[STEP] Switching profile...", flush=True)
                page.get_by_role("button", name="Switch Now").click()
                time.sleep(5)
        except: pass

        print("[STEP] Opening post box...", flush=True)
        page.get_by_role("button", name="What's on your mind?").click()
        time.sleep(random.randint(4, 7))

        page.get_by_role("paragraph").click()
        page.keyboard.type("Enjoy this video")

        print("[STEP] Uploading video...", flush=True)
        with page.expect_file_chooser() as fc:
            page.get_by_role("button", name="Photo/video", exact=True).click()
        fc.value.set_files(str(video_path))

        print("[STEP] Processing video...", flush=True)
        time.sleep(30)

        page.get_by_role("button", name="Next").click()
        time.sleep(15)

        print("[STEP] Adding Reel details...", flush=True)
        page.get_by_role("textbox", name="Reel title").fill("Watch this")
        time.sleep(15)

        tags_box = page.get_by_role("textbox", name="Add tags")
        tags_text = "viral,trending,video,masti,"
        for char in tags_text:
            tags_box.type(char)
            time.sleep(random.uniform(0.05, 0.2))

        time.sleep(15)
        page.get_by_role("button", name="Next").click()
        time.sleep(15)

        print("[STEP] Final Posting...", flush=True)
        page.get_by_role("button", name="Post", exact=True).last.click()
        time.sleep(20)

        try:
            if page.get_by_role("button", name="Not now").is_visible():
                page.get_by_role("button", name="Not now").click()
        except: pass

        print("✅ POST SUCCESS", flush=True)

        # =========================
        # SAVE TO JSON ONLY ON SUCCESS
        # =========================
        print("[STEP] Recording successful post to JSON...", flush=True)
        all_posted = load_posted_links()
        if video_link not in all_posted:
            all_posted.insert(0, video_link)
            with open(POSTED_FILE, "w", encoding="utf-8") as f:
                json.dump(all_posted, f, indent=2)
            print("[OK] Link saved to posted_reels.json", flush=True)

    except Exception as e:
        print(f"[ERROR] FB Bot failed: {e}", flush=True)
    finally:
        print("[STEP] Cleaning up resources...", flush=True)
        try: browser.close()
        except: pass
        try:
            shutil.rmtree(TEMP_DIR)
            TEMP_DIR.mkdir(exist_ok=True)
        except: pass
        try: pw_cm.__exit__(None, None, None)
        except: pass
        print("[DONE] Bot finished session", flush=True)

# =========================
# MAIN EXECUTION
# =========================
if __name__ == "__main__":
    print("🚀 Script Execution Started", flush=True)
    
    # 1. Start Scraper
    final_video_link = run_scraper()
    
    # 2. Start Bot if video found
    if final_video_link:
        run_fb_bot(final_video_link)
    else:
        print("🏁 Finished: No new videos found to post.", flush=True)
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
HEADLESS = True
FACEBOOK_COOKIES_FILE = "cookies.json.encrypted"
CHANNEL_FILE = "channels.txt"
POSTED_FILE = "posted_reels.json"
TEMP_DIR = Path("temp")
PBKDF2_ITERATIONS = 200_000
# ==========================================

# =========================
# ENV
# =========================
load_dotenv()
DECRYPT_KEY = os.getenv("DECRYPT_KEY")

if not DECRYPT_KEY:
    print("❌ DECRYPT_KEY missing in .env", flush=True)
    raise RuntimeError("DECRYPT_KEY missing")

os.makedirs(TEMP_DIR, exist_ok=True)

# ================= LOAD DATA =================
def load_posted_links():
    if os.path.exists(POSTED_FILE):
        with open(POSTED_FILE, "r") as f:
            try:
                return json.load(f)
            except:
                return []
    return []

posted_links = load_posted_links()

if os.path.exists(CHANNEL_FILE):
    with open(CHANNEL_FILE, "r") as f:
        all_channels = [line.strip() for line in f if line.strip()]
else:
    all_channels = []

if not all_channels:
    print("❌ Error: channels.txt is empty or missing!", flush=True)
    exit()

remaining_channels = all_channels.copy()

# ================= DOWNLOAD =================
def download_video(video_url):
    print(f"⬇️ Attempting Download: {video_url}", flush=True)

    ydl_opts = {
        'format': 'best[ext=mp4]/best',
        'outtmpl': f'{TEMP_DIR}/%(id)s.%(ext)s',
        'quiet': True,
        'no_warnings': True,
        'noplaylist': True,
    }

    try:
        with YoutubeDL(ydl_opts) as ydl:
            ydl.download([video_url])
        return True
    except Exception as e:
        error_msg = str(e).lower()
        if "members-only" in error_msg or "join this channel" in error_msg:
            print(f"❌ SKIPPING: Video is Members-Only.", flush=True)
            return False
            
        print(f"⚠️ Primary download failed, trying fallback...", flush=True)
        try:
            ydl_opts_fallback = {
                'format': 'bestvideo+bestaudio/best',
                'merge_output_format': 'mp4',
                'outtmpl': f'{TEMP_DIR}/%(id)s.%(ext)s',
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

# ================= SCRAPER & DOWNLOADER =================
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
            if not href or "/shorts/" not in href: 
                continue
            
            video_id = href.split("/shorts/")[-1].split("?")[0].replace("/", "")
            
            if not video_id or len(video_id) < 5:
                continue
                
            clean_link = f"https://www.youtube.com/shorts/{video_id}"

            if clean_link in seen_in_session:
                continue
            
            seen_in_session.add(clean_link)

            # Check against global posted_links (loaded at start)
            if clean_link not in posted_links:
                print(f"✅ NEW Link Found: {clean_link}", flush=True)
                
                download_success = download_video(clean_link)
                
                if download_success:
                    print(f"🎯 Downloaded. Sending to Facebook bot...", flush=True)
                    return clean_link # Returning link to main flow
                else:
                    print(f"🔄 Looking for next video in the SAME channel...", flush=True)
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

# ================= CORE LOGIC =================
def run_scraper():
    global remaining_channels

    print("[STEP] Starting Scraper with Stealth...", flush=True)
    
    # 1. Stealth setup
    stealth = Stealth()
    
    # 2. Playwright ko stealth ke saath wrap karein
    pw_cm = stealth.use_sync(sync_playwright())
    p = pw_cm.__enter__()

    try:
        # Browser launch with specific args for better stealth
        browser = p.chromium.launch(
            headless=HEADLESS,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox"
            ]
        )
        
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        
        page = context.new_page()

        while remaining_channels:
            channel_url = random.choice(remaining_channels)
            remaining_channels.remove(channel_url)

            video_link = process_channel(channel_url, page)
            if video_link:
                browser.close()
                return video_link 

        browser.close()
        print("\n🚫 All channels scanned. No new downloadable videos found.", flush=True)
        return None

    except Exception as e:
        print(f"[ERROR in Scraper] {e}", flush=True)
        return None
        
    finally:
        # Context manager ko safely exit karein
        try:
            pw_cm.__exit__(None, None, None)
        except:
            pass


# =========================
# CRYPTO
# =========================
def _derive_key(password: bytes, salt: bytes) -> bytes:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=PBKDF2_ITERATIONS,
    )
    return kdf.derive(password)


def _decrypt_payload(payload: Dict[str, Any], password: str) -> bytes:
    salt = base64.b64decode(payload["s"])
    nonce = base64.b64decode(payload["n"])
    ciphertext = base64.b64decode(payload["ct"])

    key = _derive_key(password.encode("utf-8"), salt)
    aesgcm = AESGCM(key)

    try:
        return aesgcm.decrypt(nonce, ciphertext, None)
    except InvalidTag:
        print("❌ Decryption failed: Invalid password or tag", flush=True)
        raise RuntimeError("❌ Decryption failed")


def load_cookies(file_path: Path) -> List[Dict[str, Any]]:
    print("[STEP] Loading cookies...", flush=True)

    with file_path.open("r", encoding="utf-8") as f:
        payload = json.load(f)

    plaintext = _decrypt_payload(payload, DECRYPT_KEY)
    cookies = json.loads(plaintext.decode("utf-8"))

    print("[OK] Cookies loaded", flush=True)
    return cookies

def get_latest_video():
    videos = list(TEMP_DIR.glob("*.mp4"))
    if not videos:
        print("[ERROR] No video found in temp folder", flush=True)
        raise RuntimeError("No video found in temp folder")

    return max(videos, key=os.path.getctime)

# =========================
# FACEBOOK BOT
# =========================
def run_fb_bot(video_link):
    if not video_link:
        print("[SKIP] No video link provided to bot", flush=True)
        return

    print("[START] Bot started for Reel upload", flush=True)

    cookies = load_cookies(Path(FACEBOOK_COOKIES_FILE))
    video_path = get_latest_video()

    stealth = Stealth()
    pw_cm = stealth.use_sync(sync_playwright())
    pw = pw_cm.__enter__()

    try:
        browser = pw.chromium.launch(
            headless=HEADLESS,
            args=[
                "--start-maximized",
                "--disable-blink-features=AutomationControlled"
            ]
        )

        context = browser.new_context(
            no_viewport=True,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )

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
        except:
            pass

        print("[STEP] Opening post box...", flush=True)
        page.get_by_role("button", name="What's on your mind?").click()
        time.sleep(random.randint(4, 7))

        page.get_by_role("paragraph").click()
        page.keyboard.type("Enjoy this video")

        print("[STEP] Uploading video...", flush=True)
        with page.expect_file_chooser() as fc:
            page.get_by_role("button", name="Photo/video", exact=True).click()

        fc.value.set_files(str(video_path))

        print("[STEP] Video uploaded, waiting for processing...", flush=True)
        time.sleep(29)

        print("[STEP] Clicking Next...", flush=True)
        page.get_by_role("button", name="Next").click()
        time.sleep(15)

        print("[STEP] Adding Reel title...", flush=True)
        page.get_by_role("textbox", name="Reel title").fill("Watch this")
        time.sleep(15)

        print("[STEP] Adding tags manually...", flush=True)
        tags_box = page.get_by_role("textbox", name="Add tags")
        tags_text = "viral,trending,video,masti,"
        for char in tags_text:
            tags_box.type(char)
            time.sleep(random.uniform(0.05, 0.2))

        time.sleep(15)

        print("[STEP] Clicking Next (final step)...", flush=True)
        page.get_by_role("button", name="Next").click()
        time.sleep(15)

        print("[STEP] Final Post click...", flush=True)
        page.get_by_role("button", name="Post", exact=True).last.click()
        time.sleep(20)

        try:
            if page.get_by_role("button", name="Not now").is_visible():
                print("[STEP] WhatsApp - Not Now...", flush=True)
                page.get_by_role("button", name="Not now").click()
        except:
            pass

        time.sleep(20)

        print("✅ POST SUCCESS", flush=True)

        # =========================
        # SAVE TO JSON ONLY ON SUCCESS
        # =========================
        print("[STEP] Saving link to posted_reels.json...", flush=True)
        all_posted = []
        if os.path.exists(POSTED_FILE):
            with open(POSTED_FILE, "r", encoding="utf-8") as f:
                try:
                    all_posted = json.load(f)
                except:
                    all_posted = []
        
        if video_link not in all_posted:
            all_posted.insert(0, video_link)
            with open(POSTED_FILE, "w", encoding="utf-8") as f:
                json.dump(all_posted, f, indent=2)
            print(f"[OK] Link saved successfully.", flush=True)

    except Exception as e:
        print(f"[ERROR] Failed to post: {e}", flush=True)

    finally:
        print("[STEP] Cleaning up resources...", flush=True)
        try:
            browser.close()
        except:
            pass

        try:
            shutil.rmtree(TEMP_DIR)
            TEMP_DIR.mkdir(exist_ok=True)
        except:
            pass

        try:
            pw_cm.__exit__(None, None, None)
        except:
            pass

        print("[DONE] Bot finished", flush=True)

if __name__ == "__main__":
    print("🚀 Script Started", flush=True)
    # 1. Scraper se link uthao
    target_link = run_scraper()
    
    # 2. Agar link mil gaya tabhi FB bot chalao
    if target_link:
        run_fb_bot(target_link)
    else:
        print("🏁 No new videos found to process.", flush=True)
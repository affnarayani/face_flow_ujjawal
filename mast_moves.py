import os
import json
import time
import base64
import random
import shutil
from pathlib import Path
from typing import List, Dict, Any

from dotenv import load_dotenv
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.exceptions import InvalidTag

from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth  # ✅ REQUIRED (UNTOUCHED)

# =========================
# CONFIG
# =========================
HEADLESS = True
FACEBOOK_COOKIES_FILE = "cookies.json.encrypted"
VIDEO_FOLDER = Path("mast_moves")
PBKDF2_ITERATIONS = 200_000

# =========================
# ENV
# =========================
load_dotenv()
DECRYPT_KEY = os.getenv("DECRYPT_KEY")

if not DECRYPT_KEY:
    raise RuntimeError("❌ DECRYPT_KEY missing in .env file")

# =========================
# CRYPTO (Original Logic)
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
        raise RuntimeError("❌ Decryption failed (InvalidTag) - Check your DECRYPT_KEY")

def load_cookies(file_path: Path) -> List[Dict[str, Any]]:
    print(f"[STEP] Reading encrypted cookies from {file_path}...", flush=True)
    if not file_path.exists():
        print(f"[ERROR] Cookie file {file_path} not found!", flush=True)
        raise FileNotFoundError(file_path)

    with file_path.open("r", encoding="utf-8") as f:
        payload = json.load(f)

    plaintext = _decrypt_payload(payload, DECRYPT_KEY)
    cookies = json.loads(plaintext.decode("utf-8"))

    print("[OK] Cookies decrypted and loaded successfully", flush=True)
    return cookies

# =========================
# UTILS
# =========================
def get_random_video():
    print("[STEP] Scanning folder for videos...", flush=True)
    if not VIDEO_FOLDER.exists():
        print(f"[ERROR] Folder '{VIDEO_FOLDER}' does not exist!", flush=True)
        return None
    
    videos = list(VIDEO_FOLDER.glob("*.mp4"))
    if not videos:
        print(f"[ERROR] No .mp4 files found in '{VIDEO_FOLDER}'", flush=True)
        return None
    
    selected = random.choice(videos)
    print(f"[OK] Randomly selected video: {selected.name}", flush=True)
    return selected

# =========================
# FACEBOOK BOT
# =========================
def run():
    print("[START] Bot execution initiated", flush=True)
    
    video_path = get_random_video()
    if not video_path:
        print("[EXIT] Process aborted: No video available", flush=True)
        return

    # Stealth setup - EXACTLY as requested
    print("[STEP] Initializing Stealth configuration...", flush=True)
    stealth = Stealth()
    pw_cm = stealth.use_sync(sync_playwright())
    pw = pw_cm.__enter__()

    try:
        print("[STEP] Launching Chromium browser...", flush=True)
        browser = pw.chromium.launch(
            headless=HEADLESS,
            args=[
                "--start-maximized",
                "--disable-blink-features=AutomationControlled"
            ]
        )

        print("[STEP] Setting up browser context...", flush=True)
        context = browser.new_context(
            no_viewport=True,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )

        # Load and set encrypted cookies
        cookies = load_cookies(Path(FACEBOOK_COOKIES_FILE))
        context.add_cookies(cookies)
        page = context.new_page()

        print("[STEP] Navigating to Facebook target URL...", flush=True)
        page.goto("https://www.facebook.com/mastmoves")
        time.sleep(random.randint(3, 6))

        # Profile Switching Logic
        try:
            switch_btn = page.get_by_role("button", name="Switch Now")
            if switch_btn.is_visible():
                print("[STEP] Profile switch prompt found. Clicking 'Switch Now'...", flush=True)
                switch_btn.click()
                time.sleep(random.randint(15, 30))
        except:
            print("[INFO] No profile switch required", flush=True)

        print("[STEP] Opening the create post dialog...", flush=True)
        page.get_by_role("button", name="What's on your mind?").click()
        time.sleep(random.randint(15, 30))

        print("[STEP] Typing post caption...", flush=True)
        page.get_by_role("paragraph").click()
        page.keyboard.type("""
        Mast moves aur killer performance. Kaun kaun ise repeat mode par dekh raha hai? Apna favourite part comment mein batayein.

        #DanceIndia #TrendingReels #MastMoves #DesiDance #DanceVideo #ViralDance #ReelsIndia #DanceChallenge #IndianDancers #DesiSwag #ReelItFeelIt #DanceVibes
        """)

        time.sleep(random.randint(15, 30))

        print("[STEP] Opening file picker...", flush=True)
        with page.expect_file_chooser() as fc:
            page.get_by_role("button", name="Photo/video", exact=True).click()
        
        print(f"[STEP] Uploading: {video_path.name}", flush=True)
        fc.value.set_files(str(video_path))

        print("[STEP] Video is uploading.", flush=True)
        time.sleep(random.randint(180, 300))

        print("[STEP] Clicking 'Next'...", flush=True)
        page.get_by_role("button", name="Next").click()
        time.sleep(random.randint(15, 30))

        print("[STEP] Entering Reel details...", flush=True)
        page.get_by_role("textbox", name="Reel title").fill("Bet You Can't Watch Just Once")
        time.sleep(random.randint(15, 30))

        print("[STEP] Adding hashtags manually for human-like behavior...", flush=True)
        tags_box = page.get_by_role("textbox", name="Add tags")
        tags_text = "viral,trending,video,masti,dancevibes,explorepage,reelsindia,foryou,dailymasti,viralreels,trendingnow,desienergy,nonstopdance,watchagain,entertainment,instatrend,bestdance,hotperformance,desiswag,killermoves,"
        for char in tags_text:
            tags_box.type(char)
            time.sleep(random.uniform(0.05, 0.3))

        time.sleep(random.randint(15, 30))

        print("[STEP] Clicking 'Next' for final stage...", flush=True)
        page.get_by_role("button", name="Next").click()
        time.sleep(random.randint(15, 30))

        print("[STEP] Clicking final 'Post' button...", flush=True)
        page.get_by_role("button", name="Post", exact=True).last.click()
        
        print("[STEP] Waiting for post confirmation...", flush=True)
        time.sleep(random.randint(30, 60))

        # Handle popups
        try:
            not_now = page.get_by_role("button", name="Not now")
            if not_now.is_visible():
                print("[STEP] Dismissing WhatsApp prompt...", flush=True)
                not_now.click()
                time.sleep(random.randint(30, 60))
        except:
            pass

        print("✅ POST SUCCESS", flush=True)

        # Remove video file after successful upload
        try:
            if video_path.exists():
                print(f"[STEP] Deleting uploaded file: {video_path.name}", flush=True)
                os.remove(video_path)
                print("[OK] File removed from folder", flush=True)
        except Exception as e:
            print(f"[WARNING] Could not delete file: {e}", flush=True)

    except Exception as e:
        print(f"[ERROR] Process failed: {e}", flush=True)

    finally:
        print("[STEP] Cleaning up browser and resources...", flush=True)
        try:
            browser.close()
            print("[OK] Browser closed", flush=True)
        except:
            pass

        try:
            pw_cm.__exit__(None, None, None)
            print("[OK] Playwright environment exited", flush=True)
        except:
            pass

        print("[DONE] Bot finished tasks", flush=True)

if __name__ == "__main__":
    run()
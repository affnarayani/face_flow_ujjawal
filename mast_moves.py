import os
import json
import time
import base64
import random
import sys
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
FACEBOOK_COOKIES_FILE = "fb_cookies.json.encrypted"
VIDEO_JSON_FILE = Path("video.json")
VIDEO_FOLDER = Path("mast_moves")
PBKDF2_ITERATIONS = 200_000

# =========================
# ENV
# =========================
load_dotenv()
DECRYPT_KEY = os.getenv("DECRYPT_KEY")

if not DECRYPT_KEY:
    print("DECRYPT_KEY missing in .env file", flush=True)
    sys.exit(1)

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
        print("Decryption failed - Check your DECRYPT_KEY", flush=True)
        sys.exit(1)

def load_cookies(file_path: Path) -> List[Dict[str, Any]]:
    print(f"[STEP] Reading encrypted cookies from {file_path}...", flush=True)
    if not file_path.exists():
        print(f"[ERROR] Cookie file {file_path} not found!", flush=True)
        sys.exit(1)

    with file_path.open("r", encoding="utf-8") as f:
        payload = json.load(f)

    plaintext = _decrypt_payload(payload, DECRYPT_KEY)
    cookies = json.loads(plaintext.decode("utf-8"))

    print("[OK] Cookies decrypted and loaded successfully", flush=True)
    return cookies

# =========================
# JSON DATA LOAD & UTILS
# =========================
def load_video_metadata():
    print(f"[STEP] Reading metadata from {VIDEO_JSON_FILE}...", flush=True)
    if not VIDEO_JSON_FILE.exists():
        print(f"[ERROR] JSON file '{VIDEO_JSON_FILE}' does not exist!", flush=True)
        sys.exit(1)
        
    with VIDEO_JSON_FILE.open("r", encoding="utf-8") as f:
        data = json.load(f)
    print("[OK] Video metadata loaded successfully", flush=True)
    return data

def get_json_video(filename: str):
    print(f"[STEP] Searching for file '{filename}' in '{VIDEO_FOLDER}'...", flush=True)
    if not VIDEO_FOLDER.exists():
        print(f"[ERROR] Folder '{VIDEO_FOLDER}' does not exist!", flush=True)
        sys.exit(1)
    
    video_path = VIDEO_FOLDER / filename
    if not video_path.exists():
        print(f"[ERROR] Video file '{filename}' not found in '{VIDEO_FOLDER}' folder!", flush=True)
        sys.exit(1)
    
    print(f"[OK] Video file verified: {video_path.name}", flush=True)
    return video_path

# =========================
# FACEBOOK BOT
# =========================
def run():
    print("[START] Bot execution initiated", flush=True)
    
    # JSON data load karein
    video_data = load_video_metadata()
    
    # JSON se specifics extract karein
    target_filename = video_data.get("filename")
    post_title = video_data.get("title", "")
    post_keywords = video_data.get("keyword", "") # comma separated keywords

    # Description fetch karein aur ensure karein ki end mein space ho
    post_description = video_data.get("description", "")
    if post_description and not post_description.endswith(" "):
        post_description += " "  # ✅ Code se dynamically last mein space add kar diya

    # Video select karein
    video_path = get_json_video(target_filename)
    
    # Stealth setup
    print("[STEP] Initializing Stealth configuration...", flush=True)
    clear_stealth = Stealth()
    pw_cm = clear_stealth.use_sync(sync_playwright())
    pw = pw_cm.__enter__()

    # Track failure status for final exit
    execution_failed = False

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

        cookies = load_cookies(Path(FACEBOOK_COOKIES_FILE))
        context.add_cookies(cookies)
        page = context.new_page()

        print("[STEP] Navigating to Facebook target URL...", flush=True)
        page.goto("https://www.facebook.com/mastmoves")
        time.sleep(random.randint(15, 30))

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
        
        # Space-adjusted description yahan type hoga
        page.keyboard.type(post_description)
        time.sleep(random.randint(15, 30))

        print("[STEP] Opening file picker...", flush=True)
        with page.expect_file_chooser() as fc:
            page.get_by_role("button", name="Photo/video", exact=True).click()
        
        print(f"[STEP] Uploading: {video_path.name}", flush=True)
        fc.value.set_files(str(video_path))

        print("[STEP] Video is uploading.", flush=True)
        time.sleep(random.randint(90, 180))

        print("[STEP] Clicking 'Next'...", flush=True)
        page.get_by_role("button", name="Next").click()
        time.sleep(random.randint(15, 30))

        print("[STEP] Entering Reel details...", flush=True)
        page.get_by_role("textbox", name="Reel title").fill(post_title)
        time.sleep(random.randint(15, 30))

        print("[STEP] Adding hashtags manually...", flush=True)
        tags_box = page.get_by_role("textbox", name="Add tags")
        
        tags_text = post_keywords
        if tags_text and not tags_text.endswith(','):
            tags_text += ','
            
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

        print("POST SUCCESS", flush=True)

        # Remove video file after success
        try:
            if video_path.exists():
                os.remove(video_path)
                print("[OK] File removed", flush=True)
        except:
            pass

    except Exception as e:
        print(f"[ERROR] Unexpected failure: {e}", flush=True)
        execution_failed = True  # ✅ This flag ensures we exit(1) at the end

    finally:
        print("[STEP] Cleaning up resources...", flush=True)
        try:
            browser.close()
            pw_cm.__exit__(None, None, None)
        except:
            pass

        if execution_failed:
            print("[EXIT] Script failed at a step. Reporting failure to GitHub.", flush=True)
            sys.exit(1)  # ✅ FORCE FAIL GITHUB WORKFLOW
        
        print("[DONE] Bot finished successfully", flush=True)

if __name__ == "__main__":
    run()
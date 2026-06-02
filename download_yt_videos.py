import os
import sys
from playwright.sync_api import sync_playwright
from yt_dlp import YoutubeDL
from playwright_stealth import Stealth

# ================= CONFIG =================
CHANNEL_URL = "https://www.youtube.com/@Kaelixcreates/shorts"
DOWNLOAD_FOLDER = "temp"
HEADLESS = True

with open("channels.txt", "r") as f:
    if any(CHANNEL_URL == line.strip() for line in f):
        sys.exit("Channel already exists.")

# 1. Folder create karna
if not os.path.exists(DOWNLOAD_FOLDER):
    os.makedirs(DOWNLOAD_FOLDER)

# ================= DOWNLOADER =================
def download_video(video_url):
    ydl_opts = {
        'format': 'bestvideo+bestaudio/best',
        'outtmpl': f'{DOWNLOAD_FOLDER}/%(id)s.%(ext)s',
        'quiet': True,
        'no_warnings': True,
        'ignoreerrors': True,
    }
    try:
        with YoutubeDL(ydl_opts) as ydl:
            ydl.download([video_url])
        return True
    except Exception:
        return False

# ================= MAIN SCRAPER =================
def run_scraper():
    stealth = Stealth()
    pw_cm = stealth.use_sync(sync_playwright())
    pw = pw_cm.__enter__()

    try:
        browser = pw.chromium.launch(
            headless=HEADLESS,
            args=["--start-maximized", "--disable-blink-features=AutomationControlled", "--no-sandbox"]
        )

        context = browser.new_context(
            no_viewport=True,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        
        page = context.new_page()
        print(f"🔍 Scanning: {CHANNEL_URL}")
        page.goto(CHANNEL_URL, wait_until="networkidle")

        all_links = set()
        last_height = 0

        # --- SCROLLING & LINK COLLECTION ---
        while True:
            elements = page.query_selector_all('a[href*="/shorts/"]')
            for el in elements:
                href = el.get_attribute("href")
                if href and "/shorts/" in href:
                    video_id = href.split("/shorts/")[-1].split("?")[0].replace("/", "")
                    # Sirf valid length wali ID add karein (11 chars)
                    if len(video_id) == 11:
                        all_links.add(f"https://www.youtube.com/shorts/{video_id}")

            page.evaluate("window.scrollTo(0, document.documentElement.scrollHeight)")
            page.wait_for_timeout(2500)
            
            new_height = page.evaluate("document.documentElement.scrollHeight")
            if new_height == last_height:
                break
            last_height = new_height
            print(f"Found {len(all_links)} videos...", end="\r")

        # --- DOWNLOAD LOGIC WITH COUNTER ---
        video_list = list(all_links)
        total_videos = len(video_list)
        
        print(f"\n✅ Total {total_videos} videos found. Starting Download...")

        browser.close() # Browser band kar rahe hain downloads shuru karne se pehle
        
        # Yahan enumerate(..., 1) i ko 1 se shuru karega
        for i, link in enumerate(video_list, 1):
            print(f"⬇️ Downloading {i}/{total_videos}: {link}")
            download_video(link)

    except Exception as e:
        print(f"⚠️ Scraper Error: {e}")
    finally:
        pw_cm.__exit__(None, None, None)

def append_channel_url(url):
    file_name = "channels.txt"
    
    # Check karenge ki file exist karti hai aur khali toh nahi hai
    is_empty_or_new = True
    if os.path.exists(file_name) and os.path.getsize(file_name) > 0:
        is_empty_or_new = False

    if is_empty_or_new:
        # Agar file nayi hai ya khali hai, toh direct URL aur newline likh do
        with open(file_name, "a", encoding="utf-8") as file:
            file.write(url + "\n")
    else:
        # Agar file mein pehle se data hai, toh check karenge ki last character kya hai
        with open(file_name, "rb+") as file:
            file.seek(-1, os.SEEK_END)  # Bilkul aakhri character par jayenge
            last_char = file.read(1)
            
            # Agar aakhri character newline (\n) nahi hai, toh pehle newline add karenge
            if last_char != b'\n':
                file.write(b'\n')
        
        # Ab naye line par safe tareeke se URL append karenge
        with open(file_name, "a", encoding="utf-8") as file:
            file.write(url + "\n")
            
    print("URL successfully appended to a new line!")

if __name__ == "__main__":
    run_scraper()
    append_channel_url(CHANNEL_URL)

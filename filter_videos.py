import os
import cv2

# 1. Apne temp folder ka path yahan likhein
TEMP_FOLDER_PATH = r"temp"

def clean_folder_final_attempt(folder_path):
    if not os.path.exists(folder_path):
        print("Error: Sahi folder path dalein.")
        return

    print("Frame-counting aur Resolution approach se cleaning shuru...\n")
    files = os.listdir(folder_path)
    
    MAX_SIZE_BYTES = 99 * 1024 * 1024  # 99 MB
    MAX_DURATION_SECONDS = 59.0        # 59 Seconds
    
    for filename in files:
        file_path = os.path.join(folder_path, filename)
        
        if not os.path.isfile(file_path):
            continue
            
        # --- RULE 1: MP4 check ---
        if not filename.lower().endswith('.mp4'):
            try:
                os.remove(file_path)
                print(f"Deleted (Not MP4): {filename}")
            except Exception as e:
                print(f"Error deleting {filename}: {e}")
            continue

        # --- RULE 2: Filesize check (99 MB) ---
        try:
            file_size_bytes = os.path.getsize(file_path)
            file_size_mb = file_size_bytes / (1024 * 1024)
            
            if file_size_bytes > MAX_SIZE_BYTES:
                os.remove(file_path)
                print(f"Deleted (Size > 99MB - {file_size_mb:.2f} MB): {filename}")
                continue
        except Exception as e:
            print(f"Error checking size for {filename}: {e}")
            continue

        # --- OpenCV Frame-Counting Approach ---
        try:
            cap = cv2.VideoCapture(file_path)
            
            if not cap.isOpened():
                print(f"Skipping (Could not open video file): {filename}")
                continue
            
            # 1. Dimensions nikalna
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            
            # 2. Raw math se duration nikalna
            total_frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)
            fps = cap.get(cv2.CAP_PROP_FPS)
            
            # Video stream ko turant close karein taaki file delete ho sake
            cap.release()
            
            # Safe check: Agar FPS ya frames zero aa rahe hain toh skip karein
            if fps == 0 or total_frames <= 0:
                print(f"Skipping (Corrupted metadata/Zero FPS): {filename}")
                continue
                
            duration = total_frames / fps  # Actual duration calculated here!

            # --- RULE 3: Duration check (59 seconds) ---
            if duration > MAX_DURATION_SECONDS:
                os.remove(file_path)
                print(f"Deleted (Duration > 59s - {duration:.2f}s): {filename}")
                continue

            # --- RULE 4 & 5: Resolution check (Height < 1280 ya Width < 720) ---
            if height < 1280 or width < 720:
                os.remove(file_path)
                print(f"Deleted (Low Res - {width}x{height}): {filename}")
            else:
                print(f"Kept (Safe - {file_size_mb:.2f} MB, {duration:.2f}s, {width}x{height}): {filename}")
                
        except Exception as e:
            print(f"Error processing {filename}: {e}")
            try:
                cap.release()
            except:
                pass

    print("\nCleaning poori ho gayi!")

if __name__ == "__main__":
    clean_folder_final_attempt(TEMP_FOLDER_PATH)
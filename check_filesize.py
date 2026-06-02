import os

# Apne temp folder ka sahi path yahan likhein
TEMP_FOLDER_PATH = r"temp"

# 99 MB ko bytes mein convert kiya (1 MB = 1024 * 1024 bytes)
SIZE_LIMIT_MB = 99
SIZE_LIMIT_BYTES = SIZE_LIMIT_MB * 1024 * 1024

def delete_large_files(folder_path):
    # Check kya folder sach mein exist karta hai
    if not os.path.exists(folder_path):
        # Yahan par pehle 'path' likha tha, ab 'folder_path' kar diya hai
        print(f"'{folder_path}' Folder nahi mila! Kripya sahi path dalein.")
        return

    print(f"{SIZE_LIMIT_MB} MB se badi files ko delete kiya ja raha hai...\n")
    
    # Folder ke andar ki sabhi files ko check karna
    for root, dirs, files in os.walk(folder_path):
        for file in files:
            file_path = os.path.join(root, file)
            
            try:
                # File ka size nikalna (bytes mein)
                file_size = os.path.getsize(file_path)
                
                if file_size > SIZE_LIMIT_BYTES:
                    file_size_mb = file_size / (1024 * 1024)
                    print(f"Deleting: {file} ({file_size_mb:.2f} MB)")
                    
                    # File delete karne ki command
                    os.remove(file_path)
                    
            except FileNotFoundError:
                continue
            except PermissionError:
                print(f"Skipped (Permission Denied): {file}")
            except Exception as e:
                print(f"Error processing {file}: {e}")

# Code ko run karein
if __name__ == "__main__":
    delete_large_files(TEMP_FOLDER_PATH)
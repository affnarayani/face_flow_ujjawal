import os
from moviepy.video.io.VideoFileClip import VideoFileClip

def convert_webm_to_mp4_and_delete_source(folder_name="temp"):
    # Check karna ki folder exist karta hai ya nahi
    if not os.path.exists(folder_name):
        print(f"Error: '{folder_name}' naam ka folder nahi mila!", flush=True)
        return

    # Folder ke andar ki saari files ki list nikalna
    files = os.listdir(folder_name)
    
    # Sirf .webm files ko filter karna
    webm_files = [f for f in files if f.endswith('.webm')]

    if not webm_files:
        print(f"'{folder_name}' folder mein koi .webm files nahi mili.", flush=True)
        return

    total_files = len(webm_files)
    print(f"Total {total_files} .webm files mili. Conversion shuru ho raha hai...\n", flush=True)

    # enumerate() ka use kiya hai counter chalane ke liye (1 se shuru hoga)
    for index, file_name in enumerate(webm_files, start=1):
        # Input aur Output file ka poora path banana
        input_path = os.path.join(folder_name, file_name)
        output_file_name = file_name.rsplit('.', 1)[0] + '.mp4'
        output_path = os.path.join(folder_name, output_file_name)

        # Counter display [1/212] format mein
        print(f"[{index}/{total_files}] Converting: {file_name} -> {output_file_name}", flush=True)
        
        try:
            # Video ko load aur convert karna
            clip = VideoFileClip(input_path)
            # codec='libx264' aur audio_codec='aac' ensure karta hai ki video har jagah chale
            clip.write_videofile(output_path, codec='libx264', audio_codec='aac')
            
            # File delete karne se pehle clip ko close karna zaroori hai
            clip.close()
            
            print(f"[{index}/{total_files}] Successfully converted: {output_file_name}", flush=True)
            
            # Original .webm file ko delete karna
            os.remove(input_path)
            print(f"[{index}/{total_files}] Deleted original file: {file_name}\n", flush=True)
            
        except Exception as e:
            print(f"[{index}/{total_files}] Error processing {file_name}: {e}\n", flush=True)

    print("Saari files ka conversion aur cleanup poora ho gaya!", flush=True)

if __name__ == "__main__":
    # Agar aapka folder script ke sath hi 'temp' naam se hai toh default chalega
    convert_webm_to_mp4_and_delete_source("temp")
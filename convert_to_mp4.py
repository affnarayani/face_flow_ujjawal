import os
from moviepy.video.io.VideoFileClip import VideoFileClip

def convert_webm_to_mp4(folder_name="temp"):
    # Check karna ki folder exist karta hai ya nahi
    if not os.path.exists(folder_name):
        print(f"Error: '{folder_name}' naam ka folder nahi mila!")
        return

    # Folder ke andar ki saari files ki list nikalna
    files = os.listdir(folder_name)
    
    # Sirf .webm files ko filter karna
    webm_files = [f for f in files if f.endswith('.webm')]

    if not webm_files:
        print(f"'{folder_name}' folder mein koi .webm files nahi mili.")
        return

    print(f"Total {len(webm_files)} .webm files mili. Conversion shuru ho raha hai...\n")

    for file_name in webm_files:
        # Input aur Output file ka poora path banana
        input_path = os.path.join(folder_name, file_name)
        output_file_name = file_name.rsplit('.', 1)[0] + '.mp4'
        output_path = os.path.join(folder_name, output_file_name)

        print(f"Converting: {file_name} -> {output_file_name}")
        
        try:
            # Video ko load aur convert karna
            clip = VideoFileClip(input_path)
            # codec='libx264' aur audio_codec='aac' ensure karta hai ki video har jagah chale
            clip.write_videofile(output_path, codec='libx264', audio_codec='aac')
            clip.close()
            print(f"Successfully converted: {output_file_name}\n")
        except Exception as e:
            print(f"Error converting {file_name}: {e}\n")

    print("Saari files ka conversion poora ho gaya!")

if __name__ == "__main__":
    # Agar aapka folder script ke sath hi 'temp' naam se hai toh default chalega
    convert_webm_to_mp4("temp")
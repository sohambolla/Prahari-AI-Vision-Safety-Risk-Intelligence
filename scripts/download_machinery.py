import os
import subprocess

ids = ['Kfk5cMTe-vg', 'Q9zklg2aDlc', 'F9LJeKiCQCE', 'xqW4WrLW0Ic']
os.makedirs('videos/testing/machinery', exist_ok=True)

for i, vid in enumerate(ids):
    print(f"Downloading {vid}...")
    try:
        # Download first 15 seconds
        subprocess.run([
            "yt-dlp",
            "--js-runtimes", "node",
            "--download-sections", "*00:00:15-00:00:30",
            "-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/mp4",
            "-o", f"videos/testing/machinery/machinery_vid_{i}.mp4",
            f"https://www.youtube.com/watch?v={vid}"
        ], check=True)
    except Exception as e:
        print(f"Failed {vid}: {e}")

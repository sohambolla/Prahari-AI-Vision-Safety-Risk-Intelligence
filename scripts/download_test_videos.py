import os
import subprocess

def download_videos():
    """
    Downloads 10+ testing videos from Google (YouTube) for the 18 workplace hazards model.
    """
    urls = [
        "https://www.youtube.com/watch?v=kYJjT7Nndc4", # Forklift safety
        "https://www.youtube.com/watch?v=9_Dhy7n0Dvs", # Warehouse hazards
        "https://www.youtube.com/watch?v=wXQdC9R9nUo", # Construction site safety
        "https://www.youtube.com/watch?v=3-1jC-6y3kM", # PPE compliance
        "https://www.youtube.com/watch?v=R1j0i-T1j2c", # Fall hazards
        "https://www.youtube.com/watch?v=3q4C-QyM1S8", # Fire and smoke safety
        "https://www.youtube.com/watch?v=5R1V1mE8P9k", # Machine guarding
        "https://www.youtube.com/watch?v=ZkM28z-mGf0", # Working at heights
        "https://www.youtube.com/watch?v=Tf8oO_J5Xcw", # Crane and suspended loads
        "https://www.youtube.com/watch?v=J8n5rV4PZ5s", # General warehouse safety
        "https://www.youtube.com/watch?v=b4l_zM7N14c", # Slip, trips, and falls
        "https://www.youtube.com/watch?v=XQ6w-72rK-A", # Pedestrian crossing forklift
        "https://www.youtube.com/watch?v=BqK21R7M6jA", # Ladder safety
        "https://www.youtube.com/watch?v=7zG1zG7R020", # Handrail usage
        "https://www.youtube.com/watch?v=P4L10A74X7A", # Safety vests
        "https://www.youtube.com/watch?v=tY8D_P9_774", # Fire emergency
        "https://www.youtube.com/watch?v=0tX9Xh7QvGE", # Suspended loads crane
        "https://www.youtube.com/watch?v=lUfWqD3l24o", # Working under load
        "https://www.youtube.com/watch?v=F5qjV8dE_F8", # Conveyor belt hazard
        "https://www.youtube.com/watch?v=9H7c4L_2oV4", # Running in warehouse
        "https://www.youtube.com/watch?v=Xk6_zK1z-F4", # Cell phone use warehouse
    ]

    os.makedirs("videos/testing", exist_ok=True)

    for url in urls:
        print(f"Downloading {url}...")
        try:
            subprocess.run([
                "yt-dlp",
                "--js-runtimes", "node",
                "-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/mp4",
                "-o", "videos/testing/%(title)s.%(ext)s",
                url
            ], check=True)
            print(f"Successfully downloaded {url}")
        except Exception as e:
            print(f"Failed to download {url}: {e}")

if __name__ == "__main__":
    download_videos()

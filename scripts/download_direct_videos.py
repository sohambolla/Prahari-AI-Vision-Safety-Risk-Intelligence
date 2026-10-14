import urllib.request
import os

os.makedirs('videos/testing', exist_ok=True)

urls = [
    "https://raw.githubusercontent.com/intel-iot-devkit/sample-videos/master/worker-zone-detection.mp4",
    "https://raw.githubusercontent.com/intel-iot-devkit/sample-videos/master/person-bicycle-car-detection.mp4",
    "https://raw.githubusercontent.com/intel-iot-devkit/sample-videos/master/pedestrian-and-vehicle-detector.mp4",
    "https://raw.githubusercontent.com/intel-iot-devkit/sample-videos/master/people-detection.mp4",
    "https://raw.githubusercontent.com/intel-iot-devkit/sample-videos/master/retail-store-aisle.mp4",
    "https://raw.githubusercontent.com/intel-iot-devkit/sample-videos/master/bottle-detection.mp4"
]

print("Downloading direct MP4 test videos...")
for url in urls:
    name = url.split('/')[-1]
    path = os.path.join('videos/testing', name)
    print(f"Downloading {name}...")
    try:
        urllib.request.urlretrieve(url, path)
        print(f"Saved to {path}")
    except Exception as e:
        print(f"Failed to download {name}: {e}")
print("Finished downloading direct videos.")

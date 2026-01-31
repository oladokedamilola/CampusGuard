import requests
import json

api_key = "a3f8e97b12c450d6f34a8921b567d0e9f12a34b5678c9d0e1f23a45b67c89d012"
url = "http://localhost:8001/api/v1/process/image"
image_path = r"C:\Users\PC\Desktop\processing_server (FastAPI + OpenCV)\processing_server\test_image.jpg"

# Read the image file
with open(image_path, 'rb') as f:
    files = {'image': ('test_image.jpg', f, 'image/jpeg')}
    data = {'detection_types': 'person,vehicle'}
    headers = {'X-API-Key': api_key}
    
    response = requests.post(url, files=files, data=data, headers=headers)
    
print(f"Status Code: {response.status_code}")
print(f"Response: {response.text}")
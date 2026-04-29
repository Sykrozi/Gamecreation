import requests
import base64
import os

API_TOKEN = "cd20d1e2-2698-4ddf-98d8-1e86e3dab920"
OUTPUT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bg_dungeon.png")

# API max per dimension is 400px; using 400x200 to preserve 2:1 panoramic ratio
payload = {
    "description": (
        "dungeon cave battle background, pixel art RPG style, wide panoramic view, "
        "stone walls, torches with flickering flames, dark atmosphere, mossy rocks, "
        "arched doorways, stalactites hanging from ceiling, dim orange torch light, "
        "shadows, ancient dungeon, fantasy RPG, 16-bit style"
    ),
    "image_size": {"width": 400, "height": 200},
    "no_background": False,
    "shading": "detailed shading",
    "detail": "highly detailed",
    "view": "side",
    "text_guidance_scale": 10,
}

headers = {
    "Authorization": f"Bearer {API_TOKEN}",
    "Content-Type": "application/json",
}

print("Sending request to PixelLab pixflux (400x200)...")
response = requests.post(
    "https://api.pixellab.ai/v1/generate-image-pixflux",
    json=payload,
    headers=headers,
    timeout=120,
)

if response.status_code != 200:
    print(f"Error {response.status_code}: {response.text}")
    exit(1)

data = response.json()

# Response image is base64: {"image": {"type": "base64", "base64": "data:image/png;base64,..."}}
img_field = data.get("image", {})
b64_str = img_field.get("base64", "")
if "," in b64_str:
    b64_str = b64_str.split(",", 1)[1]

if not b64_str:
    print("Could not extract image from response:")
    print(data)
    exit(1)

image_data = base64.b64decode(b64_str)

with open(OUTPUT_PATH, "wb") as f:
    f.write(image_data)

print(f"Saved: {OUTPUT_PATH} (400x200 — API max width/height is 400px)")

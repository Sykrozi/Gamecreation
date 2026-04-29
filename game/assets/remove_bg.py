from PIL import Image
from collections import deque
import os

ASSETS_DIR = os.path.dirname(os.path.abspath(__file__))
TOLERANCE = 30


def color_distance(c1, c2):
    return max(abs(c1[0] - c2[0]), abs(c1[1] - c2[1]), abs(c1[2] - c2[2]))


def flood_fill_transparent(img, start_x, start_y, bg_color, tolerance):
    pixels = img.load()
    width, height = img.size
    visited = set()
    queue = deque()

    def is_background(x, y):
        px = pixels[x, y]
        return color_distance(px[:3], bg_color) <= tolerance

    if not is_background(start_x, start_y):
        return

    queue.append((start_x, start_y))
    visited.add((start_x, start_y))

    while queue:
        x, y = queue.popleft()
        pixels[x, y] = (0, 0, 0, 0)

        for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nx, ny = x + dx, y + dy
            if 0 <= nx < width and 0 <= ny < height and (nx, ny) not in visited:
                if is_background(nx, ny):
                    visited.add((nx, ny))
                    queue.append((nx, ny))


def remove_background(path):
    img = Image.open(path).convert("RGBA")
    width, height = img.size
    pixels = img.load()

    # Sample all 4 corners and pick the most common color as background
    corners = [
        pixels[0, 0][:3],
        pixels[width - 1, 0][:3],
        pixels[0, height - 1][:3],
        pixels[width - 1, height - 1][:3],
    ]
    bg_color = max(set(corners), key=corners.count)

    # Flood fill from all 4 corners
    for cx, cy in [(0, 0), (width - 1, 0), (0, height - 1), (width - 1, height - 1)]:
        flood_fill_transparent(img, cx, cy, bg_color, TOLERANCE)

    img.save(path)
    print(f"  Done: {os.path.basename(path)}")


def main():
    png_files = [
        os.path.join(ASSETS_DIR, f)
        for f in os.listdir(ASSETS_DIR)
        if f.lower().endswith(".png") and f != os.path.basename(__file__).replace(".py", ".png")
    ]

    if not png_files:
        print("No PNG files found.")
        return

    print(f"Processing {len(png_files)} PNG file(s)...\n")
    for path in sorted(png_files):
        remove_background(path)
    print("\nAll done.")


if __name__ == "__main__":
    main()

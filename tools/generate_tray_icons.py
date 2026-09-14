"""Generate deterministic ARTEMIS tray PNG resources."""

from pathlib import Path

from PIL import Image, ImageDraw

OUTPUT = Path(__file__).resolve().parents[1] / "artemis" / "resources" / "tray"
STATES = {
    "stopped": (104, 112, 124, 255),
    "starting": (45, 139, 235, 255),
    "running": (31, 157, 85, 255),
    "stopping": (230, 126, 34, 255),
    "error": (207, 48, 48, 255),
}


def draw_icon(indicator: tuple[int, int, int, int], size: int = 64) -> Image.Image:
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((5, 5, 59, 59), radius=13, fill=(25, 31, 43, 255))
    # Stylized A remains legible in monochrome; the badge adds redundant state shape.
    draw.polygon(((17, 48), (29, 16), (36, 16), (49, 48), (40, 48), (37, 39), (27, 39), (24, 48)), fill="white")
    draw.rectangle((29, 31, 35, 34), fill=(25, 31, 43, 255))
    draw.ellipse((43, 43, 61, 61), fill=(255, 255, 255, 255))
    draw.ellipse((46, 46, 58, 58), fill=indicator)
    return image


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    for state, color in STATES.items():
        draw_icon(color).save(OUTPUT / f"artemis-tray-{state}.png", optimize=True)


if __name__ == "__main__":
    main()

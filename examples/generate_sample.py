"""Generate synthetic screen recordings to demo / test Screenline end-to-end.

Produces two short 720p recordings that exercise every core feature:

  meeting_01.mp4 : Dashboard -> Settings -> (scrolling docs page) -> Reports
  meeting_02.mp4 : Dashboard -> Reports        (shares states for dedup)

Each frame also gets a moving "cursor" dot and a blinking caret — UI noise that
must NOT create new states. Requires Pillow + ffmpeg.

    python examples/generate_sample.py            # writes into examples/sample_project/
"""

from __future__ import annotations

import math
import shutil
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H, FPS = 1280, 720, 30

THEMES = {
    "Dashboard": (28, 32, 48),
    "Settings": (40, 30, 30),
    "Reports": (24, 40, 32),
}


def _font(size: int):
    for path in (
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ):
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _chrome(d: ImageDraw.ImageDraw, title: str, accent):
    base = THEMES.get(title, (30, 30, 30))
    d.rectangle([0, 0, W, 64], fill=tuple(min(255, c + 30) for c in base))
    d.text((24, 18), title, font=_font(28), fill=(235, 235, 235))
    d.rectangle([0, 64, 220, H], fill=(18, 20, 30))
    for i, item in enumerate(["Dashboard", "Settings", "Reports", "Users", "Billing"]):
        color = accent if item == title else (120, 120, 130)
        d.text((24, 100 + i * 44), item, font=_font(20), fill=color)


def screen(title: str, accent=(90, 130, 220)) -> Image.Image:
    """Each screen has a *distinct content layout* (cards / form / report), as a
    real product would — persistent chrome, different content area."""
    img = Image.new("RGB", (W, H), THEMES.get(title, (30, 30, 30)))
    d = ImageDraw.Draw(img)
    _chrome(d, title, accent)

    if title == "Dashboard":  # grid of metric cards
        for r in range(2):
            for c in range(3):
                x, y = 260 + c * 320, 110 + r * 250
                d.rectangle([x, y, x + 280, y + 200], fill=(45, 50, 70), outline=accent, width=2)
                d.text((x + 16, y + 16), f"Metric {r*3+c+1}", font=_font(22), fill=(220, 220, 220))
                d.text((x + 16, y + 90), f"{(r*3+c+1)*137}", font=_font(40), fill=(255, 255, 255))
    elif title == "Settings":  # vertical form rows with toggles
        for i in range(7):
            y = 110 + i * 78
            d.text((280, y + 14), f"Preference {i+1}", font=_font(22), fill=(220, 220, 220))
            on = i % 2 == 0
            d.rounded_rectangle([900, y + 8, 980, y + 44], radius=18,
                                fill=(90, 180, 120) if on else (80, 80, 90))
            d.ellipse([(944 if on else 904), y + 10, (978 if on else 938), y + 44], fill=(240, 240, 240))
    elif title == "Reports":  # bar chart + table
        bx, by, bh = 280, 420, 260
        for i, v in enumerate([0.4, 0.7, 0.55, 0.9, 0.3, 0.65, 0.8]):
            x = bx + i * 130
            d.rectangle([x, by - int(bh * v), x + 80, by], fill=accent)
        for i in range(3):
            y = 470 + i * 40
            d.text((280, y), f"Row {i+1}    {i*1234}    {i*7}%", font=_font(20), fill=(210, 210, 210))
    return img


def tall_doc(title: str = "Documentation") -> Image.Image:
    """A tall page revealed by scrolling. Deliberately *non-periodic* (varied
    block heights, colours and text widths) so it resembles real content and
    gives scroll registration a stable signal to lock onto."""
    import random

    rng = random.Random(42)
    page_h = H * 3
    img = Image.new("RGB", (W, page_h), (245, 245, 248))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 64], fill=(60, 70, 110))
    d.text((24, 18), title, font=_font(28), fill=(255, 255, 255))
    y = 100
    section = 1
    while y < page_h - 120:
        d.text((60, y), f"Section {section}: {rng.choice(['Overview','Setup','API','Limits','Pricing'])}",
               font=_font(rng.choice([22, 26, 30])), fill=(30, 30, 40))
        y += 44
        for _ in range(rng.randint(2, 5)):
            w = rng.randint(400, W - 120)
            shade = rng.randint(210, 235)
            d.rectangle([60, y, 60 + w, y + 18], fill=(shade, shade, shade + 8))
            y += 30
        if rng.random() < 0.4:  # occasional coloured callout block
            ch = rng.randint(60, 140)
            col = rng.choice([(210, 230, 245), (245, 230, 210), (220, 245, 220)])
            d.rectangle([60, y, W - 120, y + ch], fill=col)
            y += ch + 20
        y += rng.randint(20, 60)
        section += 1
    return img


def add_noise(frame: Image.Image, t: int) -> Image.Image:
    """Moving cursor + blinking caret: pure UI noise."""
    f = frame.copy()
    d = ImageDraw.Draw(f)
    cx = int(W / 2 + math.sin(t * 0.5) * 300)
    cy = int(H / 2 + math.cos(t * 0.7) * 200)
    d.polygon([(cx, cy), (cx + 12, cy + 4), (cx + 5, cy + 14)], fill=(255, 255, 255))
    if t % 2 == 0:
        d.rectangle([300, 30, 302, 54], fill=(255, 255, 255))  # caret blink
    return f


def write_frames(out: Path, plan):
    out.mkdir(parents=True, exist_ok=True)
    n = 0
    for item in plan:
        if item[0] == "static":
            _, base, seconds = item
            for t in range(int(seconds * FPS)):
                add_noise(base, n).save(out / f"f_{n:06d}.png")
                n += 1
        elif item[0] == "scroll":
            _, tall, seconds = item
            steps = int(seconds * FPS)
            max_off = tall.height - H
            for t in range(steps):
                off = int(max_off * (t / max(steps - 1, 1)))
                crop = tall.crop((0, off, W, off + H))
                add_noise(crop, n).save(out / f"f_{n:06d}.png")
                n += 1
    return n


def encode(frames_dir: Path, dest: Path):
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-framerate", str(FPS),
         "-i", str(frames_dir / "f_%06d.png"),
         "-c:v", "libx264", "-pix_fmt", "yuv420p", str(dest)],
        check=True,
    )


def make(dest: Path, plan):
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        write_frames(tmp_dir, plan)
        encode(tmp_dir, dest)
    print(f"  wrote {dest}")


def main():
    root = Path(__file__).parent / "sample_project"
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)

    dash, settings, reports = screen("Dashboard"), screen("Settings"), screen("Reports")
    docs = tall_doc()

    print("Generating sample recordings (this takes ~30s)...")
    make(root / "meeting_01.mp4", [
        ("static", dash, 4),
        ("static", settings, 3),
        ("scroll", docs, 8),
        ("static", reports, 3),
    ])
    make(root / "meeting_02.mp4", [
        ("static", dash, 3),
        ("static", reports, 3),
    ])

    (root / "transcript.md").write_text(
        "# Review notes\n\nWalked through the dashboard, settings and reports.\n",
        encoding="utf-8",
    )
    print(f"\nSample project ready at {root}")
    print("Try:\n  cd examples/sample_project\n  screenline init . --fps 1   # or use this folder directly")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Build the short, reproducible GF-I4 workflow demo from fictitious screenshots."""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "docs" / "assets" / "workflow-demo.gif"
FRAME_SPECS = (
    (
        ROOT / "docs" / "assets" / "loan-form-demo.png",
        "1/4  Registrar la venta o el préstamo",
    ),
    (
        ROOT / "docs" / "assets" / "customer-detail-demo.png",
        "2/4  Revisar cuotas, saldo y pagos",
    ),
    (
        ROOT / "docs" / "assets" / "dashboard-demo.png",
        "3/4  Priorizar la cobranza diaria",
    ),
    (
        ROOT / "docs" / "assets" / "reports-demo.png",
        "4/4  Analizar resultados y cartera",
    ),
)
OUTPUT_SIZE = (960, 540)
CAPTION_HEIGHT = 58
FRAME_DURATION_MS = 2300


def load_font(size: int) -> ImageFont.ImageFont:
    candidates = (
        Path("C:/Windows/Fonts/segoeuib.ttf"),
        Path("C:/Windows/Fonts/arialbd.ttf"),
    )
    for candidate in candidates:
        if candidate.is_file():
            return ImageFont.truetype(str(candidate), size=size)
    return ImageFont.load_default()


def build_frame(path: Path, caption: str) -> Image.Image:
    if not path.is_file():
        raise SystemExit(f"Missing demo frame: {path}")

    with Image.open(path) as source:
        frame = source.convert("RGB")
    frame.thumbnail(OUTPUT_SIZE, Image.Resampling.LANCZOS)

    canvas = Image.new("RGB", OUTPUT_SIZE, "#eef2f7")
    offset = (
        (OUTPUT_SIZE[0] - frame.width) // 2,
        (OUTPUT_SIZE[1] - frame.height) // 2,
    )
    canvas.paste(frame, offset)

    overlay = Image.new("RGBA", OUTPUT_SIZE, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    top = OUTPUT_SIZE[1] - CAPTION_HEIGHT
    draw.rectangle((0, top, OUTPUT_SIZE[0], OUTPUT_SIZE[1]), fill=(15, 35, 62, 238))
    font = load_font(25)
    text_box = draw.textbbox((0, 0), caption, font=font)
    text_width = text_box[2] - text_box[0]
    text_height = text_box[3] - text_box[1]
    draw.text(
        ((OUTPUT_SIZE[0] - text_width) // 2, top + (CAPTION_HEIGHT - text_height) // 2 - 2),
        caption,
        font=font,
        fill="#ffffff",
    )
    return Image.alpha_composite(canvas.convert("RGBA"), overlay).convert("RGB")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    frames = [build_frame(path, caption) for path, caption in FRAME_SPECS]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    frames[0].save(
        args.output,
        save_all=True,
        append_images=frames[1:],
        duration=[FRAME_DURATION_MS] * len(frames),
        loop=0,
        disposal=2,
        optimize=True,
    )
    print(f"GF-I4 demo GIF built: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

FONT_CANDIDATES = {
    "dejavu_sans": ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "C:/Windows/Fonts/DejaVuSans.ttf"),
    "dejavu_sans_bold": ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "C:/Windows/Fonts/DejaVuSans-Bold.ttf"),
    "dejavu_mono": ("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", "C:/Windows/Fonts/DejaVuSansMono.ttf"),
    "dejavu_mono_bold": ("/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf", "C:/Windows/Fonts/DejaVuSansMono-Bold.ttf"),
    "dejavu_serif": ("/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf", "C:/Windows/Fonts/DejaVuSerif.ttf"),
    "dejavu_serif_bold": ("/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf", "C:/Windows/Fonts/DejaVuSerif-Bold.ttf"),
}


def resolve_font(key: str) -> Path:
    for candidate in FONT_CANDIDATES[key]:
        path = Path(candidate)
        if path.exists():
            return path
    raise RuntimeError(f"A public DejaVu font is required for recognizer data: {key}")


def render_sample(sample: dict[str, object]) -> Image.Image:
    text = str(sample["text"])
    font = ImageFont.truetype(str(resolve_font(str(sample["font"]))), int(sample["size"]))
    spacing, blur, pad = int(sample["spacing"]), float(sample.get("blur", 0.0)), 8
    dummy = Image.new("L", (10, 10), 255); draw = ImageDraw.Draw(dummy)
    advances = [math.ceil(draw.textlength(char, font=font)) for char in text]
    image = Image.new("L", (sum(advances) + spacing * max(0, len(text) - 1) + 2 * pad, int(sample["size"]) + 2 * pad + 12), 255)
    draw = ImageDraw.Draw(image); x = pad
    for char, advance in zip(text, advances, strict=True):
        draw.text((x, pad), char, font=font, fill=0); x += advance + spacing
    pixels = image.load(); xs: list[int] = []; ys: list[int] = []
    for y in range(image.height):
        for x in range(image.width):
            if pixels[x, y] < 250: xs.append(x); ys.append(y)
    if xs:
        image = image.crop((max(0, min(xs)-pad), max(0, min(ys)-pad), min(image.width, max(xs)+pad+1), min(image.height, max(ys)+pad+1)))
    if blur: image = image.filter(ImageFilter.GaussianBlur(blur))
    return image


def png_bytes(image: Image.Image) -> bytes:
    buffer = io.BytesIO(); image.save(buffer, format="PNG", compress_level=9); return buffer.getvalue()


def sample_sha256(sample: dict[str, object]) -> str:
    return hashlib.sha256(png_bytes(render_sample(sample))).hexdigest()


def _expand_manifest(payload: dict[str, object]) -> dict[str, object]:
    if "samples" in payload:
        return payload
    split = str(payload["split"]); variants = int(payload["variants_per_token"]); fonts = list(FONT_CANDIDATES); samples = []
    for i, token in enumerate(payload["tokens"]):
        for v in range(variants):
            sample = {
                "id": f"{split}-{i:03d}-v{v}", "text": token["text"], "kind": token["kind"], "expected_abstain": bool(token["expected_abstain"]),
                "font": fonts[(i + 2 * v) % len(fonts)], "size": [30, 34, 38][(i + v) % 3], "spacing": [1, 2, 3][(i + 2 * v) % 3], "blur": [0.0, 0.15][v % 2],
            }
            sample["sha256"] = sample_sha256(sample); samples.append(sample)
    actual = hashlib.sha256("".join(sample["sha256"] for sample in samples).encode()).hexdigest()
    if actual != payload["expanded_samples_sha256"]:
        raise RuntimeError(f"Recognizer split hash mismatch for {split}: {actual} != {payload['expanded_samples_sha256']}")
    expanded = dict(payload); expanded["samples"] = samples; return expanded


def load_manifest(path: Path) -> dict[str, object]:
    return _expand_manifest(json.loads(path.read_text(encoding="utf-8")))


def verify_manifest(path: Path) -> None:
    manifest = load_manifest(path)
    for sample in manifest["samples"]:
        actual = sample_sha256(sample)
        if actual != sample["sha256"]:
            raise RuntimeError(f"Recognizer sample hash mismatch for {sample['id']}: {actual} != {sample['sha256']}")


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("manifest", type=Path); parser.add_argument("--output-dir", type=Path); parser.add_argument("--verify-only", action="store_true"); args = parser.parse_args(); manifest = load_manifest(args.manifest)
    if args.verify_only: verify_manifest(args.manifest); return
    if args.output_dir is None: raise SystemExit("--output-dir is required unless --verify-only is used.")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for sample in manifest["samples"]: render_sample(sample).save(args.output_dir / f"{sample['id']}.png", format="PNG", compress_level=9)
    verify_manifest(args.manifest)


if __name__ == "__main__": main()

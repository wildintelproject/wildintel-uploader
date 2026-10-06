"""Makes a camera-trap deployment of sample images to try the wizard with.

    uv run python tools/make_example_deployment.py                 # examples/deployment_example_3000, 3000 images
    uv run python tools/make_example_deployment.py DIR -n 500

The images are small, different from each other, and numbered in the order they were taken
(IMG_0001.JPG…). Each has the camera's make, model and serial number and its capture date in
its EXIF, like a real camera trap's — the camera is a Reconyx HyperFire 2, serial P800HG08.
The shots come in bursts of three, a second apart, spread over a deployment of six weeks."""
from __future__ import annotations

import argparse
import random
from datetime import datetime, timedelta
from pathlib import Path

from PIL import Image, ImageDraw

MAKE, MODEL, SERIAL = "RECONYX", "HyperFire 2 HF2X", "P800HG08"
START = datetime(2025, 5, 1, 9, 0, 0)
DAYS = 42
BURST = 3
# EXIF tags: Make, Model, DateTime (IFD0); DateTimeOriginal, DateTimeDigitized, BodySerialNumber (Exif IFD).
MAKE_TAG, MODEL_TAG, DATETIME_TAG = 271, 272, 306
DATETIME_ORIGINAL, DATETIME_DIGITIZED, BODY_SERIAL = 36867, 36868, 42033


def capture_times(count: int, rng: random.Random) -> list[datetime]:
    """`count` times, in order: bursts of BURST shots, a second apart, at random moments of the deployment."""
    bursts = -(-count // BURST)
    starts = sorted(START + timedelta(seconds=rng.randrange(DAYS * 86400)) for _ in range(bursts))
    for i in range(1, bursts):  # a burst never overlaps the one before, so the order of the names is the order in time
        starts[i] = max(starts[i], starts[i - 1] + timedelta(seconds=BURST + 1))
    return [s + timedelta(seconds=k) for s in starts for k in range(BURST)][:count]


def make_image(path: Path, number: int, taken: datetime, rng: random.Random, size: tuple[int, int]) -> None:
    shade = rng.randrange(40, 200)
    img = Image.new("RGB", size, (shade, shade + 20 if shade < 180 else shade, shade // 2))
    draw = ImageDraw.Draw(img)
    for _ in range(12):  # something different in every image, so none is a duplicate
        x, y = rng.randrange(size[0]), rng.randrange(size[1])
        r = rng.randrange(10, 60)
        draw.ellipse((x - r, y - r, x + r, y + r), fill=tuple(rng.randrange(256) for _ in range(3)))
    draw.text((12, 10), f"IMG_{number:04d}  {taken:%Y-%m-%d %H:%M:%S}", fill=(255, 255, 255))
    exif = img.getexif()
    exif[MAKE_TAG], exif[MODEL_TAG] = MAKE, MODEL
    exif[DATETIME_TAG] = taken.strftime("%Y:%m:%d %H:%M:%S")
    sub = exif.get_ifd(0x8769)
    sub[DATETIME_ORIGINAL] = sub[DATETIME_DIGITIZED] = taken.strftime("%Y:%m:%d %H:%M:%S")
    sub[BODY_SERIAL] = SERIAL
    img.save(path, quality=80, exif=exif)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("directory", nargs="?", type=Path, default=Path(__file__).resolve().parents[1] / "examples" / "deployment_example_3000")
    parser.add_argument("-n", "--images", type=int, default=3000)
    parser.add_argument("--width", type=int, default=640)
    parser.add_argument("--height", type=int, default=360)
    args = parser.parse_args()

    rng = random.Random(3000)  # the same images every time
    args.directory.mkdir(parents=True, exist_ok=True)
    for number, taken in enumerate(capture_times(args.images, rng), start=1):
        make_image(args.directory / f"IMG_{number:04d}.JPG", number, taken, rng, (args.width, args.height))
    print(f"{args.images} images in {args.directory} — {MAKE} {MODEL}, serial {SERIAL}")


if __name__ == "__main__":
    main()

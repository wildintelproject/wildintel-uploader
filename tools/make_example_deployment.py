"""Makes a camera-trap deployment of sample images to try the wizard with.

    uv run python tools/make_example_deployment.py                 # examples/deployment_example_3000, 3000 images
    uv run python tools/make_example_deployment.py DIR -n 500
    uv run python tools/make_example_deployment.py --faulty        # examples/deployment_example_3000_faulty

The images are small, different from each other, and numbered in the order they were taken
(IMG_0001.JPG…). Each has the camera's make, model and serial number and its capture date in
its EXIF, like a real camera trap's — the camera is a Reconyx HyperFire 2, serial P800HG08.
The shots come in bursts of three, a second apart, spread over a deployment of six weeks.

With --faulty the same deployment comes with problems for every validation to find — about 14 % of the images:
corrupted (cut short, or empty), duplicated (copies and backups), out of order (the date of a shot earlier than
the one before), without a capture date, without camera model or serial number, taken by a second camera,
and some in a subfolder. The total is still the number of images asked for."""
from __future__ import annotations

import argparse
import random
import shutil
from datetime import datetime, timedelta
from pathlib import Path

from PIL import Image, ImageDraw

MAKE, MODEL, SERIAL = "RECONYX", "HyperFire 2 HF2X", "P800HG08"
OTHER_MAKE, OTHER_MODEL, OTHER_SERIAL = "BUSHNELL", "Core DS-4K", "BN4K20931"
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


def make_image(path: Path, number: int, taken: datetime | None, rng: random.Random, size: tuple[int, int], *,
               make: str | None = MAKE, model: str | None = MODEL, serial: str | None = SERIAL) -> None:
    """One image. A None for taken, make, model or serial leaves that out of its EXIF."""
    shade = rng.randrange(40, 200)
    img = Image.new("RGB", size, (shade, shade + 20 if shade < 180 else shade, shade // 2))
    draw = ImageDraw.Draw(img)
    for _ in range(12):  # something different in every image, so none is a duplicate
        x, y = rng.randrange(size[0]), rng.randrange(size[1])
        r = rng.randrange(10, 60)
        draw.ellipse((x - r, y - r, x + r, y + r), fill=tuple(rng.randrange(256) for _ in range(3)))
    draw.text((12, 10), f"IMG_{number:04d}  {taken:%Y-%m-%d %H:%M:%S}" if taken else f"IMG_{number:04d}", fill=(255, 255, 255))
    exif = img.getexif()
    if make:
        exif[MAKE_TAG] = make
    if model:
        exif[MODEL_TAG] = model
    sub = exif.get_ifd(0x8769)
    if taken:
        exif[DATETIME_TAG] = taken.strftime("%Y:%m:%d %H:%M:%S")
        sub[DATETIME_ORIGINAL] = sub[DATETIME_DIGITIZED] = taken.strftime("%Y:%m:%d %H:%M:%S")
    if serial:
        sub[BODY_SERIAL] = serial
    img.save(path, quality=80, exif=exif)


def plan_faults(count: int, rng: random.Random) -> dict[str, list[int]]:
    """Which images (numbered from 1) get which problem — a different set for each, so a check finds just its own."""
    share = lambda part: max(1, round(count * part))  # noqa: E731
    pool = list(range(1, count + 1))
    rng.shuffle(pool)

    def take(n: int) -> list[int]:
        taken, pool[:] = pool[:n], pool[n:]
        return sorted(taken)

    return {
        "corrupted": take(share(0.020)), "empty": take(share(0.003)), "duplicated": take(share(0.025)), "no_date": take(share(0.015)),
        "no_model": take(share(0.012)), "no_serial": take(share(0.015)), "other_camera": take(share(0.050)),
        "subfolder": take(share(0.008)), "swapped": take(share(0.012) * 2),
    }


def main_faulty(directory: Path, count: int, size: tuple[int, int], rng: random.Random) -> None:
    faults = plan_faults(count, rng)
    duplicates = len(faults["duplicated"])
    base = count - duplicates  # the copies are files too: the total stays `count`
    faults = {k: [n for n in v if n <= base] for k, v in faults.items()}
    times = capture_times(base, rng)
    # Out of order: the dates of a pair of numbered neighbours are swapped — the later number was shot earlier.
    for a, b in zip(faults["swapped"][::2], faults["swapped"][1::2]):
        times[a - 1], times[b - 1] = times[b - 1], times[a - 1]
    (directory / "backup").mkdir(parents=True, exist_ok=True)
    corrupted, empty, no_date = set(faults["corrupted"]), set(faults["empty"]), set(faults["no_date"])
    for number, taken in enumerate(times, start=1):
        folder = directory / "backup" if number in faults["subfolder"] else directory
        path = folder / f"IMG_{number:04d}.JPG"
        other = number in faults["other_camera"]
        make_image(
            path, number, None if number in no_date else taken, rng, size,
            make=OTHER_MAKE if other else MAKE,
            model=None if number in faults["no_model"] else (OTHER_MODEL if other else MODEL),
            serial=None if number in faults["no_serial"] else (OTHER_SERIAL if other else SERIAL),
        )
        if number in empty:
            path.write_bytes(b"")
        elif number in corrupted:
            path.write_bytes(path.read_bytes()[: path.stat().st_size // 3])  # cut short: it doesn't decode
    # Duplicates: copies of images that are fine, named as people name them.
    healthy = [n for n in range(1, base + 1) if not {n} & (corrupted | empty | set(faults["subfolder"]))]
    for i, number in enumerate(rng.sample(healthy, duplicates)):
        source = directory / f"IMG_{number:04d}.JPG"
        shutil.copy2(source, directory / (f"IMG_{number:04d} (copy).JPG" if i % 2 else f"IMG_{number:04d}_bak.JPG"))
    print(f"{count} files in {directory}: " + ", ".join(f"{len(v)} {k.replace('_', ' ')}" for k, v in faults.items()))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("directory", nargs="?", type=Path, help="default: examples/deployment_example_3000 (…_faulty with --faulty)")
    parser.add_argument("--faulty", action="store_true", help="with problems for the validations to find: corrupted, duplicated, out of order…")
    parser.add_argument("-n", "--images", type=int, default=3000)
    parser.add_argument("--width", type=int, default=640)
    parser.add_argument("--height", type=int, default=360)
    args = parser.parse_args()

    rng = random.Random(3000)  # the same images every time
    args.directory = args.directory or Path(__file__).resolve().parents[1] / "examples" / ("deployment_example_3000_faulty" if args.faulty else "deployment_example_3000")
    args.directory.mkdir(parents=True, exist_ok=True)
    if args.faulty:
        return main_faulty(args.directory, args.images, (args.width, args.height), rng)
    for number, taken in enumerate(capture_times(args.images, rng), start=1):
        make_image(args.directory / f"IMG_{number:04d}.JPG", number, taken, rng, (args.width, args.height))
    print(f"{args.images} images in {args.directory} — {MAKE} {MODEL}, serial {SERIAL}")


if __name__ == "__main__":
    main()

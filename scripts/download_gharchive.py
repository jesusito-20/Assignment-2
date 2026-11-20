"""Download the hourly GH Archive input for the unmodified course preprocessor."""

import argparse
import json
import shutil
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from http.client import HTTPException
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen


HOUR = timedelta(hours=1)
EARLIEST = datetime(2025, 12, 1, tzinfo=timezone.utc)
LATEST = datetime(2026, 11, 21, 15, tzinfo=timezone.utc)
DEFAULT_START = "2026-10-03T16:00Z"
DEFAULT_END = "2026-11-20T15:00Z"
BASE_URL = "https://data.gharchive.org/"


def utc_hour(value):
    try:
        hour = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise argparse.ArgumentTypeError(str(error)) from error
    if hour.utcoffset() != timedelta(0) or hour != hour.replace(minute=0, second=0, microsecond=0):
        raise argparse.ArgumentTypeError("Use a whole UTC hour, for example 2026-10-03T16:00Z.")
    return hour


def filename(hour):
    return f"{hour:%Y-%m-%d}-{hour.hour}.json.gz"


def has_gzip_header(path):
    if not path.is_file() or path.stat().st_size < 18:
        return False
    with path.open("rb") as stream:
        return stream.read(2) == b"\x1f\x8b"


def download(hour, folder):
    target = folder / filename(hour)
    if has_gzip_header(target):
        return "present"
    temporary = target.with_suffix(".part")
    request = Request(BASE_URL + target.name, headers={"User-Agent": "BigData2026-Assignment2/1.0"})
    for attempt in range(4):
        try:
            with urlopen(request, timeout=45) as response, temporary.open("wb") as stream:
                shutil.copyfileobj(response, stream, length=1024 * 256)
                expected_size = response.headers.get("Content-Length")
            if expected_size is not None and temporary.stat().st_size != int(expected_size):
                raise OSError(f"Incomplete download of {target.name}")
            if not has_gzip_header(temporary):
                raise OSError(f"Invalid gzip header in {target.name}")
            temporary.replace(target)
            return "present"
        except (OSError, HTTPException) as error:
            temporary.unlink(missing_ok=True)
            if isinstance(error, HTTPError) and error.code in (404, 410):
                return "missing"
            if attempt == 3:
                return f"failed: {error}"
            time.sleep(2 ** attempt)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw", type=Path, default=Path("gharchive"))
    parser.add_argument("--start", type=utc_hour, default=DEFAULT_START, help="First UTC hour, inclusive.")
    parser.add_argument("--end", type=utc_hour, default=DEFAULT_END, help="UTC end hour, exclusive.")
    parser.add_argument("--workers", type=int, default=12)
    args = parser.parse_args()
    if not EARLIEST <= args.start < args.end <= LATEST:
        parser.error("Use a range after 2025-12-01 and end by 2026-11-21T15:00Z, before the deadline.")
    if args.workers < 1:
        parser.error("--workers must be positive")
    hours = [args.start + offset * HOUR for offset in range((args.end - args.start) // HOUR)]
    args.raw.mkdir(parents=True, exist_ok=True)
    expected_names = {filename(hour) for hour in hours}
    extras = sorted(path.name for path in args.raw.rglob("*.json.gz")
                    if path.parent != args.raw or path.name not in expected_names)
    if extras:
        parser.error(f"Use a dedicated input folder for this range. Unexpected archives include {extras[:3]}.")

    print(f"Checking or downloading {len(hours):,} UTC hours in {args.raw}.", flush=True)
    status = {}
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        for index, (hour, result) in enumerate(
            zip(hours, pool.map(lambda hour: download(hour, args.raw), hours)), start=1
        ):
            status[hour.isoformat()] = result
            if result.startswith("failed:"):
                print(f"{filename(hour)}: {result}", flush=True)
            if index % 48 == 0 or index == len(hours):
                print(f"{index:,}/{len(hours):,} hours checked.", flush=True)

    present = [hour for hour, result in status.items() if result == "present"]
    missing = [hour for hour, result in status.items() if result == "missing"]
    failed = {hour: result for hour, result in status.items() if result.startswith("failed:")}
    manifest = {
        "source": BASE_URL,
        "start_utc": args.start.isoformat(),
        "end_utc_exclusive": args.end.isoformat(),
        "present_utc": present,
        "missing_utc": missing,
        "failed_utc": failed,
    }
    manifest_path = args.raw / "hours.json"
    temporary = manifest_path.with_suffix(".part")
    temporary.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    temporary.replace(manifest_path)
    print(f"{len(present):,} available, {len(missing):,} unavailable, {len(failed):,} failed.")
    if failed or not present:
        raise SystemExit("Run the same command again to retry. Completed archives will be reused.")


if __name__ == "__main__":
    main()

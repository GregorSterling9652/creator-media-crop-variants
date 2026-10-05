from __future__ import annotations

import argparse
import json
import mimetypes
import os
from pathlib import Path

import httpx


def main() -> None:
    parser = argparse.ArgumentParser(description="Submit one creator image")
    parser.add_argument("image", type=Path)
    parser.add_argument("--creator", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--width", required=True, type=int)
    parser.add_argument("--height", required=True, type=int)
    args = parser.parse_args()

    service_url = os.environ.get("MEDIA_VARIANT_SERVICE", "http://127.0.0.1:8000")
    content_type = mimetypes.guess_type(args.image.name)[0] or "application/octet-stream"
    with args.image.open("rb") as image_file:
        response = httpx.request(
            method="POST",
            url=f"{service_url}/creator-assets",
            data={
                "creator_id": args.creator,
                "title": args.title,
                "source_width": str(args.width),
                "source_height": str(args.height),
            },
            files={"image": (args.image.name, image_file, content_type)},
            timeout=120.0,
        )
    response.raise_for_status()
    print(json.dumps(response.json(), indent=2))


if __name__ == "__main__":
    main()

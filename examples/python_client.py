"""
BelegPilot Python Client Example

Usage:
    python examples/python_client.py --api-key riq_live_xxx --image receipt.jpg
    python examples/python_client.py --api-key riq_live_xxx --image receipt.jpg --server https://BelegPilot.ozkannceylan.dev
"""

import argparse
import httpx
import json
import sys


def extract_receipt(
    server_url: str,
    api_key: str,
    image_path: str,
    force_ocr: bool = False,
) -> dict:
    """Extract data from a receipt image.

    Args:
        server_url: BelegPilot server URL (e.g., http://localhost:8000)
        api_key: API key (riq_live_xxx)
        image_path: Path to receipt image file
        force_ocr: Skip VLM and use OCR only

    Returns:
        Extraction result as dict
    """
    with open(image_path, "rb") as f:
        response = httpx.post(
            f"{server_url}/api/v1/extract",
            headers={"X-API-Key": api_key},
            files={"file": (image_path, f)},
            params={"force_ocr": force_ocr},
            timeout=60.0,
        )

    response.raise_for_status()
    return response.json()


def main():
    parser = argparse.ArgumentParser(description="BelegPilot Python Client")
    parser.add_argument("--server", default="http://localhost:8000", help="Server URL")
    parser.add_argument("--api-key", required=True, help="API key")
    parser.add_argument("--image", required=True, help="Path to receipt image")
    parser.add_argument("--force-ocr", action="store_true", help="Force OCR mode")
    args = parser.parse_args()

    try:
        result = extract_receipt(
            server_url=args.server,
            api_key=args.api_key,
            image_path=args.image,
            force_ocr=args.force_ocr,
        )
        print(json.dumps(result, indent=2, default=str))
    except httpx.HTTPStatusError as e:
        print(f"Error {e.response.status_code}: {e.response.text}", file=sys.stderr)
        sys.exit(1)
    except FileNotFoundError:
        print(f"File not found: {args.image}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

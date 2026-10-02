import argparse
import csv
import json
import re
import time
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

from curl_cffi import requests

BASE_URL = "https://www.cellarbrations.com.au"
STORE_ID = "144981"
CATEGORY_URL = (
    f"{BASE_URL}/sm/delivery/rsid/{STORE_ID}/categories/spirits/"
    "whisky-id-Whisky_Food"
)
PRODUCT_API = "https://storefrontgateway.cellarbrations.com.au"
TIMEOUT = 30
PAGE_SIZE = 30
FIELDS = [
    "product_name",
    "product_id",
    "image",
    "url",
    "price",
    "scraped_at",
    "description",
    "measuring_unit",
    "units",
]


def clean(value: str) -> str:
    return " ".join(re.sub(r"<[^>]+>", " ", value or "").split())


def slugify(value: str) -> str:
    value = (
        unicodedata.normalize("NFKD", value)
        .encode("ascii", "ignore")
        .decode("ascii")
    )
    return re.sub(r"[^a-zA-Z0-9]+", "-", value.lower()).strip("-")


def build_product_url(product_name: str, product_id: str) -> str:
    return (
        f"{BASE_URL}/sm/delivery/rsid/{STORE_ID}/product/"
        f"{slugify(product_name)}-id-{product_id}"
    )


def extract_preloaded_state(html: str) -> dict:
    match = re.search(
        r"window\.__PRELOADED_STATE__\s*=\s*(\{.*?\})\s*;",
        html,
        re.DOTALL,
    )
    if not match:
        raise RuntimeError("window.__PRELOADED_STATE__ not found in category HTML")
    return json.loads(match.group(1))


def image_urls(value: object) -> list[str]:
    if isinstance(value, str):
        return [value] if value else []
    if isinstance(value, list):
        urls = []
        for item in value:
            urls.extend(image_urls(item))
        return list(dict.fromkeys(urls))
    if isinstance(value, dict):
        urls = []
        for item in value.values():
            urls.extend(image_urls(item))
        return list(dict.fromkeys(urls))
    return []


def scrape() -> list[dict[str, str]]:
    session = requests.Session(impersonate="chrome")
    session.headers.update(
        {
            "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-AU,en;q=0.9",
            "Referer": BASE_URL + "/",
        }
    )

    rows = []
    page = 1
    skip = 0

    while True:
        page_url = (
            CATEGORY_URL
            if page == 1
            else f"{CATEGORY_URL}?page={page}&skip={skip}"
        )
        response = session.get(page_url, timeout=TIMEOUT)
        response.raise_for_status()

        state = extract_preloaded_state(response.text)
        search = state.get("search", {})
        product_ids = search.get("products", {}).get("category", [])
        product_dictionary = search.get("productCardDictionary", {})
        if not product_ids:
            break

        pagination = search.get("pagination", {}).get("category", {})
        total_items = pagination.get("totalItems", 0)

        for product_id in product_ids:
            product = product_dictionary.get(str(product_id))
            if not product:
                continue

            sku = str(product.get("sku") or product_id)
            product_response = session.get(
                f"{PRODUCT_API}/api/stores/{STORE_ID}/products/{sku}",
                timeout=TIMEOUT,
            )
            product_response.raise_for_status()
            full_product = product_response.json()
            time.sleep(0.2)

            product_name = str(
                full_product.get("name") or product.get("name") or ""
            )
            product_images = full_product.get("primaryImage") or product.get("image")
            size = full_product.get("unitsOfSize") or {}
            image_list = image_urls(product_images)

            rows.append(
                {
                    "product_name": product_name,
                    "product_id": sku,
                    "image": json.dumps(image_list, ensure_ascii=False),
                    "url": build_product_url(product_name, sku),
                    "price": str(
                        full_product.get("price") or product.get("price") or ""
                    ),
                    "scraped_at": datetime.now(timezone.utc).isoformat(),
                    "description": clean(
                        full_product.get("description")
                        or product.get("description")
                        or ""
                    ),
                    "measuring_unit": str(size.get("abbreviation") or ""),
                    "units": str(size.get("size") or ""),
                }
            )

        if total_items and len(rows) >= total_items:
            break

        skip += PAGE_SIZE
        page += 1

    if not rows:
        raise RuntimeError(f"No products found at {CATEGORY_URL}")
    return rows


def write_csv(rows: list[dict[str, str]], output_path: str) -> None:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    with output.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows)} rows to {output}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Scrape Cellarbrations whisky products."
    )
    parser.add_argument(
        "--output",
        default="cellarbrations_whisky.csv",
        help="Output CSV path.",
    )
    args = parser.parse_args()
    write_csv(scrape(), args.output)


if __name__ == "__main__":
    main()

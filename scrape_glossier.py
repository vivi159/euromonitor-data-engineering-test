import argparse
import csv
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.glossier.com"
LOCALES = {"in": "/en-in", "us": ""}
FIELDS = [
    "product_name",
    "product_id",
    "image",
    "url",
    "price",
    "scraped_at",
    "description",
]
REQUEST_TIMEOUT = 30
REQUEST_DELAY = 0.2
PAGE_SIZE = 250


def get_json(session: requests.Session, url: str, **kwargs) -> dict:
    response = session.get(url, timeout=REQUEST_TIMEOUT, **kwargs)
    response.raise_for_status()

    try:
        return response.json()
    except ValueError as exc:
        raise RuntimeError(
            f"Expected JSON response but received non-JSON content from {response.url}"
        ) from exc


def clean_html(value: str) -> str:
    if not value:
        return ""
    return BeautifulSoup(value, "html.parser").get_text(" ", strip=True)


def get_locale_prefix(locale: str) -> str:
    if locale not in LOCALES:
        raise ValueError(f"Unsupported locale: {locale}")
    return LOCALES[locale]


def scrape(locale: str, variants: bool = False) -> list[dict]:
    prefix = get_locale_prefix(locale)
    collection_url = f"{BASE_URL}{prefix}/collections/all/products.json"

    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/154.0.0.0 Safari/537.36",
            "Accept": "application/json, text/html;q=0.9, */*;q=0.8",
        }
    )

    products = []
    page = 1

    while True:
        try:
            data = get_json(session, collection_url, params={"limit": PAGE_SIZE, "page": page})
        except requests.RequestException as exc:
            raise RuntimeError(f"Failed to fetch collection page {page}: {exc}") from exc

        batch = data.get("products", [])
        if not batch:
            break

        products.extend(batch)
        page += 1
        time.sleep(REQUEST_DELAY)

    if not products:
        raise RuntimeError(f"No products found at {collection_url}")

    scraped_at = datetime.now(timezone.utc).isoformat()
    rows = []

    for product in products:
        handle = product.get("handle")
        if not handle:
            continue

        detail_url = f"{BASE_URL}{prefix}/products/{handle}.js"
        product_url = f"{BASE_URL}{prefix}/products/{handle}"

        try:
            detail = get_json(session, detail_url)
        except (requests.RequestException, RuntimeError):
            continue

        options = detail.get("variants") or product.get("variants") or [{}]
        selected_variants = options if variants else options[:1]
        images = (detail.get("images") or product.get("images") or [])

        image_urls = [image for image in images if isinstance(image, str)]
        description = clean_html(detail.get("description") or product.get("body_html") or "")

        for variant in selected_variants:
            if variants:
                product_id = variant.get("id") or product.get("id") or handle
                price = variant.get("price", "")
            else:
                product_id = product.get("id") or handle
                price = variant.get("price") or product.get("price") or ""

            rows.append(
                {
                    "product_name": detail.get("title") or product.get("title") or "",
                    "product_id": str(product_id),
                    "image": json.dumps( image_urls,ensure_ascii=False,),
                    "url": product_url,
                    "price": str(price),
                    "scraped_at": scraped_at,
                    "description": description,
                }
            )

        time.sleep(REQUEST_DELAY)

    return rows


def write_csv(rows: list[dict], output_path: str) -> None:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    with output.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows)} rows to {output}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Scrape Glossier products.")
    parser.add_argument("--locale", choices=LOCALES, default="in")
    parser.add_argument("--variants", action="store_true")
    parser.add_argument("--output", default="data/glossier_india.csv")
    args = parser.parse_args()

    rows = scrape(locale=args.locale, variants=args.variants)
    write_csv(rows, args.output)


if __name__ == "__main__":
    main()

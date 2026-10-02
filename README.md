# Euromonitor Data Engineer Assignment

Python implementations of the Glossier and Cellarbrations scraping exercises.

## Requirements

- Python 3.10 or later
- Internet access

Install dependencies from the project directory:

```powershell
python -m pip install -r requirements.txt
```

## Exercise 1: Glossier

Scrape the India catalog:

```powershell
python .\scrape_glossier.py --locale in --output data\glossier_india.csv
```

Scrape the US catalog:

```powershell
python .\scrape_glossier.py --locale us --output data\glossier_us.csv
```

Create one row per variant:

```powershell
python .\scrape_glossier.py --locale in --variants --output data\glossier_india_variants.csv
```

The standard output contains:

- `product_name`
- `product_id`
- `image`
- `url`
- `price`
- `scraped_at`
- `description`

Images are written as a JSON-encoded array of image URLs in the CSV cell.

## Exercise 2: Cellarbrations

The scraper targets the whisky category for store `144981`:

<https://www.cellarbrations.com.au/sm/delivery/rsid/144981/categories/spirits/whisky-id-Whisky_Food>

Run the scraper:

```powershell
python .\scrape_cellarbrations.py --output data\cellarbrations_whisky.csv
```

The output contains:

- `product_name`
- `product_id`
- `image`
- `url`
- `price`
- `scraped_at`
- `description`
- `measuring_unit`
- `units`

The image field is a JSON-encoded array of URL strings. `measuring_unit` and
`units` are read from the product API's `unitsOfSize` data.

## Approach

Glossier uses public Shopify collection and product JSON endpoints.

Cellarbrations uses direct HTTP requests with `curl_cffi` Chrome
impersonation. Product cards are discovered from the category response, and
the storefront API supplies product details. The scraper does not hard-code
browser cookies or session tokens.

Browser automation is not used: the required listing and product data are
available through HTTP responses, so launching a browser and loading page
assets would add resource cost without helping this extraction. See
[`notes.txt`](notes.txt) for the evidence, tradeoffs, assumptions, and AI
usage disclosure.

## Validation

After running each scraper, inspect:

- Output row count and duplicate `product_id` values.
- Empty descriptions, image arrays, and prices.
- Product URLs.
- Cellarbrations `measuring_unit` and `units` values.

The catalog can change over time, so row counts and field values may vary.

# German Handwerk Leads Scraper

Automated lead generation for German blue-collar trades (Handwerk) using Google Places API. Built for HeyKiki's AI voice-bot outreach: the scraper produces a CSV of business contacts that feeds a daily email campaign (1,000–2,000 emails/day) targeting tradespeople across Germany.

---

## Goal

Collect 100,000 unique Handwerk business leads across Germany at a target budget of ~€2,000 (~$2,100). Each lead contains: business name, trade category, generated email, website, phone number, and full address. Leads are deduplicated and exported as a single CSV, ready to be loaded into an email/outreach tool.

---

## Why Google Places API

The project originally used Playwright to scrape Gelbe Seiten (gelbeseiten.de). That approach was completely abandoned:

- Websites were hidden behind JavaScript click-handlers — 0% extraction rate after multiple attempts
- No reliable way to get phone numbers or addresses without rendering full pages
- Brittle and slow (5+ hours for a single run)

Google Places API replaced it entirely. It provides verified business data (name, website, phone, address) in a single API call per business, with 90%+ website completion in practice.

---

## Active Files

| File | Role |
|------|------|
| `scraper_v2.py` | **Main scraper — this is the only file you run** |
| `checkpoint_manager.py` | Resume/progress system (used by scraper_v2) |
| `config.py` | Categories, zip regions, API settings, costs |
| `requirements.txt` | Python dependencies |
| `.env` | API keys (created from `.env.example`) |

**Deprecated — do not use:**
- `scraper.py` — original v1 Google Places scraper, superseded by v2
- `scrape_munich_carpenters_roofers.py` — Munich-only script with a config bug, never worked correctly
- `SCRAPER_V2_USAGE.md` — outdated usage doc from before the bug-fix rounds

---

## Setup

### Prerequisites

- Python 3.10+
- Google Cloud account with billing enabled

### Google Cloud — required APIs

Both of these must be enabled or you will get `REQUEST_DENIED`:

1. **Places API** — business search and details
2. **Geocoding API** — city/zip-code to coordinates

Enable at: Google Cloud Console → APIs & Services → Library.

### Install

```bash
git clone https://github.com/imamber20/germanscrape.git
cd germanscrape
pip install -r requirements.txt
cp .env.example .env
# Edit .env — add your GOOGLE_PLACES_API_KEY
```

### `.env` contents

```
GOOGLE_PLACES_API_KEY=AIzaSyXXXXXXXXXXXXXXXXXXXXXXXX   # required
OPENAI_API_KEY=sk-XXXXXXXXX                             # optional, unused currently
```

---

## How to Run — All Scenarios

### Quick sanity check (20 leads, ~$0.40)

```bash
python scraper_v2.py --micro-test --categories dachdecker --cities münchen --verbose
```

### Interactive mode — pick category and location from menus

```bash
python scraper_v2.py --interactive --micro-test
```

Displays all 10 categories with their German keywords. Accepts city names or individual 5-digit zip codes at the location prompt.

### Specific category + city (command-line, no menus)

```bash
python scraper_v2.py --categories dachdecker,zimmereien --cities münchen,berlin --max-leads 100 --verbose
```

### Multiple zip codes

Zip codes must be individual 5-digit values, comma-separated. Ranges like `80000-80999` are **not** supported yet — they get geocoded as a literal string (see Known Limitations).

```bash
python scraper_v2.py --categories dachdecker --cities 80331,80333,80336 --max-leads 50 --verbose
```

### Resume an interrupted run

If a run is interrupted (Ctrl+C or crash), resume with the exact same flags plus `--resume`:

```bash
# Original command:
python scraper_v2.py --categories dachdecker --cities 80331,80333,80336 --max-leads 50 --verbose

# After interruption — same flags, add --resume:
python scraper_v2.py --categories dachdecker --cities 80331,80333,80336 --max-leads 50 --resume --verbose
```

Resume behaviour:
- Loads `progress.json` and prints how many businesses were already processed
- Re-runs Nearby Search (cheap, ~$0.03/page) to get the place_id list
- Skips every place_id already in the checkpoint — zero Place Details calls on duplicates
- Stops when total leads (previous + new) reaches `--max-leads`

### All categories, all regions (production run)

Omit `--categories` and `--cities` to use every category and every city defined in `config.py`:

```bash
python scraper_v2.py --max-leads 5000 --verbose
```

---

## CLI Reference

| Flag | Description |
|------|-------------|
| `--micro-test` | Cap at 20 leads. Safe for iteration (~$0.40). Sets `--max-leads 20` automatically. |
| `--categories` | Comma-separated category keys (e.g. `dachdecker,zimmereien`). Omit for all. |
| `--cities` | Comma-separated city names or 5-digit zip codes. Omit for all cities in config. |
| `--max-leads N` | Stop after N leads are collected (across all categories/cities). |
| `--resume` | Load checkpoint and continue. Must use same `--categories` and `--cities` as the original run. |
| `--interactive` | Show category and location menus instead of requiring CLI flags. |
| `--verbose` | DEBUG-level logging to stdout and log file. urllib3 is silenced even in verbose mode to prevent API key leaking into logs. |

---

## Categories

Defined in `config.py`. Each has a list of German keywords used in the Google Nearby Search query, and a Google Places type that narrows results.

| Key | Display Name | Keywords | Google Type |
|-----|-------------|----------|-------------|
| `dachdecker` | Dachdecker | Dachdecker, Dachdeckerei, Dachsanierung, Dachbau | roofing_contractor |
| `heizungsbauer` | Heizungsbauer | Heizungsbauer, Heizungsbau, Heizungstechnik | plumber |
| `sanitärinstallateure` | Sanitärinstallateure | Sanitärinstallateur, Sanitärtechnik, Badezimmerbau | plumber |
| `elektrotechnik` | Elektrotechnik | Elektrotechnik, Elektroinstallation, Elektriker | electrician |
| `malerbetriebe` | Malerbetriebe | Malerbetrieb, Malerarbeiten, Fassadenanstrich | painter |
| `fliesenleger` | Fliesenleger | Fliesenleger, Fliesenverlegung, Badfliesen | general_contractor |
| `bauunternehmen` | Bauunternehmen | Bauunternehmen, Baufirma, Hochbauunternehmen | general_contractor |
| `trockenbaufirmen` | Trockenbaufirmen | Trockenbau, Gipskartonbau, Innenausbau | general_contractor |
| `zimmereien` | Zimmereien | Zimmerei, Zimmerer, Schreiner, Tischler, Holzbau, Dachstuhlbau, Holzkonstruktion, Zimmermannsbetrieb | general_contractor |
| `abrissunternehmen` | Abrissunternehmen | Abrissunternehmen, Abbruchfirma, Abbrucharbeiten | general_contractor |

---

## Output

CSV exported to `output/leads_YYYYMMDD_HHMMSS.csv`. Encoded as UTF-8-BOM so German characters (ä, ö, ü, ß) display correctly when opened directly in Excel.

| Column | Source | Notes |
|--------|--------|-------|
| `name` | Google Place Details | Authoritative business name |
| `category` | Scraper | Which category key triggered this result |
| `email` | Generated | `info@` + domain extracted from website. See Known Limitations. |
| `website` | Google Place Details | The business's own website URL |
| `phone` | Google Place Details | Formatted phone number |
| `address` | Google Place Details | Full street address including city and postal code |

Deduplication runs before export: primary key is the website URL (lowercased), fallback is the business name. One duplicate is typically removed per 20-lead batch.

---

## Cost Structure

Per-call costs from Google's pricing page, tracked in real time during every run:

| API Call | Cost | When it fires |
|----------|------|---------------|
| Geocoding | $0.005 | Once per city/zip code |
| Nearby Search | $0.032 | Once per page of results (up to 3 pages = 60 businesses) |
| Place Details | $0.017 | Once per business that passes the max_leads gate |

**Actual costs from completed test runs:**

| Test | Leads | Place Details calls | Total cost | Cost/lead |
|------|-------|---------------------|------------|-----------|
| Dachdecker München micro | 19 | 20 | $0.44 | $0.023 |
| Zimmereien München micro | 19 | 19 | $0.36 | $0.019 |
| Malerbetriebe interactive | 20 | 20 | $0.44 | $0.022 |
| Dachdecker 3 zip codes | 49 | 50 | $1.02 | $0.021 |

At $0.02/lead the 100K-lead target costs roughly **$2,000** — within the planned budget.

---

## How the Scraper Works Internally

1. **Geocode** each city/zip code to lat/lng via the Geocoding API
2. **Nearby Search** with the category's keywords + Google type + 50km radius. Paginates up to 3 pages (60 businesses max per search). 2-second sleep between pages as Google requires.
3. **Slot reservation** — before firing an expensive Place Details call, each worker thread atomically claims a slot under a `threading.Lock`. If `max_leads` is already reached, the thread returns immediately. This prevents the 25-thread pool from overshooting the lead cap.
4. **Place Details** — fetches name, website, phone, address for the business
5. **Email generation** — parses the website URL, strips `www.`, prepends `info@`
6. **Checkpoint** — `progress.json` tracks every processed `place_id`. Saved every 50 leads and on interrupt. On resume, all previously seen place_ids are skipped at zero API cost.
7. **Deduplicate + export** — removes duplicates by website/name, writes CSV

Parallel processing: 25 `ThreadPoolExecutor` workers fire Place Details calls concurrently. The googlemaps client's connection pool is sized to match (25), so no connections are discarded under load. Typical throughput: 20 Place Details calls complete in under 1 second.

---

## Checkpoint / Resume System

`progress.json` is written atomically (temp file + rename) so a crash mid-write can't corrupt it. It stores:

- `processed_place_ids` — set of every Google place_id that has been fully processed
- `stats` — cumulative API call counts, cost, leads per category, last-save timestamp

On `--resume`:
- The scraper loads the checkpoint and prints the summary
- `leads_collected` is restored from the category-count totals so `--max-leads` works correctly across interrupted runs
- The Nearby Search re-runs (cheap) to get the current place_id list; every id already in the checkpoint is skipped before any Place Details call is made

Without `--resume` the checkpoint is cleared at startup — every run starts fresh unless you explicitly opt in.

---

## Known Limitations

### Zip code ranges not supported
Entering `80000-80999` in the location prompt treats it as a literal city name, not a range. Google's geocoder happens to resolve it to the München area, so it works by accident. For reliable multi-zip coverage, enter individual codes: `80331,80333,80336`. Range expansion is planned but not yet implemented.

### Directory-site emails (~5–10% of leads)
Some businesses are listed on directory sites like `malerfinder.de` instead of having their own website. The email generator produces `info@malerfinder.de` for all of them — which is the directory's inbox, not the business's. These can be filtered post-export by checking for duplicate emails across different businesses, or flagged by detecting URL paths that look like directory listings (e.g. `/city/id-name`).

### Resume re-runs Nearby Search
On resume the scraper re-geocodes and re-searches each city/zip. This costs ~$0.07–0.10 per location in redundant API calls. The actual expensive calls (Place Details) are correctly skipped. Acceptable at current scale; search-result caching in the checkpoint is a possible future optimization.

### Google returns up to 60 businesses per search
Nearby Search maxes out at 3 pages × 20 results = 60 per keyword+location combo. To get more businesses in the same area, you need either additional keywords or overlapping search points (different zip codes). The checkpoint deduplicates place_ids across searches automatically.

---

## Troubleshooting

### `REQUEST_DENIED`
Both **Places API** and **Geocoding API** must be enabled in Google Cloud Console. Enabling one without the other produces this error on the missing API's calls. Wait 2–5 minutes after enabling for propagation.

### `Client.__init__() got an unexpected keyword argument 'session'`
The `googlemaps` library does not accept a `session` constructor argument. The connection pool is configured by mounting an `HTTPAdapter` on `client.session` after construction — this is already done in the current code.

### `KeyError: 'nearby_search_cost'`
A config key typo from an earlier version. The correct key is `google_nearby_search_cost`. Already fixed in current code. If you see this, you're running an old checkout.

### `Connection pool is full, discarding connection`
Means the googlemaps client's pool is smaller than the number of concurrent threads. Already fixed — pool size matches `concurrent_requests` (25). If you see this, you're running an old checkout.

### Only 1 lead exported despite 20 Place Details calls
A race condition from an earlier version where the result-collection loop broke on `leads_collected` (reservation count) instead of actual collected count. Already fixed. If you see this, you're running an old checkout.

---

## Project Structure

```
germanscrape/
├── scraper_v2.py              # Main scraper (the only file you run)
├── checkpoint_manager.py      # Resume / progress tracking
├── config.py                  # Categories, regions, settings, costs
├── requirements.txt           # pip dependencies
├── .env                       # API keys (gitignored)
├── .env.example               # Template for .env
├── README.md                  # This file
├── output/                    # Exported CSVs (gitignored)
├── logs/                      # Timestamped log files (gitignored)
├── progress.json              # Checkpoint file, auto-created at runtime
│
├── scraper.py                 # DEPRECATED — v1 scraper, do not use
├── scrape_munich_carpenters_roofers.py  # DEPRECATED — broken config override
└── SCRAPER_V2_USAGE.md        # DEPRECATED — outdated docs
```

---

## Test Results (all passing)

| # | Test | Command | Result |
|---|------|---------|--------|
| 1 | Dachdecker micro-test | `--micro-test --categories dachdecker --cities münchen` | 19 leads, 94.7% website, $0.44 |
| 2 | Zimmereien micro-test | `--micro-test --categories zimmereien --cities münchen` | 19 leads, 94.7% website, $0.36 |
| 3 | Zip code input | `--micro-test --categories dachdecker --cities 80331,80333` | 19 leads, zip geocoding confirmed |
| 4 | Interactive mode | `--interactive --micro-test` | Menu renders, category + location accepted |
| 5 | Interrupt + resume | `--max-leads 50` → Ctrl+C → same flags + `--resume` | Checkpoint saved on interrupt, resume skipped processed place_ids, collected remaining leads |

---

## What's Next

- **Zip range parsing** — support `80000-80999` syntax in location input, expanding to sampled representative points
- **Directory-site email filter** — detect and flag leads where the website is a directory listing, not the business's own domain
- **Production run** — large-scale scrape across all categories and regions, using checkpoint resume to run in batches within Google's daily quota

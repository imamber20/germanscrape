#!/usr/bin/env python3
"""
Smoke test for 11880.com scraper.
Runs a tiny live scrape (5 leads, 1 category, 1 city) to verify:
  1. Browser launches OK
  2. 11880.com loads without blocking
  3. HTML parsing finds listings
  4. Data extraction works (name, phone, address)
  5. CSV export works

Usage:
  python test_11880_smoke.py                    # Headless (default)
  python test_11880_smoke.py --no-headless      # Show browser for debugging

Expected output:
  - 3-10 leads from Dachdecker in Berlin (page 1 only)
  - CSV file in output/ folder
  - Summary printed to console

If 0 leads are returned, the CSS selectors need updating.
Use --no-headless to inspect the page visually and update
_parse_listings() in scraper_11880.py.
"""

import sys
import time

from scraper_11880 import Scraper11880, SETTINGS_11880


def run_smoke_test(headless: bool = True):
    print("=" * 60)
    print("11880.COM SMOKE TEST")
    print("=" * 60)
    print(f"\nConfig:")
    print(f"  Category: Dachdecker (roofers)")
    print(f"  City: Berlin")
    print(f"  Max leads: 5")
    print(f"  Headless: {headless}")
    print(f"  Cost: $0.00 (FREE)")
    print()

    start = time.time()

    scraper = Scraper11880(
        categories=['dachdecker'],
        cities=['Berlin'],
        max_leads=5,
        verbose=True,
        headless=headless,
    )

    scraper.run_scraping_workflow()

    elapsed = time.time() - start

    # Results
    print("\n" + "=" * 60)
    print("SMOKE TEST RESULTS")
    print("=" * 60)

    total = len(scraper.all_leads)
    print(f"\nLeads found: {total}")

    if total == 0:
        print("\n*** WARNING: 0 leads found! ***")
        print("This means the CSS selectors need updating.")
        print("Re-run with --no-headless to see the page and inspect the HTML:")
        print("  python test_11880_smoke.py --no-headless")
        print("\nThen update _parse_listings() in scraper_11880.py")
        return False

    # Print each lead
    for i, lead in enumerate(scraper.all_leads, 1):
        print(f"\n  Lead {i}:")
        print(f"    Name:    {lead.get('name', '-')}")
        print(f"    Phone:   {lead.get('phone', '-')}")
        print(f"    Address: {lead.get('address', '-')}")
        print(f"    Website: {lead.get('website', '-')}")
        print(f"    Email:   {lead.get('email', '-')}")

    # Export
    filename = scraper.export_to_csv()
    if filename:
        print(f"\nCSV exported: {filename}")

    # Stats
    with_phone = len([l for l in scraper.all_leads if l.get('phone')])
    with_addr = len([l for l in scraper.all_leads if l.get('address')])
    with_web = len([l for l in scraper.all_leads if l.get('website')])
    with_email = len([l for l in scraper.all_leads if l.get('email')])

    print(f"\nData completeness:")
    print(f"  Phone:   {with_phone}/{total} ({with_phone/total*100:.0f}%)")
    print(f"  Address: {with_addr}/{total} ({with_addr/total*100:.0f}%)")
    print(f"  Website: {with_web}/{total} ({with_web/total*100:.0f}%)")
    print(f"  Email:   {with_email}/{total} ({with_email/total*100:.0f}%)")
    print(f"\nElapsed: {elapsed:.1f}s")
    print(f"Cost: $0.00")

    print("\n" + "=" * 60)
    print("SMOKE TEST PASSED" if total > 0 else "SMOKE TEST FAILED")
    print("=" * 60)

    return total > 0


if __name__ == '__main__':
    headless = '--no-headless' not in sys.argv
    success = run_smoke_test(headless=headless)
    sys.exit(0 if success else 1)

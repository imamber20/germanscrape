#!/usr/bin/env python3
"""
Specialized script to scrape ONLY Carpenters and Roofers in Munich
Focus: Maximum website and email extraction
"""

import sys
import json
from scraper import LeadsScraper
from config import CATEGORIES, ZIP_RANGES, SETTINGS

# Override config to ONLY include Dachdecker and Zimmereien
MUNICH_CATEGORIES = {
    'dachdecker': CATEGORIES['dachdecker'],
    'zimmereien': CATEGORIES['zimmereien']
}

# Override to ONLY include München
MUNICH_ONLY = {
    '80000-80999': {
        'cities': ['München'],
        'state': 'Bayern',
        'region': 'Bavaria'
    }
}

def main():
    """Run Munich-specific scraping for carpenters and roofers"""

    print("=" * 70)
    print("MUNICH CARPENTERS & ROOFERS SCRAPER")
    print("=" * 70)
    print("\n📍 Target City: München (Munich)")
    print("📋 Categories:")
    print("   1. Dachdecker (Roofers) - Keywords:", MUNICH_CATEGORIES['dachdecker']['keywords'])
    print("   2. Zimmereien (Carpenters) - Keywords:", MUNICH_CATEGORIES['zimmereien']['keywords'])
    print("\n🎯 Focus: Maximum website and email extraction")
    print("💰 Estimated cost: $3-6 (within free $200 credit)")
    print("=" * 70)

    response = input("\n⚠️  Proceed with scraping? (yes/no): ")
    if response.lower() not in ['yes', 'y']:
        print("Scraping cancelled.")
        return

    # Temporarily override global config
    import config
    original_categories = config.CATEGORIES
    original_zip_ranges = config.ZIP_RANGES

    try:
        # Apply Munich-only configuration
        config.CATEGORIES = MUNICH_CATEGORIES
        config.ZIP_RANGES = MUNICH_ONLY

        # Initialize scraper
        scraper = LeadsScraper(
            test_mode=False,
            max_cities=None,  # No limit, get ALL results
            verbose=True
        )

        # Run scraping
        print("\n🚀 Starting scraping workflow...\n")
        scraper.run_scraping_workflow()

        # Export results
        scraper.export_to_csv()
        scraper.export_to_excel()

        # Print summary
        scraper.print_summary()

        # Show website and email statistics
        print("\n" + "=" * 70)
        print("WEBSITE & EMAIL EXTRACTION RESULTS")
        print("=" * 70)

        total_leads = len(scraper.all_leads)
        if total_leads > 0:
            with_website = len([l for l in scraper.all_leads if l.get('website')])
            with_email = len([l for l in scraper.all_leads if l.get('email')])

            website_pct = (with_website / total_leads * 100)
            email_pct = (with_email / total_leads * 100)

            print(f"\n✅ Total Leads: {total_leads}")
            print(f"✅ With Website: {with_website} ({website_pct:.1f}%)")
            print(f"✅ With Email: {with_email} ({email_pct:.1f}%)")

            # Show breakdown by category
            dachdecker_leads = [l for l in scraper.all_leads if l.get('category') == 'Dachdecker']
            zimmereien_leads = [l for l in scraper.all_leads if l.get('category') == 'Zimmereien']

            print(f"\n📊 By Category:")
            print(f"   Dachdecker (Roofers): {len(dachdecker_leads)} leads")
            print(f"      - With website: {len([l for l in dachdecker_leads if l.get('website')])}")
            print(f"      - With email: {len([l for l in dachdecker_leads if l.get('email')])}")

            print(f"   Zimmereien (Carpenters): {len(zimmereien_leads)} leads")
            print(f"      - With website: {len([l for l in zimmereien_leads if l.get('website')])}")
            print(f"      - With email: {len([l for l in zimmereien_leads if l.get('email')])}")

            print("\n" + "=" * 70)
            print("✅ Scraping complete! Check the output/ folder for CSV and Excel files.")
            print("=" * 70 + "\n")

    finally:
        # Restore original configuration
        config.CATEGORIES = original_categories
        config.ZIP_RANGES = original_zip_ranges

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Scraping interrupted by user\n")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Error: {e}\n")
        import traceback
        traceback.print_exc()
        sys.exit(1)

#!/usr/bin/env python3
"""
German Handwerk Leads Scraper
Automated lead generation for German blue-collar businesses using Google Places API
"""

import json
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from urllib.parse import urlparse
import argparse

import pandas as pd
from dotenv import load_dotenv
from openai import OpenAI
import googlemaps
from tqdm import tqdm

from config import CATEGORIES, ZIP_RANGES, SETTINGS, AI_FILTERING_PROMPT, AI_EMAIL_GENERATION_PROMPT


class LeadsScraper:
    """Main scraper class for collecting German business leads using Google Places API"""

    def __init__(self, test_mode: bool = False, max_cities: Optional[int] = None, verbose: bool = False):
        """Initialize scraper with configuration"""
        # Load environment variables
        load_dotenv()

        # Setup logging
        self.setup_logging(verbose)

        # Initialize API clients
        self.google_client = None
        self.openai_client = None
        self.setup_google_places()
        self.setup_openai()

        # Configuration
        self.test_mode = test_mode
        self.max_cities = max_cities
        self.request_delay = SETTINGS['request_delay']
        self.retry_attempts = SETTINGS['retry_attempts']

        # Data storage
        self.all_leads: List[Dict[str, Any]] = []
        self.stats = {
            'total_searches': 0,
            'total_api_calls': 0,
            'geocoding_calls': 0,
            'nearby_search_calls': 0,
            'place_details_calls': 0,
            'total_extracted': 0,
            'total_unique': 0,
            'businesses_with_websites': 0,
            'businesses_with_emails': 0,
            'by_category': {},
            'estimated_cost': 0.0
        }

        # Create output directory
        Path(SETTINGS['output_dir']).mkdir(exist_ok=True)

        self.logger.info("LeadsScraper initialized successfully with Google Places API")

    def setup_logging(self, verbose: bool = False) -> None:
        """Setup logging configuration"""
        log_level = logging.DEBUG if verbose else getattr(logging, SETTINGS['log_level'])

        # Create logs directory
        Path('logs').mkdir(exist_ok=True)

        # Create timestamp for log file
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        log_file = f'logs/scraper_{timestamp}.log'

        # Configure logging
        logging.basicConfig(
            level=log_level,
            format='[%(asctime)s] [%(levelname)s] [%(filename)s:%(lineno)d] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S',
            handlers=[
                logging.FileHandler(log_file, encoding='utf-8'),
                logging.StreamHandler(sys.stdout)
            ]
        )

        self.logger = logging.getLogger(__name__)
        self.logger.info(f"Logging initialized. Log file: {log_file}")

    def setup_google_places(self) -> None:
        """Initialize Google Places API client"""
        api_key = os.getenv('GOOGLE_PLACES_API_KEY')
        if not api_key:
            self.logger.error("GOOGLE_PLACES_API_KEY not found in environment variables")
            raise ValueError("GOOGLE_PLACES_API_KEY is required. Please set it in .env file")

        try:
            self.google_client = googlemaps.Client(key=api_key)
            self.logger.info("Google Places API client initialized")
        except Exception as e:
            self.logger.error(f"Failed to initialize Google Places client: {e}")
            raise

    def setup_openai(self) -> None:
        """Initialize OpenAI client (optional for filtering)"""
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            self.logger.warning("OPENAI_API_KEY not found. AI filtering will be disabled.")
            return

        try:
            self.openai_client = OpenAI(api_key=api_key)
            self.logger.info("OpenAI client initialized")
        except Exception as e:
            self.logger.warning(f"Failed to initialize OpenAI: {e}")

    def geocode_city(self, city: str) -> Optional[Dict[str, float]]:
        """
        Get coordinates for a German city using Geocoding API

        Args:
            city: City name (e.g., "München")

        Returns:
            Dictionary with lat/lng or None if failed
        """
        try:
            # Add "Germany" to ensure we get German cities
            query = f"{city}, Germany"
            self.logger.debug(f"Geocoding: {query}")

            result = self.google_client.geocode(query)
            self.stats['geocoding_calls'] += 1
            self.stats['total_api_calls'] += 1

            if result:
                location = result[0]['geometry']['location']
                self.logger.debug(f"✓ Geocoded {city}: {location['lat']}, {location['lng']}")
                return location
            else:
                self.logger.warning(f"✗ No geocoding results for {city}")
                return None

        except Exception as e:
            self.logger.error(f"Geocoding failed for {city}: {e}")
            return None

    def search_google_places(self, category: str, city: str, location: Dict[str, float]) -> List[Dict[str, Any]]:
        """
        Search for businesses using Google Places Nearby Search

        Args:
            category: Business category key (e.g., 'dachdecker')
            city: City name
            location: Dict with lat/lng coordinates

        Returns:
            List of business dictionaries
        """
        category_config = CATEGORIES.get(category)
        if not category_config:
            self.logger.error(f"Unknown category: {category}")
            return []

        category_name = category_config['name']
        google_type = category_config.get('google_type', 'general_contractor')
        keywords = ' '.join(category_config['keywords'])

        self.logger.info(f"Searching Google Places: {category_name} in {city}")

        businesses = []
        try:
            # Nearby Search
            radius = SETTINGS['google_search_radius']
            results = self.google_client.places_nearby(
                location=location,
                radius=radius,
                type=google_type,
                keyword=keywords,
                language='de'
            )

            self.stats['nearby_search_calls'] += 1
            self.stats['total_api_calls'] += 1

            # Get results from first page
            if 'results' in results:
                businesses.extend(results['results'])
                self.logger.debug(f"Found {len(results['results'])} businesses on page 1")

            # Get additional pages (Google allows up to 60 total results - 3 pages of 20)
            page_count = 1
            while 'next_page_token' in results and page_count < 3:
                # Google requires a short delay before fetching next page
                time.sleep(2)

                try:
                    results = self.google_client.places_nearby(
                        page_token=results['next_page_token']
                    )
                    self.stats['nearby_search_calls'] += 1
                    self.stats['total_api_calls'] += 1

                    if 'results' in results:
                        businesses.extend(results['results'])
                        page_count += 1
                        self.logger.debug(f"Found {len(results['results'])} businesses on page {page_count}")
                except Exception as e:
                    self.logger.warning(f"Failed to fetch page {page_count + 1}: {e}")
                    break

            self.logger.info(f"✓ Found {len(businesses)} total businesses for {category_name} in {city}")
            return businesses

        except Exception as e:
            self.logger.error(f"Google Places search failed for {category} in {city}: {e}")
            return []

    def get_place_details(self, place_id: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed information for a business using Place Details API

        Args:
            place_id: Google Place ID

        Returns:
            Dictionary with detailed business information
        """
        try:
            # Request specific fields to minimize cost
            fields = [
                'name',
                'formatted_address',
                'formatted_phone_number',
                'international_phone_number',
                'website',
                'rating',
                'user_ratings_total',
                'business_status'
            ]

            result = self.google_client.place(
                place_id=place_id,
                fields=fields,
                language='de'
            )

            self.stats['place_details_calls'] += 1
            self.stats['total_api_calls'] += 1

            if result and 'result' in result:
                return result['result']
            return None

        except Exception as e:
            self.logger.debug(f"Failed to get details for place {place_id}: {e}")
            return None

    def extract_leads_from_places(self, places: List[Dict[str, Any]], category: str, city: str) -> List[Dict[str, Any]]:
        """
        Extract structured lead data from Google Places results

        Args:
            places: List of places from Google Places API
            category: Business category
            city: City name

        Returns:
            List of structured business leads
        """
        leads = []
        category_name = CATEGORIES[category]['name']

        self.logger.info(f"Extracting details for {len(places)} businesses...")

        for place in tqdm(places, desc=f"Getting details", disable=not self.logger.isEnabledFor(logging.INFO)):
            try:
                # Get detailed information
                place_id = place.get('place_id')
                if not place_id:
                    continue

                details = self.get_place_details(place_id)
                if not details:
                    continue

                # Skip permanently closed businesses
                if details.get('business_status') == 'CLOSED_PERMANENTLY':
                    self.logger.debug(f"Skipping closed business: {details.get('name')}")
                    continue

                # Extract structured data
                lead = {
                    'name': details.get('name', ''),
                    'category': category_name,
                    'address': details.get('formatted_address', ''),
                    'phone': details.get('formatted_phone_number') or details.get('international_phone_number', ''),
                    'website': details.get('website', ''),
                    'rating': details.get('rating', ''),
                    'reviews': details.get('user_ratings_total', ''),
                    'source': 'Google Places',
                    'city': city
                }

                # Generate email from website
                if lead['website']:
                    lead['email'] = self.generate_email_from_website(lead['website'])
                    if lead['email']:
                        self.stats['businesses_with_emails'] += 1

                # Track website statistics
                if lead['website']:
                    self.stats['businesses_with_websites'] += 1

                leads.append(lead)

                # Add delay to respect rate limits
                time.sleep(SETTINGS['google_request_delay'])

            except Exception as e:
                self.logger.debug(f"Failed to process place: {e}")
                continue

        self.logger.info(f"✓ Extracted {len(leads)} leads ({len([l for l in leads if l.get('website')])} with websites, {len([l for l in leads if l.get('email')])} with emails)")
        return leads

    def generate_email_from_website(self, website: str) -> str:
        """
        Generate email address from website domain

        Args:
            website: Website URL

        Returns:
            Generated email address (info@domain.com)
        """
        try:
            # Parse domain from URL
            parsed = urlparse(website)
            domain = parsed.netloc or parsed.path

            # Remove www. prefix
            domain = domain.replace('www.', '')

            # Generate info@ email (most common in Germany)
            email = f"info@{domain}"

            return email

        except Exception as e:
            self.logger.debug(f"Failed to generate email from {website}: {e}")
            return ""

    def filter_leads_with_ai(self, leads: List[Dict[str, Any]], category: str) -> List[Dict[str, Any]]:
        """
        Use AI to filter and validate leads (optional, requires OpenAI)

        Args:
            leads: List of business leads
            category: Business category

        Returns:
            Filtered list of leads
        """
        if not self.openai_client or not SETTINGS.get('use_ai_filtering'):
            return leads

        if not leads:
            return leads

        try:
            category_name = CATEGORIES[category]['name']
            self.logger.info(f"Filtering {len(leads)} leads with AI for category: {category_name}")

            # Prepare input for AI
            input_data = json.dumps(leads, ensure_ascii=False)

            response = self.openai_client.chat.completions.create(
                model=SETTINGS['ai_model'],
                messages=[
                    {"role": "system", "content": AI_FILTERING_PROMPT},
                    {"role": "user", "content": f"Category: {category_name}\n\nBusinesses:\n{input_data}"}
                ],
                temperature=SETTINGS['ai_temperature'],
                max_tokens=SETTINGS['max_tokens']
            )

            result = response.choices[0].message.content.strip()

            # Parse JSON response
            filtered_leads = json.loads(result)

            removed_count = len(leads) - len(filtered_leads)
            self.logger.info(f"✓ AI filtering complete: Kept {len(filtered_leads)}, removed {removed_count}")

            return filtered_leads

        except Exception as e:
            self.logger.warning(f"AI filtering failed: {e}. Returning original leads.")
            return leads

    def deduplicate_leads(self, leads: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Remove duplicate leads based on website, phone, or name

        Args:
            leads: List of leads

        Returns:
            Deduplicated list
        """
        seen = set()
        unique_leads = []

        for lead in leads:
            # Create identifier from website, phone, or name
            website = lead.get('website', '').lower().strip()
            phone = lead.get('phone', '').replace(' ', '').replace('-', '').replace('(', '').replace(')', '')
            name = lead.get('name', '').lower().strip()

            # Use website as primary identifier
            if website and website in seen:
                continue
            # Use phone as secondary identifier
            elif phone and phone in seen:
                continue
            # Use name as tertiary identifier
            elif name and name in seen:
                continue

            # Add to unique set
            if website:
                seen.add(website)
            elif phone:
                seen.add(phone)
            elif name:
                seen.add(name)

            unique_leads.append(lead)

        removed = len(leads) - len(unique_leads)
        if removed > 0:
            self.logger.info(f"Removed {removed} duplicates. Unique leads: {len(unique_leads)}")

        return unique_leads

    def scrape_category_city(self, category: str, city: str) -> List[Dict[str, Any]]:
        """
        Scrape leads for a specific category and city

        Args:
            category: Business category key
            city: City name

        Returns:
            List of leads
        """
        self.logger.info(f"Scraping {category} in {city}")
        self.stats['total_searches'] += 1

        # Step 1: Geocode city
        location = self.geocode_city(city)
        if not location:
            self.logger.error(f"Failed to geocode {city}. Skipping.")
            return []

        # Step 2: Search Google Places
        places = self.search_google_places(category, city, location)
        if not places:
            self.logger.warning(f"No places found for {category} in {city}")
            return []

        # Step 3: Get detailed information
        leads = self.extract_leads_from_places(places, category, city)

        # Step 4: Optional AI filtering
        if SETTINGS.get('use_ai_filtering') and self.openai_client:
            leads = self.filter_leads_with_ai(leads, category)

        # Update category stats
        category_name = CATEGORIES[category]['name']
        if category_name not in self.stats['by_category']:
            self.stats['by_category'][category_name] = 0
        self.stats['by_category'][category_name] += len(leads)

        return leads

    def run_scraping_workflow(self) -> None:
        """Main workflow for scraping all categories and cities"""
        self.logger.info("Starting scraping workflow")

        # Prepare list of tasks (category × city combinations)
        tasks = []
        cities_processed = 0

        for zip_range, data in ZIP_RANGES.items():
            cities = data['cities']

            for city in cities:
                # Limit cities in test mode
                if self.max_cities and cities_processed >= self.max_cities:
                    break

                for category in CATEGORIES.keys():
                    tasks.append((category, city))

                cities_processed += 1

            if self.max_cities and cities_processed >= self.max_cities:
                break

        self.logger.info(f"Total tasks: {len(tasks)} ({len(CATEGORIES)} categories × {cities_processed} cities)")

        # Show cost estimate
        self.show_cost_estimate(len(tasks), cities_processed)

        # Process each task
        for category, city in tqdm(tasks, desc="Scraping progress"):
            try:
                leads = self.scrape_category_city(category, city)
                self.all_leads.extend(leads)
                self.stats['total_extracted'] += len(leads)

                # Add delay between searches
                time.sleep(self.request_delay)

            except Exception as e:
                self.logger.error(f"Failed to scrape {category} in {city}: {e}")
                continue

        # Deduplicate all leads
        self.all_leads = self.deduplicate_leads(self.all_leads)
        self.stats['total_unique'] = len(self.all_leads)

        self.logger.info(f"Scraping completed. Total leads collected: {self.stats['total_unique']}")

    def show_cost_estimate(self, total_tasks: int, total_cities: int) -> None:
        """
        Show estimated Google API costs before scraping

        Args:
            total_tasks: Number of category×city combinations
            total_cities: Number of unique cities
        """
        # Cost calculation
        geocoding_cost = total_cities * SETTINGS['google_geocoding_cost']
        nearby_search_cost = total_tasks * SETTINGS['google_nearby_search_cost']

        # Estimate ~30 businesses per search, 60% get details
        estimated_businesses = total_tasks * 30
        estimated_details = estimated_businesses * 0.6
        details_cost = estimated_details * SETTINGS['google_place_details_cost']

        total_cost = geocoding_cost + nearby_search_cost + details_cost

        self.logger.info("=" * 60)
        self.logger.info("ESTIMATED GOOGLE API COSTS")
        self.logger.info("=" * 60)
        self.logger.info(f"Geocoding calls: {total_cities} × ${SETTINGS['google_geocoding_cost']*1000:.2f}/1k = ${geocoding_cost:.2f}")
        self.logger.info(f"Nearby Search calls: {total_tasks} × ${SETTINGS['google_nearby_search_cost']*1000:.2f}/1k = ${nearby_search_cost:.2f}")
        self.logger.info(f"Place Details calls (est.): {int(estimated_details)} × ${SETTINGS['google_place_details_cost']*1000:.2f}/1k = ${details_cost:.2f}")
        self.logger.info(f"TOTAL ESTIMATED COST: ${total_cost:.2f}")
        self.logger.info(f"Free tier credit: $200.00 (Google Cloud)")
        self.logger.info("=" * 60)

        self.stats['estimated_cost'] = total_cost

    def export_to_csv(self) -> None:
        """Export leads to CSV with German character encoding"""
        if not self.all_leads:
            self.logger.warning("No leads to export")
            return

        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"{SETTINGS['output_dir']}/leads_{timestamp}.csv"

            # Convert to DataFrame
            df = pd.DataFrame(self.all_leads)

            # Reorder columns
            column_order = ['name', 'category', 'email', 'website', 'phone', 'address', 'city', 'rating', 'reviews', 'source']
            existing_columns = [col for col in column_order if col in df.columns]
            df = df[existing_columns]

            # Export with UTF-8-BOM for German characters
            df.to_csv(filename, index=False, encoding='utf-8-sig')

            self.logger.info(f"✓ Exported {len(df)} leads to: {filename}")

        except Exception as e:
            self.logger.error(f"Failed to export CSV: {e}")

    def export_to_excel(self) -> None:
        """Export leads to Excel with proper formatting"""
        if not self.all_leads:
            self.logger.warning("No leads to export")
            return

        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"{SETTINGS['output_dir']}/leads_{timestamp}.xlsx"

            # Convert to DataFrame
            df = pd.DataFrame(self.all_leads)

            # Reorder columns
            column_order = ['name', 'category', 'email', 'website', 'phone', 'address', 'city', 'rating', 'reviews', 'source']
            existing_columns = [col for col in column_order if col in df.columns]
            df = df[existing_columns]

            # Export to Excel
            df.to_excel(filename, index=False, engine='openpyxl')

            self.logger.info(f"✓ Exported {len(df)} leads to: {filename}")

        except Exception as e:
            self.logger.error(f"Failed to export Excel: {e}")

    def print_summary(self) -> None:
        """Print summary statistics"""
        if not self.all_leads:
            print("\n⚠️  No leads collected\n")
            return

        websites = len([l for l in self.all_leads if l.get('website')])
        emails = len([l for l in self.all_leads if l.get('email')])
        website_pct = (websites / len(self.all_leads) * 100) if self.all_leads else 0
        email_pct = (emails / len(self.all_leads) * 100) if self.all_leads else 0

        print("\n" + "=" * 60)
        print("SCRAPING SUMMARY")
        print("=" * 60)
        print(f"\n📊 Overall Statistics:")
        print(f"  Total searches: {self.stats['total_searches']}")
        print(f"  Total leads extracted: {self.stats['total_extracted']}")
        print(f"  Unique leads: {self.stats['total_unique']}")
        print(f"  Businesses with websites: {websites} ({website_pct:.1f}%)")
        print(f"  Businesses with emails: {emails} ({email_pct:.1f}%)")

        print(f"\n📁 By Category:")
        for category, count in sorted(self.stats['by_category'].items()):
            print(f"  {category}: {count}")

        print(f"\n💰 API Usage:")
        print(f"  Total API calls: {self.stats['total_api_calls']}")
        print(f"  Geocoding calls: {self.stats['geocoding_calls']}")
        print(f"  Nearby Search calls: {self.stats['nearby_search_calls']}")
        print(f"  Place Details calls: {self.stats['place_details_calls']}")
        print(f"  Estimated cost: ${self.stats['estimated_cost']:.2f}")

        print("\n" + "=" * 60 + "\n")


async def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='German Handwerk Leads Scraper with Google Places API')
    parser.add_argument('--test', action='store_true', help='Run in test mode (limited results)')
    parser.add_argument('--max-cities', type=int, help='Maximum number of cities to process')
    parser.add_argument('--verbose', action='store_true', help='Enable verbose logging')

    args = parser.parse_args()

    try:
        # Initialize scraper
        scraper = LeadsScraper(
            test_mode=args.test,
            max_cities=args.max_cities,
            verbose=args.verbose
        )

        # Run scraping
        scraper.run_scraping_workflow()

        # Export results
        scraper.export_to_csv()
        scraper.export_to_excel()

        # Print summary
        scraper.print_summary()

    except KeyboardInterrupt:
        print("\n\n⚠️  Scraping interrupted by user\n")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Fatal error: {e}\n")
        sys.exit(1)


if __name__ == '__main__':
    import asyncio
    asyncio.run(main())

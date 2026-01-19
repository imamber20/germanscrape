#!/usr/bin/env python3
"""
German Handwerk Leads Scraper
Automated lead generation for German blue-collar businesses
"""

import asyncio
import json
import logging
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from urllib.parse import quote_plus, urlparse
import argparse

import pandas as pd
from dotenv import load_dotenv
from openai import OpenAI
import requests
from bs4 import BeautifulSoup
from tqdm import tqdm

from config import CATEGORIES, ZIP_RANGES, SETTINGS, AI_EXTRACTION_PROMPT


class LeadsScraper:
    """Main scraper class for collecting German business leads"""

    def __init__(self, test_mode: bool = False, max_cities: Optional[int] = None, verbose: bool = False):
        """Initialize scraper with configuration"""
        # Load environment variables
        load_dotenv()

        # Setup logging
        self.setup_logging(verbose)

        # Initialize API clients
        self.openai_client = None
        self.setup_openai()

        # Configuration
        self.test_mode = test_mode
        self.max_cities = max_cities
        self.request_delay = SETTINGS['request_delay']
        self.retry_attempts = SETTINGS['retry_attempts']

        # Data storage
        self.all_leads: List[Dict[str, Any]] = []
        self.stats = {
            'total_scrapes': 0,
            'successful_scrapes': 0,
            'failed_scrapes': 0,
            'total_extracted': 0,
            'total_unique': 0,
            'by_category': {},
            'by_source': {'google_maps': 0, 'directory': 0}
        }

        # Create output directory
        Path(SETTINGS['output_dir']).mkdir(exist_ok=True)

        self.logger.info("LeadsScraper initialized successfully")

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

    def setup_openai(self) -> None:
        """Initialize OpenAI client"""
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            self.logger.error("OPENAI_API_KEY not found in environment variables")
            raise ValueError("OPENAI_API_KEY is required. Please set it in .env file")

        self.openai_client = OpenAI(api_key=api_key)
        self.logger.info("OpenAI client initialized")

    def scrape_google_maps(self, keyword: str, city: str) -> Optional[str]:
        """
        Scrape Google Maps search results

        Args:
            keyword: Business category keyword (e.g., "Dachdecker")
            city: City name (e.g., "München")

        Returns:
            HTML content or None if failed
        """
        query = f"{keyword} {city} Deutschland"
        url = f"https://www.google.com/maps/search/{quote_plus(query)}"

        self.logger.info(f"Scraping Google Maps: {query}")
        self.stats['total_scrapes'] += 1

        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
            }

            response = requests.get(url, headers=headers, timeout=SETTINGS['timeout'])
            response.raise_for_status()

            self.logger.debug(f"Response size: {len(response.content)} bytes, status: {response.status_code}")
            self.stats['successful_scrapes'] += 1

            return response.text

        except Exception as e:
            self.logger.error(f"Failed to scrape Google Maps for {query}: {str(e)}")
            self.stats['failed_scrapes'] += 1
            return None

    def scrape_gelbeseiten(self, keyword: str, city: str) -> Optional[str]:
        """
        Scrape Gelbe Seiten (German Yellow Pages)

        Args:
            keyword: Business category keyword
            city: City name

        Returns:
            HTML content or None if failed
        """
        query = quote_plus(keyword)
        location = quote_plus(city)
        url = f"https://www.gelbeseiten.de/Suche/{query}/{location}"

        self.logger.info(f"Scraping Gelbe Seiten: {keyword} in {city}")
        self.stats['total_scrapes'] += 1

        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'de-DE,de;q=0.9',
            }

            response = requests.get(url, headers=headers, timeout=SETTINGS['timeout'])
            response.raise_for_status()

            self.logger.debug(f"Response size: {len(response.content)} bytes, status: {response.status_code}")
            self.stats['successful_scrapes'] += 1

            return response.text

        except Exception as e:
            self.logger.error(f"Failed to scrape Gelbe Seiten for {keyword} in {city}: {str(e)}")
            self.stats['failed_scrapes'] += 1
            return None

    def extract_with_ai(self, html_content: str, category: str, city: str) -> List[Dict[str, Any]]:
        """
        Extract business information using OpenAI

        Args:
            html_content: Raw HTML content
            category: Business category
            city: City name

        Returns:
            List of extracted businesses
        """
        if not html_content:
            return []

        # Clean HTML and extract text
        soup = BeautifulSoup(html_content, 'html.parser')

        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.decompose()

        text = soup.get_text()

        # Limit text size to avoid token limits
        max_chars = 8000
        if len(text) > max_chars:
            text = text[:max_chars]

        self.logger.info(f"Extracting businesses with AI for {category} in {city}")

        try:
            user_prompt = f"""Search context: {category} in {city}, Deutschland

Content to extract from:
{text}

Extract all {category} businesses found in the content."""

            response = self.openai_client.chat.completions.create(
                model=SETTINGS['ai_model'],
                messages=[
                    {"role": "system", "content": AI_EXTRACTION_PROMPT},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=SETTINGS['ai_temperature'],
                max_tokens=SETTINGS['max_tokens']
            )

            content = response.choices[0].message.content.strip()

            # Log token usage
            tokens_used = response.usage.total_tokens
            self.logger.debug(f"AI extraction completed. Tokens used: {tokens_used}")

            # Parse JSON response
            # Remove markdown code blocks if present
            if content.startswith('```'):
                content = re.sub(r'^```json?\n?', '', content)
                content = re.sub(r'\n?```$', '', content)

            businesses = json.loads(content)

            if not isinstance(businesses, list):
                self.logger.warning("AI response is not a list, wrapping in list")
                businesses = [businesses]

            self.logger.info(f"Extracted {len(businesses)} businesses")
            self.stats['total_extracted'] += len(businesses)

            return businesses

        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse AI response as JSON: {str(e)}")
            self.logger.debug(f"AI response content: {content[:500]}")
            return []
        except Exception as e:
            self.logger.error(f"AI extraction failed: {str(e)}")
            return []

    def enrich_lead(self, lead: Dict[str, Any], source: str, category: str) -> Dict[str, Any]:
        """
        Enrich lead with additional data

        Args:
            lead: Lead data
            source: Source of the lead (google_maps, directory)
            category: Business category

        Returns:
            Enriched lead data
        """
        enriched = lead.copy()

        # Add metadata
        enriched['source'] = source
        enriched['scraped_at'] = datetime.now().isoformat()

        # Ensure category is set
        if 'category' not in enriched or not enriched['category']:
            enriched['category'] = category

        # Generate email from website if website exists but email doesn't
        if 'website' in enriched and enriched['website'] and ('email' not in enriched or not enriched['email']):
            domain = self.extract_domain(enriched['website'])
            if domain:
                enriched['email'] = f"info@{domain}"
                self.logger.debug(f"Generated email: {enriched['email']}")

        return enriched

    def extract_domain(self, url: str) -> Optional[str]:
        """Extract domain from URL"""
        try:
            if not url.startswith(('http://', 'https://')):
                url = 'https://' + url
            parsed = urlparse(url)
            domain = parsed.netloc
            # Remove www. prefix
            domain = re.sub(r'^www\.', '', domain)
            return domain
        except Exception as e:
            self.logger.debug(f"Failed to extract domain from {url}: {str(e)}")
            return None

    def deduplicate_leads(self, leads: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Deduplicate leads by website, phone, and name

        Args:
            leads: List of leads

        Returns:
            Deduplicated leads
        """
        seen = set()
        unique_leads = []
        duplicates = 0

        for lead in leads:
            # Create deduplication key based on available fields
            key_parts = []

            if lead.get('website'):
                domain = self.extract_domain(lead['website'])
                if domain:
                    key_parts.append(('website', domain))

            if lead.get('phone'):
                # Normalize phone number
                phone = re.sub(r'\s+|-|\(|\)', '', lead['phone'])
                key_parts.append(('phone', phone))

            if lead.get('name'):
                # Normalize name
                name = lead['name'].lower().strip()
                key_parts.append(('name', name))

            # Create key
            if key_parts:
                key = tuple(key_parts)

                if key not in seen:
                    seen.add(key)
                    unique_leads.append(lead)
                else:
                    duplicates += 1
                    self.logger.debug(f"Duplicate found: {lead.get('name', 'Unknown')}")
            else:
                # No key fields, keep the lead
                unique_leads.append(lead)

        self.logger.info(f"Deduplication: {len(leads)} -> {len(unique_leads)} (removed {duplicates} duplicates)")
        self.stats['total_unique'] = len(unique_leads)

        return unique_leads

    async def scrape_category_city(self, category_key: str, city: str) -> List[Dict[str, Any]]:
        """
        Scrape a specific category in a specific city

        Args:
            category_key: Category key from CATEGORIES
            city: City name

        Returns:
            List of leads
        """
        category_data = CATEGORIES[category_key]
        category_name = category_data['name']
        keywords = category_data['keywords']

        leads = []

        # Use first keyword for scraping
        keyword = keywords[0]

        self.logger.info(f"Scraping {category_name} in {city}")

        # Scrape Google Maps
        google_html = self.scrape_google_maps(keyword, city)
        if google_html:
            google_leads = self.extract_with_ai(google_html, category_name, city)
            for lead in google_leads:
                enriched = self.enrich_lead(lead, 'google_maps', category_name)
                leads.append(enriched)
                self.stats['by_source']['google_maps'] += 1

        # Delay between requests
        await asyncio.sleep(self.request_delay)

        # Scrape Gelbe Seiten
        directory_html = self.scrape_gelbeseiten(keyword, city)
        if directory_html:
            directory_leads = self.extract_with_ai(directory_html, category_name, city)
            for lead in directory_leads:
                enriched = self.enrich_lead(lead, 'gelbeseiten', category_name)
                leads.append(enriched)
                self.stats['by_source']['directory'] += 1

        # Update category stats
        if category_name not in self.stats['by_category']:
            self.stats['by_category'][category_name] = 0
        self.stats['by_category'][category_name] += len(leads)

        self.logger.info(f"Collected {len(leads)} leads for {category_name} in {city}")

        return leads

    async def run_scraping(self, category_filter: Optional[str] = None, ziprange_filter: Optional[str] = None):
        """
        Main scraping workflow

        Args:
            category_filter: Optional category to scrape (default: all)
            ziprange_filter: Optional zip range to scrape (default: all)
        """
        self.logger.info("Starting scraping workflow")

        # Determine categories to scrape
        if category_filter:
            if category_filter not in CATEGORIES:
                self.logger.error(f"Invalid category: {category_filter}")
                return
            categories = {category_filter: CATEGORIES[category_filter]}
        else:
            categories = CATEGORIES

        # Determine zip ranges to scrape
        if ziprange_filter:
            if ziprange_filter not in ZIP_RANGES:
                self.logger.error(f"Invalid zip range: {ziprange_filter}")
                return
            zip_ranges = {ziprange_filter: ZIP_RANGES[ziprange_filter]}
        else:
            zip_ranges = ZIP_RANGES

        # Calculate total tasks
        total_cities = sum(len(zr['cities']) for zr in zip_ranges.values())
        if self.max_cities:
            total_cities = min(total_cities, self.max_cities)

        total_tasks = len(categories) * total_cities

        self.logger.info(f"Total tasks: {total_tasks} ({len(categories)} categories × {total_cities} cities)")

        # Progress bar
        with tqdm(total=total_tasks, desc="Scraping progress") as pbar:
            city_count = 0

            for category_key in categories.keys():
                for zip_range, zip_data in zip_ranges.items():
                    for city in zip_data['cities']:
                        if self.max_cities and city_count >= self.max_cities:
                            break

                        leads = await self.scrape_category_city(category_key, city)
                        self.all_leads.extend(leads)

                        pbar.update(1)
                        city_count += 1

                        # Delay between city scrapes
                        await asyncio.sleep(self.request_delay)

                    if self.max_cities and city_count >= self.max_cities:
                        break

                if self.max_cities and city_count >= self.max_cities:
                    break

        self.logger.info(f"Scraping completed. Total leads collected: {len(self.all_leads)}")

    def export_to_csv(self, filename: str = None) -> str:
        """
        Export leads to CSV

        Args:
            filename: Optional filename (default: auto-generated)

        Returns:
            Path to exported file
        """
        if not filename:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"leads_{timestamp}.csv"

        filepath = Path(SETTINGS['output_dir']) / filename

        # Create DataFrame
        df = pd.DataFrame(self.all_leads)

        # Reorder columns
        column_order = ['name', 'email', 'website', 'category', 'phone', 'address', 'additional_info', 'source', 'scraped_at']
        existing_columns = [col for col in column_order if col in df.columns]
        df = df[existing_columns]

        # Export with UTF-8-BOM encoding for German characters
        df.to_csv(filepath, index=False, encoding='utf-8-sig')

        self.logger.info(f"Exported {len(df)} leads to CSV: {filepath}")

        return str(filepath)

    def export_to_excel(self, filename: str = None) -> str:
        """
        Export leads to Excel

        Args:
            filename: Optional filename (default: auto-generated)

        Returns:
            Path to exported file
        """
        if not filename:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"leads_{timestamp}.xlsx"

        filepath = Path(SETTINGS['output_dir']) / filename

        # Create DataFrame
        df = pd.DataFrame(self.all_leads)

        # Reorder columns
        column_order = ['name', 'email', 'website', 'category', 'phone', 'address', 'additional_info', 'source', 'scraped_at']
        existing_columns = [col for col in column_order if col in df.columns]
        df = df[existing_columns]

        # Export to Excel
        df.to_excel(filepath, index=False, engine='openpyxl')

        self.logger.info(f"Exported {len(df)} leads to Excel: {filepath}")

        return str(filepath)

    def print_summary(self):
        """Print scraping summary statistics"""
        print("\n" + "="*60)
        print("SCRAPING SUMMARY")
        print("="*60)

        print(f"\n📊 Overall Statistics:")
        print(f"  Total scrape attempts: {self.stats['total_scrapes']}")
        print(f"  Successful scrapes: {self.stats['successful_scrapes']}")
        print(f"  Failed scrapes: {self.stats['failed_scrapes']}")
        print(f"  Total leads extracted: {self.stats['total_extracted']}")
        print(f"  Unique leads: {self.stats['total_unique']}")

        if self.all_leads:
            # Calculate completion percentage
            leads_with_email = sum(1 for lead in self.all_leads if lead.get('email'))
            leads_with_phone = sum(1 for lead in self.all_leads if lead.get('phone'))
            leads_with_website = sum(1 for lead in self.all_leads if lead.get('website'))

            print(f"\n✅ Data Completeness:")
            print(f"  Leads with email: {leads_with_email} ({leads_with_email/len(self.all_leads)*100:.1f}%)")
            print(f"  Leads with phone: {leads_with_phone} ({leads_with_phone/len(self.all_leads)*100:.1f}%)")
            print(f"  Leads with website: {leads_with_website} ({leads_with_website/len(self.all_leads)*100:.1f}%)")

        if self.stats['by_category']:
            print(f"\n📁 By Category:")
            for category, count in sorted(self.stats['by_category'].items(), key=lambda x: x[1], reverse=True):
                print(f"  {category}: {count}")

        print(f"\n🌐 By Source:")
        print(f"  Google Maps: {self.stats['by_source']['google_maps']}")
        print(f"  Directory: {self.stats['by_source']['directory']}")

        print("\n" + "="*60)


async def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='German Handwerk Leads Scraper')
    parser.add_argument('--category', type=str, help='Specific category to scrape (e.g., dachdecker)')
    parser.add_argument('--ziprange', type=str, help='Specific zip range to scrape (e.g., 80000-80999)')
    parser.add_argument('--test', action='store_true', help='Test mode (limited scraping)')
    parser.add_argument('--max-cities', type=int, help='Maximum number of cities to scrape')
    parser.add_argument('--verbose', action='store_true', help='Verbose logging (DEBUG level)')
    parser.add_argument('--output-csv', type=str, help='Output CSV filename')
    parser.add_argument('--output-excel', type=str, help='Output Excel filename')

    args = parser.parse_args()

    # Initialize scraper
    scraper = LeadsScraper(
        test_mode=args.test,
        max_cities=args.max_cities,
        verbose=args.verbose
    )

    # Run scraping
    await scraper.run_scraping(
        category_filter=args.category,
        ziprange_filter=args.ziprange
    )

    # Deduplicate leads
    if scraper.all_leads:
        scraper.all_leads = scraper.deduplicate_leads(scraper.all_leads)

    # Export results
    if scraper.all_leads:
        csv_file = scraper.export_to_csv(args.output_csv)
        excel_file = scraper.export_to_excel(args.output_excel)

        print(f"\n✅ Exports completed:")
        print(f"  CSV: {csv_file}")
        print(f"  Excel: {excel_file}")
    else:
        print("\n⚠️  No leads collected")

    # Print summary
    scraper.print_summary()


if __name__ == '__main__':
    asyncio.run(main())

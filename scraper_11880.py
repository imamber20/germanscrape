#!/usr/bin/env python3
"""
11880.com Leads Scraper
Scrapes German business leads from 11880.com (Germany's largest business directory)
Uses Selenium for dynamic page rendering + BeautifulSoup for parsing

URL Pattern: https://www.11880.com/suche/{category}/{city}?page={n}
Data fields: name, category, phone, address, website, email
"""

import argparse
import json
import logging
import os
import random
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from urllib.parse import urlparse, quote

import pandas as pd
from bs4 import BeautifulSoup
from tqdm import tqdm

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException, WebDriverException
except ImportError:
    print("ERROR: selenium is required. Install with: pip install selenium")
    sys.exit(1)

from config import CATEGORIES, SETTINGS


# 11880.com-specific settings
SETTINGS_11880 = {
    'base_url': 'https://www.11880.com',
    'search_url': 'https://www.11880.com/suche/{category}/{city}',
    'max_pages': 50,           # Max pagination pages per search
    'page_delay_min': 2.0,     # Min delay between page loads (seconds)
    'page_delay_max': 5.0,     # Max delay between page loads (seconds)
    'page_load_timeout': 15,   # Selenium page load timeout (seconds)
    'element_wait_timeout': 10, # Wait for elements to appear (seconds)
    'max_retries': 3,          # Retry failed page loads
    'checkpoint_file': 'progress_11880.json',
    'checkpoint_interval': 25, # Save every 25 leads
    'output_dir': 'output',
    'concurrent_browsers': 3,  # Number of parallel browser instances
    'headless': True,          # Run browser in headless mode
}

# City name mappings for 11880.com URL slugs (German cities → URL-safe format)
CITY_URL_MAP = {
    'münchen': 'muenchen',
    'nürnberg': 'nuernberg',
    'köln': 'koeln',
    'düsseldorf': 'duesseldorf',
    'frankfurt': 'frankfurt-am-main',
    'hannover': 'hannover',
    'berlin mitte': 'berlin',
    'friedrichshain': 'berlin',
    'kreuzberg': 'berlin',
    'fürth': 'fuerth',
    'erlangen': 'erlangen',
}

# Category search terms for 11880.com (maps config keys to 11880 search slugs)
# 11880.com uses the category name directly in the URL
CATEGORY_11880_MAP = {
    'dachdecker': 'dachdecker',
    'heizungsbauer': 'heizungsbauer',
    'sanitärinstallateure': 'sanitaerinstallateur',
    'elektrotechnik': 'elektriker',
    'malerbetriebe': 'malerbetrieb',
    'fliesenleger': 'fliesenleger',
    'bauunternehmen': 'bauunternehmen',
    'trockenbaufirmen': 'trockenbau',
    'zimmereien': 'zimmerei',
    'abrissunternehmen': 'abrissunternehmen',
    'autohändler': 'autohaendler',
    'autohäuser': 'autohaus',
    'autowerkstätten': 'autowerkstatt',
}


class Scraper11880:
    """Scrapes business leads from 11880.com using Selenium + BeautifulSoup"""

    def __init__(self, categories: List[str] = None, cities: List[str] = None,
                 max_leads: Optional[int] = None, resume: bool = False,
                 verbose: bool = False, headless: bool = True):
        self.setup_logging(verbose)

        # Configuration
        self.selected_categories = categories or list(CATEGORIES.keys())
        self.selected_cities = cities or self._get_default_cities()
        self.max_leads = max_leads
        self.headless = headless

        # Data storage
        self.all_leads: List[Dict[str, Any]] = []
        self._leads_lock = threading.Lock()
        self.leads_collected = 0

        # Checkpoint
        self.checkpoint_file = Path(SETTINGS_11880['checkpoint_file'])
        self.processed_urls: set = set()
        self.stats = {
            'start_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'pages_scraped': 0,
            'total_listings_found': 0,
            'leads_collected': 0,
            'leads_by_category': {},
        }

        if resume:
            self._load_checkpoint()
        else:
            self._clear_checkpoint()

        # Create output directory
        Path(SETTINGS_11880['output_dir']).mkdir(exist_ok=True)

        self.logger.info("11880.com Scraper initialized")
        self.logger.info(f"  Categories: {len(self.selected_categories)}")
        self.logger.info(f"  Cities: {len(self.selected_cities)}")
        if self.max_leads:
            self.logger.info(f"  Max leads: {self.max_leads}")

    def _get_default_cities(self) -> List[str]:
        """Get major German cities for scraping"""
        return [
            'Berlin', 'Hamburg', 'München', 'Köln', 'Frankfurt',
            'Stuttgart', 'Düsseldorf', 'Dortmund', 'Essen', 'Leipzig',
            'Dresden', 'Hannover', 'Nürnberg', 'Bochum', 'Augsburg',
            'Bonn', 'Wiesbaden', 'Darmstadt', 'Heilbronn', 'Hildesheim',
            'Chemnitz', 'Fürth', 'Erlangen',
        ]

    def setup_logging(self, verbose: bool = False) -> None:
        log_level = logging.DEBUG if verbose else logging.INFO
        Path('logs').mkdir(exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        log_file = f'logs/scraper_11880_{timestamp}.log'

        logging.basicConfig(
            level=log_level,
            format='[%(asctime)s] [%(levelname)s] %(message)s',
            datefmt='%H:%M:%S',
            handlers=[
                logging.FileHandler(log_file, encoding='utf-8'),
                logging.StreamHandler(sys.stdout)
            ]
        )
        logging.getLogger('selenium').setLevel(logging.WARNING)
        logging.getLogger('urllib3').setLevel(logging.WARNING)
        self.logger = logging.getLogger(__name__)

    # ── Browser Management ──────────────────────────────────────────────

    def _create_browser(self) -> webdriver.Chrome:
        """Create a configured Chrome browser instance"""
        options = Options()
        if self.headless:
            options.add_argument('--headless=new')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('--window-size=1920,1080')
        options.add_argument('--disable-blink-features=AutomationControlled')

        # Rotate user agents to reduce detection
        user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
        ]
        options.add_argument(f'--user-agent={random.choice(user_agents)}')

        # Disable automation flags
        options.add_experimental_option('excludeSwitches', ['enable-automation'])
        options.add_experimental_option('useAutomationExtension', False)

        driver = webdriver.Chrome(options=options)
        driver.set_page_load_timeout(SETTINGS_11880['page_load_timeout'])

        # Remove webdriver property to avoid detection
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        return driver

    # ── URL Building ────────────────────────────────────────────────────

    def _get_city_slug(self, city: str) -> str:
        """Convert city name to 11880.com URL slug"""
        city_lower = city.lower().strip()

        # Check predefined mappings first
        if city_lower in CITY_URL_MAP:
            return CITY_URL_MAP[city_lower]

        # Replace German umlauts
        slug = city_lower
        slug = slug.replace('ä', 'ae').replace('ö', 'oe').replace('ü', 'ue')
        slug = slug.replace('ß', 'ss')

        # Replace spaces with hyphens, remove special chars
        slug = re.sub(r'[^a-z0-9-]', '-', slug)
        slug = re.sub(r'-+', '-', slug).strip('-')

        return slug

    def _get_category_slug(self, category_key: str) -> str:
        """Get the 11880.com search slug for a category"""
        if category_key in CATEGORY_11880_MAP:
            return CATEGORY_11880_MAP[category_key]

        # Fallback: use the first keyword from config, slugified
        config = CATEGORIES.get(category_key, {})
        keyword = config.get('keywords', [category_key])[0]
        slug = keyword.lower()
        slug = slug.replace('ä', 'ae').replace('ö', 'oe').replace('ü', 'ue')
        slug = slug.replace('ß', 'ss')
        slug = re.sub(r'[^a-z0-9-]', '-', slug).strip('-')
        return slug

    def _build_search_url(self, category_key: str, city: str, page: int = 1) -> str:
        """Build 11880.com search URL"""
        cat_slug = self._get_category_slug(category_key)
        city_slug = self._get_city_slug(city)

        url = f"{SETTINGS_11880['base_url']}/suche/{cat_slug}/{city_slug}"
        if page > 1:
            url += f"?page={page}"
        return url

    # ── Page Fetching & Parsing ─────────────────────────────────────────

    def _fetch_page(self, driver: webdriver.Chrome, url: str) -> Optional[str]:
        """Fetch a page using Selenium, return page source HTML"""
        for attempt in range(SETTINGS_11880['max_retries']):
            try:
                driver.get(url)

                # Wait for listing content to load
                try:
                    WebDriverWait(driver, SETTINGS_11880['element_wait_timeout']).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR,
                            '[class*="result"], [class*="listing"], [class*="entry"], '
                            '[class*="treffer"], [class*="business"], [data-type="entry"]'))
                    )
                except TimeoutException:
                    # Page loaded but no listings found (could be last page)
                    pass

                # Small random delay to mimic human behavior
                time.sleep(random.uniform(0.5, 1.5))

                return driver.page_source

            except TimeoutException:
                self.logger.warning(f"  Timeout loading {url} (attempt {attempt + 1})")
                time.sleep(2 ** attempt)
            except WebDriverException as e:
                self.logger.warning(f"  WebDriver error for {url}: {e} (attempt {attempt + 1})")
                time.sleep(2 ** attempt)

        self.logger.error(f"  Failed to load {url} after {SETTINGS_11880['max_retries']} attempts")
        return None

    def _parse_listings(self, html: str, category_key: str) -> List[Dict[str, Any]]:
        """Parse business listings from 11880.com search results page HTML"""
        soup = BeautifulSoup(html, 'html.parser')
        listings = []

        category_name = CATEGORIES.get(category_key, {}).get('name', category_key)

        # 11880.com uses various selectors for listing cards.
        # We try multiple strategies to find business entries.

        # Strategy 1: Look for structured result items by common class patterns
        # Note: use word-boundary-aware patterns to avoid matching parent
        # containers (e.g., "search-results" should not match "search-result")
        result_items = soup.select(
            '.result-item, .entry-item, '
            '[class*="treffer"], .ResultItem, '
            '.listing-entry, .search-result'
        )

        # Strategy 2: If no results from Strategy 1, look for article/li patterns
        if not result_items:
            result_items = soup.select(
                'article[class*="result"], div[class*="result"] > div, '
                'ul[class*="result"] > li, section[class*="result"] > div'
            )

        # Strategy 3: Look for elements containing business data markers
        if not result_items:
            # Find the smallest container for each /branchenbuch/ link
            # that is not a child of another matched container
            branchenbuch_links = soup.find_all('a', href=re.compile(r'/branchenbuch/'))
            seen_elements = set()
            for link in branchenbuch_links:
                # Walk up to the nearest container element
                parent = link.parent
                for _ in range(5):
                    if parent and parent.name in ('div', 'article', 'li', 'section'):
                        parent_id = id(parent)
                        if parent_id not in seen_elements:
                            # Check this isn't a parent of an already-matched element
                            seen_elements.add(parent_id)
                            result_items.append(parent)
                        break
                    parent = parent.parent if parent else None

            # Deduplicate: remove items that are ancestors of other items
            if len(result_items) > 1:
                filtered = []
                for item in result_items:
                    is_ancestor = any(
                        item is not other and item in (other.parents or [])
                        for other in result_items
                    )
                    if not is_ancestor:
                        filtered.append(item)
                result_items = filtered

        self.logger.debug(f"  Found {len(result_items)} potential listing elements")

        for item in result_items:
            lead = self._extract_lead_from_element(item, category_name)
            if lead and lead.get('name'):
                listings.append(lead)

        return listings

    def _extract_lead_from_element(self, element, category_name: str) -> Optional[Dict[str, Any]]:
        """Extract business data from a single listing element"""
        lead = {
            'name': '',
            'category': category_name,
            'email': '',
            'website': '',
            'phone': '',
            'address': '',
        }

        try:
            # ── Business Name ───────────────────────────────────────
            # Try multiple selectors for business name
            name_el = (
                element.select_one('[class*="name"] a, [class*="title"] a, h2 a, h3 a') or
                element.select_one('[class*="name"], [class*="title"], h2, h3') or
                element.select_one('a[href*="/branchenbuch/"]')
            )
            if name_el:
                lead['name'] = name_el.get_text(strip=True)

                # Get detail page URL for potential further scraping
                if name_el.get('href'):
                    href = name_el['href']
                    if href.startswith('/'):
                        href = SETTINGS_11880['base_url'] + href
                    lead['_detail_url'] = href

            if not lead['name']:
                return None

            # ── Phone Number ────────────────────────────────────────
            phone_el = (
                element.select_one('[class*="phone"] a, [class*="telefon"] a, a[href^="tel:"]') or
                element.select_one('[class*="phone"], [class*="telefon"], [class*="tel"]')
            )
            if phone_el:
                if phone_el.get('href', '').startswith('tel:'):
                    lead['phone'] = phone_el['href'].replace('tel:', '').strip()
                else:
                    lead['phone'] = phone_el.get_text(strip=True)

            # Also check for phone in data attributes
            if not lead['phone']:
                tel_link = element.find('a', href=re.compile(r'^tel:'))
                if tel_link:
                    lead['phone'] = tel_link['href'].replace('tel:', '').strip()

            # ── Address ─────────────────────────────────────────────
            addr_el = (
                element.select_one('[class*="address"], [class*="adress"], [class*="addr"]') or
                element.select_one('address') or
                element.select_one('[class*="street"], [class*="location"]')
            )
            if addr_el:
                lead['address'] = ' '.join(addr_el.get_text(strip=True).split())

            # ── Website ─────────────────────────────────────────────
            website_el = element.select_one(
                'a[class*="website"], a[class*="web"], '
                'a[href*="redirect"], a[data-action*="website"]'
            )
            if website_el:
                href = website_el.get('href', '')
                # 11880 often uses redirect links; extract actual URL if possible
                if 'redirect' in href or 'url=' in href:
                    # Try to extract target URL from redirect
                    match = re.search(r'url=([^&]+)', href)
                    if match:
                        from urllib.parse import unquote
                        lead['website'] = unquote(match.group(1))
                    else:
                        lead['website'] = href
                elif href.startswith('http') and '11880.com' not in href:
                    lead['website'] = href

            # Also look for website links that open externally
            if not lead['website']:
                external_links = element.find_all('a', href=re.compile(r'^https?://'))
                for link in external_links:
                    href = link.get('href', '')
                    if '11880.com' not in href and 'google' not in href:
                        lead['website'] = href
                        break

            # ── Email ───────────────────────────────────────────────
            email_el = element.select_one('a[href^="mailto:"]')
            if email_el:
                lead['email'] = email_el['href'].replace('mailto:', '').strip()

            # Generate email from website if not found directly
            if not lead['email'] and lead['website']:
                lead['email'] = self._generate_email(lead['website'])

            # Clean up internal fields
            lead.pop('_detail_url', None)

            return lead

        except Exception as e:
            self.logger.debug(f"  Error extracting lead: {e}")
            return None

    def _has_next_page(self, html: str, current_page: int) -> bool:
        """Check if there's a next page of results"""
        soup = BeautifulSoup(html, 'html.parser')

        # Look for explicit "next" links
        next_link = soup.select_one('a[class*="next"], a[rel="next"]')
        if next_link:
            return True

        # Check if pagination contains any page number higher than current
        page_links = soup.select(
            '[class*="pagination"] a[href*="page="], '
            '[class*="pager"] a[href*="page="]'
        )
        max_page = current_page
        for link in page_links:
            href = link.get('href', '')
            match = re.search(r'page=(\d+)', href)
            if match:
                max_page = max(max_page, int(match.group(1)))

        return max_page > current_page

    def _generate_email(self, website: str) -> str:
        """Generate info@ email from website domain"""
        try:
            parsed = urlparse(website)
            domain = parsed.netloc or parsed.path
            domain = domain.replace('www.', '').strip('/')

            # Skip directory/social domains
            skip_domains = SETTINGS.get('skip_domains', set())
            if any(domain == d or domain.endswith('.' + d) for d in skip_domains):
                return ''

            if domain:
                return f"info@{domain}"
        except Exception:
            pass
        return ''

    # ── Detail Page Scraping ────────────────────────────────────────────

    def _scrape_detail_page(self, driver: webdriver.Chrome, url: str,
                            lead: Dict[str, Any]) -> Dict[str, Any]:
        """Scrape additional details from a business's detail page on 11880.com"""
        html = self._fetch_page(driver, url)
        if not html:
            return lead

        soup = BeautifulSoup(html, 'html.parser')

        # Try to get phone if missing
        if not lead.get('phone'):
            phone_el = (
                soup.select_one('a[href^="tel:"]') or
                soup.select_one('[class*="phone"], [class*="telefon"]')
            )
            if phone_el:
                if phone_el.get('href', '').startswith('tel:'):
                    lead['phone'] = phone_el['href'].replace('tel:', '').strip()
                else:
                    lead['phone'] = phone_el.get_text(strip=True)

        # Try to get address if missing
        if not lead.get('address'):
            addr_el = soup.select_one('[class*="address"], address, [class*="street"]')
            if addr_el:
                lead['address'] = ' '.join(addr_el.get_text(strip=True).split())

        # Try to get website if missing
        if not lead.get('website'):
            website_el = soup.select_one('a[class*="website"], a[data-action*="website"]')
            if website_el:
                href = website_el.get('href', '')
                if href.startswith('http') and '11880.com' not in href:
                    lead['website'] = href

            if not lead.get('website'):
                external_links = soup.find_all('a', href=re.compile(r'^https?://'))
                for link in external_links:
                    href = link.get('href', '')
                    if '11880.com' not in href and 'google' not in href:
                        lead['website'] = href
                        break

        # Try to get email if missing
        if not lead.get('email'):
            email_el = soup.select_one('a[href^="mailto:"]')
            if email_el:
                lead['email'] = email_el['href'].replace('mailto:', '').strip()
            elif lead.get('website'):
                lead['email'] = self._generate_email(lead['website'])

        return lead

    # ── Checkpoint Management ───────────────────────────────────────────

    def _load_checkpoint(self) -> None:
        """Load checkpoint for resume"""
        if not self.checkpoint_file.exists():
            self.logger.info("No checkpoint found, starting fresh")
            return

        try:
            with open(self.checkpoint_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            self.processed_urls = set(data.get('processed_urls', []))
            self.stats = data.get('stats', self.stats)
            self.leads_collected = self.stats.get('leads_collected', 0)

            self.logger.info(f"Loaded checkpoint: {len(self.processed_urls)} URLs processed, "
                           f"{self.leads_collected} leads collected")
        except Exception as e:
            self.logger.warning(f"Failed to load checkpoint: {e}")

    def _save_checkpoint(self) -> None:
        """Save progress to checkpoint file"""
        try:
            self.stats['leads_collected'] = self.leads_collected
            self.stats['last_checkpoint'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            data = {
                'processed_urls': list(self.processed_urls),
                'stats': self.stats,
            }

            temp_file = self.checkpoint_file.with_suffix('.tmp')
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            temp_file.replace(self.checkpoint_file)
        except Exception as e:
            self.logger.warning(f"Failed to save checkpoint: {e}")

    def _clear_checkpoint(self) -> None:
        """Clear checkpoint for fresh start"""
        if self.checkpoint_file.exists():
            self.checkpoint_file.unlink()
        self.processed_urls.clear()

    # ── Main Scraping Logic ─────────────────────────────────────────────

    def scrape_category_city(self, category_key: str, city: str,
                             driver: webdriver.Chrome) -> List[Dict[str, Any]]:
        """Scrape all listings for a category in a city"""
        category_name = CATEGORIES.get(category_key, {}).get('name', category_key)
        self.logger.info(f"\n{'='*60}")
        self.logger.info(f"Scraping: {category_name} in {city}")
        self.logger.info(f"{'='*60}")

        all_page_leads = []
        page = 1
        consecutive_empty = 0

        while page <= SETTINGS_11880['max_pages']:
            # Check max leads
            if self.max_leads and self.leads_collected >= self.max_leads:
                self.logger.info(f"  Max leads ({self.max_leads}) reached")
                break

            url = self._build_search_url(category_key, city, page)

            # Skip already processed URLs (resume)
            if url in self.processed_urls:
                self.logger.debug(f"  Skipping processed page: {url}")
                page += 1
                continue

            self.logger.info(f"  Page {page}: {url}")

            html = self._fetch_page(driver, url)
            if not html:
                consecutive_empty += 1
                if consecutive_empty >= 3:
                    self.logger.info(f"  3 consecutive failures, moving to next category/city")
                    break
                page += 1
                continue

            # Parse listings
            listings = self._parse_listings(html, category_key)
            self.logger.info(f"  Found {len(listings)} listings on page {page}")

            if not listings:
                consecutive_empty += 1
                if consecutive_empty >= 2:
                    self.logger.info(f"  No more listings found, moving on")
                    break
                page += 1
                self.processed_urls.add(url)
                continue

            consecutive_empty = 0

            # Process leads
            for lead in listings:
                if self.max_leads and self.leads_collected >= self.max_leads:
                    break

                # Deduplicate by name+address
                dedup_key = f"{lead['name'].lower()}|{lead.get('address', '').lower()}"
                if dedup_key in self.processed_urls:
                    continue

                self.processed_urls.add(dedup_key)
                all_page_leads.append(lead)

                with self._leads_lock:
                    self.leads_collected += 1

                # Update category stats
                if category_name not in self.stats['leads_by_category']:
                    self.stats['leads_by_category'][category_name] = 0
                self.stats['leads_by_category'][category_name] += 1

            self.processed_urls.add(url)
            self.stats['pages_scraped'] += 1
            self.stats['total_listings_found'] += len(listings)

            # Save checkpoint periodically
            if len(all_page_leads) % SETTINGS_11880['checkpoint_interval'] == 0 and all_page_leads:
                self._save_checkpoint()

            # Check for next page
            if not self._has_next_page(html, page):
                self.logger.info(f"  No more pages available")
                break

            # Random delay between pages
            delay = random.uniform(SETTINGS_11880['page_delay_min'], SETTINGS_11880['page_delay_max'])
            time.sleep(delay)
            page += 1

        self.logger.info(f"  Collected {len(all_page_leads)} leads for {category_name} in {city}")
        self._save_checkpoint()

        return all_page_leads

    def run_scraping_workflow(self) -> None:
        """Main scraping workflow"""
        self.logger.info("\n" + "=" * 60)
        self.logger.info("STARTING 11880.COM SCRAPING WORKFLOW")
        self.logger.info("=" * 60)

        self.logger.info(f"\nConfiguration:")
        self.logger.info(f"  Categories: {', '.join([CATEGORIES[c]['name'] for c in self.selected_categories if c in CATEGORIES])}")
        self.logger.info(f"  Cities: {', '.join(self.selected_cities)}")
        if self.max_leads:
            self.logger.info(f"  Max leads: {self.max_leads}")
        self.logger.info(f"  Source: 11880.com (FREE - no API costs)")

        total_searches = len(self.selected_categories) * len(self.selected_cities)
        self.logger.info(f"  Total search combinations: {total_searches}")

        # Create browser
        driver = None
        try:
            driver = self._create_browser()
            self.logger.info("Browser initialized")

            for category_key in self.selected_categories:
                if category_key not in CATEGORIES:
                    self.logger.warning(f"Unknown category: {category_key}, skipping")
                    continue

                for city in self.selected_cities:
                    try:
                        leads = self.scrape_category_city(category_key, city, driver)
                        self.all_leads.extend(leads)

                        if self.max_leads and self.leads_collected >= self.max_leads:
                            self.logger.info(f"\nMax leads ({self.max_leads}) reached, stopping")
                            break

                        # Delay between city searches
                        time.sleep(random.uniform(1.0, 3.0))

                    except KeyboardInterrupt:
                        self.logger.warning("\nInterrupted by user. Progress saved.")
                        self._save_checkpoint()
                        raise

                    except Exception as e:
                        self.logger.error(f"Error scraping {category_key} in {city}: {e}")
                        continue

                if self.max_leads and self.leads_collected >= self.max_leads:
                    break

        finally:
            if driver:
                driver.quit()
                self.logger.info("Browser closed")

        # Deduplicate
        self.all_leads = self._deduplicate_leads(self.all_leads)
        self.logger.info(f"\nScraping completed. Total unique leads: {len(self.all_leads)}")

    def _deduplicate_leads(self, leads: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Remove duplicates by website or name"""
        seen = set()
        unique = []

        for lead in leads:
            website = lead.get('website', '').lower().strip()
            name = lead.get('name', '').lower().strip()
            identifier = website if website else name

            if identifier and identifier not in seen:
                seen.add(identifier)
                unique.append(lead)

        removed = len(leads) - len(unique)
        if removed > 0:
            self.logger.info(f"Removed {removed} duplicates")

        return unique

    def export_to_csv(self) -> Optional[str]:
        """Export leads to CSV"""
        if not self.all_leads:
            self.logger.warning("No leads to export")
            return None

        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"{SETTINGS_11880['output_dir']}/leads_11880_{timestamp}.csv"

            df = pd.DataFrame(self.all_leads)

            # Ensure column order matches Google Places scraper
            columns = ['name', 'category', 'email', 'website', 'phone', 'address']
            existing = [col for col in columns if col in df.columns]
            df = df[existing]

            df.to_csv(filename, index=False, encoding='utf-8-sig')

            self.logger.info(f"Exported {len(df)} leads to: {filename}")
            return filename

        except Exception as e:
            self.logger.error(f"Failed to export CSV: {e}")
            return None

    def print_summary(self) -> None:
        """Print scraping summary"""
        if not self.all_leads:
            print("\nNo leads collected\n")
            return

        websites = len([l for l in self.all_leads if l.get('website')])
        emails = len([l for l in self.all_leads if l.get('email')])
        phones = len([l for l in self.all_leads if l.get('phone')])
        addresses = len([l for l in self.all_leads if l.get('address')])

        total = len(self.all_leads)
        print("\n" + "=" * 60)
        print("11880.COM SCRAPING SUMMARY")
        print("=" * 60)
        print(f"\nTotal Leads: {total}")
        print(f"With Website: {websites} ({websites/total*100:.1f}%)")
        print(f"With Email: {emails} ({emails/total*100:.1f}%)")
        print(f"With Phone: {phones} ({phones/total*100:.1f}%)")
        print(f"With Address: {addresses} ({addresses/total*100:.1f}%)")

        print(f"\nBy Category:")
        categories = {}
        for lead in self.all_leads:
            cat = lead.get('category', 'Unknown')
            categories[cat] = categories.get(cat, 0) + 1
        for cat, count in sorted(categories.items()):
            print(f"  {cat}: {count} leads")

        print(f"\nPages Scraped: {self.stats['pages_scraped']}")
        print(f"Total Listings Found: {self.stats['total_listings_found']}")
        print(f"Cost: $0.00 (FREE - no API costs)")
        print("=" * 60 + "\n")


# ── Interactive Selection ───────────────────────────────────────────────

def interactive_category_selection() -> List[str]:
    """Interactive CLI for category selection"""
    print("\n" + "=" * 70)
    print("CATEGORY SELECTION (11880.com)")
    print("=" * 70)
    print("\nAvailable categories:")

    categories_list = list(CATEGORIES.items())
    for i, (key, config) in enumerate(categories_list, 1):
        slug = CATEGORY_11880_MAP.get(key, key)
        print(f"  {i}. {config['name']} (11880 slug: {slug})")
    print(f"  {len(categories_list) + 1}. ALL categories")

    while True:
        try:
            choice = input("\nEnter numbers (comma-separated) or 'all': ").strip().lower()
            if choice == 'all' or choice == str(len(categories_list) + 1):
                return list(CATEGORIES.keys())

            indices = [int(x.strip()) - 1 for x in choice.split(',')]
            selected = [categories_list[i][0] for i in indices if 0 <= i < len(categories_list)]

            if selected:
                print(f"\nSelected:")
                for cat in selected:
                    print(f"  - {CATEGORIES[cat]['name']}")
                return selected
            else:
                print("Invalid selection.")
        except (ValueError, IndexError):
            print("Invalid input.")


def interactive_city_input() -> List[str]:
    """Interactive city input"""
    print("\n" + "=" * 70)
    print("CITY INPUT (11880.com)")
    print("=" * 70)
    print("\nEnter German city names (comma-separated)")
    print("Examples: Berlin, München, Hamburg, Köln, Frankfurt")

    choice = input("\nCities: ").strip()
    cities = [c.strip() for c in choice.split(',') if c.strip()]

    if cities:
        print(f"\nWill scrape:")
        for city in cities:
            print(f"  - {city}")
        return cities
    else:
        print("No cities entered. Using Berlin as default.")
        return ['Berlin']


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='11880.com German Business Leads Scraper')
    parser.add_argument('--categories', type=str, help='Categories (comma-separated)')
    parser.add_argument('--cities', type=str, help='Cities (comma-separated)')
    parser.add_argument('--max-leads', type=int, help='Maximum number of leads')
    parser.add_argument('--micro-test', action='store_true', help='Micro-test mode (20 leads)')
    parser.add_argument('--resume', action='store_true', help='Resume from checkpoint')
    parser.add_argument('--verbose', action='store_true', help='Verbose logging')
    parser.add_argument('--interactive', action='store_true', help='Interactive mode')
    parser.add_argument('--no-headless', action='store_true', help='Show browser window')

    args = parser.parse_args()

    try:
        if args.micro_test:
            print("\nMICRO-TEST MODE (11880.com)")
            print("  Max leads: 20")
            print("  Cost: $0.00 (FREE)")
            args.max_leads = 20

        if args.interactive:
            categories = interactive_category_selection()
            cities = interactive_city_input()
        else:
            categories = args.categories.split(',') if args.categories else None
            cities = args.cities.split(',') if args.cities else None

        scraper = Scraper11880(
            categories=categories,
            cities=cities,
            max_leads=args.max_leads,
            resume=args.resume,
            verbose=args.verbose,
            headless=not args.no_headless,
        )

        scraper.run_scraping_workflow()
        scraper.export_to_csv()
        scraper.print_summary()

    except KeyboardInterrupt:
        print("\n\nScraping interrupted. Progress saved to checkpoint.")
        print("Run with --resume to continue.")
        sys.exit(1)

    except Exception as e:
        print(f"\n\nFatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()

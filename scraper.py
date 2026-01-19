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
from playwright.async_api import async_playwright, Page, Browser

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

        # Playwright browser
        self.playwright = None
        self.browser = None

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

    async def init_browser(self):
        """Initialize Playwright browser"""
        if not self.playwright:
            self.logger.info("Initializing Playwright browser...")
            self.playwright = await async_playwright().start()
            self.browser = await self.playwright.chromium.launch(
                headless=True,
                args=['--disable-blink-features=AutomationControlled']
            )
            self.logger.info("Playwright browser initialized")

    async def close_browser(self):
        """Close Playwright browser"""
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
            self.logger.info("Playwright browser closed")

    async def scrape_gelbeseiten_playwright(self, keyword: str, city: str) -> Optional[str]:
        """
        Scrape Gelbe Seiten using Playwright for JavaScript rendering

        Args:
            keyword: Business category keyword
            city: City name

        Returns:
            HTML content or None if failed
        """
        query = quote_plus(keyword)
        location = quote_plus(city)
        url = f"https://www.gelbeseiten.de/Suche/{query}/{location}"

        self.logger.info(f"Scraping Gelbe Seiten with Playwright: {keyword} in {city}")
        self.stats['total_scrapes'] += 1

        try:
            # Ensure browser is initialized
            await self.init_browser()

            # Create new page
            page = await self.browser.new_page()

            # Set user agent
            await page.set_extra_http_headers({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept-Language': 'de-DE,de;q=0.9',
            })

            # Navigate to page
            await page.goto(url, wait_until='domcontentloaded', timeout=30000)

            # Wait for business listings to load
            try:
                await page.wait_for_selector('article, .mod-Treffer', timeout=5000)
            except:
                self.logger.warning("No business listings found on page")

            # Get page content
            html_content = await page.content()

            # DEBUG: Save HTML to file for inspection
            debug_file = Path('output') / f'debug_html_{keyword}_{city}.html'
            debug_file.write_text(html_content, encoding='utf-8')
            self.logger.debug(f"Saved HTML to {debug_file} for debugging")

            # Close page
            await page.close()

            self.logger.debug(f"Response size: {len(html_content)} bytes")
            self.stats['successful_scrapes'] += 1

            return html_content

        except Exception as e:
            self.logger.error(f"Failed to scrape Gelbe Seiten for {keyword} in {city}: {str(e)}")
            self.stats['failed_scrapes'] += 1
            return None

    def scrape_gelbeseiten(self, keyword: str, city: str) -> Optional[str]:
        """
        Scrape Gelbe Seiten (German Yellow Pages) - Deprecated, use Playwright version

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

    def parse_html_structure(self, html_content: str) -> Dict[str, Any]:
        """
        Parse HTML to extract structured data including links

        Args:
            html_content: Raw HTML content

        Returns:
            Dictionary with text and links
        """
        soup = BeautifulSoup(html_content, 'html.parser')

        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.decompose()

        # Extract all links with their text and context
        links = []
        business_data = []

        # For Gelbe Seiten, extract business listings with their websites
        # Enhanced article selector with more patterns
        article_patterns = ['gs-card', 'mod-treffer', 'entry', 'teilnehmer', 'listing', 'result-item', 'business-card']
        articles_found = soup.find_all(['article', 'div'], class_=lambda x: x and any(pattern in str(x).lower() for pattern in article_patterns))

        self.logger.debug(f"Found {len(articles_found)} article elements matching patterns: {article_patterns}")

        for article in articles_found:
            business_name = None
            website_url = None
            website_strategy = None
            phone = None
            address = None

            # Try to find business name (multiple strategies)
            name_elem = article.find(['h2', 'h3', 'h1'], class_=lambda x: x and any(c in str(x).lower() for c in ['name', 'title', 'headline', 'heading']))
            if not name_elem:
                # Try finding it in links
                name_link = article.find('a', class_=lambda x: x and 'link-name' in str(x).lower())
                if name_link:
                    name_elem = name_link

            if name_elem:
                business_name = name_elem.get_text(strip=True)

            # Try to find website link (multiple strategies)
            # Strategy 1: Look for link with "website" or "webseite" text
            web_link = article.find('a', href=True, string=lambda x: x and ('webseite' in x.lower() or 'website' in x.lower() or 'homepage' in x.lower()))
            if web_link and web_link.get('href'):
                href = web_link['href']
                if href.startswith('http') and 'gelbeseiten.de' not in href:
                    website_url = href
                    website_strategy = "Strategy 1: Link text"

            # Strategy 2: Look for link with website/homepage in class
            if not website_url:
                web_link = article.find('a', href=True, class_=lambda x: x and any(c in str(x).lower() for c in ['website', 'homepage', 'webseite', 'link-website']))
                if web_link and web_link.get('href'):
                    href = web_link['href']
                    if href.startswith('http') and 'gelbeseiten.de' not in href:
                        website_url = href
                        website_strategy = "Strategy 2: Link class"

            # Strategy 3: Look for any link in a div/button with website-related class
            if not website_url:
                website_container = article.find(['div', 'button', 'span'], class_=lambda x: x and any(c in str(x).lower() for c in ['website', 'webseite', 'homepage']))
                if website_container:
                    web_link = website_container.find('a', href=True)
                    if web_link and web_link.get('href'):
                        href = web_link['href']
                        if href.startswith('http') and 'gelbeseiten.de' not in href:
                            website_url = href
                            website_strategy = "Strategy 3: Container"

            # Strategy 4: Look for data attributes on any element (not just links)
            if not website_url:
                # Check all common data attribute patterns
                data_patterns = ['data-href', 'data-url', 'data-website', 'data-link', 'data-website-url', 'data-target-url']
                for pattern in data_patterns:
                    elem = article.find(attrs={pattern: True})
                    if elem and elem.get(pattern):
                        potential_url = elem.get(pattern)
                        if potential_url and potential_url.startswith('http') and 'gelbeseiten.de' not in potential_url:
                            website_url = potential_url
                            website_strategy = f"Strategy 4: Data attribute ({pattern})"
                            break

            # Strategy 5: Look for button elements with data attributes
            if not website_url:
                buttons = article.find_all(['button', 'a', 'div'], attrs={'class': True})
                for button in buttons:
                    # Check if button text suggests it's a website link
                    button_text = button.get_text(strip=True).lower()
                    if any(word in button_text for word in ['webseite', 'website', 'homepage']):
                        # Look for data attributes
                        for attr, value in button.attrs.items():
                            if attr.startswith('data-') and isinstance(value, str) and value.startswith('http'):
                                if 'gelbeseiten.de' not in value:
                                    website_url = value
                                    website_strategy = f"Strategy 5: Button data ({attr})"
                                    break
                        if website_url:
                            break

            # Strategy 6: Check onclick handlers for URLs
            if not website_url:
                onclick_elems = article.find_all(attrs={'onclick': True})
                for elem in onclick_elems:
                    onclick = elem.get('onclick', '')
                    # Look for URLs in onclick handlers (e.g., onclick="window.open('https://...')")
                    url_match = re.search(r'https?://[^\s\'"]+', onclick)
                    if url_match:
                        potential_url = url_match.group(0)
                        if 'gelbeseiten.de' not in potential_url:
                            website_url = potential_url
                            website_strategy = "Strategy 6: onclick handler"
                            break

            # Strategy 7: Last resort - find any external link that looks like a business website
            if not website_url:
                all_links = article.find_all('a', href=True)
                excluded_domains = ['facebook.com', 'instagram.com', 'twitter.com', 'youtube.com',
                                  'linkedin.com', 'google.com', 'maps.google', 'gelbeseiten.de',
                                  'apple.com', 'microsoft.com']
                for link in all_links:
                    href = link.get('href', '')
                    if href.startswith('http'):
                        # Check if it's not an excluded domain
                        if not any(domain in href.lower() for domain in excluded_domains):
                            # Check if it looks like a business domain (.de, .com, etc.)
                            if any(tld in href for tld in ['.de', '.com', '.net', '.eu', '.org']):
                                website_url = href
                                website_strategy = "Strategy 7: Generic external link"
                                break

            if business_name and website_url:
                self.logger.debug(f"Found business-website mapping ({website_strategy}): {business_name} → {website_url}")
                business_data.append({
                    'name': business_name,
                    'website': website_url,
                    'extraction_strategy': website_strategy
                })
            elif business_name:
                self.logger.debug(f"Found business without website: {business_name}")

        # Log extraction statistics
        websites_found = len(business_data)
        self.logger.info(f"Article extraction complete: {len(articles_found)} articles processed, {websites_found} with websites ({websites_found/len(articles_found)*100:.1f}%)" if articles_found else "No articles found")

        # Also extract all links as fallback
        for link in soup.find_all('a', href=True):
            href = link['href']
            link_text = link.get_text(strip=True)

            # Filter for likely business websites (exclude navigation, social media, etc.)
            if href and link_text:
                # Clean up the URL
                if href.startswith('http'):
                    # Skip common non-business domains
                    skip_domains = ['facebook.com', 'instagram.com', 'twitter.com', 'youtube.com',
                                  'linkedin.com', 'google.com', 'maps.google', 'gelbeseiten.de',
                                  '/suche/', '/branche/', '/ort/']
                    if not any(domain in href.lower() for domain in skip_domains):
                        links.append({
                            'url': href,
                            'text': link_text
                        })

        # Extract text content
        text = soup.get_text(separator='\n', strip=True)

        return {
            'text': text,
            'links': links,
            'business_data': business_data
        }

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

        # Parse HTML structure to get text and links
        parsed = self.parse_html_structure(html_content)
        text = parsed['text']
        links = parsed['links']
        business_data = parsed['business_data']

        # Limit text size to avoid token limits
        max_chars = 6000
        if len(text) > max_chars:
            text = text[:max_chars]

        # Create links section for prompt
        links_text = ""

        # If we have structured business data, use that
        if business_data:
            links_text = "\n\nBusiness-Website Mappings (USE THESE):\n"
            for biz in business_data[:20]:
                links_text += f"- Business: {biz['name']} → Website: {biz['website']}\n"
            self.logger.debug(f"Found {len(business_data)} business-website mappings: {business_data[:3]}")

        # Otherwise use all links
        elif links:
            links_text = "\n\nWebsite URLs found:\n"
            for i, link in enumerate(links[:30]):  # Limit to 30 links
                links_text += f"- {link['text']}: {link['url']}\n"
            self.logger.debug(f"URLs found: {[link['url'] for link in links[:10]]}")

        self.logger.info(f"Extracting businesses with AI for {category} in {city} (found {len(links)} potential links, {len(business_data)} structured mappings)")

        try:
            # Customize instructions based on what data we have
            if business_data:
                instructions = """CRITICAL - USE THE MAPPINGS ABOVE:
- There is a "Business-Website Mappings" section above with exact name→website pairs
- For each business you extract, if its name matches or is similar to a name in the mappings, USE THAT WEBSITE
- Include the website field for businesses that have mappings
- Extract ALL businesses found in the content"""
            else:
                instructions = """IMPORTANT:
- Match business names from the content with their corresponding website URLs from the "Website URLs found" section
- Extract ALL businesses found in the content
- Include the website URL for each business if available"""

            user_prompt = f"""Search context: {category} in {city}, Deutschland

Content to extract from:
{text}
{links_text}

{instructions}"""

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

            # Debug: Log raw AI response
            self.logger.debug(f"AI raw response (first 500 chars): {content[:500]}")

            # Parse JSON response
            # Remove markdown code blocks if present
            if content.startswith('```'):
                content = re.sub(r'^```json?\n?', '', content)
                content = re.sub(r'\n?```$', '', content)

            businesses = json.loads(content)

            if not isinstance(businesses, list):
                self.logger.warning("AI response is not a list, wrapping in list")
                businesses = [businesses]

            # Debug: Log sample business with fields
            if businesses:
                sample = businesses[0]
                self.logger.debug(f"Sample business fields: {list(sample.keys())}")
                if 'website' in sample:
                    self.logger.debug(f"Sample website value: {sample['website']}")

            self.logger.info(f"Extracted {len(businesses)} businesses, {sum(1 for b in businesses if b.get('website'))} with websites")
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

        # NOTE: Google Maps scraping disabled - returns compressed binary data
        # Re-enable if proper decompression is implemented
        # google_html = self.scrape_google_maps(keyword, city)
        # if google_html:
        #     google_leads = self.extract_with_ai(google_html, category_name, city)
        #     for lead in google_leads:
        #         enriched = self.enrich_lead(lead, 'google_maps', category_name)
        #         leads.append(enriched)
        #         self.stats['by_source']['google_maps'] += 1

        # Scrape Gelbe Seiten with Playwright for JavaScript rendering
        directory_html = await self.scrape_gelbeseiten_playwright(keyword, city)
        if directory_html:
            directory_leads = self.extract_with_ai(directory_html, category_name, city)
            for lead in directory_leads:
                enriched = self.enrich_lead(lead, 'gelbeseiten', category_name)
                leads.append(enriched)
                self.stats['by_source']['directory'] += 1

        # Delay between requests
        await asyncio.sleep(self.request_delay)

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

        # Close browser
        await self.close_browser()

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

        # Ensure all important columns exist (add empty ones if missing)
        column_order = ['name', 'email', 'website', 'category', 'phone', 'address', 'additional_info', 'source', 'scraped_at']
        for col in column_order:
            if col not in df.columns:
                df[col] = ''

        # Reorder columns
        df = df[column_order]

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

        # Ensure all important columns exist (add empty ones if missing)
        column_order = ['name', 'email', 'website', 'category', 'phone', 'address', 'additional_info', 'source', 'scraped_at']
        for col in column_order:
            if col not in df.columns:
                df[col] = ''

        # Reorder columns
        df = df[column_order]

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

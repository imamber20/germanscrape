#!/usr/bin/env python3
"""
Debug script to fetch and inspect Gelbe Seiten HTML structure
"""

import requests
from bs4 import BeautifulSoup
from pathlib import Path
import json

def fetch_gelbeseiten(keyword: str, city: str):
    """Fetch a Gelbe Seiten page and save it for inspection"""

    # Construct URL
    base_url = "https://www.gelbeseiten.de"
    search_url = f"{base_url}/suche/{keyword}/{city}"

    print(f"Fetching: {search_url}")

    # Headers to mimic a browser
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'de-DE,de;q=0.9,en;q=0.8',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1'
    }

    try:
        # Fetch the page
        response = requests.get(search_url, headers=headers, timeout=30)
        response.raise_for_status()

        print(f"✓ Status: {response.status_code}")
        print(f"✓ Content length: {len(response.content)} bytes")
        print(f"✓ Content type: {response.headers.get('content-type', 'unknown')}")

        # Save raw HTML
        output_dir = Path('output')
        output_dir.mkdir(exist_ok=True)

        html_file = output_dir / f'debug_{keyword}_{city}.html'
        html_file.write_text(response.text, encoding='utf-8')
        print(f"✓ Saved HTML to: {html_file}")

        # Parse with BeautifulSoup
        soup = BeautifulSoup(response.text, 'html.parser')

        # Find all article tags (business listings)
        articles = soup.find_all('article')
        print(f"\n✓ Found {len(articles)} article elements")

        if articles:
            # Inspect first article in detail
            first_article = articles[0]
            print(f"\n=== FIRST ARTICLE STRUCTURE ===")
            print(f"Article classes: {first_article.get('class', [])}")
            print(f"Article ID: {first_article.get('id', 'none')}")

            # Find all links in the article
            links = first_article.find_all('a', href=True)
            print(f"\n✓ Found {len(links)} links in first article:")
            for i, link in enumerate(links[:5], 1):  # Show first 5 links
                href = link.get('href', '')
                text = link.get_text(strip=True)
                classes = link.get('class', [])
                data_attrs = {k: v for k, v in link.attrs.items() if k.startswith('data-')}

                print(f"\nLink {i}:")
                print(f"  Text: {text[:50]}")
                print(f"  Href: {href[:80]}")
                print(f"  Classes: {classes}")
                if data_attrs:
                    print(f"  Data attributes: {data_attrs}")

            # Look for website-related elements
            print(f"\n=== WEBSITE-RELATED ELEMENTS ===")

            # Search for "webseite" text
            webseite_elements = first_article.find_all(string=lambda x: x and 'webseite' in x.lower())
            print(f"✓ Found {len(webseite_elements)} elements with 'webseite' text")
            for elem in webseite_elements[:3]:
                parent = elem.parent
                print(f"  Parent tag: {parent.name}, classes: {parent.get('class', [])}")

            # Search for buttons
            buttons = first_article.find_all(['button', 'a'], class_=lambda x: x and any(c in str(x).lower() for c in ['button', 'btn', 'link']))
            print(f"\n✓ Found {len(buttons)} button-like elements")
            for i, btn in enumerate(buttons[:3], 1):
                print(f"  Button {i}: {btn.name}, classes: {btn.get('class', [])}, text: {btn.get_text(strip=True)[:30]}")

            # Save first article HTML for detailed inspection
            article_file = output_dir / f'debug_first_article_{keyword}_{city}.html'
            article_file.write_text(str(first_article), encoding='utf-8')
            print(f"\n✓ Saved first article HTML to: {article_file}")

            # Extract business name
            name_elem = first_article.find(['h2', 'h3'], class_=lambda x: x and any(c in str(x).lower() for c in ['name', 'title', 'heading']))
            if name_elem:
                print(f"\n✓ Business name: {name_elem.get_text(strip=True)}")

        # Look for overall structure
        print(f"\n=== OVERALL PAGE STRUCTURE ===")
        result_container = soup.find(['div', 'section', 'main'], class_=lambda x: x and any(c in str(x).lower() for c in ['result', 'listing', 'search']))
        if result_container:
            print(f"✓ Result container found: {result_container.name}, classes: {result_container.get('class', [])}")

        return response.text

    except Exception as e:
        print(f"✗ Error: {e}")
        return None

if __name__ == '__main__':
    # Test with a common search
    fetch_gelbeseiten('dachdecker', 'münchen')

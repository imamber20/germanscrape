#!/usr/bin/env python3
"""
Unit tests for scraper_11880.py
Tests URL building, HTML parsing, deduplication, email generation, and checkpoint logic.
No browser or network needed — everything is tested with mock HTML.

Run:  python -m pytest tests/test_scraper_11880.py -v
"""

import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scraper_11880 import (
    Scraper11880,
    CATEGORY_11880_MAP,
    CITY_URL_MAP,
    SETTINGS_11880,
)
from config import CATEGORIES


# ── Fixtures ────────────────────────────────────────────────────────────

@pytest.fixture
def scraper(tmp_path):
    """Create a scraper instance with temp dirs for tests (no browser)."""
    # Override checkpoint file to temp location
    original_cp = SETTINGS_11880['checkpoint_file']
    original_output = SETTINGS_11880['output_dir']
    SETTINGS_11880['checkpoint_file'] = str(tmp_path / 'progress_test.json')
    SETTINGS_11880['output_dir'] = str(tmp_path / 'output')

    s = Scraper11880(
        categories=['dachdecker'],
        cities=['Berlin'],
        max_leads=10,
        verbose=False,
        headless=True,
    )

    yield s

    # Restore
    SETTINGS_11880['checkpoint_file'] = original_cp
    SETTINGS_11880['output_dir'] = original_output


# ── URL Building Tests ──────────────────────────────────────────────────

class TestURLBuilding:
    """Test URL slug generation for cities and categories."""

    def test_city_slug_with_umlaut(self, scraper):
        assert scraper._get_city_slug('München') == 'muenchen'

    def test_city_slug_koeln(self, scraper):
        assert scraper._get_city_slug('Köln') == 'koeln'

    def test_city_slug_duesseldorf(self, scraper):
        assert scraper._get_city_slug('Düsseldorf') == 'duesseldorf'

    def test_city_slug_nuernberg(self, scraper):
        assert scraper._get_city_slug('Nürnberg') == 'nuernberg'

    def test_city_slug_fuerth(self, scraper):
        assert scraper._get_city_slug('Fürth') == 'fuerth'

    def test_city_slug_plain(self, scraper):
        assert scraper._get_city_slug('Berlin') == 'berlin'

    def test_city_slug_hamburg(self, scraper):
        assert scraper._get_city_slug('Hamburg') == 'hamburg'

    def test_city_slug_berlin_mitte_maps_to_berlin(self, scraper):
        assert scraper._get_city_slug('Berlin Mitte') == 'berlin'

    def test_city_slug_frankfurt(self, scraper):
        assert scraper._get_city_slug('Frankfurt') == 'frankfurt-am-main'

    def test_city_slug_unknown_city_with_umlaut(self, scraper):
        """Unknown city should still get umlauts replaced."""
        slug = scraper._get_city_slug('Würzburg')
        assert slug == 'wuerzburg'

    def test_city_slug_unknown_city_with_spaces(self, scraper):
        slug = scraper._get_city_slug('Bad Homburg')
        assert slug == 'bad-homburg'

    def test_category_slug_dachdecker(self, scraper):
        assert scraper._get_category_slug('dachdecker') == 'dachdecker'

    def test_category_slug_sanitaer(self, scraper):
        assert scraper._get_category_slug('sanitärinstallateure') == 'sanitaerinstallateur'

    def test_category_slug_elektrotechnik(self, scraper):
        assert scraper._get_category_slug('elektrotechnik') == 'elektriker'

    def test_category_slug_autowerkstaetten(self, scraper):
        assert scraper._get_category_slug('autowerkstätten') == 'autowerkstatt'

    def test_all_categories_have_slug_mapping(self):
        """Every category in config.py should have an 11880 slug mapping."""
        for key in CATEGORIES:
            assert key in CATEGORY_11880_MAP, f"Missing 11880 slug for category: {key}"

    def test_build_search_url_page1(self, scraper):
        url = scraper._build_search_url('dachdecker', 'Berlin', page=1)
        assert url == 'https://www.11880.com/suche/dachdecker/berlin'
        assert '?page=' not in url  # Page 1 has no query param

    def test_build_search_url_page2(self, scraper):
        url = scraper._build_search_url('dachdecker', 'Berlin', page=2)
        assert url == 'https://www.11880.com/suche/dachdecker/berlin?page=2'

    def test_build_search_url_umlaut_city(self, scraper):
        url = scraper._build_search_url('dachdecker', 'München', page=1)
        assert url == 'https://www.11880.com/suche/dachdecker/muenchen'

    def test_build_search_url_umlaut_category(self, scraper):
        url = scraper._build_search_url('autowerkstätten', 'Berlin', page=3)
        assert url == 'https://www.11880.com/suche/autowerkstatt/berlin?page=3'


# ── Email Generation Tests ──────────────────────────────────────────────

class TestEmailGeneration:
    """Test info@ email generation from website URLs."""

    def test_simple_domain(self, scraper):
        assert scraper._generate_email('https://www.mueller-dach.de') == 'info@mueller-dach.de'

    def test_domain_with_www(self, scraper):
        email = scraper._generate_email('https://www.schmidt-bau.de')
        assert email == 'info@schmidt-bau.de'

    def test_domain_without_www(self, scraper):
        email = scraper._generate_email('https://example-firma.de')
        assert email == 'info@example-firma.de'

    def test_empty_website(self, scraper):
        assert scraper._generate_email('') == ''

    def test_skip_facebook(self, scraper):
        assert scraper._generate_email('https://www.facebook.com/somepage') == ''

    def test_skip_instagram(self, scraper):
        assert scraper._generate_email('https://www.instagram.com/business') == ''

    def test_skip_youtube(self, scraper):
        assert scraper._generate_email('https://www.youtube.com/channel') == ''


# ── HTML Parsing Tests ──────────────────────────────────────────────────

class TestHTMLParsing:
    """Test business listing extraction from mock 11880.com HTML."""

    MOCK_LISTING_HTML_STRATEGY3 = """
    <html>
    <body>
    <div class="search-results">
        <div class="result-container">
            <a href="/branchenbuch/berlin/01234B5678/mueller-dachdeckerei.html">
                <h3>Müller Dachdeckerei GmbH</h3>
            </a>
            <a href="tel:+493012345678">030 1234 5678</a>
            <div class="address">Hauptstr. 10, 10115 Berlin</div>
            <a href="https://www.mueller-dach.de" class="website">Webseite</a>
            <a href="mailto:info@mueller-dach.de">E-Mail</a>
        </div>
        <div class="result-container">
            <a href="/branchenbuch/berlin/09876B5432/schmidt-dach.html">
                <h3>Schmidt Dach &amp; Bau</h3>
            </a>
            <a href="tel:+493098765432">030 9876 5432</a>
            <div class="address">Berliner Str. 5, 10243 Berlin</div>
        </div>
    </div>
    </body>
    </html>
    """

    MOCK_LISTING_HTML_STRATEGY1 = """
    <html>
    <body>
    <div class="search-results">
        <div class="result-item">
            <h2 class="title"><a href="/branchenbuch/berlin/111/abc-dach.html">ABC Dachdecker</a></h2>
            <span class="phone"><a href="tel:+4930111111">030 111111</a></span>
            <span class="address">Musterweg 1, 10115 Berlin</span>
            <a class="website" href="https://www.abc-dach.de">Website</a>
        </div>
        <div class="result-item">
            <h2 class="title"><a href="/branchenbuch/berlin/222/xyz-bau.html">XYZ Bau GmbH</a></h2>
            <span class="phone"><a href="tel:+4930222222">030 222222</a></span>
            <span class="address">Teststr. 7, 10117 Berlin</span>
        </div>
    </div>
    </body>
    </html>
    """

    MOCK_EMPTY_HTML = """
    <html>
    <body>
    <div class="search-results">
        <p>Keine Ergebnisse gefunden.</p>
    </div>
    </body>
    </html>
    """

    MOCK_PAGINATION_HTML = """
    <html>
    <body>
    <div class="result-item">
        <h2><a href="/branchenbuch/berlin/333/test.html">Test Firma</a></h2>
    </div>
    <div class="pagination">
        <a href="/suche/dachdecker/berlin?page=1">1</a>
        <a href="/suche/dachdecker/berlin?page=2">2</a>
        <a href="/suche/dachdecker/berlin?page=3" class="next">3</a>
    </div>
    </body>
    </html>
    """

    MOCK_PAGINATION_LAST_PAGE = """
    <html>
    <body>
    <div class="result-item">
        <h2><a href="/branchenbuch/berlin/444/last.html">Last Firma</a></h2>
    </div>
    <div class="pagination">
        <a href="/suche/dachdecker/berlin?page=1">1</a>
        <a href="/suche/dachdecker/berlin?page=2">2</a>
    </div>
    </body>
    </html>
    """

    def test_parse_listings_strategy1(self, scraper):
        """Strategy 1: result-item class pattern."""
        listings = scraper._parse_listings(self.MOCK_LISTING_HTML_STRATEGY1, 'dachdecker')
        assert len(listings) == 2

        lead1 = listings[0]
        assert lead1['name'] == 'ABC Dachdecker'
        assert lead1['category'] == 'Dachdecker'
        assert lead1['phone'] == '+4930111111'
        assert lead1['address'] == 'Musterweg 1, 10115 Berlin'
        assert lead1['website'] == 'https://www.abc-dach.de'
        assert lead1['email'] == 'info@abc-dach.de'

        lead2 = listings[1]
        assert lead2['name'] == 'XYZ Bau GmbH'
        assert lead2['phone'] == '+4930222222'
        assert lead2['website'] == ''  # No website in mock

    def test_parse_listings_strategy3_branchenbuch_links(self, scraper):
        """Strategy 3: Find containers with /branchenbuch/ links."""
        listings = scraper._parse_listings(self.MOCK_LISTING_HTML_STRATEGY3, 'dachdecker')
        assert len(listings) >= 1

        # First listing should have full data
        names = [l['name'] for l in listings]
        assert any('Müller' in n for n in names)

    def test_parse_empty_results(self, scraper):
        """No listings should be returned for empty results page."""
        listings = scraper._parse_listings(self.MOCK_EMPTY_HTML, 'dachdecker')
        assert len(listings) == 0

    def test_parse_extracts_email_from_mailto(self, scraper):
        """Direct mailto: links should be extracted."""
        listings = scraper._parse_listings(self.MOCK_LISTING_HTML_STRATEGY3, 'dachdecker')
        emails = [l['email'] for l in listings if l.get('email')]
        assert any('mueller-dach.de' in e for e in emails)

    def test_has_next_page_true(self, scraper):
        """Should detect next page when pagination has higher page numbers."""
        assert scraper._has_next_page(self.MOCK_PAGINATION_HTML, 1) is True

    def test_has_next_page_false_on_last(self, scraper):
        """Should return False when on last page."""
        assert scraper._has_next_page(self.MOCK_PAGINATION_LAST_PAGE, 2) is False

    def test_has_next_page_false_on_empty(self, scraper):
        """No pagination on empty page."""
        assert scraper._has_next_page(self.MOCK_EMPTY_HTML, 1) is False


# ── Deduplication Tests ─────────────────────────────────────────────────

class TestDeduplication:
    """Test lead deduplication logic."""

    def test_dedup_by_website(self, scraper):
        leads = [
            {'name': 'Firma A', 'website': 'https://firma-a.de', 'email': ''},
            {'name': 'Firma A Copy', 'website': 'https://firma-a.de', 'email': ''},
            {'name': 'Firma B', 'website': 'https://firma-b.de', 'email': ''},
        ]
        result = scraper._deduplicate_leads(leads)
        assert len(result) == 2

    def test_dedup_by_name_when_no_website(self, scraper):
        leads = [
            {'name': 'Firma C', 'website': '', 'email': ''},
            {'name': 'firma c', 'website': '', 'email': ''},  # Same name different case
            {'name': 'Firma D', 'website': '', 'email': ''},
        ]
        result = scraper._deduplicate_leads(leads)
        assert len(result) == 2

    def test_dedup_preserves_order(self, scraper):
        leads = [
            {'name': 'First', 'website': 'https://first.de', 'email': ''},
            {'name': 'Second', 'website': 'https://second.de', 'email': ''},
            {'name': 'First Duplicate', 'website': 'https://first.de', 'email': ''},
        ]
        result = scraper._deduplicate_leads(leads)
        assert result[0]['name'] == 'First'
        assert result[1]['name'] == 'Second'

    def test_dedup_empty_list(self, scraper):
        assert scraper._deduplicate_leads([]) == []


# ── Checkpoint Tests ────────────────────────────────────────────────────

class TestCheckpoint:
    """Test checkpoint save/load/clear."""

    def test_save_and_load_checkpoint(self, scraper, tmp_path):
        scraper.processed_urls.add('https://test.com/page1')
        scraper.processed_urls.add('some-dedup-key')
        scraper.leads_collected = 5
        scraper.stats['pages_scraped'] = 3

        scraper._save_checkpoint()
        assert scraper.checkpoint_file.exists()

        # Create new scraper and load
        SETTINGS_11880['checkpoint_file'] = str(scraper.checkpoint_file)
        new_scraper = Scraper11880(
            categories=['dachdecker'],
            cities=['Berlin'],
            max_leads=10,
            resume=True,
            verbose=False,
        )
        assert 'https://test.com/page1' in new_scraper.processed_urls
        assert 'some-dedup-key' in new_scraper.processed_urls
        assert new_scraper.leads_collected == 5

    def test_clear_checkpoint(self, scraper):
        scraper.processed_urls.add('test')
        scraper._save_checkpoint()
        assert scraper.checkpoint_file.exists()

        scraper._clear_checkpoint()
        assert not scraper.checkpoint_file.exists()
        assert len(scraper.processed_urls) == 0

    def test_load_missing_checkpoint(self, scraper):
        """Loading when no checkpoint exists should not crash."""
        scraper._clear_checkpoint()
        scraper._load_checkpoint()  # Should log "No checkpoint found"
        assert scraper.leads_collected == 0


# ── CSV Export Tests ────────────────────────────────────────────────────

class TestCSVExport:
    """Test CSV export functionality."""

    def test_export_creates_file(self, scraper, tmp_path):
        scraper.all_leads = [
            {
                'name': 'Test Firma GmbH',
                'category': 'Dachdecker',
                'email': 'info@test-firma.de',
                'website': 'https://test-firma.de',
                'phone': '+49 30 1234567',
                'address': 'Teststr. 1, 10115 Berlin',
            }
        ]

        filename = scraper.export_to_csv()
        assert filename is not None
        assert Path(filename).exists()

        # Check CSV content
        import pandas as pd
        df = pd.read_csv(filename)
        assert len(df) == 1
        assert df.iloc[0]['name'] == 'Test Firma GmbH'
        assert df.iloc[0]['email'] == 'info@test-firma.de'
        assert df.iloc[0]['phone'] == '+49 30 1234567'

    def test_export_column_order(self, scraper, tmp_path):
        scraper.all_leads = [
            {
                'name': 'A', 'category': 'B', 'email': 'C',
                'website': 'D', 'phone': 'E', 'address': 'F',
            }
        ]
        filename = scraper.export_to_csv()
        import pandas as pd
        df = pd.read_csv(filename)
        assert list(df.columns) == ['name', 'category', 'email', 'website', 'phone', 'address']

    def test_export_empty_leads(self, scraper):
        scraper.all_leads = []
        assert scraper.export_to_csv() is None


# ── Max Leads Limiting Tests ────────────────────────────────────────────

class TestMaxLeads:
    """Test that max_leads cap is respected."""

    def test_scraper_initializes_with_max_leads(self, tmp_path):
        SETTINGS_11880['checkpoint_file'] = str(tmp_path / 'cp.json')
        SETTINGS_11880['output_dir'] = str(tmp_path / 'out')

        s = Scraper11880(
            categories=['dachdecker'],
            cities=['Berlin'],
            max_leads=5,
        )
        assert s.max_leads == 5

    def test_default_cities_populated(self, scraper):
        cities = scraper._get_default_cities()
        assert 'Berlin' in cities
        assert 'Hamburg' in cities
        assert 'München' in cities
        assert len(cities) >= 20


# ── Integration-style: Full Parse Pipeline ──────────────────────────────

class TestParsePipeline:
    """Test the full pipeline from HTML to deduplicated leads."""

    MOCK_HTML_MULTI = """
    <html>
    <body>
    <div class="result-item">
        <h2><a href="/branchenbuch/berlin/001/firma-alpha.html">Firma Alpha</a></h2>
        <a href="tel:+49301111">030 1111</a>
        <span class="address">Str 1, 10115 Berlin</span>
        <a class="website" href="https://firma-alpha.de">Web</a>
    </div>
    <div class="result-item">
        <h2><a href="/branchenbuch/berlin/002/firma-beta.html">Firma Beta</a></h2>
        <a href="tel:+49302222">030 2222</a>
        <span class="address">Str 2, 10117 Berlin</span>
    </div>
    <div class="result-item">
        <h2><a href="/branchenbuch/berlin/003/firma-gamma.html">Firma Gamma</a></h2>
        <a href="tel:+49303333">030 3333</a>
        <span class="address">Str 3, 10119 Berlin</span>
        <a class="website" href="https://firma-gamma.de">Web</a>
        <a href="mailto:kontakt@firma-gamma.de">Mail</a>
    </div>
    </body>
    </html>
    """

    def test_full_parse_pipeline(self, scraper):
        """Parse HTML -> extract leads -> check all fields."""
        listings = scraper._parse_listings(self.MOCK_HTML_MULTI, 'dachdecker')
        assert len(listings) == 3

        # Firma Alpha: has website, email should be generated
        alpha = next(l for l in listings if 'Alpha' in l['name'])
        assert alpha['website'] == 'https://firma-alpha.de'
        assert alpha['email'] == 'info@firma-alpha.de'
        assert alpha['phone'] == '+49301111'
        assert 'Berlin' in alpha['address']

        # Firma Beta: no website, no email
        beta = next(l for l in listings if 'Beta' in l['name'])
        assert beta['website'] == ''
        assert beta['email'] == ''
        assert beta['phone'] == '+49302222'

        # Firma Gamma: has mailto, should use direct email
        gamma = next(l for l in listings if 'Gamma' in l['name'])
        assert gamma['email'] == 'kontakt@firma-gamma.de'
        assert gamma['website'] == 'https://firma-gamma.de'

    def test_parse_then_dedup(self, scraper):
        """Duplicates should be removed after parsing."""
        listings = scraper._parse_listings(self.MOCK_HTML_MULTI, 'dachdecker')
        # Add a duplicate
        listings.append(listings[0].copy())
        deduped = scraper._deduplicate_leads(listings)
        assert len(deduped) == 3  # One duplicate removed

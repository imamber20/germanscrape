"""
Configuration file for German Handwerk Leads Scraper
Contains categories, zip ranges, and application settings
"""

# Business categories with German keywords
CATEGORIES = {
    'dachdecker': {
        'name': 'Dachdecker',
        'keywords': ['Dachdecker', 'Dachdeckerei', 'Dachsanierung', 'Dachbau']
    },
    'heizungsbauer': {
        'name': 'Heizungsbauer',
        'keywords': ['Heizungsbauer', 'Heizungsbau', 'Heizungstechnik']
    },
    'sanitärinstallateure': {
        'name': 'Sanitärinstallateure',
        'keywords': ['Sanitärinstallateur', 'Sanitärtechnik', 'Badezimmerbau']
    },
    'elektrotechnik': {
        'name': 'Elektrotechnik',
        'keywords': ['Elektrotechnik', 'Elektroinstallation', 'Elektriker']
    },
    'malerbetriebe': {
        'name': 'Malerbetriebe',
        'keywords': ['Malerbetrieb', 'Malerarbeiten', 'Fassadenanstrich']
    },
    'fliesenleger': {
        'name': 'Fliesenleger',
        'keywords': ['Fliesenleger', 'Fliesenverlegung', 'Badfliesen']
    },
    'bauunternehmen': {
        'name': 'Bauunternehmen',
        'keywords': ['Bauunternehmen', 'Baufirma', 'Hochbauunternehmen']
    },
    'trockenbaufirmen': {
        'name': 'Trockenbaufirmen',
        'keywords': ['Trockenbau', 'Gipskartonbau', 'Innenausbau']
    },
    'zimmereien': {
        'name': 'Zimmereien',
        'keywords': ['Zimmerei', 'Holzbau', 'Dachstuhlbau']
    },
    'abrissunternehmen': {
        'name': 'Abrissunternehmen',
        'keywords': ['Abrissunternehmen', 'Abbruchfirma', 'Abbrucharbeiten']
    }
}

# German zip code ranges by region
ZIP_RANGES = {
    '80000-80999': {
        'cities': ['München', 'Nürnberg', 'Augsburg'],
        'state': 'Bayern',
        'region': 'Bavaria'
    },
    '10000-10999': {
        'cities': ['Berlin Mitte', 'Friedrichshain', 'Kreuzberg'],
        'state': 'Berlin',
        'region': 'Berlin'
    },
    '20000-20999': {
        'cities': ['Hamburg'],
        'state': 'Hamburg',
        'region': 'Hamburg'
    },
    '50000-50999': {
        'cities': ['Köln', 'Bonn', 'Düsseldorf'],
        'state': 'NRW',
        'region': 'North Rhine-Westphalia'
    },
    '60000-60999': {
        'cities': ['Frankfurt', 'Wiesbaden', 'Darmstadt'],
        'state': 'Hessen',
        'region': 'Hesse'
    },
    '70000-70999': {
        'cities': ['Stuttgart', 'Heilbronn'],
        'state': 'Baden-Württemberg',
        'region': 'Baden-Württemberg'
    },
    '30000-30999': {
        'cities': ['Hannover', 'Hildesheim'],
        'state': 'Niedersachsen',
        'region': 'Lower Saxony'
    },
    '40000-40999': {
        'cities': ['Essen', 'Dortmund', 'Bochum'],
        'state': 'NRW',
        'region': 'North Rhine-Westphalia'
    },
    '01000-01999': {
        'cities': ['Dresden', 'Leipzig', 'Chemnitz'],
        'state': 'Sachsen',
        'region': 'Saxony'
    },
    '90000-90999': {
        'cities': ['Nürnberg', 'Fürth', 'Erlangen'],
        'state': 'Bayern',
        'region': 'Bavaria'
    }
}

# Application settings
SETTINGS = {
    # Rate limiting
    'request_delay': 2,  # seconds between requests
    'retry_attempts': 3,
    'retry_delay': 2,  # initial retry delay in seconds

    # Scraping limits
    'max_results_per_search': 20,
    'timeout': 30,  # seconds

    # AI extraction
    'ai_model': 'gpt-4o-mini',
    'ai_temperature': 0.1,
    'max_tokens': 4000,

    # Output
    'output_dir': 'output',
    'log_level': 'INFO',  # DEBUG, INFO, WARNING, ERROR

    # Data validation
    'required_fields': ['name', 'category'],
    'optional_fields': ['address', 'phone', 'website', 'email', 'additional_info']
}

# System prompt for AI extraction
AI_EXTRACTION_PROMPT = """You are a data extraction specialist for German business information.

Extract business information from the provided content and return a JSON array of businesses.

Each business should have:
- name (string, required): Business name
- category (string, required): Type of business (e.g., Dachdecker, Heizungsbauer)
- address (string, optional): Full address
- phone (string, optional): Phone number in German format
- website (string, optional): Website URL (full URL with https://)
- additional_info (string, optional): Any relevant info like certifications, service areas, opening hours

Rules:
1. Return ONLY valid JSON, no markdown formatting
2. Extract ALL businesses found in the content
3. If a field is not found, omit it from the object
4. Ensure phone numbers are properly formatted
5. Ensure websites include the full URL with protocol (https://)
6. For category, use the German term from the search query if available

Return format:
[
  {
    "name": "Mustermann Dachdeckerei GmbH",
    "category": "Dachdecker",
    "address": "Musterstraße 123, 80331 München",
    "phone": "+49 89 12345678",
    "website": "https://www.mustermann-dach.de",
    "additional_info": "Meisterbetrieb seit 1985, Flachdach-Spezialist"
  }
]
"""

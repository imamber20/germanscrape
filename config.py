"""
Configuration file for German Handwerk Leads Scraper
Contains categories, zip ranges, and application settings
"""

# Business categories with German keywords and Google Places types
CATEGORIES = {
    'dachdecker': {
        'name': 'Dachdecker',
        'keywords': ['Dachdecker', 'Dachdeckerei', 'Dachsanierung', 'Dachbau'],
        'google_type': 'roofing_contractor'
    },
    'heizungsbauer': {
        'name': 'Heizungsbauer',
        'keywords': ['Heizungsbauer', 'Heizungsbau', 'Heizungstechnik'],
        'google_type': 'plumber'  # Google combines heating and plumbing
    },
    'sanitärinstallateure': {
        'name': 'Sanitärinstallateure',
        'keywords': ['Sanitärinstallateur', 'Sanitärtechnik', 'Badezimmerbau'],
        'google_type': 'plumber'
    },
    'elektrotechnik': {
        'name': 'Elektrotechnik',
        'keywords': ['Elektrotechnik', 'Elektroinstallation', 'Elektriker'],
        'google_type': 'electrician'
    },
    'malerbetriebe': {
        'name': 'Malerbetriebe',
        'keywords': ['Malerbetrieb', 'Malerarbeiten', 'Fassadenanstrich'],
        'google_type': 'painter'
    },
    'fliesenleger': {
        'name': 'Fliesenleger',
        'keywords': ['Fliesenleger', 'Fliesenverlegung', 'Badfliesen'],
        'google_type': 'general_contractor'  # Google doesn't have tile-specific
    },
    'bauunternehmen': {
        'name': 'Bauunternehmen',
        'keywords': ['Bauunternehmen', 'Baufirma', 'Hochbauunternehmen'],
        'google_type': 'general_contractor'
    },
    'trockenbaufirmen': {
        'name': 'Trockenbaufirmen',
        'keywords': ['Trockenbau', 'Gipskartonbau', 'Innenausbau'],
        'google_type': 'general_contractor'
    },
    'zimmereien': {
        'name': 'Zimmereien',
        'keywords': ['Zimmerei', 'Zimmerer', 'Schreiner', 'Tischler', 'Holzbau', 'Dachstuhlbau', 'Holzkonstruktion', 'Zimmermannsbetrieb'],
        'google_type': 'general_contractor'
    },
    'abrissunternehmen': {
        'name': 'Abrissunternehmen',
        'keywords': ['Abrissunternehmen', 'Abbruchfirma', 'Abbrucharbeiten'],
        'google_type': 'general_contractor'
    },
    'autohändler': {
        'name': 'Autohändler',
        'keywords': ['Autohändler', 'KFZ Handel', 'Gebrauchtwagen Händler', 'Neuwagen Verkauf',
                     'Fahrzeughandel', 'Autohaus Händler', 'PKW Verkauf', 'Fahrzeugvertrieb',
                     'Autohandel Firma', 'Automobilhandel'],
        'google_type': 'car_dealer'
    },
    'autohäuser': {
        'name': 'Autohäuser',
        'keywords': ['Autohaus', 'Autohaus Betrieb', 'Fahrzeugzentrum', 'Markenautohaus',
                     'Autohandelshaus', 'PKW Autohaus', 'Autohaus Service', 'Autoverkaufshaus',
                     'Mobilitätszentrum Auto', 'Autohaus Firma'],
        'google_type': 'car_dealer'
    },
    'autowerkstätten': {
        'name': 'Autowerkstätten',
        'keywords': ['Autowerkstatt', 'KFZ Werkstatt', 'Fahrzeugreparatur', 'Autoservice',
                     'Wartung Auto', 'Reparaturbetrieb KFZ', 'Meisterwerkstatt Auto',
                     'Fahrzeugservice', 'Auto Instandsetzung', 'KFZ Servicebetrieb'],
        'google_type': 'car_repair'
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
    # Google Places API - OPTIMIZED
    'google_search_radius': 50000,  # 50km radius for each city search (covers entire Munich metropolitan area)
    'google_max_results': 60,  # Google Places limit (20 per page, 3 pages max)
    'google_request_delay': 0.02,  # OPTIMIZED: 0.02s = 50 req/sec (was 0.1s = 10 req/sec)
    'concurrent_requests': 25,  # OPTIMIZED: Process 25 businesses in parallel

    # Rate limiting
    'request_delay': 0.5,  # OPTIMIZED: Reduced from 1s to 0.5s
    'retry_attempts': 3,
    'retry_delay': 2,  # initial retry delay in seconds

    # AI extraction (for email generation and data filtering)
    'ai_model': 'gpt-4o-mini',
    'ai_temperature': 0.1,
    'max_tokens': 2000,
    'use_ai_filtering': False,  # OPTIMIZED: Disabled to save time (was True)

    # Checkpoint/Resume
    'checkpoint_interval': 50,  # Save progress every 50 businesses
    'checkpoint_file': 'progress.json',

    # Output - OPTIMIZED (essential fields for quality leads)
    'output_dir': 'output',
    'log_level': 'INFO',  # DEBUG, INFO, WARNING, ERROR
    'output_fields': ['name', 'category', 'email', 'website', 'phone', 'address'],  # All essential contact fields

    # Data validation
    'required_fields': ['name', 'category'],
    'optional_fields': ['website', 'email'],  # OPTIMIZED: Removed unnecessary fields

    # Cost tracking
    'google_nearby_search_cost': 0.032,  # $32 per 1000 requests
    'google_place_details_cost': 0.017,  # $17 per 1000 requests
    'google_geocoding_cost': 0.005,  # $5 per 1000 requests

    # Micro-test mode
    'micro_test_max_leads': 20,  # Default for micro-test mode

    # Domains that are directories or social-media profiles, not the business's
    # own site.  Leads with these as their website are skipped — the generated
    # email would belong to the platform, not the business.
    'skip_domains': {
        'facebook.com', 'instagram.com', 'twitter.com', 'x.com',
        'linkedin.com', 'pinterest.com', 'youtube.com', 'tiktok.com',
        'google.com', 'yelp.com', 'tripadvisor.com',
        'kfzwerkstatt.io', 'malerfinder.de',
        'jameda.de', 'branchenbuch.de', 'dasbranchenbuch.de',
        'trustedshops.de',
    },
}

# System prompt for AI filtering (Google Places provides clean data already)
AI_FILTERING_PROMPT = """You are a quality control specialist for German business lead data.

Your task: Filter and validate business leads to ensure they match the target category.

Input: A list of businesses from Google Places API
Output: Filtered list containing ONLY businesses that match the target category

Rules:
1. Return ONLY valid JSON array, no markdown code blocks, no explanations
2. KEEP businesses that clearly match the category (e.g., keep "Müller Dachdeckerei" for category "Dachdecker")
3. REMOVE businesses that are:
   - Suppliers/wholesalers (e.g., "Baustoffhandel", "Großhandel")
   - Retailers/shops (e.g., "Baumarkt", "Fachhandel")
   - Manufacturers (e.g., "Hersteller", "Produktion")
   - Not relevant to the category (e.g., "Restaurant" in Dachdecker search)
4. KEEP all fields from the input exactly as they are
5. If you're unsure, KEEP the business (better to have more than miss good leads)

Example - Category: "Dachdecker"
Input:
[
  {"name": "Müller Dachdeckerei GmbH", "category": "Dachdecker", "website": "https://mueller-dach.de"},
  {"name": "Baustoffe Schmidt - Dachziegel Großhandel", "category": "Dachdecker", "website": "https://baustoffe-schmidt.de"},
  {"name": "Zimmerei & Dachbau Meier", "category": "Dachdecker", "website": "https://meier-dach.de"}
]

Output (removed the wholesaler):
[
  {"name": "Müller Dachdeckerei GmbH", "category": "Dachdecker", "website": "https://mueller-dach.de"},
  {"name": "Zimmerei & Dachbau Meier", "category": "Dachdecker", "website": "https://meier-dach.de"}
]
"""

# Email generation prompt (used when website exists but no email)
AI_EMAIL_GENERATION_PROMPT = """Generate professional email addresses for German businesses based on their website domain.

Rules:
1. Use common German business email patterns: info@, kontakt@, office@
2. Extract domain from website URL
3. Return JSON object with "email" field
4. Use info@ as the primary pattern (most common in Germany)

Example:
Input: {"website": "https://www.mueller-dachdeckerei.de"}
Output: {"email": "info@mueller-dachdeckerei.de"}

Input: {"website": "https://schmidt-dach.com"}
Output: {"email": "info@schmidt-dach.com"}
"""

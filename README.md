# German Handwerk Leads Scraper

Automated B2B lead generation system for German blue-collar businesses (Handwerk). Scrapes Google Maps and German business directories to collect contact information for tradesmen companies.

## 🎯 Purpose

This tool is designed for **HeyKiki** - an AI voice bot service targeting German tradesmen. It automatically collects qualified leads including:

- Company name
- Email addresses (auto-generated as info@domain.de)
- Website
- Phone number
- Address
- Business category
- Additional information (certifications, service areas, hours)

## 🏗️ Features

- ✅ **Multi-source scraping**: Google Maps + Gelbe Seiten (German Yellow Pages)
- ✅ **AI-powered extraction**: Uses OpenAI GPT-4o-mini to parse HTML and extract structured data
- ✅ **Smart deduplication**: Removes duplicates by website, phone, and name
- ✅ **Email generation**: Automatically creates info@domain.de emails from websites
- ✅ **German encoding support**: Proper UTF-8-BOM encoding for ä, ö, ü, ß characters
- ✅ **Comprehensive logging**: Debug-friendly logs for troubleshooting
- ✅ **Async scraping**: Efficient parallel processing
- ✅ **Rate limiting**: Respectful delays between requests
- ✅ **Export formats**: Both CSV and Excel (.xlsx)
- ✅ **Progress tracking**: Real-time progress bars
- ✅ **Graceful error handling**: Continues on failures

## 📋 Requirements

- Python 3.10 or higher
- OpenAI API key (for AI extraction)

## 🚀 Installation

### 1. Clone the repository

```bash
git clone <repository-url>
cd germanscrape
```

### 2. Create virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure API keys

```bash
# Copy example environment file
cp .env.example .env

# Edit .env and add your OpenAI API key
nano .env  # or use your preferred editor
```

Your `.env` file should look like:
```
OPENAI_API_KEY=sk-your-actual-openai-api-key-here
```

## 📖 Usage

### Basic Usage

Scrape all configured categories and regions:

```bash
python scraper.py
```

### Test Mode

Test with limited scraping (2 cities only):

```bash
python scraper.py --test --max-cities 2
```

### Scrape Specific Category

```bash
python scraper.py --category dachdecker
```

### Scrape Specific Region

```bash
python scraper.py --ziprange 80000-80999
```

### Combine Filters

```bash
python scraper.py --category heizungsbauer --ziprange 10000-10999
```

### Verbose Logging

```bash
python scraper.py --verbose
```

### Custom Output Filenames

```bash
python scraper.py --output-csv my_leads.csv --output-excel my_leads.xlsx
```

## 📊 Business Categories

The scraper supports these 10 German trade categories:

1. **Dachdecker** - Roofers
2. **Heizungsbauer** - Heating technicians
3. **Sanitärinstallateure** - Plumbers
4. **Elektrotechnik** - Electricians
5. **Malerbetriebe** - Painters
6. **Fliesenleger** - Tile layers
7. **Bauunternehmen** - Construction companies
8. **Trockenbaufirmen** - Drywall companies
9. **Zimmereien** - Carpentry
10. **Abrissunternehmen** - Demolition companies

## 🗺️ Covered Regions

The scraper covers 10 major German regions:

- **Bayern (Bavaria)**: München, Nürnberg, Augsburg, Fürth, Erlangen
- **Berlin**: Berlin Mitte, Friedrichshain, Kreuzberg
- **Hamburg**: Hamburg
- **NRW**: Köln, Bonn, Düsseldorf, Essen, Dortmund, Bochum
- **Hessen**: Frankfurt, Wiesbaden, Darmstadt
- **Baden-Württemberg**: Stuttgart, Heilbronn
- **Niedersachsen**: Hannover, Hildesheim
- **Sachsen**: Dresden, Leipzig, Chemnitz

## 📁 Output Files

The scraper generates two output files in the `output/` directory:

### CSV File (`leads_YYYYMMDD_HHMMSS.csv`)
- UTF-8-BOM encoded for proper German character display
- Opens correctly in Excel without encoding issues
- Comma-separated values

### Excel File (`leads_YYYYMMDD_HHMMSS.xlsx`)
- Formatted columns
- Native Excel format
- Supports all German characters

### Output Columns

| Column | Description | Example |
|--------|-------------|---------|
| name | Company name | Müller Dachdeckerei GmbH |
| email | Email address | info@mueller-dach.de |
| website | Company website | https://www.mueller-dach.de |
| category | Business category | Dachdecker |
| phone | Phone number | +49 89 12345678 |
| address | Full address | Musterstraße 123, 80331 München |
| additional_info | Extra information | Meisterbetrieb seit 1985 |
| source | Data source | google_maps / gelbeseiten |
| scraped_at | Timestamp | 2025-01-18T14:30:45.123456 |

## 📈 Performance

- **Speed**: ~2 cities per minute (with 2-second delays)
- **Coverage**: 50-100 leads per category per region
- **Accuracy**: 85-95% data quality
- **Cost**: ~$0.01-0.05 per 100 leads (OpenAI API)

## 🔍 Logs

All scraping activities are logged to `logs/scraper_YYYYMMDD_HHMMSS.log`

Log levels:
- **INFO**: Progress updates, successful operations
- **DEBUG**: Detailed responses, AI prompts (use `--verbose`)
- **WARNING**: Retries, partial failures
- **ERROR**: Critical failures, exceptions

## 🛠️ Configuration

Edit `config.py` to customize:

- Business categories and keywords
- Zip code ranges and cities
- Request delays and timeouts
- AI model settings
- Output directory
- Log levels

## ❗ Troubleshooting

### "OPENAI_API_KEY is required"
- Ensure you've created a `.env` file from `.env.example`
- Add your actual OpenAI API key to `.env`
- The key should start with `sk-`

### German characters display incorrectly
- Open CSV files with UTF-8-BOM encoding
- Excel files should display correctly by default
- Use LibreOffice if Excel has issues (select UTF-8 encoding on import)

### No leads collected
- Check your internet connection
- Verify API keys are valid
- Review logs in `logs/` directory
- Try with `--verbose` flag for detailed debugging

### Rate limiting errors
- Increase `request_delay` in `config.py`
- Check OpenAI API usage limits
- Wait a few minutes and retry

## 💰 Cost Estimates

### OpenAI API Costs (GPT-4o-mini)

- **Per search**: ~$0.0002-0.0005
- **Per 100 leads**: ~$0.01-0.05
- **Full run** (10 categories × 10 regions): ~$2-5

### Tips to Reduce Costs

1. Test with `--max-cities 1` first
2. Use specific `--category` and `--ziprange` filters
3. Cache results to avoid re-scraping

## 🤝 Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📝 License

MIT License - See LICENSE file for details

## ⚠️ Legal Notice

This tool is for legitimate B2B lead generation only. Please:

- Respect robots.txt and terms of service
- Use reasonable rate limits
- Comply with GDPR and data protection laws
- Only contact businesses for lawful purposes
- Do not use for spam or unsolicited marketing

## 📞 Support

For issues and questions:
- Open an issue on GitHub
- Check logs in `logs/` directory
- Review error messages in console output

## 🎯 Roadmap

Future enhancements:
- [ ] Web UI (Streamlit dashboard)
- [ ] Database storage (SQLite/PostgreSQL)
- [ ] Email validation API integration
- [ ] Lead scoring system
- [ ] Scheduled runs (cron jobs)
- [ ] Additional data sources
- [ ] Multi-language support

---

**Built for HeyKiki** - AI Voice Assistants for German Tradesmen

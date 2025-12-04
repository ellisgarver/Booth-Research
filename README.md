# SEC 10-K and 10-Q Filings Downloader

A Python script to download and parse SEC 10-K and 10-Q filings from EDGAR for multiple companies.

## Features

- Download 10-K and 10-Q filings from SEC EDGAR
- Automatic CIK lookup from company tickers
- Filter by year and quarter
- Batch processing for multiple tickers
- Saves filings as clean, parsable text files
- Rate-limited requests to comply with SEC guidelines
- Output directly to OneDrive or any local folder

## Installation

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Required Packages

- `requests` - For HTTP requests to SEC EDGAR
- `beautifulsoup4` - For parsing HTML documents

## Usage

### Basic Usage (Command Line)

Edit the configuration variables at the bottom of `sec_filings_downloader.py`:

```python
TICKERS = ["AAPL", "MSFT", "GOOGL"]  # Add your company tickers
OUTPUT_FOLDER = "/Users/username/OneDrive/Documents/SEC_Filings"  # Your OneDrive path
FILING_TYPES = ["10-K", "10-Q"]  # Types to download
YEARS = [2024, 2023]  # Years to download
```

Then run:

```bash
python sec_filings_downloader.py
```

### Python Script Usage

```python
from sec_filings_downloader import download_sec_filings

# Download filings for multiple companies
results = download_sec_filings(
    tickers=["AAPL", "MSFT", "TSLA"],
    output_folder="/Users/username/OneDrive/Documents/SEC_Filings",
    filing_types=["10-K", "10-Q"],
    years=[2024, 2023]
)

print(results)
```

### Advanced Usage with SECFilingDownloader Class

```python
from sec_filings_downloader import SECFilingDownloader

# Create downloader instance
downloader = SECFilingDownloader(output_folder="/path/to/folder")

# Download specific 10-K
downloader.download_filing("AAPL", "10-K", year=2024)

# Download specific Q1 10-Q
downloader.download_filing("MSFT", "10-Q", year=2024, quarter=1)

# Batch download
results = downloader.download_batch(
    tickers=["AAPL", "MSFT", "GOOGL"],
    filing_types=["10-K", "10-Q"],
    years=[2023, 2024]
)
```

## Output File Format

Files are saved with the following naming convention:

- **10-K filings**: `10K-{TICKER}-{YEAR}.txt`
  - Example: `10K-AAPL-2024.txt`

- **10-Q filings**: `10Q-{TICKER}-Q{QUARTER}{YEAR}.txt`
  - Example: `10Q-MSFT-Q12024.txt` (Q1 2024)

## Function Parameters

### `download_sec_filings()`

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `tickers` | List[str] | Yes | Company ticker symbols (e.g., ["AAPL", "MSFT"]) |
| `output_folder` | str | Yes | Path to save filings (OneDrive path or local) |
| `filing_types` | List[str] | No | Types to download: "10-K", "10-Q", or both (default: ["10-K", "10-Q"]) |
| `years` | List[int] | No | Years to download (e.g., [2023, 2024]). If None, downloads most recent |

### `SECFilingDownloader.download_filing()`

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `ticker` | str | Yes | Company ticker symbol |
| `filing_type` | str | Yes | "10-K" or "10-Q" |
| `year` | int | No | Year of filing. If None, gets most recent |
| `quarter` | int | No | Quarter for 10-Q (1-4). If None with 10-Q, gets most recent |

## Important Notes

1. **Rate Limiting**: The script includes a 1.0-second delay between requests to comply with SEC guidelines. Please don't reduce this.

2. **Data Coverage**: The SEC JSON API provides access to approximately the 1000 most recent filings for each company, which typically covers 15-30+ years of history depending on the company's filing frequency.

3. **Text Extraction**: The script now filters out XBRL metadata and namespace references to produce clean, readable output files containing the actual financial statements and text sections.

4. **OneDrive Path**: On macOS, your OneDrive path is typically:
   ```
   /Users/{username}/Library/CloudStorage/OneDrive-<YourOrganization>/
   ```
   Or check by running: `ls ~/Library/CloudStorage/`

5. **CIK Lookup**: The script automatically looks up CIK numbers from ticker symbols using SEC's official database.

6. **Error Handling**: If a filing can't be downloaded, the script will print an error and continue with the next one.

7. **Large Files**: Some 10-K filings can be quite large (200KB-1MB). Be patient while downloading and parsing.

8. **Output File Quality**: Extracted text files are cleaned to remove:
   - XBRL metadata and tags
   - Namespace references (aapl:, us-gaap:, etc.)
   - Standalone metadata values (isolated numbers, dates, codes)
   - Excessive whitespace
   
   This results in much more readable documents focused on the actual financial content.

## Example: Downloading Last 2 Years of 10-Ks

```python
from sec_filings_downloader import download_sec_filings

results = download_sec_filings(
    tickers=["AAPL", "MSFT", "GOOGL", "AMZN"],
    output_folder="/Users/username/OneDrive/Documents/SEC_Filings",
    filing_types=["10-K"],
    years=[2024, 2023]
)

for key, success in results.items():
    print(f"{key}: {'Success' if success else 'Failed'}")
```

## Troubleshooting

### Import Error for `requests` or `beautifulsoup4`
Install the missing package:
```bash
pip install requests beautifulsoup4
```

### Connection Timeout
The SEC servers may be slow. The script includes timeouts and retry logic. If you continue to get timeouts, try running the script again later.

### "Could not find CIK for ticker"
Make sure the ticker symbol is correct. The script performs a lookup, but invalid tickers won't be found.

### Large Files Not Downloading
Some 10-Ks are very large documents. The script has a 15-second timeout for downloading documents. Very large filings may fail; consider downloading them individually from SEC EDGAR website.

## License

This script accesses public data from the SEC EDGAR database. Ensure you comply with SEC's terms of service and robots.txt guidelines.

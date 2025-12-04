import os
import re
import json
import time
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Tuple, Optional
import requests
from urllib.parse import urljoin
from bs4 import BeautifulSoup

SEC_EDGAR_BASE_URL = "https://www.sec.gov"
SEC_EDGAR_CIK_LOOKUP = "https://www.sec.gov/files/company_tickers.json"
SEC_EDGAR_SUBMISSIONS = "https://data.sec.gov/submissions/CIK{cik}.json"

HEADERS = {
    "User-Agent": "Ellis Garver (ehgarver@uchicago.edu) - SEC Filings Downloader for Research Purposes"
}

REQUEST_DELAY = 1.0

class SECFilingDownloader:
    def __init__(self, output_folder_10k: Optional[str] = None, output_folder_10q: Optional[str] = None, output_folder: Optional[str] = None):
        if output_folder_10k is None and output_folder_10q is None and output_folder is None:
            raise ValueError("Must provide either output_folder_10k and output_folder_10q, or output_folder")
        
        if output_folder_10k is None and output_folder_10q is None:
            self.output_folder_10k = Path(output_folder)
            self.output_folder_10q = Path(output_folder)
        else:
            self.output_folder_10k = Path(output_folder_10k) if output_folder_10k else None
            self.output_folder_10q = Path(output_folder_10q) if output_folder_10q else None
        if self.output_folder_10k:
            self.output_folder_10k.mkdir(parents=True, exist_ok=True)
        if self.output_folder_10q:
            self.output_folder_10q.mkdir(parents=True, exist_ok=True)
        
        self.cik_lookup = {}
        self._load_cik_lookup()
    
    def _load_cik_lookup(self) -> None:
        try:
            print("Loading SEC CIK lookup table...")
            response = requests.get(SEC_EDGAR_CIK_LOOKUP, headers=HEADERS, timeout=10)
            response.raise_for_status()
            data = response.json()
            for entry in data.values():
                ticker = entry['ticker'].upper()
                cik = str(entry['cik_str']).zfill(10)
                self.cik_lookup[ticker] = cik
            print(f"Loaded {len(self.cik_lookup)} company tickers")
        except Exception as e:
            print(f"Warning: Could not load CIK lookup: {e}")
            self.cik_lookup = {}
    
    def _get_cik(self, ticker: str) -> Optional[str]:
        ticker_upper = ticker.upper()
        
        if ticker_upper in self.cik_lookup:
            return self.cik_lookup[ticker_upper]
        
        try:
            search_url = f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&company={ticker}&type=&dateb=&owner=exclude&count=100&search_text=&CIK=&myHID="
            response = requests.get(search_url, headers=HEADERS, timeout=10)
            response.raise_for_status()
            
            match = re.search(r'CIK=(\d+)', response.text)
            if match:
                cik = str(int(match.group(1))).zfill(10)
                self.cik_lookup[ticker_upper] = cik
                return cik
        except Exception as e:
            print(f"Error looking up CIK for {ticker}: {e}")
        
        return None
    
    def _get_filings_metadata(self, cik: str, filing_type: str) -> List[Dict]:
        try:
            url = SEC_EDGAR_SUBMISSIONS.format(cik=cik)
            response = requests.get(url, headers=HEADERS, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            filings = []
            
            filings_data = data.get('filings', {}).get('recent', {})
            
            if isinstance(filings_data, dict) and 'form' in filings_data:
                forms = filings_data.get('form', [])
                accession_numbers = filings_data.get('accessionNumber', [])
                filing_dates = filings_data.get('filingDate', [])
                report_dates = filings_data.get('reportDate', [])
                
                for i, form in enumerate(forms):
                    if form == filing_type:
                        if i < len(accession_numbers) and i < len(filing_dates) and i < len(report_dates):
                            filings.append({
                                'accession_number': accession_numbers[i],
                                'filing_date': filing_dates[i],
                                'report_date': report_dates[i],
                                'form_type': form
                            })
            
            return filings
        except Exception as e:
            print(f"Error getting filings metadata for CIK {cik}: {e}")
            return []
    
    def _fetch_filing_from_edgar(self, cik: str, accession_number: str, filing_type: str = "10-K") -> Optional[str]:
        try:
            time.sleep(REQUEST_DELAY)
            
            cik_num = cik.lstrip('0') or '0'
            accession_clean = accession_number.replace('-', '')
            
            dir_url = f"https://www.sec.gov/Archives/edgar/data/{cik_num}/{accession_clean}/"
            
            response = requests.get(dir_url, headers=HEADERS, timeout=10)
            if response.status_code != 200:
                return None
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            main_doc = None
            all_htm_files = []
            
            for link in soup.find_all('a'):
                href = link.get('href', '')
                
                if href and '/Archives/edgar' in href and '.htm' in href.lower():
                    filename = href.split('/')[-1].lower()
                    
                    if 'index' not in filename and '/search' not in href:
                        all_htm_files.append((filename, href))
                        
                        if 'exhibit' not in filename and not (filename.startswith('r') and len(filename) < 10):
                            if not main_doc:
                                main_doc = href
            
            if not main_doc and all_htm_files:
                for fname, fpath in all_htm_files:
                    if fname == 'r1.htm':
                        main_doc = fpath
                        break
                if not main_doc:
                    main_doc = all_htm_files[0][1]
            
            if not main_doc:
                return None
            
            if main_doc.startswith('/'):
                main_doc_url = f"https://www.sec.gov{main_doc}"
            else:
                main_doc_url = main_doc
            
            doc_response = requests.get(main_doc_url, headers=HEADERS, timeout=15)
            if doc_response.status_code != 200:
                return None
            
            doc_soup = BeautifulSoup(doc_response.text, 'html.parser')
            
            tags_to_remove = ['script', 'style', 'meta', 'link', 'button', 'noscript', 'head']
            for tag_name in tags_to_remove:
                for element in doc_soup.find_all(tag_name):
                    element.decompose()
            
            for tag in list(doc_soup.find_all(True)):
                if tag.name and (tag.name.startswith('ix:') or tag.name.startswith('aapl:') or tag.name.startswith('us-gaap:') or ':' in tag.name):
                    tag.unwrap()
            
            text = doc_soup.get_text(separator='\n')
            
            lines = []
            found_start = False
            
            for line in text.split('\n'):
                line = line.rstrip()
                
                if not line or len(line.strip()) == 0:
                    continue
                
                if not found_start:
                    if 'UNITED STATES' in line:
                        found_start = True
                    else:
                        continue
                
                if 'http' in line and ('fasb.org' in line or 'sec.gov/Archives/edgar/xmlbrl' in line):
                    continue
                
                if len(line.strip()) < 100 and ':' in line and ' ' not in line:
                    if any(line.startswith(prefix) for prefix in ['aapl:', 'us-gaap:', 'xbrli:', 'iso4217:', 'usfr:', 'exch:', 'dei:']):
                        continue
                
                lines.append(line)
            
            cleaned = '\n'.join(lines)
            
            while '\n\n\n' in cleaned:
                cleaned = cleaned.replace('\n\n\n', '\n\n')
            
            if len(cleaned) > 5000:
                return cleaned
            
            return None
            
        except Exception as e:
            print(f"  Error fetching filing: {str(e)[:80]}")
            return None
    
    def download_filing(
        self,
        ticker: str,
        filing_type: str,
        year: Optional[int] = None,
        quarter: Optional[int] = None,
        download_all: bool = False
    ) -> bool:
        if filing_type not in ("10-K", "10-Q"):
            print(f"Error: filing_type must be '10-K' or '10-Q', got '{filing_type}'")
            return False
        
        if filing_type == "10-Q" and quarter is not None:
            if quarter not in (1, 2, 3, 4):
                print(f"Error: quarter must be 1-4, got {quarter}")
                return False
        
        cik = self._get_cik(ticker)
        if not cik:
            print(f"Error: Could not find CIK for ticker {ticker}")
            return False
        
        print(f"\nProcessing {filing_type} for {ticker} (CIK: {cik})")
        
        filings = self._get_filings_metadata(cik, filing_type)
        if not filings:
            print(f"No {filing_type} filings found for {ticker}")
            return False
        
        LAST_N_YEARS = 10
        current_year = datetime.now(datetime.timezone.utc).year

        if download_all:
            matching_filings = filings
            print(f"Found {len(matching_filings)} {filing_type} filings")
        else:
            matching_filings = []

            if year is not None:
                years_to_include = {year}
            else:
                years_to_include = set(range(current_year - (LAST_N_YEARS - 1), current_year + 1))

            for filing in filings:
                try:
                    filing_year = int(filing['filing_date'][:4])
                except Exception:
                    continue

                if filing_year not in years_to_include:
                    continue

                if filing_type == "10-K":
                    matching_filings.append(filing)
                else:
                    if quarter is None:
                        matching_filings.append(filing)
                    else:
                        try:
                            report_month = int(filing['report_date'][5:7])
                        except Exception:
                            continue
                        filing_quarter = (report_month - 1) // 3 + 1
                        if filing_quarter == quarter:
                            matching_filings.append(filing)
        
        if not matching_filings:
            print(f"No matching {filing_type} filing found")
            return False
        
        all_successful = True
        for matching_filing in matching_filings:
            print(f"Found filing dated {matching_filing['filing_date']}")
            print("Downloading and scraping document...")
            
            filing_text = self._fetch_filing_from_edgar(cik, matching_filing['accession_number'], filing_type)
            
            if not filing_text:
                print(f"Failed to download filing document for {matching_filing['filing_date']}")
                all_successful = False
                continue
            
            if filing_type == "10-K":
                year_str = matching_filing['filing_date'][:4]
                filename = f"10K-{ticker.upper()}-{year_str}.txt"
                output_folder = self.output_folder_10k
            else:
                report_month = int(matching_filing['report_date'][5:7])
                quarter_num = (report_month - 1) // 3 + 1
                year_str = matching_filing['filing_date'][:4]
                filename = f"10Q-{ticker.upper()}-Q{quarter_num}{year_str}.txt"
                output_folder = self.output_folder_10q
            
            try:
                ticker_dir = output_folder / ticker.upper()
                original_dir = ticker_dir / 'original'
                original_dir.mkdir(parents=True, exist_ok=True)

                output_path = original_dir / filename
                with open(output_path, 'w', encoding='utf-8') as f:
                    f.write(filing_text)
                print(f"Successfully saved to: {output_path}")
            except Exception as e:
                print(f"Error saving file: {e}")
                all_successful = False
        
        return all_successful
    
    def download_batch(
        self,
        tickers: List[str],
        filing_types: List[str] = ["10-K", "10-Q"],
        years: Optional[List[int]] = None,
        download_all: bool = False
    ) -> Dict[str, bool]:
        results = {}
        
        for ticker in tickers:
            for filing_type in filing_types:
                if download_all:
                    key = f"{ticker}-{filing_type}-all"
                    results[key] = self.download_filing(ticker, filing_type, download_all=True)
                elif years:
                    for year in years:
                        key = f"{ticker}-{filing_type}-{year}"
                        results[key] = self.download_filing(ticker, filing_type, year=year)
                else:
                    key = f"{ticker}-{filing_type}"
                    results[key] = self.download_filing(ticker, filing_type)
        
        return results

def download_sec_filings(
    tickers: List[str],
    output_folder_10k: Optional[str] = None,
    output_folder_10q: Optional[str] = None,
    output_folder: Optional[str] = None,
    filing_types: List[str] = ["10-K", "10-Q"],
    years: Optional[List[int]] = None,
    download_all: bool = False
) -> Dict[str, bool]:
    downloader = SECFilingDownloader(
        output_folder_10k=output_folder_10k,
        output_folder_10q=output_folder_10q,
        output_folder=output_folder
    )
    return downloader.download_batch(tickers, filing_types, years, download_all=download_all)

if __name__ == "__main__":
    TICKERS = ["AAPL"]
    OUTPUT_FOLDER_10K = "/Users/ellisgarver/Library/CloudStorage/OneDrive-TheUniversityofChicago/Claire Tseng's files - Earnings Data/10K"
    OUTPUT_FOLDER_10Q = "/Users/ellisgarver/Library/CloudStorage/OneDrive-TheUniversityofChicago/Claire Tseng's files - Earnings Data/10Q"
    FILING_TYPES = ["10-K", "10-Q"]
    DOWNLOAD_ALL = True
    YEARS = [2024]
    
    print("=" * 60)
    print("SEC 10-K and 10-Q Filings Downloader")
    print("=" * 60)
    
    results = download_sec_filings(
        tickers=TICKERS,
        output_folder_10k=OUTPUT_FOLDER_10K,
        output_folder_10q=OUTPUT_FOLDER_10Q,
        filing_types=FILING_TYPES,
        years=YEARS,
        download_all=DOWNLOAD_ALL
    )
    
    print("\n" + "=" * 60)
    print("Download Summary:")
    print("=" * 60)
    for key, success in results.items():
        status = "✓ Success" if success else "✗ Failed"
        print(f"{key}: {status}")
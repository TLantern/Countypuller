"""
Harris County Texas Clerk Records Scraper

This script scrapes real estate records for Harris County, Texas from the
Harris County Clerk's public search form.

Website: https://www.cclerk.hctx.net/Applications/WebSearch/RP.aspx

Features:
- Searches for recent Harris County records by date range
- Filters by document type (LIS PENDENS, etc.)
- Extracts structured data including case numbers, parties, dates
- Uses direct HTTP requests (no browser automation needed)

Dependencies:
- aiohttp (async HTTP client)
- beautifulsoup4 (HTML parsing)
"""

import asyncio
import aiohttp
from bs4 import BeautifulSoup, Tag
import re
from typing import Dict, List, Optional, Any, cast
import logging
import datetime
import os
from bs4.element import Tag as Bs4Tag

logger = logging.getLogger(__name__)

class HarrisCountySearchError(Exception):
    """Custom exception for Harris County search errors"""
    pass

class HarrisCountyScraper:
    """Harris County Clerk search scraper"""
    
    def __init__(self):
        self.base_url = "https://www.cclerk.hctx.net/Applications/WebSearch/RP.aspx"
        self.session = None
        self.viewstate = None
        self.eventvalidation = None
        
    async def __aenter__(self):
        """Async context manager entry"""
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1'
            }
        )
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.session:
            await self.session.close()
    
    async def _get_hidden_fields(self) -> bool:
        """Get all hidden form fields from a preliminary GET request"""
        if self.session is None:
            raise HarrisCountySearchError("Session is not initialized.")
        try:
            logger.info("Getting hidden form fields from Harris County search page")
            
            timeout = aiohttp.ClientTimeout(total=30)
            
            async with self.session.get(self.base_url, timeout=timeout) as response:
                if response.status != 200:
                    raise HarrisCountySearchError(f"Failed to load search page: {response.status}")
                
                html = await asyncio.wait_for(response.text(), timeout=20.0)
                soup = BeautifulSoup(html, 'html.parser')
                
                self.hidden_fields = {}
                for input_tag in soup.find_all('input', {'type': 'hidden'}):
                    if not isinstance(input_tag, Tag):
                        continue
                    name = input_tag.get('name')
                    value = input_tag.get('value', '')
                    if name:
                        self.hidden_fields[name] = value
                logger.info(f"Extracted {len(self.hidden_fields)} hidden fields")
                
                self.viewstate = self.hidden_fields.get('__VIEWSTATE')
                self.eventvalidation = self.hidden_fields.get('__EVENTVALIDATION')
                
                if not self.viewstate or not self.eventvalidation:
                    logger.warning("Could not extract all required hidden fields")
                    logger.info("Proceeding with available fields...")
                
                logger.info("Successfully extracted hidden form fields")
                return True
                
        except asyncio.TimeoutError:
            logger.error("Timeout while getting hidden fields from Harris County")
            raise HarrisCountySearchError("Timeout getting hidden fields")
        except Exception as e:
            logger.error(f"Error getting hidden fields: {e}")
            raise HarrisCountySearchError(f"Failed to get hidden fields: {e}")
    
    def _build_form_data(self, filters: Dict[str, Any]) -> Dict[str, str]:
        """Build the form data payload for the POST request"""
        form_data = dict(self.hidden_fields) if hasattr(self, 'hidden_fields') else {}
        
        if not form_data:
            logger.warning("No hidden fields available - using minimal form data")
            form_data = {
                '__VIEWSTATE': '',
                '__EVENTVALIDATION': '',
                '__VIEWSTATEGENERATOR': ''
            }
        
        doc_type = filters.get('doc_type', 'L/P')
        if doc_type:
            form_data['ctl00$ContentPlaceHolder1$txtInstrument'] = doc_type
        
        from_date = filters.get('from_date')
        if from_date:
            form_data['ctl00$ContentPlaceHolder1$txtFrom'] = from_date
        
        to_date = filters.get('to_date')
        if to_date:
            form_data['ctl00$ContentPlaceHolder1$txtTo'] = to_date
        
        form_data['ctl00$ContentPlaceHolder1$btnSearch'] = 'Search'
        
        logger.info(f"Built form data with {len(form_data)} fields")
        return form_data
    
    def _parse_results(self, html: str) -> List[Dict[str, str]]:
        """Parse the HTML results and extract record data"""
        soup = BeautifulSoup(html, 'html.parser')
        records = []

        results_table = soup.find('table', class_='table-condensed table-hover table-striped')
        if not results_table:
            logger.warning("No results table found in response")
            return records

        results_table = cast(Tag, results_table)

        logger.info("Results table found - beginning parse")

        rows_iter = (r for r in results_table.children if isinstance(r, Tag) and r.name == 'tr')
        rows_list: List[Tag] = list(rows_iter)

        logger.info(f"Total <tr> rows (including header): {len(rows_list)}")

        if len(rows_list) <= 1:
            logger.warning("Results table contained only header row – no data rows to parse")
            return records

        for row in rows_list[1:]:
            cells = [c for c in row.children if isinstance(c, Tag) and c.name == 'td']
            if len(cells) < 7:
                continue

            instrument_number = self._clean_text(cells[1].get_text())
            filing_date = self._clean_text(cells[2].get_text())
            doc_type = self._clean_text(cells[3].get_text())

            names_cell = cast(Bs4Tag, cells[4])
            grantors: List[str] = []
            grantees: List[str] = []
            for name_row in names_cell.find_all('tr'):
                name_row = cast(Bs4Tag, name_row)
                header_b_opt = name_row.find('b')
                if not isinstance(header_b_opt, Bs4Tag):
                    continue
                header_b = header_b_opt
                label = header_b.get_text(strip=True).rstrip(':').lower()
                value_td = cast(Optional[Bs4Tag], header_b.parent.find_next_sibling('td') if header_b.parent else None)
                if not value_td:
                    continue
                value_text = value_td.get_text(separator=' ', strip=True)
                if label == 'grantor':
                    grantors.append(value_text)
                elif label == 'grantee':
                    grantees.append(value_text)

            legal_cell = cast(Bs4Tag, cells[5])
            legal_description_text = legal_cell.get_text(separator=' ', strip=True)
            legal_info = self._parse_legal_description(legal_description_text)

            record = {
                'caseNumber': instrument_number,
                'filingDate': filing_date,
                'docType': doc_type,
                'subdivision': legal_info.get('subdivision', ''),
                'block': legal_info.get('block', ''),
                'lot': legal_info.get('lot', ''),
                'grantor': grantors,
                'grantee': grantees,
                'description': legal_description_text
            }

            logger.debug(f"Parsed record - Instrument#: {record['caseNumber']} Date: {record['filingDate']}")

            records.append(record)

        logger.info(f"Completed parsing results table – total records extracted: {len(records)}")

        return records
    
    def _clean_text(self, text: str) -> str:
        """Clean and normalize text from HTML"""
        if not text:
            return ""
        return re.sub(r'\s+', ' ', text.strip())
    
    def _parse_legal_description(self, description: str) -> Dict[str, str]:
        """Parse legal description to extract subdivision, block, lot"""
        result = {
            'subdivision': '',
            'block': '',
            'lot': ''
        }
        
        if not description:
            return result
        
        label_desc = re.search(r"Desc:\s*([^\n\r]+?)(?:\s+Sec:|\s+Lot:|\s+Block:|$)", description, flags=re.I)
        if label_desc:
            result['subdivision'] = self._clean_text(label_desc.group(1)).upper()

        label_lot = re.search(r"Lot:\s*(\d+)", description, flags=re.I)
        if label_lot:
            result['lot'] = label_lot.group(1)

        label_blk = re.search(r"Block:\s*(\d+)", description, flags=re.I)
        if label_blk:
            result['block'] = label_blk.group(1)

        if result['subdivision'] or result['block'] or result['lot']:
            return result

        patterns = [
            r'([A-Z\s]+?)\s+BLK\s+(\d+)\s+LOT\s+(\d+)',
            r'LOT\s+(\d+)\s+BLK\s+(\d+)\s+([A-Z\s]+)',
            r'BLOCK\s+(\d+)\s+LOT\s+(\d+)\s+OF\s+([A-Z\s]+)',
            r'([A-Z\s]+?)\s+BLOCK\s+(\d+)\s+LOT\s+(\d+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, description.upper())
            if match:
                groups = match.groups()
                if len(groups) == 3:
                    if 'LOT' in pattern and pattern.startswith(r'LOT'):
                        result['lot'] = groups[0]
                        result['block'] = groups[1] 
                        result['subdivision'] = groups[2].strip()
                    elif 'BLOCK' in pattern and 'OF' in pattern:
                        result['block'] = groups[0]
                        result['lot'] = groups[1]
                        result['subdivision'] = groups[2].strip()
                    else:
                        result['subdivision'] = groups[0].strip()
                        result['block'] = groups[1]
                        result['lot'] = groups[2]
                break
        
        return result
    
    async def search(self, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, str]]:
        """Main search method - queries the Harris County search form"""
        if filters is None:
            filters = {}
        if 'doc_type' not in filters:
            filters['doc_type'] = 'L/P'
        today = datetime.date.today()
        if 'from_date' not in filters:
            filters['from_date'] = (today - datetime.timedelta(days=14)).strftime('%m/%d/%Y')
        if 'to_date' not in filters:
            filters['to_date'] = today.strftime('%m/%d/%Y')
        try:
            await asyncio.wait_for(self._get_hidden_fields(), timeout=40.0)
            
            form_data = self._build_form_data(filters)
            
            logger.info(f"Submitting search with filters: {filters}")
            if self.session is None:
                raise HarrisCountySearchError("Session is not initialized.")
            
            timeout = aiohttp.ClientTimeout(total=90)
            
            async with self.session.post(
                self.base_url,
                data=form_data,
                headers={
                    'Content-Type': 'application/x-www-form-urlencoded',
                    'Referer': self.base_url
                },
                timeout=timeout
            ) as response:
                if response.status != 200:
                    raise HarrisCountySearchError(f"Search failed with status: {response.status}")
                
                html = await asyncio.wait_for(response.text(), timeout=30.0)
                
                records = self._parse_results(html)
                if not records:
                    logger.warning("No records found. Check if search parameters are valid.")
                    if os.getenv('DEBUG_HARRIS_SCRAPER'):
                        log_path = os.path.join(os.getcwd(), f"harris_no_results_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.html")
                        with open(log_path, 'w', encoding='utf-8') as f:
                            f.write(html)
                        logger.warning(f"Raw HTML written to file: {log_path}")
                
                logger.info(f"Successfully extracted {len(records)} records")
                return records
                
        except asyncio.TimeoutError:
            logger.error("Harris County search timed out")
            raise HarrisCountySearchError("Search timed out")
        except Exception as e:
            logger.error(f"Search failed: {e}")
            raise HarrisCountySearchError(f"Search failed: {e}")

async def scrape_harris_records(filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, str]]:
    """
    Scrape Harris County records using the public search form
    
    Args:
        filters: Search parameters (doc_type, from_date, to_date, _mock)
            
    Returns:
        List of records with caseNumber, filingDate, docType, subdivision, block, lot, grantor, grantee, description
    """
    if filters is None:
        filters = {'doc_type': 'LIS PENDENS'}
    
    if filters.get('_mock', False):
        return get_mock_harris_records()
    
    async with HarrisCountyScraper() as scraper:
        return await scraper.search(filters)

def get_mock_harris_records() -> List[Dict[str, str]]:
    """Mock Harris County records for testing"""
    return [
        {
            "caseNumber": "202500122891",
            "filingDate": "06/13/2025",
            "docType": "LIS PENDENS",
            "subdivision": "MEMORIAL NORTHWEST",
            "block": "3",
            "lot": "14",
            "grantor": "ADAM EPSTEIN",
            "grantee": "MASSOUMI PAULINE S",
            "description": "LOT 14 BLK 3 MEMORIAL NORTHWEST"
        },
        {
            "caseNumber": "202500122892", 
            "filingDate": "06/13/2025",
            "docType": "LIS PENDENS",
            "subdivision": "VENTANA LAKES",
            "block": "5",
            "lot": "34",
            "grantor": "WELLS FARGO BANK",
            "grantee": "RODRIGUEZ MARIA",
            "description": "VENTANA LAKES BLK 5 LOT 34"
        },
        {
            "caseNumber": "202500122893",
            "filingDate": "06/12/2025", 
            "docType": "LIS PENDENS",
            "subdivision": "SPRING MEADOWS",
            "block": "7",
            "lot": "12",
            "grantor": "JPMORGAN CHASE BANK",
            "grantee": "JOHNSON ROBERT",
            "description": "SPRING MEADOWS BLOCK 7 LOT 12"
        }
    ]

def scrape_harris_records_sync(filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, str]]:
    """Synchronous wrapper for scrape_harris_records"""
    return asyncio.run(scrape_harris_records(filters))

if __name__ == "__main__":
    import json
    
    async def test():
        print("Testing Harris County scraper...")
        
        mock_results = await scrape_harris_records({'_mock': True})
        print(f"Mock results: {json.dumps(mock_results, indent=2)}")
    
    asyncio.run(test())

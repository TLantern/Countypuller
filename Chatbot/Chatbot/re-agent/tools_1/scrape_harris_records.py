"""
Harris County Clerk Records Scraper - Direct API Implementation

This tool queries the Harris County Clerk's public search form directly:
https://www.cclerk.hctx.net/applications/websearch/FRCL_R.aspx

Features:
1. Query the public search form with filters
2. Return clean JS array format
3. Parse HTML results using BeautifulSoup
"""

import asyncio
import aiohttp
from bs4 import BeautifulSoup
import re
from typing import Dict, List, Optional, Any
from urllib.parse import urlencode
import logging
import datetime
import os

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
        """
        Get the hidden form fields (__VIEWSTATE, __EVENTVALIDATION) 
        from a preliminary GET request
        """
        try:
            logger.info("Getting hidden form fields from Harris County search page")
            async with self.session.get(self.base_url) as response:
                if response.status != 200:
                    raise HarrisCountySearchError(f"Failed to load search page: {response.status}")
                
                html = await response.text()
                soup = BeautifulSoup(html, 'html.parser')
                
                # Extract __VIEWSTATE
                viewstate_input = soup.find('input', {'name': '__VIEWSTATE'})
                if viewstate_input:
                    self.viewstate = viewstate_input.get('value')
                
                # Extract __EVENTVALIDATION
                eventvalidation_input = soup.find('input', {'name': '__EVENTVALIDATION'})
                if eventvalidation_input:
                    self.eventvalidation = eventvalidation_input.get('value')
                
                if not self.viewstate or not self.eventvalidation:
                    logger.warning("Could not extract all hidden fields")
                    return False
                    
                logger.info("Successfully extracted hidden form fields")
                return True
                
        except Exception as e:
            logger.error(f"Error getting hidden fields: {e}")
            raise HarrisCountySearchError(f"Failed to get hidden fields: {e}")
    
    def _build_form_data(self, filters: Dict[str, Any]) -> Dict[str, str]:
        """
        Build the form data payload for the POST request
        """
        # Base form data with hidden fields
        form_data = {
            '__VIEWSTATE': self.viewstate or '',
            '__EVENTVALIDATION': self.eventvalidation or '',
            '__EVENTTARGET': '',
            '__EVENTARGUMENT': ''
        }
        # Instrument Type (doc_type) - default to 'L/P'
        doc_type = filters.get('doc_type', 'L/P')
        if doc_type:
            form_data['ctl00$ContentPlaceHolder1$txtInstrument'] = doc_type
        # Date range fields (use MM/DD/YYYY)
        from_date = filters.get('from_date')
        if from_date:
            form_data['ctl00$ContentPlaceHolder1$txtFrom'] = from_date
        to_date = filters.get('to_date')
        if to_date:
            form_data['ctl00$ContentPlaceHolder1$txtTo'] = to_date
        # Search button
        form_data['ctl00$ContentPlaceHolder1$btnSearch'] = 'Search'
        # Other filters (if needed in future)
        # case_number = filters.get('case_number')
        # if case_number:
        #     form_data['ctl00$ContentPlaceHolder1$txtCaseNumber'] = case_number
        # plaintiff = filters.get('plaintiff')
        # if plaintiff:
        #     form_data['ctl00$ContentPlaceHolder1$txtPlaintiff'] = plaintiff
        # defendant = filters.get('defendant')
        # if defendant:
        #     form_data['ctl00$ContentPlaceHolder1$txtDefendant'] = defendant
        return form_data
    
    def _parse_results(self, html: str) -> List[Dict[str, str]]:
        """
        Parse the HTML results and extract record data
        """
        soup = BeautifulSoup(html, 'html.parser')
        records = []
        
        try:
            # Find the results table
            results_table = soup.find('table', {'id': 'ctl00_ContentPlaceHolder1_gvResults'})
            if not results_table:
                logger.warning("No results table found in response")
                return records
            
            # Get all data rows (skip header)
            rows = results_table.find_all('tr')[1:]  # Skip header row
            
            for row in rows:
                cells = row.find_all('td')
                if len(cells) < 6:  # Ensure we have enough columns
                    continue
                
                # Extract data from cells
                record = {
                    'caseNumber': self._clean_text(cells[0].get_text()),
                    'filingDate': self._clean_text(cells[1].get_text()),
                    'docType': self._clean_text(cells[2].get_text()),
                    'plaintiff': self._clean_text(cells[3].get_text()),
                    'respondent': self._clean_text(cells[4].get_text()),
                    'description': self._clean_text(cells[5].get_text()) if len(cells) > 5 else ''
                }
                
                # Extract subdivision, block, lot from description
                legal_info = self._parse_legal_description(record['description'])
                record.update(legal_info)
                
                records.append(record)
                
        except Exception as e:
            logger.error(f"Error parsing results: {e}")
            raise HarrisCountySearchError(f"Failed to parse results: {e}")
        
        return records
    
    def _clean_text(self, text: str) -> str:
        """Clean and normalize text from HTML"""
        if not text:
            return ""
        return re.sub(r'\s+', ' ', text.strip())
    
    def _parse_legal_description(self, description: str) -> Dict[str, str]:
        """
        Parse legal description to extract subdivision, block, lot
        """
        result = {
            'subdivision': '',
            'block': '',
            'lot': ''
        }
        
        if not description:
            return result
        
        # Common patterns for legal descriptions
        patterns = [
            # Pattern: SUBDIVISION NAME BLK 3 LOT 14
            r'([A-Z\s]+?)\s+BLK\s+(\d+)\s+LOT\s+(\d+)',
            # Pattern: LOT 14 BLK 3 SUBDIVISION NAME
            r'LOT\s+(\d+)\s+BLK\s+(\d+)\s+([A-Z\s]+)',
            # Pattern: BLOCK 3 LOT 14 OF SUBDIVISION NAME
            r'BLOCK\s+(\d+)\s+LOT\s+(\d+)\s+OF\s+([A-Z\s]+)',
            # Pattern: SUBDIVISION NAME BLOCK 3 LOT 14
            r'([A-Z\s]+?)\s+BLOCK\s+(\d+)\s+LOT\s+(\d+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, description.upper())
            if match:
                groups = match.groups()
                if len(groups) == 3:
                    # Different patterns have different group orders
                    if 'LOT' in pattern and pattern.startswith(r'LOT'):
                        # LOT first pattern
                        result['lot'] = groups[0]
                        result['block'] = groups[1] 
                        result['subdivision'] = groups[2].strip()
                    elif 'BLOCK' in pattern and 'OF' in pattern:
                        # BLOCK LOT OF SUBDIVISION pattern
                        result['block'] = groups[0]
                        result['lot'] = groups[1]
                        result['subdivision'] = groups[2].strip()
                    else:
                        # SUBDIVISION BLOCK LOT pattern
                        result['subdivision'] = groups[0].strip()
                        result['block'] = groups[1]
                        result['lot'] = groups[2]
                break
        
        return result
    
    async def search(self, filters: Dict[str, Any] = None) -> List[Dict[str, str]]:
        """
        Main search method - queries the Harris County search form
        """
        if filters is None:
            filters = {}
        # Set default doc_type to 'L/P'
        if 'doc_type' not in filters:
            filters['doc_type'] = 'L/P'
        # Set default date range to last 14 days
        today = datetime.date.today()
        if 'from_date' not in filters:
            filters['from_date'] = (today - datetime.timedelta(days=14)).strftime('%m/%d/%Y')
        if 'to_date' not in filters:
            filters['to_date'] = today.strftime('%m/%d/%Y')
        try:
            # Step 1: Get hidden form fields
            if not await self._get_hidden_fields():
                raise HarrisCountySearchError("Failed to get required form fields")
            # Step 2: Build form data
            form_data = self._build_form_data(filters)
            # Step 3: Submit search
            logger.info(f"Submitting search with filters: {filters}")
            async with self.session.post(
                self.base_url,
                data=form_data,
                headers={
                    'Content-Type': 'application/x-www-form-urlencoded',
                    'Referer': self.base_url
                }
            ) as response:
                if response.status != 200:
                    raise HarrisCountySearchError(f"Search failed with status: {response.status}")
                html = await response.text()
                # Step 4: Parse results
                records = self._parse_results(html)
                if not records:
                    logger.warning("No records found. Logging raw HTML response.")
                    log_path = os.path.join(os.getcwd(), f"harris_no_results_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.html")
                    with open(log_path, 'w', encoding='utf-8') as f:
                        f.write(html)
                    logger.warning(f"Raw HTML written to file: {log_path}")
                logger.info(f"Successfully extracted {len(records)} records")
                return records
        except Exception as e:
            logger.error(f"Search failed: {e}")
            raise HarrisCountySearchError(f"Search failed: {e}")

# Main async function for the tool
async def scrape_harris_records(filters: Dict[str, Any] = None) -> List[Dict[str, str]]:
    """
    Scrape Harris County records using the public search form
    
    Args:
        filters: Search parameters
            
    Returns:
        List of records in clean JS array format:
        [
          {
            caseNumber: "202500122891",
            filingDate: "06/13/2025", 
            docType: "LIS PENDENS",
            subdivision: "MEMORIAL NORTHWEST",
            block: "3",
            lot: "14",
            plaintiff: "ADAM EPSTEIN…",
            respondent: "MASSOUMI PAULINE S"
          }
        ]
    """
    if filters is None:
        filters = {'doc_type': 'LIS PENDENS'}
    
    # Use mock data in test mode
    if filters.get('_mock', False):
        return get_mock_harris_records()
    
    async with HarrisCountyScraper() as scraper:
        return await scraper.search(filters)

def get_mock_harris_records() -> List[Dict[str, str]]:
    """
    Mock Harris County records for testing
    """
    return [
        {
            "caseNumber": "202500122891",
            "filingDate": "06/13/2025",
            "docType": "LIS PENDENS",
            "subdivision": "MEMORIAL NORTHWEST",
            "block": "3",
            "lot": "14",
            "plaintiff": "ADAM EPSTEIN",
            "respondent": "MASSOUMI PAULINE S",
            "description": "LOT 14 BLK 3 MEMORIAL NORTHWEST"
        },
        {
            "caseNumber": "202500122892", 
            "filingDate": "06/13/2025",
            "docType": "LIS PENDENS",
            "subdivision": "VENTANA LAKES",
            "block": "5",
            "lot": "34",
            "plaintiff": "WELLS FARGO BANK",
            "respondent": "RODRIGUEZ MARIA",
            "description": "VENTANA LAKES BLK 5 LOT 34"
        },
        {
            "caseNumber": "202500122893",
            "filingDate": "06/12/2025", 
            "docType": "LIS PENDENS",
            "subdivision": "SPRING MEADOWS",
            "block": "7",
            "lot": "12",
            "plaintiff": "JPMORGAN CHASE BANK",
            "respondent": "JOHNSON ROBERT",
            "description": "SPRING MEADOWS BLOCK 7 LOT 12"
        }
    ]

# Sync wrapper for compatibility
def scrape_harris_records_sync(filters: Dict[str, Any] = None) -> List[Dict[str, str]]:
    """Synchronous wrapper for scrape_harris_records"""
    return asyncio.run(scrape_harris_records(filters))

if __name__ == "__main__":
    # Test the scraper
    import json
    
    async def test():
        print("Testing Harris County scraper...")
        
        # Test with mock data
        mock_results = await scrape_harris_records({'_mock': True})
        print(f"Mock results: {json.dumps(mock_results, indent=2)}")
        
        # Test real search (uncomment to test against real site)
        # real_results = await scrape_harris_records({
        #     'doc_type': 'LIS PENDENS',
        #     'from_date': '06/01/2025',
        #     'to_date': '06/30/2025'
        # })
        # print(f"Real results: {json.dumps(real_results, indent=2)}")
    
    asyncio.run(test()) 
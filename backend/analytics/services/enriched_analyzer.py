"""
Enhanced eBay Auto Parts Market Analyzer
Complete Implementation

This module provides:
1. API-based active listing collection (no scraping)
2. Playwright-based sold listing collection
3. Comprehensive item enrichment
4. Vehicle compatibility matching
5. Part name relevance scoring
6. Category-based analysis and reporting
"""

import asyncio
import re
import statistics
from typing import List, Dict, Optional, Tuple, Any
from collections import defaultdict, Counter
from datetime import datetime, timedelta  # Add datetime
from difflib import SequenceMatcher
from dateutil import parser
import statistics
import math
import requests
from typing import List, Dict, Optional, Tuple, Any
from playwright.async_api import async_playwright
import random
import math
# from celery import shared_task
import logging

logger = logging.getLogger(__name__)


# ============================================================================
# CONFIGURATION
# ============================================================================

class Config:
    """Configuration for maximum data collection"""
    
    # eBay API Settings
    EBAY_BROWSE_API = "https://api.ebay.com/buy/browse/v1"
    
    # API Pagination (Active Listings)
    API_MAX_ITEMS_PER_REQUEST = 240  # eBay API hard limit
    API_MAX_PAGES = 15
    API_MAX_TOTAL_ITEMS = 2000  # 200 * 15
    
    # Scraper Pagination (Sold Listings)
    SCRAPER_ITEMS_PER_PAGE = 240  # Maximum eBay allows
    SCRAPER_MAX_PAGES = 15
    SCRAPER_MAX_TOTAL_ITEMS = 2400  # 240 * 15
    
    MULTI_PART_MAX_PAGES = 30  # For multi-part mode
    
    # Enrichment Settings
    ENRICH_MAX_CONCURRENT = 5
    ENRICH_RATE_LIMIT_DELAY = 0.5
    ENRICH_DESCRIPTION_LENGTH = 500

    # Statistical Outlier Detection
    OUTLIER_METHOD = "iqr"  # Options: "iqr", "zscore", "modified_zscore"
    IQR_MULTIPLIER = 1.5    # Standard is 1.5, can use 2.0 for less aggressive filtering
    ZSCORE_THRESHOLD = 3.0  # Prices beyond 3 standard deviations are outliers
    MIN_PRICE_ABSOLUTE = 5.0  # Safety minimum - no item should be < $5
    
    # Filtering Thresholds
    VEHICLE_MATCH_THRESHOLD = 80
    TITLE_RELEVANCE_THRESHOLD = 80
    
    # Search Settings
    MAX_QUERIES = 4

    MIN_ITEMS_PER_CATEGORY = 3

    # Scraper Settings
    SCRAPER_HEADLESS = True
    SCRAPER_TIMEOUT = 30000
    SCRAPER_PAGE_DELAY = (2, 5)

    MIN_ITEMS_PER_CATEGORY = 3

# ============================================================================
# VEHICLE COMPATIBILITY MATCHER
# ============================================================================

class VehicleCompatibilityMatcher:
    """
    Smart vehicle matching with multiple strategies:
    1. Compatible vehicles list (from item aspects)
    2. Title analysis
    """
    
    def __init__(self, year: int, make: str, model: str):
        self.year = year
        self.make = make.lower()
        self.model = model.lower()
        self.vehicle_string = f"{year} {make} {model}".lower()
    
    def score_item(self, item: Dict) -> Dict:
        """
        Score an item's compatibility with target vehicle
        
        Returns dict with:
        - vehicle_match_score: 0-100
        - vehicle_match_method: 'aspects'|'title'|'none'
        - vehicle_match_details: additional info
        """
        
        # Strategy 1: Check compatible_vehicles field from aspects
        compatible_vehicles = item.get('compatible_vehicles', [])
        if compatible_vehicles:
            score = self._match_against_compatible_list(compatible_vehicles)
            if score >= 80:
                return {
                    'vehicle_match_score': score,
                    'vehicle_match_method': 'aspects',
                    'vehicle_match_details': {
                        'matched_vehicles': compatible_vehicles[:5]  # Sample
                    }
                }
        
        # Strategy 2: Analyze title
        title = item.get('title', '').lower()
        title_score = self._analyze_title(title)
        
        return {
            'vehicle_match_score': title_score,
            'vehicle_match_method': 'title' if title_score > 0 else 'none',
            'vehicle_match_details': {
                'title_contains_year': str(self.year) in title,
                'title_contains_make': self.make in title,
                'title_contains_model': self.model in title
            }
        }
    
    def _match_against_compatible_list(self, compatible_vehicles: List[str]) -> int:
        """
        Fuzzy match against compatible vehicles list
        Returns score 0-100
        """
        best_score = 0
        
        for vehicle in compatible_vehicles:
            vehicle_lower = vehicle.lower()
            
            # Exact match
            if self.vehicle_string in vehicle_lower:
                return 100
            
            # Check components
            year_match = str(self.year) in vehicle_lower
            make_match = self.make in vehicle_lower
            model_match = self.model in vehicle_lower
            
            if year_match and make_match and model_match:
                return 95
            elif make_match and model_match:
                return 85
            elif make_match:
                # Fuzzy similarity
                similarity = SequenceMatcher(
                    None, 
                    self.vehicle_string, 
                    vehicle_lower
                ).ratio() * 100
                best_score = max(best_score, similarity)
        
        return int(best_score)
    
    def _analyze_title(self, title: str) -> int:
        """
        Analyze title for vehicle compatibility
        Returns score 0-100
        """
        score = 0
        
        # Year match: +30 points
        if str(self.year) in title:
            score += 30
        
        # Make match: +40 points
        if self.make in title:
            score += 40
        
        # Model match: +30 points
        if self.model in title:
            score += 30
        
        return min(score, 100)


# ============================================================================
# PART NAME RELEVANCE SCORER
# ============================================================================

class PartNameRelevanceScorer:
    """
    Score how well a listing matches the target part
    
    Prevents false matches:
    - "front bumper" should not match "bumper bracket"
    - "headlight" should not match "headlight bulb"
    """
    
    def __init__(self, part_name: str):
        self.part_name = part_name.lower()
        self.part_keywords = self._extract_keywords(part_name)
    
    def _extract_keywords(self, part_name: str) -> List[str]:
        """Extract important keywords from part name"""
        stopwords = {'the', 'a', 'an', 'and', 'or', 'for', 'oem', 'new', 'used'}
        words = [
            w.lower() for w in part_name.split() 
            if w.lower() not in stopwords
        ]
        return words
    
    def score_title(self, title: str) -> int:
        """
        Score title relevance (0-100)
        High score = highly relevant
        Low score = not relevant (filter out)
        """
        title_lower = title.lower()
        
        # Count matching keywords
        matches = sum(
            1 for keyword in self.part_keywords 
            if keyword in title_lower
        )
        
        if len(self.part_keywords) == 0:
            return 50  # Neutral
        
        # Calculate percentage
        match_percentage = (matches / len(self.part_keywords)) * 100
        
        # Apply penalty for keywords suggesting different part
        penalty_keywords = self._get_penalty_keywords()
        penalty = sum(
            10 for pk in penalty_keywords 
            if pk in title_lower
        )
        
        final_score = max(0, int(match_percentage - penalty))
        
        return final_score
    
    def _get_penalty_keywords(self) -> List[str]:
        """
        Keywords that indicate a different part type
        """
        base_part = self.part_keywords[0] if self.part_keywords else ""
        
        penalty_map = {
            'bumper': ['bracket', 'mount', 'support', 'clip', 'trim', 'molding'],
            'headlight': ['bulb', 'socket', 'harness', 'switch'],
            'door': ['handle', 'latch', 'seal', 'weatherstrip'],
            'hood': ['latch', 'hinge', 'prop', 'support'],
            'fender': ['liner', 'trim', 'molding', 'bracket'],
            'mirror': ['glass', 'cover', 'cap'],
            'grille': ['emblem', 'badge', 'trim'],
        }
        
        return penalty_map.get(base_part, [])


# ============================================================================
# CATEGORY ANALYZER
# ============================================================================

class CategoryAnalyzer:
    """
    Organize and analyze items by category
    """
    
    def __init__(self, items: List[Dict]):
        self.items = items
        self.category_groups = self._group_by_category()
    
    def _group_by_category(self) -> Dict[str, List[Dict]]:
        """Group items by category"""
        groups = defaultdict(list)
        
        for item in self.items:
            category_id = item.get('category_id', 'unknown')
            category_path = item.get('category_path', 'Unknown Category')
            
            # Extract category name from path (last segment)
            if category_path and '>' in category_path:
                category_name = category_path.split('>')[-1].strip()
            else:
                category_name = category_path or 'Unknown'
            
            groups[category_id].append({
                **item,
                'category_name': category_name
            })
        
        return dict(groups)
    
    def get_top_category(self) -> Tuple[str, str, int]:
        """
        Get the most common category
        Returns: (category_id, category_name, count)
        """
        if not self.category_groups:
            return ('', 'Unknown', 0)
        
        top_category_id = max(
            self.category_groups.keys(), 
            key=lambda k: len(self.category_groups[k])
        )
        
        items = self.category_groups[top_category_id]
        category_name = items[0]['category_name'] if items else 'Unknown'
        count = len(items)
        
        return (top_category_id, category_name, count)
    
    def get_category_stats(self) -> List[Dict]:
        """Get statistics for all categories"""
        stats = []
        
        for category_id, items in self.category_groups.items():
            if not items:
                continue
            
            category_name = items[0].get('category_name', 'Unknown')
            
            active_items = [i for i in items if i.get('status') == 'active']
            sold_items = [i for i in items if i.get('status') == 'sold']
            
            stats.append({
                'category_id': category_id,
                'category_name': category_name,
                'total_items': len(items),
                'active_count': len(active_items),
                "active_items":active_items,
                "sold_items":sold_items,
                'sold_count': len(sold_items),
                'category_path': items[0].get('category_path', '')
            })
        
        # Sort by item count (descending)
        stats.sort(key=lambda x: x['total_items'], reverse=True)
        
        return stats
    
    def filter_by_min_items(self, min_items: int = 3) -> None:
        """Remove categories with fewer than min_items"""
        self.category_groups = {
            cat_id: items 
            for cat_id, items in self.category_groups.items() 
            if len(items) >= min_items
        }


class ActiveListingsCollector:
    """
    Collect active listings using eBay Buy API with pagination
    
    Strategy:
    1. Get total count from first request
    2. Calculate pages needed (max 15)
    3. Paginate using offset parameter
    """
    
    def __init__(self, oauth_token: str):
        self.oauth_token = oauth_token
    
    async def collect_for_queries(
        self, 
        queries: List[str]
    ) -> List[Dict]:
        """Collect active listings for multiple queries"""
        all_listings = []
        
        for query_idx, query in enumerate(queries, 1):
            print(f"\n{'='*80}")
            print(f"API Query {query_idx}/{len(queries)}: '{query}'")
            print(f"{'='*80}")
            
            query_listings = await self._collect_single_query(query)
            all_listings.extend(query_listings)
            
            print(f"✅ Query {query_idx} complete: {len(query_listings)} items")
        
        return all_listings
    
    async def _collect_single_query(self, query: str) -> List[Dict]:
        """
        Collect all items for a single query with pagination
        
        Steps:
        1. First request: Get total count
        2. Calculate pages needed
        3. Fetch remaining pages in parallel
        """
        
        # Step 1: Get first page and total count
        print("   Step 1: Getting total count...")
        
        first_page_data = await self._fetch_page(query, offset=0, limit=200)
        
        if not first_page_data:
            print("   No data returned from API")
            return []
        
        # Extract items from first page
        all_items = first_page_data.get('items', [])
        total_items = first_page_data.get('total_count', 0)
        
        print(f"   Found {total_items:,} total items")
        
        # Step 2: Calculate pages needed
        max_items_to_collect = min(
            total_items, 
            Config.API_MAX_TOTAL_ITEMS
        )
        
        pages_needed = math.ceil(
            max_items_to_collect / Config.API_MAX_ITEMS_PER_REQUEST
        )
        pages_needed = min(pages_needed, Config.API_MAX_PAGES)
        
        print(f"   Will fetch {pages_needed} pages ({max_items_to_collect:,} items)")
        
        # Step 3: Fetch remaining pages (starting from page 2)
        if pages_needed > 1:
            print(f"   Step 2: Fetching remaining {pages_needed - 1} pages...")
            
            # Create tasks for parallel fetching
            tasks = []
            for page_num in range(2, pages_needed + 1):
                offset = (page_num - 1) * Config.API_MAX_ITEMS_PER_REQUEST
                task = self._fetch_page(
                    query, 
                    offset=offset, 
                    limit=Config.API_MAX_ITEMS_PER_REQUEST
                )
                tasks.append(task)
            
            # Fetch all pages in parallel
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Combine results
            for page_num, result in enumerate(results, start=2):
                if isinstance(result, Exception):
                    print(f"   Page {page_num} failed: {result}")
                    continue
                
                if result and 'items' in result:
                    page_items = result['items']
                    all_items.extend(page_items)
                    print(f"   ✓ Page {page_num}: {len(page_items)} items")
        
        print(f"   Total collected: {len(all_items)} items")
        
        return all_items
    
    async def _fetch_page(
        self, 
        query: str, 
        offset: int, 
        limit: int
    ) -> Optional[Dict]:
        """
        Fetch a single page from eBay Buy API
        
        Returns dict with:
        - items: list of item summaries
        - total_count: total items matching query
        """
        
        try:
            url = f"{Config.EBAY_BROWSE_API}/item_summary/search"
            params = {
                'q': query,
                'limit': limit,
                'offset': offset,
                'filter': 'conditions:(USED)',  # Used conditions
                'sort': '-newlyListed'
            }
            headers = {
                'Authorization': f'Bearer {self.oauth_token}',
                'X-EBAY-C-MARKETPLACE-ID': 'EBAY_US'
            }
            
            response = await asyncio.to_thread(
                requests.get,
                url,
                params=params,
                headers=headers,
                timeout=15
            )
            
            if response.status_code == 200:
                data = response.json()
                
                # Parse items
                items = []
                for item in data.get('itemSummaries', []):
                    items.append({
                        'item_id': item['itemId'],
                        'title': item['title'],
                        'price': float(item['price']['value']),
                        'url': item['itemWebUrl'],
                        'image_url': item.get('image', {}).get('imageUrl', ''),
                        'condition': item.get('condition', 'Used'),
                        'source': 'buy_api',
                        'status': 'active'
                    })
                
                return {
                    'items': items,
                    'total_count': data.get('total', 0)
                }
            
            else:
                print(f"   API error: {response.status_code}")
                return None
        
        except Exception as e:
            print(f"   API request failed: {e}")
            return None


# ============================================================================
# SOLD LISTINGS - PLAYWRIGHT WITH 240 ITEMS PER PAGE
# ============================================================================

class SoldListingsCollector:
    """
    Scrape sold listings with maximum items per page (240)
    
    Strategy:
    1. Navigate and apply filters
    2. Set items per page to 240
    3. Get total count
    4. Calculate pages needed (max 15)
    5. Scrape all pages
    """
    
    async def collect_for_queries(
        self, 
        queries: List[str]
    ) -> List[Dict]:
        """Collect sold listings for multiple queries"""
        all_listings = []
        
        for query_idx, query in enumerate(queries, 1):
            print(f"\n{'='*80}")
            print(f"SCRAPE Query {query_idx}/{len(queries)}: '{query}'")
            print(f"{'='*80}")
            
            query_listings = await self._scrape_single_query(query)
            all_listings.extend(query_listings)
            
            print(f"✅ Query {query_idx} complete: {len(query_listings)} items")
        
        return all_listings
    
    async def _scrape_single_query(self, query: str) -> List[Dict]:
        """
        Scrape sold listings for a single query
        
        Steps:
        1. Navigate and search
        2. Apply sold filter
        3. Set 240 items per page
        4. Get total count
        5. Calculate pages needed
        6. Scrape all pages
        """
        
       
        
        listings = []
        
        async with async_playwright() as p:
            browser = None
            try:
                # Launch browser
                print("   Launching browser...")
                browser = await p.chromium.launch(
                    headless=Config.SCRAPER_HEADLESS,
                    args=[
                        '--no-sandbox',
                        '--disable-setuid-sandbox',
                        '--disable-dev-shm-usage',
                        '--disable-blink-features=AutomationControlled'
                    ]
                )
                
                context = await browser.new_context(
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                    viewport={'width': 1920, 'height': 1080}
                )
                
                page = await context.new_page()
                page.set_default_timeout(Config.SCRAPER_TIMEOUT)
                
                # Step 1: Navigate and search
                print("   Step 1: Navigating to eBay...")
                await page.goto("https://www.ebay.com", wait_until="domcontentloaded")
                await page.wait_for_timeout(2000)
                
                print(f"   Step 2: Searching for '{query}'...")
                await page.click("#gh-ac")
                await page.fill("#gh-ac", query)
                await page.click("#gh-search-btn")
                await page.wait_for_load_state("domcontentloaded")
                await page.wait_for_timeout(3000)
                
                # Step 2: Apply sold filter
                print("   Step 3: Applying sold listings filter...")
                try:
                
                    sold_selector = '#x-refine__group__7 li[name="LH_Sold"] a'
                    if await page.locator(sold_selector).count() > 0:
                        await page.click(sold_selector)
                        await page.wait_for_load_state("domcontentloaded")
                        await page.wait_for_timeout(3000)
                    else:
                        print("   Could not find sold filter")
                except Exception as e:
                    print(f"   Could not apply sold filter: {e}")
                
                # Step 3: Set 240 items per page
                print("   Step 4: Setting 240 items per page...")
                await self._set_items_per_page(page, 240)
                
                # Step 4: Get total count
                print("   Step 5: Getting total count...")
                total_items = await self._get_total_count(page)
                print(f"   Found {total_items:,} total items")
                
                # Step 5: Calculate pages needed
                if total_items == 0:
                    print("   No items found")
                    return []
                
                max_items_to_collect = min(
                    total_items, 
                    Config.SCRAPER_MAX_TOTAL_ITEMS
                )
                
                pages_needed = math.ceil(
                    max_items_to_collect / Config.SCRAPER_ITEMS_PER_PAGE
                )
                pages_needed = min(pages_needed, Config.SCRAPER_MAX_PAGES)
                
                print(f"   Will scrape {pages_needed} pages ({max_items_to_collect:,} items)")
                
                # Step 6: Scrape all pages
                print(f"   Step 6: Scraping {pages_needed} pages...")
                for page_num in range(1, pages_needed + 1):
                    print(f"\n   {'─'*60}")
                    print(f"   Page {page_num}/{pages_needed}")
                    
                    try:
                        # Wait for results
                        await page.wait_for_selector("#srp-river-results", timeout=15000)
                        await page.wait_for_timeout(2000)
                        
                        # Extract listings
                        page_listings = await self._extract_listings_from_page(page)
                        
                        if not page_listings:
                            print(f"   No listings found on page {page_num}")
                            break
                        # For single page with small result set, limit to reported count
                        if pages_needed == 1 and total_items < Config.SCRAPER_ITEMS_PER_PAGE:
                            page_listings = page_listings[:total_items]
                    
                        listings.extend(page_listings)
                        print(f"   ✓ Page {page_num}: {len(page_listings)} items | Total: {len(listings)}")
                        
                        # Navigate to next page (if not last page)
                        if page_num < pages_needed:
                            if not await self._go_to_next_page(page):
                                print("   No more pages available")
                                break
                            
                            # Random delay
                            delay = random.uniform(*Config.SCRAPER_PAGE_DELAY)
                            await asyncio.sleep(delay)
                    
                    except Exception as e:
                        print(f"   Error on page {page_num}: {e}")
                        break
                
                print(f"\n   Total scraped: {len(listings)} items")
            
            except Exception as e:
                print(f"   Critical scraping error: {e}")
            finally:
                if browser:
                    await browser.close()
        
        return listings
    
    async def _set_items_per_page(self, page, items: int = 240):
        """
        Set items per page to maximum (240)
        
        eBay dropdown options: 60, 120, 240
        """
        try:
            # Possible dropdown selectors
            dropdown_selectors = [
                '.srp-ipp .fake-menu-button__button',
                '.srp-ipp button',
                'button[aria-controls="srp-ipp-menu-content"]'
            ]
            
            clicked = False
            for selector in dropdown_selectors:
                if await page.locator(selector).count() > 0:
                    await page.click(selector)
                    await page.wait_for_timeout(1000)
                    clicked = True
                    break
            
            if not clicked:
                print("   Could not find items-per-page dropdown")
                return
            
            # Click on 240 option
            option_selectors = [
                'a[href*="_ipg=240"]',
                'li:has-text("240") a',
                '.srp-ipp ul li:last-child a',  # Last option is usually highest
                '#srp-ipp-menu-content li:last-child a'
            ]
            
            for selector in option_selectors:
                if await page.locator(selector).count() > 0:
                    await page.click(selector)
                    await page.wait_for_load_state("domcontentloaded")
                    await page.wait_for_timeout(2000)
                    print(f"   ✓ Set to 240 items per page")
                    return
            
            print("   Could not set 240 items per page")
        
        except Exception as e:
            print(f"   Error setting items per page: {e}")
    
    async def _get_total_count(self, page) -> int:
        """
        Extract total number of items from page
        
        eBay shows count in format: "X,XXX results"
        """
        try:
            # Possible count selectors
            count_selectors = [
                ".srp-controls__count span.BOLD:first-child",
                ".srp-controls__count .BOLD",
                "h1.srp-controls__count span:first-child",
                ".srp-controls__count-heading"
            ]
            
            for selector in count_selectors:
                if await page.locator(selector).count() > 0:
                    count_text = await page.locator(selector).text_content()
                    
                    # Extract numbers
                    numbers = re.findall(r'[\d,]+', count_text)
                    if numbers:
                        # First number is usually the total
                        total = int(re.sub(r'[^\d]', '', numbers[0]))
                        return total
            
            print("   Could not find total count")
            return 0
        
        except Exception as e:
            print(f"   Error getting total count: {e}")
            return 0
    
    async def _extract_listings_from_page(self, page) -> List[Dict]:
        """Extract all listings from current page"""
        try:
            # Find listing items
            li_selectors = [
                "#srp-river-results ul li.s-card",
                "#srp-river-results li.s-card",
                ".s-card"
            ]
            
            listings_locator = None
            for selector in li_selectors:
                locator = page.locator(selector)
                count = await locator.count()
                if count > 0:
                    listings_locator = locator
                    break
            
            if not listings_locator:
                return []
            
            item_count = await listings_locator.count()
            listings = []
            
            # Process each item
            for idx in range(item_count):
                try:
                    item_locator = listings_locator.nth(idx)
                    block = await item_locator.inner_html()
                    
                    # Extract data
                    listing = self._parse_listing_block(block)
                    
                    if listing and listing.get('item_id'):
                        listings.append(listing)
                
                except Exception:
                    continue
            
            return listings
        
        except Exception as e:
            print(f"   Error extracting listings: {e}")
            return []
    
    def _parse_listing_block(self, block: str) -> Optional[Dict]:
        """Parse HTML block for a single listing"""
        try:
            # Extract title
            title_match = re.search(
                r's-card__title.*?<[^>]+>(.*?)</', 
                block, re.S
            )
            title = re.sub(r"<.*?>", "", title_match.group(1)).strip() \
                if title_match else None
            
            # Extract price
            price_match = re.search(
                r's-card__price.*?>(.*?)</span>', 
                block, re.S
            )
            price_text = re.sub(r"<.*?>", "", price_match.group(1)).strip() \
                if price_match else None
            
            price = None
            if price_text:
                price_clean = re.sub(r'[^0-9.]', '', price_text)
                try:
                    price = float(price_clean)
                except:
                    pass
            
            # Extract item ID
            item_id = None
            url_match = re.search(r'href="([^"]*?/itm/[^"]*?)"', block)
            if url_match:
                url = url_match.group(1)
                id_match = re.search(r'/itm/(\d+)', url)
                if id_match:
                    item_id = id_match.group(1)
            
            # Extract image
            image_url = ""
            img_match = re.search(r'<img[^>]*src="([^"]+)"', block)
            if img_match:
                image_url = img_match.group(1)
            
            # Extract sold date
            date_match = re.search(
                r's-card__caption.*?<span.*?>(.*?)</span>', 
                block, re.S
            )
            sold_date = re.sub(r'<.*?>', '', date_match.group(1)).strip() \
                if date_match else None
            
            if not (title and item_id):
                return None
            
            return {
                'item_id': item_id,
                'title': title,
                'price': price or 0.0,
                'url': f"https://www.ebay.com/itm/{item_id}",
                'image_url': image_url,
                'condition': 'Used',
                'sold_date': sold_date,
                'source': 'scraped_sold',
                'status': 'sold'
            }
        
        except Exception as e:
            return None
    
    async def _go_to_next_page(self, page) -> bool:
        """Navigate to next page"""
        try:
            # Scroll to bottom
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await page.wait_for_timeout(1000)
            
            # Find and click next button
            selectors = [
                "a.pagination__next",
                ".pagination__next",
                "a[aria-label='Next page']",
                "nav.pagination a.pagination__next"
            ]
            
            for selector in selectors:
                if await page.locator(selector).count() > 0:
                    await page.click(selector)
                    await page.wait_for_load_state("domcontentloaded")
                    await page.wait_for_timeout(3000)
                    return True
            
            return False
        
        except Exception as e:
            print(f"   Error navigating to next page: {e}")
            return False


# ============================================================================
# ENHANCED EBAY ANALYZER
# ============================================================================

class EnhancedEbayAnalyzer:
    """
    Enhanced analyzer with maximum data collection
    """
    
    def __init__(self,
        part_name: str = None,  # Make optional
        part_number: str = None,
        year: int = None,
        make: str = None,
        model: str = None,
        oauth_token: str = None,
        multi_part: bool = False  ):
        self.part_name = part_name
        self.part_number = part_number
        self.year = year
        self.make = make
        self.model = model
        self.oauth_token = oauth_token
        self.multi_part = multi_part  # ADD THIS

        
        # Initialize collectors
        self.active_collector = ActiveListingsCollector(oauth_token)
        self.sold_collector = SoldListingsCollector()
        
      
        self.vehicle_matcher = VehicleCompatibilityMatcher(year, make, model)
        # self.part_scorer = PartNameRelevanceScorer(part_name)
        # ADD THIS:
        if multi_part:
            self.category_extractor = CategoryExtractor()
            self.part_scorer = None  # Don't need relevance scorer in multi-part
        else:
            self.part_scorer = PartNameRelevanceScorer(part_name)

    
    
    def _build_search_queries(self) -> List[str]:
        """Build search queries - simple for multi-part, detailed for single-part"""
        
        # ADD THIS CHECK:
        if self.multi_part:
            # Multi-part: just search for vehicle + parts
            return [f"{self.year} {self.make} {self.model} parts"]
        
        # Original single-part logic:
        queries = []
        base = f"{self.year} {self.make} {self.model}"
        
        queries.append(f"{base} {self.part_name}")
        # queries.append(f"{self.part_name} {base}")
        
        if self.part_number:
            queries.append(f"{base} {self.part_number}")
            queries.append(f"{self.part_name} {self.part_number}")
        
        return queries[:Config.MAX_QUERIES]
    
    async def collect_data(self) -> Dict:
        """
        Main data collection method
        
        Returns dict with:
        - active_listings: list
        - sold_listings: list
        - collection_stats: dict
        """
        
        print("\n" + "="*80)
        print("STARTING DATA COLLECTION")
        print("="*80)
        
        # Build queries
        queries = self._build_search_queries()
        print(f"\nSearch queries: {queries}\n")
        
        # Collect in parallel
        print("="*80)
        print("COLLECTING ACTIVE LISTINGS (API)")
        print("="*80)
        active_task = self.active_collector.collect_for_queries(queries)
        
        print("\n" + "="*80)
        print("COLLECTING SOLD LISTINGS (SCRAPING)")
        print("="*80)
        sold_task = self.sold_collector.collect_for_queries(queries)
        
        active_listings, sold_listings = await asyncio.gather(
            active_task, sold_task
        )
        
        # Deduplicate
        active_listings = self._deduplicate(active_listings)
        sold_listings = self._deduplicate(sold_listings)
        
        print("\n" + "="*80)
        print("COLLECTION SUMMARY")
        print("="*80)
        print(f"Active listings: {len(active_listings)}")
        print(f"Sold listings: {len(sold_listings)}")
        print(f"Total unique items: {len(active_listings) + len(sold_listings)}")
        print("="*80 + "\n")
        
        return {
            'active_listings': active_listings,
            'sold_listings': sold_listings,
            'collection_stats': {
                'active_count': len(active_listings),
                'sold_count': len(sold_listings),
                'total_count': len(active_listings) + len(sold_listings)
            }
        }
    
    def _deduplicate(self, listings: List[Dict]) -> List[Dict]:
        """Remove duplicates by item_id"""
        seen = set()
        unique = []
        
        for listing in listings:
            item_id = listing.get('item_id')
            if item_id and item_id not in seen:
                seen.add(item_id)
                unique.append(listing)
        
        return unique


    
    # # ========================================================================
    # # ENRICHMENT
    # # ========================================================================
    
    async def _enrich_all_items(self, listings: List[Dict]) -> List[Dict]:
        """Enrich ALL items with full details from eBay Browse API"""
        if not listings:
            return []
        
        
        total_items = len(listings)
        print(f"\n{'='*80}")
        print(f"ENRICHING {total_items} ITEMS")
        print(f"{'='*80}")
        print(f"Concurrency: {Config.ENRICH_MAX_CONCURRENT} items at a time")
        print(f"Rate limit: {Config.ENRICH_RATE_LIMIT_DELAY}s delay per item")
        print(f"Estimated time: {(total_items * Config.ENRICH_RATE_LIMIT_DELAY / Config.ENRICH_MAX_CONCURRENT / 60):.1f} minutes")
        print(f"{'='*80}\n")
       
        semaphore = asyncio.Semaphore(Config.ENRICH_MAX_CONCURRENT)
        completed = 0
        failed = 0
        start_time = datetime.now()

        
        async def enrich_with_limit(listing, idx):
            nonlocal completed, failed
            async with semaphore:
                try:
                    result = await self._get_item_full_details(listing)
                    await asyncio.sleep(Config.ENRICH_RATE_LIMIT_DELAY)
                    completed += 1
                    
                    # Print progress every 50 items
                    if completed % 50 == 0:
                        elapsed = (datetime.now() - start_time).total_seconds()
                        rate = completed / elapsed if elapsed > 0 else 0
                        remaining = total_items - completed
                        eta_seconds = remaining / rate if rate > 0 else 0
                        
                        print(f"   Progress: {completed}/{total_items} ({completed/total_items*100:.1f}%) | "
                            f"Rate: {rate:.1f} items/sec | "
                            f"ETA: {eta_seconds/60:.1f} min | "
                            f"Failed: {failed}")
                    
                    return result
                except Exception as e:
                    failed += 1
                    if failed <= 5:
                        print(f"   ⚠️  Error enriching item {idx+1}: {str(e)[:50]}")
                    return listing
        
        tasks = [enrich_with_limit(item, idx) for idx, item in enumerate(listings)]
        enriched = await asyncio.gather(*tasks, return_exceptions=True)
        
        successful = [r for r in enriched if not isinstance(r, Exception) and r]
        elapsed = (datetime.now() - start_time).total_seconds()
        
        print(f"\n{'='*80}")
        print(f"ENRICHMENT COMPLETE")
        print(f"{'='*80}")
        print(f"✅ Successful: {len(successful)}/{total_items} ({len(successful)/total_items*100:.1f}%)")
        print(f"❌ Failed: {failed}")
        print(f"⏱️  Time taken: {elapsed/60:.1f} minutes")
        print(f"📊 Rate: {total_items/elapsed:.1f} items/second")
        print(f"{'='*80}\n")
        
        return successful
    

    async def _get_item_full_details(self, listing: Dict) -> Optional[Dict]:
        """Fetch full item details from eBay Browse API"""
        item_id = listing.get('item_id')
        if not item_id:
            return listing
        
        try:
            # Format item ID
            if not item_id.startswith('v1|'):
                item_id_formatted = f"v1|{item_id}|0"
            else:
                item_id_formatted = item_id
            
            url = f"{Config.EBAY_BROWSE_API}/item/{item_id_formatted}"
            headers = {
                'Authorization': f'Bearer {self.oauth_token}',
                'X-EBAY-C-MARKETPLACE-ID': 'EBAY_US'
            }
            
            response = await asyncio.to_thread(
                requests.get, url, headers=headers, timeout=10
            )
            
            if response.status_code != 200:
                return listing
            
            item = response.json()
            enriched = listing.copy()
            
            # Core fields
            enriched['title'] = item.get('title', listing.get('title', ''))
            enriched['condition'] = item.get('condition', 'Used')
            enriched['condition_description'] = item.get('conditionDescription', '')
            
            # Category info
            enriched['category_id'] = item.get('categoryId', '')
            enriched['category_path'] = item.get('categoryPath', '')
            enriched['category_id_path'] = item.get('categoryIdPath', '')
            
            # Description
            description = item.get('description', '')
            if description:
                description_clean = re.sub(r'<[^>]+>', '', description).strip()
                enriched['description'] = description_clean[:Config.ENRICH_DESCRIPTION_LENGTH]
            else:
                enriched['description'] = ''
            
            # === SELLER INFORMATION === (NEW)
            seller = item.get('seller', {})
            enriched['seller_username'] = seller.get('username', '')
            enriched['seller_user_id'] = seller.get('userId', '')
            enriched['seller_feedback_score'] = seller.get('feedbackScore', 0)
            enriched['seller_feedback_percentage'] = seller.get('feedbackPercentage', '')
            enriched['seller_account_type'] = seller.get('sellerAccountType', '')
            
            # === IMAGE === (NEW)
            image = item.get('image', {})
            if not enriched.get('image_url'):
                enriched['image_url'] = image.get('imageUrl', '')
            
            # === DATES === (NEW)
            enriched['item_creation_date'] = item.get('itemCreationDate', '')
            enriched['item_end_date'] = item.get('itemEndDate', '')
            
            # Calculate how long item has been listed / was listed
            if enriched['item_creation_date']:
                try:
                    creation_date = parser.parse(enriched['item_creation_date'])
                    
                    if enriched.get('status') == 'sold' and enriched['item_end_date']:
                        end_date = parser.parse(enriched['item_end_date'])
                        days_listed = (end_date - creation_date).days
                        enriched['days_on_market'] = days_listed
                    elif enriched.get('status') == 'active':
                        now = datetime.now(creation_date.tzinfo)
                        days_listed = (now - creation_date).days
                        enriched['days_on_market'] = days_listed
                    else:
                        enriched['days_on_market'] = 0
                except:
                    enriched['days_on_market'] = 0
            else:
                enriched['days_on_market'] = 0
            
            # Item aspects/specifics
            aspects = {}
            compatible_vehicles = []
            
            for aspect in item.get('localizedAspects', []):
                name = aspect.get('name', '')
                value = aspect.get('value', '')
                
                if name and value:
                    aspects[name] = value
                    
                    # Look for compatibility info
                    compatibility_keywords = [
                        'compatible', 'fitment', 'fits', 
                        'interchange', 'vehicle', 'application'
                    ]
                    if any(kw in name.lower() for kw in compatibility_keywords):
                        if isinstance(value, str):
                            compatible_vehicles.extend([
                                v.strip() for v in value.split(',')
                            ])
                        elif isinstance(value, list):
                            compatible_vehicles.extend(value)
            
            enriched['aspects'] = aspects
            enriched['compatible_vehicles'] = list(set(compatible_vehicles))
            
            # Manufacturer info
            enriched['brand'] = item.get('brand', aspects.get('Brand', ''))
            enriched['mpn'] = item.get(
                'mpn', 
                aspects.get('Manufacturer Part Number', '')
            )
            
            enriched['is_enriched'] = True
            
            return enriched
            
        except Exception as e:
            return listing

    # # ========================================================================
    # # FILTERING & SCORING
    # # ========================================================================
    def _apply_intelligent_filtering(self, items: List[Dict]) -> List[Dict]:
        """
        Apply vehicle compatibility and part relevance filtering
        
        Filters:
        - Vehicle match >= 80% (always)
        - Title relevance >= 80% (only in single-part mode)
        """
        filtered_items = []
        
        for item in items:
            # Score vehicle compatibility (always)
            vehicle_scores = self.vehicle_matcher.score_item(item)
            item.update(vehicle_scores)
            
            # Check vehicle compatibility threshold
            if vehicle_scores['vehicle_match_score'] < Config.VEHICLE_MATCH_THRESHOLD:
                item['is_relevant'] = False
                continue
            
            # Score part relevance (only in single-part mode)
            if not self.multi_part:
                title_score = self.part_scorer.score_title(item.get('title', ''))
                item['title_relevance_score'] = title_score
                
                # Apply title relevance filter
                if title_score < Config.TITLE_RELEVANCE_THRESHOLD:
                    item['is_relevant'] = False
                    continue
            else:
                # Multi-part mode: no title relevance check needed
                item['title_relevance_score'] = None
            
            # Item passed all filters
            item['is_relevant'] = True
            filtered_items.append(item)
        
        return filtered_items
    # # ========================================================================
    # # DEDUPLICATION
    # # ========================================================================
    
    # def _deduplicate_listings(self, listings: List[Dict]) -> List[Dict]:
    #     """Remove duplicate listings by item_id"""
    #     seen = set()
    #     unique = []
        
    #     for listing in listings:
    #         item_id = listing.get('item_id')
    #         if item_id and item_id not in seen:
    #             seen.add(item_id)
    #             unique.append(listing)
        
    #     return unique
    
    def clean_price(self, price_value) -> Optional[float]:
        """Convert price to float"""
        if price_value is None:
            return None
        if isinstance(price_value, (int, float)):
            return float(price_value)
        cleaned = re.sub(r'[^\d.]', '', str(price_value))
        try:
            return float(cleaned)
        except (ValueError, TypeError):
            return None

    def parse_sold_date(self, sold_date_str: str) -> Optional[datetime]:
        """Parse sold date string"""
        if not sold_date_str or sold_date_str == "Unknown":
            return None
        try:
            match = re.search(r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d{1,2}),\s+(\d{4})', sold_date_str)
            if match:
                month_str, day, year = match.groups()
                month_map = {'Jan': 1, 'Feb': 2, 'Mar': 3, 'Apr': 4, 'May': 5, 'Jun': 6,
                            'Jul': 7, 'Aug': 8, 'Sep': 9, 'Oct': 10, 'Nov': 11, 'Dec': 12}
                return datetime(int(year), month_map[month_str], int(day))
        except Exception:
            pass
        return None

    def calculate_market_snapshot(self, items: List[Dict]) -> Dict[str, Any]:
        """Calculate current market snapshot"""
        active = [i for i in items if i.get('status') == 'active']
        active_prices = [self.clean_price(i.get('price')) for i in active]
        active_prices = [p for p in active_prices if p is not None and p > 0]
        
        if not active_prices:
            return {"active_listings_count": 0, "competition_level": "unknown",
                    "price_range": {"min": 0, "avg": 0, "max": 0, "median": 0}}
        
        count = len(active)
        competition = "low" if count < 10 else "medium" if count < 30 else "high"
        
        return {
            "active_listings_count": count,
            "competition_level": competition,
            "price_range": {
                "min": float(min(active_prices)),
                "avg": float(statistics.mean(active_prices)),
                "max": float(max(active_prices)),
                "median": float(statistics.median(active_prices))
            }
        }

    def calculate_historical_performance(self, items: List[Dict]) -> Dict[str, Any]:
        """Calculate historical performance"""
        periods = [30, 60, 90, 180, 365]
        now = datetime.now()
        sold = [i for i in items if i.get('status') == 'sold']
        
        sold_with_dates = []
        for item in sold:
            date = self.parse_sold_date(item.get('sold_date', ''))
            if date:
                price = self.clean_price(item.get('price'))
                if price and price > 0:
                    sold_with_dates.append({'date': date, 'price': price})
        
        performance = {}
        for days in periods:
            start_date = now - timedelta(days=days)
            period_sales = [s for s in sold_with_dates if s['date'] >= start_date]
            period_key = f"{days}_days"
            
            if period_sales:
                prices = [s['price'] for s in period_sales]
                performance[period_key] = {
                    "units_sold": len(period_sales),
                    "avg_price": float(statistics.mean(prices)),
                    "total_revenue": float(sum(prices)),
                    "min_price": float(min(prices)),
                    "max_price": float(max(prices))
                }
            else:
                performance[period_key] = {"units_sold": 0, "avg_price": 0, "total_revenue": 0, 
                                        "min_price": 0, "max_price": 0}
        
        active_count = len([i for i in items if i.get('status') == 'active'])
        total_listings = active_count + len(sold)
        performance["sell_through_rate"] = float((len(sold) / total_listings * 100) if total_listings > 0 else 0)
        
        return performance
        
        
    def detect_price_outliers_iqr(self, prices: List[float], multiplier: float = 1.5) -> Tuple[float, float]:
        """
        Detect outliers using IQR (Interquartile Range) method
        
        This is the most common and robust method for outlier detection.
        
        Returns: (lower_bound, upper_bound)
        """
        if len(prices) < 4:
            # Not enough data for quartiles
            return (min(prices), max(prices))
        
        sorted_prices = sorted(prices)
        n = len(sorted_prices)
        
        # Calculate quartiles
        q1_idx = int(n * 0.25)
        q3_idx = int(n * 0.75)
        
        q1 = sorted_prices[q1_idx]
        q3 = sorted_prices[q3_idx]
        
        # Calculate IQR
        iqr = q3 - q1
        
        # Calculate bounds
        lower_bound = q1 - (multiplier * iqr)
        upper_bound = q3 + (multiplier * iqr)
        
        # Apply absolute minimum safety check
        lower_bound = max(lower_bound, Config.MIN_PRICE_ABSOLUTE)
        
        return (lower_bound, upper_bound)


    def detect_price_outliers_zscore(self, prices: List[float], threshold: float = 3.0) -> Tuple[float, float]:
        """
        Detect outliers using Z-score method
        
        Works well for normally distributed data.
        Standard threshold is 3.0 (3 standard deviations).
        
        Returns: (lower_bound, upper_bound)
        """
        if len(prices) < 3:
            return (min(prices), max(prices))
        
        mean = statistics.mean(prices)
        stdev = statistics.stdev(prices)
        
        if stdev == 0:
            return (mean, mean)
        
        lower_bound = mean - (threshold * stdev)
        upper_bound = mean + (threshold * stdev)
        
        # Apply absolute minimum safety check
        lower_bound = max(lower_bound, Config.MIN_PRICE_ABSOLUTE)
        
        return (lower_bound, upper_bound)


    def detect_price_outliers_modified_zscore(self, prices: List[float], threshold: float = 3.5) -> Tuple[float, float]:
        """
        Detect outliers using Modified Z-score (MAD - Median Absolute Deviation)
        
        More robust than regular Z-score, less affected by extreme outliers.
        
        Returns: (lower_bound, upper_bound)
        """
        if len(prices) < 3:
            return (min(prices), max(prices))
        
        median = statistics.median(prices)
        
        # Calculate MAD (Median Absolute Deviation)
        deviations = [abs(p - median) for p in prices]
        mad = statistics.median(deviations)
        
        if mad == 0:
            return (median, median)
        
        # Modified Z-score: 0.6745 is the scaling factor
        # to make MAD comparable to standard deviation
        lower_bound = median - (threshold * mad / 0.6745)
        upper_bound = median + (threshold * mad / 0.6745)
        
        # Apply absolute minimum safety check
        lower_bound = max(lower_bound, Config.MIN_PRICE_ABSOLUTE)
        
        return (lower_bound, upper_bound)


    def filter_valid_prices(self, items: List[Dict]) -> Tuple[List[Dict], Dict[str, Any]]:
        """
        Filter out items with statistical outlier prices
        
        Returns: (filtered_items, statistics_dict)
        """
        if not items:
            return ([], {})
        
        # Extract all valid prices
        all_prices = []
        for item in items:
            price = self.clean_price(item.get('price'))
            if price and price > 0:
                all_prices.append(price)
        
        if len(all_prices) < 3:
            # Not enough data for statistical analysis
            return (items, {
                'method': 'none',
                'reason': 'insufficient_data',
                'total_items': len(items),
                'prices_analyzed': len(all_prices)
            })
        
        # Detect outliers based on configured method
        method = Config.OUTLIER_METHOD.lower()
        
        if method == "iqr":
            lower_bound, upper_bound = self.detect_price_outliers_iqr(
                all_prices, 
                Config.IQR_MULTIPLIER
            )
        elif method == "zscore":
            lower_bound, upper_bound = self.detect_price_outliers_zscore(
                all_prices,
                Config.ZSCORE_THRESHOLD
            )
        elif method == "modified_zscore":
            lower_bound, upper_bound = self.detect_price_outliers_modified_zscore(
                all_prices,
                3.5
            )
        else:
            # Fallback to IQR
            lower_bound, upper_bound = self.detect_price_outliers_iqr(all_prices, 1.5)
        
        # Filter items
        valid_items = []
        outliers = []
        
        for item in items:
            price = self.clean_price(item.get('price'))
            if price:
                if lower_bound <= price <= upper_bound:
                    valid_items.append(item)
                else:
                    outliers.append({
                        'item_id': item.get('item_id'),
                        'title': item.get('title', '')[:50] + '...',
                        'price': price,
                        'reason': 'too_low' if price < lower_bound else 'too_high'
                    })
            else:
                # Keep items without price (they'll be filtered elsewhere)
                valid_items.append(item)
        
        # Calculate statistics
        stats = {
            'method': method,
            'total_items': len(items),
            'prices_analyzed': len(all_prices),
            'valid_items': len(valid_items),
            'outliers_removed': len(outliers),
            'bounds': {
                'lower': round(lower_bound, 2),
                'upper': round(upper_bound, 2)
            },
            'price_stats': {
                'min': round(min(all_prices), 2),
                'max': round(max(all_prices), 2),
                'mean': round(statistics.mean(all_prices), 2),
                'median': round(statistics.median(all_prices), 2),
                'stdev': round(statistics.stdev(all_prices), 2) if len(all_prices) > 1 else 0
            }
        }
        
        # Add IQR-specific stats if using IQR method
        if method == "iqr" and len(all_prices) >= 4:
            sorted_prices = sorted(all_prices)
            q1_idx = int(len(sorted_prices) * 0.25)
            q3_idx = int(len(sorted_prices) * 0.75)
            q1 = sorted_prices[q1_idx]
            q3 = sorted_prices[q3_idx]
            iqr = q3 - q1
            
            stats['iqr_details'] = {
                'q1': round(q1, 2),
                'q3': round(q3, 2),
                'iqr': round(iqr, 2),
                'lower_fence': round(q1 - (Config.IQR_MULTIPLIER * iqr), 2),
                'upper_fence': round(q3 + (Config.IQR_MULTIPLIER * iqr), 2)
            }
        
        # Print summary
        if outliers:
            print(f"\n   📊 Price Outlier Detection ({method.upper()}):")
            print(f"   Valid range: ${lower_bound:.2f} - ${upper_bound:.2f}")
            print(f"   Filtered {len(outliers)} outliers:")
            
            # Show sample outliers
            for outlier in outliers[:5]:
                reason_emoji = "⬇️" if outlier['reason'] == 'too_low' else "⬆️"
                print(f"   {reason_emoji} ${outlier['price']:.2f} - {outlier['title']}")
            
            if len(outliers) > 5:
                print(f"   ... and {len(outliers) - 5} more outliers")
        
        return (valid_items, stats)


    def calculate_pricing_intelligence(self, items: List[Dict]) -> Dict[str, Any]:
        """Calculate pricing recommendations"""
        # Filter valid prices - now returns tuple
        items, filter_stats = self.filter_valid_prices(items)
        
        sold = [i for i in items if i.get('status') == 'sold']
        sold_prices = [self.clean_price(i.get('price')) for i in sold]
        sold_prices = [p for p in sold_prices if p is not None and p > 0]
        
        if not sold_prices:
            return {
                "optimal_price": 0, 
                "sweet_spot_range": {"min": 0, "max": 0},
                "price_trend": "unknown", 
                "recent_avg": 0, 
                "older_avg": 0,
                "profit_margin_estimate": {
                    "gross_price": 0, "ebay_fee": 0, "payment_fee": 0,
                    "net_profit": 0, "margin_percent": 0
                },
                "price_filter_stats": filter_stats  # ← Add filter stats
            }
        
        sorted_prices = sorted(sold_prices)
        q1_idx, q3_idx = int(len(sorted_prices) * 0.25), int(len(sorted_prices) * 0.75)
        optimal_price = float(statistics.median(sorted_prices))
        
        # Price trend
        cutoff_date = datetime.now() - timedelta(days=90)
        recent_sales, older_sales = [], []
        for item in sold:
            date = self.parse_sold_date(item.get('sold_date', ''))
            price = self.clean_price(item.get('price'))
            if date and price and price > 0:
                (recent_sales if date >= cutoff_date else older_sales).append(price)
        
        trend = "unknown"
        recent_avg = float(statistics.mean(recent_sales)) if recent_sales else 0
        older_avg = float(statistics.mean(older_sales)) if older_sales else 0
        if recent_sales and older_sales and len(recent_sales) >= 3 and len(older_sales) >= 3:
            price_change = ((recent_avg - older_avg) / older_avg) * 100
            trend = "increasing" if price_change > 5 else "decreasing" if price_change < -5 else "stable"
        
        # Profit margin WITHOUT shipping cost
        ebay_fee = optimal_price * 0.1325
        payment_fee = (optimal_price * 0.029) + 0.30
        net_profit = optimal_price - ebay_fee - payment_fee
        
        return {
            "optimal_price": float(optimal_price),
            "sweet_spot_range": {
                "min": float(sorted_prices[q1_idx]) if sorted_prices else 0, 
                "max": float(sorted_prices[q3_idx]) if sorted_prices else 0
            },
            "price_trend": trend, 
            "recent_avg": recent_avg, 
            "older_avg": older_avg,
            "profit_margin_estimate": {
                "gross_price": float(optimal_price), 
                "ebay_fee": float(ebay_fee),
                "payment_fee": float(payment_fee),
                "net_profit": float(net_profit), 
                "margin_percent": float((net_profit / optimal_price * 100) if optimal_price > 0 else 0)
            },
            "price_filter_stats": filter_stats  # ← Add filter stats
        }




    def calculate_demand_signals(self, items: List[Dict]) -> Dict[str, Any]:
        """Calculate demand signals"""
        sold = [i for i in items if i.get('status') == 'sold']
        now, cutoff_30, cutoff_90 = datetime.now(), datetime.now() - timedelta(days=30), datetime.now() - timedelta(days=90)
        
        recent_sales = []
        for item in sold:
            date = self.parse_sold_date(item.get('sold_date', ''))
            if date and date >= cutoff_90:
                recent_sales.append({'date': date, 'in_last_30': date >= cutoff_30})
        
        sales_30_days = len([s for s in recent_sales if s['in_last_30']])
        velocity_30 = sales_30_days / 30.0
        
        if velocity_30 >= 1.0: demand_level = "very_high"
        elif velocity_30 >= 0.5: demand_level = "high"
        elif velocity_30 >= 0.2: demand_level = "moderate"
        elif velocity_30 > 0: demand_level = "low"
        else: demand_level = "very_low"
        
        active_count = len([i for i in items if i.get('status') == 'active'])
        if demand_level in ["high", "very_high"] and active_count < 20: opportunity = "excellent"
        elif demand_level in ["moderate", "high"] and active_count < 30: opportunity = "good"
        elif demand_level == "moderate": opportunity = "fair"
        else: opportunity = "poor"
        
        return {
            "demand_level": demand_level, "opportunity_rating": opportunity,
            "sales_velocity_30d": float(velocity_30), "sales_velocity_90d": float(len(recent_sales) / 90.0),
            "units_sold_30d": sales_30_days, "units_sold_90d": len(recent_sales),
            "days_to_sell_estimate": float(1.0 / velocity_30) if velocity_30 > 0 else 999
        }

    def analyze_competition(self, items: List[Dict]) -> Dict[str, Any]:
        """Analyze competition"""
        active = [i for i in items if i.get('status') == 'active']
        if not active:
            return {"total_active_sellers": 0, "avg_listing_age_days": 0,
                    "price_distribution": {}, "condition_breakdown": {}}
        
        prices = [self.clean_price(i.get('price')) for i in active]
        prices = [p for p in prices if p is not None and p > 0]
        
        price_dist = {}
        if prices:
            for min_p, max_p, label in [(0, 100, "under_100"), (100, 200, "100_200"),
                                        (200, 300, "200_300"), (300, 500, "300_500"),
                                        (500, float('inf'), "over_500")]:
                price_dist[label] = len([p for p in prices if min_p <= p < max_p])
        
        conditions = [i.get('condition', 'Unknown') for i in active]
        return {
            "total_active_sellers": len(active), "avg_listing_age_days": 30,
            "price_distribution": price_dist, "condition_breakdown": dict(Counter(conditions))
        }

    def analyze_sellers(self, items: List[Dict]) -> Dict[str, Any]:
        """Analyze seller information"""
        sellers_data = {}
        
        for item in items:
            username = item.get('seller_username', 'Unknown')
            if not username or username == 'Unknown':
                continue
            
            if username not in sellers_data:
                sellers_data[username] = {
                    'username': username,
                    'user_id': item.get('seller_user_id', ''),
                    'feedback_score': item.get('seller_feedback_score', 0),
                    'feedback_percentage': item.get('seller_feedback_percentage', ''),
                    'account_type': item.get('seller_account_type', ''),
                    'items': []
                }
            
            sellers_data[username]['items'].append({
                'item_id': item.get('item_id'),
                'title': item.get('title', '')[:50] + '...',
                'price': self.clean_price(item.get('price')),
                'status': item.get('status'),
                'days_on_market': item.get('days_on_market', 0)
            })
        
        # Convert to list and sort by item count
        sellers_list = list(sellers_data.values())
        sellers_list.sort(key=lambda x: len(x['items']), reverse=True)
        
        # Add item count to each seller
        for seller in sellers_list:
            seller['total_items'] = len(seller['items'])
            seller['active_items'] = len([i for i in seller['items'] if i['status'] == 'active'])
            seller['sold_items'] = len([i for i in seller['items'] if i['status'] == 'sold'])
        
        return {
            'total_unique_sellers': len(sellers_list),
            'sellers': sellers_list,
            'top_sellers': sellers_list[:10]  # Top 10 sellers by item count
        }


    def format_items_summary(self, items: List[Dict]) -> List[Dict]:
        """Format all items into short summary data"""
        summary = []
        
        for item in items:
            price = self.clean_price(item.get('price'))
            
            # Skip invalid prices
            # if not price or price < Config.MIN_VALID_PRICE or price > Config.MAX_VALID_PRICE:
            #     continue
            
            summary.append({
                'item_id': item.get('item_id'),
                'title': item.get('title', 'No Title'),
                'price': float(price),
                'image_url': item.get('image_url', ''),
                'status': item.get('status', 'unknown'),
                'condition': item.get('condition', 'Unknown'),
                'days_on_market': item.get('days_on_market', 0),
                'seller_username': item.get('seller_username', 'Unknown'),
                'seller_feedback_score': item.get('seller_feedback_score', 0),
                'url': item.get('url', f"https://www.ebay.com/itm/{item.get('item_id', '')}")
            })
        
        # Sort: active first (by days on market), then sold (by days on market)
        summary.sort(key=lambda x: (
            0 if x['status'] == 'active' else 1,
            -x['days_on_market']
        ))
        
        return summary



    def find_related_parts(self, items: List[Dict]) -> List[str]:
        """Find related parts from titles"""
        words = []
        for title in [i.get('title', '') for i in items]:
            words.extend(re.findall(r'\b[A-Z][a-z]+\b', title))
        word_counts = Counter(words)
        return [word for word, count in word_counts.most_common(10) 
                if word.lower() not in ['toyota', 'prius', 'used', 'oem', 'genuine']][:7]

    def _generate_recommendation(self, report: Dict[str, Any]) -> Dict[str, Any]:
        """Generate overall recommendation"""
        demand = report['demand_signals']
        pricing = report['pricing_intelligence']
        competition = report['market_snapshot']
        
        opportunity = demand['opportunity_rating']
        demand_level = demand['demand_level']
        competition_level = competition['competition_level']
        
        if opportunity == "excellent":
            rec, text = "good_to_sell", f"Excellent opportunity! {demand_level.replace('_', ' ').title()} demand with {competition_level} competition."
        elif opportunity == "good":
            rec, text = "good_to_sell", f"Good opportunity to sell. {demand_level.replace('_', ' ').title()} demand detected."
        elif opportunity == "fair":
            rec, text = "moderate_demand", f"Moderate opportunity. Price competitively at around ${pricing['optimal_price']:.2f}."
        elif demand_level in ["low", "very_low"]:
            rec, text = "low_demand", "Low demand detected. Consider if this part is worth listing."
        else:
            rec, text = "saturated", f"Market appears saturated with {competition_level} competition."
        
        data_points = report['data_summary']['total_data_points']
        confidence = "high" if data_points >= 50 else "medium" if data_points >= 20 else "low"
        
        return {"status": rec, "text": text, "suggested_price": float(pricing['optimal_price']), "confidence": confidence}

    # ========================================================================
    # MAIN ANALYSIS PIPELINE
    # ========================================================================
    
    
    async def analyze(self) -> Dict:
        """Complete analysis pipeline with comprehensive report"""
        
        # 1. Build queries
        queries = self._build_search_queries()
        max_pages = Config.MULTI_PART_MAX_PAGES if self.multi_part else Config.API_MAX_PAGES

        print(f"Search queries: {queries}")
        
        # 2. Collect data
        print("Collecting active and sold listings...")
        
        try:
            result = await asyncio.wait_for(
                self.collect_data(),
                timeout=600
            )
            active_listings = result['active_listings']
            sold_listings = result['sold_listings']
            all_listings = active_listings + sold_listings
        except asyncio.TimeoutError:
            print("❌ Data collection timed out")
            return self._generate_no_data_report()
        
        if not all_listings:
            return self._generate_no_data_report()
        
        # 3. Enrich ALL items (both active and sold)
        print(f"\n{'='*80}")
        print(f"ENRICHING ALL LISTINGS (Active + Sold)")
        print(f"{'='*80}")
        print(f"Active listings to enrich: {len(active_listings)}")
        print(f"Sold listings to enrich: {len(sold_listings)}")
        enriched_items = await self._enrich_all_items(all_listings)
        print(f"Successfully enriched: {len(enriched_items)}")

        # 4. Apply intelligent filtering
        print("Applying intelligent filtering...")
        filtered_items = self._apply_intelligent_filtering(enriched_items)
        print(f"Items passing filters: {len(filtered_items)}")
        
        if not filtered_items:
            return self._generate_no_data_report()
        
        # 5. Category-based analysis
        category_analyzer = CategoryAnalyzer(filtered_items)
        category_analyzer.filter_by_min_items(Config.MIN_ITEMS_PER_CATEGORY)
        
        top_category = category_analyzer.get_top_category()
        category_stats = category_analyzer.get_category_stats()
        
        print(f"Top category: {top_category[1]} ({top_category[2]} items)")
        print(f"Total categories: {len(category_stats)}")
        
        # 6. Base report structure
        final_report = {
            "part_name": self.part_name,
            "part_number": self.part_number,
            "vehicle": f"{self.year} {self.make} {self.model}",
            "analysis_timestamp": datetime.now().isoformat(),
            "analysis_type": "multi_part" if self.multi_part else "single_part",
            
            "data_summary": {
                "total_items_found": len(all_listings),
                "items_enriched": len(enriched_items),
                "items_after_filtering": len(filtered_items),
                "active_listings": len([i for i in filtered_items if i['status'] == 'active']),
                "sold_listings": len([i for i in filtered_items if i['status'] == 'sold']),
                # "sold_items":[i for i in filtered_items if i['status'] == 'sold'],
                # "active_items":[i for i in filtered_items if i['status'] == 'active'],
                "total_data_points": len(filtered_items)
            },
            
            "category_analysis": {
                "top_category": {
                    "id": top_category[0],
                    "name": top_category[1],
                    "item_count": top_category[2]
                },
                "all_categories": category_stats,
                "total_categories": len(category_stats)
            },
        }
        
        # 7. MODE-SPECIFIC ANALYSIS
        if self.multi_part:
            # ========== MULTI-PART ANALYSIS ==========
            print("Generating multi-part analysis...")
            
            # Analyze each category in detail
            category_groups = category_analyzer.category_groups
            multi_category_detailed_stats = []
            
            for cat_id, cat_items in category_groups.items():
                if not cat_items:
                    continue
                    
                cat_name = cat_items[0]['category_name'] if cat_items else 'Unknown'
                
                # Separate active and sold
                active = [i for i in cat_items if i['status'] == 'active']
                sold = [i for i in cat_items if i['status'] == 'sold']
                
                # Generate FULL detailed report for this category
                category_report = self._generate_category_report(cat_items, cat_id)
                
                # Extract key metrics for comparison
                prices = [self.clean_price(i.get('price')) for i in cat_items]
                prices = [p for p in prices if p and p > 0]
                
                sold_prices = [self.clean_price(i.get('price')) for i in sold]
                sold_prices = [p for p in sold_prices if p and p > 0]
                
                active_prices = [self.clean_price(i.get('price')) for i in active]
                active_prices = [p for p in active_prices if p and p > 0]
                
                # Calculate velocity and sell-through
                total_listings = len(active) + len(sold)
                sell_through_rate = (len(sold) / total_listings * 100) if total_listings > 0 else 0
                
                # Calculate sales velocity (units per day - using 30 day window)
                recent_sold = [i for i in sold if 'sold_date' in i]
                sales_velocity_30d = len(recent_sold) / 30 if recent_sold else 0
                
                # Build comprehensive category stats
                category_stats = {
                    'category_id': cat_id,
                    'category_name': cat_name,
                    'category_path': cat_items[0].get('category_path', ''),
                    
                    # Item counts
                    'total_items': len(cat_items),
                    'active_count': len(active),
                    'sold_count': len(sold),
                    
                    # Pricing data
                    'price_stats': {
                        'min': float(min(prices)) if prices else 0,
                        'max': float(max(prices)) if prices else 0,
                        'avg': float(statistics.mean(prices)) if prices else 0,
                        'median': float(statistics.median(prices)) if prices else 0,
                    },
                    
                    'sold_price_stats': {
                        'min': float(min(sold_prices)) if sold_prices else 0,
                        'max': float(max(sold_prices)) if sold_prices else 0,
                        'avg': float(statistics.mean(sold_prices)) if sold_prices else 0,
                        'median': float(statistics.median(sold_prices)) if sold_prices else 0,
                    },
                    
                    'active_price_stats': {
                        'min': float(min(active_prices)) if active_prices else 0,
                        'max': float(max(active_prices)) if active_prices else 0,
                        'avg': float(statistics.mean(active_prices)) if active_prices else 0,
                        'median': float(statistics.median(active_prices)) if active_prices else 0,
                    },
                    
                    # Market metrics
                    'sell_through_rate': float(sell_through_rate),
                    'sales_velocity_30d': float(sales_velocity_30d),
                    
                    # Competition level
                    'competition_level': 'low' if len(active) < 10 else 'medium' if len(active) < 30 else 'high',
                    
                    # Demand level based on sales velocity
                    'demand_level': 'very_high' if sales_velocity_30d >= 2 else 'high' if sales_velocity_30d >= 1 else 'medium' if sales_velocity_30d >= 0.5 else 'low',
                    
                    # Include full detailed report
                    'detailed_analysis': category_report,
                    
                    # Sample items (top 5 sold, top 5 active)
                    'sample_sold_items': self.format_items_summary(sorted(sold, key=lambda x: x.get('price', 0), reverse=True)[:5]),
                    'sample_active_items': self.format_items_summary(sorted(active, key=lambda x: x.get('price', 0), reverse=True)[:5])
                }
                
                multi_category_detailed_stats.append(category_stats)
            
            # Sort categories by opportunity score
            def calculate_opportunity_score(cat_stats):
                score = 0
                
                # High sales velocity = good
                velocity = cat_stats['sales_velocity_30d']
                if velocity >= 2.0:
                    score += 50
                elif velocity >= 1.0:
                    score += 35
                elif velocity >= 0.5:
                    score += 20
                
                # Good sell-through rate = good
                str_rate = cat_stats['sell_through_rate']
                if str_rate >= 50:
                    score += 30
                elif str_rate >= 30:
                    score += 20
                elif str_rate >= 15:
                    score += 10
                
                # Higher median sold price = better
                median_sold = cat_stats['sold_price_stats']['median']
                if median_sold >= 100:
                    score += 20
                elif median_sold >= 50:
                    score += 10
                elif median_sold >= 25:
                    score += 5
                
                return score
            
            for cat_stats in multi_category_detailed_stats:
                cat_stats['opportunity_score'] = calculate_opportunity_score(cat_stats)
            
            # Sort by opportunity score
            multi_category_detailed_stats.sort(key=lambda x: x['opportunity_score'], reverse=True)
            
            # Hot parts identification
            hot_parts = [
                {
                    'category_name': cat['category_name'],
                    'opportunity_score': cat['opportunity_score'],
                    'sales_velocity': cat['sales_velocity_30d'],
                    'sell_through_rate': cat['sell_through_rate'],
                    'median_sold_price': cat['sold_price_stats']['median'],
                    'total_sold': cat['sold_count'],
                    'competition_level': cat['competition_level']
                }
                for cat in multi_category_detailed_stats[:5]  # Top 5 opportunities
            ]
            
            # Category comparison table
            comparison_table = []
            for cat in multi_category_detailed_stats:
                comparison_table.append({
                    'category': cat['category_name'],
                    'total_items': cat['total_items'],
                    'active': cat['active_count'],
                    'sold': cat['sold_count'],
                    'sell_through_rate': f"{cat['sell_through_rate']:.1f}%",
                    'avg_sold_price': f"${cat['sold_price_stats']['avg']:.2f}",
                    'median_sold_price': f"${cat['sold_price_stats']['median']:.2f}",
                    'sales_per_day': f"{cat['sales_velocity_30d']:.2f}",
                    'competition': cat['competition_level'],
                    'demand': cat['demand_level'],
                    'opportunity_score': cat['opportunity_score']
                })
            
            # Overall market insights
            total_sold_all_cats = sum(cat['sold_count'] for cat in multi_category_detailed_stats)
            total_active_all_cats = sum(cat['active_count'] for cat in multi_category_detailed_stats)
            
            # Add multi-part specific data to report
            final_report['multi_part_analysis'] = {
                'total_categories_analyzed': len(multi_category_detailed_stats),
                'total_parts_sold_30d': total_sold_all_cats,
                'total_active_listings': total_active_all_cats,
                
                'hot_opportunities': hot_parts,
                'category_comparison': comparison_table,
                'detailed_category_stats': multi_category_detailed_stats,
                
                'market_insights': {
                    'most_active_category': max(multi_category_detailed_stats, key=lambda x: x['active_count'])['category_name'] if multi_category_detailed_stats else 'N/A',
                    'best_selling_category': max(multi_category_detailed_stats, key=lambda x: x['sold_count'])['category_name'] if multi_category_detailed_stats else 'N/A',
                    'highest_value_category': max(multi_category_detailed_stats, key=lambda x: x['sold_price_stats']['median'])['category_name'] if multi_category_detailed_stats else 'N/A',
                    'fastest_selling_category': max(multi_category_detailed_stats, key=lambda x: x['sales_velocity_30d'])['category_name'] if multi_category_detailed_stats else 'N/A',
                },
                
                'recommendations': {
                    'best_opportunity': hot_parts[0] if hot_parts else None,
                    'suggestion': f"Focus on {hot_parts[0]['category_name']} - showing {hot_parts[0]['sales_velocity']:.2f} sales/day with {hot_parts[0]['sell_through_rate']:.1f}% sell-through rate" if hot_parts else "Insufficient data"
                }
            }
            
            print(f"\n{'='*80}")
            print("MULTI-PART ANALYSIS COMPLETE")
            print(f"{'='*80}")
            print(f"Categories analyzed: {len(multi_category_detailed_stats)}")
            print(f"Top opportunity: {hot_parts[0]['category_name'] if hot_parts else 'N/A'}")
            print(f"{'='*80}\n")

        else:
            # ========== SINGLE-PART ANALYSIS (your existing logic) ==========
            
            # Generate reports per category
            category_reports = {}
            for category_id, items in category_analyzer.category_groups.items():
                report = self._generate_category_report(items, category_id)
                category_reports[category_id] = report
            
            # Get top category detailed report
            top_category_report = category_reports.get(top_category[0], {})
            
            # Add single-part results to report
            final_report.update({
                "market_snapshot": top_category_report.get('market_snapshot', {}),
                "historical_performance": top_category_report.get('historical_performance', {}),
                "pricing_intelligence": top_category_report.get('pricing_intelligence', {}),
                "demand_signals": top_category_report.get('demand_signals', {}),
                "competition_analysis": top_category_report.get('competition_analysis', {}),
                "related_parts": top_category_report.get('related_parts', []),
                "recommendation": top_category_report.get('recommendation', {}),
                "seller_analysis": top_category_report.get('seller_analysis', {}),
                "all_items": top_category_report.get('all_items', []),
                "filtering_stats": {
                    "avg_vehicle_match_score": statistics.mean([
                        i['vehicle_match_score'] for i in filtered_items
                    ]) if filtered_items else 0,
                    "avg_title_relevance": statistics.mean([
                        i['title_relevance_score'] for i in filtered_items
                    ]) if filtered_items else 0,
                    "vehicle_match_methods": dict(Counter([
                        i['vehicle_match_method'] for i in filtered_items
                    ]))
                },
                "all_category_reports": category_reports,
                "multi_part_analysis": None
            })
            
            print(f"\n{'='*80}")
            print("ANALYSIS COMPLETE")
            print(f"{'='*80}")
            print(f"Recommendation: {final_report['recommendation'].get('text', 'N/A')}")
            print(f"Suggested Price: ${final_report['recommendation'].get('suggested_price', 0):.2f}")
            print(f"Confidence: {final_report['recommendation'].get('confidence', 'N/A')}")
            print(f"{'='*80}\n")
        
        return final_report   
    
    def _generate_category_report(self, items: List[Dict], category_id: str) -> Dict:
        """Generate detailed report for a specific category"""
        category_name = items[0].get('category_name', 'Unknown') if items else 'Unknown'
        
        # Filter valid prices - now returns tuple
        items, filter_stats = self.filter_valid_prices(items)
        
        active = [i for i in items if i['status'] == 'active']
        sold = [i for i in items if i['status'] == 'sold']
        
        report = {
            "category_name": category_name,
            "category_id": category_id,
            "item_count": len(items),
            "active_count": len(active),
            "sold_count": len(sold),
            "price_filtering": filter_stats,  # ← Add filter stats to report
            "market_snapshot": self.calculate_market_snapshot(items),
            "historical_performance": self.calculate_historical_performance(items),
            "pricing_intelligence": self.calculate_pricing_intelligence(items),
            "demand_signals": self.calculate_demand_signals(items),
            "competition_analysis": self.analyze_competition(items),
            "related_parts": self.find_related_parts(items),
            "seller_analysis": self.analyze_sellers(items),
            "all_items": self.format_items_summary(items),
            "data_summary": {
                "active_listings": len(active),
                "sold_listings": len(sold),
                "total_data_points": len(items)
            }
        }
        
        report["recommendation"] = self._generate_recommendation(report)
        return report



    # ============================================================================
    # 8. UPDATE calculate_market_snapshot to filter prices
    # ============================================================================
    
    def calculate_market_snapshot(self, items: List[Dict]) -> Dict[str, Any]:
        """Calculate current market snapshot"""
        # Filter valid prices - now returns tuple
        items, filter_stats = self.filter_valid_prices(items)
        
        active = [i for i in items if i.get('status') == 'active']
        active_prices = [self.clean_price(i.get('price')) for i in active]
        active_prices = [p for p in active_prices if p is not None and p > 0]
        
        if not active_prices:
            return {
                "active_listings_count": 0, 
                "competition_level": "unknown",
                "price_range": {"min": 0, "avg": 0, "max": 0, "median": 0},
                "price_filter_stats": filter_stats  # ← Add filter stats
            }
        
        count = len(active)
        competition = "low" if count < 10 else "medium" if count < 30 else "high"
        
        return {
            "active_listings_count": count,
            "competition_level": competition,
            "price_range": {
                "min": float(min(active_prices)),
                "avg": float(statistics.mean(active_prices)),
                "max": float(max(active_prices)),
                "median": float(statistics.median(active_prices))
            },
            "price_filter_stats": filter_stats  # ← Add filter stats
        }


    
    def _generate_no_data_report(self) -> Dict:
        """Generate report when no data found"""
        return {
            "part_name": self.part_name,
            "part_number": self.part_number,
            "vehicle": f"{self.year} {self.make} {self.model}",
            "analysis_timestamp": datetime.now().isoformat(),
            "data_summary": {
                "total_items_found": 0,
                "items_enriched": 0,
                "items_after_filtering": 0,
                "active_listings": 0,
                "sold_listings": 0,
                "total_data_points": 0
            },
            "error": "No relevant data found",
            "recommendation": {
                "status": "insufficient_data",
                "text": "No listings found matching your criteria. Try a broader search or different part name.",
                "suggested_price": 0,
                "confidence": "none"
            },
            "market_snapshot": {
                "active_listings_count": 0,
                "competition_level": "unknown",
                "price_range": {"min": 0, "avg": 0, "max": 0, "median": 0}
            },
            "pricing_intelligence": {
                "optimal_price": 0,
                "sweet_spot_range": {"min": 0, "max": 0},
                "price_trend": "unknown"
            },
            "demand_signals": {
                "demand_level": "unknown",
                "opportunity_rating": "unknown"
            }
        }


class CategoryExtractor:
    """Extract and normalize categories from items"""
    
    def extract_category(self, item: Dict) -> Optional[str]:
        # Try primary category
        if 'primaryCategory' in item:
            return self.normalize(item['primaryCategory'])
        
        # Try categories array
        if 'categories' in item and item['categories']:
            cat = item['categories'][-1] if isinstance(item['categories'], list) else item['categories']
            if cat:
                return self.normalize(cat)
        
        # Try title
        title = item.get('title', '').lower()
        patterns = {
            r'\b(front|rear)\s+bumper': 'Bumper',
            r'\bheadlight': 'Headlight',
            r'\btaillight': 'Taillight',
            r'\bmirror': 'Mirror',
            r'\bdoor': 'Door',
            r'\bhood\b': 'Hood',
            r'\bfender': 'Fender',
            r'\bgrille': 'Grille',
            r'\bbrake\s+pad': 'Brake Pad',
            r'\brotor': 'Rotor',
            r'\bstrut': 'Strut',
        }
        
        for pattern, name in patterns.items():
            if re.search(pattern, title):
                return name
        
        return None
    
    def normalize(self, cat: str) -> str:
        if not cat:
            return "Unknown"
        
        # Get last part of hierarchy
        parts = re.split(r'[>|/]', cat)
        cat = parts[-1].strip().title()
        
        # Remove generic terms
        for term in ['Parts', 'Auto', 'Car']:
            cat = cat.replace(term, '').strip()
        
        return cat if cat else "Unknown"

def print_formatted_report(report: Dict):
    """Pretty print the analysis report"""
    
    print("\n" + "="*80)
    print("EBAY AUTO PARTS MARKET ANALYSIS REPORT")
    print("="*80)
    
    # Header
    print(f"\n📦 Part: {report['part_name']}")
    if report.get('part_number'):
        print(f"🔢 Part Number: {report['part_number']}")
    print(f"🚗 Vehicle: {report['vehicle']}")
    print(f"📅 Analysis Date: {report['analysis_timestamp'][:10]}")
    
    # Data Summary
    print(f"\n{'─'*80}")
    print("DATA SUMMARY")
    print(f"{'─'*80}")
    ds = report['data_summary']
    print(f"  Total Items Found:     {ds['total_items_found']}")
    print(f"  Items Enriched:        {ds['items_enriched']}")
    print(f"  Items After Filtering: {ds['items_after_filtering']}")
    print(f"  Active Listings:       {ds['active_listings']}")
    print(f"  Sold Listings:         {ds['sold_listings']}")
    
    # Market Snapshot
    print(f"\n{'─'*80}")
    print("CURRENT MARKET SNAPSHOT")
    print(f"{'─'*80}")
    ms = report.get('market_snapshot', {})
    print(f"  Active Sellers:    {ms.get('active_listings_count', 0)}")
    print(f"  Competition Level: {ms.get('competition_level', 'unknown').upper()}")
    
    pr = ms.get('price_range', {})
    if pr.get('avg', 0) > 0:
        print(f"\n  Price Range:")
        print(f"    Minimum:  ${pr.get('min', 0):.2f}")
        print(f"    Average:  ${pr.get('avg', 0):.2f}")
        print(f"    Median:   ${pr.get('median', 0):.2f}")
        print(f"    Maximum:  ${pr.get('max', 0):.2f}")
    
    # Historical Performance
    print(f"\n{'─'*80}")
    print("HISTORICAL PERFORMANCE")
    print(f"{'─'*80}")
    hp = report.get('historical_performance', {})
    
    for period in ['30_days', '90_days', '180_days', '365_days']:
        if period in hp:
            data = hp[period]
            units = data.get('units_sold', 0)
            if units > 0:
                print(f"  {period.replace('_', ' ').title()}:")
                print(f"    Units Sold:     {units}")
                print(f"    Average Price:  ${data.get('avg_price', 0):.2f}")
                print(f"    Total Revenue:  ${data.get('total_revenue', 0):.2f}")
    
    if 'sell_through_rate' in hp:
        print(f"\n  Sell-Through Rate: {hp['sell_through_rate']:.1f}%")
    
    # Pricing Intelligence
    print(f"\n{'─'*80}")
    print("PRICING INTELLIGENCE")
    print(f"{'─'*80}")
    pi = report.get('pricing_intelligence', {})
    print(f"  Optimal Price:     ${pi.get('optimal_price', 0):.2f}")
    
    ss = pi.get('sweet_spot_range', {})
    if ss.get('min', 0) > 0:
        print(f"  Sweet Spot Range:  ${ss.get('min', 0):.2f} - ${ss.get('max', 0):.2f}")
    
    print(f"  Price Trend:       {pi.get('price_trend', 'unknown').upper()}")
    
    # Profit margins
    pm = pi.get('profit_margin_estimate', {})
    if pm.get('gross_price', 0) > 0:
        print(f"\n  Profit Estimate (at ${pm['gross_price']:.2f}):")
        print(f"    eBay Fee:       -${pm.get('ebay_fee', 0):.2f}")
        print(f"    Payment Fee:    -${pm.get('payment_fee', 0):.2f}")
        print(f"    Shipping Cost:  -${pm.get('shipping_cost', 0):.2f}")
        print(f"    Net Profit:      ${pm.get('net_profit', 0):.2f}")
        print(f"    Margin:          {pm.get('margin_percent', 0):.1f}%")
    
    # Demand Signals
    print(f"\n{'─'*80}")
    print("DEMAND SIGNALS")
    print(f"{'─'*80}")
    ds = report.get('demand_signals', {})
    print(f"  Demand Level:       {ds.get('demand_level', 'unknown').replace('_', ' ').upper()}")
    print(f"  Opportunity Rating: {ds.get('opportunity_rating', 'unknown').upper()}")
    
    if ds.get('units_sold_30d', 0) > 0:
        print(f"\n  Recent Sales:")
        print(f"    Last 30 Days:  {ds.get('units_sold_30d', 0)} units")
        print(f"    Last 90 Days:  {ds.get('units_sold_90d', 0)} units")
        print(f"    Velocity:      {ds.get('sales_velocity_30d', 0):.2f} units/day")
        
        dte = ds.get('days_to_sell_estimate', 0)
        if dte < 999:
            print(f"    Est. Time to Sell: {dte:.0f} days")
    
    # Competition Analysis
    print(f"\n{'─'*80}")
    print("COMPETITION ANALYSIS")
    print(f"{'─'*80}")
    ca = report.get('competition_analysis', {})
    print(f"  Total Active Sellers: {ca.get('total_active_sellers', 0)}")
    
    pd = ca.get('price_distribution', {})
    if pd:
        print(f"\n  Price Distribution:")
        for range_name, count in pd.items():
            if count > 0:
                print(f"    {range_name.replace('_', ' ').title()}: {count} listings")
    
    cb = ca.get('condition_breakdown', {})
    if cb:
        print(f"\n  Condition Breakdown:")
        for condition, count in cb.items():
            print(f"    {condition}: {count}")
    
    # Related Parts
    rp = report.get('related_parts', [])
    if rp:
        print(f"\n{'─'*80}")
        print("RELATED PARTS")
        print(f"{'─'*80}")
        print(f"  {', '.join(rp[:7])}")
    
    # Recommendation
    print(f"\n{'='*80}")
    print("RECOMMENDATION")
    print(f"{'='*80}")
    rec = report.get('recommendation', {})
    
    status = rec.get('status', 'unknown').upper()
    if 'good' in status.lower():
        icon = "✅"
    elif 'moderate' in status.lower() or 'fair' in status.lower():
        icon = "⚠️"
    else:
        icon = "❌"
    
    print(f"\n{icon} Status: {status}")
    print(f"\n{rec.get('text', 'No recommendation available')}")
    print(f"\nSuggested Price: ${rec.get('suggested_price', 0):.2f}")
    print(f"Confidence Level: {rec.get('confidence', 'unknown').upper()}")
    
    print(f"\n{'='*80}\n")



async def example_maximum_collection():
    """Example: Collect maximum data for a part"""
    
    analyzer = EnhancedEbayAnalyzer(
        part_name="ABS Pump",
        part_number="47050-47070",
        year=2010,
        make="Toyota",
        model="Prius",
        oauth_token="v^1.1#i^1#p^3#f^0#r^0#I^3#t^H4sIAAAAAAAA/+1Ze2hb1xm3/CqZ65Su3RzcB5qaUrpwpfuW7l0kkB+J5cWWYilOawja0TnnWre+r9x7rmWZbjVmMxtbMmibjhG6JhSaZWFlMLqyBbLR/jGyUbrRhWSUFdqNtRAGG4yWQcd2rmwritcllpRSwaZ/xD3ne/2+8z3Og13p3/H5tYm1DwZDt3WfWmFXukMhboDd0d+3Z2dP93BfF9tAEDq1snuld7Xnvb0eMA1HncGeY1seDi+ZhuWptcFkxHct1Qae7qkWMLGnEqjm01MHVD7Kqo5rExvaRiScGUtGoIAFSREwEFEcA1mko9amzIKdjMgoHgcySgi8xiM2XqLznufjjOURYJFkhGd5ieFYhpcLrKQKnMqJUU7i5yLhWex6um1RkigbSdXMVWu8boOtNzYVeB52CRUSSWXS+/LZdGZsfLqwN9YgK7XhhzwBxPeu/xq1EQ7PAsPHN1bj1ajVvA8h9rxILLWu4XqhanrTmBbMr7k6ISuigsSSBLiEJPP4lrhyn+2agNzYjmBER4xWI1WxRXRSvZlHqTdKj2FINr6mqYjMWDj4O+gDQ9d07CYj4yPpRw/lx2ci4Xwu59qLOsIoQMrLUiLOiWKci6TKlBo5wCXehpZ1URs+3qJm1LaQHnjMC0/bZARTk/FWx/ANjqFEWSvrpjUSmNNIF990oEjpYptL6JOyFSwqNqkXwrXPm7t/Mx6uRcAtiwgByIJSQjJIIJGF8KMiIsj1ZqMiFSxMOpeLBbbgEqgyJnAXMHEMADEDqXt9E7s6UgVJ44WEhhkkKxojKprGlCQkM5yGMYtxqQSVxP9McBDi6iWf4HqAbJ2oIUxG8tB2cM42dFiNbCWpVZuNcFjykpEyIY4ai1UqlWhFiNrufIxnWS72yNSBPCxjE0TqtPrNiRm9FhiQVg5Kr5KqQ61ZonFHlVvzkZTgohz1ZTWPDYMObEbtdbalto7+F5Cjhk49UKAqOgvjhO0RjNqChvCiDnFRR52FjF/PdYlTFIWLU9a2QBr2vG5NYVK2OwxmUBIyY21hoxUUkM5CVa8uUoHnN6sQKzK01LBsW2DTjpMxTZ+AkoEzHbaWEi8LotQWPMf3Oy0RE/oykMmy73qVtqAFjVfVgaYSewFbW0tpkOufPNaZ8X0z4/mJYiH7xfHpttDOYM3FXrkQYO20OE0fTB9I099UhlMwtCqCtpT342Vtbt7JiYI9klUEUK1IsFpCnJtV0MgCVIwC3jNKtAI9Hh1YmLDMikfsQ5Vksi0n5TF0cYeVroMjLDZHprJjM/FCLs3vS1e0OTQ7up8cjRVgefQot6wrs3uE/UvLbHvgp+Y7LdNpy71F7bbwUSleFxPk+icG0l1PzGKtChXpV1tAx+c7rl7zEMhIZjW6kiwAJU6AiKMDnKZpWKDn7bbbb4fhTVct350BZYaeX22H7oeZ3MwYo/AyByWIBCYOZVmRodBmX+60Zb5VbdkLjm8fH7Qg11uBF8jwqBDg6NFg5xCFthmzgU/KwVCxZnV4O0Qxjx7/ousHfio56mKAbMuotsLcBI9uLdIDo+1WW1FYZ26CB0Bo+xZpRd0GaxMcmm9oumEEtwKtKGxgb8ZMCxhVokOvJZW6FUSb1wSLA6o1gEj3nCBftsVJx0zsQhzV0frNYivGupgqBLWrtFaYmlRZN9myia7pcF2G55c86OrO9q2AQa7fVFYr/qB7TbeppVtn2JaqBi6MsKEv4u2mXd1vlMVukkXDGJUAXGipopjAcdq90HIx0l0MSdF39c5qbLV+XqQNvWrai4DZ0t4Z4GmPIYJwe/ADB3fidVAunc8fzs60dyE0hhc/9k0azfWRZjemgNdEzLEM5BISIyoJjQEwLjOJuCKjhEy3afH27oY67hqMi8ucKFFcfJt3CcAwOwuZ49rIh0E9/z+yLQMN7yX/8U4Wu/6VOtVV+3GroVfY1dCF7lCI3cs+yD3Afq6/51Bvz+3Dnk7oTgJoUU+ftwDxXRxdwFUH6G73XV2/uvT76fvPT37/G38aWvna7tiTXTsbHslPHWF31Z/Jd/RwAw1v5uy912b6uDuGBnmJY3mZlQSOE+fYB67N9nKf7b37u/j+h8Nn/9X3/jc/fe5T70StE7GBw+xgnSgU6uvqXQ11ffnqkHD2n8WXxrqyL/XOXRF/Evrz7QOPRLOz8rHhtfljdyfVtw+98dRRNv3bytX+bim6/9m+15/74/Fh680PMk/+oI+Z+87pczY68erTx9+85+pXya5q/w9/uVIc+d3Bq0NvLLz1qnLu1wOvvfPhiW+9GO654+yl87etvfWZy4PMH0Q0fE54b/D1l6s/mtz1wvd2nj7z7Z+e6DMu7b442XvyzN+6o3PPPp8ytTtLF2zrF9IT92ZefP/IXSnrteryh6ePyRcfV05yz/313YefeeWFRweOFH9+ZfXwy9zJv3ypMLT76cl3OU4YnzgzuWTec/l0Jnflzt98vXT8obXc84/bF7WvXFa/cN/P3v77M/ed//GFJ/L/WF/LfwPuaMUiviAAAA=="
    )
    
    
    # Collect and analyze data
    result = await analyzer.analyze()
    
    # Pretty print the report
    print_formatted_report(result)
    
    # Also save as JSON for programmatic use
    import json
    print("\n" + "="*80)
    print("JSON OUTPUT (for programmatic use)")
    print("="*80)
    print(json.dumps(result, indent=2))
    
    return result



if __name__ == "__main__":
    # Run example
    import asyncio
    asyncio.run(example_maximum_collection())



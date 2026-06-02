"""
eBay Auto Parts Scraper & Analyzer
Pure scraping approach with intelligent categorization
"""

import asyncio
import re
import statistics
import time
from typing import List, Dict, Optional, Tuple, Any
from collections import defaultdict, Counter
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from dateutil import parser
import math
import random
import logging
from playwright.async_api import async_playwright
import anthropic
from urllib.parse import quote, urlparse, urlencode, parse_qs

logger = logging.getLogger(__name__)


# ============================================================================
# CONFIGURATION
# ============================================================================

class Config:
    """Configuration for scraping and analysis"""
    DEBUG_STOP_AFTER_FIRST_LEAF = False
    # Scraper Pagination
    SCRAPER_ITEMS_PER_PAGE = 240
    SCRAPER_MAX_PAGES = 15
    SCRAPER_MAX_TOTAL_ITEMS = 3600
    SCRAPER_CONCURRENT_PAGES = 3
    
    # Scraper Settings
    SCRAPER_HEADLESS = True
    SCRAPER_TIMEOUT = 30000
    SCRAPER_PAGE_DELAY = (2, 5)
    
    # Deduplication
    TITLE_SIMILARITY_THRESHOLD = 0.85
    
    # Vehicle Matching
    VEHICLE_MATCH_MIN_SCORE = 60
    
    # Grouping
    GROUP_SIMILARITY_THRESHOLD = 0.60
    MIN_ITEMS_PER_GROUP = 3
    MAX_GROUPS_FOR_NAMING = 20
    ITEMS_PER_GROUP_FOR_NAMING = 5
    
    # Statistical Outlier Detection
    OUTLIER_METHOD = "iqr"
    IQR_MULTIPLIER = 1.5
    MIN_PRICE_ABSOLUTE = 5.0
    
    # Claude API
    CLAUDE_API_KEY = None
    CLAUDE_MODEL = "claude-sonnet-4-5-20250929"


# ============================================================================
# UNIVERSAL SCRAPER (ACTIVE + SOLD) - WITH ASYNC
# ============================================================================

class UniversalEbayScraper:
    """Scrape both active and sold listings using Playwright with async batch processing"""
    
    def __init__(self):
        self._leaf_category_collected = False  # Track if first leaf category collected (for debug mode)
    
    async def _take_screenshot(self, page, step_name: str, category_info: str = "") -> str:
        """Take a screenshot with consistent naming (only called on errors)"""
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            category_safe = category_info.replace(' ', '_').replace('/', '_')[:50] if category_info else ""
            filename = f"error_{step_name}_{category_safe}_{timestamp}.png"
            await page.screenshot(path=filename, full_page=True)
            print(f"        ___________________________________________")
            print(f"        📸 ERROR Screenshot saved: {filename}")
            print(f"        ___________________________________________")
            return filename
        except Exception as e:
            print(f"        ⚠️  Screenshot failed: {e}")
            return ""

    async def collect_for_queries(
        self, 
        queries: List[str],
        include_active: bool = True,
        include_sold: bool = True,
        use_category_tree: bool = False
        
    ) -> Tuple[List[Dict], Optional[Dict]]:
        """Collect listings for multiple queries
        Returns: (flattened_listings, nested_category_tree)
        """
        all_listings = []
        nested_categories = {}
        
        for query_idx, query in enumerate(queries, 1):
            print(f"\n{'='*80}")
            print(f"SCRAPE Query {query_idx}/{len(queries)}: '{query}'")
            print(f"{'='*80}")
            
            if use_category_tree:
                # Use new category-based scraping (returns nested structure)
                # Run active and sold concurrently
                tasks = []
                if include_active:
                    tasks.append(('active', self._scrape_by_category_tree(query, listing_type='active')))
                if include_sold:
                    tasks.append(('sold', self._scrape_by_category_tree(query, listing_type='sold')))
                
                # Run all tasks concurrently
                if tasks:
                    print(f"  🚀 Running {len(tasks)} scraper(s) concurrently...")
                    results = await asyncio.gather(*[task[1] for task in tasks], return_exceptions=True)
                    
                    # Process results
                    for (listing_type, _), result in zip(tasks, results):
                        if isinstance(result, Exception):
                            print(f"  ❌ {listing_type.capitalize()} scraping failed: {result}")
                            continue
                        
                        if isinstance(result, dict):
                            nested_categories[listing_type] = result
                            items = self._flatten_category_tree(result, listing_type)
                            all_listings.extend(items)
                            total = self._count_items_in_tree(result)
                            print(f"  ✅ {listing_type.capitalize()}: {total} items")
                        else:
                            all_listings.extend(result if isinstance(result, list) else [])
                            print(f"  ✅ {listing_type.capitalize()}: {len(result)} items")
            else:
                # Original query-based scraping
                # Run active and sold concurrently
                tasks = []
                if include_active:
                    tasks.append(('active', self._scrape_single_query(query, listing_type='active')))
                if include_sold:
                    tasks.append(('sold', self._scrape_single_query(query, listing_type='sold')))
                
                # Run all tasks concurrently
                if tasks:
                    print(f"  🚀 Running {len(tasks)} scraper(s) concurrently...")
                    results = await asyncio.gather(*[task[1] for task in tasks], return_exceptions=True)
                    
                    # Process results
                    for (listing_type, _), result in zip(tasks, results):
                        if isinstance(result, Exception):
                            print(f"  ❌ {listing_type.capitalize()} scraping failed: {result}")
                            continue
                        
                        all_listings.extend(result if isinstance(result, list) else [])
                        print(f"  ✅ {listing_type.capitalize()}: {len(result)} items")
            
            print(f"✅ Query {query_idx} complete")
        
        return all_listings, nested_categories if nested_categories else None
    
    async def _scrape_single_query(self, query: str, listing_type: str = 'active') -> List[Dict]:
        """Scrape listings for a single query with async page processing"""

        print(f"     🌐 Starting {listing_type} listings scraper for: '{query}'")
        listings = []

        async with async_playwright() as p:
            browser = None
            try:
                print(f"     🚀 Launching browser (headless={Config.SCRAPER_HEADLESS})...")
                browser = await p.chromium.launch(
                    headless=Config.SCRAPER_HEADLESS,
                    args=['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage']
                )

                print(f"     📱 Creating browser context...")
                context = await browser.new_context(
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                    viewport={'width': 1920, 'height': 1080}
                )

                page = await context.new_page()
                page.set_default_timeout(Config.SCRAPER_TIMEOUT)

                # Navigate and search
                print(f"     🔗 Navigating to eBay...")
                await page.goto("https://www.ebay.com", wait_until="domcontentloaded")
                await page.wait_for_timeout(2000)

                print(f"     🔍 Searching for: '{query}'...")
                await page.click("#gh-ac")
                await page.fill("#gh-ac", query)
                await page.click("#gh-search-btn")
                await page.wait_for_load_state("domcontentloaded")
                await page.wait_for_timeout(3000)

                print("Clicked on search button ")

                print("Choosing category")
                await self._choose_parts_category(page)
                
                if listing_type == 'sold':
                    print(f"     🏷️  Applying sold filter...")
                    await self._apply_sold_filter(page)

                print(f"     ⚙️  Applying condition filters...")
                await self._apply_used_condition_filter(page)


                print(f"     📊 Setting items per page to 240...")
                await self._set_items_per_page(page, 240)

                total_items = await self._get_total_count(page)
                print(f"     ✅ Found {total_items:,} {listing_type} items")

                if total_items == 0:
                    print(f"     ⚠️  No items found, closing browser...")
                    await browser.close()
                    return []

                max_items = min(total_items, Config.SCRAPER_MAX_TOTAL_ITEMS)
                pages_needed = math.ceil(max_items / Config.SCRAPER_ITEMS_PER_PAGE)
                pages_needed = min(pages_needed, Config.SCRAPER_MAX_PAGES)

                print(f"     📄 Will scrape {pages_needed} pages (max {max_items} items)")

                # Process pages sequentially (more reliable)
                for page_num in range(1, pages_needed + 1):
                    try:
                        print(f"     📖 Processing page {page_num}/{pages_needed}...")
                        await page.wait_for_selector("#srp-river-results", timeout=15000)
                        await page.wait_for_timeout(2000)

                        page_listings = await self._extract_listings_from_page(page)

                        if page_listings:
                            if page_num == 1 and total_items < Config.SCRAPER_ITEMS_PER_PAGE:
                                page_listings = page_listings[:total_items]

                            for listing in page_listings:
                                listing['query'] = query
                                listing['status'] = listing_type

                            listings.extend(page_listings)
                            print(f"     ✓ Page {page_num}: {len(page_listings)} items (total: {len(listings)})")
                        else:
                            print(f"     ⚠️  Page {page_num}: No items extracted")

                        # Navigate to next page if not last
                        if page_num < pages_needed:
                            print(f"     ➡️  Navigating to next page...")
                            if not await self._go_to_next_page(page):
                                print(f"     ⛔ Failed to navigate to next page, stopping...")
                                break

                            delay = random.uniform(*Config.SCRAPER_PAGE_DELAY)
                            print(f"     ⏱️  Waiting {delay:.1f}s before next page...")
                            await asyncio.sleep(delay)

                    except Exception as e:
                        print(f"     ❌ Error on page {page_num}: {e}")
                        break

            except Exception as e:
                print(f"     ❌ Scraping error: {e}")
                import traceback
                print(f"     {traceback.format_exc()}")
            finally:
                if browser:
                    print(f"     🔒 Closing browser...")
                    await browser.close()

        print(f"     🎯 Scraping complete: {len(listings)} {listing_type} listings collected")
        return listings
    
    def _flatten_category_tree(self, category_tree: Dict, listing_type: str) -> List[Dict]:
        """Flatten nested category tree to list of items for backward compatibility"""
        items = []
        
        def extract_items(cat_dict: Dict):
            if 'items' in cat_dict and cat_dict['items']:
                if isinstance(cat_dict['items'], dict):
                    # Items organized by type
                    for type_name, type_items in cat_dict['items'].items():
                        if isinstance(type_items, list):
                            for item in type_items:
                                item['status'] = listing_type
                                item['category_type'] = type_name
                                items.append(item)
                elif isinstance(cat_dict['items'], list):
                    # Regular list of items
                    for item in cat_dict['items']:
                        item['status'] = listing_type
                        items.append(item)
            
            if 'categories' in cat_dict:
                for subcat in cat_dict['categories']:
                    extract_items(subcat)
        
        extract_items(category_tree)
        return items
    
    def _format_time(self, seconds: float) -> str:
        """Format seconds into human-readable time string"""
        if seconds < 60:
            return f"{seconds:.1f}s"
        elif seconds < 3600:
            minutes = int(seconds // 60)
            secs = int(seconds % 60)
            return f"{minutes}m {secs}s"
        else:
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            secs = int(seconds % 60)
            return f"{hours}h {minutes}m {secs}s"
    
    async def _scrape_by_category_tree(self, query: str, listing_type: str = 'active') -> Dict:
        """Scrape by traversing category tree following links 6000 → 6028 → 6030 → subcategories"""
        print(f"     🌐 Starting category-tree {listing_type} scraper for: '{query}'")
        
        # Track start time
        start_time = time.time()
        self._scrape_start_time = start_time
        self._category_times = []  # Track time per category
        
        # Reset debug flag for new scrape
        self._leaf_category_collected = False
        
        async with async_playwright() as p:
            browser = None
            try:
                print(f"     🚀 Launching browser (headless={Config.SCRAPER_HEADLESS})...")
                browser = await p.chromium.launch(
                    headless=Config.SCRAPER_HEADLESS,
                    args=['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage']
                )
                
                context = await browser.new_context(
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                    viewport={'width': 1920, 'height': 1080}
                )
                
                page = await context.new_page()
                page.set_default_timeout(Config.SCRAPER_TIMEOUT)
                
                # Step 1: Navigate to eBay and search
                print(f"     🔍 Searching for: '{query}'...")
                await page.goto("https://www.ebay.com", wait_until="domcontentloaded")
                await page.wait_for_timeout(2000)
                await page.click("#gh-ac")
                await page.fill("#gh-ac", query)
                await page.click("#gh-search-btn")
                await page.wait_for_load_state("domcontentloaded")
                await page.wait_for_timeout(3000)
                
                # Step 2: Navigate 6000 → 6028 → 6030 by finding and clicking links
                print(f"     📂 Step 1: Finding and clicking category 6000 (eBay Motors)...")
                cat_6000_link = page.locator('#x-refine__group__0 a[href*="/sch/6000/"]').first
                if await cat_6000_link.count() > 0:
                    await cat_6000_link.click()
                    await page.wait_for_load_state("domcontentloaded")
                    await page.wait_for_timeout(2000)
                    print(f"     ✅ Clicked 6000")
                else:
                    print(f"     ⚠️  Category 6000 link not found, using direct URL")
                    # Retry navigation with better error handling
                    nav_success = False
                    for retry in range(3):
                        try:
                            print(f"     🔄 Attempting navigation (attempt {retry + 1}/3)...")
                            await page.goto(f"https://www.ebay.com/sch/6000/i.html?_nkw={quote(query)}", 
                                          wait_until="domcontentloaded", timeout=30000)
                            # Try networkidle but don't fail if it times out (especially when running concurrent browsers)
                            try:
                                await page.wait_for_load_state("networkidle", timeout=5000)
                            except:
                                # networkidle timeout is okay, page is loaded enough
                                pass
                            nav_success = True
                            break
                        except Exception as nav_error:
                            print(f"     ⚠️  Navigation attempt {retry + 1} failed: {nav_error}")
                            if retry < 2:
                                await page.wait_for_timeout(2000 * (retry + 1))  # Exponential backoff
                            else:
                                # Last attempt: try with different wait strategy
                                try:
                                    await page.goto(f"https://www.ebay.com/sch/6000/i.html?_nkw={quote(query)}", 
                                                  wait_until="load", timeout=30000)
                                    nav_success = True
                                    break
                                except Exception as final_error:
                                    print(f"     ❌ Final navigation attempt failed: {final_error}")
                                    raise
                    
                    if not nav_success:
                        raise Exception("Failed to navigate to category 6000 after 3 attempts")
                    
                    await page.wait_for_timeout(2000)
                
                print(f"     📂 Step 2: Finding and clicking category 6028 (Parts & Accessories)...")
                cat_6028_link = page.locator('#x-refine__group__0 a[href*="/sch/6028/"]').first
                if await cat_6028_link.count() > 0:
                    await cat_6028_link.click()
                    await page.wait_for_load_state("domcontentloaded")
                    await page.wait_for_timeout(2000)
                    print(f"     ✅ Clicked 6028")
                else:
                    print(f"     ⚠️  Category 6028 link not found, using direct URL")
                    # Retry navigation with better error handling
                    nav_success = False
                    for retry in range(3):
                        try:
                            print(f"     🔄 Attempting navigation to 6028 (attempt {retry + 1}/3)...")
                            await page.goto(f"https://www.ebay.com/sch/6028/i.html?_nkw={quote(query)}",
                                          wait_until="domcontentloaded", timeout=30000)
                            # Try networkidle but don't fail if it times out
                            try:
                                await page.wait_for_load_state("networkidle", timeout=5000)
                            except:
                                pass
                            nav_success = True
                            print(f"     ✅ Successfully navigated to 6028")
                            break
                        except Exception as nav_error:
                            print(f"     ⚠️  Navigation attempt {retry + 1} failed: {nav_error}")
                            if retry < 2:
                                await page.wait_for_timeout(2000 * (retry + 1))
                            else:
                                # Last attempt: try with different wait strategy
                                try:
                                    await page.goto(f"https://www.ebay.com/sch/6028/i.html?_nkw={quote(query)}",
                                                  wait_until="load", timeout=30000)
                                    nav_success = True
                                    print(f"     ✅ Successfully navigated to 6028 (using load strategy)")
                                    break
                                except Exception as final_error:
                                    print(f"     ❌ Final navigation attempt to 6028 failed: {final_error}")
                                    # Don't raise - just continue with what we have
                                    print(f"     ⚠️  Skipping category 6028, will try 6030...")

                    await page.wait_for_timeout(2000)
                
                print(f"     📂 Step 3: Finding and clicking category 6030 (Car & Truck Parts & Accessories)...")
                cat_6030_link = page.locator('#x-refine__group__0 a[href*="/sch/6030/"]').first
                if await cat_6030_link.count() > 0:
                    await cat_6030_link.click()
                    await page.wait_for_load_state("domcontentloaded")
                    await page.wait_for_timeout(2000)
                    print(f"     ✅ Clicked 6030")
                else:
                    print(f"     ⚠️  Category 6030 link not found, using direct URL")
                    # Retry navigation with better error handling
                    nav_success = False
                    for retry in range(3):
                        try:
                            print(f"     🔄 Attempting navigation to 6030 (attempt {retry + 1}/3)...")
                            await page.goto(f"https://www.ebay.com/sch/6030/i.html?_nkw={quote(query)}",
                                          wait_until="domcontentloaded", timeout=30000)
                            # Try networkidle but don't fail if it times out
                            try:
                                await page.wait_for_load_state("networkidle", timeout=5000)
                            except:
                                pass
                            nav_success = True
                            print(f"     ✅ Successfully navigated to 6030")
                            break
                        except Exception as nav_error:
                            print(f"     ⚠️  Navigation attempt {retry + 1} failed: {nav_error}")
                            if retry < 2:
                                await page.wait_for_timeout(2000 * (retry + 1))
                            else:
                                # Last attempt: try with different wait strategy
                                try:
                                    await page.goto(f"https://www.ebay.com/sch/6030/i.html?_nkw={quote(query)}",
                                                  wait_until="load", timeout=30000)
                                    nav_success = True
                                    print(f"     ✅ Successfully navigated to 6030 (using load strategy)")
                                    break
                                except Exception as final_error:
                                    print(f"     ❌ Final navigation attempt to 6030 failed: {final_error}")
                                    # Don't raise - just continue with what we have
                                    print(f"     ⚠️  Skipping category 6030, continuing with current page...")

                    await page.wait_for_timeout(2000)
                
                # Step 3: Apply filters
                print(f"     🏷️  Applying filters...")
                if listing_type == 'sold':
                    await self._apply_sold_filter(page)
                    await page.wait_for_timeout(1000)
                
                await self._apply_used_condition_filter(page)
                await page.wait_for_timeout(1000)
                
                await self._set_items_per_page(page, 240)
                await page.wait_for_timeout(2000)
                
                # Wait for sidebar to be ready before starting traversal
                print(f"     🔍 Ensuring sidebar is ready before traversal...")
                try:
                    await page.wait_for_selector('#x-refine__group__0', timeout=15000, state='attached')
                    await page.wait_for_load_state("domcontentloaded")
                    await page.wait_for_timeout(2000)  # Extra wait for sidebar to fully render
                    print(f"     ✅ Sidebar ready")
                except Exception as sidebar_error:
                    print(f"     ⚠️  Sidebar wait warning: {sidebar_error}, continuing anyway...")
                    await page.wait_for_timeout(3000)  # Give extra time
                
                # Step 4: Start category traversal
                print(f"     🌳 Starting category tree traversal...")
                collected_ids = set()  # Initialize collected_ids for deduplication
                category_tree = await self._traverse_category_tree_new(page, query, listing_type, depth=0, parent_category_id="6030", parent_category_name="Car & Truck Parts & Accessories", collected_ids=collected_ids)
                
            except Exception as e:
                print(f"     ❌ Category tree scraping error: {e}")
                import traceback
                print(f"     {traceback.format_exc()}")
                category_tree = {'depth': '0', 'category_name': 'Error', 'category_id': '0', 'categories': [], 'items': None, 'specs': []}
            finally:
                if browser:
                    print(f"     🔒 Closing browser...")
                    await browser.close()
        
        # Calculate and display final timing summary
        if hasattr(self, '_scrape_start_time') and self._scrape_start_time:
            end_time = time.time()
            total_time = end_time - self._scrape_start_time
            total_time_str = self._format_time(total_time)
            
            if hasattr(self, '_category_times') and len(self._category_times) > 0:
                avg_time = sum(self._category_times) / len(self._category_times)
                min_time = min(self._category_times)
                max_time = max(self._category_times)
                avg_time_str = self._format_time(avg_time)
                min_time_str = self._format_time(min_time)
                max_time_str = self._format_time(max_time)
                
                print(f"     {'─'*60}")
                print(f"     ⏱️  TIMING SUMMARY")
                print(f"     {'─'*60}")
                print(f"     Total time: {total_time_str}")
                print(f"     Categories processed: {len(self._category_times)}")
                print(f"     Average time per category: {avg_time_str}")
                print(f"     Fastest category: {min_time_str}")
                print(f"     Slowest category: {max_time_str}")
                print(f"     {'─'*60}")
        
        total = self._count_items_in_tree(category_tree)
        print(f"     🎯 Category tree scraping complete: {total} {listing_type} listings collected")
        return category_tree
    
    def _count_items_in_tree(self, tree: Dict) -> int:
        """Count total items in category tree"""
        count = 0
        if tree.get('items'):
            if isinstance(tree['items'], dict):
                # Items by type
                for type_items in tree['items'].values():
                    count += len(type_items) if isinstance(type_items, list) else 0
            elif isinstance(tree['items'], list):
                count += len(tree['items'])
        if tree.get('categories'):
            for cat in tree['categories']:
                count += self._count_items_in_tree(cat)
        return count
    
    async def _traverse_category_tree(self, page, query: str, listing_type: str, base_params: Dict, depth: int = 0, category_path: List[str] = None, visited_ids: set = None) -> Dict:
        """Recursively traverse category tree and scrape items from each leaf category, returns nested structure"""
        indent = "  " * (depth + 1)
        category_path = category_path or []
        visited_ids = visited_ids or set()
        result = {
            'categories': {},
            'items': [],
            'total_items': 0
        }
        
        # Safety check: prevent infinite loops
        if depth > 10:
            print(f"{indent}⚠️  Max depth reached, stopping recursion")
            return result
        
        try:
            # Wait for category sidebar
            await page.wait_for_selector('#x-refine__group__0', timeout=10000)
            await page.wait_for_timeout(1000)
            
            # Extract categories from current level (excluding current and visited)
            categories = await self._extract_categories_from_sidebar(page, exclude_ids=visited_ids)
            
            print(f"{indent}📋 Found {len(categories)} new categories at depth {depth}")
            
            # If no subcategories, this is a leaf - scrape all items
            if not categories:
                print(f"{indent}🍃 Leaf category - scraping all items...")
                
                total_items = await self._get_total_count(page)
                print(f"{indent}   ✅ Found {total_items:,} items in this category")
                
                if total_items > 0:
                    category_listings = await self._scrape_category_pages(page, query, listing_type)
                    # Add category path to each item
                    for item in category_listings:
                        item['category_path'] = category_path.copy()
                    result['items'] = category_listings
                    result['total_items'] = len(category_listings)
                    print(f"{indent}   ✅ Scraped {len(category_listings)} items")
                
                return result
            
            # Process each category recursively
            for cat_idx, category in enumerate(categories, 1):
                cat_id = category['id']
                
                # Skip if already visited (prevent infinite loops)
                if cat_id in visited_ids:
                    print(f"{indent}[{cat_idx}/{len(categories)}] ⏭️  Skipping already visited: {category['name']} (ID: {cat_id})")
                    continue
                
                print(f"{indent}[{cat_idx}/{len(categories)}] 📂 Processing: {category['name']} (ID: {cat_id})")
                
                try:
                    # Mark as visited
                    new_visited = visited_ids | {cat_id}
                    
                    # Build URL with filters from base_params
                    category_url = category['url']
                    if '?' not in category_url:
                        sep = '?'
                    else:
                        sep = '&'
                    
                    # Append base params to maintain filters
                    params_str = '&'.join(f"{k}={quote(str(v))}" for k, v in base_params.items())
                    full_category_url = f"{category_url}{sep}{params_str}"
                    
                    # Navigate to category (filters already in URL, no need to reapply)
                    await page.goto(full_category_url, wait_until="domcontentloaded")
                    await page.wait_for_timeout(2000)
                    
                    # Screenshot: After navigating to category
                    # Check if this category has subcategories (excluding current and visited)
                    await page.wait_for_selector('#x-refine__group__0', timeout=5000)
                    await page.wait_for_timeout(1000)
                    subcategories = await self._extract_categories_from_sidebar(page, exclude_ids=new_visited)
                    
                    # Create category entry
                    category_key = f"{cat_id}_{category['name'].lower().replace(' ', '_')[:30]}"
                    new_path = category_path + [category['name']]
                    
                    if subcategories:
                        # Has subcategories - recurse deeper
                        print(f"{indent}   🔽 Has {len(subcategories)} new subcategories, recursing...")
                        
                        sub_result = await self._traverse_category_tree(
                            page, query, listing_type, base_params, depth + 1, new_path, new_visited
                        )
                        result['categories'][category_key] = {
                            'id': cat_id,
                            'name': category['name'],
                            'url': category['url'],
                            'category_path': new_path,
                            'categories': sub_result['categories'],
                            'items': sub_result['items'],
                            'total_items': sub_result['total_items']
                        }
                        result['total_items'] += sub_result['total_items']
                    else:
                        # Leaf category - scrape items
                        print(f"{indent}   🍃 Leaf category - scraping items...")
                        await self._set_items_per_page(page, 240)
                        
                        total_items = await self._get_total_count(page)
                        print(f"{indent}   ✅ Found {total_items:,} items")
                        
                        category_listings = []
                        if total_items > 0:
                            category_listings = await self._scrape_category_pages(page, query, listing_type)
                            # Add category path to each item
                            for item in category_listings:
                                item['category_path'] = new_path
                            print(f"{indent}   ✅ Scraped {len(category_listings)} items")
                        
                        result['categories'][category_key] = {
                            'id': cat_id,
                            'name': category['name'],
                            'url': category['url'],
                            'category_path': new_path,
                            'categories': {},
                            'items': category_listings,
                            'total_items': len(category_listings)
                        }
                        result['total_items'] += len(category_listings)
                    
                    # Small delay between categories
                    await asyncio.sleep(random.uniform(1, 2))
                    
                except Exception as e:
                    print(f"{indent}   ⚠️  Error processing category {category['name']}: {e}")
                    # Screenshot: Error occurred
                    await self._take_screenshot(page, f"depth_{depth}_error", f"cat_{cat_id}_{category['name'][:20]}")
                    continue
            
        except Exception as e:
            print(f"{indent}❌ Error in category traversal: {e}")
            # Screenshot: Error in traversal
            try:
                await self._take_screenshot(page, f"depth_{depth}_traversal_error", f"general_error")
            except:
                pass
        
        return result
    
    async def _traverse_category_tree_new(self, page, query: str, listing_type: str, depth: int, parent_category_id: str, parent_category_name: str, parent_link: Optional[Any] = None, collected_ids: set = None) -> Dict:
        """New traversal: Find selected category span, get next ul, extract siblings, traverse with backtracking"""
        if collected_ids is None:
            collected_ids = set()
        
        indent = "  " * depth
        print(f"{indent}{'='*60}")
        print(f"{indent}🌳 DEPTH {depth}: Starting traversal for '{parent_category_name}' (ID: {parent_category_id})")
        print(f"{indent}{'='*60}")
        
        # Wait for sidebar with retries (important after filter application or navigation)
        sidebar_ready = False
        for retry in range(3):
            try:
                print(f"{indent}   🔍 Waiting for sidebar to load (attempt {retry + 1}/3)...")
                await page.wait_for_selector('#x-refine__group__0', timeout=15000, state='attached')
                # Also check if it's visible
                sidebar = page.locator('#x-refine__group__0').first
                if await sidebar.count() > 0:
                    # Give it a moment to fully render
                    await page.wait_for_timeout(2000)
                    sidebar_ready = True
                    print(f"{indent}   ✅ Sidebar ready")
                    break
            except Exception as e:
                print(f"{indent}   ⚠️  Sidebar wait attempt {retry + 1} failed: {e}")
                if retry < 2:
                    await page.wait_for_timeout(2000 * (retry + 1))
                else:
                    # Last attempt: try to reload page
                    try:
                        print(f"{indent}   🔄 Reloading page as last resort...")
                        await page.reload(wait_until="domcontentloaded")
                        await page.wait_for_timeout(3000)
                        await page.wait_for_selector('#x-refine__group__0', timeout=15000)
                        sidebar_ready = True
                        print(f"{indent}   ✅ Sidebar ready after reload")
                    except Exception as reload_error:
                        print(f"{indent}   ❌ Failed to load sidebar after reload: {reload_error}")
        
        if not sidebar_ready:
            print(f"{indent}   ⚠️  Sidebar not ready, continuing anyway (may cause issues)...")
            await page.wait_for_timeout(3000)  # Give it extra time
        
        # Find the selected category span in sidebar
        print(f"{indent}🔍 Looking for selected category span: '{parent_category_name}'...")
        selected_span = page.locator(f'#x-refine__group__0 span:has-text("{parent_category_name}")').first
        
        if await selected_span.count() == 0:
            print(f"{indent}⚠️  Selected category span not found by text, trying data-state...")
            selected_item = page.locator('#x-refine__group__0 li[data-state*="selected"]').first
            if await selected_item.count() > 0:
                selected_span = selected_item.locator('span').first
                print(f"{indent}✅ Found by data-state")
            else:
                print(f"{indent}❌ Cannot find selected category, returning empty structure")
                return {
                    'depth': str(depth),
                    'category_name': parent_category_name,
                    'category_id': parent_category_id,
                    'categories': [],
                    'items': None,
                    'specs': []
                }
        else:
            print(f"{indent}✅ Found selected category span")
        
        # Get parent li of selected span
        selected_li = selected_span.locator('xpath=ancestor::li[1]')
        
        # Find next ul sibling (subcategories) - check nested first, then following sibling
        print(f"{indent}🔍 Looking for subcategories ul...")
        nested_ul = selected_li.locator('ul.srp-refine__category__list').first
        next_ul = None
        
        if await nested_ul.count() > 0:
            next_ul = nested_ul
            print(f"{indent}✅ Found nested ul inside li")
        else:
            following_ul = selected_li.locator('xpath=following-sibling::ul[@class="srp-refine__category__list"]').first
            if await following_ul.count() > 0:
                next_ul = following_ul
                print(f"{indent}✅ Found following sibling ul")
        
        if next_ul is None or await next_ul.count() == 0:
            # Leaf category - no subcategories
            print(f"{indent}🍃 LEAF CATEGORY: No subcategories found for '{parent_category_name}'")
            
            # Debug mode: stop after first leaf category
            if Config.DEBUG_STOP_AFTER_FIRST_LEAF and self._leaf_category_collected:
                print(f"{indent}🛑 DEBUG MODE: Already collected from first leaf category, stopping traversal")
                return {
                    'depth': str(depth),
                    'category_name': parent_category_name,
                    'category_id': parent_category_id,
                    'categories': [],
                    'items': None,
                    'specs': [],
                    'debug_stopped': True
                }
            
            # Collect items (with type support if needed)
            items, specs = await self._collect_items_with_types_and_specs(page, query, listing_type, depth, collected_ids)
            
            # Mark that we've collected from a leaf category
            if Config.DEBUG_STOP_AFTER_FIRST_LEAF:
                self._leaf_category_collected = True
                print(f"{indent}✅ DEBUG MODE: Collected from first leaf category '{parent_category_name}', will stop on next leaf")
            
            return {
                'depth': str(depth),
                'category_name': parent_category_name,
                'category_id': parent_category_id,
                'categories': [],
                'items': items,
                'specs': specs
            }
        
        print(f"{indent}✅ Found subcategories ul, extracting li elements...")
        
        # Extract all li elements from the ul
        category_lis = await next_ul.locator('li.srp-refine__category__item').all()
        print(f"{indent}📋 Found {len(category_lis)} potential subcategory li elements")
        
        categories = []
        visited_ids = set()
        
        for li_idx, li in enumerate(category_lis, 1):
            try:
                li_text = await li.text_content()
                li_text = li_text.strip() if li_text else ''
                
                # Skip if contains "More" or "Fewer"
                if li_text and any(word in li_text.lower() for word in ['more', 'fewer']):
                    print(f"{indent}   ⏭️  Skipping li {li_idx}: contains More/Fewer - '{li_text[:50]}'")
                    continue
                
                # Skip breadcrumbs
                class_attr = await li.get_attribute('class') or ''
                if 'breadcrumb' in class_attr:
                    print(f"{indent}   ⏭️  Skipping li {li_idx}: breadcrumb")
                    continue
                
                # Skip buttons
                if await li.locator('button').count() > 0:
                    print(f"{indent}   ⏭️  Skipping li {li_idx}: contains button")
                    continue
                
                # Get link
                link = li.locator('a[href*="/sch/"]').first
                if await link.count() == 0:
                    print(f"{indent}   ⏭️  Skipping li {li_idx}: no link found")
                    continue
                
                href = await link.get_attribute('href')
                if not href:
                    print(f"{indent}   ⏭️  Skipping li {li_idx}: no href")
                    continue
                
                # Extract category name from span
                span = link.locator('span').first
                if await span.count() == 0:
                    print(f"{indent}   ⏭️  Skipping li {li_idx}: no span in link")
                    continue
                
                cat_name = await span.text_content()
                cat_name = cat_name.strip() if cat_name else ''
                
                if not cat_name or cat_name.lower() == 'all':
                    print(f"{indent}   ⏭️  Skipping li {li_idx}: invalid name '{cat_name}'")
                    continue
                
                # Extract category ID
                cat_id_match = re.search(r'/sch/(\d+)/', href)
                if not cat_id_match:
                    print(f"{indent}   ⏭️  Skipping li {li_idx}: no category ID in href")
                    continue
                
                cat_id = cat_id_match.group(1)
                
                if cat_id in visited_ids:
                    print(f"{indent}   ⏭️  Skipping li {li_idx}: already visited ID {cat_id}")
                    continue
                
                visited_ids.add(cat_id)
                
                categories.append({
                    'id': cat_id,
                    'name': cat_name,
                    'href': href,
                    'link': link
                })
                
                print(f"{indent}   ✅ Extracted category {len(categories)}: '{cat_name}' (ID: {cat_id})")
                
            except Exception as e:
                print(f"{indent}   ⚠️  Error extracting li {li_idx}: {e}")
                continue
        
        print(f"{indent}📊 Total valid subcategories extracted: {len(categories)}")
        
        # Build category structure (items is None for non-leaf)
        category_data = {
            'depth': str(depth),
            'category_name': parent_category_name,
            'category_id': parent_category_id,
            'categories': [],
            'items': None,
            'specs': []
        }
        
        if len(categories) == 0:
            print(f"{indent}⚠️  No subcategories found, treating as leaf")
            # Treat as leaf if no subcategories
            items, specs = await self._collect_items_with_types_and_specs(page, query, listing_type, depth)
            category_data['items'] = items
            category_data['specs'] = specs
            return category_data
        
        # Process each subcategory
        for cat_idx, cat_info in enumerate(categories, 1):
            # Debug mode: stop if already collected from first leaf
            if Config.DEBUG_STOP_AFTER_FIRST_LEAF and self._leaf_category_collected:
                print(f"{indent}🛑 DEBUG MODE: Already collected from first leaf category, stopping sibling processing")
                break
            
            cat_id = cat_info['id']
            cat_name = cat_info['name']
            
            # Track category start time
            cat_start_time = time.time()
            
            # Calculate elapsed time and ETA
            if hasattr(self, '_scrape_start_time') and self._scrape_start_time:
                elapsed = cat_start_time - self._scrape_start_time
                if hasattr(self, '_category_times') and len(self._category_times) > 0:
                    avg_time_per_cat = sum(self._category_times) / len(self._category_times)
                    remaining_cats = len(categories) - cat_idx + 1  # +1 for current category
                    eta_seconds = avg_time_per_cat * remaining_cats
                    eta_str = self._format_time(eta_seconds)
                else:
                    eta_str = "calculating..."
                
                elapsed_str = self._format_time(elapsed)
                progress_pct = (cat_idx - 1) / len(categories) * 100 if len(categories) > 0 else 0
                
                print(f"{indent}{'─'*50}")
                print(f"{indent}[{cat_idx}/{len(categories)}] 📂 Processing subcategory: '{cat_name}' (ID: {cat_id})")
                print(f"{indent}   ⏱️  Elapsed: {elapsed_str} | ETA: {eta_str} | Progress: {progress_pct:.1f}%")
                print(f"{indent}{'─'*50}")
            else:
                print(f"{indent}{'─'*50}")
                print(f"{indent}[{cat_idx}/{len(categories)}] 📂 Processing subcategory: '{cat_name}' (ID: {cat_id})")
                print(f"{indent}{'─'*50}")
            
            try:
                # If not first category, go back to parent first to see all siblings
                if cat_idx > 1:
                    print(f"{indent}   ⬆️  Returning to parent to access sibling {cat_idx}...")
                    parent_link_in_sidebar = page.locator(f'#x-refine__group__0 a[href*="/sch/{parent_category_id}/"]').first
                    if await parent_link_in_sidebar.count() > 0:
                        await parent_link_in_sidebar.click()
                        await page.wait_for_load_state("domcontentloaded")
                        await page.wait_for_timeout(2000)
                        print(f"{indent}   ✅ Returned to parent")
                    
                    # Re-extract categories to get fresh link - wait for sidebar with retries
                    sidebar_ready = False
                    for retry in range(3):
                        try:
                            print(f"{indent}   🔍 Waiting for sidebar after returning to parent (attempt {retry + 1}/3)...")
                            await page.wait_for_selector('#x-refine__group__0', timeout=15000, state='attached')
                            sidebar = page.locator('#x-refine__group__0').first
                            if await sidebar.count() > 0:
                                await page.wait_for_timeout(2000)  # Give it time to render
                                sidebar_ready = True
                                print(f"{indent}   ✅ Sidebar ready")
                                break
                        except Exception as e:
                            print(f"{indent}   ⚠️  Sidebar wait attempt {retry + 1} failed: {e}")
                            if retry < 2:
                                await page.wait_for_timeout(2000 * (retry + 1))
                            else:
                                # Last attempt: try reload
                                try:
                                    print(f"{indent}   🔄 Reloading page as last resort...")
                                    await page.reload(wait_until="domcontentloaded")
                                    await page.wait_for_timeout(3000)
                                    await page.wait_for_selector('#x-refine__group__0', timeout=15000)
                                    sidebar_ready = True
                                    print(f"{indent}   ✅ Sidebar ready after reload")
                                except Exception as reload_error:
                                    print(f"{indent}   ❌ Failed to load sidebar after reload: {reload_error}")
                    
                    if not sidebar_ready:
                        print(f"{indent}   ⚠️  Sidebar not ready, continuing anyway...")
                        await page.wait_for_timeout(3000)  # Give extra time
                    
                    # Expand "Show More" button if it exists
                    print(f"{indent}   🔍 Checking for 'Show More' button...")
                    
                    # Try to find Show More button within the parent category's ul
                    selected_span = page.locator(f'#x-refine__group__0 span:has-text("{parent_category_name}")').first
                    show_more_found = False
                    
                    if await selected_span.count() > 0:
                        selected_li = selected_span.locator('xpath=ancestor::li[1]')
                        nested_ul = selected_li.locator('ul.srp-refine__category__list').first
                        if await nested_ul.count() == 0:
                            nested_ul = selected_li.locator('xpath=following-sibling::ul[@class="srp-refine__category__list"]').first
                        
                        if await nested_ul.count() > 0:
                            # Look for Show More button in the same ul
                            show_more_btn = nested_ul.locator('button:has-text("Show More"), button:has-text("More")').first
                            if await show_more_btn.count() > 0:
                                try:
                                    is_visible = await show_more_btn.is_visible()
                                    if is_visible:
                                        print(f"{indent}   📂 Expanding 'Show More' to reveal all categories...")
                                        await show_more_btn.scroll_into_view_if_needed()
                                        await show_more_btn.click()
                                        await page.wait_for_timeout(1000)
                                        print(f"{indent}   ✅ Expanded 'Show More'")
                                        show_more_found = True
                                except:
                                    pass
                    
                    # Also try general Show More button
                    if not show_more_found:
                        try:
                            general_show_more = page.locator('#x-refine__group__0 button:has-text("Show More"), #x-refine__group__0 button[aria-label*="Show more"]').first
                            if await general_show_more.count() > 0:
                                is_visible = await general_show_more.is_visible()
                                if is_visible:
                                    print(f"{indent}   📂 Expanding 'Show More' to reveal all categories...")
                                    await general_show_more.scroll_into_view_if_needed()
                                    await general_show_more.click()
                                    await page.wait_for_timeout(1000)
                                    print(f"{indent}   ✅ Expanded 'Show More'")
                        except:
                            pass
                    
                    # Re-extract the link after potentially expanding Show More
                    selected_span = page.locator(f'#x-refine__group__0 span:has-text("{parent_category_name}")').first
                    if await selected_span.count() > 0:
                        selected_li = selected_span.locator('xpath=ancestor::li[1]')
                        nested_ul = selected_li.locator('ul.srp-refine__category__list').first
                        if await nested_ul.count() == 0:
                            nested_ul = selected_li.locator('xpath=following-sibling::ul[@class="srp-refine__category__list"]').first
                        
                        if await nested_ul.count() > 0:
                            current_cat_link = nested_ul.locator(f'a[href*="/sch/{cat_id}/"]').first
                            if await current_cat_link.count() > 0:
                                cat_info['link'] = current_cat_link
                
                # Wait for sidebar to be ready before trying to click
                try:
                    await page.wait_for_selector('#x-refine__group__0', timeout=5000)
                    await page.wait_for_timeout(1000)
                except:
                    pass  # Continue anyway
                
                # Try to verify link is still valid, if not use URL navigation directly
                link_valid = False
                try:
                    if await cat_info['link'].count() > 0:
                        link_valid = True
                except:
                    pass
                
                # Click the category link with multiple strategies
                print(f"{indent}   🖱️  Clicking category link...")
                
                # If link is stale or invalid, go straight to URL navigation
                if not link_valid:
                    print(f"{indent}   ⚠️  Link is stale, using URL navigation...")
                    clicked = False
                else:
                    clicked = False
                    # Strategy 1: Try normal click with scroll into view
                    try:
                        await cat_info['link'].scroll_into_view_if_needed(timeout=5000)
                        await page.wait_for_timeout(500)
                        await cat_info['link'].click(timeout=10000)
                        await page.wait_for_load_state("domcontentloaded")
                        await page.wait_for_timeout(2000)
                        print(f"{indent}   ✅ Clicked category: '{cat_name}'")
                        clicked = True
                    except Exception as e:
                        print(f"{indent}   ⚠️  Normal click failed: {e}, trying force click...")
                        
                        # Strategy 2: Try force click
                        try:
                            await cat_info['link'].click(force=True, timeout=10000)
                            await page.wait_for_load_state("domcontentloaded")
                            await page.wait_for_timeout(2000)
                            print(f"{indent}   ✅ Force-clicked category: '{cat_name}'")
                            clicked = True
                        except Exception as e2:
                            print(f"{indent}   ⚠️  Force click failed: {e2}, trying JavaScript click...")
                            
                            # Strategy 3: Try JavaScript click
                            try:
                                await cat_info['link'].evaluate('element => element.click()', timeout=10000)
                                await page.wait_for_load_state("domcontentloaded")
                                await page.wait_for_timeout(2000)
                                print(f"{indent}   ✅ JavaScript-clicked category: '{cat_name}'")
                                clicked = True
                            except Exception as e3:
                                print(f"{indent}   ⚠️  JavaScript click failed: {e3}, will use URL navigation...")
                
                # Strategy 4: URL fallback - build URL directly from category_id
                if not clicked:
                    try:
                        # Use category_id to build URL directly (don't rely on stale locator)
                        current_url = page.url
                        
                        # Extract base query params from current URL
                        parsed = urlparse(current_url)
                        query_params = parse_qs(parsed.query)
                        
                        # Build new URL with category ID
                        base_url = f"https://www.ebay.com/sch/{cat_id}/i.html"
                        
                        # Preserve important query params
                        new_params = {
                            '_nkw': query_params.get('_nkw', [query])[0] if query_params.get('_nkw') else query,
                            '_from': query_params.get('_from', ['R40'])[0],
                            '_ipg': query_params.get('_ipg', ['240'])[0]
                        }
                        
                        # Preserve sold/complete filters if present
                        if 'LH_Sold' in query_params:
                            new_params['LH_Sold'] = query_params['LH_Sold'][0]
                        if 'LH_Complete' in query_params:
                            new_params['LH_Complete'] = query_params['LH_Complete'][0]
                        if 'LH_ItemCondition' in query_params:
                            new_params['LH_ItemCondition'] = query_params['LH_ItemCondition'][0]
                        
                        url = f"{base_url}?{urlencode(new_params)}"
                        
                        print(f"{indent}   🌐 Navigating to URL (built from category_id): {url}")
                        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                        await page.wait_for_timeout(3000)  # Extra wait for page to settle
                        
                        # Try networkidle but don't fail if it times out (especially when running concurrent browsers)
                        try:
                            await page.wait_for_load_state("networkidle", timeout=5000)
                        except:
                            # networkidle timeout is okay, page is loaded enough
                            pass
                        
                        # Wait for sidebar to be ready
                        print(f"{indent}   🔍 Waiting for sidebar after URL navigation...")
                        try:
                            await page.wait_for_selector('#x-refine__group__0', timeout=15000, state='attached')
                            await page.wait_for_timeout(2000)
                        except:
                            print(f"{indent}   ⚠️  Sidebar wait timeout, continuing anyway...")
                            await page.wait_for_timeout(3000)
                        
                        # Reapply all filters after URL navigation
                        print(f"{indent}   🔄 Reapplying filters after URL navigation...")
                        try:
                            await self._set_items_per_page(page, 240)
                            await page.wait_for_timeout(2000)
                            
                            print(f"{indent}   ✅ Filters reapplied")
                        except Exception as filter_error:
                            print(f"{indent}   ⚠️  Error reapplying filters: {filter_error}, continuing anyway...")
                        
                        print(f"{indent}   ✅ Navigated to category: '{cat_name}'")
                    except Exception as e4:
                        print(f"{indent}   ❌ All navigation strategies failed for '{cat_name}': {e4}")
                        # Don't raise - skip this category and continue
                        print(f"{indent}   ⏭️  Skipping category '{cat_name}' due to navigation failure")
                        raise
                
                # Recursively traverse this category
                print(f"{indent}   🔄 Recursing into subcategory '{cat_name}'...")
                sub_result = await self._traverse_category_tree_new(
                    page, query, listing_type, depth + 1, cat_id, cat_name, cat_info['link'], collected_ids
                )
                
                category_data['categories'].append(sub_result)
                
                # Track category completion time
                cat_end_time = time.time()
                cat_duration = cat_end_time - cat_start_time
                if hasattr(self, '_category_times'):
                    self._category_times.append(cat_duration)
                
                cat_duration_str = self._format_time(cat_duration)
                print(f"{indent}   ✅ Completed subcategory '{cat_name}' (took {cat_duration_str})")
                
                # Small delay
                await asyncio.sleep(random.uniform(1, 2))
                
            except Exception as e:
                # Track error category time too
                cat_end_time = time.time()
                cat_duration = cat_end_time - cat_start_time
                if hasattr(self, '_category_times'):
                    self._category_times.append(cat_duration)
                
                cat_duration_str = self._format_time(cat_duration)
                print(f"{indent}   ⚠️  Error processing '{cat_name}' (took {cat_duration_str}): {e}")
                import traceback
                print(f"{indent}   {traceback.format_exc()}")
                await self._take_screenshot(page, f"depth_{depth}_cat_{cat_idx}_error", cat_name[:20])
                
                # Add error category
                category_data['categories'].append({
                    'depth': str(depth + 1),
                    'category_name': cat_name,
                    'category_id': cat_id,
                    'categories': [],
                    'items': None,
                    'specs': [],
                    'error': str(e)
                })
                continue
        
        # After processing all subcategories, backtrack to parent if not at root
        if depth > 0 and parent_link:
            print(f"{indent}⬆️  Backtracking to parent category '{parent_category_name}'...")
            try:
                # Find parent link in sidebar
                parent_link_in_sidebar = page.locator(f'#x-refine__group__0 a[href*="/sch/{parent_category_id}/"]').first
                if await parent_link_in_sidebar.count() > 0:
                    await parent_link_in_sidebar.click()
                    await page.wait_for_load_state("domcontentloaded")
                    await page.wait_for_timeout(2000)
                    print(f"{indent}   ✅ Backtracked to parent")
                    await self._take_screenshot(page, f"depth_{depth}_backtracked", parent_category_name[:30])
                else:
                    print(f"{indent}   ⚠️  Parent link not found in sidebar, trying breadcrumb...")
                    breadcrumb = page.locator(f'#x-refine__group__0 li.srp-refine__category__item--breadcrumb-root a[href*="/sch/{parent_category_id}/"]').first
                    if await breadcrumb.count() > 0:
                        await breadcrumb.click()
                        await page.wait_for_load_state("domcontentloaded")
                        await page.wait_for_timeout(2000)
                        print(f"{indent}   ✅ Backtracked via breadcrumb")
            except Exception as e:
                print(f"{indent}   ⚠️  Error backtracking: {e}")
        
        print(f"{indent}✅ Completed traversal for '{parent_category_name}' at depth {depth}")
        print(f"{indent}{'='*60}")
        
        return category_data
    
    async def _collect_items_with_types_and_specs(self, page, query: str, listing_type: str, depth: int, collected_ids: set = None) -> Tuple[Optional[Dict], List[Dict]]:
        """Collect items, handle types if multiple types exist, and collect all sidebar specs
        
        Args:
            page: Playwright page object
            query: Search query
            listing_type: 'active' or 'sold'
            depth: Category depth
            collected_ids: Set of already collected item IDs for deduplication (will be updated)
        """
        if collected_ids is None:
            collected_ids = set()
        
        indent = "  " * depth
        print(f"{indent}🔍 COLLECTING ITEMS WITH TYPES AND SPECS")
        print(f"{indent}{'─'*50}")
        
        await self._set_items_per_page(page, 240)
        await page.wait_for_timeout(1000)
        
        total_items = await self._get_total_count(page)
        print(f"{indent}   📊 Total items found: {total_items:,}")
        
        if total_items == 0:
            print(f"{indent}   ⚠️  No items found, returning empty")
            return None, []
        
        # Check for Type filter in sidebar - must be exactly "Type", not "Placement on Vehicle" or similar
        print(f"{indent}   🔍 Checking for Type filter...")
        type_section = None
        
        # Find h3 elements and check their exact text
        all_h3s = await page.locator('ul.x-refine__left__nav h3').all()
        for h3 in all_h3s:
            h3_text = await h3.text_content()
            h3_text = h3_text.strip() if h3_text else ''
            # Match exactly "Type", not "Placement on Vehicle" or other similar names
            if h3_text == 'Type':
                type_section = h3
                break
        
        # Collect all items directly without filtering by type
        # Types will be collected as specs from the sidebar
        print(f"{indent}   📦 Collecting all items from page (types will be collected as specs)...")
        all_items = await self._scrape_category_pages(page, query, listing_type, collected_ids)
        items_result = all_items if all_items else None
        
        # Collect sidebar specs
        print(f"{indent}   📊 Collecting sidebar filter specs...")
        specs = await self._collect_sidebar_specs(page, depth)
        print(f"{indent}   ✅ Collected {len(specs)} specs")
        
        print(f"{indent}{'─'*50}")
        print(f"{indent}✅ COMPLETED COLLECTING ITEMS")
        
        return items_result, specs
    
    async def _collect_sidebar_specs(self, page, depth: int) -> List[Dict]:
        """Collect all filter specifications from sidebar"""
        indent = "  " * depth
        specs = []
        
        print(f"{indent}     🔍 COLLECTING SIDEBAR SPECS")
        
        try:
            filter_h3s = await page.locator('ul.x-refine__left__nav h3').all()
            filter_names = ['Type', 'Manufacturer Warranty', 'Items Included', 'Performance Part', 
                          'Material', 'Brand', 'Universal Fitment', 'Country of Origin', 'Vintage Part', 'Brand Type', 'Placement on Vehicle', 
                          'Terminal Type', 'Condition', 'Buying format']
            
            print(f"{indent}     📋 Found {len(filter_h3s)} h3 elements in sidebar")
            
            for h3_idx, h3 in enumerate(filter_h3s, 1):
                try:
                    h3_text = await h3.text_content()
                    h3_text = h3_text.strip() if h3_text else ''
                    
                    print(f"{indent}     🔍 Checking h3 {h3_idx}: '{h3_text}'...")
                    
                    if h3_text not in filter_names:
                        print(f"{indent}     ⏭️  Skipping '{h3_text}' (not in filter list)")
                        continue
                    
                    print(f"{indent}     ✅ Processing filter: '{h3_text}'")
                    
                    # Find corresponding group
                    h3_id = await h3.get_attribute('id')
                    group_id = None
                    
                    if h3_id:
                        print(f"{indent}     🔍 h3 has id: '{h3_id}'")
                        # Extract number from id like "x-refine__group__7"
                        match = re.search(r'group__(\d+)', h3_id)
                        if match:
                            group_num = match.group(1)
                            group_id = f'#x-refine__group_{group_num}__0'
                            print(f"{indent}     ✅ Constructed group_id: '{group_id}'")
                    else:
                        print(f"{indent}     🔍 h3 has no id, trying following sibling...")
                        # Try to find by following sibling
                        next_div = h3.locator('xpath=following-sibling::div[contains(@id, "x-refine__group")]').first
                        if await next_div.count() > 0:
                            div_id = await next_div.get_attribute('id')
                            group_id = f"#{div_id}"
                            print(f"{indent}     ✅ Found following sibling div: '{group_id}'")
                    
                    if not group_id:
                        print(f"{indent}     ⚠️  Could not find group_id for '{h3_text}'")
                        continue
                    
                    group = page.locator(group_id).first
                    if await group.count() == 0:
                        print(f"{indent}     ⚠️  Group '{group_id}' not found")
                        continue
                    
                    print(f"{indent}     ✅ Found group: '{group_id}'")
                    
                    # Extract all options
                    options = []
                    option_lis = await group.locator('ul > li').all()
                    print(f"{indent}     📋 Found {len(option_lis)} option li elements")
                    
                    for option_idx, option_li in enumerate(option_lis, 1):
                        try:
                            option_link = option_li.locator('a').first
                            if await option_link.count() == 0:
                                continue
                            
                            option_text = await option_link.text_content()
                            option_text = option_text.strip() if option_text else ''
                            
                            if not option_text:
                                continue
                            
                            # Parse: "ABS Accumulator(24) Items (24)" or "ABS Accumulator (24) Items (24)"
                            # Extract name (everything before first parenthesis)
                            name_match = re.match(r'^([^(]+)', option_text)
                            name = name_match.group(1).strip() if name_match else option_text
                            
                            # Extract amount (number in parentheses, prefer last one)
                            amount_matches = re.findall(r'\((\d+)\)', option_text)
                            amount = int(amount_matches[-1]) if amount_matches else 0
                            
                            options.append({'name': name, 'amount': amount})
                            
                        except Exception as e:
                            print(f"{indent}     ⚠️  Error extracting option {option_idx}: {e}")
                            continue
                    
                    if options:
                        total = sum(opt['amount'] for opt in options)
                        print(f"{indent}     📊 Total items for '{h3_text}': {total}")
                        
                        # Calculate percentages
                        for opt in options:
                            opt['percent'] = round((opt['amount'] / total * 100) if total > 0 else 0, 2)
                        
                        specs.append({
                            'name': h3_text,
                            'values': options
                        })
                        
                        print(f"{indent}     ✅ Collected spec '{h3_text}': {len(options)} values")
                    else:
                        print(f"{indent}     ⚠️  No options extracted for '{h3_text}'")
                        
                except Exception as e:
                    print(f"{indent}     ⚠️  Error collecting spec '{h3_text}': {e}")
                    import traceback
                    print(f"{indent}     {traceback.format_exc()}")
                    continue
                    
        except Exception as e:
            print(f"{indent}     ⚠️  Error in sidebar specs collection: {e}")
            import traceback
            print(f"{indent}     {traceback.format_exc()}")
        
        print(f"{indent}     ✅ Completed collecting sidebar specs: {len(specs)} specs")
        return specs
    
    async def _extract_categories_from_sidebar(self, page, exclude_ids: set = None) -> List[Dict]:
        """Extract categories from the sidebar (#x-refine__group__0)
        
        Args:
            page: Playwright page object
            exclude_ids: Set of category IDs to exclude (already visited or current)
        """
        categories = []
        exclude_ids = exclude_ids or set()
        
        try:
            # Find all category items in the sidebar (not breadcrumbs, not "All" link, not "Show More" buttons)
            category_items = await page.locator('#x-refine__group__0 li.srp-refine__category__item').all()
            
            for item in category_items:
                try:
                    # Skip the currently selected category (data-state="selected")
                    data_state = await item.get_attribute('data-state') or ''
                    if 'selected' in data_state:
                        continue
                    
                    # Get class attribute to check for breadcrumb
                    class_attr = await item.get_attribute('class') or ''
                    is_breadcrumb = 'breadcrumb' in class_attr
                    
                    # Skip breadcrumbs (they navigate up the hierarchy)
                    if is_breadcrumb:
                        continue
                    
                    # Skip items with "Show More"/"Show Less" buttons (not actual categories)
                    if await item.locator('button.fake-link').count() > 0:
                        continue
                    
                    # Get category link
                    link_locator = item.locator('a[href*="/sch/"]').first
                    if await link_locator.count() == 0:
                        continue
                    
                    href = await link_locator.get_attribute('href')
                    if not href:
                        continue
                    
                    # Skip "All" category (it's just a reset link)
                    name_elem = link_locator.locator('span').first
                    name = await name_elem.text_content() if await name_elem.count() > 0 else ''
                    name = name.strip() if name else ''
                    
                    if name.lower() == 'all' or not name:
                        continue
                    
                    # Extract category ID from URL (e.g., /sch/33637/i.html)
                    cat_id_match = re.search(r'/sch/(\d+)/', href)
                    if not cat_id_match:
                        continue
                    
                    cat_id = cat_id_match.group(1)
                    
                    # Skip if already visited (prevent infinite loops)
                    if cat_id in exclude_ids:
                        continue
                    
                    # Check if this item has nested subcategories (has nested ul inside the item)
                    # Look for subcategories within the same list item
                    nested_list = item.locator('ul.srp-refine__category__list')
                    has_subcategories = await nested_list.count() > 0
                    
                    # Normalize URL
                    full_url = href if href.startswith('http') else f"https://www.ebay.com{href}"
                    
                    categories.append({
                        'id': cat_id,
                        'name': name,
                        'url': full_url,
                        'is_breadcrumb': False,  # We've already filtered these
                        'has_subcategories': has_subcategories
                    })
                    
                except Exception as e:
                    continue
            
        except Exception as e:
            print(f"        ⚠️  Error extracting categories: {e}")
        
        return categories
    
    async def _scrape_category_pages(self, page, query: str, listing_type: str, collected_ids: set = None) -> List[Dict]:
        """Scrape all pages of listings from current category
        
        Args:
            page: Playwright page object
            query: Search query
            listing_type: 'active' or 'sold'
            collected_ids: Set of already collected item IDs for deduplication (will be updated)
        """
        if collected_ids is None:
            collected_ids = set()
        
        all_listings = []
        
        # Ensure items per page is set (important after clicking type filters)
        print(f"        🔧 Ensuring items per page is set to {Config.SCRAPER_ITEMS_PER_PAGE}...")
        await self._set_items_per_page(page, Config.SCRAPER_ITEMS_PER_PAGE)
        await page.wait_for_timeout(2000)
        
        total_items = await self._get_total_count(page)
        print(f"        📊 Total items available: {total_items:,}")
        
        if total_items == 0:
            return []
        
        max_items = min(total_items, Config.SCRAPER_MAX_TOTAL_ITEMS)
        print(f"        📊 Max items to collect (limit): {max_items:,}")
        
        pages_needed = math.ceil(max_items / Config.SCRAPER_ITEMS_PER_PAGE)
        print(f"        📊 Pages needed (before max limit): {pages_needed} (max_items={max_items}, items_per_page={Config.SCRAPER_ITEMS_PER_PAGE})")
        
        pages_needed = min(pages_needed, Config.SCRAPER_MAX_PAGES)
        print(f"        📊 Pages to scrape (after max limit {Config.SCRAPER_MAX_PAGES}): {pages_needed}")
        
        duplicates_skipped = 0
        
        for page_num in range(1, pages_needed + 1):
            try:
                print(f"        📄 Scraping page {page_num}/{pages_needed}...")
                
                await page.wait_for_selector("#srp-river-results", timeout=15000)
                await page.wait_for_timeout(2000)
                
                # Calculate how many items we still need
                remaining_items = max_items - len(all_listings)
                # For first page, don't limit if count is close (eBay counts can be approximate)
                # Only limit if we have way more than needed (likely sponsored/related items)
                max_items_for_page = None
                if page_num == 1 and total_items < Config.SCRAPER_ITEMS_PER_PAGE:
                    # If count is small, limit extraction to avoid processing too many false positives
                    # But add some buffer (20%) in case count is slightly off
                    max_items_for_page = int(total_items * 1.2)
                    print(f"        📊 Limiting page 1 extraction to {max_items_for_page} items (total={total_items})")
                
                page_listings = await self._extract_listings_from_page(page, max_items=max_items_for_page)
                
                if page_listings:
                    
                    # Deduplicate: only add items with unique item_id
                    new_items = []
                    for listing in page_listings:
                        item_id = listing.get('item_id')
                        if item_id and item_id not in collected_ids:
                            listing['query'] = query
                            listing['status'] = listing_type
                            collected_ids.add(item_id)
                            new_items.append(listing)
                        elif item_id:
                            duplicates_skipped += 1
                    
                    all_listings.extend(new_items)
                    print(f"        ✅ Page {page_num}: Collected {len(new_items)} new items, skipped {len(page_listings) - len(new_items)} duplicates (Total so far: {len(all_listings)}, Total skipped: {duplicates_skipped})")
                else:
                    print(f"        ⚠️  Page {page_num}: No listings found")
                
                # Navigate to next page if not last
                if page_num < pages_needed:
                    print(f"        ➡️  Navigating to page {page_num + 1}...")
                    if not await self._go_to_next_page(page):
                        print(f"        ⚠️  Could not navigate to page {page_num + 1}, stopping")
                        break
                    await asyncio.sleep(random.uniform(1, 2))
                
            except Exception as e:
                print(f"        ⚠️  Error on page {page_num}: {e}")
                # Screenshot: Error on page
                await self._take_screenshot(page, f"scrape_page_{page_num}_error", "error")
                break
        
        return all_listings
    
    async def _apply_sold_filter(self, page):
        """Apply sold listings filter"""
        try:
            print(f"        🔍 Looking for sold items filter...")
            sold_selectors = [
                'input[aria-label="Sold Items"]',
                'input[name="LH_Sold"]',
                '#x-refine__group__7 li[name="LH_Sold"] a',
                'a:has-text("Sold Items")'
            ]

            for idx, selector in enumerate(sold_selectors, 1):
                try:
                    print(f"        Trying selector {idx}/{len(sold_selectors)}: {selector[:50]}...")
                    if await page.locator(selector).count() > 0:
                        print(f"        ✅ Found sold filter with selector {idx}, clicking...")
                        await page.locator(selector).first.click()
                        await page.wait_for_load_state("domcontentloaded")
                        await page.wait_for_timeout(3000)
                        print(f"        ✅ Sold filter applied successfully")
                        return
                except Exception as e:
                    print(f"        ⚠️  Selector {idx} failed: {e}")
                    continue

            print(f"        ⚠️  No sold filter selector worked")
        except Exception as e:
            print(f"        ❌ Error applying sold filter: {e}")
    
    async def _apply_used_condition_filter(self, page):
        """Apply used condition filter"""
        try:
            print(f"        🔍 Looking for 'used' condition filter...")
            used_selectors = [
                'input[aria-label*="Used"]',
                'input[name="LH_ItemCondition"][value="3000"]'
            ]
            for idx, selector in enumerate(used_selectors, 1):
                print(f"        Trying used selector {idx}/{len(used_selectors)}...")
                if await page.locator(selector).count() > 0:
                    print(f"        ✅ Found used filter, clicking...")
                    await page.click(selector)
                    await page.wait_for_load_state("domcontentloaded")
                    await page.wait_for_timeout(2000)
                    print(f"        ✅ Used filter applied")
                    break
            else:
                print(f"        ⚠️  No used filter found")
        except Exception as e:
            print(f"        ❌ Error applying used filter: {e}")

    async def _choose_parts_category(self, page):
        """Choose Parts & Accessories category (6000) and then Parts subcategory (6028)"""
        try:
            print(f"        🔍 Selecting Parts & Accessories category...")

            # Step 1: Try to find and click direct link to category 6000
            category_selected = False

            # Method 1: Look for direct link to category 6000
            print(f"        Method 1: Looking for direct link to category 6000...")
            try:
                link_selector = 'a[href*="/sch/6000/"]'
                if await page.locator(link_selector).count() > 0:
                    print(f"        ✅ Found direct link to category 6000, clicking...")
                    await page.locator(link_selector).first.click()
                    await page.wait_for_load_state("domcontentloaded")
                    await page.wait_for_timeout(3000)
                    category_selected = True
                    print(f"        ✅ Category 6000 link clicked successfully")
                else:
                    print(f"        ⚠️  No direct link found")
            except Exception as e:
                print(f"        ⚠️  Direct link method failed: {e}")

            # Method 2: Try to select by text "eBay Motors"
            if not category_selected:
                print(f"        Method 2: Looking for 'eBay Motors' option by text...")
                category_selectors = [
                    '#gh-cat',
                    '.gh-search-categories',
                    'select[aria-label*="category"]'
                ]

                for idx, selector in enumerate(category_selectors, 1):
                    try:
                        print(f"        Trying selector {idx}/{len(category_selectors)}: {selector}")
                        if await page.locator(selector).count() > 0:
                            print(f"        ✅ Found dropdown, selecting 'eBay Motors' by text...")
                            # Try selecting by text
                            try:
                                await page.select_option(selector, label='eBay Motors')
                                category_selected = True
                                print(f"        ✅ 'eBay Motors' selected by text")
                                break
                            except Exception as e:
                                print(f"        ⚠️  Text selection failed: {e}")
                    except Exception as e:
                        print(f"        ⚠️  Selector {idx} failed: {e}")
                        continue

            # Method 3: Try to select by value 6000
            if not category_selected:
                print(f"        Method 3: Selecting option with value 6000...")
                category_selectors = [
                    '#gh-cat',
                    '.gh-search-categories',
                    'select[aria-label*="category"]'
                ]

                for idx, selector in enumerate(category_selectors, 1):
                    try:
                        print(f"        Trying selector {idx}/{len(category_selectors)}: {selector}")
                        if await page.locator(selector).count() > 0:
                            print(f"        ✅ Found dropdown, selecting value 6000...")
                            await page.select_option(selector, value='6000')
                            category_selected = True
                            print(f"        ✅ Category 6000 selected by value")
                            break
                    except Exception as e:
                        print(f"        ⚠️  Selector {idx} failed: {e}")
                        continue

            if not category_selected:
                print(f"        ⚠️  Could not select category 6000 using any method")
                return False

            # Step 2: Click search button to apply category filter
            print(f"        🔍 Looking for search button...")
            search_button_selectors = [
                '#gh-search-btn',
                'button[type="submit"]'
            ]

            button_clicked = False
            for idx, selector in enumerate(search_button_selectors, 1):
                try:
                    print(f"        Trying search button selector {idx}/{len(search_button_selectors)}")
                    if await page.locator(selector).count() > 0:
                        print(f"        ✅ Found search button, clicking...")
                        await page.click(selector)
                        await page.wait_for_load_state("domcontentloaded")
                        await page.wait_for_timeout(3000)
                        button_clicked = True
                        print(f"        ✅ Search button clicked, page loaded")
                        break
                except Exception as e:
                    print(f"        ⚠️  Button selector {idx} failed: {e}")
                    continue

            if not button_clicked:
                print(f"        ⚠️  Could not click search button")
                return False

            # Step 3: Find and click Parts subcategory (6028)
            print(f"        🔍 Looking for Parts subcategory (6028)...")

            # Try to find the category refinement section
            try:
                await page.wait_for_selector('#x-refine__group__0', timeout=5000)
                print(f"        ✅ Found category refinement section")
            except Exception as e:
                print(f"        ⚠️  Category refinement section not found: {e}")

            # Look for Parts subcategory link (6028)
            parts_selectors = [
                'a[href*="/sch/6028/"]',
                '#x-refine__group__0 li:has-text("Parts") a',
                'a[href*="6028"][href*="_nkw"]'
            ]

            parts_clicked = False
            for idx, selector in enumerate(parts_selectors, 1):
                try:
                    print(f"        Trying parts selector {idx}/{len(parts_selectors)}: {selector[:50]}...")
                    loc = page.locator(selector).first
                    if await loc.count() > 0:
                        print(f"        ✅ Found Parts (6028) link, clicking...")
                        try:
                            await loc.scroll_into_view_if_needed()
                        except Exception:
                            pass
                        try:
                            await loc.click()
                        except Exception as e:
                            print(f"        ⚠️  Normal click failed ({e}), trying force click...")
                            continue
                            # try:
                            #     await loc.click(force=True)
                            # except Exception as e2:
                            #     print(f"        ⚠️  Force click failed ({e2}), trying JS click...")
                            #     try:
                            #         await page.evaluate('(el) => el.click()', await loc.element_handle())
                            #     except Exception as e3:
                            #         print(f"        ⚠️  JS click failed ({e3})")
                            #         continue
                        await page.wait_for_load_state("domcontentloaded")
                        await page.wait_for_timeout(3000)
                        parts_clicked = True
                        print(f"        ✅ Parts category (6028) selected successfully")
                        return True
                except Exception as e:
                    print(f"        ⚠️  Parts selector {idx} failed: {e}")
                    continue

            if not parts_clicked:
                print(f"        ⚠️  Could not find/click Parts subcategory (6028) - trying direct URL fallback")
                try:
                    current_query = await page.locator('#gh-ac').input_value().catch(lambda _: '') if await page.locator('#gh-ac').count() else ''
                except Exception:
                    current_query = ''
                fallback_url = f"https://www.ebay.com/sch/6028/i.html?_nkw={quote(current_query or '')}"
                try:
                    await page.goto(fallback_url, wait_until="domcontentloaded")
                    await page.wait_for_timeout(3000)
                    print("        ✅ Navigated directly to Parts category via URL fallback")
                    return True
                except Exception as e:
                    print(f"        ❌ URL fallback failed: {e}")
                return False

            return True

        except Exception as e:
            print(f"        ❌ Error choosing parts category: {e}")
            import traceback
            print(f"        {traceback.format_exc()}")
            return False

    async def _set_items_per_page(self, page, items: int = 240):
        """Set items per page to maximum"""
        try:
            # Check if items per page is already set in URL
            current_url = page.url
            if f"_ipg={items}" in current_url:
                print(f"        ⏭️  Items per page already set to {items} in URL, skipping...")
                return
            
            print(f"        🔍 Setting items per page to {items}...")
            dropdown_selectors = [
                '.srp-ipp .fake-menu-button__button',
                'button[aria-controls="srp-ipp-menu-content"]'
            ]

            for idx, selector in enumerate(dropdown_selectors, 1):
                print(f"        Trying dropdown selector {idx}/{len(dropdown_selectors)}...")
                if await page.locator(selector).count() > 0:
                    print(f"        ✅ Found dropdown, clicking...")
                    await page.click(selector)
                    await page.wait_for_timeout(1000)

                    # Look for the option within the items-per-page menu, not any link with _ipg
                    option_selector = f'#srp-ipp-menu-content a[href*="_ipg={items}"]:not([class*="advanced"])'
                    print(f"        Looking for option: {items} items per page...")
                    if await page.locator(option_selector).count() > 0:
                        print(f"        ✅ Found {items} option, clicking...")
                        await page.click(option_selector)
                        await page.wait_for_load_state("domcontentloaded")
                        await page.wait_for_timeout(2000)
                        print(f"        ✅ Items per page set to {items}")
                        return
                    else:
                        # Try alternative selector without excluding advanced
                        alt_selector = f'.srp-ipp-menu a[href*="_ipg={items}"]'
                        if await page.locator(alt_selector).count() > 0:
                            print(f"        ✅ Found {items} option (alt selector), clicking...")
                            await page.click(alt_selector)
                            await page.wait_for_load_state("domcontentloaded")
                            await page.wait_for_timeout(2000)
                            print(f"        ✅ Items per page set to {items}")
                            return
                        else:
                            print(f"        ⚠️  {items} option not found")
                    break
            print(f"        ⚠️  Could not set items per page - trying URL parameter fallback")
            try:
                url = page.url
                if "_ipg=" in url:
                    base = re.sub(r"([?&])_ipg=\d+", f"\\1_ipg={items}", url)
                else:
                    sep = '&' if '?' in url else '?'
                    base = f"{url}{sep}_ipg={items}"
                await page.goto(base, wait_until="domcontentloaded")
                await page.wait_for_timeout(1500)
                print(f"        ✅ Items per page set to {items} via URL fallback")
            except Exception as e:
                print(f"        ❌ IPG URL fallback failed: {e}")
        except Exception as e:
            print(f"        ❌ Error setting items per page: {e}")
    
    async def _get_total_count(self, page) -> int:
        """Extract total number of items"""
        try:
            print(f"        🔍 Getting total item count...")
            count_selectors = [
                ".srp-controls__count span.BOLD:first-child",
                ".srp-controls__count .BOLD"
            ]

            for idx, selector in enumerate(count_selectors, 1):
                print(f"        Trying count selector {idx}/{len(count_selectors)}...")
                if await page.locator(selector).count() > 0:
                    count_text = await page.locator(selector).text_content()
                    print(f"        Found count text: '{count_text}'")
                    numbers = re.findall(r'[\d,]+', count_text)
                    if numbers:
                        total = int(re.sub(r'[^\d]', '', numbers[0]))
                        print(f"        ✅ Total count: {total:,}")
                        return total
            print(f"        ⚠️  Could not extract total count, returning 0")
            return 0
        except Exception as e:
            print(f"        ❌ Error getting total count: {e}")
            return 0
    
    async def _extract_listings_from_page(self, page, max_items: int = None) -> List[Dict]:
        """Extract all listings from current page with enhanced data
        
        Args:
            page: Playwright page object
            max_items: Maximum number of items to extract (None = extract all)
        """
        try:
            print(f"        🔍 Extracting listings from page...")
            # More specific selectors to avoid matching sponsored/related items
            li_selectors = [
                "#srp-river-results ul li.s-card",  # Primary selector
                ".s-card"  # Fallback
            ]
            
            listings_locator = None
            for idx, selector in enumerate(li_selectors, 1):
                print(f"        Trying listing selector {idx}/{len(li_selectors)}: {selector}")
                locator = page.locator(selector)
                count = await locator.count()
                print(f"        Found {count} elements with selector {idx}")
                if count > 0:
                    listings_locator = locator
                    break
            
            if not listings_locator:
                print(f"        ⚠️  No listings found with any selector")
                return []
            
            # Extract all items, filtering to only those with valid item links
            item_count = await listings_locator.count()
            print(f"        📋 Processing {item_count} listing blocks (filtering for valid listings)...")
            listings = []
            
            for idx in range(item_count):
                try:
                    # Stop if we've reached max_items
                    if max_items and len(listings) >= max_items:
                        print(f"        ⏹️  Reached max_items limit ({max_items}), stopping extraction")
                        break
                    
                    item_locator = listings_locator.nth(idx)
                    
                    # Pre-filter: only process items that have valid item links (avoid sponsored/related items)
                    item_link = item_locator.locator('a[href*="/itm/"]').first
                    if await item_link.count() == 0:
                        continue  # Skip items without valid item links
                    
                    block = await item_locator.inner_html()
                    listing = self._parse_listing_block(block)
                    
                    if listing and listing.get('item_id'):
                        listings.append(listing)
                        if len(listings) % 50 == 0:
                            print(f"        ✓ Processed {idx + 1}/{item_count} blocks, found {len(listings)} valid listings...")
                    elif not listing:
                        print(f"        ⚠️  Block {idx} parsed as None (skipped)")
                    elif not listing.get('item_id'):
                        print(f"        ⚠️  Block {idx} missing item_id (skipped)")
                except Exception as e:
                    print(f"        ⚠️  Error parsing block {idx}: {e}")
                    continue
            
            print(f"        ✅ Extracted {len(listings)} valid listings from {item_count} blocks")
            return listings
        except Exception as e:
            print(f"        ❌ Error extracting listings: {e}")
            return []
    
    def _parse_listing_block(self, block: str) -> Optional[Dict]:
        """Parse HTML block with enhanced data extraction"""
        try:
            # Title
            title_match = re.search(r's-card__title.*?<[^>]+>(.*?)</', block, re.S)
            title = re.sub(r"<.*?>", "", title_match.group(1)).strip() if title_match else None
            
            # Price
            price_match = re.search(r's-card__price.*?>(.*?)</span>', block, re.S)
            price_text = re.sub(r"<.*?>", "", price_match.group(1)).strip() if price_match else None
            
            price = 0.0
            if price_text:
                price_clean = re.sub(r'[^0-9.]', '', price_text)
                try:
                    price = float(price_clean)
                except:
                    pass
            
            # Item ID and URL
            item_id = None
            url = None
            url_match = re.search(r'href="([^"]*?/itm/[^"]*?)"', block)
            if url_match:
                url = url_match.group(1)
                if not url.startswith('http'):
                    url = 'https://www.ebay.com' + url
                id_match = re.search(r'/itm/(\d+)', url)
                if id_match:
                    item_id = id_match.group(1)
            
            # Image
            image_url = ""
            img_match = re.search(r'<img[^>]*src="([^"]+)"', block)
            if img_match:
                image_url = img_match.group(1)
            
            # Shipping cost
            shipping_cost = 0.0
            shipping_match = re.search(r'\+\$?([\d.,]+)\s+shipping', block, re.I)
            if shipping_match:
                try:
                    shipping_cost = float(re.sub(r'[^0-9.]', '', shipping_match.group(1)))
                except:
                    pass
            
            if re.search(r'free\s+shipping', block, re.I):
                shipping_cost = 0.0
            
            # Seller info - extract from ALL s-card__attribute-row divs
            seller = "Unknown"
            seller_feedback = ""
            
            # Find all div.s-card__attribute-row elements
            attr_rows = re.findall(r'<div[^>]*class="[^"]*s-card__attribute-row[^"]*"[^>]*>(.*?)</div>', block, re.S|re.I)
            
            for attr_row_html in attr_rows:
                # Extract all text from spans in this attribute row
                inner_html = attr_row_html
                # Remove HTML tags and get clean text
                inner_text = re.sub(r'<[^>]+>', ' ', inner_html)  # Replace tags with space
                inner_text = re.sub(r'\s+', ' ', inner_text).strip()  # Normalize whitespace
                
                # Pattern: "german-831  99.3% positive (5.8K)" or "username 100% positive (1K)"
                # Format: seller_username + rating% + positive/negative + (rating_amount)
                # Allow multiple spaces between components
                seller_match = re.match(r'^([a-zA-Z0-9\-_]+)\s+([\d.]+)%\s+(positive|negative)\s+\(([^)]+)\)', inner_text, re.I)
                if seller_match:
                    seller = seller_match.group(1).strip()
                    rating_pct = seller_match.group(2)
                    pos_neg = seller_match.group(3)
                    rating_amount = seller_match.group(4)
                    seller_feedback = f"{rating_pct}% {pos_neg} ({rating_amount})"
                    break
                
                # Alternative pattern: sometimes there's no percentage, just: "username positive (1K)"
                seller_match_alt = re.match(r'^([a-zA-Z0-9\-_]+)\s+(positive|negative)\s+\(([^)]+)\)', inner_text)
                if seller_match_alt and seller == "Unknown":
                    seller = seller_match_alt.group(1).strip()
                    pos_neg = seller_match_alt.group(2)
                    rating_amount = seller_match_alt.group(3)
                    seller_feedback = f"{pos_neg} ({rating_amount})"
                    break
                
                # Fallback: if text contains pattern like "username  99.3% positive (5.8K)" without exact match
                # Try to parse components separately
                if seller == "Unknown" and ('positive' in inner_text.lower() or 'negative' in inner_text.lower()):
                    # Split by whitespace
                    parts = inner_text.split()
                    if len(parts) >= 2:
                        # First part might be username
                        potential_username = parts[0]
                        # Check if it's not a number or price
                        if not potential_username.startswith('$') and not potential_username.replace('.', '').isdigit():
                            seller = potential_username
                            # Look for feedback pattern
                            feedback_parts = []
                            for i, part in enumerate(parts[1:], 1):
                                if '%' in part or 'positive' in part.lower() or 'negative' in part.lower() or '(' in part or ')' in part:
                                    feedback_parts = parts[i:]
                                    break
                            if feedback_parts:
                                seller_feedback = ' '.join(feedback_parts)
                            break
            
            # Fallback: Try other seller selectors
            if seller == "Unknown":
                # Try s-card__seller-info
                seller_match = re.search(r's-card__seller-info[^>]*>(.*?)</span>', block, re.S)
                if seller_match:
                    seller_text = re.sub(r"<.*?>", "", seller_match.group(1)).strip()
                    if seller_text and not seller_text.startswith('$'):
                        seller = seller_text or "Unknown"
                
                # Try looking for seller name pattern in other places
                if seller == "Unknown":
                    seller_patterns = [
                        r'data-testid="seller-name"[^>]*>(.*?)</',
                        r'seller[^>]*name[^>]*>(.*?)</',
                    ]
                    for pattern in seller_patterns:
                        match = re.search(pattern, block, re.S|re.I)
                        if match:
                            seller_text = re.sub(r"<.*?>", "", match.group(1)).strip()
                            if seller_text and not seller_text.startswith('$') and not seller_text.replace('.', '').isdigit():
                                seller = seller_text
                                break
            
            # Condition
            condition = "Used"
            condition_match = re.search(r'SECONDARY_INFO">([^<]+)</span>', block)
            if condition_match:
                condition = condition_match.group(1).strip()
            
            # Location
            location = ""
            location_match = re.search(r's-card__location.*?>(.*?)</span>', block, re.S)
            if location_match:
                location = re.sub(r"<.*?>", "", location_match.group(1)).strip()
            
            # Sold date
            sold_date = None
            date_match = re.search(r'Sold\s+([A-Z][a-z]+\s+\d{1,2})', block)
            if date_match:
                sold_date = date_match.group(1)
            
            # Watchers count
            watchers = 0
            watchers_match = re.search(r'(\d+)\s+watcher', block, re.I)
            if watchers_match:
                watchers = int(watchers_match.group(1))
            
            # Bids count
            bids = 0
            bids_match = re.search(r'(\d+)\s+bid', block, re.I)
            if bids_match:
                bids = int(bids_match.group(1))
            
            if not (title and item_id):
                return None
            
            return {
                'item_id': item_id,
                'title': title,
                'price': price,
                'url': url or f"https://www.ebay.com/itm/{item_id}",
                'image_url': image_url,
                'condition': condition,
                'shipping_cost': shipping_cost,
                'seller': seller,
                'seller_feedback': seller_feedback,
                'location': location,
                'sold_date': sold_date,
                'watchers': watchers,
                'bids': bids,
                'source': 'scraped'
            }
        except Exception as e:
            print(f"        ⚠️  Parse error: {e}")
            return None
    
    async def _go_to_next_page(self, page) -> bool:
        """Navigate to next page"""
        try:
            print(f"        📜 Scrolling to bottom of page...")
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await page.wait_for_timeout(1000)
            
            print(f"        🔍 Looking for 'Next' button...")
            selectors = ["a.pagination__next", "a[aria-label='Next page']"]
            
            for idx, selector in enumerate(selectors, 1):
                print(f"        Trying next page selector {idx}/{len(selectors)}: {selector}")
                if await page.locator(selector).count() > 0:
                    print(f"        ✅ Found 'Next' button, clicking...")
                    await page.click(selector)
                    await page.wait_for_load_state("domcontentloaded")
                    await page.wait_for_timeout(3000)
                    print(f"        ✅ Navigated to next page successfully")
                    return True
            
            print(f"        ⚠️  No 'Next' button found")
            return False
        except Exception as e:
            print(f"        ❌ Error navigating to next page: {e}")
            return False


# ============================================================================
# TITLE-BASED DEDUPLICATION
# ============================================================================


class TitleDeduplicator:
    """Optimized deduplication using LSH (Locality Sensitive Hashing)"""
    
    def __init__(self, similarity_threshold: float = 0.85):
        self.threshold = similarity_threshold
    
    def deduplicate(self, items: List[Dict]) -> List[Dict]:
        """Remove duplicates - MUCH faster for large datasets"""
        if not items:
            return []
        
        print(f"\n{'='*80}")
        print(f"FAST DEDUPLICATION (Threshold: {self.threshold*100}%)")
        print(f"{'='*80}")
        print(f"Input items: {len(items)}")
        
        # Phase 1: Exact matching (O(n))
        exact_groups = defaultdict(list)
        for item in items:
            title = self._normalize_title(item.get('title', ''))
            exact_groups[title].append(item)
        
        candidates = []
        for title, group in exact_groups.items():
            best = self._select_best_item(group)
            candidates.append(best)
        
        print(f"After exact matching: {len(candidates)} items")
        
        # Phase 2: LSH-based fuzzy matching (much faster)
        # Group candidates by shingles (n-grams)
        # shingle_groups = defaultdict(list)
        
        # for idx, item in enumerate(candidates):
        #     title = item.get('title', '')
        #     shingles = self._get_shingles(title, n=3)
            
        #     # Add to multiple buckets (increases chance of finding similar items)
        #     for shingle in shingles[:5]:  # Use top 5 shingles
        #         shingle_groups[shingle].append(idx)
        
        # # Phase 3: Compare only candidates in same buckets
        # unique_items = []
        # seen_indices = set()
        # compared_pairs = set()  # Track which pairs we've already compared
        
        # for i, item1 in enumerate(candidates):
        #     if i in seen_indices:
        #         continue
            
        #     title1 = item1.get('title', '')
        #     duplicates = [item1]
            
        #     # Get candidate indices that share shingles with this item
        #     shingles1 = self._get_shingles(title1, n=3)
        #     candidate_indices = set()
        #     for shingle in shingles1[:5]:
        #         candidate_indices.update(shingle_groups[shingle])
            
        #     # Only compare with candidates in same buckets
        #     for j in candidate_indices:
        #         if j <= i or j in seen_indices:
        #             continue
                
        #         # Skip if we already compared this pair
        #         pair = (i, j)
        #         if pair in compared_pairs:
        #             continue
        #         compared_pairs.add(pair)
                
        #         item2 = candidates[j]
        #         title2 = item2.get('title', '')
                
        #         similarity = self._calculate_similarity(title1, title2)
                
        #         if similarity >= self.threshold:
        #             duplicates.append(item2)
        #             seen_indices.add(j)
            
        #     best_item = self._select_best_item(duplicates)
        #     unique_items.append(best_item)
        
        # duplicates_removed = len(items) - len(unique_items)
        # print(f"After fuzzy matching: {len(unique_items)} items")
        # print(f"Comparisons made: {len(compared_pairs):,} (vs {len(candidates)*(len(candidates)-1)//2:,} naive)")
        # print(f"Total duplicates removed: {duplicates_removed} ({duplicates_removed/len(items)*100:.1f}%)")
        # print(f"{'='*80}\n")
        
        # return unique_items
        return candidates
    
    def _get_shingles(self, text: str, n: int = 3) -> List[str]:
        """Get n-gram shingles for LSH"""
        text = self._normalize_title(text)
        words = text.split()
        
        # Create word-level n-grams
        shingles = []
        for i in range(len(words) - n + 1):
            shingle = ' '.join(words[i:i+n])
            shingles.append(shingle)
        
        # Sort by frequency (most unique shingles first)
        return sorted(set(shingles), key=lambda x: (len(x), x), reverse=True)
    
    def _normalize_title(self, title: str) -> str:
        """Normalize title for comparison"""
        title = title.lower()
        title = re.sub(r'\s+', ' ', title)
        title = re.sub(r'[^\w\s-]', '', title)
        return title.strip()
    
    def _calculate_similarity(self, title1: str, title2: str) -> float:
        """Calculate similarity between two titles"""
        title1 = self._normalize_title(title1)
        title2 = self._normalize_title(title2)
        return SequenceMatcher(None, title1, title2).ratio()
    
    def _select_best_item(self, items: List[Dict]) -> Dict:
        """Select the best item from duplicates"""
        if len(items) == 1:
            return items[0]
        
        scored_items = []
        for item in items:
            score = 0
            
            price = item.get('price', 0)
            if price and price > 0:
                score += 10
            
            if item.get('image_url'):
                score += 5
            
            if item.get('shipping_cost', 0) >= 0:
                score += 2
            
            if item.get('status') == 'sold' and item.get('sold_date'):
                score += 3
            
            if item.get('seller') and item.get('seller') != 'Unknown':
                score += 2
            
            scored_items.append((score, item))
        
        scored_items.sort(key=lambda x: (-x[0], x[1].get('price', 999999)))
        return scored_items[0][1]

# ============================================================================
# VEHICLE MATCHING FROM TITLES
# ============================================================================

class SmartVehicleMatcher:
    """Extract vehicle info from titles and score relevance"""
    
    def __init__(self, year: Optional[int], make: Optional[str], model: Optional[str]):
        self.year = year
        self.make = make.lower() if make else None
        self.model = model.lower() if model else None
    
    def score_items(self, items: List[Dict]) -> List[Dict]:
        """Score all items and add vehicle match metadata"""
        print(f"\n{'='*80}")
        print(f"VEHICLE MATCHING")
        print(f"{'='*80}")
        print(f"Target: {self.year} {self.make} {self.model}")
        print(f"Items to score: {len(items)}")
        
        scored_items = []
        score_distribution = Counter()
        
        for item in items:
            title = item.get('title', '')
            score_data = self._score_title(title)
            
            item['vehicle_match_score'] = score_data['score']
            item['vehicle_match_details'] = score_data['details']
            
            scored_items.append(item)
            
            score_bucket = (score_data['score'] // 10) * 10
            score_distribution[score_bucket] += 1
        
        print(f"\nScore Distribution:")
        for bucket in sorted(score_distribution.keys(), reverse=True):
            count = score_distribution[bucket]
            bar = '█' * (count // 5 or 1)
            print(f"  {bucket:3d}-{bucket+9:3d}: {count:4d} {bar}")
        
        print(f"{'='*80}\n")
        
        return scored_items
    
    def _score_title(self, title: str) -> Dict:
        """Score a single title for vehicle match"""
        title_lower = title.lower()
        score = 0
        details = {
            'year_match': False,
            'make_match': False,
            'model_match': False,
            'year_found': None,
            'make_found': None,
            'model_found': None
        }
        
        # Year matching (30 points)
        if self.year:
            year_pattern = r'\b' + str(self.year) + r'\b'
            if re.search(year_pattern, title):
                score += 30
                details['year_match'] = True
                details['year_found'] = self.year
            else:
                # Check year range
                year_range_match = re.search(r'(\d{4})-(\d{4})', title)
                if year_range_match:
                    start_year = int(year_range_match.group(1))
                    end_year = int(year_range_match.group(2))
                    if start_year <= self.year <= end_year:
                        score += 25
                        details['year_match'] = True
                        details['year_found'] = f"{start_year}-{end_year}"
        
        # Make matching (40 points)
        if self.make:
            if self.make in title_lower:
                score += 40
                details['make_match'] = True
                details['make_found'] = self.make
            else:
                make_variants = self._get_make_variants(self.make)
                for variant in make_variants:
                    if variant in title_lower:
                        score += 35
                        details['make_match'] = True
                        details['make_found'] = variant
                        break
        
        # Model matching (30 points)
        if self.model:
            if self.model in title_lower:
                score += 30
                details['model_match'] = True
                details['model_found'] = self.model
            else:
                model_variants = self._get_model_variants(self.model)
                for variant in model_variants:
                    if variant in title_lower:
                        score += 25
                        details['model_match'] = True
                        details['model_found'] = variant
                        break
        
        return {'score': min(score, 100), 'details': details}
    
    def _get_make_variants(self, make: str) -> List[str]:
        """Get common variants of a make"""
        variants = {
            'toyota': ['toyota', 'toyot'],
            'honda': ['honda'],
            'ford': ['ford'],
            'chevrolet': ['chevrolet', 'chevy', 'chev'],
            'mercedes': ['mercedes', 'mercedes-benz', 'merc', 'mb'],
            'bmw': ['bmw'],
            'volkswagen': ['volkswagen', 'vw'],
        }
        return variants.get(make.lower(), [make.lower()])
    
    def _get_model_variants(self, model: str) -> List[str]:
        """Get common variants of a model"""
        variants = [model.lower()]
        variants.append(model.replace(' ', '').lower())
        variants.append(model.replace(' ', '-').lower())
        return variants
    
    def filter_by_min_score(self, items: List[Dict], min_score: int = 60) -> Tuple[List[Dict], List[Dict]]:
        """Filter items by minimum vehicle match score"""
        passed = []
        filtered = []
        
        for item in items:
            score = item.get('vehicle_match_score', 0)
            if score >= min_score:
                passed.append(item)
            else:
                filtered.append(item)
        
        print(f"Vehicle filter (min score {min_score}): Passed: {len(passed)} items, Filtered: {len(filtered)} items")
        
        return passed, filtered


# ============================================================================
# TITLE-BASED GROUPING - IMPROVED
# ============================================================================

class TitleGrouper:
    """Group items by similar titles (after removing vehicle info and ALL numbers)"""
    
    def __init__(self, year: Optional[int] = None, make: Optional[str] = None, 
                 model: Optional[str] = None, similarity_threshold: float = 0.60):
        self.year = year
        self.make = make
        self.model = model
        self.threshold = similarity_threshold
        # Domain-aware keep-words that carry meaning for parts
        self.orientation_words = {
            'left', 'right', 'driver', 'passenger', 'front', 'rear', 'upper', 'lower',
            'inner', 'outer', 'lh', 'rh', 'oem', 'assembly', 'sensor', 'bracket', 'cover'
        }
        # Junk/common words to ignore in comparison (post core extraction)
        self.stop_words = {
            'with', 'without', 'w', 'wo', 'set', 'pair', 'fits', 'fit', 'for', 'and', 'the',
            'of', 'to', 'in', 'on', 'by', 'from', 'part', 'parts', 'auto', 'car', 'vehicle',
            'replacement', 'aftermarket', 'genuine', 'stock', 'factory', 'original', 'new', 'used'
        }
        # Part headwords used to gate grouping to same part family - expanded
        self.part_headwords = {
            'bumper','cover','headlight','headlamp','taillight','lamp','mirror','glass',
            'regulator','window','switch','pump','booster','actuator','inverter','converter',
            'battery','sensor','caliper','rotor','brake','rim','wheel','visor','seat','headrest',
            'console','armrest','fender','hood','door','grille','steering','column','motor',
            'key','fob','manual','garnish','trim','molding','moulding','module','cell',
            'lock','handle','hinge','latch','striker','panel','skin','sill','rocker',
            'abs','hydraulic','master','cylinder','pad','shoe','hose','line','fitting',
            'filter','oil','air','fuel','injector','coil','spark','plug','alternator',
            'starter','relay','solenoid','fuse','wiring','harness','connector','socket'
        }
    
    def group_items(self, items: List[Dict]) -> Dict[str, List[Dict]]:
        """Group items by similar titles using two-pass approach for better coverage"""
        print(f"\n{'='*80}")
        print(f"TITLE GROUPING (Threshold: {self.threshold*100}%)")
        print(f"{'='*80}")
        print(f"Items to group: {len(items)}")
        
        if not items:
            return {}
        
        # Step 1: Extract core titles and tokens
        titles_data = []  # [{item, core, tokens}]
        for item in items:
            title = item.get('title', '')
            core = self._extract_core_title(title)
            tokens = self._tokenize_core(core)
            if len(tokens) == 0:
                continue
            titles_data.append({'item': item, 'core': core, 'tokens': tokens})
        
        # Build inverted index over titles_data indices (not original items indices)
        token_to_indices = defaultdict(list)
        for idx_td, data in enumerate(titles_data):
            for t in data['tokens']:
                token_to_indices[t].append(idx_td)
        
        if not titles_data:
            return {}
        
        # Step 2: Two-pass grouping with union-find
        n = len(titles_data)
        parent = list(range(n))  # union-find for grouping
        size = [1] * n
        
        def find(x: int) -> int:
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x
        
        def union(x: int, y: int):
            rx, ry = find(x), find(y)
            if rx == ry:
                return
            if size[rx] < size[ry]:
                rx, ry = ry, rx
            parent[ry] = rx
            size[rx] += size[ry]
        
        # Pass 1: Strict grouping (with headword requirement, higher threshold)
        strict_threshold = self.threshold
        for i, data in enumerate(titles_data):
            tokens_i = data['tokens']
            candidate_indices = set()
            for t in tokens_i:
                indices = token_to_indices.get(t, [])
                if len(indices) > 200:
                    indices = indices[:200]
                candidate_indices.update(indices)
            
            for j in candidate_indices:
                if j <= i:
                    continue
                tokens_j = titles_data[j]['tokens']
                if len(tokens_i) < 2 or len(tokens_j) < 2:
                    continue
                # Pass 1: Require headword overlap for precision
                headword_overlap = set(tokens_i) & set(tokens_j) & self.part_headwords
                if not headword_overlap:
                    continue
                sim = self._tokens_similarity(tokens_i, tokens_j)
                if sim >= strict_threshold:
                    union(i, j)
        
        # Pass 2: Lenient grouping for remaining ungrouped items (lower threshold, headword optional)
        lenient_threshold = max(0.45, self.threshold * 0.75)  # Lower threshold
        ungrouped = set()
        # Find items that are still in singleton groups (parent[i] == i and size[i] == 1)
        for i in range(n):
            if parent[i] == i and size[i] == 1:  # Still ungrouped (singleton)
                ungrouped.add(i)
        
        # Group ungrouped items with more lenient criteria
        for i in ungrouped:
            tokens_i = titles_data[i]['tokens']
            candidate_indices = set()
            for t in tokens_i:
                indices = token_to_indices.get(t, [])
                if len(indices) > 150:
                    indices = indices[:150]
                candidate_indices.update(indices)
            
            best_match_score = 0
            best_match_idx = None
            for j in candidate_indices:
                if j == i or find(j) == find(i):
                    continue
                tokens_j = titles_data[j]['tokens']
                if len(tokens_i) < 2 or len(tokens_j) < 2:
                    continue
                sim = self._tokens_similarity(tokens_i, tokens_j)
                # Pass 2: More lenient - allow if high similarity OR moderate similarity with headword
                headword_overlap = set(tokens_i) & set(tokens_j) & self.part_headwords
                if sim >= lenient_threshold or (sim >= 0.35 and headword_overlap):
                    if sim > best_match_score:
                        best_match_score = sim
                        best_match_idx = j
            
            # Merge with best match if found
            if best_match_idx is not None:
                union(i, best_match_idx)
        
        # Step 3: Materialize groups from union-find
        groups_map: Dict[int, List[Dict]] = defaultdict(list)
        for i, data in enumerate(titles_data):
            root = find(i)
            groups_map[root].append(data['item'])
        
        # Re-key groups to group_X - allow groups of 2 or more
        min_group_size = max(2, Config.MIN_ITEMS_PER_GROUP)
        result: Dict[str, List[Dict]] = {}
        gid = 0
        for members in groups_map.values():
            if len(members) >= min_group_size:
                result[f"group_{gid}"] = members
                gid += 1
        
        total_grouped = sum(len(members) for members in result.values())
        print(f"Created {len(result)} groups (min {min_group_size} items)")
        print(f"Items in groups: {total_grouped}/{len(items)} ({(total_grouped/len(items)*100 if items else 0):.1f}%)")
        print(f"\nGroup sizes:")
        for gid_key, members in sorted(result.items(), key=lambda x: len(x[1]), reverse=True)[:10]:
            print(f"  {gid_key}: {len(members)} items")
        
        print(f"{'='*80}\n")
        return result
    
    def _extract_core_title(self, title: str) -> str:
        """Extract core part name: remove vehicle info and numeric-like tokens, keep meaningful orientation"""
        s = title.lower()
        # Normalize common synonyms - expanded
        synonym_map = [
            ('head lamp', 'headlight'), ('head-lamp', 'headlight'), ('head lamp assembly', 'headlight assembly'),
            ('tail light', 'taillight'), ('tail-light', 'taillight'), ('tail lamp', 'taillight'),
            ('grill', 'grille'), ('grille grill', 'grille'), ('grill grille', 'grille'),
            ('molding', 'trim'), ('moulding','trim'), ('molding trim', 'trim'), ('trim molding', 'trim'),
            ('console lid', 'armrest'), ('arm rest lid', 'armrest'), ('console armrest', 'armrest'),
            ('key fob', 'fob'), ('keyfob', 'fob'), ('remote key', 'fob'),
            ('abs pump', 'pump'), ('abs module pump', 'pump'), ('brake pump abs', 'pump'),
            ('wheel rim', 'rim'), ('wheel rim', 'wheel'), ('rim wheel', 'rim'),
            ('battery cell', 'cell'), ('battery module', 'module'), ('cell module', 'module'),
            ('door handle', 'handle'), ('door lock', 'lock'), ('lock actuator', 'actuator'),
            ('brake caliper', 'caliper'), ('brake rotor', 'rotor'), ('brake pad', 'pad'),
            ('window regulator', 'regulator'), ('regulator motor', 'regulator')
        ]
        for a, b in synonym_map:
            s = s.replace(a, b)
        
        # Remove year
        if self.year:
            s = re.sub(r'\b' + str(self.year) + r'\b', '', s)
        
        # Remove make
        if self.make:
            s = re.sub(r'\b' + re.escape(self.make.lower()) + r'\b', '', s)
        
        # Remove model
        if self.model:
            s = re.sub(r'\b' + re.escape(self.model.lower()) + r'\b', '', s)
        
        # Remove tokens containing digits (likely part numbers), but keep pure orientation words
        tokens = re.split(r'[^a-z0-9]+', s)
        filtered = []
        for t in tokens:
            if not t:
                continue
            if any(ch.isdigit() for ch in t):
                continue
            filtered.append(t)
        s = ' '.join(filtered)
        
        # Remove common junk terms
        for term in ['oem', 'genuine', 'aftermarket', 'replacement', 'new', 'used',
                     'refurbished', 'fits', 'for', 'part', 'parts', 'original', 'factory', 'stock']:
            s = re.sub(r'\b' + term + r'\b', '', s)
        
        # Clean up whitespace and special chars
        s = re.sub(r'\s+', ' ', s)
        s = re.sub(r'[^\w\s-]', '', s)
        return s.strip()

    def _tokenize_core(self, core: str) -> List[str]:
        """Tokenize core string into meaningful tokens removing stopwords, preserving orientation words"""
        if not core:
            return []
        tokens = [t for t in re.split(r'[^a-z0-9]+', core.lower()) if t]
        result = []
        for t in tokens:
            if t in self.stop_words:
                continue
            result.append(t)
        # Include bigrams to capture phrases
        bigrams = [result[i] + ' ' + result[i+1] for i in range(len(result)-1)] if len(result) >= 2 else []
        return result + bigrams

    def _tokens_similarity(self, a: List[str], b: List[str]) -> float:
        """Jaccard similarity with small boost for orientation/location tokens"""
        set_a, set_b = set(a), set(b)
        if not set_a or not set_b:
            return 0.0
        inter = set_a & set_b
        union = set_a | set_b
        # Weighted Jaccard
        def weight(tok: str) -> float:
            if tok in self.part_headwords:
                return 2.0
            if tok in self.orientation_words:
                return 1.2
            return 1.0 + (0.3 if ' ' in tok else 0.0)
        inter_w = sum(weight(t) for t in inter)
        union_w = sum(weight(t) for t in union)
        score = inter_w / max(1e-6, union_w)
        if any(tok in self.orientation_words for tok in inter):
            score += 0.08
        return min(score, 1.0)


# ============================================================================
# CLAUDE CATEGORY NAMING - IMPROVED
# ============================================================================

class ClaudeCategoryNamer:
    """Use Claude API to name categories with improved prompting"""
    
    def __init__(self, api_key: str):
        self.client = anthropic.Anthropic(api_key=api_key)
    
    async def name_categories(self, groups: Dict[str, List[Dict]]) -> Dict[str, Dict]:
        """Name all groups using Claude with improved prompts"""
        print(f"\n{'='*80}")
        print(f"CLAUDE CATEGORY NAMING")
        print(f"{'='*80}")
        
        # Limit groups for naming
        sorted_groups = sorted(groups.items(), key=lambda x: len(x[1]), reverse=True)
        groups_to_name = dict(sorted_groups[:Config.MAX_GROUPS_FOR_NAMING])
        
        print(f"Groups to name: {len(groups_to_name)}")
        
        named_categories = {}
        
        for group_id, items in groups_to_name.items():
            sample_items = items[:Config.ITEMS_PER_GROUP_FOR_NAMING]
            category_info = await self._get_category_name(sample_items)
            
            named_categories[group_id] = {
                'name': category_info['name'],
                'description': category_info['description'],
                'sample_items': [
                    {'title': item.get('title', '')[:80], 'price': item.get('price', 0)}
                    for item in sample_items
                ],
                'total_items': len(items)
            }
            
            print(f"  ✓ {group_id}: {category_info['name']} ({len(items)} items)")
        
        print(f"{'='*80}\n")
        
        return named_categories
    
    async def _get_category_name(self, items: List[Dict]) -> Dict:
        """Get category name from Claude with improved prompt"""
        titles = [item.get('title', '') for item in items]
        titles_text = '\n'.join(f"{i+1}. {title}" for i, title in enumerate(titles))
        
        prompt = f"""You are analyzing automotive part listings. Look at these titles and identify what SPECIFIC AUTO PART they are selling.

Listing titles:
{titles_text}

Instructions:
1. Ignore vehicle make/model/year information
2. Ignore part numbers, OEM codes, SKUs
3. Focus ONLY on what type of part this is (e.g., "Front Bumper Cover", "Headlight Assembly", "Brake Rotor")
4. Be specific about the part type and location if applicable
5. Use proper automotive terminology
6. Keep the name SHORT (2-4 words max)

Respond ONLY in this JSON format:
{{
  "name": "Specific Part Name",
  "description": "What this part is and where it's located on the vehicle."
}}

Examples of GOOD names:
- "Front Bumper Cover"
- "Passenger Headlight Assembly"
- "Rear Brake Caliper"
- "Door Mirror Glass"

Examples of BAD names:
- "For Parts 2010-2012" (includes years)
- "Toyota Parts" (too generic)
- "8481033120 Window Regulator" (includes part number)"""
        
        try:
            message = await asyncio.to_thread(
                self.client.messages.create,
                model=Config.CLAUDE_MODEL,
                max_tokens=200,
                messages=[{"role": "user", "content": prompt}]
            )
            
            response_text = message.content[0].text
            
            # Clean response
            response_text = response_text.strip()
            if response_text.startswith('```json'):
                response_text = response_text[7:]
            if response_text.startswith('```'):
                response_text = response_text[3:]
            if response_text.endswith('```'):
                response_text = response_text[:-3]
            response_text = response_text.strip()
            
            import json
            result = json.loads(response_text)
            
            return {
                'name': result.get('name', 'Unknown Part'),
                'description': result.get('description', 'Auto part')
            }
        
        except Exception as e:
            print(f"     Error getting category name: {e}")
            first_title = items[0].get('title', '') if items else ''
            return {
                'name': self._extract_fallback_name(first_title),
                'description': 'Auto part'
            }
    
    def _extract_fallback_name(self, title: str) -> str:
        """Extract a simple category name from title as fallback"""
        patterns = {
            r'bumper': 'Bumper',
            r'headlight': 'Headlight',
            r'taillight': 'Taillight',
            r'mirror': 'Mirror',
            r'door': 'Door',
            r'hood': 'Hood',
            r'fender': 'Fender',
            r'grille': 'Grille',
            r'brake': 'Brake Component',
            r'abs': 'ABS System',
        }
        
        title_lower = title.lower()
        for pattern, name in patterns.items():
            if re.search(pattern, title_lower):
                return name
        
        words = title.split()[:3]
        return ' '.join(words).title()


# ============================================================================
# PRICE ANALYSIS - FIXED
# ============================================================================

class PriceAnalyzer:
    """Analyze pricing with outlier detection"""
    
    @staticmethod
    def clean_price(price_value) -> Optional[float]:
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
    
    @staticmethod
    def filter_valid_prices(items: List[Dict]) -> Tuple[List[Dict], Dict]:
        """Filter out price outliers using IQR method"""
        if not items:
            return [], {}
        
        prices = []
        for item in items:
            price = PriceAnalyzer.clean_price(item.get('price'))
            if price and price > 0:
                prices.append(price)
        
        if len(prices) < 4:
            return items, {
                'method': 'none',
                'reason': 'insufficient_data',
                'total_items': len(items)
            }
        
        sorted_prices = sorted(prices)
        q1_idx = int(len(sorted_prices) * 0.25)
        q3_idx = int(len(sorted_prices) * 0.75)
        q1 = sorted_prices[q1_idx]
        q3 = sorted_prices[q3_idx]
        iqr = q3 - q1
        
        lower_bound = max(q1 - (Config.IQR_MULTIPLIER * iqr), Config.MIN_PRICE_ABSOLUTE)
        upper_bound = q3 + (Config.IQR_MULTIPLIER * iqr)
        
        valid_items = []
        outliers = []
        
        for item in items:
            price = PriceAnalyzer.clean_price(item.get('price'))
            if price and (lower_bound <= price <= upper_bound):
                valid_items.append(item)
            elif price:
                outliers.append(item)
        
        stats = {
            'method': 'iqr',
            'total_items': len(items),
            'valid_items': len(valid_items),
            'outliers_removed': len(outliers),
            'bounds': {'lower': round(lower_bound, 2), 'upper': round(upper_bound, 2)},
            'quartiles': {'q1': round(q1, 2), 'q3': round(q3, 2), 'iqr': round(iqr, 2)}
        }
        
        if outliers:
            print(f"  Price outliers filtered: {len(outliers)}")
            print(f"  Valid range: ${lower_bound:.2f} - ${upper_bound:.2f}")
        
        return valid_items, stats
    
    @staticmethod
    def calculate_pricing_stats(items: List[Dict]) -> Dict:
        """Calculate comprehensive pricing statistics - FIXED"""
        items, filter_stats = PriceAnalyzer.filter_valid_prices(items)
        
        active = [i for i in items if i.get('status') == 'active']
        sold = [i for i in items if i.get('status') == 'sold']
        
        active_prices = [PriceAnalyzer.clean_price(i.get('price')) for i in active]
        active_prices = [p for p in active_prices if p and p > 0]
        
        sold_prices = [PriceAnalyzer.clean_price(i.get('price')) for i in sold]
        sold_prices = [p for p in sold_prices if p and p > 0]
        
        # FIX: Calculate average shipping safely
        shipping_costs = [i.get('shipping_cost', 0) for i in items]
        positive_shipping = [s for s in shipping_costs if s > 0]
        avg_shipping = statistics.mean(positive_shipping) if positive_shipping else 0.0
        
        result = {
            'filter_stats': filter_stats,
            'active': {},
            'sold': {},
            'optimal_price': 0,
            'avg_shipping': float(avg_shipping),
            'recommendation': ''
        }
        
        if active_prices:
            result['active'] = {
                'count': len(active_prices),
                'min': float(min(active_prices)),
                'max': float(max(active_prices)),
                'avg': float(statistics.mean(active_prices)),
                'median': float(statistics.median(active_prices))
            }
        
        if sold_prices:
            result['sold'] = {
                'count': len(sold_prices),
                'min': float(min(sold_prices)),
                'max': float(max(sold_prices)),
                'avg': float(statistics.mean(sold_prices)),
                'median': float(statistics.median(sold_prices))
            }
            
            result['optimal_price'] = float(statistics.median(sold_prices))
            
            optimal = result['optimal_price']
            ebay_fee = optimal * 0.1325
            payment_fee = (optimal * 0.029) + 0.30
            net_profit = optimal - ebay_fee - payment_fee
            
            result['profit_estimate'] = {
                'gross_price': float(optimal),
                'ebay_fee': float(ebay_fee),
                'payment_fee': float(payment_fee),
                'net_profit': float(net_profit),
                'margin_percent': float((net_profit / optimal * 100) if optimal > 0 else 0)
            }
        
        if sold_prices and active_prices:
            sold_median = statistics.median(sold_prices)
            active_median = statistics.median(active_prices)
            
            if active_median > sold_median * 1.2:
                result['recommendation'] = f"Current listings may be overpriced. Consider pricing around ${sold_median:.2f}"
            elif active_median < sold_median * 0.8:
                result['recommendation'] = f"Good opportunity! Items selling for ${sold_median:.2f}, current listings underpriced"
            else:
                result['recommendation'] = f"Market is balanced. Price around ${sold_median:.2f} for optimal results"
        elif sold_prices:
            result['recommendation'] = f"Price around ${statistics.median(sold_prices):.2f} based on sold data"
        elif active_prices:
            result['recommendation'] = f"No sold data available. Active listings range ${min(active_prices):.2f}-${max(active_prices):.2f}"
        else:
            result['recommendation'] = "Insufficient pricing data"
        
        return result


# ============================================================================
# MAIN ANALYZER
# ============================================================================

class ScraperOnlyAnalyzer:
    """Complete scraping-only analyzer with intelligent categorization"""
    
    def __init__(self, year: int, make: str, model: str, claude_api_key: str, is_multi_part: bool,
                 search_terms: Optional[List[str]] = None):
        self.year = year
        self.make = make
        self.model = model
        self.search_terms = search_terms or [f"{year} {make} {model} parts"]
        self.is_multi_part = is_multi_part
        
        self.scraper = UniversalEbayScraper()
        self.deduplicator = TitleDeduplicator(Config.TITLE_SIMILARITY_THRESHOLD)
        self.vehicle_matcher = SmartVehicleMatcher(year, make, model)
        self.grouper = TitleGrouper(year, make, model, Config.GROUP_SIMILARITY_THRESHOLD)
        self.category_namer = ClaudeCategoryNamer(claude_api_key)
    
    async def analyze(self) -> Dict:
        """Complete analysis pipeline"""
        print(f"\n{'='*80}")
        print(f"SCRAPER-ONLY EBAY ANALYSIS")
        print(f"{'='*80}")
        print(f"Vehicle: {self.year} {self.make} {self.model}")
        print(f"Search terms: {self.search_terms}")
        print(f"{'='*80}\n")
        
        # Step 1: Scrape (use category tree for better organization)
        raw_items, nested_categories = await self.scraper.collect_for_queries(
            self.search_terms, include_active=True, include_sold=True, use_category_tree=True
        )
        
        if not raw_items and not nested_categories:
            return self._generate_no_data_report()
        
        print(f"\n✅ Scraped {len(raw_items)} total items\n")
        
        # Step 2: Deduplicate
        # unique_items = self.deduplicator.deduplicate(raw_items)
        
        # Step 3: Vehicle matching
        filtered_items = []
        relevant_items = raw_items

        if not self.is_multi_part:
            scored_items = self.vehicle_matcher.score_items(raw_items)
            relevant_items, filtered_items = self.vehicle_matcher.filter_by_min_score(
                scored_items, min_score=Config.VEHICLE_MATCH_MIN_SCORE
            )
        
        if not relevant_items and not nested_categories:
            return self._generate_no_data_report()
        
        # Step 4: Use nested categories directly (no title grouping or AI naming needed)
        if nested_categories:
            print(f"\n{'='*80}")
            print(f"USING EBAY CATEGORIES (No AI categorization needed)")
            print(f"{'='*80}\n")
            
            # Analyze nested category structure
            category_analysis = self._analyze_nested_categories(nested_categories)
            
            # Step 5: Report using nested categories
            report = self._generate_report_from_categories(
                raw_items, raw_items, relevant_items, filtered_items,
                nested_categories, category_analysis
            )
        else:
            # Fallback to old grouping if no nested categories
            groups = self.grouper.group_items(relevant_items)
            if not groups:
                return self._generate_no_data_report()
            categories = await self.category_namer.name_categories(groups)
            category_analysis = self._analyze_categories(groups, categories)
            report = self._generate_report(
                raw_items, raw_items, relevant_items, filtered_items,
                groups, categories, category_analysis
            )
        
        # Add report summary
        report['reports_summary'] = self._generate_reports_summary(report)
        
        print(f"\n{'='*80}")
        print(f"ANALYSIS COMPLETE")
        print(f"{'='*80}")
        print(f"Total items scraped: {len(raw_items)}")
        print(f"Unique items: {len(raw_items)}")
        print(f"Vehicle-relevant items: {len(relevant_items)}")
        if nested_categories:
            total_cats = self._count_categories_in_tree(nested_categories)
            print(f"Categories found: {total_cats}")
        
        # Print reports summary
        print(f"\n{'='*80}")
        print(f"📊 REPORTS GENERATED")
        print(f"{'='*80}")
        for report_info in report['reports_summary']['generated_reports']:
            print(f"  ✅ {report_info['name']}: {report_info['description']}")
        print(f"\n{'='*80}")
        print(f"📋 AVAILABLE REPORTS")
        print(f"{'='*80}")
        for report_info in report['reports_summary']['available_reports']:
            status = "✅ Generated" if report_info['generated'] else "⏳ Can Generate"
            print(f"  {status} - {report_info['name']}: {report_info['description']}")
        print(f"{'='*80}\n")
        
        return report
    
    def _analyze_nested_categories(self, nested_categories: Dict) -> List[Dict]:
        """Analyze nested category structure"""
        analysis_results = []
        
        def analyze_category(cat_dict: Dict, path: List[str] = None):
            path = path or []
            current_path = path + [cat_dict.get('category_name', cat_dict.get('name', 'Unknown'))]
            
            items_raw = cat_dict.get('items', [])
            
            # Check if items are grouped by type
            if isinstance(items_raw, dict):
                # Items grouped by type - analyze each type separately
                types_analyzed = []
                all_items = []
                
                for type_name, type_items in items_raw.items():
                    if isinstance(type_items, list) and type_items:
                        # Analyze this type
                        active_type = [i for i in type_items if isinstance(i, dict) and i.get('status') == 'active']
                        sold_type = [i for i in type_items if isinstance(i, dict) and i.get('status') == 'sold']
                        
                        pricing_type = PriceAnalyzer.calculate_pricing_stats(type_items)
                        total_type = len(active_type) + len(sold_type)
                        sell_through_type = (len(sold_type) / total_type * 100) if total_type > 0 else 0
                        
                        demand_type = "high" if len(sold_type) >= 10 else "medium" if len(sold_type) >= 5 else "low"
                        competition_type = "high" if len(active_type) >= 30 else "medium" if len(active_type) >= 15 else "low"
                        
                        types_analyzed.append({
                            'type_name': type_name,
                            'total_items': len(type_items),
                            'active_count': len(active_type),
                            'sold_count': len(sold_type),
                            'sell_through_rate': float(sell_through_type),
                            'demand_level': demand_type,
                            'competition_level': competition_type,
                            'pricing': pricing_type,
                            'opportunity_score': self._calculate_opportunity_score(
                                len(sold_type), len(active_type), pricing_type.get('optimal_price', 0)
                            )
                        })
                        
                        all_items.extend(type_items)
                    elif isinstance(type_items, dict):
                        # Nested dict structure, flatten recursively
                        for nested_items in type_items.values():
                            if isinstance(nested_items, list):
                                all_items.extend(nested_items)
                
                # Analyze overall category
                if all_items:
                    active = [i for i in all_items if isinstance(i, dict) and i.get('status') == 'active']
                    sold = [i for i in all_items if isinstance(i, dict) and i.get('status') == 'sold']
                    
                    pricing = PriceAnalyzer.calculate_pricing_stats(all_items)
                    total_listings = len(active) + len(sold)
                    sell_through_rate = (len(sold) / total_listings * 100) if total_listings > 0 else 0
                    
                    demand = "high" if len(sold) >= 10 else "medium" if len(sold) >= 5 else "low"
                    competition = "high" if len(active) >= 30 else "medium" if len(active) >= 15 else "low"
                    
                    analysis_results.append({
                        'category_id': cat_dict.get('category_id', cat_dict.get('id', '')),
                        'category_name': cat_dict.get('category_name', cat_dict.get('name', 'Unknown')),
                        'category_path': current_path,
                        'category_url': cat_dict.get('url', ''),
                        'total_items': len(all_items),
                        'active_count': len(active),
                        'sold_count': len(sold),
                        'sell_through_rate': float(sell_through_rate),
                        'demand_level': demand,
                        'competition_level': competition,
                        'pricing': pricing,
                        'sample_items': self._format_sample_items(all_items[:10]),
                        'opportunity_score': self._calculate_opportunity_score(
                            len(sold), len(active), pricing.get('optimal_price', 0)
                        ),
                        'types_breakdown': types_analyzed if types_analyzed else None  # Include type breakdown if available
                    })
            elif isinstance(items_raw, list) and items_raw:
                # Items as list - analyze normally
                items = items_raw
                active = [i for i in items if isinstance(i, dict) and i.get('status') == 'active']
                sold = [i for i in items if isinstance(i, dict) and i.get('status') == 'sold']
                
                pricing = PriceAnalyzer.calculate_pricing_stats(items)
                
                total_listings = len(active) + len(sold)
                sell_through_rate = (len(sold) / total_listings * 100) if total_listings > 0 else 0
                
                demand = "high" if len(sold) >= 10 else "medium" if len(sold) >= 5 else "low"
                competition = "high" if len(active) >= 30 else "medium" if len(active) >= 15 else "low"
                
                analysis_results.append({
                    'category_id': cat_dict.get('category_id', cat_dict.get('id', '')),
                    'category_name': cat_dict.get('category_name', cat_dict.get('name', 'Unknown')),
                    'category_path': current_path,
                    'category_url': cat_dict.get('url', ''),
                    'total_items': len(items),
                    'active_count': len(active),
                    'sold_count': len(sold),
                    'sell_through_rate': float(sell_through_rate),
                    'demand_level': demand,
                    'competition_level': competition,
                    'pricing': pricing,
                    'sample_items': self._format_sample_items(items[:10]),
                    'opportunity_score': self._calculate_opportunity_score(
                        len(sold), len(active), pricing.get('optimal_price', 0)
                    ),
                    'types_breakdown': None  # No type breakdown for non-typed items
                })
            
            # Recurse into subcategories (categories is a list, not a dict)
            subcategories = cat_dict.get('categories', [])
            if isinstance(subcategories, list):
                for subcat in subcategories:
                    analyze_category(subcat, current_path)
            elif isinstance(subcategories, dict):
                # Handle legacy dict structure if it exists
                for subcat in subcategories.values():
                    analyze_category(subcat, current_path)
        
        # Process both active and sold category trees
        for listing_type, category_tree in nested_categories.items():
            if isinstance(category_tree, dict):
                categories = category_tree.get('categories', [])
                if isinstance(categories, list):
                    for cat in categories:
                        analyze_category(cat, [listing_type])
                elif isinstance(categories, dict):
                    # Handle legacy dict structure if it exists
                    for cat in categories.values():
                        analyze_category(cat, [listing_type])
        
        analysis_results.sort(key=lambda x: x['opportunity_score'], reverse=True)
        return analysis_results
    
    def _count_categories_in_tree(self, nested_categories: Dict) -> int:
        """Count total categories in nested structure"""
        count = 0
        
        def count_recursive(cat_dict: Dict):
            nonlocal count
            if cat_dict.get('items'):
                count += 1
            # Handle categories as list or dict
            subcategories = cat_dict.get('categories', [])
            if isinstance(subcategories, list):
                for subcat in subcategories:
                    count_recursive(subcat)
            elif isinstance(subcategories, dict):
                # Handle legacy dict structure if it exists
                for subcat in subcategories.values():
                    count_recursive(subcat)
        
        for listing_type, category_tree in nested_categories.items():
            if isinstance(category_tree, dict):
                categories = category_tree.get('categories', [])
                if isinstance(categories, list):
                    for cat in categories:
                        count_recursive(cat)
                elif isinstance(categories, dict):
                    # Handle legacy dict structure if it exists
                    for cat in categories.values():
                        count_recursive(cat)
        
        return count
    
    def _analyze_categories(self, groups: Dict[str, List[Dict]], categories: Dict[str, Dict]) -> List[Dict]:
        """Analyze each category (legacy method for non-category-tree mode)"""
        analysis_results = []
        
        for group_id, items in groups.items():
            if group_id not in categories:
                continue
            
            category_info = categories[group_id]
            active = [i for i in items if i.get('status') == 'active']
            sold = [i for i in items if i.get('status') == 'sold']
            
            pricing = PriceAnalyzer.calculate_pricing_stats(items)
            
            total_listings = len(active) + len(sold)
            sell_through_rate = (len(sold) / total_listings * 100) if total_listings > 0 else 0
            
            demand = "high" if len(sold) >= 10 else "medium" if len(sold) >= 5 else "low"
            competition = "high" if len(active) >= 30 else "medium" if len(active) >= 15 else "low"
            
            analysis_results.append({
                'group_id': group_id,
                'category_name': category_info['name'],
                'category_description': category_info['description'],
                'total_items': len(items),
                'active_count': len(active),
                'sold_count': len(sold),
                'sell_through_rate': float(sell_through_rate),
                'demand_level': demand,
                'competition_level': competition,
                'pricing': pricing,
                'sample_items': self._format_sample_items(items[:10]),
                'opportunity_score': self._calculate_opportunity_score(
                    len(sold), len(active), pricing.get('optimal_price', 0)
                )
            })
        
        analysis_results.sort(key=lambda x: x['opportunity_score'], reverse=True)
        return analysis_results
    
    def _calculate_opportunity_score(self, sold_count: int, active_count: int, optimal_price: float) -> int:
        """Calculate opportunity score"""
        score = 0
        
        if sold_count >= 10:
            score += 40
        elif sold_count >= 5:
            score += 25
        elif sold_count >= 3:
            score += 10
        
        if active_count < 15:
            score += 30
        elif active_count < 30:
            score += 15
        
        if optimal_price >= 100:
            score += 30
        elif optimal_price >= 50:
            score += 20
        elif optimal_price >= 25:
            score += 10
        
        return score
    
    def _format_sample_items(self, items: List[Dict]) -> List[Dict]:
        """Format items for display"""
        return [
            {
                'title': item.get('title', '')[:100],
                'price': PriceAnalyzer.clean_price(item.get('price')),
                'shipping': item.get('shipping_cost', 0),
                'status': item.get('status'),
                'seller': item.get('seller', 'Unknown'),
                'location': item.get('location', ''),
                'vehicle_match_score': item.get('vehicle_match_score', 0),
                'url': item.get('url', '')
            }
            for item in items
        ]
    
    def _generate_report_from_categories(self, raw_items, unique_items, relevant_items, filtered_items,
                                         nested_categories: Dict, category_analysis: List[Dict]) -> Dict:
        """Generate comprehensive report from nested category structure"""
        
        active_count = len([i for i in relevant_items if i.get('status') == 'active'])
        sold_count = len([i for i in relevant_items if i.get('status') == 'sold'])
        top_opportunities = category_analysis[:5]
        
        # Generate seller report first to pass to competition analysis
        seller_report = self._generate_seller_report(relevant_items)
        
        report = {
            'vehicle': {'year': self.year, 'make': self.make, 'model': self.model},
            'analysis_timestamp': datetime.now().isoformat(),
            'analysis_type': 'category_tree',
            'data_summary': {
                'total_items_scraped': len(raw_items),
                'duplicates_removed': len(raw_items) - len(unique_items),
                'unique_items': len(unique_items),
                'vehicle_relevant': len(relevant_items),
                'vehicle_filtered': len(filtered_items),
                'active_listings': active_count,
                'sold_listings': sold_count,
                'categories_identified': len(category_analysis)
            },
            'nested_categories': nested_categories,  # Full nested structure
            'categories': category_analysis,
            'top_opportunities': [
                {
                    'category_name': cat['category_name'],
                    'category_path': cat.get('category_path', []),
                    'category_id': cat.get('category_id', ''),
                    'opportunity_score': cat['opportunity_score'],
                    'sold_count': cat['sold_count'],
                    'active_count': cat['active_count'],
                    'optimal_price': cat['pricing'].get('optimal_price', 0),
                    'avg_shipping': cat['pricing'].get('avg_shipping', 0),
                    'sell_through_rate': cat['sell_through_rate'],
                    'recommendation': cat['pricing'].get('recommendation', '')
                }
                for cat in top_opportunities
            ],
            'market_overview': {
                'total_categories': len(category_analysis),
                'total_active': active_count,
                'total_sold': sold_count,
                'overall_sell_through': (sold_count / (active_count + sold_count) * 100) 
                    if (active_count + sold_count) > 0 else 0,
                'avg_opportunity_score': statistics.mean([
                    cat['opportunity_score'] for cat in category_analysis
                ]) if category_analysis else 0
            },
            'recommendations': {
                'best_category': top_opportunities[0]['category_name'] if top_opportunities else 'N/A',
                'suggestion': self._generate_main_recommendation(category_analysis)
            },
            'seller_report': seller_report,
            'price_distribution_report': self._generate_price_distribution_report(relevant_items, category_analysis),
            'competition_analysis_report': self._generate_competition_analysis_report(
                relevant_items, category_analysis, seller_report
            ),
            'category_performance_report': self._generate_category_performance_report(category_analysis, relevant_items),
            'time_based_analysis_report': self._generate_time_based_analysis_report(
                relevant_items, category_analysis, datetime.now().isoformat()
            )
        }
        
        return report
    
    def _generate_report(self, raw_items, unique_items, relevant_items, filtered_items,
                        groups, categories, category_analysis) -> Dict:
        """Generate comprehensive report (legacy method for non-category-tree mode)"""
        
        active_count = len([i for i in relevant_items if i.get('status') == 'active'])
        sold_count = len([i for i in relevant_items if i.get('status') == 'sold'])
        top_opportunities = category_analysis[:5]
        
        # Generate seller report first to pass to competition analysis
        seller_report = self._generate_seller_report(relevant_items)
        
        report = {
            'vehicle': {'year': self.year, 'make': self.make, 'model': self.model},
            'analysis_timestamp': datetime.now().isoformat(),
            'analysis_type': 'scraper_only',
            'data_summary': {
                'total_items_scraped': len(raw_items),
                'duplicates_removed': len(raw_items) - len(unique_items),
                'unique_items': len(unique_items),
                'vehicle_relevant': len(relevant_items),
                'vehicle_filtered': len(filtered_items),
                'active_listings': active_count,
                'sold_listings': sold_count,
                'categories_identified': len(categories)
            },
            'categories': category_analysis,
            'top_opportunities': [
                {
                    'category_name': cat['category_name'],
                    'opportunity_score': cat['opportunity_score'],
                    'sold_count': cat['sold_count'],
                    'active_count': cat['active_count'],
                    'optimal_price': cat['pricing'].get('optimal_price', 0),
                    'avg_shipping': cat['pricing'].get('avg_shipping', 0),
                    'sell_through_rate': cat['sell_through_rate'],
                    'recommendation': cat['pricing'].get('recommendation', '')
                }
                for cat in top_opportunities
            ],
            'market_overview': {
                'total_categories': len(categories),
                'total_active': active_count,
                'total_sold': sold_count,
                'overall_sell_through': (sold_count / (active_count + sold_count) * 100) 
                    if (active_count + sold_count) > 0 else 0,
                'avg_opportunity_score': statistics.mean([
                    cat['opportunity_score'] for cat in category_analysis
                ]) if category_analysis else 0
            },
            'recommendations': {
                'best_category': top_opportunities[0]['category_name'] if top_opportunities else 'N/A',
                'suggestion': self._generate_main_recommendation(category_analysis)
            },
            'seller_report': seller_report,
            'price_distribution_report': self._generate_price_distribution_report(relevant_items, category_analysis),
            'competition_analysis_report': self._generate_competition_analysis_report(
                relevant_items, category_analysis, seller_report
            ),
            'category_performance_report': self._generate_category_performance_report(category_analysis, relevant_items),
            'time_based_analysis_report': self._generate_time_based_analysis_report(
                relevant_items, category_analysis, datetime.now().isoformat()
            )
        }
        
        return report
    
    def _generate_price_distribution_report(self, items: List[Dict], category_analysis: List[Dict] = None) -> Dict:
        """Generate price distribution report with quartiles and ranges"""
        prices = [PriceAnalyzer.clean_price(item.get('price')) for item in items]
        prices = [p for p in prices if p and p > 0]
        
        if not prices:
            return {
                'total_items': len(items),
                'valid_prices': 0,
                'error': 'No valid prices found'
            }
        
        sorted_prices = sorted(prices)
        n = len(sorted_prices)
        
        # Calculate quartiles
        q1_idx = int(n * 0.25)
        q2_idx = int(n * 0.50)  # Median
        q3_idx = int(n * 0.75)
        
        q1 = sorted_prices[q1_idx] if q1_idx < n else sorted_prices[-1]
        q2 = sorted_prices[q2_idx] if q2_idx < n else sorted_prices[-1]
        q3 = sorted_prices[q3_idx] if q3_idx < n else sorted_prices[-1]
        
        iqr = q3 - q1
        
        # Price ranges
        min_price = min(prices)
        max_price = max(prices)
        mean_price = statistics.mean(prices)
        median_price = statistics.median(prices)
        std_dev = statistics.stdev(prices) if len(prices) > 1 else 0
        
        # Distribution by price ranges
        ranges = [
            (0, 25, "$0-$25"),
            (25, 50, "$25-$50"),
            (50, 100, "$50-$100"),
            (100, 200, "$100-$200"),
            (200, 500, "$200-$500"),
            (500, 1000, "$500-$1,000"),
            (1000, float('inf'), "$1,000+")
        ]
        
        distribution = []
        for min_val, max_val, label in ranges:
            count = len([p for p in prices if min_val <= p < max_val])
            percentage = (count / n * 100) if n > 0 else 0
            distribution.append({
                'range': label,
                'count': count,
                'percentage': round(percentage, 2)
            })
        
        # Separate by status
        active_prices = [PriceAnalyzer.clean_price(item.get('price')) for item in items 
                         if item.get('status') == 'active']
        active_prices = [p for p in active_prices if p and p > 0]
        
        sold_prices = [PriceAnalyzer.clean_price(item.get('price')) for item in items 
                       if item.get('status') == 'sold']
        sold_prices = [p for p in sold_prices if p and p > 0]
        
        # Category breakdown if available
        category_distribution = []
        if category_analysis:
            for cat in category_analysis[:10]:  # Top 10 categories
                cat_prices = cat.get('pricing', {})
                if cat_prices:
                    category_distribution.append({
                        'category_name': cat.get('category_name', 'Unknown'),
                        'min_price': cat_prices.get('sold', {}).get('min', 0),
                        'max_price': cat_prices.get('sold', {}).get('max', 0),
                        'avg_price': cat_prices.get('sold', {}).get('avg', 0),
                        'median_price': cat_prices.get('sold', {}).get('median', 0),
                        'optimal_price': cat_prices.get('optimal_price', 0)
                    })
        
        return {
            'overall_statistics': {
                'total_items': len(items),
                'valid_prices': n,
                'min_price': round(min_price, 2),
                'max_price': round(max_price, 2),
                'mean_price': round(mean_price, 2),
                'median_price': round(median_price, 2),
                'std_deviation': round(std_dev, 2),
                'quartiles': {
                    'q1': round(q1, 2),
                    'q2_median': round(q2, 2),
                    'q3': round(q3, 2),
                    'iqr': round(iqr, 2)
                },
                'price_range': round(max_price - min_price, 2)
            },
            'distribution_by_range': distribution,
            'active_listings': {
                'count': len(active_prices),
                'min_price': round(min(active_prices), 2) if active_prices else 0,
                'max_price': round(max(active_prices), 2) if active_prices else 0,
                'avg_price': round(statistics.mean(active_prices), 2) if active_prices else 0,
                'median_price': round(statistics.median(active_prices), 2) if active_prices else 0
            },
            'sold_listings': {
                'count': len(sold_prices),
                'min_price': round(min(sold_prices), 2) if sold_prices else 0,
                'max_price': round(max(sold_prices), 2) if sold_prices else 0,
                'avg_price': round(statistics.mean(sold_prices), 2) if sold_prices else 0,
                'median_price': round(statistics.median(sold_prices), 2) if sold_prices else 0
            },
            'category_breakdown': category_distribution
        }
    
    def _generate_competition_analysis_report(self, items: List[Dict], category_analysis: List[Dict] = None, 
                                            seller_report: Dict = None) -> Dict:
        """Generate competition analysis report"""
        active_items = [i for i in items if i.get('status') == 'active']
        sold_items = [i for i in items if i.get('status') == 'sold']
        
        # Seller concentration
        seller_counts = Counter([i.get('seller', 'Unknown') for i in active_items])
        seller_counts = {k: v for k, v in seller_counts.items() if k != 'Unknown'}
        
        total_sellers = len(seller_counts)
        top_10_sellers = dict(list(sorted(seller_counts.items(), key=lambda x: x[1], reverse=True))[:10])
        top_10_percentage = (sum(top_10_sellers.values()) / len(active_items) * 100) if active_items else 0
        
        # Market concentration (HHI-like metric)
        if active_items and seller_counts:
            market_shares = [count / len(active_items) * 100 for count in seller_counts.values()]
            hhi = sum(share ** 2 for share in market_shares)  # Herfindahl-Hirschman Index approximation
        else:
            hhi = 0
        
        # Competition level assessment
        if len(active_items) < 10:
            competition_level = "Low"
            competition_color = "green"
        elif len(active_items) < 30:
            competition_level = "Medium"
            competition_color = "yellow"
        else:
            competition_level = "High"
            competition_color = "red"
        
        # Category-level competition
        category_competition = []
        if category_analysis:
            for cat in category_analysis:
                active_count = cat.get('active_count', 0)
                sold_count = cat.get('sold_count', 0)
                total = active_count + sold_count
                
                if total > 0:
                    sell_through = (sold_count / total * 100) if total > 0 else 0
                    
                    # Competition assessment per category
                    if active_count < 5:
                        cat_competition = "Low"
                    elif active_count < 15:
                        cat_competition = "Medium"
                    else:
                        cat_competition = "High"
                    
                    category_competition.append({
                        'category_name': cat.get('category_name', 'Unknown'),
                        'active_listings': active_count,
                        'sold_listings': sold_count,
                        'sell_through_rate': round(sell_through, 2),
                        'competition_level': cat_competition,
                        'opportunity_score': cat.get('opportunity_score', 0)
                    })
        
        # Geographic distribution (if location data available)
        locations = Counter([i.get('location', '') for i in active_items if i.get('location')])
        top_locations = dict(list(sorted(locations.items(), key=lambda x: x[1], reverse=True))[:5])
        
        # Price competitiveness
        active_prices = [PriceAnalyzer.clean_price(i.get('price')) for i in active_items]
        active_prices = [p for p in active_prices if p and p > 0]
        
        sold_prices = [PriceAnalyzer.clean_price(i.get('price')) for i in sold_items]
        sold_prices = [p for p in sold_prices if p and p > 0]
        
        price_competitiveness = {}
        if active_prices and sold_prices:
            avg_active = statistics.mean(active_prices)
            avg_sold = statistics.mean(sold_prices)
            price_premium = ((avg_active - avg_sold) / avg_sold * 100) if avg_sold > 0 else 0
            
            price_competitiveness = {
                'avg_active_price': round(avg_active, 2),
                'avg_sold_price': round(avg_sold, 2),
                'price_premium_percentage': round(price_premium, 2),
                'competitiveness': 'Competitive' if price_premium < 10 else 'Moderate' if price_premium < 25 else 'High Premium'
            }
        
        return {
            'overall_competition': {
                'total_active_listings': len(active_items),
                'total_sellers': total_sellers,
                'competition_level': competition_level,
                'competition_color': competition_color,
                'market_concentration_hhi': round(hhi, 2),
                'top_10_sellers_market_share': round(top_10_percentage, 2)
            },
            'seller_concentration': {
                'total_unique_sellers': total_sellers,
                'top_10_sellers': top_10_sellers,
                'concentration_risk': 'High' if top_10_percentage > 50 else 'Medium' if top_10_percentage > 30 else 'Low'
            },
            'category_competition': sorted(category_competition, key=lambda x: x['competition_level'], reverse=True),
            'geographic_distribution': {
                'unique_locations': len(locations),
                'top_locations': top_locations
            },
            'price_competitiveness': price_competitiveness,
            'market_saturation': {
                'active_to_sold_ratio': round(len(active_items) / len(sold_items), 2) if sold_items else 0,
                'saturation_level': 'Oversaturated' if len(active_items) > len(sold_items) * 2 else 
                                   'Balanced' if len(active_items) <= len(sold_items) * 1.5 else 'Undersaturated'
            }
        }
    
    def _generate_category_performance_report(self, category_analysis: List[Dict], items: List[Dict]) -> Dict:
        """Generate category performance report with ROI estimates"""
        performance_data = []
        
        for cat in category_analysis:
            cat_name = cat.get('category_name', 'Unknown')
            active_count = cat.get('active_count', 0)
            sold_count = cat.get('sold_count', 0)
            total = active_count + sold_count
            
            if total == 0:
                continue
            
            pricing = cat.get('pricing', {})
            sold_pricing = pricing.get('sold', {})
            active_pricing = pricing.get('active', {})
            
            avg_sold_price = sold_pricing.get('avg', 0)
            avg_active_price = active_pricing.get('avg', 0)
            optimal_price = pricing.get('optimal_price', 0)
            avg_shipping = pricing.get('avg_shipping', 0)
            
            sell_through_rate = cat.get('sell_through_rate', 0)
            opportunity_score = cat.get('opportunity_score', 0)
            
            # Calculate ROI estimates (simplified model)
            # Assume eBay fees: ~13% + $0.30 per listing
            estimated_fees = (optimal_price * 0.13) + 0.30 if optimal_price > 0 else 0
            estimated_net_per_item = optimal_price - estimated_fees - avg_shipping if optimal_price > 0 else 0
            
            # Estimated monthly sales based on sell-through rate
            # Assume items listed for ~30 days average
            estimated_monthly_sales = (sold_count / 30) if sold_count > 0 else 0
            estimated_monthly_revenue = estimated_monthly_sales * optimal_price if optimal_price > 0 else 0
            estimated_monthly_profit = estimated_monthly_sales * estimated_net_per_item if estimated_net_per_item > 0 else 0
            
            # ROI percentage (simplified)
            # Assume average cost basis is 50% of selling price (adjustable)
            assumed_cost_basis = optimal_price * 0.5 if optimal_price > 0 else 0
            roi_percentage = ((optimal_price - assumed_cost_basis - estimated_fees - avg_shipping) / 
                            assumed_cost_basis * 100) if assumed_cost_basis > 0 else 0
            
            # Performance rating
            if opportunity_score >= 70 and sell_through_rate >= 50:
                performance_rating = "Excellent"
            elif opportunity_score >= 50 and sell_through_rate >= 30:
                performance_rating = "Good"
            elif opportunity_score >= 30:
                performance_rating = "Fair"
            else:
                performance_rating = "Poor"
            
            performance_data.append({
                'category_name': cat_name,
                'category_path': cat.get('category_path', []),
                'metrics': {
                    'active_listings': active_count,
                    'sold_listings': sold_count,
                    'sell_through_rate': round(sell_through_rate, 2),
                    'opportunity_score': round(opportunity_score, 2)
                },
                'pricing': {
                    'avg_sold_price': round(avg_sold_price, 2),
                    'avg_active_price': round(avg_active_price, 2),
                    'optimal_price': round(optimal_price, 2),
                    'avg_shipping': round(avg_shipping, 2)
                },
                'roi_estimates': {
                    'estimated_fees_per_item': round(estimated_fees, 2),
                    'estimated_net_per_item': round(estimated_net_per_item, 2),
                    'estimated_monthly_sales': round(estimated_monthly_sales, 2),
                    'estimated_monthly_revenue': round(estimated_monthly_revenue, 2),
                    'estimated_monthly_profit': round(estimated_monthly_profit, 2),
                    'roi_percentage': round(roi_percentage, 2)
                },
                'performance_rating': performance_rating
            })
        
        # Sort by opportunity score
        performance_data.sort(key=lambda x: x['metrics']['opportunity_score'], reverse=True)
        
        # Calculate overall statistics
        total_categories = len(performance_data)
        avg_opportunity_score = statistics.mean([p['metrics']['opportunity_score'] for p in performance_data]) if performance_data else 0
        avg_sell_through = statistics.mean([p['metrics']['sell_through_rate'] for p in performance_data]) if performance_data else 0
        avg_roi = statistics.mean([p['roi_estimates']['roi_percentage'] for p in performance_data]) if performance_data else 0
        
        return {
            'summary': {
                'total_categories_analyzed': total_categories,
                'avg_opportunity_score': round(avg_opportunity_score, 2),
                'avg_sell_through_rate': round(avg_sell_through, 2),
                'avg_roi_percentage': round(avg_roi, 2)
            },
            'top_performers': performance_data[:10],  # Top 10
            'all_categories': performance_data,
            'performance_distribution': {
                'excellent': len([p for p in performance_data if p['performance_rating'] == 'Excellent']),
                'good': len([p for p in performance_data if p['performance_rating'] == 'Good']),
                'fair': len([p for p in performance_data if p['performance_rating'] == 'Fair']),
                'poor': len([p for p in performance_data if p['performance_rating'] == 'Poor'])
            }
        }
    
    def _generate_time_based_analysis_report(self, items: List[Dict], category_analysis: List[Dict] = None,
                                           analysis_timestamp: str = None) -> Dict:
        """Generate time-based analysis report (trends and patterns)"""
        # Since we don't have exact dates, we'll use sold vs active as a proxy
        # Sold items are "older" (completed transactions)
        # Active items are "current" (ongoing listings)
        
        active_items = [i for i in items if i.get('status') == 'active']
        sold_items = [i for i in items if i.get('status') == 'sold']
        
        # Current vs historical comparison
        active_prices = [PriceAnalyzer.clean_price(i.get('price')) for i in active_items]
        active_prices = [p for p in active_prices if p and p > 0]
        
        sold_prices = [PriceAnalyzer.clean_price(i.get('price')) for i in sold_items]
        sold_prices = [p for p in sold_prices if p and p > 0]
        
        # Price trend analysis
        price_trend = {}
        if active_prices and sold_prices:
            avg_active = statistics.mean(active_prices)
            avg_sold = statistics.mean(sold_prices)
            price_change = avg_active - avg_sold
            price_change_percent = (price_change / avg_sold * 100) if avg_sold > 0 else 0
            
            price_trend = {
                'current_avg_price': round(avg_active, 2),
                'historical_avg_price': round(avg_sold, 2),
                'price_change': round(price_change, 2),
                'price_change_percent': round(price_change_percent, 2),
                'trend': 'Increasing' if price_change > 0 else 'Decreasing' if price_change < 0 else 'Stable'
            }
        
        # Volume trends
        volume_trend = {
            'current_active_listings': len(active_items),
            'historical_sold_listings': len(sold_items),
            'active_to_sold_ratio': round(len(active_items) / len(sold_items), 2) if sold_items else 0,
            'market_activity': 'High' if len(active_items) > len(sold_items) else 
                            'Moderate' if len(active_items) > len(sold_items) * 0.5 else 'Low'
        }
        
        # Category trends
        category_trends = []
        if category_analysis:
            for cat in category_analysis[:10]:  # Top 10 categories
                active_count = cat.get('active_count', 0)
                sold_count = cat.get('sold_count', 0)
                sell_through = cat.get('sell_through_rate', 0)
                
                cat_pricing = cat.get('pricing', {})
                active_avg = cat_pricing.get('active', {}).get('avg', 0)
                sold_avg = cat_pricing.get('sold', {}).get('avg', 0)
                
                if sold_count > 0:
                    price_change_cat = active_avg - sold_avg if active_avg > 0 and sold_avg > 0 else 0
                    price_change_pct = (price_change_cat / sold_avg * 100) if sold_avg > 0 else 0
                    
                    category_trends.append({
                        'category_name': cat.get('category_name', 'Unknown'),
                        'active_listings': active_count,
                        'sold_listings': sold_count,
                        'sell_through_rate': round(sell_through, 2),
                        'current_avg_price': round(active_avg, 2),
                        'historical_avg_price': round(sold_avg, 2),
                        'price_change_percent': round(price_change_pct, 2),
                        'trend': 'Growing' if sell_through > 50 and price_change_pct > 0 else 
                                'Stable' if sell_through > 30 else 'Declining'
                    })
        
        # Market velocity (simplified)
        # Higher sell-through rate = faster market
        market_velocity = {}
        if category_analysis:
            avg_sell_through = statistics.mean([c.get('sell_through_rate', 0) for c in category_analysis])
            total_active = sum([c.get('active_count', 0) for c in category_analysis])
            total_sold = sum([c.get('sold_count', 0) for c in category_analysis])
            
            if total_active + total_sold > 0:
                overall_sell_through = (total_sold / (total_active + total_sold) * 100)
                
                if overall_sell_through >= 60:
                    velocity = "Very Fast"
                elif overall_sell_through >= 40:
                    velocity = "Fast"
                elif overall_sell_through >= 25:
                    velocity = "Moderate"
                else:
                    velocity = "Slow"
                
                market_velocity = {
                    'overall_sell_through_rate': round(overall_sell_through, 2),
                    'avg_category_sell_through': round(avg_sell_through, 2),
                    'velocity': velocity,
                    'total_transactions': total_active + total_sold
                }
        
        # Seasonal indicators (placeholder - would need actual dates)
        # This is a simplified version based on current market activity
        seasonal_analysis = {
            'note': 'Full seasonal analysis requires date-stamped data',
            'current_market_activity': volume_trend.get('market_activity', 'Unknown'),
            'recommendation': 'Monitor trends over multiple months for accurate seasonal patterns'
        }
        
        return {
            'analysis_timestamp': analysis_timestamp or datetime.now().isoformat(),
            'price_trends': price_trend,
            'volume_trends': volume_trend,
            'category_trends': category_trends,
            'market_velocity': market_velocity,
            'seasonal_analysis': seasonal_analysis,
            'insights': {
                'price_momentum': price_trend.get('trend', 'Unknown'),
                'market_health': 'Healthy' if volume_trend.get('active_to_sold_ratio', 0) < 2 else 'Saturated',
                'best_performing_categories': [c['category_name'] for c in category_trends 
                                              if c.get('trend') == 'Growing'][:5]
            }
        }
    
    def _generate_reports_summary(self, report: Dict) -> Dict:
        """Generate summary of all available and generated reports"""
        
        # Check what's in the report
        has_seller_report = 'seller_report' in report
        has_category_analysis = 'categories' in report
        has_nested_categories = 'nested_categories' in report
        has_top_opportunities = 'top_opportunities' in report
        has_market_overview = 'market_overview' in report
        has_data_summary = 'data_summary' in report
        has_price_distribution = 'price_distribution_report' in report
        has_competition_analysis = 'competition_analysis_report' in report
        has_category_performance = 'category_performance_report' in report
        has_time_analysis = 'time_based_analysis_report' in report
        
        # List of all available reports
        all_reports = [
            {
                'name': 'Data Summary Report',
                'description': 'Overview of scraped items, duplicates, and filtering statistics',
                'generated': has_data_summary,
                'key': 'data_summary'
            },
            {
                'name': 'Category Analysis Report',
                'description': 'Detailed analysis of each category with pricing, demand, and opportunity scores',
                'generated': has_category_analysis,
                'key': 'categories'
            },
            {
                'name': 'Nested Categories Report',
                'description': 'Full hierarchical category structure with items organized by eBay categories',
                'generated': has_nested_categories,
                'key': 'nested_categories'
            },
            {
                'name': 'Top Opportunities Report',
                'description': 'Top 5 categories ranked by opportunity score with recommendations',
                'generated': has_top_opportunities,
                'key': 'top_opportunities'
            },
            {
                'name': 'Market Overview Report',
                'description': 'Overall market statistics including sell-through rates and average opportunity scores',
                'generated': has_market_overview,
                'key': 'market_overview'
            },
            {
                'name': 'Seller Report',
                'description': 'Analysis of sellers including top sellers by volume, ratings, and seller statistics',
                'generated': has_seller_report,
                'key': 'seller_report'
            },
            {
                'name': 'Recommendations Report',
                'description': 'Best category recommendations and strategic suggestions',
                'generated': 'recommendations' in report,
                'key': 'recommendations'
            },
            {
                'name': 'Price Distribution Report',
                'description': 'Price ranges, quartiles, and distribution analysis across all categories',
                'generated': has_price_distribution,
                'key': 'price_distribution_report'
            },
            {
                'name': 'Competition Analysis Report',
                'description': 'Analysis of competitor activity and market saturation',
                'generated': has_competition_analysis,
                'key': 'competition_analysis_report'
            },
            {
                'name': 'Category Performance Report',
                'description': 'Performance metrics for each category including ROI estimates',
                'generated': has_category_performance,
                'key': 'category_performance_report'
            },
            {
                'name': 'Time-based Analysis Report',
                'description': 'Trends over time, seasonal patterns, and recent activity',
                'generated': has_time_analysis,
                'key': 'time_based_analysis_report'
            }
        ]
        
        # Filter generated reports
        generated_reports = [r for r in all_reports if r['generated']]
        
        # Reports that can be generated (have data but not yet generated)
        can_generate = [
            {
                'name': 'Shipping Cost Analysis',
                'description': 'Analysis of shipping costs by category and seller',
                'generated': False,
                'key': 'shipping_analysis',
                'requires': ['categories']
            },
            {
                'name': 'Condition Analysis Report',
                'description': 'Breakdown of items by condition (new, used, refurbished, etc.)',
                'generated': False,
                'key': 'condition_analysis',
                'requires': ['data_summary']
            },
            {
                'name': 'Location Analysis Report',
                'description': 'Geographic distribution of sellers and items',
                'generated': False,
                'key': 'location_analysis',
                'requires': ['seller_report']
            }
        ]
        
        return {
            'generated_reports': generated_reports,
            'available_reports': all_reports + can_generate,
            'total_generated': len(generated_reports),
            'total_available': len(all_reports) + len(can_generate)
        }
    
    def _generate_seller_report(self, items: List[Dict]) -> Dict:
        """Generate seller analysis report"""
        seller_stats = defaultdict(lambda: {
            'listings_count': 0,
            'total_value': 0.0,
            'avg_price': 0.0,
            'feedback': '',
            'sold_count': 0,
            'active_count': 0,
            'categories': set(),
            'locations': set()
        })
        
        for item in items:
            seller = item.get('seller', 'Unknown')
            if seller == 'Unknown':
                continue
            
            price = item.get('price', 0)
            status = item.get('status', 'active')
            seller_feedback = item.get('seller_feedback', '')
            location = item.get('location', '')
            category = item.get('category_name', '')
            
            seller_stats[seller]['listings_count'] += 1
            seller_stats[seller]['total_value'] += price
            seller_stats[seller]['avg_price'] = seller_stats[seller]['total_value'] / seller_stats[seller]['listings_count']
            
            if seller_feedback and not seller_stats[seller]['feedback']:
                seller_stats[seller]['feedback'] = seller_feedback
            
            if status == 'sold':
                seller_stats[seller]['sold_count'] += 1
            else:
                seller_stats[seller]['active_count'] += 1
            
            if category:
                seller_stats[seller]['categories'].add(category)
            if location:
                seller_stats[seller]['locations'].add(location)
        
        # Convert to list and calculate metrics
        seller_list = []
        for seller, stats in seller_stats.items():
            if stats['listings_count'] > 0:
                sell_through = (stats['sold_count'] / stats['listings_count'] * 100) if stats['listings_count'] > 0 else 0
                seller_list.append({
                    'seller_name': seller,
                    'listings_count': stats['listings_count'],
                    'sold_count': stats['sold_count'],
                    'active_count': stats['active_count'],
                    'sell_through_rate': round(sell_through, 2),
                    'total_value': round(stats['total_value'], 2),
                    'avg_price': round(stats['avg_price'], 2),
                    'feedback': stats['feedback'],
                    'categories_count': len(stats['categories']),
                    'categories': sorted(list(stats['categories']))[:10],  # Top 10 categories
                    'locations': sorted(list(stats['locations']))[:5]  # Top 5 locations
                })
        
        # Sort by listings count (most active sellers first)
        seller_list.sort(key=lambda x: x['listings_count'], reverse=True)
        
        # Calculate overall stats
        total_sellers = len(seller_list)
        top_sellers = seller_list[:10]  # Top 10 sellers
        
        # Parse feedback ratings
        top_rated_sellers = []
        for seller in seller_list:
            feedback = seller.get('feedback', '')
            if feedback:
                # Extract rating percentage
                rating_match = re.search(r'([\d.]+)%', feedback)
                if rating_match:
                    rating = float(rating_match.group(1))
                    seller['rating_percent'] = rating
                    top_rated_sellers.append(seller)
        
        top_rated_sellers.sort(key=lambda x: x.get('rating_percent', 0), reverse=True)
        top_rated_sellers = top_rated_sellers[:10]
        
        return {
            'total_unique_sellers': total_sellers,
            'top_sellers_by_volume': top_sellers,
            'top_rated_sellers': top_rated_sellers[:10],
            'seller_statistics': {
                'avg_listings_per_seller': round(sum(s['listings_count'] for s in seller_list) / total_sellers, 2) if total_sellers > 0 else 0,
                'sellers_with_100_plus': len([s for s in seller_list if s['listings_count'] >= 100]),
                'sellers_with_50_plus': len([s for s in seller_list if s['listings_count'] >= 50]),
                'high_volume_sellers': len([s for s in seller_list if s['listings_count'] >= 20])
            }
        }
    
    def _generate_main_recommendation(self, category_analysis: List[Dict]) -> str:
        """Generate main recommendation"""
        if not category_analysis:
            return "Insufficient data"
        
        best = category_analysis[0]
        category = best['category_name']
        score = best['opportunity_score']
        sold = best['sold_count']
        price = best['pricing'].get('optimal_price', 0)
        
        if score >= 70:
            return f"Excellent opportunity in {category}! {sold} recent sales at ~${price:.2f}. High demand, low competition."
        elif score >= 50:
            return f"Good opportunity in {category}. {sold} sales at ~${price:.2f}. Consider listing."
        elif score >= 30:
            return f"Moderate opportunity in {category}. Price competitively around ${price:.2f}."
        else:
            return f"Limited opportunity. Best category is {category} but demand is low."
    
    def _generate_no_data_report(self) -> Dict:
        """Generate report when no data found"""
        return {
            'vehicle': {'year': self.year, 'make': self.make, 'model': self.model},
            'analysis_timestamp': datetime.now().isoformat(),
            'error': 'No relevant data found',
            'data_summary': {
                'total_items_scraped': 0,
                'unique_items': 0,
                'vehicle_relevant': 0,
                'categories_identified': 0
            },
            'recommendations': {'suggestion': 'No listings found. Try different search terms.'}
        }


# ============================================================================
# PRETTY PRINT
# ============================================================================

def print_report(report: Dict):
    """Pretty print the analysis report"""
    
    print("\n" + "="*80)
    print("EBAY SCRAPER ANALYSIS REPORT")
    print("="*80)
    
    vehicle = report.get('vehicle', {})
    print(f"\n🚗 Vehicle: {vehicle.get('year')} {vehicle.get('make')} {vehicle.get('model')}")
    print(f"📅 Analysis: {report.get('analysis_timestamp', '')[:10]}")
    
    print(f"\n{'─'*80}")
    print("DATA SUMMARY")
    print(f"{'─'*80}")
    ds = report.get('data_summary', {})
    print(f"  Items Scraped:        {ds.get('total_items_scraped', 0):,}")
    print(f"  Duplicates Removed:   {ds.get('duplicates_removed', 0):,}")
    print(f"  Unique Items:         {ds.get('unique_items', 0):,}")
    print(f"  Vehicle Relevant:     {ds.get('vehicle_relevant', 0):,}")
    print(f"  Categories Found:     {ds.get('categories_identified', 0)}")
    
    print(f"\n{'─'*80}")
    print("TOP OPPORTUNITIES")
    print(f"{'─'*80}")
    
    opportunities = report.get('top_opportunities', [])
    for i, opp in enumerate(opportunities[:5], 1):
        print(f"\n  {i}. {opp.get('category_name', 'Unknown')}")
        print(f"     Opportunity Score: {opp.get('opportunity_score', 0)}/100")
        print(f"     Sold/Active: {opp.get('sold_count', 0)}/{opp.get('active_count', 0)}")
        print(f"     Optimal Price: ${opp.get('optimal_price', 0):.2f}")
        print(f"     Avg Shipping: ${opp.get('avg_shipping', 0):.2f}")
        print(f"     Sell-Through: {opp.get('sell_through_rate', 0):.1f}%")
        print(f"     💡 {opp.get('recommendation', '')}")
    
    print(f"\n{'='*80}")
    print("RECOMMENDATION")
    print(f"{'='*80}")
    rec = report.get('recommendations', {})
    print(f"\n💡 {rec.get('suggestion', 'No recommendation')}")
    print(f"\n{'='*80}\n")


# ============================================================================
# EXAMPLE
# ============================================================================
import json
async def example_analysis():
    """Example analysis"""
    
    
    analyzer = ScraperOnlyAnalyzer(
        year=2010,
        make="Toyota",
        model="Prius",
        claude_api_key=Config.CLAUDE_API_KEY,
        search_terms=["2010 Toyota Prius"],
        is_multi_part=True
    )
    
    report = await analyzer.analyze()
    print_report(report)
    with open('report.json', 'w') as f:
        json.dump(report, f)
    return report


if __name__ == "__main__":
    asyncio.run(example_analysis())
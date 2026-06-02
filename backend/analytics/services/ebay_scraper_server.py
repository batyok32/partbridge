"""
Fast eBay Scraper with Proxy Support
Asynchronously scrapes eBay categories and items using rotating proxies
"""

import asyncio
import json
import math
import re
import random
import os
from typing import List, Dict, Optional, Set
from urllib.parse import quote
from datetime import datetime
from playwright.async_api import async_playwright, Browser, Page, BrowserContext
import logging
from playwright_stealth import Stealth, ALL_EVASIONS_DISABLED_KWARGS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ============================================================================
# CONFIGURATION
# ============================================================================

class ProxyConfig:
    """Proxy configuration"""
    SERVER = "http://rp.scrapegw.com:6060"
    USERNAME="pgyzaexnixcmpth-odds-5+100"
    # USERNAME = "pgyzaexnixcmpth-country-us"
    PASSWORD = "3rg8so22zqa5tvt"

    @classmethod
    def get_proxy_config(cls) -> Dict:
        """Get proxy configuration dict"""
        return {
            "server": cls.SERVER,
            "username": cls.USERNAME,
            "password": cls.PASSWORD,
        }


class ScraperConfig:
    """Scraper configuration"""
    HEADLESS = True
    TIMEOUT = 30000
    MAX_CONCURRENT_PAGES = 5
    ITEMS_PER_PAGE = 240
    MAX_PAGES_PER_CATEGORY = 5
    WAIT_STRATEGY = "domcontentloaded"

    # Debug mode: limit leaf categories for faster testing
    DEBUG = False
    MAX_LEAF_CATEGORIES = 3  # Maximum leaf categories (only enforced in DEBUG mode)

    START_CATEGORY = 6000
    TARGET_CATEGORY = 6030

    # Anti-detection features
    USE_STEALTH = True  # Enable playwright-stealth for bot detection evasion
    USE_SESSION_PERSISTENCE = True  # Save and reuse browser sessions
    SESSION_DIR = "./browser_sessions"  # Directory to store session data

    # Human-like behavior simulation
    ENABLE_HUMAN_DELAYS = True  # Add random delays between actions
    MIN_DELAY = 1.0  # Minimum delay in seconds
    MAX_DELAY = 3.0  # Maximum delay in seconds
    ENABLE_MOUSE_MOVEMENTS = True  # Simulate natural mouse movements
    MOUSE_MOVE_STEPS = 10  # Number of steps for mouse movements


# ============================================================================
# HUMAN-LIKE BEHAVIOR HELPERS
# ============================================================================

async def random_delay(min_delay: float = None, max_delay: float = None):
    """Add a random delay to simulate human behavior"""
    if not ScraperConfig.ENABLE_HUMAN_DELAYS:
        return

    min_d = min_delay or ScraperConfig.MIN_DELAY
    max_d = max_delay or ScraperConfig.MAX_DELAY
    delay = random.uniform(min_d, max_d)
    await asyncio.sleep(delay)


async def human_like_mouse_move(page: Page, x: int, y: int):
    """Move mouse in a human-like curved path"""
    if not ScraperConfig.ENABLE_MOUSE_MOVEMENTS:
        await page.mouse.move(x, y)
        return

    # Get current viewport size to start from a random position
    try:
        viewport = page.viewport_size
        start_x = random.randint(0, viewport['width'])
        start_y = random.randint(0, viewport['height'])
    except:
        start_x, start_y = 0, 0

    steps = ScraperConfig.MOUSE_MOVE_STEPS
    for i in range(steps + 1):
        progress = i / steps
        # Add some randomness to the path (curved movement)
        curve_offset_x = random.randint(-20, 20) * (1 - abs(progress - 0.5) * 2)
        curve_offset_y = random.randint(-20, 20) * (1 - abs(progress - 0.5) * 2)

        current_x = start_x + (x - start_x) * progress + curve_offset_x
        current_y = start_y + (y - start_y) * progress + curve_offset_y

        await page.mouse.move(current_x, current_y)
        await asyncio.sleep(random.uniform(0.01, 0.03))


async def human_like_click(page: Page, selector: str):
    """Perform a human-like click with mouse movement and delay"""
    try:
        element = await page.query_selector(selector)
        if element:
            box = await element.bounding_box()
            if box:
                # Click at a random position within the element
                x = box['x'] + box['width'] * random.uniform(0.3, 0.7)
                y = box['y'] + box['height'] * random.uniform(0.3, 0.7)

                await human_like_mouse_move(page, x, y)
                await random_delay(0.1, 0.3)
                await page.mouse.click(x, y)
                await random_delay(0.2, 0.5)
                return True
    except Exception as e:
        logger.debug(f"Human-like click failed: {e}")

    # Fallback to regular click
    try:
        await page.click(selector)
        return True
    except:
        return False


async def random_scroll(page: Page):
    """Perform random scrolling to simulate human behavior"""
    if not ScraperConfig.ENABLE_MOUSE_MOVEMENTS:
        return

    try:
        # Random number of scroll actions
        scroll_count = random.randint(1, 3)
        for _ in range(scroll_count):
            scroll_amount = random.randint(100, 500)
            await page.evaluate(f"window.scrollBy(0, {scroll_amount})")
            await random_delay(0.3, 0.8)
    except Exception as e:
        logger.debug(f"Random scroll failed: {e}")


# ============================================================================
# CATEGORY DATABASE
# ============================================================================

class CategoryDB:
    """In-memory database for categories and subcategories"""

    def __init__(self):
        self.categories = {}
        self.scraped_items = []
        self.specs = {}

    def add_category(self, category_id: str, name: str, url: str,
                    parent_id: Optional[str] = None, is_leaf: bool = False):
        """Add category to database"""
        self.categories[category_id] = {
            'id': category_id,
            'name': name,
            'url': url,
            'parent_id': parent_id,
            'is_leaf': is_leaf,
            'subcategories': [],
            'item_count': 0,
            'scraped': False
        }

        if parent_id and parent_id in self.categories:
            if category_id not in self.categories[parent_id]['subcategories']:
                self.categories[parent_id]['subcategories'].append(category_id)

    def add_items(self, category_id: str, items: List[Dict]):
        """Add scraped items to database"""
        for item in items:
            item['category_id'] = category_id
            self.scraped_items.append(item)

        if category_id in self.categories:
            self.categories[category_id]['item_count'] += len(items)
            self.categories[category_id]['scraped'] = True

    def add_specs(self, category_id: str, specs):
        """Add specs for a category (can be List[str] or List[Dict] with options)"""
        self.specs[category_id] = specs

    def get_category(self, category_id: str) -> Optional[Dict]:
        """Get category data"""
        return self.categories.get(category_id)

    def get_leaf_categories(self) -> List[Dict]:
        """Get all leaf categories"""
        return [cat for cat in self.categories.values() if cat['is_leaf']]

    def get_unscraped_leaf_categories(self) -> List[Dict]:
        """Get leaf categories that haven't been scraped yet"""
        return [cat for cat in self.categories.values()
                if cat['is_leaf'] and not cat['scraped']]

    def export_to_json(self, filepath: str, query: str = ""):
        """Export database to JSON file"""
        report = self._generate_rich_report(query)
        with open(filepath, 'w') as f:
            json.dump(report, f, indent=2)
        print(f"   💾 Full report exported to: {filepath}")

    def _generate_rich_report(self, query: str) -> Dict:
        """Generate comprehensive analysis report"""
        import statistics

        active_items = [item for item in self.scraped_items if item.get('listing_type') == 'active']
        sold_items = [item for item in self.scraped_items if item.get('listing_type') == 'sold']
        leaf_cats = self.get_leaf_categories()

        category_analysis = []
        for cat in leaf_cats:
            cat_items = [item for item in self.scraped_items if item.get('category_id') == cat['id']]
            if not cat_items:
                continue

            cat_active = [i for i in cat_items if i.get('listing_type') == 'active']
            cat_sold = [i for i in cat_items if i.get('listing_type') == 'sold']

            pricing = self._analyze_pricing(cat_items, cat_active, cat_sold)

            total_listings = len(cat_active) + len(cat_sold)
            sell_through_rate = (len(cat_sold) / total_listings * 100) if total_listings > 0 else 0

            demand = "high" if len(cat_sold) >= 10 else "medium" if len(cat_sold) >= 5 else "low"
            competition = "high" if len(cat_active) >= 30 else "medium" if len(cat_active) >= 15 else "low"

            opportunity_score = self._calculate_opportunity_score(
                len(cat_sold), len(cat_active), pricing.get('optimal_price', 0)
            )

            # Generate word frequency analysis for this category
            word_frequency = self._generate_word_frequency_analysis(cat_items, query)

            category_analysis.append({
                'category_id': cat['id'],
                'category_name': cat['name'],
                'category_url': cat['url'],
                'total_items': len(cat_items),
                'active_count': len(cat_active),
                'sold_count': len(cat_sold),
                'sell_through_rate': round(sell_through_rate, 2),
                'demand_level': demand,
                'competition_level': competition,
                'pricing': pricing,
                'opportunity_score': opportunity_score,
                'word_frequency_analysis': word_frequency,
                'sample_items': self._format_sample_items(cat_items[:10])
            })

        category_analysis.sort(key=lambda x: x['opportunity_score'], reverse=True)
        top_opportunities = category_analysis[:5]
        suggestion, score = self._generate_main_recommendation(category_analysis)
        report = {
            'query': query,
            'analysis_timestamp': datetime.now().isoformat(),
            'analysis_type': 'proxy_scraper_category_tree',
            'data_summary': {
                'total_categories': len(self.categories),
                'leaf_categories': len(leaf_cats),
                'non_leaf_categories': len(self.categories) - len(leaf_cats),
                'total_items_scraped': len(self.scraped_items),
                'active_listings': len(active_items),
                'sold_listings': len(sold_items),
                'categories_with_items': len(category_analysis),
                'categories_with_specs': len(self.specs) if self.specs else 0
            },
            'category_tree': self._build_category_tree_structure(),
            'categories': category_analysis,
            'top_opportunities': [
                {
                    'category_name': cat['category_name'],
                    'category_id': cat['category_id'],
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
                'total_active': len(active_items),
                'total_sold': len(sold_items),
                'overall_sell_through': (len(sold_items) / (len(active_items) + len(sold_items)) * 100)
                    if (len(active_items) + len(sold_items)) > 0 else 0,
                'avg_opportunity_score': statistics.mean([cat['opportunity_score'] for cat in category_analysis])
                    if category_analysis else 0
            },
            'recommendations': {
                'best_category': top_opportunities[0]['category_name'] if top_opportunities else 'N/A',
                'suggestion': suggestion,
                'score':score
            },
            # 'price_distribution': self._generate_price_distribution(self.scraped_items),
            'condition_breakdown': self._generate_condition_breakdown(self.scraped_items),
            'shipping_analysis': self._generate_shipping_analysis(self.scraped_items),
            'specs_collected': self.specs,
            'scraper_config': {
                'items_per_page': ScraperConfig.ITEMS_PER_PAGE,
                'max_pages_per_category': ScraperConfig.MAX_PAGES_PER_CATEGORY
            }
        }

        # Generate additional reports (same as scraper_analyzer.py)
        relevant_items = self.scraped_items  # All items are relevant for proxy scraper
        
        # Generate seller report first (needed for competition analysis)
        seller_report = self._generate_seller_report(relevant_items, category_analysis)
        
        # Add all additional reports
        report['seller_report'] = seller_report
        report['price_distribution_report'] = self._generate_price_distribution_report(relevant_items, category_analysis)
        report['competition_analysis_report'] = self._generate_competition_analysis_report(
            relevant_items, category_analysis, seller_report
        )
        report['category_performance_report'] = self._generate_category_performance_report(category_analysis, relevant_items)
        report['time_based_analysis_report'] = self._generate_time_based_analysis_report(
            relevant_items, category_analysis, datetime.now().isoformat()
        )
        report['car_disassembly_profitability_report'] = self._generate_car_disassembly_profitability_report(
            category_analysis, relevant_items
        )
        report['reports_summary'] = self._generate_reports_summary(report)

        return report

    def _build_category_tree_structure(self) -> List[Dict]:
        """Build nested category tree structure"""
        root_cats = [c for c in self.categories.values() if c['parent_id'] is None]

        def build_node(cat_id):
            cat = self.categories.get(cat_id)
            if not cat:
                return None

            node = {
                'id': cat['id'],
                'name': cat['name'],
                'is_leaf': cat['is_leaf'],
                'item_count': cat['item_count'],
                'subcategories': []
            }

            for subcat_id in cat.get('subcategories', []):
                subnode = build_node(subcat_id)
                if subnode:
                    node['subcategories'].append(subnode)

            return node

        tree = []
        for root_cat in root_cats:
            node = build_node(root_cat['id'])
            if node:
                tree.append(node)

        return tree

    def _analyze_pricing(self, items: List[Dict], active: List[Dict], sold: List[Dict]) -> Dict:
        """Analyze pricing for a category"""
        import statistics

        result = {
            'active': {},
            'sold': {},
            'optimal_price': 0,
            'avg_shipping': 0,
            'recommendation': ''
        }

        active_prices = [i['price'] for i in active if i.get('price', 0) > 0]
        sold_prices = [i['price'] for i in sold if i.get('price', 0) > 0]

        shipping_costs = [i.get('shipping_cost', 0) for i in items if i.get('shipping_cost', 0) > 0]
        result['avg_shipping'] = statistics.mean(shipping_costs) if shipping_costs else 0.0

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
            result['recommendation'] = f"No sold data. Active listings range ${min(active_prices):.2f}-${max(active_prices):.2f}"

        return result

    def _calculate_opportunity_score(self, sold_count: int, active_count: int, optimal_price: float) -> int:
        """Calculate opportunity score (0-100) based on demand, competition, and price
        
        Scoring breakdown:
        - Demand (sold items): 0-40 points
        - Competition (active items - lower is better): 0-30 points  
        - Price (optimal price): 0-30 points
        Total: 0-100 points
        """
        # Handle None/invalid values
        sold_count = sold_count or 0
        active_count = active_count or 0
        optimal_price = optimal_price or 0.0
        
        # Ensure non-negative
        sold_count = max(0, int(sold_count))
        active_count = max(0, int(active_count))
        optimal_price = max(0.0, float(optimal_price))
        
        score = 0
        
        # 1. DEMAND SCORING (0-40 points) - based on sold_count
        # Higher demand = more points
        if sold_count >= 20:
            score += 40  # Excellent demand
        elif sold_count >= 10:
            score += 35  # Very good demand
        elif sold_count >= 5:
            score += 25  # Good demand
        elif sold_count >= 3:
            score += 15  # Moderate demand
        elif sold_count >= 1:
            score += 5   # Low demand
        # 0 sold = 0 points for demand
        
        # 2. COMPETITION SCORING (0-30 points) - based on active_count
        # Lower competition = more points (inverse relationship)
        if active_count == 0:
            score += 30  # No competition (rare but best)
        elif active_count < 5:
            score += 30  # Very low competition
        elif active_count < 10:
            score += 25  # Low competition
        elif active_count < 15:
            score += 20  # Moderate-low competition
        elif active_count < 25:
            score += 15  # Moderate competition
        elif active_count < 50:
            score += 10  # Higher competition
        elif active_count < 100:
            score += 5   # High competition
        # 100+ active = 0 points (very competitive)
        
        # 3. PRICE SCORING (0-30 points) - based on optimal_price
        # Higher price (higher value items) = more points
        if optimal_price >= 500:
            score += 30  # Very high value items
        elif optimal_price >= 200:
            score += 25  # High value items
        elif optimal_price >= 100:
            score += 20  # Good value items
        elif optimal_price >= 50:
            score += 15  # Moderate value items
        elif optimal_price >= 25:
            score += 10  # Lower value items
        elif optimal_price >= 10:
            score += 5   # Very low value items
        # < $10 = 0 points (too low value)
        
        # Cap at 100
        return min(100, max(0, score))

    def _format_sample_items(self, items: List[Dict]) -> List[Dict]:
        """Format items for display"""
        return [
            {
                'title': item.get('title', '')[:100],
                'price': item.get('price', 0),
                'shipping': item.get('shipping_cost', 0),
                'listing_type': item.get('listing_type'),
                'condition': item.get('condition', ''),
                'url': item.get('url', '')
            }
            for item in items
        ]

    def _extract_car_details_from_query(self, query: str) -> Dict[str, Set[str]]:
        """Extract year, make, and model from query to exclude from word analysis"""
        from collections import defaultdict
        
        query_lower = query.lower()
        exclude_words = {
            'car', 'truck', 'vehicle', 'parts', 'accessories', 'part',
            'for', 'the', 'a', 'an', 'and', 'or', 'of', 'in', 'on', 'at', 'to', 'from',
            'used', 'new', 'oem', 'genuine', 'original', 'aftermarket',
            'left', 'right', 'front', 'rear', 'driver', 'passenger',
            'side', 'l', 'r', 'lh', 'rh', 'l/r', 'left/right'
        }
        
        # Common car years (1900-2030)
        years = set()
        year_pattern = r'\b(19\d{2}|20\d{2})\b'
        year_matches = re.findall(year_pattern, query)
        years.update(year_matches)
        
        # Common car makes (case-insensitive match)
        common_makes = {
            'toyota', 'honda', 'ford', 'chevrolet', 'chev', 'gmc', 'dodge', 'ram',
            'nissan', 'hyundai', 'kia', 'mazda', 'subaru', 'jeep', 'bmw', 'mercedes',
            'benz', 'audi', 'volkswagen', 'vw', 'volvo', 'lexus', 'acura', 'infiniti',
            'cadillac', 'buick', 'lincoln', 'chrysler', 'tesla', 'porsche', 'jaguar',
            'land rover', 'mini', 'fiat', 'alfa romeo', 'mitsubishi', 'isuzu'
        }
        
        makes = set()
        query_words = query_lower.split()
        for make in common_makes:
            # Check if make appears as a word or part of compound word
            if make in query_lower:
                # Extract the make word(s)
                if ' ' in make:
                    # Multi-word make like "land rover"
                    if make in query_lower:
                        makes.add(make)
                else:
                    # Single word make
                    if make in query_words:
                        makes.add(make)
        
        # Common car models - try to extract from query
        # Models are trickier, but we can look for common model patterns
        models = set()
        # Look for words after make (common pattern: "Toyota Prius")
        if makes:
            for make in makes:
                make_pos = query_lower.find(make)
                if make_pos >= 0:
                    # Get text after make
                    after_make = query_lower[make_pos + len(make):].strip()
                    if after_make:
                        # First 1-2 words after make might be model
                        words_after = after_make.split()[:2]
                        for word in words_after:
                            if word and len(word) > 2 and word not in exclude_words:
                                models.add(word)
        
        return {
            'years': years,
            'makes': makes,
            'models': models,
            'exclude_words': exclude_words
        }

    def _generate_word_frequency_analysis(self, items: List[Dict], query: str) -> Dict:
        """Generate word frequency analysis for items, excluding car year, make, and model"""
        from collections import Counter
        
        # Extract car details to exclude
        car_details = self._extract_car_details_from_query(query)
        exclude_all = set()
        exclude_all.update(car_details['years'])
        exclude_all.update(car_details['makes'])
        exclude_all.update(car_details['models'])
        exclude_all.update(car_details['exclude_words'])
        
        # Normalize exclude words to lowercase for comparison
        exclude_all_lower = {w.lower() for w in exclude_all}
        
        # Collect all words from titles
        word_counter = Counter()
        total_titles = 0
        
        for item in items:
            title = item.get('title', '')
            if not title:
                continue
            
            total_titles += 1
            
            # Clean and split title into words
            # Remove special characters but keep alphanumeric and some symbols
            title_clean = re.sub(r'[^\w\s&-]', ' ', title.lower())
            # Split on whitespace and remove empty strings
            words = [w.strip() for w in title_clean.split() if w.strip()]
            
            # Filter out excluded words and very short words
            filtered_words = []
            for word in words:
                # Remove common suffixes/prefixes if they make the word too short
                word_clean = word.strip('.,!?;:()[]{}"\'-_')
                if len(word_clean) < 2:
                    continue
                # Check if word should be excluded
                if word_clean.lower() in exclude_all_lower:
                    continue
                # Skip numbers that are likely years or part numbers
                if word_clean.isdigit():
                    # Exclude if it's a 4-digit number (likely a year)
                    if len(word_clean) == 4:
                        continue
                    # Exclude very long numbers (likely part numbers)
                    if len(word_clean) > 6:
                        continue
                filtered_words.append(word_clean.lower())
            
            # Count words
            word_counter.update(filtered_words)
        
        # Get top words
        top_words = word_counter.most_common(50)  # Top 50 words
        
        # Calculate statistics
        total_words = sum(word_counter.values())
        unique_words = len(word_counter)
        
        # Word frequency distribution
        word_freq_ranges = {
            'very_high': 0,  # 50+ occurrences
            'high': 0,       # 20-49 occurrences
            'medium': 0,     # 10-19 occurrences
            'low': 0,        # 5-9 occurrences
            'very_low': 0    # 1-4 occurrences
        }
        
        for word, count in word_counter.items():
            if count >= 50:
                word_freq_ranges['very_high'] += 1
            elif count >= 20:
                word_freq_ranges['high'] += 1
            elif count >= 10:
                word_freq_ranges['medium'] += 1
            elif count >= 5:
                word_freq_ranges['low'] += 1
            else:
                word_freq_ranges['very_low'] += 1
        
        return {
            'total_titles_analyzed': total_titles,
            'total_words': total_words,
            'unique_words': unique_words,
            'average_words_per_title': round(total_words / total_titles, 2) if total_titles > 0 else 0,
            'top_words': [
                {
                    'word': word,
                    'count': count,
                    'percentage': round((count / total_words * 100) if total_words > 0 else 0, 2)
                }
                for word, count in top_words
            ],
            'word_frequency_distribution': word_freq_ranges,
            'excluded_terms': {
                'years': sorted(list(car_details['years'])),
                'makes': sorted(list(car_details['makes'])),
                'models': sorted(list(car_details['models']))
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
            return f"Excellent opportunity in {category}! {sold} recent sales at ~${price:.2f}. High demand, low competition.", score
        elif score >= 50:
            return f"Good opportunity in {category}. {sold} sales at ~${price:.2f}. Consider listing.", score
        elif score >= 30:
            return f"Moderate opportunity in {category}. Price competitively around ${price:.2f}.", score
        else:
            return f"Limited opportunity. Best category is {category} but demand is low.", score

    def _generate_price_distribution(self, items: List[Dict]) -> Dict:
        """Generate price distribution analysis"""
        prices = [item['price'] for item in items if item.get('price', 0) > 0]

        if not prices:
            return {}

        import statistics

        return {
            'total_items_with_price': len(prices),
            'min': float(min(prices)),
            'max': float(max(prices)),
            'mean': float(statistics.mean(prices)),
            'median': float(statistics.median(prices)),
            'ranges': {
                'under_25': len([p for p in prices if p < 25]),
                '25_to_50': len([p for p in prices if 25 <= p < 50]),
                '50_to_100': len([p for p in prices if 50 <= p < 100]),
                '100_to_250': len([p for p in prices if 100 <= p < 250]),
                'over_250': len([p for p in prices if p >= 250])
            }
        }

    def _generate_condition_breakdown(self, items: List[Dict]) -> Dict:
        """Generate condition breakdown"""
        conditions = {}
        for item in items:
            cond = item.get('condition', 'Unknown')
            conditions[cond] = conditions.get(cond, 0) + 1

        total = len(items)
        return {
            condition: {
                'count': count,
                'percentage': round((count / total * 100) if total > 0 else 0, 2)
            }
            for condition, count in conditions.items()
        }

    def _generate_shipping_analysis(self, items: List[Dict]) -> Dict:
        """Generate shipping analysis"""
        import statistics

        shipping_costs = [item.get('shipping_cost', 0) for item in items if item.get('shipping_cost', 0) > 0]
        free_shipping = len(items) - len(shipping_costs)

        return {
            'total_items': len(items),
            'free_shipping_count': free_shipping,
            'free_shipping_percentage': round((free_shipping / len(items) * 100) if items else 0, 2),
            'paid_shipping_count': len(shipping_costs),
            'avg_shipping_cost': round(statistics.mean(shipping_costs), 2) if shipping_costs else 0,
            'min_shipping': round(min(shipping_costs), 2) if shipping_costs else 0,
            'max_shipping': round(max(shipping_costs), 2) if shipping_costs else 0
        }

    def _clean_price(self, price_value) -> Optional[float]:
        """Convert price to float (helper method)"""
        if price_value is None:
            return None
        if isinstance(price_value, (int, float)):
            return float(price_value)
        import re
        cleaned = re.sub(r'[^\d.]', '', str(price_value))
        try:
            return float(cleaned)
        except (ValueError, TypeError):
            return None

    def _generate_seller_report(self, items: List[Dict], category_analysis: List[Dict] = None) -> Dict:
        """Generate seller analysis report"""
        from collections import defaultdict
        import re
        
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
            
            price = self._clean_price(item.get('price', 0)) or 0
            listing_type = item.get('listing_type', 'active')  # proxy scraper uses listing_type
            seller_feedback = item.get('seller_feedback', '')
            location = item.get('location', '')
            category_id = item.get('category_id', '')
            
            # Find category name
            category_name = ''
            if category_id:
                cat = self.get_category(category_id)
                if cat:
                    category_name = cat.get('name', '')
            
            seller_stats[seller]['listings_count'] += 1
            seller_stats[seller]['total_value'] += price
            seller_stats[seller]['avg_price'] = seller_stats[seller]['total_value'] / seller_stats[seller]['listings_count']
            
            if seller_feedback and not seller_stats[seller]['feedback']:
                seller_stats[seller]['feedback'] = seller_feedback
            
            if listing_type == 'sold':
                seller_stats[seller]['sold_count'] += 1
            else:
                seller_stats[seller]['active_count'] += 1
            
            if category_name:
                seller_stats[seller]['categories'].add(category_name)
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
                    'categories': sorted(list(stats['categories']))[:10],
                    'locations': sorted(list(stats['locations']))[:5]
                })
        
        # Sort by listings count
        seller_list.sort(key=lambda x: x['listings_count'], reverse=True)
        
        # Calculate overall stats
        total_sellers = len(seller_list)
        top_sellers = seller_list[:10]
        
        # Parse feedback ratings
        top_rated_sellers = []
        for seller in seller_list:
            feedback = seller.get('feedback', '')
            if feedback:
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
            'top_rated_sellers': top_rated_sellers,
            'seller_statistics': {
                'avg_listings_per_seller': round(sum(s['listings_count'] for s in seller_list) / total_sellers, 2) if total_sellers > 0 else 0,
                'sellers_with_100_plus': len([s for s in seller_list if s['listings_count'] >= 100]),
                'sellers_with_50_plus': len([s for s in seller_list if s['listings_count'] >= 50]),
                'high_volume_sellers': len([s for s in seller_list if s['listings_count'] >= 20])
            }
        }

    def _generate_price_distribution_report(self, items: List[Dict], category_analysis: List[Dict] = None) -> Dict:
        """Generate price distribution report with quartiles and ranges"""
        import statistics
        
        prices = [self._clean_price(item.get('price')) for item in items]
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
        
        # Separate by listing type (proxy scraper uses listing_type instead of status)
        active_prices = [self._clean_price(item.get('price')) for item in items 
                         if item.get('listing_type') == 'active']
        active_prices = [p for p in active_prices if p and p > 0]
        
        sold_prices = [self._clean_price(item.get('price')) for item in items 
                       if item.get('listing_type') == 'sold']
        sold_prices = [p for p in sold_prices if p and p > 0]
        
        # Category breakdown if available
        category_distribution = []
        if category_analysis:
            for cat in category_analysis[:10]:
                cat_pricing = cat.get('pricing', {})
                if cat_pricing:
                    category_distribution.append({
                        'category_name': cat.get('category_name', 'Unknown'),
                        'min_price': cat_pricing.get('sold', {}).get('min', 0),
                        'max_price': cat_pricing.get('sold', {}).get('max', 0),
                        'avg_price': cat_pricing.get('sold', {}).get('avg', 0),
                        'median_price': cat_pricing.get('sold', {}).get('median', 0),
                        'optimal_price': cat_pricing.get('optimal_price', 0)
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
        from collections import Counter
        import statistics
        
        active_items = [i for i in items if i.get('listing_type') == 'active']
        sold_items = [i for i in items if i.get('listing_type') == 'sold']
        
        # Seller concentration
        seller_counts = Counter([i.get('seller', 'Unknown') for i in active_items])
        seller_counts = {k: v for k, v in seller_counts.items() if k != 'Unknown'}
        
        total_sellers = len(seller_counts)
        top_10_sellers = dict(list(sorted(seller_counts.items(), key=lambda x: x[1], reverse=True))[:10])
        top_10_percentage = (sum(top_10_sellers.values()) / len(active_items) * 100) if active_items else 0
        
        # Market concentration (HHI-like metric)
        if active_items and seller_counts:
            market_shares = [count / len(active_items) * 100 for count in seller_counts.values()]
            hhi = sum(share ** 2 for share in market_shares)
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
        
        # Geographic distribution
        locations = Counter([i.get('location', '') for i in active_items if i.get('location')])
        top_locations = dict(list(sorted(locations.items(), key=lambda x: x[1], reverse=True))[:5])
        
        # Price competitiveness
        active_prices = [self._clean_price(i.get('price')) for i in active_items]
        active_prices = [p for p in active_prices if p and p > 0]
        
        sold_prices = [self._clean_price(i.get('price')) for i in sold_items]
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
        import statistics
        
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
            
            # Calculate ROI estimates
            estimated_fees = (optimal_price * 0.13) + 0.30 if optimal_price > 0 else 0
            estimated_net_per_item = optimal_price - estimated_fees - avg_shipping if optimal_price > 0 else 0
            
            estimated_monthly_sales = (sold_count / 30) if sold_count > 0 else 0
            estimated_monthly_revenue = estimated_monthly_sales * optimal_price if optimal_price > 0 else 0
            estimated_monthly_profit = estimated_monthly_sales * estimated_net_per_item if estimated_net_per_item > 0 else 0
            
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
        
        performance_data.sort(key=lambda x: x['metrics']['opportunity_score'], reverse=True)
        
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
            'top_performers': performance_data[:10],
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
        import statistics
        
        active_items = [i for i in items if i.get('listing_type') == 'active']
        sold_items = [i for i in items if i.get('listing_type') == 'sold']
        
        active_prices = [self._clean_price(i.get('price')) for i in active_items]
        active_prices = [p for p in active_prices if p and p > 0]
        
        sold_prices = [self._clean_price(i.get('price')) for i in sold_items]
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
            for cat in category_analysis[:10]:
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
        
        # Market velocity
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

    def _generate_car_disassembly_profitability_report(self, category_analysis: List[Dict], items: List[Dict]) -> Dict:
        """Generate car disassembly profitability report - estimate total revenue and time to sell all parts"""
        import statistics
        
        if not category_analysis:
            return {
                'error': 'No category data available',
                'total_potential_revenue': 0,
                'estimated_time_to_sell_all': 'N/A',
                'parts_breakdown': []
            }
        
        # Calculate per-category metrics
        parts_projection = []
        total_potential_revenue = 0.0
        total_estimated_days = 0.0
        
        for cat in category_analysis:
            cat_name = cat.get('category_name', 'Unknown')
            active_count = cat.get('active_count', 0)
            sold_count = cat.get('sold_count', 0)
            total_listings = active_count + sold_count
            
            if total_listings == 0:
                continue
            
            pricing = cat.get('pricing', {})
            optimal_price = pricing.get('optimal_price', 0)
            avg_shipping = pricing.get('avg_shipping', 0)
            
            if optimal_price <= 0:
                # Try to use sold pricing if optimal_price is 0
                sold_pricing = pricing.get('sold', {})
                if sold_pricing:
                    optimal_price = sold_pricing.get('avg', sold_pricing.get('median', 0))
                if optimal_price <= 0:
                    continue
            
            # Calculate fees and net profit per item
            ebay_fee = optimal_price * 0.1325  # 13.25% eBay fee
            payment_fee = (optimal_price * 0.029) + 0.30  # 2.9% + $0.30 payment processing
            net_per_item = optimal_price - ebay_fee - payment_fee - avg_shipping
            
            # Calculate sell-through rate
            sell_through_rate = (sold_count / total_listings * 100) if total_listings > 0 else 0
            
            # Estimate time to sell this part
            # Based on sell-through rate: higher sell-through = faster sales
            # Assumption: Average listing duration is ~30 days
            # If sell-through is 50%, items sell in ~30 days on average
            # If sell-through is 100%, items sell in ~15 days on average
            # If sell-through is 25%, items sell in ~60 days on average
            
            if sell_through_rate >= 75:
                # High sell-through = fast market (2-4 weeks)
                estimated_days_per_item = 15
            elif sell_through_rate >= 50:
                # Good sell-through = moderate market (4-6 weeks)
                estimated_days_per_item = 30
            elif sell_through_rate >= 25:
                # Moderate sell-through = slower market (6-12 weeks)
                estimated_days_per_item = 60
            elif sell_through_rate >= 10:
                # Low sell-through = slow market (12-24 weeks)
                estimated_days_per_item = 90
            elif sold_count > 0:
                # Very low sell-through but some sales = very slow market
                estimated_days_per_item = 120
            else:
                # No sales data = conservative estimate (6 months)
                estimated_days_per_item = 180
            
            # For parts that typically sell one at a time (most car parts)
            # Assume we sell 1 unit of this part
            parts_to_sell = 1
            gross_revenue = optimal_price * parts_to_sell
            total_fees = (ebay_fee + payment_fee) * parts_to_sell
            net_revenue = net_per_item * parts_to_sell
            estimated_time_days = estimated_days_per_item * parts_to_sell
            
            total_potential_revenue += net_revenue
            total_estimated_days = max(total_estimated_days, estimated_time_days)  # Use max since parts sell in parallel
            
            # Calculate ROI percentage (assuming 50% cost basis)
            cost_basis = optimal_price * 0.5  # Assume we bought the car for parts, cost is 50% of selling price
            roi_percentage = ((net_revenue - cost_basis) / cost_basis * 100) if cost_basis > 0 else 0
            
            parts_projection.append({
                'part_name': cat_name,
                'category_id': cat.get('category_id', ''),
                'gross_price_per_item': round(optimal_price, 2),
                'fees_per_item': round(ebay_fee + payment_fee, 2),
                'shipping_per_item': round(avg_shipping, 2),
                'net_profit_per_item': round(net_per_item, 2),
                'quantity_to_sell': parts_to_sell,
                'total_gross_revenue': round(gross_revenue, 2),
                'total_fees': round(total_fees, 2),
                'total_net_revenue': round(net_revenue, 2),
                'sell_through_rate': round(sell_through_rate, 2),
                'estimated_days_to_sell': round(estimated_time_days, 1),
                'estimated_time_description': self._format_time_description(estimated_time_days),
                'competition_level': cat.get('competition_level', 'Unknown'),
                'demand_level': cat.get('demand_level', 'Unknown'),
                'active_listings': active_count,
                'sold_listings': sold_count,
                'roi_percentage': round(roi_percentage, 2),
                'cost_basis': round(cost_basis, 2)
            })
        
        # Sort by estimated time (fastest sellers first)
        parts_projection.sort(key=lambda x: x['estimated_days_to_sell'])
        
        # Calculate overall metrics
        total_gross_revenue = sum(p['total_gross_revenue'] for p in parts_projection)
        total_fees_all = sum(p['total_fees'] for p in parts_projection)
        total_cost_basis = sum(p['cost_basis'] for p in parts_projection)
        overall_roi = ((total_potential_revenue - total_cost_basis) / total_cost_basis * 100) if total_cost_basis > 0 else 0
        
        # Estimate total time to sell all parts
        # Since parts can be listed simultaneously, time is the maximum of all parts (longest selling part)
        # But also consider that we might list parts in batches
        longest_selling_part = max([p['estimated_days_to_sell'] for p in parts_projection], default=0)
        
        # Alternative calculation: if we list parts in batches of 10, estimate total time
        num_parts = len(parts_projection)
        if num_parts > 0:
            # Assume we can list 10 parts at a time, and each batch takes ~2 weeks to sell
            # This is more realistic than assuming all parts sell simultaneously
            batches_needed = (num_parts + 9) // 10  # Ceiling division
            parallel_time_days = longest_selling_part
            sequential_time_days = batches_needed * 14  # 2 weeks per batch
            # Use the maximum of parallel vs sequential
            estimated_total_days = max(parallel_time_days, sequential_time_days)
        else:
            estimated_total_days = 0
        
        # Group parts by sale timeline
        fast_sellers = [p for p in parts_projection if p['estimated_days_to_sell'] <= 30]
        medium_sellers = [p for p in parts_projection if 30 < p['estimated_days_to_sell'] <= 90]
        slow_sellers = [p for p in parts_projection if p['estimated_days_to_sell'] > 90]
        
        return {
            'summary': {
                'total_parts_available': len(parts_projection),
                'total_gross_revenue': round(total_gross_revenue, 2),
                'total_fees': round(total_fees_all, 2),
                'total_net_revenue': round(total_potential_revenue, 2),
                'total_cost_basis': round(total_cost_basis, 2),
                'total_profit': round(total_potential_revenue - total_cost_basis, 2),
                'overall_roi_percentage': round(overall_roi, 2),
                'estimated_time_to_sell_all_days': round(estimated_total_days, 1),
                'estimated_time_to_sell_all_description': self._format_time_description(estimated_total_days),
                'longest_selling_part_days': round(longest_selling_part, 1),
                'average_days_per_part': round(statistics.mean([p['estimated_days_to_sell'] for p in parts_projection]), 1) if parts_projection else 0
            },
            'timeline_breakdown': {
                'fast_sellers': {
                    'count': len(fast_sellers),
                    'parts': fast_sellers[:10],  # Top 10 fast sellers
                    'total_revenue': round(sum(p['total_net_revenue'] for p in fast_sellers), 2),
                    'estimated_time_days': round(max([p['estimated_days_to_sell'] for p in fast_sellers], default=0), 1)
                },
                'medium_sellers': {
                    'count': len(medium_sellers),
                    'parts': medium_sellers[:10],  # Top 10 medium sellers
                    'total_revenue': round(sum(p['total_net_revenue'] for p in medium_sellers), 2),
                    'estimated_time_days': round(max([p['estimated_days_to_sell'] for p in medium_sellers], default=0), 1)
                },
                'slow_sellers': {
                    'count': len(slow_sellers),
                    'parts': slow_sellers[:10],  # Top 10 slow sellers
                    'total_revenue': round(sum(p['total_net_revenue'] for p in slow_sellers), 2),
                    'estimated_time_days': round(max([p['estimated_days_to_sell'] for p in slow_sellers], default=0), 1)
                }
            },
            'parts_by_profitability': sorted(parts_projection, key=lambda x: x['total_net_revenue'], reverse=True)[:20],
            'parts_by_sale_speed': parts_projection[:20],  # Already sorted by estimated_days_to_sell
            'all_parts': parts_projection,
            'assumptions': {
                'ebay_fee_percentage': 13.25,
                'payment_fee_percentage': 2.9,
                'payment_fee_fixed': 0.30,
                'average_listing_duration_days': 30,
                'cost_basis_percentage': 50,
                'parts_listed_in_batches': 10,
                'batch_processing_time_days': 14
            }
        }
    
    def _format_time_description(self, days: float) -> str:
        """Format days into human-readable time description"""
        days_int = int(days)
        
        if days_int < 7:
            return f"{days_int} day{'s' if days_int != 1 else ''}"
        elif days_int < 30:
            weeks = days_int // 7
            remaining_days = days_int % 7
            if remaining_days == 0:
                return f"{weeks} week{'s' if weeks != 1 else ''}"
            else:
                return f"{weeks} week{'s' if weeks != 1 else ''} {remaining_days} day{'s' if remaining_days != 1 else ''}"
        elif days_int < 365:
            months = days_int // 30
            remaining_days = days_int % 30
            if remaining_days < 7:
                return f"{months} month{'s' if months != 1 else ''}"
            else:
                weeks = remaining_days // 7
                return f"{months} month{'s' if months != 1 else ''} {weeks} week{'s' if weeks != 1 else ''}"
        else:
            years = days_int // 365
            remaining_days = days_int % 365
            months = remaining_days // 30
            if months == 0:
                return f"{years} year{'s' if years != 1 else ''}"
            else:
                return f"{years} year{'s' if years != 1 else ''} {months} month{'s' if months != 1 else ''}"

    def _generate_reports_summary(self, report: Dict) -> Dict:
        """Generate summary of all available and generated reports"""
        
        # Check what's in the report
        has_seller_report = 'seller_report' in report
        has_category_analysis = 'categories' in report
        has_top_opportunities = 'top_opportunities' in report
        has_market_overview = 'market_overview' in report
        has_data_summary = 'data_summary' in report
        has_price_distribution = 'price_distribution_report' in report
        has_competition_analysis = 'competition_analysis_report' in report
        has_category_performance = 'category_performance_report' in report
        has_time_analysis = 'time_based_analysis_report' in report
        
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
            },
            {
                'name': 'Car Disassembly Profitability Report',
                'description': 'Total revenue potential, time to sell all parts, and per-part profitability analysis',
                'generated': 'car_disassembly_profitability_report' in report,
                'key': 'car_disassembly_profitability_report'
            }
        ]
        
        generated_reports = [r for r in all_reports if r['generated']]
        
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
            }
        ]
        
        return {
            'generated_reports': generated_reports,
            'available_reports': all_reports + can_generate,
            'total_generated': len(generated_reports),
            'total_available': len(all_reports) + len(can_generate)
        }


# ============================================================================
# PROXY-BASED SCRAPER
# ============================================================================

class ProxyEbayScraper:
    """Scrape eBay using rotating proxies for each request"""

    def __init__(self, query: str):
        self.query = query
        self.db = CategoryDB()
        self.semaphore = asyncio.Semaphore(ScraperConfig.MAX_CONCURRENT_PAGES)
        self.use_proxy = True
        self.visited_categories = set()

    async def scrape(self) -> CategoryDB:
        """Main scraping pipeline"""
        print(f"\n{'='*80}")
        print(f"🚀 PROXY-BASED EBAY SCRAPER")
        print(f"{'='*80}")
        print(f"Query: '{self.query}'")
        print(f"Scraping: Both ACTIVE and SOLD items")
        print(f"Max concurrent browsers: {ScraperConfig.MAX_CONCURRENT_PAGES}")
        print(f"Items per page: {ScraperConfig.ITEMS_PER_PAGE}")
        print(f"Max pages per category: {ScraperConfig.MAX_PAGES_PER_CATEGORY}")
        print(f"{'='*80}\n")

        async with async_playwright() as p:
            print(f"\n{'='*80}")
            print(f"📂 STEP 1: BUILDING CATEGORY TREE")
            print(f"{'='*80}")
            if ScraperConfig.DEBUG:
                print(f"🐛 DEBUG MODE: Max leaf categories: {ScraperConfig.MAX_LEAF_CATEGORIES}")
            else:
                print(f"🚀 PRODUCTION MODE: No leaf category limit")
            await self._build_category_tree(p)
            leaf_count = len(self.db.get_leaf_categories())
            print(f"\n✅ Category tree complete!")
            print(f"   Total categories: {len(self.db.categories)}")
            print(f"   Leaf categories: {leaf_count}")
            if ScraperConfig.DEBUG and leaf_count >= ScraperConfig.MAX_LEAF_CATEGORIES:
                print(f"   ⚡ Reached max leaf categories limit ({ScraperConfig.MAX_LEAF_CATEGORIES})")
                print(f"   🚀 Going straight to item scraping!")
            print(f"{'='*80}\n")

            print(f"\n{'='*80}")
            print(f"📦 STEP 2: SCRAPING SOLD ITEMS FROM LEAF CATEGORIES")
            print(f"{'='*80}")
            await self._scrape_leaf_categories(p, listing_type='sold')
            sold_count = len(self.db.scraped_items)
            print(f"\n✅ Sold item scraping complete!")
            print(f"   Sold items scraped: {sold_count}")
            print(f"{'='*80}\n")

            print(f"\n{'='*80}")
            print(f"📦 STEP 3: SCRAPING ACTIVE ITEMS FROM LEAF CATEGORIES")
            print(f"{'='*80}")
            await self._scrape_leaf_categories(p, listing_type='active')
            active_count = len(self.db.scraped_items) - sold_count
            print(f"\n✅ Active item scraping complete!")
            print(f"   Active items scraped: {active_count}")
            print(f"   Total items scraped: {len(self.db.scraped_items)}")
            print(f"{'='*80}\n")

        return self.db

    async def _build_category_tree(self, playwright):
        """Build category tree by traversing from root"""
        print(f"🌐 Creating browser with proxy...")

        browser = None
        for attempt in range(3):
            try:
                print(f"   Attempt {attempt + 1}/3 to create browser with proxy...")
                browser = await self._create_browser(playwright, use_proxy=True)
                print(f"✅ Browser created successfully WITH proxy")
                break
            except Exception as e:
                print(f"   ⚠️  Browser creation attempt {attempt + 1} failed: {e}")
                if attempt < 2:
                    print(f"   ⏳ Waiting 3 seconds before retry...")
                    await asyncio.sleep(3)
                else:
                    print(f"   ⚠️  All proxy attempts failed")

        if browser is None:
            print(f"\n   ⚠️  Proxy connection failed. Trying WITHOUT proxy as fallback...")
            try:
                browser = await self._create_browser(playwright, use_proxy=False)
                self.use_proxy = False
                print(f"✅ Browser created successfully WITHOUT proxy (fallback mode)")
                print(f"   ℹ️  All subsequent browsers will run without proxy")
            except Exception as e:
                print(f"   ❌ Failed to create browser even without proxy: {e}")
                raise Exception("Could not create browser with or without proxy")

        try:
            # Create context with session and stealth
            context = await self._create_context_with_session(browser, session_name="ebay_main")
            page = await self._create_page_with_stealth(context)

            print(f"\n🔍 Navigating to eBay...")
            nav_success = False
            for attempt in range(3):
                try:
                    print(f"   Navigation attempt {attempt + 1}/3...")
                    await page.goto("https://www.ebay.com", wait_until="domcontentloaded", timeout=60000)
                    await random_delay(2, 4)  # Human-like delay instead of fixed timeout
                    await random_scroll(page)  # Simulate human scrolling
                    print(f"✅ eBay homepage loaded")
                    nav_success = True
                    break
                except Exception as e:
                    print(f"   ⚠️  Navigation attempt {attempt + 1} failed: {e}")
                    if attempt < 2:
                        print(f"   ⏳ Waiting 3 seconds before retry...")
                        await asyncio.sleep(3)
                    else:
                        print(f"   ❌ Could not navigate to eBay after 3 attempts")
                        raise

            if not nav_success:
                raise Exception("Failed to navigate to eBay")

            print(f"🔍 Searching for: '{self.query}'")
            try:
                await page.click("#gh-ac", timeout=10000)
                await page.fill("#gh-ac", self.query)
                await page.click("#gh-search-btn", timeout=10000)
                print(f"   ⏳ Waiting for search results to load...")
                await page.wait_for_load_state("domcontentloaded", timeout=30000)
                await page.wait_for_timeout(3000)
                print(f"✅ Search completed")
            except Exception as e:
                print(f"   ⚠️  Search execution error: {e}")
                print(f"   Trying alternative approach...")
                search_url = f"https://www.ebay.com/sch/i.html?_nkw={quote(self.query)}"
                await page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
                await random_delay(2, 4)
                await random_scroll(page)
                print(f"✅ Search completed via direct URL")

            
            print(f"\n🎯 Navigating to category {ScraperConfig.TARGET_CATEGORY}...")
            await self._navigate_to_target_category(page)

            print(f"\n⚙️  Setting items per page for discovery...")
            await self._set_items_per_page(page)

            print(f"\n🌳 Starting category tree traversal...")
            current_url = page.url
            print(f"   Starting URL: {current_url}")
            category_id = str(ScraperConfig.TARGET_CATEGORY)
            category_name = "Car & Truck Parts & Accessories"
          
            await self._traverse_categories(
                playwright,
                category_id=category_id,
                category_name=category_name,
                category_url=current_url,
                parent_id=None,
                depth=0
            )

        finally:
            # Save session before closing
            if 'context' in locals():
                await self._save_session(context, session_name="ebay_main")
            print(f"🔒 Closing initial browser...")
            await browser.close()

    async def _navigate_to_target_category(self, page: Page):
        """Navigate through category hierarchy"""
        # print(f"   Looking for category 6000 link...")
        # try:
        #     await page.wait_for_timeout(2000)
        #     cat_link = page.locator('#x-refine__group__0 a[href*="/sch/6000/"]').first
        #     if await cat_link.count() > 0:
        #         print(f"   ✅ Found category 6000 link, clicking...")
        #         await cat_link.click()
        #         await page.wait_for_load_state("domcontentloaded", timeout=30000)
        #         await page.wait_for_timeout(3000)
        #         print(f"   ✅ Clicked category 6000")
        #     else:
        #         print(f"   ⚠️  Category 6000 link not found")
        # except Exception as e:
        #     print(f"   ⚠️  Could not click 6000: {e}")

        print(f"   Looking for category 6030 link...")
        try:
            await page.wait_for_timeout(2000)
            cat_link = page.locator('#x-refine__group__0 a[href*="/sch/6030/"]').first
            if await cat_link.count() > 0:
                print(f"   ✅ Found category 6030 link, clicking...")
                await cat_link.click()
                await page.wait_for_load_state("domcontentloaded", timeout=30000)
                await page.wait_for_timeout(3000)
                print(f"   ✅ Clicked category 6030")
            else:
                print(f"   ⚠️  Category 6030 link not found, using direct navigation...")
                await page.goto(
                    f"https://www.ebay.com/sch/6030/i.html?_nkw={quote(self.query)}",
                    wait_until="domcontentloaded",
                    timeout=30000
                )
                await random_delay(2, 4)
                await random_scroll(page)
                await page.wait_for_timeout(3000)
                print(f"   ✅ Direct navigation to 6030 successful")
        except Exception as e:
            print(f"   ⚠️  Could not navigate to 6030: {e}")

    async def _set_items_per_page(self, page: Page):
        """Set items per page to 240"""
        try:
            print(f"   Looking for items per page dropdown...")
            dropdown_selectors = [
                '.srp-ipp .fake-menu-button__button',
                'button[aria-controls="srp-ipp-menu-content"]'
            ]
            for selector in dropdown_selectors:
                if await page.locator(selector).count() > 0:
                    print(f"   ✅ Found dropdown, clicking...")
                    await page.click(selector)
                    await page.wait_for_timeout(1000)

                    option_selector = f'a[href*="_ipg={ScraperConfig.ITEMS_PER_PAGE}"]'
                    if await page.locator(option_selector).count() > 0:
                        print(f"   ✅ Setting to {ScraperConfig.ITEMS_PER_PAGE} items per page...")
                        await page.click(option_selector)
                        await page.wait_for_load_state("domcontentloaded")
                        await page.wait_for_timeout(2000)
                        print(f"   ✅ Items per page set to {ScraperConfig.ITEMS_PER_PAGE}")
                        return
                    break
            print(f"   ⚠️  Could not set items per page")
        except Exception as e:
            print(f"   ⚠️  Error setting items per page: {e}")

    async def _apply_filters(self, page: Page, listing_type: str):
        """Apply filters (sold items, condition, etc.)"""
        print(f"      ⚙️  Applying filters for {listing_type} items...")

        if listing_type == 'sold':
            try:
                print(f"      Looking for sold items filter...")
                sold_selectors = [
                    'input[aria-label="Sold Items"]',
                    'input[name="LH_Sold"]',
                ]
                for selector in sold_selectors:
                    if await page.locator(selector).count() > 0:
                        print(f"      ✅ Found sold filter, clicking...")
                        await page.locator(selector).first.click()
                        await page.wait_for_load_state("domcontentloaded")
                        await page.wait_for_timeout(2000)
                        print(f"      ✅ Applied sold filter")
                        break
            except Exception as e:
                print(f"      ⚠️  Could not apply sold filter: {e}")

        try:
            print(f"      Looking for used condition filter...")
            used_selectors = [
                'input[aria-label*="Used"]',
                'input[name="LH_ItemCondition"][value="3000"]'
            ]
            for selector in used_selectors:
                if await page.locator(selector).count() > 0:
                    print(f"      ✅ Found used filter, clicking...")
                    await page.click(selector)
                    await page.wait_for_load_state("domcontentloaded")
                    await page.wait_for_timeout(1000)
                    print(f"      ✅ Applied used filter")
                    break
        except Exception as e:
            print(f"      ⚠️  Could not apply used filter: {e}")

        await self._set_items_per_page(page)

    async def _traverse_categories(self, playwright, category_id: str,
                                   category_name: str, category_url: str,
                                   parent_id: Optional[str], depth: int):
        """Recursively traverse category tree"""

        if category_id in self.visited_categories:
            indent = '  ' * depth
            print(f"{indent}⚠️  Already visited {category_name} (ID: {category_id}), skipping...")
            return

        if depth > 10:
            indent = '  ' * depth
            print(f"{indent}⚠️  Max depth (10) reached for {category_name}")
            return

        self.visited_categories.add(category_id)

        indent = '  ' * depth
        print(f"{indent}📂 Exploring: {category_name} (ID: {category_id})")

        print(f"{indent}   🌐 Creating new browser...")
        browser = await self._create_browser(playwright, use_proxy=self.use_proxy)

        try:
            # Create context with session and stealth
            context = await self._create_context_with_session(browser, session_name=f"category_{category_id}")
            page = await self._create_page_with_stealth(context)
            print(f"{indent}   ✅ Browser created")

            print(f"{indent}   🔗 Navigating to: {category_url[:80]}...")
            await page.goto(category_url, wait_until="domcontentloaded", timeout=30000)
            await random_delay(2, 4)  # Human-like delay
            await random_scroll(page)  # Simulate human scrolling
            print(f"{indent}   ✅ Page loaded")

            print(f"{indent}   🔍 Extracting subcategories...")
            subcategories = await self._extract_subcategories(page, category_id)

            is_leaf = len(subcategories) == 0

            print(f"{indent}   🔍 Extracting specs...")
            specs = await self._extract_specs(page)

            self.db.add_category(
                category_id=category_id,
                name=category_name,
                url=category_url,
                parent_id=parent_id,
                is_leaf=is_leaf
            )

            if specs:
                self.db.add_specs(category_id, specs)
                print(f"{indent}   📊 Specs found: {len(specs)}")

            print(f"{indent}   ✅ Subcategories: {len(subcategories)}, Is leaf: {is_leaf}, Specs: {len(specs)}")

            # Check if we've reached the max leaf categories limit (only in DEBUG mode)
            if ScraperConfig.DEBUG:
                current_leaf_count = len(self.db.get_leaf_categories())
                if current_leaf_count >= ScraperConfig.MAX_LEAF_CATEGORIES:
                    print(f"{indent}   ⚡ Reached max leaf categories limit ({ScraperConfig.MAX_LEAF_CATEGORIES})!")
                    print(f"{indent}   🚀 Stopping category traversal - going straight to item scraping!")
                    return

            if not is_leaf and subcategories:
                current_leaf_count = len(self.db.get_leaf_categories())
                if ScraperConfig.DEBUG:
                    print(f"{indent}   📂 Will explore subcategories (current leaf count: {current_leaf_count}/{ScraperConfig.MAX_LEAF_CATEGORIES})...")
                else:
                    print(f"{indent}   📂 Will explore {len(subcategories)} subcategories...")

                for idx, subcat in enumerate(subcategories, 1):
                    # Check again before each traversal (only in DEBUG mode)
                    if ScraperConfig.DEBUG:
                        if len(self.db.get_leaf_categories()) >= ScraperConfig.MAX_LEAF_CATEGORIES:
                            print(f"{indent}   ⚡ Reached max leaf categories limit during traversal!")
                            print(f"{indent}   🚀 Stopping category traversal - going straight to item scraping!")
                            return
                    
                    print(f"{indent}   [{idx}/{len(subcategories)}] Traversing: {subcat['name']}")
                    await self._traverse_categories(
                        playwright,
                        category_id=subcat['id'],
                        category_name=subcat['name'],
                        category_url=subcat['url'],
                        parent_id=category_id,
                        depth=depth + 1
                    )
            else:
                print(f"{indent}   🍃 LEAF CATEGORY - Will scrape items later")

        except Exception as e:
            print(f"{indent}   ❌ Error traversing {category_name}: {e}")
            import traceback
            print(f"{indent}   {traceback.format_exc()}")

        finally:
            # Save session before closing
            if 'context' in locals():
                await self._save_session(context, session_name=f"category_{category_id}")
            print(f"{indent}   🔒 Closing browser...")
            await browser.close()
    
    async def _extract_category_name_from_sidebar(self, page: Page) -> Optional[str]:
        """Extract category name from 'Selected category' span's parent"""
        try:
            print(f"        🔍 Looking for 'Selected category' span...")
            
            # Wait for sidebar to be ready
            try:
                await page.wait_for_selector('#x-refine__group__0', timeout=15000, state='attached')
                await page.wait_for_timeout(2000)
            except Exception as e:
                print(f"        ⚠️  Sidebar wait timeout: {e}, continuing anyway...")
                await page.wait_for_timeout(3000)
            
            # Try multiple times to find the "Selected category" span
            selected_span = None
            max_retries = 3
            
            for attempt in range(max_retries):
                if attempt > 0:
                    print(f"        🔄 Retry attempt {attempt + 1}/{max_retries}...")
                    await page.wait_for_timeout(2000 * attempt)
                
                selectors_to_try = [
                    'span.clipped:has-text("Selected category")',
                    'span:has-text("Selected category")',
                    '.clipped:has-text("Selected category")',
                    '#x-refine__group__0 span.clipped',
                    '#x-refine__group__0 span:has-text("Selected")'
                ]
                
                for selector in selectors_to_try:
                    try:
                        temp_span = page.locator(selector).first
                        if await temp_span.count() > 0:
                            text_content = await temp_span.text_content()
                            if text_content and 'selected category' in text_content.lower():
                                selected_span = temp_span
                                print(f"        ✅ Found 'Selected category' span")
                                break
                    except Exception:
                        continue
                
                if selected_span and await selected_span.count() > 0:
                    break
                selected_span = None
            
            if not selected_span or await selected_span.count() == 0:
                print(f"        ❌ 'Selected category' span not found")
                return None
            
            print(f"        🔍 Getting parent span...")
            parent_span = selected_span.locator('xpath=..')
            
            if await parent_span.count() == 0:
                print(f"        ❌ No parent span found")
                return None
            
            print(f"        ✅ Found parent span")
            parent_text = await parent_span.text_content()
            
            if not parent_text:
                print(f"        ❌ Parent span has no text content")
                return None
            
            # Remove "Selected category" text and clean up
            category_name = parent_text.strip()
            # Remove "Selected category" (case-insensitive)
            category_name = re.sub(r'Selected\s+category\s*', '', category_name, flags=re.IGNORECASE)
            # Clean up any extra whitespace
            category_name = re.sub(r'\s+', ' ', category_name).strip()
            
            if not category_name:
                print(f"        ⚠️  Category name is empty after removing 'Selected category'")
                return None
            
            print(f"        ✅ Extracted category name: '{category_name}'")
            return category_name
            
        except Exception as e:
            print(f"        ❌ Error extracting category name: {e}")
            import traceback
            print(f"        {traceback.format_exc()}")
            return None
    
    async def _extract_subcategories(self, page: Page, current_category_id: str) -> List[Dict]:
        """
        Find selected category and check for subcategories:
        1. Find <span class="clipped">Selected category</span>
        2. Go to parent <span>
        3. Go to parent <li>
        4. Look for child <ul>
        5. If <ul> exists -> extract subcategories (not leaf)
        6. If no <ul> -> leaf category
        """
        subcategories = []

        try:
            # Wait for sidebar to be ready first
            print(f"      🔍 Waiting for sidebar to be ready...")
            try:
                await page.wait_for_selector('#x-refine__group__0', timeout=15000, state='attached')
                await page.wait_for_timeout(2000)
                print(f"      ✅ Sidebar ready")
            except Exception as e:
                print(f"      ⚠️  Sidebar wait timeout: {e}, continuing anyway...")
                await page.wait_for_timeout(3000)
            
            print(f"      🔍 STEP 1: Looking for 'Selected category' span")
            
            # Try multiple times to find the "Selected category" span
            selected_span = None
            max_retries = 3
            
            for attempt in range(max_retries):
                if attempt > 0:
                    print(f"      🔄 Retry attempt {attempt + 1}/{max_retries}...")
                    await page.wait_for_timeout(2000 * attempt)  # Exponential backoff
                
                # Try different selectors
                selectors_to_try = [
                    'span.clipped:has-text("Selected category")',
                    'span:has-text("Selected category")',
                    '.clipped:has-text("Selected category")',
                    '#x-refine__group__0 span.clipped',
                    '#x-refine__group__0 span:has-text("Selected")'
                ]
                
                for selector in selectors_to_try:
                    try:
                        temp_span = page.locator(selector).first
                        if await temp_span.count() > 0:
                            # Verify it actually contains "Selected category" text
                            text_content = await temp_span.text_content()
                            if text_content and 'selected category' in text_content.lower():
                                selected_span = temp_span
                                print(f"      ✅ STEP 1: Found 'Selected category' span (attempt {attempt + 1}, selector: {selector[:50]})")
                                break
                    except Exception:
                        continue
                
                if selected_span:
                    # Verify it's still valid
                    if await selected_span.count() > 0:
                        break
                    else:
                        selected_span = None  # Reset if count is 0
                
                # If not found, try waiting for it explicitly
                if attempt < max_retries - 1:
                    try:
                        print(f"      ⏳ Waiting for 'Selected category' span to appear...")
                        await page.wait_for_selector('span.clipped:has-text("Selected category")', timeout=5000, state='attached')
                        await page.wait_for_timeout(1000)
                    except Exception:
                        pass
            
            if not selected_span or await selected_span.count() == 0:
                # Last resort: try reloading the page
                print(f"      🔄 Last resort: Reloading page to refresh sidebar...")
                try:
                    await page.reload(wait_until="domcontentloaded", timeout=30000)
                    await page.wait_for_timeout(3000)
                    await page.wait_for_selector('#x-refine__group__0', timeout=15000, state='attached')
                    await page.wait_for_timeout(2000)
                    
                    # Try one more time after reload
                    selected_span = page.locator('span.clipped:has-text("Selected category")').first
                    if await selected_span.count() == 0:
                        # Try alternative selector after reload
                        selected_span = page.locator('span:has-text("Selected category")').first
                except Exception as reload_error:
                    print(f"      ⚠️  Reload failed: {reload_error}")
            
            # Final verification
            if not selected_span:
                print(f"      ❌ 'Selected category' span NOT found after {max_retries} attempts")
                print(f"      ℹ️  Assuming leaf category or page structure changed")
                return []
            
            # Verify the span is still valid
            if await selected_span.count() == 0:
                print(f"      ❌ 'Selected category' span became invalid")
                print(f"      ℹ️  Assuming leaf category or page structure changed")
                return []
            
            print(f"      ✅ STEP 1: Found 'Selected category' span")
            
            print(f"      🔍 STEP 2: Getting parent <span>")
            parent_span = selected_span.locator('xpath=..')
            
            if await parent_span.count() == 0:
                print(f"      ❌ STEP 2: No parent span found")
                return []
            
            print(f"      ✅ STEP 2: Found parent <span>")
            
            print(f"      🔍 STEP 3: Getting parent <li>")
            parent_li = parent_span.locator('xpath=..')
            
            if await parent_li.count() == 0:
                print(f"      ❌ STEP 3: No parent <li> found")
                return []
            
            # Verify it's actually an LI
            tag_name = await parent_li.evaluate('el => el.tagName.toLowerCase()')
            if tag_name != 'li':
                print(f"      ⚠️  STEP 3: Parent is <{tag_name}>, not <li>. Looking for ancestor <li>...")
                parent_li = selected_span.locator('xpath=ancestor::li[1]')
                
                if await parent_li.count() == 0:
                    print(f"      ❌ STEP 3: No ancestor <li> found")
                    return []
            
            print(f"      ✅ STEP 3: Found parent <li>")
            
            print(f"      🔍 STEP 4: Looking for child <ul> in <li>")
            child_ul = parent_li.locator('> ul').first
            
            if await child_ul.count() == 0:
                print(f"      🍃 STEP 4: No child <ul> found - LEAF CATEGORY")
                return []
            
            print(f"      ✅ STEP 4: Found child <ul> - NOT a leaf category")
            
            print(f"      🔍 STEP 5: Extracting <li> items from <ul>")
            li_items = await child_ul.locator('> li').all()
            
            print(f"      ✅ STEP 5: Found {len(li_items)} <li> items")
            
            print(f"      🔍 STEP 6: Extracting subcategories")
            
            seen_ids = set()
            
            for li in li_items:
                try:
                    # Skip if this LI has "Selected category" (that's us)
                    if await li.locator('span.clipped:has-text("Selected category")').count() > 0:
                        continue
                    
                    a_tag = li.locator('a[href*="/sch/"]').first
                    
                    if await a_tag.count() == 0:
                        continue
                    
                    href = await a_tag.get_attribute('href')
                    text = await a_tag.text_content()
                    
                    if not href or not text:
                        continue
                    
                    cat_id_match = re.search(r'/sch/(\d+)/', href)
                    if not cat_id_match:
                        continue
                    
                    cat_id = cat_id_match.group(1)
                    
                    if cat_id == current_category_id or cat_id in self.visited_categories or cat_id in seen_ids:
                        continue
                    
                    # if not self._is_car_parts_category(cat_id, text):
                    #     print(f"      ⚠️  Skipping non-car: {text[:30]} ({cat_id})")
                    #     continue
                    
                    seen_ids.add(cat_id)
                    
                    if not href.startswith('http'):
                        href = 'https://www.ebay.com' + href
                    
                    subcategories.append({
                        'id': cat_id,
                        'name': text.strip(),
                        'url': href
                    })
                    print(f"      ✅ Added: {text.strip()[:40]} (ID: {cat_id})")
                    
                except Exception:
                    continue
            
            print(f"      ✅ STEP 6: Done")

        except Exception as e:
            logger.warning(f"Error: {e}")
            import traceback
            print(f"      ❌ Error: {traceback.format_exc()}")

        print(f"      📊 Total subcategories: {len(subcategories)}")
        return subcategories
  
    def _is_car_parts_category(self, category_id: str, category_name: str) -> bool:
        """Check if category is car parts related"""
        # Car parts category IDs
        car_parts_prefixes = ['6', '33', '38', '184', '107']
        
        if any(category_id.startswith(prefix) for prefix in car_parts_prefixes):
            return True
        
        # Blocked non-automotive categories
        blocked_ids = [
            '293', '267', '11700', '14339', '12576', '220', '1', '99', '888', '3252', '11554',
        ]
        
        if category_id in blocked_ids:
            return False
        
        # Check name for automotive keywords
        automotive_keywords = [
            'car', 'truck', 'auto', 'vehicle', 'motor', 'engine', 
            'brake', 'tire', 'wheel', 'parts', 'accessories',
            'transmission', 'suspension', 'exhaust', 'fuel'
        ]
        
        name_lower = category_name.lower()
        if any(keyword in name_lower for keyword in automotive_keywords):
            return True
        
        return False

    async def _extract_specs(self, page: Page) -> List[Dict]:
        """Extract available specs/filters with options (exactly like _collect_sidebar_specs)"""
        specs = []
        
        print(f"        🔍 COLLECTING SIDEBAR SPECS")
        
        try:
            filter_h3s = await page.locator('ul.x-refine__left__nav h3').all()
            filter_names = ['Type', 'Manufacturer Warranty', 'Items Included', 'Performance Part', 
                          'Material', 'Brand', 'Universal Fitment', 'Country of Origin', 'Vintage Part', 'Brand Type', 'Placement on Vehicle', 'Finish', 
                          'Terminal Type', 'Condition', 'Buying format']
            exclude_names = ['Category', 'Price', 'Buying Format', 'Item Location', 'Shipping and pickup', 'Show only']
            print(f"        📋 Found {len(filter_h3s)} h3 elements in sidebar")
            
            for h3_idx, h3 in enumerate(filter_h3s, 1):
                try:
                    h3_text = await h3.text_content()
                    h3_text = h3_text.strip() if h3_text else ''
                    
                    print(f"        🔍 Checking h3 {h3_idx}: '{h3_text}'...")
                    
                    if h3_text in exclude_names:
                        print(f"        ⏭️  Skipping '{h3_text}' (not in filter list)")
                        continue
                    
                    print(f"        ✅ Processing filter: '{h3_text}'")
                    
                    # Find corresponding group
                    h3_id = await h3.get_attribute('id')
                    group_id = None
                    
                    if h3_id:
                        print(f"        🔍 h3 has id: '{h3_id}'")
                        # Extract number from id like "x-refine__group__7"
                        match = re.search(r'group__(\d+)', h3_id)
                        if match:
                            group_num = match.group(1)
                            group_id = f'#x-refine__group_{group_num}__0'
                            print(f"        ✅ Constructed group_id: '{group_id}'")
                    else:
                        print(f"        🔍 h3 has no id, trying following sibling...")
                        # Try to find by following sibling
                        next_div = h3.locator('xpath=following-sibling::div[contains(@id, "x-refine__group")]').first
                        if await next_div.count() > 0:
                            div_id = await next_div.get_attribute('id')
                            group_id = f"#{div_id}"
                            print(f"        ✅ Found following sibling div: '{group_id}'")
                    
                    if not group_id:
                        print(f"        ⚠️  Could not find group_id for '{h3_text}'")
                        continue
                    
                    group = page.locator(group_id).first
                    if await group.count() == 0:
                        print(f"        ⚠️  Group '{group_id}' not found")
                        continue
                    
                    print(f"        ✅ Found group: '{group_id}'")
                    
                    # Extract all options
                    options = []
                    option_lis = await group.locator('ul > li').all()
                    print(f"        📋 Found {len(option_lis)} option li elements")
                    
                    for option_idx, option_li in enumerate(option_lis, 1):
                        try:
                            option_link = option_li.locator('a').first
                            if await option_link.count() == 0:
                                continue
                            
                            option_text = await option_link.text_content()
                            option_text = option_text.strip() if option_text else ''
                            
                            if not option_text:
                                continue
                            
                            print(f"        🔍 Processing option {option_idx}: '{option_text}'...")
                            
                            # Parse: "ABS Accumulator(24) Items (24)" or "ABS Accumulator (24) Items (24)"
                            # Extract name (everything before first parenthesis)
                            name_match = re.match(r'^([^(]+)', option_text)
                            name = name_match.group(1).strip() if name_match else option_text
                            
                            # Extract amount (number in parentheses, prefer last one)
                            amount_matches = re.findall(r'\((\d+)\)', option_text)
                            amount = int(amount_matches[-1]) if amount_matches else 0
                            
                            print(f"        ✅ Extracted: name='{name}', amount={amount}")
                            
                            options.append({'name': name, 'amount': amount})
                            
                        except Exception as e:
                            print(f"        ⚠️  Error extracting option {option_idx}: {e}")
                            continue
                    
                    if options:
                        total = sum(opt['amount'] for opt in options)
                        print(f"        📊 Total items for '{h3_text}': {total}")
                        
                        # Calculate percentages
                        for opt in options:
                            opt['percent'] = round((opt['amount'] / total * 100) if total > 0 else 0, 2)
                        
                        specs.append({
                            'name': h3_text,
                            'values': options
                        })
                        
                        print(f"        ✅ Collected spec '{h3_text}': {len(options)} values")
                    else:
                        print(f"        ⚠️  No options extracted for '{h3_text}'")
                        
                except Exception as e:
                    print(f"        ⚠️  Error collecting spec '{h3_text}': {e}")
                    import traceback
                    print(f"        {traceback.format_exc()}")
                    continue
                    
        except Exception as e:
            print(f"        ⚠️  Error in sidebar specs collection: {e}")
            import traceback
            print(f"        {traceback.format_exc()}")
        
        print(f"        ✅ Completed collecting sidebar specs: {len(specs)} specs")
        return specs

    async def _scrape_leaf_categories(self, playwright, listing_type: str):
        """Scrape items from all leaf categories concurrently"""
        leaf_categories = self.db.get_leaf_categories()
        
        # Limit to max leaf categories only in DEBUG mode
        if ScraperConfig.DEBUG and len(leaf_categories) > ScraperConfig.MAX_LEAF_CATEGORIES:
            print(f"   🐛 DEBUG MODE: Limiting to first {ScraperConfig.MAX_LEAF_CATEGORIES} leaf categories (found {len(leaf_categories)})")
            leaf_categories = leaf_categories[:ScraperConfig.MAX_LEAF_CATEGORIES]

        print(f"\n📦 Found {len(leaf_categories)} leaf categories to scrape ({listing_type})")
        print(f"   Concurrent browsers: {ScraperConfig.MAX_CONCURRENT_PAGES}")
        print(f"   Pages per category: {ScraperConfig.MAX_PAGES_PER_CATEGORY}")

        if not leaf_categories:
            print(f"   ⚠️  No leaf categories found!")
            return

        print(f"\n📋 Leaf categories to scrape:")
        for idx, cat in enumerate(leaf_categories, 1):
            print(f"   {idx}. {cat['name']} (ID: {cat['id']})")

        print(f"\n🚀 Starting concurrent {listing_type} scraping...")

        tasks = []
        for cat in leaf_categories:
            task = self._scrape_category_items(playwright, cat, listing_type)
            tasks.append(task)

        await asyncio.gather(*tasks)

        print(f"\n✅ All leaf categories scraped ({listing_type})!")

    async def _scrape_category_items(self, playwright, category: Dict, listing_type: str):
        """Scrape items from a single category using URL-based filtering and pagination"""
        async with self.semaphore:
            category_id = category['id']
            category_name = category['name']

            print(f"\n📦 [{listing_type.upper()}] [{category_name}] Starting item scraping...")
            print(f"   🌐 Creating browser...")

            browser = await self._create_browser(playwright, use_proxy=self.use_proxy)

            try:
                # Create context with session and stealth
                context = await self._create_context_with_session(browser, session_name=f"scrape_{category_id}_{listing_type}")
                page = await self._create_page_with_stealth(context)
                print(f"   ✅ [{listing_type.upper()}] [{category_name}] Browser created")

                items = []

                # Build URL for first page to get total count
                base_url = f"https://www.ebay.com/sch/{category_id}/i.html"
                query_params = [
                    f"_nkw={quote(self.query)}",
                    f"_ipg={ScraperConfig.ITEMS_PER_PAGE}",
                    "LH_ItemCondition=3000"  # Used condition
                ]
                
                # Add sold filters only for sold listings
                if listing_type == 'sold':
                    query_params.extend([
                        "LH_Sold=1",
                        "LH_Complete=1",
                        "rt=nc"
                    ])
                
                first_page_url = f"{base_url}?{'&'.join(query_params)}"
                
                print(f"   🔗 [{listing_type.upper()}] [{category_name}] Loading first page to get total count...")
                print(f"      URL: {first_page_url[:100]}...")
                
                # Navigate to first page
                await page.goto(first_page_url, wait_until="domcontentloaded", timeout=30000)
                await random_delay(2, 4)
                await random_scroll(page)
                
                # Wait for results to load (check if attached, not visible)
                try:
                    # Wait for selector to be attached to DOM (exists, even if hidden)
                    await page.wait_for_selector("#srp-river-results", timeout=20000, state="attached")
                    # Additional wait to ensure content is loaded
                    await page.wait_for_timeout(2000)
                except Exception as e:
                    print(f"   ⚠️  [{listing_type.upper()}] [{category_name}] Results container check failed: {e}")
                    # Check if page has no results
                    no_results = page.locator('text="No exact matches found"')
                    if await no_results.count() > 0:
                        print(f"   ℹ️  [{listing_type.upper()}] [{category_name}] No results found, skipping category...")
                        return
                    # If results container doesn't exist, skip this category
                    results_container = page.locator("#srp-river-results")
                    if await results_container.count() == 0:
                        print(f"   ℹ️  [{listing_type.upper()}] [{category_name}] Results container not found, skipping category...")
                        return
                
                # Get total count
                total_count = await self._get_total_count(page)
                
                if total_count == 0:
                    print(f"   ⚠️  [{listing_type.upper()}] [{category_name}] No items found, skipping category...")
                    return
                
                # Calculate number of pages needed
                total_pages = math.ceil(total_count / ScraperConfig.ITEMS_PER_PAGE)
                # Apply max pages limit if configured
                max_pages = min(total_pages, ScraperConfig.MAX_PAGES_PER_CATEGORY) if ScraperConfig.MAX_PAGES_PER_CATEGORY > 0 else total_pages
                
                print(f"   📊 [{listing_type.upper()}] [{category_name}] Total items: {total_count:,}")
                print(f"   📄 [{listing_type.upper()}] [{category_name}] Total pages: {total_pages}, Will scrape: {max_pages}")

                # Extract items from first page
                print(f"   📄 [{listing_type.upper()}] [{category_name}] Extracting items from page 1...")
                page_items = await self._extract_items_from_page(page)
                if page_items:
                    for item in page_items:
                        item['listing_type'] = listing_type
                    items.extend(page_items)
                    print(f"   ✅ [{listing_type.upper()}] [{category_name}] Page 1: {len(page_items)} items (total: {len(items)})")
                
                # Paginate through remaining pages
                for page_num in range(2, max_pages + 1):
                    try:
                        # Build URL with page number
                        query_params_with_page = query_params + [f"_pgn={page_num}"]
                        url = f"{base_url}?{'&'.join(query_params_with_page)}"
                        
                        print(f"   🔗 [{listing_type.upper()}] [{category_name}] Loading page {page_num}/{max_pages}...")
                        print(f"      URL: {url[:100]}...")
                        
                        # Navigate to URL with human-like behavior
                        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                        await random_delay(2, 4)
                        await random_scroll(page)
                        
                        # Wait for results to load (check if attached, not visible)
                        try:
                            # Wait for selector to be attached to DOM (exists, even if hidden)
                            await page.wait_for_selector("#srp-river-results", timeout=20000, state="attached")
                            # Additional wait to ensure content is loaded
                            await page.wait_for_timeout(2000)
                            # Try to wait for actual items to be present
                            try:
                                await page.wait_for_selector("#srp-river-results ul li.s-card, .s-card", timeout=5000, state="attached")
                            except Exception:
                                # If items selector doesn't work, check if results container has content
                                results_container = page.locator("#srp-river-results")
                                if await results_container.count() > 0:
                                    # Container exists, continue even if items aren't immediately visible
                                    pass
                        except Exception as e:
                            print(f"   ⚠️  [{listing_type.upper()}] [{category_name}] Results container check failed: {e}")
                            # Check if page has no results
                            no_results = page.locator('text="No exact matches found"')
                            if await no_results.count() > 0:
                                print(f"   ℹ️  [{listing_type.upper()}] [{category_name}] No results found on page {page_num}, stopping...")
                                break
                        
                        print(f"   📄 [{listing_type.upper()}] [{category_name}] Extracting items from page {page_num}...")
                        page_items = await self._extract_items_from_page(page)

                        if not page_items:
                            print(f"   ⚠️  [{listing_type.upper()}] [{category_name}] No items found on page {page_num}, stopping...")
                            break

                        for item in page_items:
                            item['listing_type'] = listing_type

                        items.extend(page_items)

                        print(f"   ✅ [{listing_type.upper()}] [{category_name}] Page {page_num}/{max_pages}: {len(page_items)} items (total: {len(items)})")

                    except Exception as e:
                        print(f"   ❌ [{listing_type.upper()}] [{category_name}] Error on page {page_num}: {e}")
                        import traceback
                        print(f"   {traceback.format_exc()}")
                        break

                if items:
                    # Deduplicate items by exact title match within this category
                    original_count = len(items)
                    unique_items = self._deduplicate_items_by_title(items)
                    duplicates_removed = original_count - len(unique_items)
                    
                    if duplicates_removed > 0:
                        print(f"   🔄 [{listing_type.upper()}] [{category_name}] Removed {duplicates_removed} duplicate(s) by title (kept {len(unique_items)} unique items)")
                    
                    self.db.add_items(category_id, unique_items)
                    print(f"✅ [{listing_type.upper()}] [{category_name}] Complete: {len(unique_items)} items scraped")
                else:
                    print(f"⚠️  [{listing_type.upper()}] [{category_name}] No items found")

            except Exception as e:
                print(f"❌ [{listing_type.upper()}] [{category_name}] Error scraping: {e}")
                import traceback
                print(f"{traceback.format_exc()}")

            finally:
                # Save session before closing
                if 'context' in locals():
                    await self._save_session(context, session_name=f"scrape_{category_id}_{listing_type}")
                print(f"   🔒 [{listing_type.upper()}] [{category_name}] Closing browser...")
                await browser.close()

    async def _get_total_count(self, page: Page) -> int:
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

    async def _extract_items_from_page(self, page: Page) -> List[Dict]:
        """Extract items from current page"""
        items = []

        try:
            # Wait for results container to be attached (exists in DOM, even if hidden)
            try:
                await page.wait_for_selector("#srp-river-results", timeout=20000, state="attached")
            except Exception:
                # If waiting fails, check if it exists anyway
                results_container = page.locator("#srp-river-results")
                if await results_container.count() == 0:
                    return []

            # Give it a moment to render items
            await page.wait_for_timeout(2000)

            li_selectors = [
                "#srp-river-results ul li.s-card",
                ".s-card",
                "#srp-river-results li[class*='s-item']",
                "li.s-item"
            ]

            listings_locator = None
            for selector in li_selectors:
                locator = page.locator(selector)
                # Check if elements exist (even if hidden)
                count = await locator.count()
                if count > 0:
                    listings_locator = locator
                    break

            if not listings_locator:
                # Try one more time with a longer wait
                await page.wait_for_timeout(3000)
                for selector in li_selectors:
                    locator = page.locator(selector)
                    if await locator.count() > 0:
                        listings_locator = locator
                        break
                
                if not listings_locator:
                    return []

            item_count = await listings_locator.count()

            for idx in range(item_count):
                try:
                    item_locator = listings_locator.nth(idx)
                    block = await item_locator.inner_html()
                    listing = self._parse_listing_block(block)

                    if listing and listing.get('item_id'):
                        items.append(listing)
                except Exception:
                    continue

        except Exception as e:
            logger.warning(f"Could not extract items: {e}")

        return items

    def _deduplicate_items_by_title(self, items: List[Dict]) -> List[Dict]:
        """Remove duplicate items based on exact title match within the same category"""
        seen_titles = set()
        unique_items = []
        
        for item in items:
            title = item.get('title', '').strip()
            if not title:
                # Keep items without titles (might be useful)
                unique_items.append(item)
                continue
            
            # Normalize title for comparison (exact match)
            title_lower = title.lower()
            
            # Skip if we've seen this exact title before
            if title_lower in seen_titles:
                continue
            
            seen_titles.add(title_lower)
            unique_items.append(item)
        
        return unique_items

    def _parse_listing_block(self, block: str) -> Optional[Dict]:
        """Parse HTML block to extract listing data"""
        try:
            title_match = re.search(r's-card__title.*?<[^>]+>(.*?)</', block, re.S)
            title = re.sub(r"<.*?>", "", title_match.group(1)).strip() if title_match else None

            price_match = re.search(r's-card__price.*?>(.*?)</span>', block, re.S)
            price_text = re.sub(r"<.*?>", "", price_match.group(1)).strip() if price_match else None

            price = 0.0
            if price_text:
                price_clean = re.sub(r'[^0-9.]', '', price_text)
                try:
                    price = float(price_clean)
                except:
                    pass

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

            image_url = ""
            img_match = re.search(r'<img[^>]*src="([^"]+)"', block)
            if img_match:
                image_url = img_match.group(1)

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
            

            condition = "Used"
            condition_match = re.search(r'SECONDARY_INFO">([^<]+)</span>', block)
            if condition_match:
                condition = condition_match.group(1).strip()

            sold_date = None
            date_match = re.search(r'Sold\s+([A-Z][a-z]+\s+\d{1,2})', block)
            if date_match:
                sold_date = date_match.group(1)

            if not (title and item_id):
                return None

            return {
                'item_id': item_id,
                'title': title,
                'price': price,
                'url': url or f"https://www.ebay.com/itm/{item_id}",
                'image_url': image_url,
                'condition': condition,
                'seller': seller,
                'seller_feedback': seller_feedback,
                'shipping_cost': shipping_cost,
                'sold_date': sold_date,
                'source': 'proxy_scraper'
            }
        except Exception:
            return None
   
    async def _create_browser(self, playwright, use_proxy: bool = True) -> Browser:
        """Create a new browser instance with enhanced anti-detection"""
        try:
            # Enhanced browser arguments for anti-detection
            browser_args = [
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-blink-features=AutomationControlled',
                '--disable-features=IsolateOrigins,site-per-process',
                '--disable-web-security',
                '--flag-switches-begin --disable-site-isolation-trials --flag-switches-end'
            ]

            if use_proxy:
                print(f"      🌐 Launching browser WITH proxy...")
                browser = await playwright.chromium.launch(
                    proxy=ProxyConfig.get_proxy_config(),
                    headless=ScraperConfig.HEADLESS,
                    args=browser_args
                )
            else:
                print(f"      🌐 Launching browser WITHOUT proxy (fallback mode)...")
                browser = await playwright.chromium.launch(
                    headless=ScraperConfig.HEADLESS,
                    args=browser_args
                )

            return browser
        except Exception as e:
            print(f"      ❌ Browser launch failed: {e}")
            raise

    async def _create_context_with_session(self, browser: Browser, session_name: str = "default") -> BrowserContext:
        """Create a browser context with session persistence and stealth mode"""
        try:
            # Create session directory if it doesn't exist
            if ScraperConfig.USE_SESSION_PERSISTENCE:
                os.makedirs(ScraperConfig.SESSION_DIR, exist_ok=True)
                session_path = os.path.join(ScraperConfig.SESSION_DIR, session_name)
                os.makedirs(session_path, exist_ok=True)
                print(f"      💾 Using persistent session: {session_path}")

                # Create context with persistent storage
                context = await browser.new_context(
                    storage_state=os.path.join(session_path, "state.json") if os.path.exists(
                        os.path.join(session_path, "state.json")) else None,
                    viewport={'width': 1920, 'height': 1080},
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
                    locale='en-US',
                    timezone_id='America/New_York',
                    permissions=['geolocation'],
                    geolocation={'latitude': 40.7128, 'longitude': -74.0060},  # New York coordinates
                    color_scheme='light',
                    extra_http_headers={
                        'Accept-Language': 'en-US,en;q=0.9',
                        'Accept-Encoding': 'gzip, deflate, br',
                        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                        'DNT': '1',
                        'Connection': 'keep-alive',
                        'Upgrade-Insecure-Requests': '1'
                    }
                )
            else:
                # Create context without persistence
                context = await browser.new_context(
                    viewport={'width': 1920, 'height': 1080},
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
                    locale='en-US',
                    timezone_id='America/New_York'
                )

            return context
        except Exception as e:
            print(f"      ❌ Context creation failed: {e}")
            # Fallback to basic context
            return await browser.new_context()

    async def _save_session(self, context: BrowserContext, session_name: str = "default"):
        """Save the current session state"""
        if not ScraperConfig.USE_SESSION_PERSISTENCE:
            return

        try:
            session_path = os.path.join(ScraperConfig.SESSION_DIR, session_name)
            os.makedirs(session_path, exist_ok=True)
            state_file = os.path.join(session_path, "state.json")

            # Save storage state (cookies, localStorage, etc.)
            await context.storage_state(path=state_file)
            print(f"      💾 Session saved to: {state_file}")
        except Exception as e:
            logger.debug(f"Failed to save session: {e}")

    async def _create_page_with_stealth(self, context: BrowserContext) -> Page:
        """Create a new page with stealth mode enabled"""
        page = await context.new_page()
        stealth = Stealth(
            init_scripts_only=True
        )
        # Apply stealth mode if enabled
        if ScraperConfig.USE_STEALTH:
            await stealth.apply_stealth_async(page)
            print(f"      🥷 Stealth mode enabled")

        # Additional anti-detection measures
        await page.add_init_script("""
            // Override the navigator.webdriver property
            Object.defineProperty(navigator, 'webdriver', {
                get: () => false
            });

            // Override the navigator.plugins to make it look realistic
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5]
            });

            // Override the navigator.languages property
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en']
            });

            // Add chrome object
            window.chrome = {
                runtime: {}
            };

            // Override permissions
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({state: Notification.permission}) :
                    originalQuery(parameters)
            );
        """)

        page.set_default_timeout(ScraperConfig.TIMEOUT)
        return page


# ============================================================================
# RICH REPORT GENERATION
# ============================================================================

def print_rich_report(db: CategoryDB, query: str, output_file: str):
    """Generate and print a comprehensive rich report"""

    print(f"\n\n{'='*80}")
    print(f"📊 EBAY PROXY SCRAPER - FINAL REPORT")
    print(f"{'='*80}")

    print(f"\n🔍 QUERY INFORMATION")
    print(f"{'─'*80}")
    print(f"  Search Query:     {query}")
    print(f"  Listing Types:    Both ACTIVE and SOLD")
    print(f"  Scraped At:       {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    print(f"\n📂 CATEGORY STATISTICS")
    print(f"{'─'*80}")
    total_cats = len(db.categories)
    leaf_cats = db.get_leaf_categories()
    non_leaf_cats = [c for c in db.categories.values() if not c['is_leaf']]

    print(f"  Total Categories:         {total_cats}")
    print(f"  Leaf Categories:          {len(leaf_cats)}")
    print(f"  Non-Leaf Categories:      {len(non_leaf_cats)}")

    if db.specs:
        print(f"  Categories with Specs:    {len(db.specs)}")
        total_specs = sum(len(specs) for specs in db.specs.values())
        print(f"  Total Specs Collected:    {total_specs}")

    print(f"\n🌳 CATEGORY TREE STRUCTURE")
    print(f"{'─'*80}")

    root_cats = [c for c in db.categories.values() if c['parent_id'] is None]

    def print_tree(cat_id, indent=0):
        cat = db.categories.get(cat_id)
        if not cat:
            return

        prefix = "  " * indent
        leaf_marker = "🍃" if cat['is_leaf'] else "📂"
        item_count = f" ({cat['item_count']} items)" if cat['item_count'] > 0 else ""

        print(f"{prefix}{leaf_marker} {cat['name']}{item_count}")

        for subcat_id in cat.get('subcategories', []):
            print_tree(subcat_id, indent + 1)

    for root_cat in root_cats:
        print_tree(root_cat['id'])

    print(f"\n📦 ITEMS STATISTICS")
    print(f"{'─'*80}")
    total_items = len(db.scraped_items)
    print(f"  Total Items Scraped:      {total_items}")

    if total_items > 0:
        active_items = [item for item in db.scraped_items if item.get('listing_type') == 'active']
        sold_items = [item for item in db.scraped_items if item.get('listing_type') == 'sold']

        print(f"  Active Items:             {len(active_items)}")
        print(f"  Sold Items:               {len(sold_items)}")

        items_by_category = {}
        for item in db.scraped_items:
            cat_id = item.get('category_id')
            if cat_id:
                if cat_id not in items_by_category:
                    items_by_category[cat_id] = []
                items_by_category[cat_id].append(item)

        print(f"  Categories with Items:    {len(items_by_category)}")

        prices = [item['price'] for item in db.scraped_items if item.get('price', 0) > 0]
        if prices:
            print(f"\n  💰 PRICE STATISTICS")
            print(f"  {'─'*76}")
            print(f"    Min Price:              ${min(prices):.2f}")
            print(f"    Max Price:              ${max(prices):.2f}")
            print(f"    Average Price:          ${sum(prices)/len(prices):.2f}")
            print(f"    Median Price:           ${sorted(prices)[len(prices)//2]:.2f}")

        shipping_costs = [item['shipping_cost'] for item in db.scraped_items
                         if item.get('shipping_cost', 0) > 0]
        if shipping_costs:
            print(f"\n  📮 SHIPPING STATISTICS")
            print(f"  {'─'*76}")
            print(f"    Items with Shipping:    {len(shipping_costs)}")
            print(f"    Avg Shipping Cost:      ${sum(shipping_costs)/len(shipping_costs):.2f}")
            print(f"    Free Shipping:          {total_items - len(shipping_costs)}")

        conditions = {}
        for item in db.scraped_items:
            cond = item.get('condition', 'Unknown')
            conditions[cond] = conditions.get(cond, 0) + 1

        if conditions:
            print(f"\n  🔧 CONDITION BREAKDOWN")
            print(f"  {'─'*76}")
            for condition, count in sorted(conditions.items(), key=lambda x: x[1], reverse=True):
                percentage = (count / total_items) * 100
                bar = '█' * int(percentage / 2)
                print(f"    {condition:20s}: {count:4d} ({percentage:5.1f}%) {bar}")

    print(f"\n🏆 TOP CATEGORIES BY ITEM COUNT")
    print(f"{'─'*80}")

    leaf_with_items = [(cat, cat['item_count'])
                       for cat in leaf_cats if cat['item_count'] > 0]
    leaf_with_items.sort(key=lambda x: x[1], reverse=True)

    if leaf_with_items:
        for idx, (cat, count) in enumerate(leaf_with_items[:10], 1):
            print(f"  {idx:2d}. {cat['name']:50s} {count:4d} items")
    else:
        print(f"  No items scraped yet")

    print(f"\n💾 EXPORT INFORMATION")
    print(f"{'─'*80}")
    print(f"  Output File:              {output_file}")
    print(f"  File Format:              JSON")

    print(f"\n⚡ SCRAPING CONFIGURATION")
    print(f"{'─'*80}")
    print(f"  Proxy Server:             {ProxyConfig.SERVER}")
    print(f"  Headless Mode:            {ScraperConfig.HEADLESS}")
    print(f"  Max Concurrent Browsers:  {ScraperConfig.MAX_CONCURRENT_PAGES}")
    print(f"  Items Per Page:           {ScraperConfig.ITEMS_PER_PAGE}")
    print(f"  Max Pages Per Category:   {ScraperConfig.MAX_PAGES_PER_CATEGORY}")

    print(f"\n💡 KEY INSIGHTS")
    print(f"{'─'*80}")

    if total_items > 0:
        if prices:
            avg_price = sum(prices) / len(prices)
            if avg_price > 100:
                print(f"  • High-value items detected (avg: ${avg_price:.2f})")
            elif avg_price < 25:
                print(f"  • Low-cost parts market (avg: ${avg_price:.2f})")
            else:
                print(f"  • Mid-range pricing (avg: ${avg_price:.2f})")

        if len(leaf_with_items) > 0:
            top_cat = leaf_with_items[0][0]
            print(f"  • Most active category: {top_cat['name']} ({leaf_with_items[0][1]} items)")

        if shipping_costs:
            free_shipping_pct = ((total_items - len(shipping_costs)) / total_items) * 100
            print(f"  • Free shipping rate: {free_shipping_pct:.1f}%")
    else:
        print(f"  • No items found - try different search terms or categories")
        print(f"  • Check if filters are too restrictive")

    print(f"\n{'='*80}")
    print(f"✅ REPORT COMPLETE")
    print(f"{'='*80}\n")


# ============================================================================
# MAIN FUNCTION
# ============================================================================

async def main():
    """Example usage"""
    query = "2010 Toyota Prius front bumper"

    scraper = ProxyEbayScraper(query=query)

    db = await scraper.scrape()

    output_file = f"ebay_scrape_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    db.export_to_json(output_file, query=query)

    print_rich_report(db, query, output_file)


if __name__ == "__main__":
    asyncio.run(main())
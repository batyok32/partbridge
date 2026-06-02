"""
Fast eBay Scraper with ScrapingBee
Scrapes eBay categories and items using ScrapingBee API for anti-detection
"""

import requests
import json
import math
import re
import time
from typing import List, Dict, Optional, Set
from urllib.parse import quote, urljoin
from datetime import datetime
from bs4 import BeautifulSoup
import logging
from django.conf import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ============================================================================
# CONFIGURATION
# ============================================================================

class ScrapingBeeConfig:
    """ScrapingBee API configuration"""
    API_KEY = settings.SCRAPING_BEE_API_KEY
    API_URL = "https://app.scrapingbee.com/api/v1"
    RENDER_JS = True  # eBay requires JavaScript rendering
    PREMIUM_PROXY = True  # Use premium proxies for better success rate
    COUNTRY_CODE = "us"  # Target US eBay

    @classmethod
    def get_scraping_params(cls, url: str, render_js: bool = None, wait_for: str = None,
                           js_scenario: str = None) -> Dict:
        """Get ScrapingBee request parameters"""
        params = {
            "api_key": cls.API_KEY,
            "url": url,
            "render_js": str(render_js if render_js is not None else cls.RENDER_JS).lower(),
            # "premium_proxy": str(cls.PREMIUM_PROXY).lower(),
            "country_code": cls.COUNTRY_CODE,
            "wait": "8000",  # Wait 8 seconds for JS to fully load (specs/filters need time)
            # Send cookies before page load to force English locale
            "cookies": "lc=en-US;ebay=%5Esbf%3D%2340000000000100000000007089ed9fff%5E",
            'forward_headers': 'true'
        }

        # Only add wait_for if specified (makes it more flexible)
        if wait_for is not None:
            params["wait_for"] = wait_for

        # Add JavaScript scenario if specified (for scrolling, clicking, etc)
        if js_scenario is not None:
            params["js_scenario"] = js_scenario

        return params


class ScraperConfig:
    """Scraper configuration"""
    ITEMS_PER_PAGE = 240
    MAX_PAGES_PER_CATEGORY = 10
    MAX_CONCURRENT_REQUESTS = 3  # Limit concurrent API calls
    REQUEST_DELAY = 2  # Delay between requests in seconds
    
    # Debug mode: limit leaf categories for faster testing
    DEBUG = False
    MAX_LEAF_CATEGORIES = 3  # Maximum leaf categories (only enforced in DEBUG mode)

    START_CATEGORY = 6000
    TARGET_CATEGORY = 6030
    
    # Top-level eBay categories to exclude (not related to car parts)
    EXCLUDED_TOP_LEVEL_CATEGORIES = {
        '1',      # Collectibles
        '99',     # Everything Else
        '6000',   # eBay Motors (too broad, we want specific parts)
        '888',    # Sporting Goods
        '267',    # Books
        '11450',  # Clothing, Shoes & Accessories
        '58058',  # Electronics
        '11700',  # Home & Garden
        '1281',   # Jewelry & Watches
        '11232',  # Musical Instruments & Gear
        '619',    # Pet Supplies
        '26395',  # Toys & Hobbies
        '159260', # Video Games & Consoles
    }


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

    def _deduplicate_items_globally(self):
        """Deduplicate items across all categories based on exact title match"""
        print(f"   🔍 Deduplicating items by exact title match...")
        
        # Group items by normalized title (case-insensitive, stripped)
        title_to_items = {}
        for item in self.scraped_items:
            title = item.get('title', '').strip()
            if not title:
                continue
            
            # Normalize title for comparison (lowercase, strip whitespace)
            normalized_title = title.lower().strip()
            
            if normalized_title not in title_to_items:
                title_to_items[normalized_title] = []
            
            title_to_items[normalized_title].append(item)
        
        # Keep only the first occurrence of each title
        deduplicated_items = []
        seen_titles = set()
        duplicates_removed = 0
        
        for item in self.scraped_items:
            title = item.get('title', '').strip()
            if not title:
                continue
            
            normalized_title = title.lower().strip()
            
            # If we've already seen this exact title, skip it
            if normalized_title in seen_titles:
                duplicates_removed += 1
                continue
            
            # First time seeing this title, keep it
            seen_titles.add(normalized_title)
            deduplicated_items.append(item)
        
        # Update scraped_items with deduplicated list
        self.scraped_items = deduplicated_items
        
        # Recalculate item counts for each category
        self._recalculate_category_item_counts()
        
        print(f"   ✅ Removed {duplicates_removed} duplicate items")
    
    def _recalculate_category_item_counts(self):
        """Recalculate item counts for each category after deduplication"""
        # Reset all category item counts
        for category_id in self.categories:
            self.categories[category_id]['item_count'] = 0
        
        # Count items by category
        for item in self.scraped_items:
            category_id = item.get('category_id')
            if category_id and category_id in self.categories:
                self.categories[category_id]['item_count'] += 1
    
    def _remove_empty_categories(self):
        """Remove leaf categories that have 0 items after deduplication"""
        print(f"   🔍 Checking for empty leaf categories...")
        
        empty_categories = []
        for category_id, category in self.categories.items():
            if category['is_leaf'] and category['item_count'] == 0:
                empty_categories.append(category_id)
        
        # Remove empty categories
        for category_id in empty_categories:
            category = self.categories[category_id]
            
            # Remove from parent's subcategories list if it has a parent
            if category['parent_id']:
                parent = self.categories.get(category['parent_id'])
                if parent and category_id in parent.get('subcategories', []):
                    parent['subcategories'].remove(category_id)
            
            # Remove the category itself
            del self.categories[category_id]
            
            # Remove associated specs if any
            if category_id in self.specs:
                del self.specs[category_id]
            
            print(f"   🗑️  Removed empty category: {category['name']} (ID: {category_id})")
        
        print(f"   ✅ Removed {len(empty_categories)} empty categories")

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
            'analysis_type': 'scrapingbee_category_tree',
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
                'score': score
            },
            'condition_breakdown': self._generate_condition_breakdown(self.scraped_items),
            'shipping_analysis': self._generate_shipping_analysis(self.scraped_items),
            'specs_collected': self.specs,
            'scraper_config': {
                'api_provider': 'ScrapingBee',
                'items_per_page': ScraperConfig.ITEMS_PER_PAGE,
                'max_pages_per_category': ScraperConfig.MAX_PAGES_PER_CATEGORY
            }
        }

        # Generate additional reports
        relevant_items = self.scraped_items
        
        seller_report = self._generate_seller_report(relevant_items, category_analysis)
        
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
        report['top_sellers_earnings_report'] = self._generate_top_sellers_earnings_report(relevant_items)
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
        """Calculate opportunity score (0-100) based on demand, competition, and price"""
        sold_count = sold_count or 0
        active_count = active_count or 0
        optimal_price = optimal_price or 0.0
        
        sold_count = max(0, int(sold_count))
        active_count = max(0, int(active_count))
        optimal_price = max(0.0, float(optimal_price))
        
        score = 0
        
        # Demand scoring (0-40 points)
        if sold_count >= 20:
            score += 40
        elif sold_count >= 10:
            score += 35
        elif sold_count >= 5:
            score += 25
        elif sold_count >= 3:
            score += 15
        elif sold_count >= 1:
            score += 5
        
        # Competition scoring (0-30 points)
        if active_count == 0:
            score += 30
        elif active_count < 5:
            score += 30
        elif active_count < 10:
            score += 25
        elif active_count < 15:
            score += 20
        elif active_count < 25:
            score += 15
        elif active_count < 50:
            score += 10
        elif active_count < 100:
            score += 5
        
        # Price scoring (0-30 points)
        if optimal_price >= 500:
            score += 30
        elif optimal_price >= 200:
            score += 25
        elif optimal_price >= 100:
            score += 20
        elif optimal_price >= 50:
            score += 15
        elif optimal_price >= 25:
            score += 10
        elif optimal_price >= 10:
            score += 5
        
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
        query_lower = query.lower()
        exclude_words = {
            'car', 'truck', 'vehicle', 'parts', 'accessories', 'part',
            'for', 'the', 'a', 'an', 'and', 'or', 'of', 'in', 'on', 'at', 'to', 'from',
            'used', 'new', 'oem', 'genuine', 'original', 'aftermarket',
            'left', 'right', 'front', 'rear', 'driver', 'passenger',
            'side', 'l', 'r', 'lh', 'rh', 'l/r', 'left/right'
        }
        
        years = set()
        year_pattern = r'\b(19\d{2}|20\d{2})\b'
        year_matches = re.findall(year_pattern, query)
        years.update(year_matches)
        
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
            if make in query_lower:
                if ' ' in make:
                    if make in query_lower:
                        makes.add(make)
                else:
                    if make in query_words:
                        makes.add(make)
        
        models = set()
        if makes:
            for make in makes:
                make_pos = query_lower.find(make)
                if make_pos >= 0:
                    after_make = query_lower[make_pos + len(make):].strip()
                    if after_make:
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

    def _clean_title(self, title: str) -> str:
        """Clean title by removing unwanted text patterns"""
        if not title:
            return title
        
        # Remove "Opens in a new window or tab" (case-insensitive)
        title = re.sub(r'\s*Opens\s+in\s+a\s+new\s+window\s+or\s+tab\s*', ' ', title, flags=re.IGNORECASE)
        
        # Remove "(For: ...)" pattern - matches (For: anything)
        title = re.sub(r'\(For:\s*[^)]+\)', '', title, flags=re.IGNORECASE)
        
        # Clean up extra whitespace
        title = re.sub(r'\s+', ' ', title).strip()
        
        return title

    def _generate_word_frequency_analysis(self, items: List[Dict], query: str) -> Dict:
        """Generate word frequency analysis for items"""
        from collections import Counter
        
        car_details = self._extract_car_details_from_query(query)
        exclude_all = set()
        exclude_all.update(car_details['years'])
        exclude_all.update(car_details['makes'])
        exclude_all.update(car_details['models'])
        exclude_all.update(car_details['exclude_words'])
        
        exclude_all_lower = {w.lower() for w in exclude_all}
        
        word_counter = Counter()
        total_titles = 0
        
        for item in items:
            title = item.get('title', '')
            if not title:
                continue
            
            total_titles += 1
            
            # Clean title by removing unwanted patterns
            title = self._clean_title(title)
            
            title_clean = re.sub(r'[^\w\s&-]', ' ', title.lower())
            words = [w.strip() for w in title_clean.split() if w.strip()]
            
            filtered_words = []
            for word in words:
                word_clean = word.strip('.,!?;:()[]{}"\'-_')
                if len(word_clean) < 2:
                    continue
                if word_clean.lower() in exclude_all_lower:
                    continue
                if word_clean.isdigit():
                    if len(word_clean) == 4 or len(word_clean) > 6:
                        continue
                filtered_words.append(word_clean.lower())
            
            word_counter.update(filtered_words)
        
        top_words = word_counter.most_common(50)
        
        total_words = sum(word_counter.values())
        unique_words = len(word_counter)
        
        word_freq_ranges = {
            'very_high': 0,
            'high': 0,
            'medium': 0,
            'low': 0,
            'very_low': 0
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

    def _generate_main_recommendation(self, category_analysis: List[Dict]) -> tuple:
        """Generate main recommendation"""
        if not category_analysis:
            return "Insufficient data", 0

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

    def _generate_seller_report(self, items: List[Dict], category_analysis: List[Dict] = None) -> Dict:
        """Generate seller analysis report"""
        from collections import defaultdict
        
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
            listing_type = item.get('listing_type', 'active')
            seller_feedback = item.get('seller_feedback', '')
            location = item.get('location', '')
            category_id = item.get('category_id', '')
            
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
        
        seller_list.sort(key=lambda x: x['listings_count'], reverse=True)
        
        total_sellers = len(seller_list)
        top_sellers = seller_list[:10]
        
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
        """Generate price distribution report"""
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
        
        q1_idx = int(n * 0.25)
        q2_idx = int(n * 0.50)
        q3_idx = int(n * 0.75)
        
        q1 = sorted_prices[q1_idx] if q1_idx < n else sorted_prices[-1]
        q2 = sorted_prices[q2_idx] if q2_idx < n else sorted_prices[-1]
        q3 = sorted_prices[q3_idx] if q3_idx < n else sorted_prices[-1]
        
        iqr = q3 - q1
        
        min_price = min(prices)
        max_price = max(prices)
        mean_price = statistics.mean(prices)
        median_price = statistics.median(prices)
        std_dev = statistics.stdev(prices) if len(prices) > 1 else 0
        
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
        
        active_prices = [self._clean_price(item.get('price')) for item in items 
                         if item.get('listing_type') == 'active']
        active_prices = [p for p in active_prices if p and p > 0]
        
        sold_prices = [self._clean_price(item.get('price')) for item in items 
                       if item.get('listing_type') == 'sold']
        sold_prices = [p for p in sold_prices if p and p > 0]
        
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
        
        seller_counts = Counter([i.get('seller', 'Unknown') for i in active_items])
        seller_counts = {k: v for k, v in seller_counts.items() if k != 'Unknown'}
        
        total_sellers = len(seller_counts)
        top_10_sellers = dict(list(sorted(seller_counts.items(), key=lambda x: x[1], reverse=True))[:10])
        top_10_percentage = (sum(top_10_sellers.values()) / len(active_items) * 100) if active_items else 0
        
        if active_items and seller_counts:
            market_shares = [count / len(active_items) * 100 for count in seller_counts.values()]
            hhi = sum(share ** 2 for share in market_shares)
        else:
            hhi = 0
        
        if len(active_items) < 10:
            competition_level = "Low"
            competition_color = "green"
        elif len(active_items) < 30:
            competition_level = "Medium"
            competition_color = "yellow"
        else:
            competition_level = "High"
            competition_color = "red"
        
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
        
        locations = Counter([i.get('location', '') for i in active_items if i.get('location')])
        top_locations = dict(list(sorted(locations.items(), key=lambda x: x[1], reverse=True))[:5])
        
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
        """Generate time-based analysis report"""
        import statistics
        
        active_items = [i for i in items if i.get('listing_type') == 'active']
        sold_items = [i for i in items if i.get('listing_type') == 'sold']
        
        active_prices = [self._clean_price(i.get('price')) for i in active_items]
        active_prices = [p for p in active_prices if p and p > 0]
        
        sold_prices = [self._clean_price(i.get('price')) for i in sold_items]
        sold_prices = [p for p in sold_prices if p and p > 0]
        
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
        
        volume_trend = {
            'current_active_listings': len(active_items),
            'historical_sold_listings': len(sold_items),
            'active_to_sold_ratio': round(len(active_items) / len(sold_items), 2) if sold_items else 0,
            'market_activity': 'High' if len(active_items) > len(sold_items) else 
                            'Moderate' if len(active_items) > len(sold_items) * 0.5 else 'Low'
        }
        
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

    def _generate_top_sellers_earnings_report(self, items: List[Dict]) -> Dict:
        """Generate top sellers earnings report - shows how much top sellers earned from sold parts"""
        from collections import defaultdict
        
        # Only analyze SOLD items for earnings calculation
        sold_items = [item for item in items if item.get('listing_type') == 'sold']
        
        if not sold_items:
            return {
                'error': 'No sold items available for earnings calculation',
                'top_sellers_by_earnings': [],
                'summary': {
                    'total_sellers': 0,
                    'total_earnings': 0,
                    'total_parts_sold': 0
                }
            }
        
        seller_stats = defaultdict(lambda: {
            'sold_count': 0,
            'total_gross_revenue': 0.0,
            'total_shipping_revenue': 0.0,
            'items': [],
            'feedback': ''
        })
        
        # Calculate earnings for each seller based on sold items
        for item in sold_items:
            seller = item.get('seller', 'Unknown')
            if seller == 'Unknown':
                continue
            
            price = self._clean_price(item.get('price', 0)) or 0
            shipping_cost = item.get('shipping_cost', 0) or 0
            seller_feedback = item.get('seller_feedback', '')
            
            seller_stats[seller]['sold_count'] += 1
            seller_stats[seller]['total_gross_revenue'] += price
            seller_stats[seller]['total_shipping_revenue'] += shipping_cost
            seller_stats[seller]['items'].append({
                'title': item.get('title', ''),
                'price': price,
                'shipping': shipping_cost,
                'item_id': item.get('item_id', '')
            })
            
            if seller_feedback and not seller_stats[seller]['feedback']:
                seller_stats[seller]['feedback'] = seller_feedback
        
        # Calculate net earnings (after eBay fees)
        seller_list = []
        for seller, stats in seller_stats.items():
            if stats['sold_count'] == 0:
                continue
            
            # eBay fees: 13.25% of final value + $0.30 payment processing
            total_gross = stats['total_gross_revenue']
            total_shipping = stats['total_shipping_revenue']
            
            # Calculate fees per item and total
            ebay_fee_percentage = 0.1325  # 13.25%
            payment_fee_per_item = 0.30
            
            total_ebay_fees = total_gross * ebay_fee_percentage
            total_payment_fees = payment_fee_per_item * stats['sold_count']
            total_fees = total_ebay_fees + total_payment_fees
            
            # Net revenue = gross revenue - fees + shipping (shipping is usually kept by seller)
            net_revenue = total_gross - total_fees + total_shipping
            
            avg_gross_per_item = total_gross / stats['sold_count'] if stats['sold_count'] > 0 else 0
            avg_net_per_item = net_revenue / stats['sold_count'] if stats['sold_count'] > 0 else 0
            avg_fees_per_item = total_fees / stats['sold_count'] if stats['sold_count'] > 0 else 0
            
            seller_list.append({
                'seller_name': seller,
                'parts_sold': stats['sold_count'],
                'total_gross_earnings': round(total_gross, 2),
                'total_shipping_revenue': round(total_shipping, 2),
                'total_fees': round(total_fees, 2),
                'total_net_earnings': round(net_revenue, 2),
                'avg_gross_per_item': round(avg_gross_per_item, 2),
                'avg_net_per_item': round(avg_net_per_item, 2),
                'avg_fees_per_item': round(avg_fees_per_item, 2),
                'feedback': stats['feedback'],
                'sample_items': stats['items'][:5]  # First 5 items as sample
            })
        
        # Sort by total net earnings (most profitable sellers first)
        seller_list.sort(key=lambda x: x['total_net_earnings'], reverse=True)
        
        # Calculate summary statistics
        total_sellers = len(seller_list)
        total_gross_all = sum(s['total_gross_earnings'] for s in seller_list)
        total_net_all = sum(s['total_net_earnings'] for s in seller_list)
        total_parts_sold = sum(s['parts_sold'] for s in seller_list)
        total_fees_all = sum(s['total_fees'] for s in seller_list)
        
        # Get top 20 earners
        top_earners = seller_list[:20]
        
        # Calculate earnings tiers
        earnings_tiers = {
            'high_earners': len([s for s in seller_list if s['total_net_earnings'] >= 1000]),
            'medium_earners': len([s for s in seller_list if 500 <= s['total_net_earnings'] < 1000]),
            'low_earners': len([s for s in seller_list if s['total_net_earnings'] < 500])
        }
        
        return {
            'summary': {
                'total_unique_sellers': total_sellers,
                'total_parts_sold': total_parts_sold,
                'total_gross_earnings': round(total_gross_all, 2),
                'total_net_earnings': round(total_net_all, 2),
                'total_fees_paid': round(total_fees_all, 2),
                'avg_earnings_per_seller': round(total_net_all / total_sellers, 2) if total_sellers > 0 else 0,
                'avg_parts_per_seller': round(total_parts_sold / total_sellers, 2) if total_sellers > 0 else 0,
                'avg_net_per_part': round(total_net_all / total_parts_sold, 2) if total_parts_sold > 0 else 0
            },
            'top_sellers_by_earnings': top_earners,
            'earnings_tiers': earnings_tiers,
            'assumptions': {
                'ebay_fee_percentage': 13.25,
                'payment_fee_per_item': 0.30,
                'shipping_revenue_kept': True,
                'note': 'Earnings calculated from sold items only. Fees are estimates based on eBay standard rates.'
            }
        }
    
    def _generate_reports_summary(self, report: Dict) -> Dict:
        """Generate summary of all available and generated reports"""
        
        has_seller_report = 'seller_report' in report
        has_category_analysis = 'categories' in report
        has_top_opportunities = 'top_opportunities' in report
        has_market_overview = 'market_overview' in report
        has_data_summary = 'data_summary' in report
        has_price_distribution = 'price_distribution_report' in report
        has_competition_analysis = 'competition_analysis_report' in report
        has_category_performance = 'category_performance_report' in report
        has_time_analysis = 'time_based_analysis_report' in report
        has_car_disassembly = 'car_disassembly_profitability_report' in report
        
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
                'description': 'Performance metrics for each category',
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
                'generated': has_car_disassembly,
                'key': 'car_disassembly_profitability_report'
            },
            {
                'name': 'Top Sellers Earnings Report',
                'description': 'Analysis of top sellers earnings from sold parts, including gross revenue, net profit, and parts sold',
                'generated': 'top_sellers_earnings_report' in report,
                'key': 'top_sellers_earnings_report'
            }
        ]
        
        generated_reports = [r for r in all_reports if r['generated']]
        
        return {
            'generated_reports': generated_reports,
            'available_reports': all_reports,
            'total_generated': len(generated_reports),
            'total_available': len(all_reports)
        }


# ============================================================================
# SCRAPINGBEE SCRAPER
# ============================================================================

class ScrapingBeeScraper:
    """Scrape eBay using ScrapingBee API"""

    def __init__(self, query: str):
        self.query = query
        self.db = CategoryDB()
        self.visited_categories = set()
        self.request_count = 0

    def scrape(self) -> CategoryDB:
        """Main scraping pipeline"""
        print(f"\n{'='*80}")
        print(f"🚀 SCRAPINGBEE EBAY SCRAPER")
        print(f"{'='*80}")
        print(f"Query: '{self.query}'")
        print(f"Scraping: Both ACTIVE and SOLD items")
        print(f"Items per page: {ScraperConfig.ITEMS_PER_PAGE}")
        print(f"Max pages per category: {ScraperConfig.MAX_PAGES_PER_CATEGORY}")
        print(f"{'='*80}\n")

        print(f"\n{'='*80}")
        print(f"📂 STEP 1: BUILDING CATEGORY TREE")
        print(f"{'='*80}")
        if ScraperConfig.DEBUG:
            print(f"🐛 DEBUG MODE: Max leaf categories: {ScraperConfig.MAX_LEAF_CATEGORIES}")
        else:
            print(f"🚀 PRODUCTION MODE: No leaf category limit")

        self._build_category_tree()

        # Global deduplication across all categories
        print(f"\n{'='*80}")
        print(f"🔄 STEP 2: DEDUPLICATING ITEMS ACROSS ALL CATEGORIES")
        print(f"{'='*80}")
        initial_count = len(self.db.scraped_items)
        self.db._deduplicate_items_globally()
        deduplicated_count = len(self.db.scraped_items)
        duplicates_removed = initial_count - deduplicated_count
        print(f"   ✅ Deduplication complete!")
        print(f"   📊 Initial items: {initial_count:,}")
        print(f"   📊 After deduplication: {deduplicated_count:,}")
        print(f"   🗑️  Duplicates removed: {duplicates_removed:,}")

        # Remove empty leaf categories
        print(f"\n{'='*80}")
        print(f"🧹 STEP 3: REMOVING EMPTY CATEGORIES")
        print(f"{'='*80}")
        initial_leaf_count = len(self.db.get_leaf_categories())
        self.db._remove_empty_categories()
        final_leaf_count = len(self.db.get_leaf_categories())
        categories_removed = initial_leaf_count - final_leaf_count
        print(f"   ✅ Cleanup complete!")
        print(f"   📊 Initial leaf categories: {initial_leaf_count}")
        print(f"   📊 After cleanup: {final_leaf_count}")
        print(f"   🗑️  Empty categories removed: {categories_removed}")

        leaf_count = len(self.db.get_leaf_categories())
        print(f"\n✅ Category tree and item scraping complete!")
        print(f"   Total categories: {len(self.db.categories)}")
        print(f"   Leaf categories: {leaf_count}")
        print(f"   Total items scraped: {deduplicated_count:,}")
        print(f"   Total API requests: {self.request_count}")
        print(f"   💰 Optimization: Items scraped during tree traversal (saved ~{leaf_count * 2} requests!)")
        print(f"{'='*80}\n")

        return self.db

    def _ensure_english_locale(self, url: str) -> str:
        """Ensure eBay URL includes English locale parameters"""
        # Add locale parameters to force English/US locale
        if 'ebay.com' in url:
            # Parse URL to add locale parameters properly
            separator = '&' if '?' in url else '?'
            
            # Add user location parameter (forces US English locale)
            if '_ul=' not in url:
                url = f"{url}{separator}_ul=US"
                separator = '&'  # Next param should use &
            
            # Add site ID parameter for US eBay (1 = US site, ensures English)
            if '_fcid=' not in url:
                url = f"{url}{separator}_fcid=1"
        return url

    def _fetch_url(self, url: str, render_js: bool = True, wait_for: str = None,
                   js_scenario: str = None) -> BeautifulSoup:
        """Fetch URL using ScrapingBee API"""
        # Ensure English locale is set in URL
        url = self._ensure_english_locale(url)
        
        self.request_count += 1
        print(f"   📡 API Request #{self.request_count}: {url}...")

        if js_scenario:
            print(f"   🎬 Using JavaScript scenario for scrolling")

        params = ScrapingBeeConfig.get_scraping_params(url, render_js=render_js, wait_for=wait_for,
                                                       js_scenario=js_scenario)
        headers = {
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8'
            }
        try:
            response = requests.get(
                url=ScrapingBeeConfig.API_URL,
                params=params,
                headers=headers,
                timeout=60
            )

            if response.status_code == 200:
                print(f"   ✅ Success (Status: {response.status_code})")

                # Debug: Check ScrapingBee response headers
                if 'Spb-Cost' in response.headers:
                    print(f"   💰 Request cost: {response.headers['Spb-Cost']} credits")

                time.sleep(ScraperConfig.REQUEST_DELAY)  # Rate limiting
                return BeautifulSoup(response.content, 'html.parser')
            else:
                print(f"   ⚠️  Failed (Status: {response.status_code})")
                print(f"   Response: {response.text[:200]}")
                return None

        except Exception as e:
            print(f"   ❌ Request failed: {e}")
            return None

    def _build_category_tree(self):
        """Build category tree by traversing from root"""
        print(f"🔍 Searching for: '{self.query}'")

        # Build initial search URL
        search_url = f"https://www.ebay.com/sch/i.html?_nkw={quote(self.query)}"

        soup = self._fetch_url(search_url)
        if not soup:
            raise Exception("Failed to load eBay search page")
            
        print(f"✅ Search page loaded")

        # Navigate to target category
        print(f"\n🎯 Navigating to category {ScraperConfig.TARGET_CATEGORY}...")
        category_url = f"https://www.ebay.com/sch/{ScraperConfig.TARGET_CATEGORY}/i.html?_nkw={quote(self.query)}"

        print(f"\n🌳 Starting category tree traversal...")
        category_id = str(ScraperConfig.TARGET_CATEGORY)
        category_name = "Car & Truck Parts & Accessories"
          
        self._traverse_categories(
            category_id=category_id,
            category_name=category_name,
            category_url=category_url,
            parent_id=None,
            depth=0
        )

    def _traverse_categories(self, category_id: str, category_name: str,
                            category_url: str, parent_id: Optional[str], depth: int):
        """Recursively traverse category tree"""

        # Skip excluded top-level categories
        if category_id in ScraperConfig.EXCLUDED_TOP_LEVEL_CATEGORIES:
            indent = '  ' * depth
            print(f"{indent}⏭️  Skipping excluded top-level category: {category_name} (ID: {category_id})")
            return

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

        # JavaScript to scroll the sidebar to load all filters
        scroll_js = """
        {
            "instructions": [
                {"wait": 1000},
                {"scroll_y": 500},
                {"wait": 500},
                {"scroll_y": 1000},
                {"wait": 500},
                {"scroll_y": 1500},
                {"wait": 1000}
            ]
        }
        """

        soup = self._fetch_url(category_url, js_scenario=scroll_js)
        if not soup:
            print(f"{indent}   ❌ Failed to load category page")
            return

        print(f"{indent}   🔍 Extracting subcategories...")
        subcategories = self._extract_subcategories(soup, category_id)

        is_leaf = len(subcategories) == 0

        print(f"{indent}   🔍 Extracting specs...")
        specs = self._extract_specs(soup)

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

        # Check if we've reached the max leaf categories limit
        if ScraperConfig.DEBUG:
            current_leaf_count = len(self.db.get_leaf_categories())
            if current_leaf_count >= ScraperConfig.MAX_LEAF_CATEGORIES:
                self._scrape_items_from_leaf(
                    category_id=category_id,
                    category_name=category_name,
                    first_page_soup=soup,
                    depth=depth
                )
                print(f"{indent}   ⚡ Reached max leaf categories limit ({ScraperConfig.MAX_LEAF_CATEGORIES})!")
                return

        if not is_leaf and subcategories:
            current_leaf_count = len(self.db.get_leaf_categories())
            if ScraperConfig.DEBUG:
                print(f"{indent}   📂 Will explore subcategories (current leaf count: {current_leaf_count}/{ScraperConfig.MAX_LEAF_CATEGORIES})...")
            else:
                print(f"{indent}   📂 Will explore {len(subcategories)} subcategories...")

            for idx, subcat in enumerate(subcategories, 1):
                if ScraperConfig.DEBUG:
                    if len(self.db.get_leaf_categories()) >= ScraperConfig.MAX_LEAF_CATEGORIES:
                        self._scrape_items_from_leaf(
                            category_id=category_id,
                            category_name=category_name,
                            first_page_soup=soup,
                            depth=depth
                        )
                        print(f"{indent}   ⚡ Reached max leaf categories limit!")
                        return
                
                print(f"{indent}   [{idx}/{len(subcategories)}] Traversing: {subcat['name']}")
                self._traverse_categories(
                    category_id=subcat['id'],
                    category_name=subcat['name'],
                    category_url=subcat['url'],
                    parent_id=category_id,
                    depth=depth + 1
                )
        else:
            print(f"{indent}   🍃 LEAF CATEGORY - Scraping items now (saves 2 requests)!")
            # Scrape items immediately using the current page we already fetched
            self._scrape_items_from_leaf(
                category_id=category_id,
                category_name=category_name,
                first_page_soup=soup,
                depth=depth
            )

    def _scrape_items_from_leaf(self, category_id: str, category_name: str,
                               first_page_soup: BeautifulSoup, depth: int):
        """Scrape items from a leaf category immediately using the already-fetched page"""
        indent = '  ' * depth

        # Scrape both SOLD and ACTIVE items
        for listing_type in ['sold', 'active']:
            print(f"{indent}   📦 [{listing_type.upper()}] Scraping items...")

            # Build URL for this listing type
            base_url = f"https://www.ebay.com/sch/{category_id}/i.html"
            query_params = [
                f"_nkw={quote(self.query)}",
                f"_ipg={ScraperConfig.ITEMS_PER_PAGE}",
                "LH_ItemCondition=3000"  # Used condition
            ]

            if listing_type == 'sold':
                query_params.extend([
                    "LH_Sold=1",
                    "LH_Complete=1",
                    "rt=nc"
                ])

            first_page_url = f"{base_url}?{'&'.join(query_params)}"

            # Only fetch the page if we need SOLD or ACTIVE items
            # (first_page_soup might be for the category page without filters)
            # Wait for the results heading to ensure page is fully loaded
            soup = self._fetch_url(first_page_url, wait_for=".srp-controls__count-heading")

            if not soup:
                print(f"{indent}      ⚠️  Failed to load {listing_type} page, skipping...")
                continue
                
            # Get total count
            total_count = self._get_total_count(soup)

            if total_count == 0:
                print(f"{indent}      ⚠️  No {listing_type} items found")
                continue

            # Calculate pages
            total_pages = math.ceil(total_count / ScraperConfig.ITEMS_PER_PAGE)
            max_pages = min(total_pages, ScraperConfig.MAX_PAGES_PER_CATEGORY) if ScraperConfig.MAX_PAGES_PER_CATEGORY > 0 else total_pages

            print(f"{indent}      📊 Total: {total_count:,} items, Will scrape: {max_pages} pages")

            all_items = []
            items_needed = total_count  # Track how many items we still need

            # Extract items from first page (already fetched)
            page_items = self._extract_items_from_page(soup, listing_type)
            if page_items:
                # Only take the number of items we need
                items_to_take = min(len(page_items), items_needed)
                all_items.extend(page_items[:items_to_take])
                items_needed -= items_to_take
                print(f"{indent}      ✅ Page 1: {len(page_items)} items found, took {items_to_take} items ({items_needed} remaining)")
                
                # If we already have all needed items, skip pagination
                if items_needed <= 0:
                    print(f"{indent}      ✅ Got all {total_count} items from page 1, skipping pagination")

            # Scrape remaining pages only if we still need more items
            if items_needed > 0:
                for page_num in range(2, max_pages + 1):
                    query_params_with_page = query_params + [f"_pgn={page_num}"]
                    url = f"{base_url}?{'&'.join(query_params_with_page)}"

                    soup = self._fetch_url(url, wait_for="#srp-river-results")

                    if not soup:
                        print(f"{indent}      ⚠️  Failed to load page {page_num}, stopping...")
                        break  # Stop pagination if we can't load the page

                    page_items = self._extract_items_from_page(soup, listing_type)
                    
                    if not page_items:
                        print(f"{indent}      ⚠️  Page {page_num}: No items found - stopping pagination")
                        break  # Stop pagination - no more items available
                    
                    # Only take the number of items we still need
                    items_to_take = min(len(page_items), items_needed)
                    all_items.extend(page_items[:items_to_take])
                    items_needed -= items_to_take
                    
                    print(f"{indent}      ✅ Page {page_num}: {len(page_items)} items found, took {items_to_take} items ({items_needed} remaining)")
                    
                    # If we've got all needed items, stop pagination
                    if items_needed <= 0:
                        print(f"{indent}      ✅ Got all {total_count} items, stopping pagination")
                        break

            # Add items to database
            if all_items:
                self.db.add_items(category_id, all_items)
                print(f"{indent}      ✅ [{listing_type.upper()}] Total: {len(all_items)} items scraped")

    def _extract_subcategories(self, soup: BeautifulSoup, current_category_id: str) -> List[Dict]:
        """Extract subcategories from eBay sidebar"""
        subcategories = []

        try:
            # Find "Selected category" span
            selected_span = soup.find('span', class_='clipped', string=re.compile('Selected category', re.I))

            if not selected_span:
                print(f"      🍃 No 'Selected category' span found - LEAF CATEGORY")
                return []
            
            # Get parent li
            parent_li = selected_span.find_parent('li')
            if not parent_li:
                print(f"      ❌ No parent <li> found")
                return []
            
            # Look for child ul
            child_ul = parent_li.find('ul', recursive=False)
            if not child_ul:
                print(f"      🍃 No child <ul> found - LEAF CATEGORY")
                return []
            
            # Extract subcategories
            seen_ids = set()
            for li in child_ul.find_all('li', recursive=False):
                try:
                    # Skip if this LI has "Selected category"
                    if li.find('span', class_='clipped', string=re.compile('Selected category', re.I)):
                        continue
                    
                    a_tag = li.find('a', href=re.compile(r'/sch/\d+/'))
                    if not a_tag:
                        continue
                    
                    href = a_tag.get('href', '')
                    text = a_tag.get_text(strip=True)
                    
                    if not href or not text:
                        continue
                    
                    cat_id_match = re.search(r'/sch/(\d+)/', href)
                    if not cat_id_match:
                        continue
                    
                    cat_id = cat_id_match.group(1)
                    
                    # Skip if this is an excluded top-level category
                    if cat_id in ScraperConfig.EXCLUDED_TOP_LEVEL_CATEGORIES:
                        print(f"      ⏭️  Skipping excluded top-level category: {text} (ID: {cat_id})")
                        continue
                    
                    # Skip if already visited or is current category
                    if cat_id == current_category_id or cat_id in self.visited_categories or cat_id in seen_ids:
                        continue
                    
                    seen_ids.add(cat_id)
                    
                    if not href.startswith('http'):
                        href = urljoin('https://www.ebay.com', href)
                    
                    subcategories.append({
                        'id': cat_id,
                        'name': text,
                        'url': href
                    })
                    print(f"      ✅ Added: {text[:40]} (ID: {cat_id})")
                    
                except Exception:
                    continue

        except Exception as e:
            print(f"      ❌ Error extracting subcategories: {e}")

        print(f"      📊 Total subcategories: {len(subcategories)}")
        return subcategories
  
    def _extract_specs(self, soup: BeautifulSoup) -> List[Dict]:
        """Extract available specs/filters with options"""
        specs = []
        
        print(f"        🔍 COLLECTING SIDEBAR SPECS")
        
        try:
            # Debug: Check what's in the sidebar
            sidebar = soup.find('div', id='x-refine__group__0')
            if sidebar:
                print(f"        ✅ Found main sidebar div")
                # Count all divs with IDs matching the pattern
                all_divs_with_pattern = soup.find_all('div', id=re.compile(r'x-refine__group_\d+'))
                print(f"        📊 Total divs with x-refine__group pattern: {len(all_divs_with_pattern)}")

                # Show first few IDs
                if all_divs_with_pattern:
                    sample_ids = [d.get('id') for d in all_divs_with_pattern[:10]]
                    print(f"        🔍 Sample IDs: {sample_ids}")
            else:
                print(f"        ⚠️  Main sidebar div #x-refine__group__0 NOT found")

            # Find all filter sections - match x-refine__group_N__M (any numbers)
            filter_sections = soup.find_all('div', id=re.compile(r'x-refine__group_\d+__\d+'))
            print(f"        📊 Found {len(filter_sections)} filter sections with pattern x-refine__group_N__M")

            for section in filter_sections:
                try:
                    # Find the h3 title
                    h3 = section.find_previous('h3')
                    if not h3:
                        continue
                    
                    spec_name = h3.get_text(strip=True)

                    # Skip certain filters
                    exclude_names = ['Category', 'Price', 'Buying Format', 'Item Location',
                                   'Shipping and pickup', 'Show only']
                    if spec_name in exclude_names:
                        continue
                    
                    print(f"        ✅ Processing filter: '{spec_name}'")
                    
                    # Extract options
                    options = []
                    option_lis = section.find_all('li')
                    
                    for option_li in option_lis:
                        try:
                            option_link = option_li.find('a')
                            if not option_link:
                                continue
                            
                            option_text = option_link.get_text(strip=True)
                            if not option_text:
                                continue
                            
                            # Parse: "Option Name (24)" - extract name and count
                            name_match = re.match(r'^([^(]+)', option_text)
                            name = name_match.group(1).strip() if name_match else option_text
                            
                            amount_matches = re.findall(r'\((\d+)\)', option_text)
                            amount = int(amount_matches[-1]) if amount_matches else 0
                            
                            options.append({'name': name, 'amount': amount})
                            
                        except Exception:
                            continue
                    
                    if options:
                        total = sum(opt['amount'] for opt in options)
                        for opt in options:
                            opt['percent'] = round((opt['amount'] / total * 100) if total > 0 else 0, 2)
                        
                        specs.append({
                            'name': spec_name,
                            'values': options
                        })
                        print(f"        ✅ Collected spec '{spec_name}': {len(options)} values")
                        
                except Exception as e:
                    print(f"        ⚠️  Error collecting spec: {e}")
                    continue
                    
        except Exception as e:
            print(f"        ⚠️  Error in sidebar specs collection: {e}")
        
        print(f"        ✅ Completed collecting sidebar specs: {len(specs)} specs")
        return specs

    def _scrape_leaf_categories(self, listing_type: str):
        """Scrape items from all leaf categories"""
        leaf_categories = self.db.get_leaf_categories()
        
        if ScraperConfig.DEBUG and len(leaf_categories) > ScraperConfig.MAX_LEAF_CATEGORIES:
            print(f"   🐛 DEBUG MODE: Limiting to first {ScraperConfig.MAX_LEAF_CATEGORIES} leaf categories")
            leaf_categories = leaf_categories[:ScraperConfig.MAX_LEAF_CATEGORIES]

        print(f"\n📦 Found {len(leaf_categories)} leaf categories to scrape ({listing_type})")

        if not leaf_categories:
            print(f"   ⚠️  No leaf categories found!")
            return

        print(f"\n📋 Leaf categories to scrape:")
        for idx, cat in enumerate(leaf_categories, 1):
            print(f"   {idx}. {cat['name']} (ID: {cat['id']})")

        print(f"\n🚀 Starting {listing_type} scraping...")

        for cat in leaf_categories:
            self._scrape_category_items(cat, listing_type)

        print(f"\n✅ All leaf categories scraped ({listing_type})!")

    def _scrape_category_items(self, category: Dict, listing_type: str):
        """Scrape items from a single category"""
        category_id = category['id']
        category_name = category['name']

        print(f"\n📦 [{listing_type.upper()}] [{category_name}] Starting item scraping...")

        # Build URL for first page
        base_url = f"https://www.ebay.com/sch/{category_id}/i.html"
        query_params = [
            f"_nkw={quote(self.query)}",
            f"_ipg={ScraperConfig.ITEMS_PER_PAGE}",
            "LH_ItemCondition=3000"  # Used condition
        ]
        
        if listing_type == 'sold':
            query_params.extend([
                "LH_Sold=1",
                "LH_Complete=1",
                "rt=nc"
            ])
        
        first_page_url = f"{base_url}?{'&'.join(query_params)}"
        
        print(f"   🔗 Loading first page to get total count...")
        soup = self._fetch_url(first_page_url)

        if not soup:
            print(f"   ⚠️  Failed to load category page, skipping...")
            return
                
        # Get total count
        total_count = self._get_total_count(soup)
        
        if total_count == 0:
            print(f"   ⚠️  No items found, skipping category...")
            return
                
        # Calculate pages
        total_pages = math.ceil(total_count / ScraperConfig.ITEMS_PER_PAGE)
        max_pages = min(total_pages, ScraperConfig.MAX_PAGES_PER_CATEGORY) if ScraperConfig.MAX_PAGES_PER_CATEGORY > 0 else total_pages
                
        print(f"   📊 Total items: {total_count:,}")
        print(f"   📄 Total pages: {total_pages}, Will scrape: {max_pages}")

        all_items = []
        items_needed = total_count  # Track how many items we still need

        # Extract items from first page
        print(f"   📄 Extracting items from page 1...")
        page_items = self._extract_items_from_page(soup, listing_type)
        if page_items:
            # Only take the number of items we need
            items_to_take = min(len(page_items), items_needed)
            all_items.extend(page_items[:items_to_take])
            items_needed -= items_to_take
            print(f"   ✅ Page 1: {len(page_items)} items found, took {items_to_take} items ({items_needed} remaining)")
            
            # If we already have all needed items, skip pagination
            if items_needed <= 0:
                print(f"   ✅ Got all {total_count} items from page 1, skipping pagination")

        # Scrape remaining pages only if we still need more items
        if items_needed > 0:
            for page_num in range(2, max_pages + 1):
                query_params_with_page = query_params + [f"_pgn={page_num}"]
                url = f"{base_url}?{'&'.join(query_params_with_page)}"
                
                print(f"   📄 Loading page {page_num}/{max_pages}...")
                soup = self._fetch_url(url, wait_for="#srp-river-results")

                if not soup:
                    print(f"   ⚠️  Failed to load page {page_num}, stopping...")
                    break  # Stop pagination if we can't load the page

                page_items = self._extract_items_from_page(soup, listing_type)
                
                if not page_items:
                    print(f"   ⚠️  Page {page_num}: No items found - stopping pagination")
                    break  # Stop pagination - no more items available
                
                # Only take the number of items we still need
                items_to_take = min(len(page_items), items_needed)
                all_items.extend(page_items[:items_to_take])
                items_needed -= items_to_take
                
                print(f"   ✅ Page {page_num}: {len(page_items)} items found, took {items_to_take} items ({items_needed} remaining)")
                
                # If we've got all needed items, stop pagination
                if items_needed <= 0:
                    print(f"   ✅ Got all {total_count} items, stopping pagination")
                    break

        # Add items to database
        if all_items:
            self.db.add_items(category_id, all_items)
            print(f"\n   ✅ [{listing_type.upper()}] [{category_name}] Scraped {len(all_items)} items total")
        else:
            print(f"\n   ⚠️  [{listing_type.upper()}] [{category_name}] No items extracted")

    def _get_total_count(self, soup: BeautifulSoup) -> int:
        """Extract total number of items"""
        try:
            # Try to find result count
            count_elem = soup.find('h1', class_='srp-controls__count-heading')
            if count_elem:
                text = count_elem.get_text()
                # Extract number from text like "1,234 results" or "1,400+ results"
                match = re.search(r'([\d,]+)\+?\s*results?', text, re.I)
                if match:
                    count_str = match.group(1).replace(',', '')
                    return int(count_str)
                else:
                    print(f"      ⚠️  Found count element but no number match in: '{text[:100]}'")
            else:
                print(f"      ⚠️  No .srp-controls__count-heading element found")
                # Try alternative selectors
                alt_count = soup.find('span', class_='BOLD')
                if alt_count:
                    text = alt_count.get_text()
                    match = re.search(r'([\d,]+)', text)
                    if match:
                        count_str = match.group(1).replace(',', '')
                        print(f"      ✅ Found count using alternative selector: {count_str}")
                        return int(count_str)

            return 0
        except Exception as e:
            print(f"      ⚠️  Error getting total count: {e}")
            return 0

    def _extract_items_from_page(self, soup: BeautifulSoup, listing_type: str) -> List[Dict]:
        """Extract items from current page (matching scrape_fast_withproxy.py logic)"""
        items = []

        try:
            # Check for results container first
            results_container = soup.find('div', id='srp-river-results')
            if not results_container:
                    return []

            # Try multiple selectors (matching scrape_fast_withproxy.py logic)
            listings = None
            
            # Try selector 1: #srp-river-results ul li.s-card
            listings = results_container.select('ul li.s-card')
            if not listings:
                # Try selector 2: .s-card (within results container)
                listings = results_container.select('.s-card')
            if not listings:
                # Try selector 3: #srp-river-results li[class*='s-item']
                listings = results_container.select('li[class*="s-item"]')
            if not listings:
                # Try selector 4: li.s-item (within results container)
                listings = results_container.select('li.s-item')
            
            # If still no listings found, try searching the whole soup
            if not listings:
                listings = soup.select('#srp-river-results ul li.s-card')
            if not listings:
                listings = soup.select('.s-card')
            if not listings:
                listings = soup.select('li[class*="s-item"]')
            if not listings:
                listings = soup.select('li.s-item')
            
            if not listings:
                    return []

            # Extract items from each listing
            for listing_elem in listings:
                try:
                    # Convert BeautifulSoup element to HTML string for parsing
                    listing_html = str(listing_elem)
                    listing = self._parse_listing_block(listing_html)

                    if listing and listing.get('item_id'):
                        listing['listing_type'] = listing_type
                        items.append(listing)
                except Exception as e:
                    logger.debug(f"Error extracting item: {e}")
                    continue

        except Exception as e:
            logger.warning(f"Could not extract items: {e}")

        return items

    def _parse_listing_block(self, block: str) -> Optional[Dict]:
        """Parse HTML block to extract listing data (using BeautifulSoup)"""
        try:
            soup = BeautifulSoup(block, 'html.parser')
            
            # Title - try s-card__title
            title = None
            title_elem = soup.select_one('.s-card__title, [class*="s-card__title"]')
            if title_elem:
                # Get text content, removing nested tags
                title = title_elem.get_text(strip=True)
                # Clean title by removing unwanted patterns (using CategoryDB's method)
                title = self.db._clean_title(title)
            
            # Price - try s-card__price
            price = 0.0
            price_elem = soup.select_one('.s-card__price, [class*="s-card__price"]')
            if price_elem:
                price_text = price_elem.get_text(strip=True)
                price_clean = re.sub(r'[^0-9.]', '', price_text)
                try:
                    price = float(price_clean)
                except:
                    pass

            # URL and item_id
            item_id = None
            url = None
            url_elem = soup.find('a', href=re.compile(r'/itm/\d+'))
            if url_elem:
                url = url_elem.get('href', '')
                if not url.startswith('http'):
                    url = 'https://www.ebay.com' + url
                id_match = re.search(r'/itm/(\d+)', url)
                if id_match:
                    item_id = id_match.group(1)

            # Image URL
            image_url = ""
            img_elem = soup.find('img')
            if img_elem:
                image_url = img_elem.get('src', '') or img_elem.get('data-src', '')

            # Shipping cost
            shipping_cost = 0.0
            shipping_text = soup.get_text()
            shipping_match = re.search(r'\+\$?([\d.,]+)\s+shipping', shipping_text, re.I)
            if shipping_match:
                try:
                    shipping_cost = float(re.sub(r'[^0-9.]', '', shipping_match.group(1)))
                except:
                    pass

            if re.search(r'free\s+shipping', shipping_text, re.I):
                shipping_cost = 0.0

            # Seller info - extract from s-card__attribute-row divs
            seller = "Unknown"
            seller_feedback = ""
            
            # Find all div.s-card__attribute-row elements
            attr_rows = soup.find_all('div', class_=re.compile(r's-card__attribute-row'))
            
            for attr_row in attr_rows:
                # Get clean text from this attribute row
                inner_text = attr_row.get_text(separator=' ', strip=True)
                inner_text = re.sub(r'\s+', ' ', inner_text).strip()
                
                # Pattern: "german-831  99.3% positive (5.8K)" or "username 100% positive (1K)"
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
                seller_elem = soup.select_one('.s-card__seller-info, [class*="s-card__seller-info"]')
                if seller_elem:
                    seller_text = seller_elem.get_text(strip=True)
                    if seller_text and not seller_text.startswith('$'):
                        seller = seller_text or "Unknown"
                
                # Try looking for seller name pattern in other places
                if seller == "Unknown":
                    seller_elem = soup.find(attrs={'data-testid': 'seller-name'})
                    if seller_elem:
                        seller_text = seller_elem.get_text(strip=True)
                        if seller_text and not seller_text.startswith('$') and not seller_text.replace('.', '').isdigit():
                            seller = seller_text
            
            # Condition
            condition = "Used"
            condition_elem = soup.find('span', class_='SECONDARY_INFO')
            if condition_elem:
                condition = condition_elem.get_text(strip=True)

            # Sold date
            sold_date = None
            date_match = re.search(r'Sold\s+([A-Z][a-z]+\s+\d{1,2})', soup.get_text())
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
                'source': 'scrapingbee_scraper'
            }
        except Exception as e:
            logger.debug(f"Error parsing listing block: {e}")
            return None


# ============================================================================
# MAIN FUNCTION
# ============================================================================
def print_rich_report(db: CategoryDB, query: str, output_file: str):
    """Generate and print a comprehensive rich report"""

    print(f"\n\n{'='*80}")
    print(f"📊 EBAY SCRAPINGBEE SCRAPER - FINAL REPORT")
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
            import statistics
            print(f"\n  💰 PRICE STATISTICS")
            print(f"  {'─'*76}")
            print(f"    Min Price:              ${min(prices):.2f}")
            print(f"    Max Price:              ${max(prices):.2f}")
            print(f"    Average Price:          ${statistics.mean(prices):.2f}")
            print(f"    Median Price:           ${statistics.median(prices):.2f}")

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
    print(f"  API Provider:             ScrapingBee")
    print(f"  Items Per Page:           {ScraperConfig.ITEMS_PER_PAGE}")
    print(f"  Max Pages Per Category:   {ScraperConfig.MAX_PAGES_PER_CATEGORY}")
    if ScraperConfig.DEBUG:
        print(f"  Debug Mode:               Enabled")
        print(f"  Max Leaf Categories:      {ScraperConfig.MAX_LEAF_CATEGORIES}")
    else:
        print(f"  Debug Mode:               Disabled")

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

def main():
    """Main entry point"""
    import sys

    # Get query from command line or use default
    query = sys.argv[1] if len(sys.argv) > 1 else "2007 toyota prius"

    # Create scraper
    scraper = ScrapingBeeScraper(query)

    # Run scraper
    try:
        db = scraper.scrape()

        # Generate output filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_query = re.sub(r'[^\w\s-]', '', query).strip().replace(' ', '_')
        output_file = f"scrapingbee_{safe_query}_{timestamp}.json"
        # Generate and print report
        print_rich_report(db, query, output_file)
        # Export report
        print(f"\n{'='*80}")
        print(f"💾 EXPORTING REPORT")
        print(f"{'='*80}")
        db.export_to_json(output_file, query)

        print(f"\n{'='*80}")
        print(f"✅ SCRAPING COMPLETE!")
        print(f"{'='*80}")
        print(f"   Total categories: {len(db.categories)}")
        print(f"   Leaf categories: {len(db.get_leaf_categories())}")
        print(f"   Total items: {len(db.scraped_items)}")
        print(f"   Report saved to: {output_file}")
        print(f"   Total API requests: {scraper.request_count}")
        print(f"{'='*80}\n")

    except Exception as e:
        print(f"\n❌ Scraping failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

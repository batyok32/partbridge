"""Simplified ScrapingBee scraper with Recursive DeepSeek Categorisation.

This module fetches listings, then enters a recursive AI loop to group
and normalize categories until a perfect taxonomy is achieved.
"""

from __future__ import annotations

import json
import logging
import re
import statistics
import time
import asyncio
from collections import Counter
import random
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Union
from difflib import SequenceMatcher

import openai  # type: ignore[import]
import aiohttp
from bs4 import BeautifulSoup
from django.conf import settings  # type: ignore[import]
from urllib.parse import quote

logger = logging.getLogger(__name__)

# --- CONFIGURATION --- #
class ScrapingBeeConfig:
    """Configuration helpers for the ScrapingBee API."""
    # API_KEY = getattr(settings, "SCRAPING_BEE_API_KEY", "")
    API_KEY="WTB6H8C9IXOP4E11KABV5MU20JWK4DOFXCHM55D4A8HD73J0IAEWG1GVI3PJN3QCS5GE8R1241YASFS8"
    API_URL = "https://app.scrapingbee.com/api/v1"
    DEFAULT_WAIT_MS = 8000
    REQUEST_DELAY_SECONDS = 2
    COUNTRY_CODE = "us"
    COOKIES = "lc=en-US;ebay=%5Esbf%3D%2340000000000100000000007089ed9fff%5E"

    @classmethod
    def build_params(cls, url: str, *, render_js: Optional[bool] = None, wait_for: Optional[str] = None, wait_ms: Optional[int] = None) -> Dict[str, str]:
        params = {
            "api_key": cls.API_KEY,
            "url": url,
            "render_js": str(render_js if render_js is not None else True).lower(),
            "country_code": cls.COUNTRY_CODE,
            "wait": str(wait_ms if wait_ms is not None else cls.DEFAULT_WAIT_MS),
            "cookies": cls.COOKIES,
            "forward_headers": "true",
        }
        if wait_for:
            params["wait_for"] = wait_for
        return params

def _safe_float(value: Optional[str]) -> Optional[float]:
    if not value: return None
    digits = "".join(ch for ch in value if ch.isdigit() or ch == ".")
    if not digits: return None
    try: return float(digits)
    except ValueError: return None

def _extract_text_blocks(response: Any) -> str:
    if hasattr(response, 'choices') and len(response.choices) > 0:
        return response.choices[0].message.content.strip()
    return str(response).strip()

def _extract_json_from_text(text: str) -> Optional[Union[dict, list]]:
    """Robustly extracts JSON object or array from LLM response text."""
    if not text: 
        return None
        
    # Regex to find the outermost valid JSON array [...] or object {...}
    # DOTALL allows dot (.) to match newlines
    match = re.search(r"(\[.*\]|\{.*\})", text, re.DOTALL)
    
    if match:
        json_candidate = match.group(1)
        try:
            return json.loads(json_candidate)
        except json.JSONDecodeError:
            # If standard load fails, sometimes there are trailing commas or similar issues
            # For now, we return None so the caller can handle/log it
            return None
    return None
@dataclass
class Listing:
    item_id: str
    title: str
    price: Optional[float]
    url: str
    shipping: Optional[float]
    page: int
    listing_type: str
    raw_title: str = field(default="")
    keep: bool = True
    category: Optional[str] = None
    classification_reason: Optional[str] = None
    seller: Optional[str] = None
    seller_feedback: Optional[str] = None
    image_url: Optional[str] = None

    def to_dict(self) -> Dict[str, object]:
        return {
            "item_id": self.item_id,
            "title": self.title,
            "price": self.price,
            "url": self.url,
            "shipping": self.shipping,
            "listing_type": self.listing_type,
            "category": self.category,
            "image_url": self.image_url,
        }

def _chunk_list(items: List[Any], size: int) -> Iterable[List[Any]]:
    for index in range(0, len(items), size):
        yield items[index : index + size]

class DeepSeekBatchCategorizer:
    """Categorise listings and then recursively consolidate categories."""

    def __init__(self, *, api_key: Optional[str] = None, model: Optional[str] = None, batch_size: int = 60) -> None:
        # api_key = api_key or getattr(settings, "DEEPSEEK_API_KEY", None)
        api_key = "sk-a5846913df044e1a813a1308e4efbea0"
        if not api_key: raise RuntimeError("DeepSeek API key required.")
        self.client = openai.AsyncOpenAI(api_key=api_key, base_url="https://api.deepseek.com/v1")
        self.model = model or "deepseek-chat"
        self.batch_size = batch_size
        self.semaphore = asyncio.Semaphore(10) # Max concurrent requests

    async def _send_with_retry(self, messages: List[Dict[str, str]], max_retries: int = 3) -> Any:
        for attempt in range(max_retries):
            try:
                async with self.semaphore:
                    return await self.client.chat.completions.create(
                        model=self.model,
                        temperature=0.1,
                        messages=messages,
                        max_tokens=4000
                    )
            except Exception as e:
                print(f"DeepSeek Error (Attempt {attempt+1}): {e}")
                if attempt == max_retries - 1: raise
                await asyncio.sleep(1 + attempt)

    # --- PHASE 1: Initial Item Classification ---
    async def classify_items(self, query: str, listings: List[Listing]) -> List[Dict[str, Any]]:
        batches = list(_chunk_list(listings, self.batch_size))
        print(f"Phase 1: Classifying {len(listings)} items in {len(batches)} batches...")
        
        # DEBUG: Print first few titles to ensure we are actually scraping parts
        if listings:
            print(f"Sample Titles being sent to AI:")
            for l in listings[:3]:
                print(f" - {l.title}")

        tasks = [self._process_item_batch(query, batch) for batch in batches]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        flat_results = []
        for res in results:
            if isinstance(res, list): 
                flat_results.extend(res)
            elif isinstance(res, Exception):
                print(f"Batch failed: {res}")
        
        return flat_results

    async def _process_item_batch(self, query: str, batch: List[Listing]) -> List[Dict[str, Any]]:
        # UPDATED PROMPT: Much more aggressive about keeping parts
        prompt = f"""
        You are an expert automotive parts specialist organizing an inventory database.
        
        CONTEXT:
        We scraped eBay 'Car & Truck Parts' for the query: '{query}'.
        The titles often start with the vehicle name (e.g. '2015 Honda Civic Headlight'). 
        THIS IS A PART, NOT THE VEHICLE.

        TASK:
        For each listing:
        1. EXTRACT the specific Part Name (e.g. "Headlight", "Alternator", "Lower Control Arm").
           - Ignore the year/make/model in the title.
           - If it is a "Service Manual", "Decal", or "Generic Tool", mark keep=false.
           - If it is a specific part for the car, mark keep=true.
        2. CATEGORY FORMAT:
           - Use Title Case.
           - Be specific but concise (e.g. "Front Bumper Cover", NOT "Bumper").
           - Do not include "Left/Right" in the category name yet (we group later).

        Listings:
        {json.dumps([{'id': x.item_id, 'title': x.title} for x in batch], indent=1)}

        Return JSON Array: [{{ "id": "...", "keep": true, "category": "extracted_part_name" }}]
        """
        try:
            response = await self._send_with_retry([{"role": "user", "content": prompt}])
            text = _extract_text_blocks(response)
            data = _extract_json_from_text(text)

            if not data:
                print(f"[DEBUG] JSON Parse Failed. content: {text[:100]}...")
                return []

            results = data.get('classified_listings', data) if isinstance(data, dict) else data
            if isinstance(results, list):
                return results
            return []
            
        except Exception as e:
            print(f"Batch processing error: {e}")
            return []

    # --- PHASE 2: Category Consolidation ---
    async def consolidate_categories_batch(self, categories: List[str]) -> Dict[str, str]:
        prompt = f"""
        You are a strict automotive taxonomy expert. 
        Normalize these raw part names into Master Categories.

        Input: {json.dumps(categories, indent=1)}

        RULES:
        1. Merge positions: "Left Headlight" -> "Headlight".
        2. Merge synonyms: "Head Lamp" -> "Headlight".
        3. KEEP distinct parts: "Tail Light" != "Headlight".
        
        Return JSON Object: {{ "Raw Name": "Master Name" }}
        """
        try:
            response = await self._send_with_retry([{"role": "user", "content": prompt}])
            text = _extract_text_blocks(response)
            mapping = _extract_json_from_text(text)
            return mapping if isinstance(mapping, dict) else {c: c for c in categories}
        except Exception:
            return {c: c for c in categories}
class ScrapingBeeAIScraper:
    def __init__(self, query: str, max_pages: int = 2, items_per_page: int = 100, batch_size: int = 50):
        self.query = query
        self.max_pages = max_pages
        self.items_per_page = items_per_page
        self.classifier = DeepSeekBatchCategorizer(batch_size=batch_size)
        self.session = None

    async def _get_session(self):
        if not self.session:
            self.session = aiohttp.ClientSession()
        return self.session

    async def _fetch_page(self, page: int, listing_type: str) -> List[Listing]:
        # simplified fetch logic for brevity - assuming ScrapingBee implementation similar to original
        url = f"https://www.ebay.com/sch/i.html?_nkw={quote(self.query)}&_sacat=6028&_from=R40&_osacat=6028&_ipg={self.items_per_page}&_pgn={page}&LH_ItemCondition=3000"
        if listing_type == "sold": url += "&LH_Sold=1&LH_Complete=1"
        
        print(f"Fetching {listing_type} page {page}...")
        session = await self._get_session()
        params = ScrapingBeeConfig.build_params(url)
        
        try:
            async with session.get(ScrapingBeeConfig.API_URL, params=params) as resp:
                if resp.status == 200:
                    html = await resp.text()
                    return self._parse_html(html, page, listing_type)
        except Exception as e:
            print(f"Error fetching: {e}")
        return []

    def _parse_html(self, html: str, page: int, listing_type: str) -> List[Listing]:
        soup = BeautifulSoup(html, "html.parser")
        items = []
        for card in soup.select(".s-card, li.s-item"):
            title_el = card.select_one(".s-item__title, .s-card__title")
            if not title_el: continue
            title = title_el.get_text(strip=True)
            if "Shop on eBay" in title: continue
            
            link = card.select_one("a.s-item__link, a.s-card__link")
            url = link['href'] if link else ""
            item_id = re.search(r"/itm/(\d+)", url)
            item_id = item_id.group(1) if item_id else str(abs(hash(title)))
            
            price_el = card.select_one(".s-item__price, .s-card__price")
            price = _safe_float(price_el.get_text() if price_el else "")
            
            img_el = card.select_one("img")
            img = img_el.get('src') if img_el else None

            items.append(Listing(
                item_id=item_id, title=title, price=price, url=url, 
                shipping=0, page=page, listing_type=listing_type, 
                image_url=img
            ))
        return items

    async def _recursive_category_normalization(self, listings: List[Listing]) -> None:
        """
        The Core Logic: Iteratively groups categories until stable.
        """
        # 1. Extract Initial Unique Categories (excluding None or Uncategorised)
        current_categories = list(set(l.category for l in listings if l.category and l.keep))
        iteration = 0
        max_iterations = 4 # Safety break
        
        while iteration < max_iterations:
            iteration += 1
            unique_count = len(current_categories)
            if unique_count <= 1: break # Nothing to group

            print(f"\n--- Iteration {iteration}: Normalizing {unique_count} unique categories ---")
            
            # Step A: Pre-cluster by keywords in Python to save tokens
            # We group strings that share words so the AI sees relevant contexts together
            clusters = self._heuristic_keyword_cluster(current_categories)
            print(f"Created {len(clusters)} keyword clusters for processing.")

            # Step B: Send clusters to DeepSeek
            # We create a mapping {OldName: NewMasterName}
            full_mapping = {}
            tasks = []
            
            for cluster in clusters:
                if len(cluster) == 1:
                    full_mapping[cluster[0]] = cluster[0] # No change needed
                else:
                    tasks.append(self.classifier.consolidate_categories_batch(cluster))
            
            if tasks:
                results = await asyncio.gather(*tasks)
                for res in results:
                    full_mapping.update(res)

            # Step C: Update Listings with New Names
            changes_made = 0
            new_category_set = set()
            
            for listing in listings:
                if not listing.keep or not listing.category: continue
                
                old_cat = listing.category
                # Normalize based on mapping
                if old_cat in full_mapping:
                    new_cat = full_mapping[old_cat]
                    # Simple clean up of title casing
                    new_cat = new_cat.title().strip() 
                    
                    if new_cat != old_cat:
                        listing.category = new_cat
                        changes_made += 1
                    
                    new_category_set.add(listing.category)

            current_categories = list(new_category_set)
            print(f"Iteration {iteration} complete. Updates applied: {changes_made}. New unique count: {len(current_categories)}")
            
            # Stop if convergence reached (very few changes)
            if changes_made == 0:
                print("Convergence reached. Categories are stable.")
                break

    def _heuristic_keyword_cluster(self, categories: List[str]) -> List[List[str]]:
        """
        Python-side helper. Groups strings like "Left Headlight" and "Right Headlight"
        into the same bucket before sending to AI. This ensures AI sees them together.
        """
        # 1. Break strings into significant words
        word_map = {}
        for cat in categories:
            # Tokenize and remove filler words
            words = set(re.findall(r"\w+", cat.lower()))
            words -= {'left', 'right', 'front', 'rear', 'driver', 'passenger', 'side', 'for', 'with', 'and', 'the', 'a'}
            # If no words left (e.g. category was just "Left"), use original
            if not words: words = {cat.lower()}
            
            # Use the longest word as the 'primary key' for crude clustering
            primary_key = max(words, key=len)
            if primary_key not in word_map: word_map[primary_key] = []
            word_map[primary_key].append(cat)
            
        # 2. Convert map to list of lists
        clusters = list(word_map.values())
        
        # 3. Handle giant clusters (if > 30 items, split them)
        final_clusters = []
        for cluster in clusters:
            if len(cluster) > 30:
                final_clusters.extend(list(_chunk_list(cluster, 30)))
            else:
                final_clusters.append(cluster)
                
        return final_clusters

    async def scrape(self):
        # 1. Collect Listings
        tasks = []
        for i in range(1, self.max_pages + 1):
            tasks.append(self._fetch_page(i, "active"))
            tasks.append(self._fetch_page(i, "sold"))
        
        results = await asyncio.gather(*tasks)
        all_listings = [item for sublist in results for item in sublist]
        print(f"Scraped {len(all_listings)} raw listings.")

        if not all_listings: return {}

        # 2. Phase 1: Initial Item Classification (Get Raw Categories)
        classified_data = await self.classifier.classify_items(self.query, all_listings)
        
        # Map back to listing objects
        data_map = {str(x['id']): x for x in classified_data if 'id' in x}
        kept_listings = []
        
        for listing in all_listings:
            if listing.item_id in data_map:
                info = data_map[listing.item_id]
                listing.keep = info.get('keep', False)
                listing.category = info.get('category', 'Uncategorised')
                if listing.keep: kept_listings.append(listing)
        
        print(f"Kept {len(kept_listings)} relevant listings after Phase 1.")

        # 3. Phase 2: The Recursive Loop (Normalize Categories)
        await self._recursive_category_normalization(kept_listings)

        # 4. Final Verification / Cleanup
        # If a group has < 3 items, maybe mark as "Other"? (Optional, kept simple for now)
        
        # 5. Build Final Report
        return self._build_report(kept_listings)

    def _build_report(self, listings: List[Listing]):
        # Group by final normalized category
        grouped = {}
        for l in listings:
            if not l.category: continue
            if l.category not in grouped: grouped[l.category] = []
            grouped[l.category].append(l)
            
        summary = []
        for cat, items in grouped.items():
            prices = [x.price for x in items if x.price]
            avg = round(statistics.mean(prices), 2) if prices else 0
            summary.append({
                "category": cat,
                "count": len(items),
                "avg_price": avg,
                "samples": [x.title for x in items[:3]]
            })
            
        summary.sort(key=lambda x: x['count'], reverse=True)
        
        return {
            "query": self.query,
            "total_listings": len(listings),
            "category_count": len(summary),
            "categories": summary
        }

    async def close(self):
        if self.session: await self.session.close()

async def main():
    import argparse, pprint
    
    parser = argparse.ArgumentParser()
    parser.add_argument("query", help="eBay search query")
    args = parser.parse_args()

    scraper = ScrapingBeeAIScraper(args.query, max_pages=2, items_per_page=240, batch_size=20)
    try:
        report = await scraper.scrape()
        print("\n--- FINAL REPORT ---")
        pprint.pprint(report['categories'])
    finally:
        await scraper.close()

if __name__ == "__main__":
    asyncio.run(main())
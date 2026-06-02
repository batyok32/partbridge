"""Simplified ScrapingBee scraper with DeepSeek categorisation.

This module fetches active and sold listings for a search query within
Ebay category 6030 (Car & Truck Parts & Accessories), aggregates the
titles and prices, and sends a representative sample to DeepSeek for
categorisation and insight generation.
"""

from __future__ import annotations

import os
import platform

# macOS compatibility: Set environment variables BEFORE importing PyTorch/transformers
# This prevents segmentation faults and threading issues
if platform.system() == 'Darwin':
    os.environ.setdefault('TOKENIZERS_PARALLELISM', 'false')
    os.environ.setdefault('OMP_NUM_THREADS', '1')
    os.environ.setdefault('MKL_NUM_THREADS', '1')

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
from typing import Any, Dict, Iterable, List, Optional, Union, Tuple
from difflib import SequenceMatcher
import numpy as np
import pickle
import hashlib

import openai  # type: ignore[import]
import httpx
import aiohttp
from bs4 import BeautifulSoup
from django.conf import settings  # type: ignore[import]
from urllib.parse import quote

try:
    import faiss
    FAISS_AVAILABLE = True
except ImportError:
    FAISS_AVAILABLE = False
    print("Warning: FAISS not available. Install with: pip install faiss-cpu")


logger = logging.getLogger(__name__)


class ScrapingBeeConfig:
    """Configuration helpers for the ScrapingBee API."""

    API_KEY = getattr(settings, "SCRAPING_BEE_API_KEY", "")
    API_URL = "https://app.scrapingbee.com/api/v1"
    DEFAULT_WAIT_MS = 8000
    REQUEST_DELAY_SECONDS = 2
    COUNTRY_CODE = "us"
    COOKIES = "lc=en-US;ebay=%5Esbf%3D%2340000000000100000000007089ed9fff%5E"

    @classmethod
    def build_params(
        cls,
        url: str,
        *,
        render_js: Optional[bool] = None,
        wait_for: Optional[str] = None,
        js_scenario: Optional[str] = None,
        wait_ms: Optional[int] = None,
    ) -> Dict[str, str]:
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
        if js_scenario:
            params["js_scenario"] = js_scenario
        return params


def _safe_float(value: Optional[str]) -> Optional[float]:
    if not value:
        return None
    digits = "".join(ch for ch in value if ch.isdigit() or ch == ".")
    if not digits:
        return None
    try:
        return float(digits)
    except ValueError:
                return None


def _extract_text_blocks(response: Any) -> str:
    """Extract text from OpenAI-compatible response."""
    if hasattr(response, 'choices') and len(response.choices) > 0:
        return response.choices[0].message.content.strip()
    elif isinstance(response, str):
        return response.strip()
    elif isinstance(response, dict):
        if 'choices' in response and len(response['choices']) > 0:
            return response['choices'][0]['message']['content'].strip()
        elif 'content' in response:
            return str(response['content']).strip()
    return str(response).strip()


def _extract_json_from_text(text: str) -> Optional[Union[dict, list]]:
    """Extract JSON from text, handling arrays, multiple objects, and extra data"""
    if not text:
        return None
    text = text.strip()

    # Remove markdown code fences
    if text.startswith("```"):
        lines = text.splitlines()
        if lines:
            lines = lines[1:]
        while lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    else:
        text = text.replace("```json", "").replace("```", "")

    # Try to extract fenced JSON first
    fenced = re.search(r"```(?:json)?\s*(\[.*?\]|\{.*?\})\s*```", text, re.DOTALL)
    if fenced:
        text = fenced.group(1)

    # Try to find array first (for batch responses)
    array_start = text.find("[")
    if array_start != -1:
        # Find matching closing bracket
        bracket_count = 0
        in_string = False
        escape_next = False
        array_end = -1
        
        for i in range(array_start, len(text)):
            char = text[i]
            if escape_next:
                escape_next = False
                continue
            if char == '\\':
                escape_next = True
                continue
            if char == '"' and not escape_next:
                in_string = not in_string
            if not in_string:
                if char == '[':
                    bracket_count += 1
                elif char == ']':
                    bracket_count -= 1
                    if bracket_count == 0:
                        array_end = i
                        break
        
        if array_end > array_start:
            snippet = text[array_start : array_end + 1]
            try:
                return json.loads(snippet)
            except json.JSONDecodeError as exc:
                # If "Extra data" error, we already have the right bounds, so try repair
                if "Extra data" not in str(exc):
                    # Try to repair common JSON errors in array
                    try:
                        repaired = re.sub(r',(\s*\])', r'\1', snippet)
                        repaired = re.sub(r'(\})\s*"', r'\1,"', repaired)
                        return json.loads(repaired)
                    except json.JSONDecodeError:
                        pass

    # Try to find object
    obj_start = text.find("{")
    if obj_start != -1:
        # Find matching closing brace (not just the last one)
        bracket_count = 0
        in_string = False
        escape_next = False
        obj_end = -1
        
        for i in range(obj_start, len(text)):
            char = text[i]
            if escape_next:
                escape_next = False
                continue
            if char == '\\':
                escape_next = True
                continue
            if char == '"' and not escape_next:
                in_string = not in_string
            if not in_string:
                if char == '{':
                    bracket_count += 1
                elif char == '}':
                    bracket_count -= 1
                    if bracket_count == 0:
                        obj_end = i
                        break
        
        if obj_end > obj_start:
            snippet = text[obj_start : obj_end + 1]
            
            # Try parsing first
            try:
                return json.loads(snippet)
            except json.JSONDecodeError as exc:
                print(f"JSON decode error: {exc}")
                # Try to repair common JSON errors
                try:
                    # Fix missing commas before closing braces
                    repaired = re.sub(r'(\})\s*"', r'\1,"', snippet)
                    repaired = re.sub(r'(\])\s*"', r'\1,"', repaired)
                    # Remove trailing commas before closing braces
                    repaired = re.sub(r',(\s*[}\]])', r'\1', repaired)
                    return json.loads(repaired)
                except (json.JSONDecodeError, Exception) as repair_exc:
                    print(f"JSON repair failed: {repair_exc}")
                    # Last resort: try to extract just the groups array
                    try:
                        groups_match = re.search(r'"groups"\s*:\s*\[(.*?)\]', snippet, re.DOTALL)
                        if groups_match:
                            groups_text = "[" + groups_match.group(1) + "]"
                            # Try to fix common issues in groups array
                            groups_text = re.sub(r'(\})\s*"', r'\1,"', groups_text)
                            groups_text = re.sub(r',(\s*\])', r'\1', groups_text)
                            groups = json.loads(groups_text)
                            return {"groups": groups}
                    except Exception as extract_exc:
                        print(f"Groups extraction failed: {extract_exc}")
    
    # No valid JSON found
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
            "page": self.page,
            "listing_type": self.listing_type,
            "keep": self.keep,
            "category": self.category,
            "classification_reason": self.classification_reason,
            "seller": self.seller,
            "seller_feedback": self.seller_feedback,
            "image_url": self.image_url,
        }


def _chunk_list(items: List[Listing], size: int) -> Iterable[List[Listing]]:
    for index in range(0, len(items), size):
        yield items[index : index + size]


def _chunk_any(items: List[Any], size: int) -> Iterable[List[Any]]:
    """Generic chunking function for any list type."""
    for index in range(0, len(items), size):
        yield items[index : index + size]


class EmbeddingCategoryMatcher:
    """Embedding-based category matcher using FAISS and OpenAI embeddings."""

    def __init__(
        self,
        *,
        parts_file_path: Optional[str] = None,
        embedding_model: str = "text-embedding-3-small",
        similarity_threshold: float = 0.90,
        deepseek_api_key: Optional[str] = None,
        deepseek_model: Optional[str] = None,
        openai_api_key: Optional[str] = None,
        title_cleaning_batch_size: int = 25,
        max_retries: int = 3,
        retry_initial_delay: float = 0.5,
    ) -> None:
        """Initialize the embedding-based category matcher.
        
        Args:
            parts_file_path: Path to parts.txt file. Defaults to backend/analytics/services/parts.txt
            embedding_model: OpenAI embedding model name (default: text-embedding-3-small, 1536 dimensions)
            similarity_threshold: Minimum similarity (0-1) for auto-assignment
            deepseek_api_key: DeepSeek API key for LLM calls
            deepseek_model: DeepSeek model name
            openai_api_key: OpenAI API key for embeddings (defaults to OPENAI_API_KEY from settings)
            title_cleaning_batch_size: Batch size for title cleaning requests
            max_retries: Maximum retries for API calls
            retry_initial_delay: Initial delay for retries
        """
        if not FAISS_AVAILABLE:
            raise RuntimeError("FAISS is required but not available. Install with: pip install faiss-cpu")
        
        # Initialize DeepSeek client for LLM calls
        deepseek_api_key = deepseek_api_key or getattr(settings, "DEEPSEEK_API_KEY", None)
        if not deepseek_api_key:
            raise RuntimeError("DeepSeek API key must be configured to run AI categorisation.")
        
        self.deepseek_client = openai.AsyncOpenAI(
            api_key=deepseek_api_key,
            base_url="https://api.deepseek.com/v1"
        )
        self.deepseek_model = deepseek_model or getattr(settings, "DEEPSEEK_MODEL", "deepseek-chat")
        
        # Initialize OpenAI client for embeddings
        openai_api_key = openai_api_key or getattr(settings, "OPENAI_API_KEY", None)
        if not openai_api_key:
            raise RuntimeError("OpenAI API key must be configured for embeddings. Set OPENAI_API_KEY in settings.")
        
        self.openai_client = openai.AsyncOpenAI(api_key=openai_api_key)
        self.embedding_model = embedding_model
        
        # Embedding dimensions for OpenAI models
        embedding_dims = {
            "text-embedding-3-small": 1536,
            "text-embedding-3-large": 3072,
            "text-embedding-ada-002": 1536,
        }
        self.embedding_dim = embedding_dims.get(embedding_model, 1536)
        
        # Load categories from parts.txt
        if parts_file_path is None:
            # Default to backend/analytics/services/parts.txt
            current_dir = os.path.dirname(os.path.abspath(__file__))
            parts_file_path = os.path.join(current_dir, "parts.txt")
        
        self.categories = self._load_categories(parts_file_path)
        if not self.categories:
            raise RuntimeError(f"No categories loaded from {parts_file_path}. File may be empty or not found.")
        
        print(f"Loaded {len(self.categories)} categories from {parts_file_path}")
        
        # Cache file paths for pre-embedded categories
        current_dir = os.path.dirname(os.path.abspath(__file__))
        cache_dir = os.path.join(current_dir, ".embeddings_cache")
        os.makedirs(cache_dir, exist_ok=True)
        
        # Create cache key based on categories and model name
        categories_hash = hashlib.md5(
            ("\n".join(sorted(self.categories)) + embedding_model).encode()
        ).hexdigest()[:16]
        
        self.embeddings_cache_file = os.path.join(cache_dir, f"category_embeddings_{categories_hash}.npz")
        self.categories_cache_file = os.path.join(cache_dir, f"category_names_{categories_hash}.pkl")
        
        # Initialize FAISS index (will be built lazily)
        self.index = None
        self.category_names = []  # Parallel array to index for reverse lookup
        self._index_built = False
        
        self.similarity_threshold = similarity_threshold
        self.title_cleaning_batch_size = title_cleaning_batch_size
        self.max_retries = max_retries
        self.retry_initial_delay = retry_initial_delay
        self.retry_max_delay = 6.0
        
        print(f"EmbeddingCategoryMatcher initialized: {len(self.categories)} categories (model will load on first use)")
    
    def _load_categories(self, file_path: str) -> List[str]:
        """Load categories from parts.txt file."""
        if not os.path.exists(file_path):
            print(f"Warning: Parts file not found at {file_path}")
            return []
        
        categories = []
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and line != "Select Part":  # Skip empty lines and header
                    categories.append(line)
        
        return categories
    
    def _load_cached_embeddings(self) -> Optional[Tuple[np.ndarray, int]]:
        """Load pre-computed embeddings from cache file if available.
        
        Returns:
            Tuple of (embeddings, embedding_dim) if cache exists and is valid, None otherwise
        """
        if not os.path.exists(self.embeddings_cache_file) or not os.path.exists(self.categories_cache_file):
            return None
        
        try:
            # Load embeddings
            cache_data = np.load(self.embeddings_cache_file)
            embeddings = cache_data['embeddings']
            embedding_dim = int(cache_data['embedding_dim'])
            
            # Load category names
            with open(self.categories_cache_file, 'rb') as f:
                cached_category_names = pickle.load(f)
            
            # Verify categories match
            if cached_category_names != self.categories:
                print("Cached categories don't match current categories, rebuilding...")
                return None
            
            print(f"Loaded {len(embeddings)} pre-computed embeddings from cache")
            return embeddings, embedding_dim
        except Exception as exc:
            print(f"Error loading cached embeddings: {exc}, rebuilding...")
            return None
    
    def _save_embeddings_cache(self, embeddings: np.ndarray, embedding_dim: int) -> None:
        """Save computed embeddings to cache file for future use."""
        try:
            # Save embeddings
            np.savez_compressed(
                self.embeddings_cache_file,
                embeddings=embeddings,
                embedding_dim=embedding_dim
            )
            
            # Save category names
            with open(self.categories_cache_file, 'wb') as f:
                pickle.dump(self.categories, f)
            
            print(f"Cached {len(embeddings)} embeddings to {self.embeddings_cache_file}")
        except Exception as exc:
            print(f"Warning: Failed to cache embeddings: {exc}")
    
    async def _create_embeddings(self, texts: List[str]) -> np.ndarray:
        """Create embeddings using OpenAI API."""
        # OpenAI API supports up to 2048 texts per request, but we'll use smaller batches
        batch_size = 100
        all_embeddings = []
        
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            try:
                response = await self.openai_client.embeddings.create(
                    model=self.embedding_model,
                    input=batch
                )
                batch_embeddings = [item.embedding for item in response.data]
                all_embeddings.extend(batch_embeddings)
            except Exception as exc:
                print(f"Error creating embeddings for batch {i//batch_size + 1}: {exc}")
                raise
        
        return np.array(all_embeddings, dtype=np.float32)
    
    async def _ensure_model_loaded(self) -> None:
        """Lazily build index if not already done."""
        if self._index_built:
            return
        
        # Build index if not built
        if not self._index_built:
            # Try to load from cache first
            cache_result = self._load_cached_embeddings()
            
            if cache_result is not None:
                # Use cached embeddings
                category_embeddings, cached_dim = cache_result
                if cached_dim != self.embedding_dim:
                    print(f"Warning: Cached embeddings dimension ({cached_dim}) doesn't match model ({self.embedding_dim}). Recomputing...")
                    cache_result = None
            
            if cache_result is None:
                # Need to compute embeddings using OpenAI API
                print(f"Computing embeddings for {len(self.categories)} categories using OpenAI {self.embedding_model}...")
                category_embeddings = await self._create_embeddings(self.categories)
                
                # Save to cache for next time
                self._save_embeddings_cache(category_embeddings, self.embedding_dim)
                print(f"Saved embeddings to cache: {self.embeddings_cache_file}")
            else:
                category_embeddings, _ = cache_result
                print(f"Loaded {len(category_embeddings)} pre-computed embeddings from cache ({self.embedding_dim}D)")
            
            # Build FAISS index
            print(f"Building FAISS index for {len(self.categories)} categories...")
            self.index = faiss.IndexFlatL2(self.embedding_dim)
            
            # Normalize embeddings for cosine similarity (L2 normalization)
            faiss.normalize_L2(category_embeddings)
            
            # Add to FAISS index
            self.index.add(category_embeddings.astype('float32'))
            self.category_names = self.categories.copy()
            self._index_built = True
            
            print(f"FAISS index built: {self.index.ntotal} vectors, {self.embedding_dim}D")
    
    async def _clean_title_with_deepseek(self, title: str) -> str:
        """Clean and normalize listing title using DeepSeek LLM."""
        prompt = f"""Extract and normalize the automotive part category name from this eBay listing title. 
Return ONLY the clean category name, nothing else. Remove vehicle-specific details, conditions, and extra words.
Example: "OEM Driver Side Left Fender for 2015 BMW 328i" → "Fender"
Example: "Used Alternator 2010 Toyota Camry" → "Alternator"

Title: {title}"""
        
        try:
            response = await self._send_with_retry({
                "model": self.deepseek_model,
                "temperature": 0.2,
                "max_tokens": 100,
                "messages": [{"role": "user", "content": prompt}],
            })
            
            text = _extract_text_blocks(response)
            # Clean up the response - remove quotes, extra whitespace
            cleaned = text.strip().strip('"').strip("'").strip()
            return cleaned
        except Exception as exc:
            print(f"Error cleaning title '{title}': {exc}")
            return title  # Fallback to original title
    
    async def _clean_titles_batch(self, titles: List[str]) -> List[str]:
        """Clean multiple titles in parallel."""
        tasks = [self._clean_title_with_deepseek(title) for title in titles]
        return await asyncio.gather(*tasks, return_exceptions=True)
    
    async def _get_similar_categories(self, embedding: np.ndarray, top_k: int = 5) -> List[Dict[str, Any]]:
        """Find top-k similar categories using FAISS search.
        
        Args:
            embedding: Query embedding vector (normalized)
            top_k: Number of top matches to return
            
        Returns:
            List of dicts with 'category', 'similarity' (cosine similarity, 0-1)
        """
        # Ensure index is built
        await self._ensure_model_loaded()
        
        # Ensure embedding is normalized and right shape
        embedding = embedding.reshape(1, -1).astype('float32')
        faiss.normalize_L2(embedding)
        
        # Search in FAISS index
        distances, indices = self.index.search(embedding, min(top_k, len(self.category_names)))
        
        results = []
        for i, (distance, idx) in enumerate(zip(distances[0], indices[0])):
            if idx < len(self.category_names):
                # Convert L2 distance to cosine similarity
                # For normalized vectors: cosine_sim = 1 - (L2_distance^2 / 2)
                similarity = 1.0 - (distance ** 2 / 2.0)
                similarity = max(0.0, min(1.0, similarity))  # Clamp to [0, 1]
                
                results.append({
                    "category": self.category_names[idx],
                    "similarity": similarity,
                    "rank": i + 1
                })
        
        return results
    
    async def _llm_judge_category(self, original_title: str, candidate_categories: List[str]) -> str:
        """Use DeepSeek LLM to choose best category from candidates."""
        categories_str = "\n".join([f"- {cat}" for cat in candidate_categories])
        prompt = f"""I have an item: '{original_title}'. 
Which of these specific categories fits best? 
Options:
{categories_str}

Return strictly the category name only, nothing else."""
        
        try:
            response = await self._send_with_retry({
                "model": self.deepseek_model,
                "temperature": 0.2,
                "max_tokens": 100,
                "messages": [{"role": "user", "content": prompt}],
            })
            
            text = _extract_text_blocks(response)
            print(f"LLM judge response for '{original_title}': {text}")
            # Clean up and try to match to one of the candidates
            cleaned = text.strip().strip('"').strip("'").strip()
            print(f"LLM judge cleaned category: '{cleaned}'")
            # Try to find exact match in candidates
            for candidate in candidate_categories:
                if candidate.lower() == cleaned.lower() or cleaned.lower() in candidate.lower():
                    return candidate
            print("No exact match found from LLM judge")
            # If no exact match, return first candidate as fallback
            return candidate_categories[0] if candidate_categories else "Uncategorised"
        except Exception as exc:
            print(f"Error in LLM judge for '{original_title}': {exc}")
            return candidate_categories[0] if candidate_categories else "Uncategorised"
    
    async def _classify_single_listing(self, listing: Listing, cleaned_category_name: str, embedding: np.ndarray) -> Dict[str, Any]:
        """Classify a single listing using pre-computed cleaned name and embedding.
        
        Args:
            listing: The listing to classify
            cleaned_category_name: Pre-cleaned category name from DeepSeek
            embedding: Pre-computed embedding for the cleaned category name
        """
        # Ensure index is built (lazy loading for Celery compatibility)
        await self._ensure_model_loaded()
        
        original_title = listing.title
        
        # Semantic search in FAISS using pre-computed embedding
        similar_categories = await self._get_similar_categories(embedding, top_k=5)
        print(f"Similar categories for listing {listing.item_id}: {similar_categories}")
        
        if not similar_categories:
            # No matches found - mark as uncategorised
            print("No similar categories found")
            return {
                "id": listing.item_id,
                "keep": True,
                "category": "Uncategorised",
                "reason": "No matching categories found in database",
                "normalized_title": original_title,
                "price": f"${listing.price:.2f}" if listing.price else "unknown",
                "listing_type": listing.listing_type,
            }
        
        best_match = similar_categories[0]
        best_similarity = best_match["similarity"]
        
        # Step 4: Auto-assignment decision
        # Find all matches with similarity >= threshold
        high_confidence_matches = [
            cat for cat in similar_categories 
            if cat["similarity"] >= self.similarity_threshold
        ]
        
        if len(high_confidence_matches) == 1:
            # Only one high-confidence match - auto-assign
            return {
                "id": listing.item_id,
                "keep": True,
                "category": high_confidence_matches[0]["category"],
                "reason": f"Auto-assigned (similarity: {high_confidence_matches[0]['similarity']*100:.1f}%)",
                "normalized_title": original_title,
                "price": f"${listing.price:.2f}" if listing.price else "unknown",
                "listing_type": listing.listing_type,
            }
        elif len(high_confidence_matches) > 1:
            # Multiple high-confidence matches - send to LLM judge to pick the best one
            candidate_categories = [cat["category"] for cat in high_confidence_matches]
            chosen_category = await self._llm_judge_category(original_title, candidate_categories)
            
            return {
                "id": listing.item_id,
                "keep": True,
                "category": chosen_category,
                "reason": f"LLM selected from {len(high_confidence_matches)} high-confidence matches (all >= {self.similarity_threshold*100:.0f}%)",
                "normalized_title": original_title,
                "price": f"${listing.price:.2f}" if listing.price else "unknown",
                "listing_type": listing.listing_type,
            }
        
        # Step 5: LLM judge for ambiguous cases (no high-confidence matches)
        candidate_categories = [cat["category"] for cat in similar_categories]
        chosen_category = await self._llm_judge_category(original_title, candidate_categories)
        
        return {
            "id": listing.item_id,
            "keep": True,
            "category": chosen_category,
            "reason": f"LLM selected from {len(candidate_categories)} candidates (best similarity: {best_similarity*100:.1f}%)",
            "normalized_title": original_title,
            "price": f"${listing.price:.2f}" if listing.price else "unknown",
            "listing_type": listing.listing_type,
        }
    
    async def classify(self, query: str, listings: List[Listing]) -> Dict[str, object]:
        """Classify listings using embedding-based matching.
        
        Args:
            query: Search query (unused, kept for compatibility)
            listings: List of Listing objects to classify
            
        Returns:
            Dict with 'classified_listings' and 'raw_batches' keys
        """
        print(f"Classifying {len(listings)} listings using embedding-based matching")
        
        # Ensure index is built first
        await self._ensure_model_loaded()
        
        all_results = []
        raw_batches = []
        
        # Step 1: Clean all titles with DeepSeek (in batches) - PARALLEL PROCESSING WITH LIMIT
        print(f"Step 1: Cleaning {len(listings)} titles with DeepSeek (max 20 batches concurrent)...")
        title_batches = list(_chunk_list(listings, self.title_cleaning_batch_size))
        
        # Use semaphore to limit concurrent batches to 20
        cleaning_semaphore = asyncio.Semaphore(20)
        
        # Process cleaning batches with concurrency limit
        async def clean_single_batch(batch_idx: int, batch: List[Listing]) -> List[str]:
            """Clean a single batch of titles"""
            async with cleaning_semaphore:
                print(f"Cleaning batch {batch_idx + 1}/{len(title_batches)} ({len(batch)} titles)")
                batch_titles = [listing.title for listing in batch]
                cleaned_batch = await self._clean_titles_batch(batch_titles)
                # Handle exceptions in cleaned batch - use original title as fallback
                cleaned_processed = []
                for j, cleaned in enumerate(cleaned_batch):
                    if isinstance(cleaned, Exception):
                        print(f"Warning: Title cleaning failed for listing in batch {batch_idx + 1}, using original title: {cleaned}")
                        cleaned_processed.append(batch_titles[j])  # Use original title
                    else:
                        cleaned_processed.append(cleaned)
                return cleaned_processed
        
        # Process all batches with concurrency limit
        cleaning_tasks = [
            clean_single_batch(batch_idx, batch)
            for batch_idx, batch in enumerate(title_batches)
        ]
        cleaned_batches = await asyncio.gather(*cleaning_tasks, return_exceptions=True)
        
        # Flatten results in order
        all_cleaned_names = []
        for batch_idx, cleaned_batch_result in enumerate(cleaned_batches):
            if isinstance(cleaned_batch_result, Exception):
                print(f"Error cleaning batch {batch_idx + 1}: {cleaned_batch_result}")
                # Use original titles as fallback for this batch
                batch = title_batches[batch_idx]
                all_cleaned_names.extend([listing.title for listing in batch])
            else:
                all_cleaned_names.extend(cleaned_batch_result)
        print("All cleaned names", all_cleaned_names)
        # Step 2: Create embeddings for all cleaned category names (in batches)
        print(f"Step 2: Creating embeddings for {len(all_cleaned_names)} cleaned category names...")
        embedding_batch_size = 100  # OpenAI API batch size
        all_embeddings = []
        
        for i in range(0, len(all_cleaned_names), embedding_batch_size):
            batch_names = all_cleaned_names[i:i + embedding_batch_size]
            print(f"Creating embeddings for batch {i//embedding_batch_size + 1} ({len(batch_names)} items)")
            try:
                batch_embeddings = await self._create_embeddings(batch_names)
                all_embeddings.extend(batch_embeddings)
            except Exception as exc:
                print(f"Error creating embeddings for batch: {exc}")
                # Create zero embeddings as fallback (will result in uncategorised)
                fallback_embeddings = np.zeros((len(batch_names), self.embedding_dim), dtype=np.float32)
                all_embeddings.extend(fallback_embeddings)
        
        # Step 3: Classify each listing using pre-computed cleaned names and embeddings - PARALLEL PROCESSING WITH LIMIT
        print(f"Step 3: Classifying {len(listings)} listings using FAISS search (max 20 batches concurrent)...")
        title_batches = list(_chunk_list(listings, self.title_cleaning_batch_size))
        
        # Use semaphore to limit concurrent batches to 20
        classification_semaphore = asyncio.Semaphore(20)
        
        # Process classification batches with concurrency limit
        async def classify_single_batch(batch_idx: int, batch: List[Listing]) -> Dict:
            """Classify a single batch of listings"""
            async with classification_semaphore:
                print(f"Classifying batch {batch_idx + 1}/{len(title_batches)} ({len(batch)} listings)")
                
                # Get corresponding cleaned names and embeddings for this batch
                batch_start = batch_idx * self.title_cleaning_batch_size
                batch_cleaned_names = all_cleaned_names[batch_start:batch_start + len(batch)]
                batch_embeddings = all_embeddings[batch_start:batch_start + len(batch)]
                
                # Classify all listings in this batch using pre-computed data
                batch_tasks = [
                    self._classify_single_listing(listing, cleaned_name, embedding)
                    for listing, cleaned_name, embedding in zip(batch, batch_cleaned_names, batch_embeddings)
                ]
                batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)
                
                # Process results for this batch
                batch_results_processed = []
                for i, result in enumerate(batch_results):
                    if isinstance(result, Exception):
                        # Error occurred - mark as uncategorised
                        print(f"Error classifying listing {batch[i].item_id} in batch {batch_idx + 1}: {result}")
                        batch_results_processed.append({
                            "id": batch[i].item_id,
                            "keep": True,
                            "category": "Uncategorised",
                            "reason": f"Classification error: {str(result)[:100]}",
                            "normalized_title": batch[i].title,
                            "price": f"${batch[i].price:.2f}" if batch[i].price else "unknown",
                            "listing_type": batch[i].listing_type,
                        })
                    else:
                        batch_results_processed.append(result)
                
                return {
                    "batch_index": batch_idx,
                    "ids": [listing.item_id for listing in batch],
                    "count": len(batch),
                    "results": batch_results_processed
                }
        
        # Process all classification batches with concurrency limit
        classification_tasks = [
            classify_single_batch(batch_idx, batch)
            for batch_idx, batch in enumerate(title_batches)
        ]
        classification_batches = await asyncio.gather(*classification_tasks, return_exceptions=True)
        
        # Process results from all batches
        for batch_result in classification_batches:
            if isinstance(batch_result, Exception):
                print(f"Error processing classification batch: {batch_result}")
                continue
            
            all_results.extend(batch_result.get("results", []))
            raw_batches.append({
                "batch_index": batch_result["batch_index"],
                "ids": batch_result["ids"],
                "count": batch_result["count"],
            })
        
        # Count auto-assigned vs LLM-judged
        auto_assigned = sum(1 for r in all_results if "Auto-assigned" in r.get("reason", ""))
        llm_judged = len(all_results) - auto_assigned
        
        print(f"Classification complete: {auto_assigned} auto-assigned, {llm_judged} LLM-judged")
        
        return {
            "classified_listings": all_results,
            "raw_batches": raw_batches,
        }
    
    async def _send_with_retry(self, payload: Dict[str, object]):
        """Send request to DeepSeek with retry logic."""
        attempt = 0
        delay = self.retry_initial_delay
        while True:
            attempt += 1
            try:
                response = await self.deepseek_client.chat.completions.create(**payload)  # type: ignore[arg-type]
                return response
            except Exception as exc:
                if not self._should_retry(exc, attempt):
                    raise
                sleep_for = min(delay, self.retry_max_delay)
                jitter = random.uniform(0, sleep_for * 0.25)
                total_sleep = sleep_for + jitter
                status_description = self._describe_http_error(exc)
                print(
                    f"DeepSeek request attempt {attempt} failed ({status_description}); "
                    f"retrying in {total_sleep:.2f}s"
                )
                await asyncio.sleep(total_sleep)
                delay = min(delay * 2, self.retry_max_delay)
    
    def _should_retry(self, exc: Exception, attempt: int) -> bool:
        """Determine if request should be retried."""
        if attempt >= self.max_retries:
            return False
        
        response = getattr(exc, "response", None)
        status_code = getattr(response, "status_code", None)
        
        headers: Dict[str, str] = {}
        if response is not None:
            try:
                headers = {str(k).lower(): str(v) for k, v in response.headers.items()}
            except Exception:
                headers = {}
        
        if headers.get("x-should-retry") == "true":
            return True
        
        server_error_statuses = {500, 502, 503, 504, 522, 524, 529}
        if status_code in server_error_statuses:
            return True
        
        retryable_statuses = {408, 409, 425, 429}
        return status_code in retryable_statuses
    
    @staticmethod
    def _describe_http_error(exc: Exception) -> str:
        """Describe HTTP error for logging."""
        response = getattr(exc, "response", None)
        if isinstance(exc, httpx.HTTPStatusError):
            return f"HTTP {exc.response.status_code}"
        if response is not None and hasattr(response, "status_code"):
            return f"HTTP {response.status_code}"
        return exc.__class__.__name__


class DeepSeekBatchCategorizer:
    """Categorise every listing via DeepSeek, removing irrelevant items."""

    def __init__(
        self,
        *,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        batch_size: int = 60,
        temperature: float = 0.2,
        max_tokens: int = 8000,  # Increased to prevent truncation of large batches
        max_retries: int = 3,
        retry_initial_delay: float = 0.5,
        max_concurrent_batches: int = 20,
    ) -> None:
        api_key = api_key or getattr(settings, "DEEPSEEK_API_KEY", None)
        if not api_key:
            raise RuntimeError("DeepSeek API key must be configured to run AI categorisation.")

        self.client = openai.AsyncOpenAI(
            api_key=api_key,
            base_url="https://api.deepseek.com/v1"
        )
        self.model = model or getattr(settings, "DEEPSEEK_MODEL", "deepseek-chat")
        self.batch_size = batch_size
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.max_retries = max_retries
        self.retry_initial_delay = retry_initial_delay
        self.retry_max_delay = 6.0
        self.max_concurrent_batches = max_concurrent_batches
    
    def _extract_partial_classified_listings(self, text: str) -> List[Dict[str, Any]]:
        """Extract partial classified_listings from incomplete JSON response"""
        if not text:
            return []
        
        results = []
        
        # Try to find the classified_listings array start
        array_start = text.find('"classified_listings"')
        if array_start == -1:
            return []
        
        # Find the opening bracket after "classified_listings"
        bracket_start = text.find('[', array_start)
        if bracket_start == -1:
            return []
        
        # Extract everything from the opening bracket onwards
        array_text = text[bracket_start:]
        
        # Use regex to find complete JSON objects (simpler than manual parsing)
        # Pattern: { ... } where braces are balanced
        obj_pattern = r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'
        matches = re.finditer(obj_pattern, array_text)
        
        for match in matches:
            obj_text = match.group(0)
            try:
                obj = json.loads(obj_text)
                if isinstance(obj, dict) and "id" in obj:
                    results.append(obj)
            except json.JSONDecodeError:
                # Try a more sophisticated approach: find balanced braces
                brace_count = 0
                obj_start = match.start()
                obj_end = -1
                in_string = False
                escape_next = False
                
                for i in range(obj_start, len(array_text)):
                    char = array_text[i]
                    if escape_next:
                        escape_next = False
                        continue
                    if char == '\\':
                        escape_next = True
                        continue
                    if char == '"' and not escape_next:
                        in_string = not in_string
                    if not in_string:
                        if char == '{':
                            brace_count += 1
                        elif char == '}':
                            brace_count -= 1
                            if brace_count == 0:
                                obj_end = i + 1
                                break
                
                if obj_end > obj_start:
                    try:
                        obj_text = array_text[obj_start:obj_end]
                        obj = json.loads(obj_text)
                        if isinstance(obj, dict) and "id" in obj:
                            results.append(obj)
                    except json.JSONDecodeError:
                        pass
        
        return results

    def _build_prompt(self, query: str, listings: List[Listing]) -> str:
        lines = [
            "You are cleaning and categorising eBay listings for an automotive parts buyer.",
            "The user searched for: '" + query + "'.",
            "For each listing decide if it is genuinely relevant, then assign a specific part category (your own wording).",
            "Rules:",
            "1. Set keep=false for unrelated, duplicate, accessory-only, or generic tool listings.",
            "2. Always provide a concise reason for the decision.",
            "3. Categories should be specific (e.g. 'Front bumper cover', 'HV battery pack'), not vague.",
            "4. Output JSON with key 'classified_listings' containing an array of objects",
            "   where each object has: id, keep (true/false), category, reason, normalized_title, price, listing_type.",
            "5. Return JSON only, no markdown or extra commentary.",
            "Listings:",
        ]

        for listing in listings:
            price_text = f"${listing.price:.2f}" if listing.price is not None else "unknown"
            lines.append(
                f"- id={listing.item_id} | type={listing.listing_type} | price={price_text} | title={listing.title}"
            )

        return "\n".join(lines)

    async def _process_batch(self, query: str, batch: List[Listing], batch_index: int) -> Dict[str, object]:
        """Process a single batch of listings - used for parallel processing"""
        try:
            prompt = self._build_prompt(query, batch)
            response = await self._send_with_retry(
                {
                    "model": self.model,
                    "temperature": self.temperature,
                    "max_tokens": self.max_tokens,
                    "messages": [{"role": "user", "content": prompt}],
                }
            )

            text = _extract_text_blocks(response)
            parsed = _extract_json_from_text(text)

            # If parsing failed or classified_listings missing, try to extract partial results
            if not parsed or "classified_listings" not in parsed:
                # Try to extract incomplete classified_listings array
                partial_results = self._extract_partial_classified_listings(text)
                if partial_results:
                    # Check if we got all items from the batch
                    if len(partial_results) >= len(batch):
                        # Got all items, JSON was just not properly closed - treat as success
                        parsed = {"classified_listings": partial_results}
                    else:
                        # Got partial results but missing some items
                        print(
                            f"Warning: DeepSeek response incomplete for batch {batch_index}, "
                            f"extracted {len(partial_results)}/{len(batch)} items. "
                            f"Raw snippet: {text[:500]}"
                        )
                        parsed = {"classified_listings": partial_results}
                else:
                    print(
                        f"Warning: DeepSeek response missing 'classified_listings' (batch {batch_index}). "
                        f"Raw snippet: {text[:500]}"
                    )
                    # Retry this batch - don't mark as uncategorised yet
                    raise Exception(f"DeepSeek response missing 'classified_listings' for batch {batch_index}")

            batch_results = parsed.get("classified_listings", [])
            if not isinstance(batch_results, list):
                print(
                    f"Warning: 'classified_listings' not a list in batch {batch_index}. Retrying batch."
                )
                raise Exception(f"'classified_listings' not a list in batch {batch_index}")
            
            # Check if any items are missing from the response
            returned_ids = {str(item.get("id", "")) for item in batch_results}
            missing_items = [item for item in batch if str(item.item_id) not in returned_ids]
            
            # Add missing items as uncategorised (will be retried at classify level)
            for item in missing_items:
                batch_results.append({
                    "id": item.item_id,
                    "keep": True,
                    "category": "Uncategorised",
                    "reason": "Item missing from DeepSeek response",
                    "normalized_title": item.title,
                    "price": f"${item.price:.2f}" if item.price else "unknown",
                    "listing_type": item.listing_type,
                })
            
            return {
                "batch_index": batch_index,
                "ids": [item.item_id for item in batch],
                "response": text,
                "error": None,
                "results": batch_results,
            }
            
        except Exception as exc:
            # Batch failed after all retries - mark all items as keep=True
            error_msg = str(exc)
            print(
                f"Error: Batch {batch_index} failed after retries: {error_msg}. "
                f"Marking {len(batch)} items as keep=True with default category."
            )
            batch_results = []
            for item in batch:
                batch_results.append({
                    "id": item.item_id,
                    "keep": True,
                    "category": "Uncategorised",
                    "reason": f"Classification failed: {error_msg[:100]}",
                    "normalized_title": item.title,
                    "price": f"${item.price:.2f}" if item.price else "unknown",
                    "listing_type": item.listing_type,
                })
            return {
                "batch_index": batch_index,
                "ids": [item.item_id for item in batch],
                "response": None,
                "error": error_msg,
                "results": batch_results,
            }

    async def classify(self, query: str, listings: List[Listing]) -> Dict[str, object]:
        """Classify listings using limited concurrent DeepSeek requests"""
        results: List[Dict[str, object]] = []
        raw_batches: List[Dict[str, object]] = []

        # Create all batch tasks
        batches = list(_chunk_list(listings, self.batch_size))
        print(f"Processing {len(batches)} batches (max {self.max_concurrent_batches} concurrent) for {len(listings)} listings")
        
        # Use semaphore to limit concurrent batches
        semaphore = asyncio.Semaphore(self.max_concurrent_batches)
        
        async def process_with_limit(batch_index: int, batch: List[Listing]):
            async with semaphore:
                return await self._process_batch(query, batch, batch_index)
        
        # Process batches with concurrency limit
        batch_tasks = [
            process_with_limit(batch_index, batch)
            for batch_index, batch in enumerate(batches)
        ]
        
        # Wait for all batches to complete
        batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)
        
        # Process results
        for batch_result in batch_results:
            if isinstance(batch_result, Exception):
                print(f"Batch task raised exception: {batch_result}")
                continue
            
            raw_batches.append({
                "batch_index": batch_result["batch_index"],
                "ids": batch_result["ids"],
                "response": batch_result.get("response"),
                "error": batch_result.get("error"),
            })
            
            results.extend(batch_result.get("results", []))
        
        # Retry uncategorised items
        uncategorised_results = [r for r in results if r.get("category") == "Uncategorised" or not r.get("category")]
        if uncategorised_results:
            print(f"Found {len(uncategorised_results)} uncategorised items, retrying classification...")
            # Map results back to listings
            result_map = {str(r.get("id", "")): r for r in results}
            uncategorised_listings = []
            for listing in listings:
                if str(listing.item_id) in result_map:
                    result = result_map[str(listing.item_id)]
                    if result.get("category") == "Uncategorised" or not result.get("category"):
                        uncategorised_listings.append(listing)
            
            if uncategorised_listings:
                # Retry uncategorised items in smaller batches
                retry_batches = list(_chunk_list(uncategorised_listings, 5))  # Smaller batches for retry
                print(f"Retrying {len(uncategorised_listings)} uncategorised items in {len(retry_batches)} batches")
                
                retry_tasks = [
                    process_with_limit(1000 + batch_idx, batch)  # Use high index to avoid conflicts
                    for batch_idx, batch in enumerate(retry_batches)
                ]
                
                retry_results = await asyncio.gather(*retry_tasks, return_exceptions=True)
                
                # Update results with retry classifications
                result_map = {str(r.get("id", "")): r for r in results}
                for retry_result in retry_results:
                    if isinstance(retry_result, Exception):
                        continue
                    for retry_item in retry_result.get("results", []):
                        item_id = str(retry_item.get("id", ""))
                        # Only update if we got a better category (not Uncategorised)
                        if item_id in result_map and retry_item.get("category") and retry_item.get("category") != "Uncategorised":
                            result_map[item_id] = retry_item
                            print(f"Updated item {item_id} from Uncategorised to {retry_item.get('category')}")
                
                # Update results list
                results = list(result_map.values())
        
        print(f"Classification complete: processed {len(batches)} batches, got {len(results)} results")
        
        return {
            "classified_listings": results,
            "raw_batches": raw_batches,
        }

    async def _send_with_retry(self, payload: Dict[str, object]):
        attempt = 0
        delay = self.retry_initial_delay
        while True:
            attempt += 1
            try:
                response = await self.client.chat.completions.create(**payload)  # type: ignore[arg-type]
                return response
            except Exception as exc:
                if not self._should_retry(exc, attempt):
                    raise
                sleep_for = min(delay, self.retry_max_delay)
                jitter = random.uniform(0, sleep_for * 0.25)
                total_sleep = sleep_for + jitter
                status_description = self._describe_http_error(exc)
                print(
                    f"DeepSeek request attempt {attempt} failed ({status_description}); "
                    f"retrying in {total_sleep:.2f}s"
                )
                await asyncio.sleep(total_sleep)
                delay = min(delay * 2, self.retry_max_delay)

    def _should_retry(self, exc: Exception, attempt: int) -> bool:
        if attempt >= self.max_retries:
            return False

        response = getattr(exc, "response", None)
        status_code = getattr(response, "status_code", None)

        headers: Dict[str, str] = {}
        if response is not None:
            try:
                headers = {str(k).lower(): str(v) for k, v in response.headers.items()}
            except Exception:
                headers = {}

        # Always retry if header explicitly says to retry
        if headers.get("x-should-retry") == "true":
            return True

        # For 5xx server errors, retry even if x-should-retry is false
        # These are typically transient server issues
        server_error_statuses = {500, 502, 503, 504, 522, 524, 529}
        if status_code in server_error_statuses:
            return True

        # Other retryable statuses
        retryable_statuses = {
            408,  # Request Timeout
            409,  # Conflict
            425,  # Too Early
            429,  # Too Many Requests
        }

        return status_code in retryable_statuses

    @staticmethod
    def _describe_http_error(exc: Exception) -> str:
        response = getattr(exc, "response", None)
        if isinstance(exc, httpx.HTTPStatusError):
            return f"HTTP {exc.response.status_code}"
        if response is not None and hasattr(response, "status_code"):
            return f"HTTP {response.status_code}"
        return exc.__class__.__name__


class ScrapingBeeAIScraper:
    """Main orchestrator for scraping and AI-enabled analysis."""

    def __init__(
        self,
        query: str,
        *,
        category_id: int = 6030,
        max_pages: int = 50,
        items_per_page: int = 240,
        claude_model: Optional[str] = None,
        claude_batch_size: int = 10,
        vehicle_year: Optional[int] = None,
        vehicle_make: Optional[str] = None,
        vehicle_model: Optional[str] = None,
        part_name: Optional[str] = None,
    ) -> None:
        if not ScrapingBeeConfig.API_KEY:
            print("SCRAPING_BEE_API_KEY is not configured; requests will fail.")

        self.query = query.strip()
        self.category_id = category_id
        self.max_pages = max_pages
        self.items_per_page = items_per_page
        self.headers = {
            "Accept-Language": "en-US,en;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        }
        self.pages_fetched: Dict[str, int] = {"active": 0, "sold": 0}
        self.request_count = 0
        # Use embedding-based matcher instead of batch categorizer
        self.classifier = EmbeddingCategoryMatcher(
            deepseek_model=claude_model,
            title_cleaning_batch_size=claude_batch_size,
            similarity_threshold=0.90,
        )
        
        # Store vehicle and part information
        self.vehicle_year = vehicle_year
        self.vehicle_make = vehicle_make
        self.vehicle_model = vehicle_model
        self.part_name = part_name
        
        # Create a single session that will be reused for all requests
        self.session: Optional[aiohttp.ClientSession] = None

    def _ensure_locale(self, url: str) -> str:
        if "ebay.com" not in url:
            return url

        separator = "&" if "?" in url else "?"
        if "_ul=" not in url:
            url = f"{url}{separator}_ul=US"
            separator = "&"
        if "_fcid=" not in url:
            url = f"{url}{separator}_fcid=1"
        return url

    def _build_page_url(self, listing_type: str, page: int) -> str:
        base_url = f"https://www.ebay.com/sch/{self.category_id}/i.html"
        params = [
            f"_nkw={quote(self.query)}",
            f"_ipg={self.items_per_page}",
            "LH_ItemCondition=3000",
        ]

        if listing_type == "sold":
            params.extend(["LH_Sold=1", "LH_Complete=1", "rt=nc"])

        if page > 1:
            params.append(f"_pgn={page}")

        return f"{base_url}?{'&'.join(params)}"

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create the aiohttp session"""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(
                headers=self.headers,
                timeout=aiohttp.ClientTimeout(total=60),
            )
        return self.session

    async def _fetch_page_with_retry(self, url: str, wait_for: Optional[str], max_retries: int = 5) -> Optional[BeautifulSoup]:
        """Fetch a page with retry logic - retries until success"""
        url = self._ensure_locale(url)
        params = ScrapingBeeConfig.build_params(url, wait_for=wait_for)
        
        for attempt in range(1, max_retries + 1):
            try:
                self.request_count += 1
                print(f"ScrapingBee request #{self.request_count} (attempt {attempt}/{max_retries}): {url}")

                session = await self._get_session()
                async with session.get(
                    ScrapingBeeConfig.API_URL,
                    params=params,
                ) as response:
                    if response.status != 200:
                        snippet = await response.text()
                        print(f"ScrapingBee request failed (status={response.status}, attempt {attempt}): {snippet[:200]}")
                        if attempt < max_retries:
                            await asyncio.sleep(2 ** attempt)  # Exponential backoff
                            continue
                        return None
                    
                    content = await response.read()
                    await asyncio.sleep(ScrapingBeeConfig.REQUEST_DELAY_SECONDS)
                    return BeautifulSoup(content, "html.parser")
            except Exception as exc:
                print(f"ScrapingBee request failed (attempt {attempt}/{max_retries}): {exc}")
                if attempt < max_retries:
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
                    continue
                return None
        
        return None

    @staticmethod
    def _clean_title_text(title: str) -> str:
        if not title:
            return title
        title = re.sub(r"\s*Opens\s+in\s+a\s+new\s+window\s+or\s+tab\s*", " ", title, flags=re.IGNORECASE)
        title = re.sub(r"\(For:\s*[^)]+\)", "", title, flags=re.IGNORECASE)
        title = re.sub(r"\s+", " ", title).strip()
        return title

    def _parse_listing_block(self, block: str, page: int, listing_type: str) -> Optional[Listing]:
        soup = BeautifulSoup(block, "html.parser")

        title_elem = soup.select_one(".s-card__title, [class*='s-card__title']")
        if not title_elem:
            return None
        title_text = self._clean_title_text(title_elem.get_text(strip=True))
        if not title_text:
            return None

        link_elem = soup.find("a", href=re.compile(r"/itm/\d+"))
        if not link_elem:
            return None
        url = link_elem.get("href", "")
        if not url:
            return None
        if not url.startswith("http"):
            url = "https://www.ebay.com" + url

        id_match = re.search(r"/itm/(\d+)", url)
        item_id = id_match.group(1) if id_match else str(abs(hash(url)))

        price_elem = soup.select_one(".s-card__price, [class*='s-card__price']")
        price = _safe_float(price_elem.get_text() if price_elem else None)

        shipping = None
        shipping_match = re.search(r"\+\$([\d.,]+)\s+shipping", block, re.IGNORECASE)
        if shipping_match:
            shipping = _safe_float(shipping_match.group(1))
        elif re.search(r"free\s+shipping", block, re.IGNORECASE):
            shipping = 0.0

        seller = "Unknown"
        seller_feedback = ""
        attr_rows = soup.find_all("div", class_=re.compile(r"s-card__attribute-row"))
        for attr_row in attr_rows:
            inner_text = attr_row.get_text(separator=" ", strip=True)
            inner_text = re.sub(r"\s+", " ", inner_text)

            match = re.match(r"^([A-Za-z0-9\-_]+)\s+([\d.]+)%\s+(positive|negative)\s+\(([^)]+)\)", inner_text, re.I)
            if match:
                seller = match.group(1)
                seller_feedback = f"{match.group(2)}% {match.group(3)} ({match.group(4)})"
                break

            alt = re.match(r"^([A-Za-z0-9\-_]+)\s+(positive|negative)\s+\(([^)]+)\)", inner_text, re.I)
            if alt:
                seller = alt.group(1)
                seller_feedback = f"{alt.group(2)} ({alt.group(3)})"
                break

            parts = inner_text.split()
            if parts and not parts[0].startswith("$") and not parts[0].replace(".", "").isdigit():
                seller = parts[0]

        # Extract image URL - try multiple strategies
        image_url = None
        
        # Strategy 1: Look for img tag with common eBay image classes
        img_elem = soup.find("img", class_=re.compile(r"image|img|thumbnail|s-item__image", re.I))
        if not img_elem:
            # Strategy 2: Look for any img tag
            img_elem = soup.find("img")
        
        if img_elem:
            # Try src first
            image_url = img_elem.get("src") or img_elem.get("data-src") or img_elem.get("data-lazy-src")
            # Try data attributes common in eBay listings
            if not image_url:
                image_url = img_elem.get("data-zoom-src") or img_elem.get("data-original")
            # If not found, try href on parent link
            if not image_url:
                parent_link = img_elem.find_parent("a")
                if parent_link:
                    href = parent_link.get("href")
                    # Only use href if it looks like an image URL
                    if href and any(ext in href.lower() for ext in [".jpg", ".jpeg", ".png", ".gif", ".webp", "ebayimg"]):
                        image_url = href
            # Clean up the URL
            if image_url:
                if image_url.startswith("//"):
                    image_url = "https:" + image_url
                elif image_url.startswith("/"):
                    image_url = "https://www.ebay.com" + image_url
                # Remove query parameters that might make image unavailable, but keep important ones
                if "?" in image_url:
                    # Keep s-lXXX parameters (eBay image size parameters)
                    if "s-l" in image_url:
                        parts = image_url.split("?")
                        base = parts[0]
                        params = parts[1].split("&")
                        keep_params = [p for p in params if "s-l" in p]
                        if keep_params:
                            image_url = base + "?" + "&".join(keep_params)
                        else:
                            image_url = base
                    else:
                        image_url = image_url.split("?")[0]

        return Listing(
            item_id=item_id,
            title=title_text,
            raw_title=title_text,
            price=price,
            url=url,
            shipping=shipping,
            page=page,
            listing_type=listing_type,
            seller=seller,
            seller_feedback=seller_feedback,
            image_url=image_url,
        )

    def _parse_page(self, soup: BeautifulSoup, page: int, listing_type: str) -> List[Listing]:
        results_container = soup.find("div", id="srp-river-results")

        selectors = [
            "ul li.s-card",
            ".s-card",
        ]

        elements: List[BeautifulSoup] = []
        for selector in selectors:
            if results_container:
                elements = results_container.select(selector)
            else:
                elements = soup.select(selector)
            if elements:
                break

        listings: List[Listing] = []
        for element in elements:
            listing_html = str(element)
            listing = self._parse_listing_block(listing_html, page, listing_type)
            if listing:
                listings.append(listing)
        print(f"_parse_page: listing_type={listing_type}, page={page}, listings_found={len(listings)}")
        return listings

    async def _fetch_and_parse_page(self, listing_type: str, page: int, semaphore: asyncio.Semaphore) -> Optional[Dict[str, object]]:
        """Fetch and parse a single page - used for parallel processing"""
        async with semaphore:  # Limit concurrent requests
            url = self._build_page_url(listing_type, page)
            wait_selector = "#srp-river-results" if page > 1 else ".srp-controls__count-heading"
            soup = await self._fetch_page_with_retry(url, wait_selector)
            
            if not soup:
                return {
                    "page": page,
                    "listings": [],
                    "success": False,
                    "error": "Failed to fetch page",
                }
            
            page_listings = self._parse_page(soup, page, listing_type)
            return {
                "page": page,
                "listings": page_listings,
                "success": True,
                "error": None,
            }

    async def _collect_listings(self, listing_type: str) -> List[Listing]:
        """Collect listings with parallel page fetching (max 50 concurrent)"""
        all_listings: List[Listing] = []
        seen_ids: set[str] = set()
        max_concurrent = 50  # Maximum concurrent ScrapingBee requests
        semaphore = asyncio.Semaphore(max_concurrent)
        max_consecutive_empty = 2  # Stop after 2 consecutive pages with no new items
        duplicate_threshold = 0.8  # Stop if >80% of items are duplicates in a chunk
        max_high_duplicate_chunks = 2  # Stop after 2 chunks with high duplicate ratio

        print(f"{listing_type.capitalize()}: Starting parallel collection (max {max_concurrent} concurrent requests)")

        # Process pages in batches to check for early stopping
        consecutive_empty_pages = 0
        consecutive_high_duplicate_chunks = 0
        pages_to_process = list(range(1, self.max_pages + 1))
        
        # Process pages in chunks to allow early stopping
        chunk_size = 40  # Process 40 pages at a time
        for chunk_start in range(0, len(pages_to_process), chunk_size):
            chunk_pages = pages_to_process[chunk_start:chunk_start + chunk_size]
            # Create tasks dynamically for this chunk only
            chunk_tasks = [
                self._fetch_and_parse_page(listing_type, page, semaphore)
                for page in chunk_pages
            ]
            
            print(f"{listing_type.capitalize()}: Processing pages {chunk_pages[0]}-{chunk_pages[-1]} in parallel")
            
            # Wait for this chunk to complete
            chunk_results = await asyncio.gather(*chunk_tasks, return_exceptions=True)
            
            # Process results from this chunk
            chunk_has_new_items = False
            chunk_total_items = 0
            chunk_new_items = 0
            
            for result in chunk_results:
                if isinstance(result, Exception):
                    print(f"{listing_type.capitalize()}: Page task raised exception: {result}")
                    consecutive_empty_pages += 1
                    continue
                
                if not result or not result.get("success"):
                    consecutive_empty_pages += 1
                    continue
                
                page = result["page"]
                page_listings = result["listings"]
                
                if not page_listings:
                    consecutive_empty_pages += 1
                    print(f"{listing_type.capitalize()} page {page}: No listings found (consecutive empty: {consecutive_empty_pages})")
                    if consecutive_empty_pages >= max_consecutive_empty:
                        print(f"{listing_type.capitalize()}: Stopping after {consecutive_empty_pages} consecutive empty pages")
                        return all_listings
                    continue
                
                chunk_total_items += len(page_listings)
                new_items = 0
                duplicates = 0
                
                for listing in page_listings:
                    if listing.item_id in seen_ids:
                        duplicates += 1
                        continue
                    seen_ids.add(listing.item_id)
                    all_listings.append(listing)
                    new_items += 1
                
                chunk_new_items += new_items
                
                if new_items > 0:
                    chunk_has_new_items = True
                    consecutive_empty_pages = 0
                
                print(
                    "%s page %s: %s listings (new=%s, duplicates=%s, total=%s)",
                    listing_type.capitalize(),
                    page,
                    len(page_listings),
                    new_items,
                    duplicates,
                    len(all_listings),
                )
                
                self.pages_fetched[listing_type] += 1
            
            # Check duplicate ratio for this chunk
            if chunk_total_items > 0:
                duplicate_ratio = (chunk_total_items - chunk_new_items) / chunk_total_items
                print(f"{listing_type.capitalize()}: Chunk duplicate ratio: {duplicate_ratio:.1%} ({chunk_total_items - chunk_new_items}/{chunk_total_items} duplicates)")
                
                if duplicate_ratio >= duplicate_threshold:
                    consecutive_high_duplicate_chunks += 1
                    print(f"{listing_type.capitalize()}: High duplicate ratio detected ({duplicate_ratio:.1%}). Consecutive high-duplicate chunks: {consecutive_high_duplicate_chunks}")
                    
                    if consecutive_high_duplicate_chunks >= max_high_duplicate_chunks:
                        print(f"{listing_type.capitalize()}: Stopping scraping - too many duplicate listings ({duplicate_ratio:.1%} duplicates in last {consecutive_high_duplicate_chunks} chunks)")
                        break
                else:
                    consecutive_high_duplicate_chunks = 0  # Reset counter if we get a chunk with low duplicates
            
            # Check if we should stop early
            if not chunk_has_new_items:
                consecutive_empty_pages += len(chunk_results)
                if consecutive_empty_pages >= max_consecutive_empty:
                    print(f"{listing_type.capitalize()}: Stopping after {consecutive_empty_pages} consecutive pages with no new items")
                    break

        print(f"{listing_type.capitalize()}: Finished collecting. Total pages: {self.pages_fetched[listing_type]}, Total unique listings: {len(all_listings)}")
        return all_listings

    @staticmethod
    def _deduplicate_listings(listings: List[Listing]) -> List[Listing]:
        """Remove duplicate listings based on item_id, keeping the first occurrence."""
        seen_ids: set[str] = set()
        unique_listings: List[Listing] = []
        duplicates_count = 0
        
        for listing in listings:
            if listing.item_id in seen_ids:
                duplicates_count += 1
                continue
            seen_ids.add(listing.item_id)
            unique_listings.append(listing)
        
        if duplicates_count > 0:
            print(f"Deduplication: Removed {duplicates_count} duplicate listings ({len(listings)} -> {len(unique_listings)})")
        else:
            print(f"Deduplication: No duplicates found ({len(listings)} listings)")
        
        return unique_listings

    def _apply_classification(self, listings: List[Listing], classified_entries: List[Dict[str, object]]) -> Dict[str, Dict[str, object]]:
        mapping: Dict[str, Dict[str, object]] = {}
        print("classified entries")
        for entry in classified_entries:
            print("entry in classified entries", entry)
            listing_id = str(entry.get("id", ""))
            if not listing_id:
                print("no listing id thats why it is marked as uncategorized")
                continue
            mapping[listing_id] = entry

        for listing in listings:
            print("Listing", listing)
            entry = mapping.get(listing.item_id)
            if not entry:
                print("No entry", mapping)
                listing.category = "Uncategorised"
                listing.keep = True
                continue

            listing.keep = bool(entry.get("keep", True))
            listing.category = entry.get("category") or "Uncategorised"
            reason = entry.get("reason") or entry.get("rationale")
            listing.classification_reason = reason
            normalized_title = entry.get("normalized_title") or entry.get("normalised_title")
            if normalized_title:
                listing.title = normalized_title

        return mapping
    
    @staticmethod
    def _calculate_similarity(str1: str, str2: str) -> float:
        """Calculate similarity ratio between two strings using SequenceMatcher"""
        return SequenceMatcher(None, str1.lower(), str2.lower()).ratio()
    
    @staticmethod
    def _extract_core_part_name(category: str) -> str:
        """Extract core part name by removing specifications, variants, and normalizing"""
        import re
        core = category.lower().strip()
        
        # Remove everything in parentheses
        core = re.sub(r'\([^)]*\)', '', core)
        
        # Remove common variant words (hybrid, halogen, xenon, etc.)
        variant_words = ['hybrid', 'halogen', 'xenon', 'hid', 'led', 'standard', 'premium', 'base', 'turbo', 'sport']
        for word in variant_words:
            core = re.sub(rf'\b{word}\b', '', core, flags=re.IGNORECASE)
        
        # Remove common location/position words
        location_words = ['left', 'right', 'front', 'rear', 'driver', 'passenger', 'upper', 'lower', 'inner', 'outer']
        for word in location_words:
            core = re.sub(rf'\b{word}\b', '', core, flags=re.IGNORECASE)
        
        # Normalize common terms (keep them as-is, just ensure consistent casing)
        # These terms are already normalized, so we don't need to replace them
        
        # Remove extra whitespace and normalize
        core = re.sub(r'\s+', ' ', core).strip()
        
        # Extract key words (remove common filler words)
        words = core.split()
        filler_words = {'the', 'a', 'an', 'for', 'with', 'and', 'or', 'of', 'to', 'in', 'on', 'at', 'by'}
        key_words = [w for w in words if w not in filler_words and len(w) > 2]
        
        # Sort key words to normalize order (e.g., "abs pump" and "pump abs" become same)
        key_words_sorted = sorted(key_words)
        return ' '.join(key_words_sorted) if key_words_sorted else core
    
    @staticmethod
    def _group_by_similarity(categories: List[str], threshold: float = 0.30) -> List[List[str]]:
        """Group ALL categories by core part name and string similarity - every category goes into a group"""
        if not categories:
            return []
        
        # Filter out "Uncategorised" - it should never be merged
        categories_to_group = [cat for cat in categories if cat != "Uncategorised"]
        uncategorised = [cat for cat in categories if cat == "Uncategorised"]
        
        if not categories_to_group:
            return [[cat] for cat in uncategorised] if uncategorised else []
        
        groups: List[List[str]] = []
        used = set()
        
        # First pass: Group by core part name (normalized)
        core_name_groups: Dict[str, List[str]] = {}
        for cat in categories_to_group:
            core_name = ScrapingBeeAIScraper._extract_core_part_name(cat)
            if core_name:
                if core_name not in core_name_groups:
                    core_name_groups[core_name] = []
                core_name_groups[core_name].append(cat)
        
        # Add ALL groups (even single items) - we'll send them all to AI
        for core_name, cats in core_name_groups.items():
            groups.append(cats)
            used.update(cats)
        
        # Second pass: Group remaining categories by string similarity
        remaining = [cat for cat in categories_to_group if cat not in used]
        
        for i, cat1 in enumerate(remaining):
            if cat1 in used:
                continue
            
            # Start a new group with this category
            group = [cat1]
            used.add(cat1)
            
            # Find all similar categories
            for j, cat2 in enumerate(remaining):
                if i == j or cat2 in used:
                    continue
                
                similarity = ScrapingBeeAIScraper._calculate_similarity(cat1, cat2)
                if similarity >= threshold:
                    group.append(cat2)
                    used.add(cat2)
            
            groups.append(group)
        
        # Add uncategorised as separate single-item groups
        for cat in uncategorised:
            groups.append([cat])
        
        # Third pass: Merge single-item groups into other groups based on keyword matching
        single_item_groups = [g for g in groups if len(g) == 1]
        multi_item_groups = [g for g in groups if len(g) > 1]
        
        if single_item_groups and multi_item_groups:
            merged_singles = set()
            for single_group in single_item_groups:
                single_cat = single_group[0]
                if single_cat in merged_singles:
                    continue
                
                # Extract keywords from single category
                single_core = ScrapingBeeAIScraper._extract_core_part_name(single_cat)
                single_keywords = set(single_core.split())
                single_keywords_lower = {kw.lower() for kw in single_keywords if len(kw) > 2}
                single_cat_lower = single_cat.lower()
                
                if not single_keywords_lower:
                    continue
                
                # Find best matching multi-item group
                best_match_idx = -1
                best_match_score = 0
                
                for idx, multi_group in enumerate(multi_item_groups):
                    # Extract keywords from all categories in this group
                    group_keywords = set()
                    group_cats_lower = []
                    for cat in multi_group:
                        cat_core = ScrapingBeeAIScraper._extract_core_part_name(cat)
                        cat_keywords = cat_core.split()
                        group_keywords.update({kw.lower() for kw in cat_keywords if len(kw) > 2})
                        group_cats_lower.append(cat.lower())
                    
                    # Calculate keyword overlap score
                    overlap = len(single_keywords_lower & group_keywords)
                    total_unique = len(single_keywords_lower | group_keywords)
                    keyword_score = overlap / total_unique if total_unique > 0 else 0
                    
                    # Also check if single category name appears in any group category (substring match)
                    substring_score = 0
                    for group_cat in group_cats_lower:
                        # Check if significant words from single category appear in group category
                        matching_words = sum(1 for kw in single_keywords_lower if kw in group_cat)
                        if matching_words > 0:
                            substring_score = max(substring_score, matching_words / len(single_keywords_lower))
                    
                    # Combined score (weighted: 70% keyword overlap, 30% substring match)
                    score = (keyword_score * 0.7) + (substring_score * 0.3)
                    
                    if score > best_match_score and score > 0.2:  # At least 20% combined score
                        best_match_score = score
                        best_match_idx = idx
                
                # Merge single category into best matching group
                if best_match_idx >= 0:
                    multi_item_groups[best_match_idx].append(single_cat)
                    merged_singles.add(single_cat)
                    print(f"Merged single-item category '{single_cat}' into group with {len(multi_item_groups[best_match_idx])-1} items (match score: {best_match_score*100:.0f}%)")
            
            # Rebuild groups: multi-item groups + remaining single-item groups
            groups = multi_item_groups + [[g[0]] for g in single_item_groups if g[0] not in merged_singles]
        
        return groups
    
    @staticmethod
    def _force_merge_by_keywords(categories: List[str], target_count: int) -> Dict[str, str]:
        """Force merge categories by keyword similarity when we have too many categories"""
        if len(categories) <= target_count:
            return {}
        
        merge_mapping: Dict[str, str] = {}
        used = set()
        
        # Sort categories by length (shorter = more general, use as canonical)
        sorted_cats = sorted(categories, key=len)
        
        for i, cat1 in enumerate(sorted_cats):
            if cat1 in used:
                continue
            
            # Extract keywords from cat1
            core1 = ScrapingBeeAIScraper._extract_core_part_name(cat1)
            keywords1 = set(core1.split())
            
            if not keywords1:
                continue
            
            # Find similar categories
            similar = [cat1]  # Start with itself as canonical
            for j, cat2 in enumerate(sorted_cats):
                if i == j or cat2 in used:
                    continue
                
                core2 = ScrapingBeeAIScraper._extract_core_part_name(cat2)
                keywords2 = set(core2.split())
                
                if not keywords2:
                    continue
                
                # Calculate keyword overlap
                overlap = len(keywords1 & keywords2)
                total = len(keywords1 | keywords2)
                similarity = overlap / total if total > 0 else 0
                
                # If >30% keyword overlap, merge
                if similarity > 0.3:
                    similar.append(cat2)
                    used.add(cat2)
            
            # Use shortest category name as canonical
            canonical = min(similar, key=len)
            for cat in similar:
                if cat != canonical:
                    merge_mapping[cat] = canonical
                    used.add(cat)
            
            used.add(canonical)
        
        return merge_mapping
    
    async def _merge_category_group(self, category_group: List[str], phase: int) -> Optional[Dict[str, object]]:
        """Send a group of categories to DeepSeek to determine if they should be merged"""
        # Even single categories should be sent - AI will determine if they're unique or can merge with others
        if len(category_group) == 0:
            return None
        
        vehicle_info = f"{self.vehicle_year or ''} {self.vehicle_make or ''} {self.vehicle_model or ''}".strip()
        
        # Build prompt based on group size
        if len(category_group) == 1:
            # Single category - mark as unique (will be handled by batching)
            return {
                "canonical_name": category_group[0],
                "variations": [category_group[0]],
                "reason": "Single category",
                "should_merge": False
            }
        elif len(category_group) > 5:
            # Large batch (likely single-item categories batched together) - be very aggressive about merging
            prompt = f"""You are analyzing a batch of automotive part categories that were previously single-item groups. These need to be merged aggressively to reduce category count.

Vehicle: {vehicle_info if vehicle_info else 'Unknown'}

Categories to analyze (Phase {phase} - BATCH OF SINGLES):
{json.dumps(category_group, indent=2)}

CRITICAL: These are ALL single-item categories that need to be merged. BE VERY AGGRESSIVE:
1. Group categories that share ANY common keywords (e.g., "ABS pump", "ABS module", "ABS actuator" → all merge to "ABS pump")
2. Merge variants aggressively (e.g., "Hybrid ABS brake pump system", "hybrid abs brake pump", "abs hydraulic control unit/pump (hybrid)", "abs pump module" → ALL merge to "ABS pump")
3. If categories share 2+ keywords, they MUST merge
4. Create multiple merged groups if needed - not all categories need to merge into one

Return JSON array with multiple merge groups:
[
  {{
    "should_merge": true,
    "canonical_name": "Best name for this merged group",
    "reason": "Why these merge together",
    "variations": ["list of categories in this merge group"]
  }},
  {{
    "should_merge": true,
    "canonical_name": "Another merged group name",
    "reason": "Why these merge",
    "variations": ["list of categories"]
  }}
]

If a category truly cannot merge with any other, return it as a single-item group with should_merge: false.
Return JSON only, no markdown."""
        else:
            prompt = f"""You are analyzing automotive part categories to determine if they are variations of the same part.

Vehicle: {vehicle_info if vehicle_info else 'Unknown'}

Categories to analyze (Phase {phase}):
{json.dumps(category_group, indent=2)}

CRITICAL RULES - BE FLEXIBLE AND AGGRESSIVE IN MERGING:
1. MERGE if these are variations/descriptions of the SAME part type:
   - Different naming conventions (e.g., "Hybrid ABS brake pump system" = "hybrid abs brake pump" = "abs hydraulic control unit/pump (hybrid)" = "abs pump module" - ALL are ABS pump)
   - Different specifications in parentheses (e.g., "Headlight Assembly (Halogen, Left)" vs "Headlight Assembly (Xenon HID, Left, Hybrid)" - both are headlight assemblies)
   - Different word order (e.g., "ABS pump" vs "pump ABS" - same thing)
   - Different descriptions (e.g., "Sun visor set" vs "Sun visors (pair)")
   - Different trim/engine variants of the same part (e.g., "Engine assembly (1.6L)" vs "Engine assembly (2.0L)" - both are engine assemblies)
   - Core part name is the same, only specifications differ (e.g., "Bumper (Front)" vs "Front Bumper (Primed)" - both are front bumpers)
   - Variant words like "hybrid", "halogen", "xenon", "HID", "LED" don't make them different parts if core is same
   
2. DO NOT MERGE only if these are CLEARLY DIFFERENT parts:
   - Completely different part types (e.g., "Engine assembly" vs "Transmission")
   - Different components that serve different functions (e.g., "Front bumper" vs "Rear bumper")
   - Fundamentally different assemblies (e.g., "Short block" vs "Long block" - these are different engine configurations)

3. BE AGGRESSIVE: When in doubt, MERGE. If the core part name is the same and only specifications/variants differ, merge them.

Return JSON with this structure:
{{
  "should_merge": true/false,
  "canonical_name": "Best name for the merged category (use most descriptive, remove variant words like 'hybrid' if not essential)",
  "reason": "Brief explanation of why merge or not merge",
  "variations": ["list of ALL category names that should be merged together"]
}}

If should_merge is true, ALL categories in the list should be in variations array.
If should_merge is false, return variations as empty array.
Return JSON only, no markdown or extra commentary."""
        
        try:
            response = await self.classifier._send_with_retry({
                "model": self.classifier.deepseek_model,
                "temperature": 0.3,
                "max_tokens": 2000,
                "messages": [{"role": "user", "content": prompt}],
            })
            
            text = _extract_text_blocks(response)
            parsed = _extract_json_from_text(text)
            
            # Handle array response (for batches of single categories)
            if isinstance(parsed, list) and len(parsed) > 0:
                # Multiple merge groups returned - combine them
                all_variations = []
                all_canonicals = []
                for group in parsed:
                    # Ensure group is a dictionary, not a string
                    if not isinstance(group, dict):
                        continue
                    if group.get("should_merge") and group.get("canonical_name"):
                        canonical = group["canonical_name"]
                        variations = group.get("variations", [])
                        # Ensure variations is a list
                        if not isinstance(variations, list):
                            variations = [variations] if variations else []
                        all_canonicals.append(canonical)
                        all_variations.extend(variations)
                
                if all_variations:
                    # Use the first canonical as the main one, or find most common
                    main_canonical = all_canonicals[0] if all_canonicals else category_group[0]
                    return {
                        "canonical_name": main_canonical,
                        "variations": all_variations,
                        "reason": f"Merged {len(parsed)} groups",
                        "should_merge": True
                    }
            
            # Handle single object response
            if isinstance(parsed, dict):
                canonical_name = parsed.get("canonical_name")
                if not canonical_name and len(category_group) == 1:
                    canonical_name = category_group[0]
                
                if canonical_name:
                    variations = parsed.get("variations", category_group)
                    # Ensure variations is a list
                    if not isinstance(variations, list):
                        variations = [variations] if variations else category_group
                    # If should_merge is false but we have variations, use them anyway
                    if not variations and len(category_group) > 1:
                        variations = category_group
                    
                    return {
                        "canonical_name": canonical_name,
                        "variations": variations if variations else category_group,
                        "reason": parsed.get("reason", ""),
                        "should_merge": parsed.get("should_merge", len(category_group) > 1)
                    }
            
            return None
        except Exception as exc:
            print(f"Error merging category group {category_group}: {exc}")
            return None
    
    async def _merge_similar_categories(self, listings: List[Listing]) -> Dict[str, str]:
        """Merge similar categories iteratively until no categories have >30% similarity and total categories <= 100"""
        # Get unique categories (excluding Uncategorised)
        unique_categories = list(set(
            listing.category for listing in listings 
            if listing.category and listing.category != "Uncategorised"
        ))
        
        if len(unique_categories) < 2:
            print("Not enough categories to merge (need at least 2)")
            return {}
        
        print(f"Merging similar categories: {len(unique_categories)} unique categories found")
        
        merge_mapping: Dict[str, str] = {}  # original -> canonical
        phase = 0
        max_phases = 20  # Increased limit for aggressive merging
        max_categories = 100  # Target maximum categories
        threshold = 0.30  # Start with 30% similarity
        
        # Continue merging until no more similar categories are found AND we're under 100 categories
        while phase < max_phases:
            phase += 1
            
            # Get current unique categories (after previous merges - these are the merged categories from previous phases)
            current_categories = list(set(
                listing.category for listing in listings 
                if listing.category and listing.category != "Uncategorised"
            ))
            
            print(f"Phase {phase}: Starting with {len(current_categories)} categories (from previous phase merges)")
            
            if len(current_categories) < 2:
                print(f"Phase {phase}: Not enough categories to merge (only {len(current_categories)} remaining)")
                break
            
            # If we're under the limit, still try to merge more aggressively
            if len(current_categories) <= max_categories:
                # Still group and send to AI - might find more merges
                similarity_groups = self._group_by_similarity(current_categories, threshold=threshold)
                if not any(len(group) > 1 for group in similarity_groups):
                    print(f"Phase {phase}: {len(current_categories)} categories remaining (under {max_categories} limit). No groups found. Merging complete.")
                    break
            
            print(f"Phase {phase}: {len(current_categories)} categories remaining (target: <= {max_categories}), checking for merges...")
            
            # If we have too many categories, lower the threshold to merge more aggressively
            if len(current_categories) > max_categories:
                # Lower threshold progressively: 30% -> 25% -> 20% -> 15% -> 10%
                if len(current_categories) > 200:
                    threshold = 0.10
                elif len(current_categories) > 150:
                    threshold = 0.15
                elif len(current_categories) > 120:
                    threshold = 0.20
                elif len(current_categories) > max_categories:
                    threshold = 0.25
                print(f"Phase {phase}: Too many categories ({len(current_categories)}), lowering similarity threshold to {threshold*100:.0f}% for aggressive merging")
            
            # Group ALL categories by similarity (every category goes into a group)
            similarity_groups = self._group_by_similarity(current_categories, threshold=threshold)
            
            # Separate multi-item and single-item groups
            multi_item_groups = [g for g in similarity_groups if len(g) > 1]
            single_item_groups = [g[0] for g in similarity_groups if len(g) == 1]
            
            print(f"Phase {phase}: Grouped {len(current_categories)} categories into {len(multi_item_groups)} multi-item groups and {len(single_item_groups)} single-item categories at {threshold*100:.0f}% threshold")
            
            # If we have too many categories, send ALL single-item categories together to AI for cross-merging
            all_groups = multi_item_groups.copy()
            if len(current_categories) > max_categories and len(single_item_groups) > 0:
                # Batch single-item categories into groups of 20 for AI processing
                batch_size = 20
                for i in range(0, len(single_item_groups), batch_size):
                    single_batch = single_item_groups[i:i+batch_size]
                    all_groups.append(single_batch)
                print(f"Phase {phase}: Batching {len(single_item_groups)} single-item categories into {len(single_item_groups) // batch_size + 1} batches for cross-merging")
            else:
                # Add single-item groups as-is
                all_groups.extend([[cat] for cat in single_item_groups])
            
            print(f"Phase {phase}: Sending all {len(all_groups)} groups to AI for merging")
            
            # Process ALL groups in parallel
            merge_tasks = [
                self._merge_category_group(group, phase=phase)
                for group in all_groups
            ]
            
            merge_results = await asyncio.gather(*merge_tasks, return_exceptions=True)
            
            # Track if any merges occurred in this phase
            phase_merges: Dict[str, str] = {}
            merges_occurred = False
            
            # Apply merges from this phase
            for idx, result in enumerate(merge_results):
                if isinstance(result, Exception):
                    # If merge failed, try splitting the group and retrying
                    failed_group = all_groups[idx]
                    if len(failed_group) > 2:
                        print(f"Phase {phase}: Merge failed for group of {len(failed_group)} categories, trying split...")
                        # Split into smaller groups and retry
                        mid = len(failed_group) // 2
                        split1 = failed_group[:mid]
                        split2 = failed_group[mid:]
                        
                        # Retry with split groups
                        retry_results = await asyncio.gather(
                            self._merge_category_group(split1, phase=phase),
                            self._merge_category_group(split2, phase=phase),
                            return_exceptions=True
                        )
                        
                        # Process retry results
                        for retry_result in retry_results:
                            if isinstance(retry_result, Exception) or not retry_result:
                                continue
                            canonical = retry_result["canonical_name"]
                            variations = retry_result["variations"]
                            for variation in variations:
                                if variation != canonical:
                                    phase_merges[variation] = canonical
                                    merges_occurred = True
                                    print(f"Phase {phase} merge (retry): '{variation}' → '{canonical}'")
                    continue
                if not result:
                    continue
                
                canonical = result["canonical_name"]
                variations = result["variations"]
                should_merge = result.get("should_merge", len(variations) > 1)
                
                # IMPORTANT: Resolve variations to their current merged names (from previous phases)
                # If a variation was already merged in a previous phase, use its current canonical name
                resolved_variations = []
                for variation in variations:
                    # Check if this variation was already merged in a previous phase
                    if variation in merge_mapping:
                        # Use the current canonical name from previous merges
                        resolved_variation = merge_mapping[variation]
                        if resolved_variation not in resolved_variations:
                            resolved_variations.append(resolved_variation)
                    elif variation in current_categories:
                        # This is a current category name, use it as-is
                        resolved_variations.append(variation)
                    else:
                        # Variation doesn't exist in current categories, might be from AI hallucination
                        # Try to find a similar current category
                        found = False
                        for current_cat in current_categories:
                            if variation.lower() == current_cat.lower() or variation in current_cat or current_cat in variation:
                                resolved_variations.append(current_cat)
                                found = True
                                break
                        if not found:
                            # Use the variation as-is (might be a new category name from AI)
                            resolved_variations.append(variation)
                
                # Remove duplicates and ensure canonical is in the list
                resolved_variations = list(set(resolved_variations))
                if canonical not in resolved_variations and canonical in current_categories:
                    resolved_variations.append(canonical)
                
                # Use resolved variations
                variations = resolved_variations if resolved_variations else variations
                
                # If we have too many categories, be more aggressive - merge even if AI says no (if variations > 1)
                force_merge = len(current_categories) > max_categories and len(variations) > 1
                
                # Merge if should_merge is true OR if we have multiple variations OR if forcing merge
                if should_merge or len(variations) > 1 or force_merge:
                    for variation in variations:
                        # Only merge if variation is different from canonical and exists in current categories
                        if variation != canonical and variation in current_categories:
                            phase_merges[variation] = canonical
                            merges_occurred = True
                            merge_type = "forced" if force_merge and not should_merge else "normal"
                            print(f"Phase {phase} merge ({merge_type}): '{variation}' → '{canonical}'")
            
            # If still too many categories and no merges occurred, force merge by keyword similarity
            if not merges_occurred and len(current_categories) > max_categories:
                print(f"Phase {phase}: No AI merges occurred but still have {len(current_categories)} categories. Forcing keyword-based merges...")
                forced_merges = self._force_merge_by_keywords(current_categories, max_categories)
                if forced_merges:
                    phase_merges.update(forced_merges)
                    merges_occurred = True
                    print(f"Phase {phase}: Forced {len(forced_merges)} keyword-based merges")
            
            if not merges_occurred:
                print(f"Phase {phase}: No merges occurred. Merging complete.")
                if len(current_categories) > max_categories:
                    print(f"WARNING: Still have {len(current_categories)} categories (target: {max_categories}) but cannot merge further.")
                break
            
            # Apply phase merges to listings IMMEDIATELY so next phase uses merged categories
            for listing in listings:
                if listing.category in phase_merges:
                    old_category = listing.category
                    listing.category = phase_merges[listing.category]
                    if old_category != listing.category:
                        print(f"Phase {phase}: Updated listing category '{old_category}' → '{listing.category}'")
            
            # Verify merges were applied by recalculating categories
            updated_categories = list(set(
                listing.category for listing in listings 
                if listing.category and listing.category != "Uncategorised"
            ))
            print(f"Phase {phase}: After applying merges, {len(updated_categories)} unique categories remain (was {len(current_categories)})")
            
            # Update merge_mapping to reflect this phase's merges
            # For categories already in merge_mapping, trace through to find final canonical
            for orig_cat in list(merge_mapping.keys()):
                current_canonical = merge_mapping[orig_cat]
                # If current canonical was merged in this phase, update to new canonical
                if current_canonical in phase_merges:
                    merge_mapping[orig_cat] = phase_merges[current_canonical]
            
            # Add new phase merges for categories not yet in merge_mapping
            for phase_variation, phase_canonical in phase_merges.items():
                if phase_variation not in merge_mapping:
                    merge_mapping[phase_variation] = phase_canonical
            
            # IMPORTANT: Use the updated categories for the next phase
            # The next iteration will get current_categories from listings, which now have merged categories
        
        if phase >= max_phases:
            print(f"Warning: Reached maximum phases ({max_phases}). Stopping merge process.")
        
        final_categories = list(set(
            listing.category for listing in listings 
            if listing.category and listing.category != "Uncategorised"
        ))
        final_canonical_count = len(final_categories)
        
        print(f"Category merging complete after {phase} phase(s): {len(merge_mapping)} category mappings, {final_canonical_count} final canonical categories (from {len(unique_categories)} initial)")
        
        if final_canonical_count > 100:
            print(f"WARNING: Still have {final_canonical_count} categories (target: <= 100). Consider reviewing merge logic.")
        else:
            print(f"✅ Successfully reduced to {final_canonical_count} categories (target: <= 100)")
        
        return merge_mapping

    @staticmethod
    def _calculate_opportunity_score(sold_count: int, active_count: int, optimal_price: float) -> int:
        sold_count = max(0, sold_count)
        active_count = max(0, active_count)
        optimal_price = max(0.0, optimal_price)
        
        score = 0
        
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

    def _category_recommendation(self, score: int, sell_through: float, demand_level: str) -> str:
        if score >= 70 and sell_through >= 50:
            return "Excellent opportunity – strong demand and manageable competition."
        if score >= 50 and sell_through >= 30:
            return "Good opportunity – consider prioritising this category."
        if score >= 35:
            return "Moderate opportunity – list selectively and monitor competition."
        if demand_level == "low":
            return "Low demand – only list if acquisition cost is minimal."
        return "Limited opportunity – focus effort elsewhere unless inventory is on hand."

    def _build_category_summary(self, listings: List[Listing]) -> List[Dict[str, object]]:
        grouped: Dict[str, List[Listing]] = {}
        for listing in listings:
            category = listing.category or "Uncategorised"
            grouped.setdefault(category, []).append(listing)

        summary: List[Dict[str, object]] = []
        for category, cat_listings in grouped.items():
            active = [item for item in cat_listings if item.listing_type == "active" and item.price]
            sold = [item for item in cat_listings if item.listing_type == "sold" and item.price]

            active_count = len(active)
            sold_count = len(sold)
            total_count = len(cat_listings)
            sell_through = (sold_count / (sold_count + active_count) * 100) if (sold_count + active_count) else 0

            sold_prices = [item.price for item in sold if item.price is not None]
            active_prices = [item.price for item in active if item.price is not None]
            all_prices = sold_prices + active_prices
            
            optimal_price = round(statistics.median(sold_prices), 2) if sold_prices else 0
            avg_sold_price = round(statistics.mean(sold_prices), 2) if sold_prices else 0
            avg_active_price = round(statistics.mean(active_prices), 2) if active_prices else 0
            min_price = round(min(all_prices), 2) if all_prices else 0
            max_price = round(max(all_prices), 2) if all_prices else 0

            shipping_values = [item.shipping for item in sold if item.shipping]
            avg_shipping = round(statistics.mean(shipping_values), 2) if shipping_values else 0

            demand_level = "high" if sold_count >= 10 else "medium" if sold_count >= 5 else "low"
            competition_level = "high" if active_count >= 30 else "medium" if active_count >= 15 else "low"

            opportunity_score = self._calculate_opportunity_score(sold_count, active_count, optimal_price)
            recommendation = self._category_recommendation(opportunity_score, sell_through, demand_level)

            print(
                f"Category '{category}': total={total_count}, active={active_count}, sold={sold_count}, "
                f"score={opportunity_score}, demand={demand_level}, competition={competition_level}"
            )

            # Get one image URL per category (prefer sold listings, then active)
            category_image = None
            for listing in cat_listings:
                if listing.image_url:
                    category_image = listing.image_url
                    break

            summary.append(
                {
                    "category": category,
                    "total_listings": total_count,
                    "active_count": active_count,
                    "sold_count": sold_count,
                    "sell_through_rate": round(sell_through, 2),
                    "demand_level": demand_level,
                    "competition_level": competition_level,
                    "opportunity_score": opportunity_score,
                    "optimal_price": optimal_price,
                    "min_price": min_price,
                    "max_price": max_price,
                    "avg_sold_price": avg_sold_price,
                    "avg_active_price": avg_active_price,
                    "avg_shipping": avg_shipping,
                    "recommendation": recommendation,
                    "sample_titles": [item.title for item in cat_listings[:10]],
                    "image_url": category_image,
                    "items": [item.to_dict() for item in cat_listings],  # Add all items for this category
                    "item_count": len(cat_listings),
                }
            )

        summary.sort(key=lambda entry: entry["total_listings"], reverse=True)
        return summary

    async def _build_category_tree(self, category_summary: List[Dict[str, object]]) -> Dict[str, object]:
        """Build hierarchical category tree using batched DeepSeek requests for large category sets."""
        if not category_summary:
            return {"tree": [], "flat_categories": []}
        
        # Prepare category data with net values
        categories_data = []
        for entry in category_summary:
            optimal_price = entry.get("optimal_price") or 0
            if optimal_price <= 0:
                continue
            fees = optimal_price * 0.1325 + 0.30
            net = max(0.0, optimal_price - fees - (entry.get("avg_shipping") or 0))
            categories_data.append({
                "category": entry["category"],
                "optimal_price": optimal_price,
                "estimated_net": round(net, 2),
            })
        
        if not categories_data:
            return {"tree": [], "flat_categories": []}
        
        # Phase 1: Identify parent categories and relationships (batched)
        # Send only category names in batches to identify relationships
        category_names = [cat["category"] for cat in categories_data]
        
        # Batch category names (50 per batch to stay under token limits)
        relationship_batch_size = 50
        all_relationships = []
        
        print(f"Building category tree for {len(category_names)} categories in batches of {relationship_batch_size}")
        
        # Create all batch tasks for parallel processing
        name_batches = list(_chunk_any(category_names, relationship_batch_size))
        batch_tasks = [
            self._identify_category_relationships(name_batch, batch_idx)
            for batch_idx, name_batch in enumerate(name_batches)
        ]
        
        print(f"Processing {len(batch_tasks)} relationship batches in parallel")
        
        # Process all batches in parallel
        batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)
        
        # Collect results
        for batch_result in batch_results:
            if isinstance(batch_result, Exception):
                print(f"Relationship batch raised exception: {batch_result}")
                continue
            if batch_result:
                all_relationships.extend(batch_result)
        
        # Phase 2: Build tree structure from relationships
        tree = self._build_tree_from_relationships(categories_data, all_relationships)
        
        return {
            "tree": tree,
            "flat_categories": categories_data,
        }

    async def _identify_category_relationships(self, category_names: List[str], batch_index: int) -> List[Dict[str, object]]:
        """Use DeepSeek to identify parent-child relationships for a batch of categories."""
        vehicle_info = f"{self.vehicle_year or ''} {self.vehicle_make or ''} {self.vehicle_model or ''}".strip()
        
        prompt = f"""You are organizing automotive parts categories into hierarchical relationships.

Vehicle: {vehicle_info if vehicle_info else 'Unknown'}

Categories to organize (batch {batch_index + 1}):
{json.dumps(category_names, indent=2)}

Your task:
1. Identify parent categories (e.g., "Engine", "Transmission", "Body Parts", "Interior", "Electrical", "Suspension")
2. Assign each category to a parent, or mark as standalone if it's a top-level category
3. Some categories might be children of other categories (e.g., "Engine Block" under "Engine", "Cylinder Head" under "Engine")
4. Maximum depth: 3 levels (parent -> child -> grandchild)
5. Create logical automotive groupings

Return JSON with this structure:
{{
  "relationships": [
    {{
      "category": "Engine Block",
      "parent": "Engine",
      "level": 2
    }},
    {{
      "category": "Engine",
      "parent": null,
      "level": 1
    }},
    {{
      "category": "Front Bumper",
      "parent": "Body Parts",
      "level": 2
    }},
    {{
      "category": "Body Parts",
      "parent": null,
      "level": 1
    }}
  ],
  "parent_categories": ["Engine", "Transmission", "Body Parts", "Interior", "Electrical"]
}}

Rules:
- Group related categories under logical automotive parent categories
- A category can only have one parent
- If a category name already suggests a parent (e.g., "Engine Block" clearly belongs to "Engine"), assign it
- Standalone categories should have parent: null and level: 1
- Return JSON only, no markdown or extra commentary."""
        
        try:
            response = await self.classifier._send_with_retry({
                "model": self.classifier.deepseek_model,
                "temperature": 0.3,
                "max_tokens": 3000,
                "messages": [{"role": "user", "content": prompt}],
            })
            
            text = _extract_text_blocks(response)
            parsed = _extract_json_from_text(text)
            
            if parsed and "relationships" in parsed:
                relationships = parsed["relationships"]
                print(f"Batch {batch_index + 1}: Identified {len(relationships)} relationships")
                return relationships
            else:
                print(f"Warning: Batch {batch_index + 1} missing relationships, using flat structure")
                # Return flat structure as fallback
                return [{"category": name, "parent": None, "level": 1} for name in category_names]
        except Exception as exc:
            print(f"Error identifying relationships for batch {batch_index + 1}: {exc}")
            return [{"category": name, "parent": None, "level": 1} for name in category_names]

    def _build_tree_from_relationships(
        self, 
        categories_data: List[Dict[str, object]], 
        relationships: List[Dict[str, object]]
    ) -> List[Dict[str, object]]:
        """Build tree structure from relationships and category data."""
        # Create lookup maps
        category_map = {cat["category"]: cat for cat in categories_data}
        relationship_map = {rel["category"]: rel for rel in relationships}
        
        # Build tree structure
        tree_nodes = {}  # name -> node dict
        root_nodes = []
        
        # First pass: create all nodes
        for cat_data in categories_data:
            cat_name = cat_data["category"]
            rel = relationship_map.get(cat_name, {"parent": None, "level": 1})
            
            node = {
                "name": cat_name,
                "original_category": cat_name,
                "value": cat_data.get("estimated_net", 0),
                "optimal_price": cat_data.get("optimal_price", 0),
                "children": [],
                "parent": rel.get("parent"),
                "level": rel.get("level", 1),
            }
            tree_nodes[cat_name] = node
        
        # Second pass: build parent-child relationships
        for cat_name, node in tree_nodes.items():
            parent_name = node["parent"]
            if parent_name and parent_name in tree_nodes:
                # Add to parent's children
                tree_nodes[parent_name]["children"].append(node)
            else:
                # Root node
                root_nodes.append(node)
        
        # Third pass: calculate totals for parent nodes recursively
        def calculate_totals(node):
            if node["children"]:
                for child in node["children"]:
                    calculate_totals(child)
                total = sum(
                    child.get("total_value", child.get("value", 0)) 
                    for child in node["children"]
                )
                node["total_value"] = round(total, 2)
                node["type"] = "parent"
            else:
                node["type"] = "standalone"
                node["total_value"] = node.get("value", 0)
        
        for root in root_nodes:
            calculate_totals(root)
        
        # Sort by total value (descending)
        root_nodes.sort(key=lambda n: n.get("total_value", n.get("value", 0)), reverse=True)
        
        # Sort children within each parent
        def sort_children(node):
            if node["children"]:
                node["children"].sort(key=lambda n: n.get("total_value", n.get("value", 0)), reverse=True)
                for child in node["children"]:
                    sort_children(child)
        
        for root in root_nodes:
            sort_children(root)
        
        print(f"Built tree with {len(root_nodes)} root nodes")
        return root_nodes

    async def _group_categories(self, category_summary: List[Dict[str, object]], kept_listings: List[Listing]) -> List[Dict[str, object]]:
        """Group categories logically using DeepSeek - no duplicates per group (e.g., car can't have two engines)"""
        if not category_summary:
            return []
        
        # Prepare category data for grouping
        categories_data = []
        for entry in category_summary:
            if entry.get("optimal_price", 0) > 0:
                categories_data.append({
                    "category": entry["category"],
                    "optimal_price": entry.get("optimal_price", 0),
                    "min_price": entry.get("min_price", 0),
                    "max_price": entry.get("max_price", 0),
                })
        
        if not categories_data:
            return []
        
        vehicle_info = f"{self.vehicle_year or ''} {self.vehicle_make or ''} {self.vehicle_model or ''}".strip()
        
        prompt = f"""You are organizing automotive parts into logical groups for a part-out analysis.

Vehicle: {vehicle_info if vehicle_info else 'Unknown'}

Categories to group:
{json.dumps([cat["category"] for cat in categories_data], indent=2)}

CRITICAL RULES:
1. A car CANNOT have duplicate or alternative versions of the same part - these MUST go in SEPARATE groups
   - Example: "Left side mirror assembly" and "Left side mirror with turn signal" are ALTERNATIVES - put in different groups
   - Example: "Base engine" and "Turbo engine" are ALTERNATIVES - put in different groups
   - Example: "Standard headlight" and "LED headlight" are ALTERNATIVES - put in different groups
2. Each group should contain parts that can coexist on the same vehicle simultaneously
3. If two categories are variants/alternatives of the same part (same location, same function, different specs), they go in DIFFERENT groups
4. Only group parts that are truly different parts that can be on the same car (e.g., front bumper + rear bumper + hood can be together)
5. Variants/alternatives should be separated:
   - Different trim levels (Base vs Premium)
   - Different options (Standard vs With Turn Signal)
   - Different specifications (2.0L vs 2.5L engine)
   - Different styles (Standard vs Sport)

Return JSON with this structure:
{{
  "groups": [
    {{
      "group_id": 1,
      "group_name": "Base Model Engine Group",
      "categories": ["Engine Block", "Cylinder Head", "Oil Pan"]
    }},
    {{
      "group_id": 2,
      "group_name": "Turbo Engine Group",
      "categories": ["Turbo Engine", "Turbocharger", "Intercooler"]
    }},
    {{
      "group_id": 3,
      "group_name": "Left Side Mirror - Standard",
      "categories": ["Left side mirror assembly"]
    }},
    {{
      "group_id": 4,
      "group_name": "Left Side Mirror - With Turn Signal",
      "categories": ["Left side mirror with turn signal"]
    }},
    {{
      "group_id": 5,
      "group_name": "Body Parts Group",
      "categories": ["Front Bumper", "Rear Bumper", "Hood", "Trunk Lid"]
    }}
  ]
}}

Rules for naming:
- For variants/alternatives, use descriptive names that distinguish them (e.g., "Standard", "Premium", "With Turn Signal", "Base Model", "Turbo")
- For groups with multiple different parts, use descriptive names (e.g., "Body Parts Group", "Interior Parts Group")
- Be specific about what makes each group unique

Return JSON only, no markdown or extra commentary."""
        
        try:
            response = await self.classifier._send_with_retry({
                "model": self.classifier.deepseek_model,
                "temperature": 0.3,
                "max_tokens": 3000,
                "messages": [{"role": "user", "content": prompt}],
            })
            
            text = _extract_text_blocks(response)
            parsed = _extract_json_from_text(text)
            
            if parsed and "groups" in parsed:
                groups = parsed["groups"]
                print(f"Grouped {len(categories_data)} categories into {len(groups)} groups")
                
                # Enrich groups with category data, calculate profits, and include items
                enriched_groups = []
                category_map = {cat["category"]: cat for cat in categories_data}
                
                # Map listings by category for easy lookup
                listings_by_category: Dict[str, List[Listing]] = {}
                for listing in kept_listings:
                    if listing.category and listing.category != "Uncategorised":
                        listings_by_category.setdefault(listing.category, []).append(listing)
                
                for group in groups:
                    group_categories = []
                    group_items: List[Dict[str, object]] = []
                    min_profit = 0.0
                    max_profit = 0.0
                    min_total_price = 0.0
                    max_total_price = 0.0
                    
                    for cat_name in group.get("categories", []):
                        if cat_name in category_map:
                            cat_data = category_map[cat_name]
                            group_categories.append(cat_data)
                            
                            # Calculate profit (price - fees - shipping)
                            min_price = cat_data.get("min_price", 0)
                            max_price = cat_data.get("max_price", 0)
                            
                            # Fees: 13.25% + $0.30
                            min_fees = min_price * 0.1325 + 0.30
                            max_fees = max_price * 0.1325 + 0.30
                            
                            # Assume shipping is included in avg_shipping or estimate
                            min_net = max(0.0, min_price - min_fees)
                            max_net = max(0.0, max_price - max_fees)
                            
                            min_total_price += min_price
                            max_total_price += max_price
                            min_profit += min_net
                            max_profit += max_net
                            
                            # Add items for this category to the group
                            if cat_name in listings_by_category:
                                for listing in listings_by_category[cat_name]:
                                    group_items.append(listing.to_dict())
                    
                    enriched_groups.append({
                        "group_id": group.get("group_id"),
                        "group_name": group.get("group_name", f"Group {group.get('group_id', 0)}"),
                        "categories": group_categories,
                        "category_names": group.get("categories", []),
                        "items": group_items,  # Add items to each group
                        "item_count": len(group_items),
                        "min_total_price": round(min_total_price, 2),
                        "max_total_price": round(max_total_price, 2),
                        "min_profit": round(min_profit, 2),
                        "max_profit": round(max_profit, 2),
                        "category_count": len(group_categories),
                    })
                
                return enriched_groups
            else:
                print("Warning: DeepSeek response missing groups, creating single group")
                # Fallback: create one group with all categories
            # Fallback: create one group with all categories and items
            listings_by_category: Dict[str, List[Listing]] = {}
            for listing in kept_listings:
                if listing.category and listing.category != "Uncategorised":
                    listings_by_category.setdefault(listing.category, []).append(listing)
            
            all_items: List[Dict[str, object]] = []
            for cat in categories_data:
                cat_name = cat["category"]
                if cat_name in listings_by_category:
                    for listing in listings_by_category[cat_name]:
                        all_items.append(listing.to_dict())
            
            return [{
                "group_id": 1,
                "group_name": "All Parts Group",
                "categories": categories_data,
                "category_names": [cat["category"] for cat in categories_data],
                "items": all_items,
                "item_count": len(all_items),
                "min_total_price": round(sum(cat.get("min_price", 0) for cat in categories_data), 2),
                "max_total_price": round(sum(cat.get("max_price", 0) for cat in categories_data), 2),
                "min_profit": round(sum(max(0.0, cat.get("min_price", 0) - (cat.get("min_price", 0) * 0.1325 + 0.30)) for cat in categories_data), 2),
                "max_profit": round(sum(max(0.0, cat.get("max_price", 0) - (cat.get("max_price", 0) * 0.1325 + 0.30)) for cat in categories_data), 2),
                "category_count": len(categories_data),
            }]
        except Exception as exc:
            print(f"Error grouping categories: {exc}")
            # Fallback: create one group with all categories
            # Fallback: create one group with all categories and items
            listings_by_category: Dict[str, List[Listing]] = {}
            for listing in kept_listings:
                if listing.category and listing.category != "Uncategorised":
                    listings_by_category.setdefault(listing.category, []).append(listing)
            
            all_items: List[Dict[str, object]] = []
            for cat in categories_data:
                cat_name = cat["category"]
                if cat_name in listings_by_category:
                    for listing in listings_by_category[cat_name]:
                        all_items.append(listing.to_dict())
            
            return [{
                "group_id": 1,
                "group_name": "All Parts Group",
                "categories": categories_data,
                "category_names": [cat["category"] for cat in categories_data],
                "items": all_items,
                "item_count": len(all_items),
                "min_total_price": round(sum(cat.get("min_price", 0) for cat in categories_data), 2),
                "max_total_price": round(sum(cat.get("max_price", 0) for cat in categories_data), 2),
                "min_profit": round(sum(max(0.0, cat.get("min_price", 0) - (cat.get("min_price", 0) * 0.1325 + 0.30)) for cat in categories_data), 2),
                "max_profit": round(sum(max(0.0, cat.get("max_price", 0) - (cat.get("max_price", 0) * 0.1325 + 0.30)) for cat in categories_data), 2),
                "category_count": len(categories_data),
            }]

    async def _generate_part_out_summary(self, category_summary: List[Dict[str, object]], kept_listings: List[Listing]) -> Dict[str, object]:
        parts = []
        total_net = 0.0
        for entry in category_summary:
            optimal_price = entry.get("optimal_price") or 0
            if optimal_price <= 0:
                continue
            fees = optimal_price * 0.1325 + 0.30
            net = max(0.0, optimal_price - fees - (entry.get("avg_shipping") or 0))
            parts.append(
                {
                    "category": entry["category"],
                    "optimal_price": optimal_price,
                    "min_price": entry.get("min_price", 0),
                    "max_price": entry.get("max_price", 0),
                    "estimated_net": round(net, 2),
                    "recommendation": entry.get("recommendation"),
                }
            )
            total_net += net
            print(
                f"Part-out calc: category={entry['category']}, optimal_price={optimal_price}, estimated_net={round(net, 2)}"
            )

        parts.sort(key=lambda p: p["estimated_net"], reverse=True)

        return {
            "total_categories": len(parts),
            "estimated_total_net": round(total_net, 2),
            "top_parts": parts[:10],
            "recommendation": (
                "Part-out is financially attractive" if total_net >= 1000 else "Part-out returns are modest"
            ),
        }

    def _generate_seller_report(self, sold_listings: List[Listing]) -> Dict[str, object]:
        seller_stats: Dict[str, Dict[str, object]] = {}
        for listing in sold_listings:
            seller = listing.seller or "Unknown"
            if seller not in seller_stats:
                seller_stats[seller] = {
                    "sold_count": 0,
                    "gross_revenue": 0.0,
                    "listings": [],
                }
            seller_stats[seller]["sold_count"] += 1
            if listing.price:
                seller_stats[seller]["gross_revenue"] += listing.price
            seller_stats[seller]["listings"].append(listing.title)
        print(f"Seller report: aggregated {len(seller_stats)} sellers")

        sellers = []
        for seller, stats in seller_stats.items():
            sellers.append(
                {
                    "seller": seller,
                    "parts_sold": stats["sold_count"],
                    "gross_revenue": round(stats["gross_revenue"], 2),
                    "sample_listings": stats["listings"][:5],
                }
            )

        sellers.sort(key=lambda s: s["gross_revenue"], reverse=True)
        
        return {
            "total_unique_sellers": len(sellers),
            "top_sellers": sellers[:10],
            "total_gross_revenue": round(sum(s["gross_revenue"] for s in sellers), 2),
        }

    def _generate_competition_report(self, listings: List[Listing]) -> Dict[str, object]:
        sellers = Counter((listing.seller or "Unknown") for listing in listings if listing.keep)
        active_count = sum(1 for listing in listings if listing.listing_type == "active" and listing.keep)
        sold_count = sum(1 for listing in listings if listing.listing_type == "sold" and listing.keep)

        market_shares = [count / max(1, active_count + sold_count) * 100 for count in sellers.values() if count]
        hhi = sum(share ** 2 for share in market_shares)
        print(f"Competition report: active={active_count}, sold={sold_count}, HHI={round(hhi,2)}")

        return {
            "total_active_listings": active_count,
            "total_sold_listings": sold_count,
            "total_unique_sellers": len(sellers),
            "hhi": round(hhi, 2),
            "top_sellers_by_volume": sellers.most_common(10),
            "active_to_sold_ratio": round(active_count / max(1, sold_count), 2) if sold_count else float("inf"),
        }

    def _generate_price_distribution(self, listings: List[Listing]) -> Dict[str, object]:
        prices = [listing.price for listing in listings if listing.price]
        prices = [price for price in prices if price and price > 0]
        if not prices:
            return {"count": 0}

        sorted_prices = sorted(prices)
        n = len(sorted_prices)
        
        def percentile(p: float) -> float:
            index = int(n * p)
            index = min(max(index, 0), n - 1)
            return sorted_prices[index]

        distribution_ranges = [
            (0, 25, "$0-$25"),
            (25, 50, "$25-$50"),
            (50, 100, "$50-$100"),
            (100, 200, "$100-$200"),
            (200, 500, "$200-$500"),
            (500, 1000, "$500-$1,000"),
            (1000, float("inf"), "$1,000+"),
        ]

        buckets = []
        for lower, upper, label in distribution_ranges:
            count = len([price for price in prices if lower <= price < upper])
            buckets.append({"range": label, "count": count, "percentage": round(count / n * 100, 2)})
        print(f"Price distribution: count={n}, min={round(sorted_prices[0],2)}, max={round(sorted_prices[-1],2)}")
        
        return {
            "count": n,
            "min": round(sorted_prices[0], 2),
            "max": round(sorted_prices[-1], 2),
            "mean": round(statistics.mean(prices), 2),
            "median": round(statistics.median(prices), 2),
            "p25": round(percentile(0.25), 2),
            "p75": round(percentile(0.75), 2),
            "distribution": buckets,
        }

    def _build_dropped_summary(self, listings: List[Listing]) -> List[Dict[str, object]]:
        reason_counter = Counter(
            (listing.classification_reason or "No reason provided").strip() for listing in listings
        )
        return [
            {"reason": reason, "count": count}
            for reason, count in reason_counter.most_common(10)
        ]


    async def _build_report(
        self,
        *,
        active_raw: List[Listing],
        sold_raw: List[Listing],
        active_kept: List[Listing],
        sold_kept: List[Listing],
        kept_listings: List[Listing],
        dropped_listings: List[Listing],
        classification_batches: List[Dict[str, object]],
        duration: float,
    ) -> Dict[str, object]:
        category_summary = self._build_category_summary(kept_listings)
        print(f"_build_report: category_summary_count={len(category_summary)}")
        part_out_summary = await self._generate_part_out_summary(category_summary, kept_listings)
        print(f"_build_report: part_out_estimated_total={part_out_summary.get('estimated_total_net', 0)}")
        seller_report = self._generate_seller_report([listing for listing in sold_kept if listing.keep])
        print(f"_build_report: total_sellers={seller_report.get('total_unique_sellers', 0)}")
        competition_report = self._generate_competition_report(kept_listings)
        print(f"_build_report: competition_hhi={competition_report.get('hhi')}")
        price_distribution = self._generate_price_distribution(kept_listings)
        print(f"_build_report: price_distribution_count={price_distribution.get('count', 0)}")

        report = {
            "query": self.query,
            "category_id": self.category_id,
            "scraped_at": datetime.now(timezone.utc).isoformat(),
            "vehicle_info": {
                "year": str(self.vehicle_year) if self.vehicle_year else None,
                "make": self.vehicle_make,
                "model": self.vehicle_model,
            },
            "part_name": self.part_name,
            "metadata": {
                "items_per_page": self.items_per_page,
                "max_pages": self.max_pages,
                "pages_fetched": self.pages_fetched,
                "request_count": self.request_count,
                "duration_seconds": round(duration, 2),
            },
            "counts": {
                "raw": {
                    "active": len(active_raw),
                    "sold": len(sold_raw),
                    "total": len(active_raw) + len(sold_raw),
                },
                "kept": {
                    "active": len(active_kept),
                    "sold": len(sold_kept),
                    "total": len(kept_listings),
                },
                "dropped": len(dropped_listings),
            },
            "stats": {
                "active": self._compute_stats(active_kept),
                "sold": self._compute_stats(sold_kept),
                "combined": self._compute_stats(kept_listings),
            },
            "classification": {
                "dropped_summary": self._build_dropped_summary(dropped_listings),
                # "raw_batches": classification_batches,
            },
            "category_analysis": category_summary,
            "top_opportunities": category_summary[:5],
            "part_out_summary": part_out_summary,
            "seller_report": seller_report,
            "competition": competition_report,
            "price_distribution": price_distribution,
            "kept_listings": [listing.to_dict() for listing in kept_listings[:30]],
            "dropped_listings": [listing.to_dict() for listing in dropped_listings[:30]],
        }
        return report

    def _save_report(self, report: Dict[str, object]) -> None:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        safe_query = re.sub(r"[^a-zA-Z0-9_-]+", "_", self.query.strip()) or "report"
        filename = f"bee_ai_report_{safe_query}_{timestamp}.json"
        with open(filename, "w", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2)
        report["report_file"] = filename

    @staticmethod
    def _compute_stats(listings: Iterable[Listing]) -> Dict[str, object]:
        listing_list = list(listings)
        if not listing_list:
            return {
                "count": 0,
                "avg_price": None,
                "median_price": None,
                "min_price": None,
                "max_price": None,
                "free_shipping_count": 0,
            }

        prices = [listing.price for listing in listing_list if listing.price is not None]
        price_stats = {
            "count": len(listing_list),
            "avg_price": round(statistics.mean(prices), 2) if prices else None,
            "median_price": round(statistics.median(prices), 2) if prices else None,
            "min_price": round(min(prices), 2) if prices else None,
            "max_price": round(max(prices), 2) if prices else None,
            "free_shipping_count": sum(
                1
                for listing in listing_list
                if listing.shipping == 0 or listing.shipping is None
            ),
        }
        return price_stats

    async def scrape(self) -> Dict[str, object]:
        start_time = time.time()
        print(f"Starting ScrapingBee AI scrape for query='{self.query}' (category={self.category_id})")
        
        try:
            active_listings = await self._collect_listings("active")
            print(f"Found {len(active_listings)} active listings")
            sold_listings = await self._collect_listings("sold")
            print(f"Found {len(sold_listings)} sold listings")
            combined_listings = active_listings + sold_listings
            print(f"Combined {len(combined_listings)} total listings before deduplication")
            
            # Filter duplicates before classification
            combined_listings = self._deduplicate_listings(combined_listings)
            print(f"After deduplication: {len(combined_listings)} unique listings")
            
            classification_result = {
                "classified_listings": [],
                "raw_batches": [],
            }

            if combined_listings:
                try:
                    print(
                        f"Classifying {len(combined_listings)} listings using embedding-based matching"
                    )
                    classification_result = await self.classifier.classify(self.query, combined_listings)
                    self._apply_classification(
                        combined_listings, classification_result.get("classified_listings", [])
                    )
                    print(
                        f"Classification complete: received {len(classification_result.get('classified_listings', []))} entries"
                    )
                    if not classification_result.get("classified_listings"):
                        print("Warning: Embedding matcher returned zero classified listings; keeping all items by default.")
                    
                    # Category merging not needed - listings are already categorized to parts.txt categories
                except Exception as exc:
                    print("DeepSeek classification failed: %s", exc)
                    print("Proceeding with all listings marked as relevant.")

            duration = time.time() - start_time

            active_kept = [listing for listing in active_listings if listing.keep]
            sold_kept = [listing for listing in sold_listings if listing.keep]
            kept_listings = [listing for listing in combined_listings if listing.keep]
            dropped_listings = [listing for listing in combined_listings if not listing.keep]

            report = await self._build_report(
                active_raw=active_listings,
                sold_raw=sold_listings,
                active_kept=active_kept,
                sold_kept=sold_kept,
                kept_listings=kept_listings,
                dropped_listings=dropped_listings,
                classification_batches=classification_result.get("raw_batches", []),
                duration=duration,
            )

            print(
                "Scraping complete: active=%s/%s kept, sold=%s/%s kept, duration=%ss",
                len(active_kept),
                len(active_listings),
                len(sold_kept),
                len(sold_listings),
                round(duration, 2),
            )

            # self._save_report(report)
            return report
        finally:
            # Properly close the aiohttp session and DeepSeek client
            # Close DeepSeek client first (it uses httpx internally)
            await self._close_async_clients()
    
    async def _close_async_clients(self):
        """Close all async clients properly before event loop closes"""
        # Close classifier's DeepSeek client
        if hasattr(self, 'classifier') and self.classifier:
            if hasattr(self.classifier, 'deepseek_client') and self.classifier.deepseek_client:
                try:
                    # Check if event loop is still running
                    try:
                        loop = asyncio.get_running_loop()
                        if loop and not loop.is_closed():
                            # Use asyncio.wait_for to ensure cleanup completes before timeout
                            await asyncio.wait_for(
                                self.classifier.deepseek_client.aclose(),
                                timeout=2.0
                            )
                    except RuntimeError:
                        # Event loop is closed or not running - can't close properly
                        pass
                    except asyncio.TimeoutError:
                        # Cleanup timed out - non-critical
                        pass
                except (RuntimeError, AttributeError) as e:
                    # Expected when event loop is closing
                    pass
                except Exception as e:
                    # Non-critical cleanup error
                    pass
            
            # Also close any other client in classifier if it exists
            if hasattr(self.classifier, 'client') and self.classifier.client:
                try:
                    try:
                        loop = asyncio.get_running_loop()
                        if loop and not loop.is_closed():
                            await asyncio.wait_for(
                                self.classifier.client.aclose(),
                                timeout=2.0
                            )
                    except RuntimeError:
                        pass
                    except asyncio.TimeoutError:
                        pass
                except (RuntimeError, AttributeError):
                    pass
                except Exception:
                    pass
        
        # Then close aiohttp session
        if hasattr(self, 'session') and self.session and not self.session.closed:
            try:
                try:
                    loop = asyncio.get_running_loop()
                    if loop and not loop.is_closed():
                        await asyncio.wait_for(
                            self.session.close(),
                            timeout=2.0
                        )
                except RuntimeError:
                    pass
                except asyncio.TimeoutError:
                    pass
            except (RuntimeError, AttributeError):
                pass
            except Exception:
                pass
        
        # Small delay to allow cleanup tasks to complete
        try:
            loop = asyncio.get_running_loop()
            if loop and not loop.is_closed():
                await asyncio.sleep(0.15)
        except RuntimeError:
            pass


def main() -> None:
    import argparse
    import pprint

    parser = argparse.ArgumentParser(description="Scrape eBay via ScrapingBee and analyse with DeepSeek")
    parser.add_argument("query", help="Search query to scrape")
    parser.add_argument("--pages", type=int, default=2, help="Maximum pages per listing type (default=10)")
    parser.add_argument("--items", type=int, default=240, help="Items per page (default=240)")
    parser.add_argument(
        "--batch-size",
        type=int,
        default=10,
        help="Number of listings to send to DeepSeek per batch (default=60)",
    )
    args = parser.parse_args()

    scraper = ScrapingBeeAIScraper(
        args.query,
        max_pages=args.pages,
        items_per_page=args.items,
        claude_batch_size=args.batch_size,
    )
    print(f"Scraping {args.query} with {args.pages} pages, {args.items} items per page, and {args.batch_size} batch size")
    report = asyncio.run(scraper.scrape())
    pprint.pprint(report["counts"])
    pprint.pprint(report["stats"])
    pprint.pprint(report.get("category_analysis", [])[:5])
    if report.get("report_file"):
        print(f"Report saved to: {report['report_file']}")


if __name__ == "__main__":
    main()

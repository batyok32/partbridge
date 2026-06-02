"""Main orchestrator - ties all components together."""

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional
from urllib.parse import quote

from .clients import DeepSeekClient, ScrapingBeeClient
from .config import Settings, get_settings
from .models import Listing, ListingType, ScraperMetrics
from .parsers import EbayParser
from .services import CategoryMerger, ListingClassifier, ReportBuilder

logger = logging.getLogger(__name__)


class EbayScraper:
    """
    Main orchestrator for eBay scraping with AI analysis.

    This class coordinates all components:
    - HTTP scraping via ScrapingBee
    - HTML parsing
    - AI classification
    - Category merging
    - Report generation
    """

    def __init__(
        self,
        query: str,
        category_id: int = 6030,
        max_pages: int = 50,
        items_per_page: int = 240,
        vehicle_year: Optional[int] = None,
        vehicle_make: Optional[str] = None,
        vehicle_model: Optional[str] = None,
        part_name: Optional[str] = None,
        settings: Optional[Settings] = None,
    ):
        """
        Initialize scraper.

        Args:
            query: Search query
            category_id: eBay category ID
            max_pages: Maximum pages to scrape
            items_per_page: Items per page
            vehicle_year: Vehicle year
            vehicle_make: Vehicle make
            vehicle_model: Vehicle model
            part_name: Part name
            settings: Configuration settings
        """
        self.query = query.strip()
        self.category_id = category_id
        self.max_pages = max_pages
        self.items_per_page = items_per_page
        self.vehicle_year = vehicle_year
        self.vehicle_make = vehicle_make
        self.vehicle_model = vehicle_model
        self.part_name = part_name
        self.settings = settings or get_settings()

        # Initialize metrics
        self.metrics = ScraperMetrics()

        # Initialize clients (will be created in context manager)
        self.scrapingbee: Optional[ScrapingBeeClient] = None
        self.deepseek: Optional[DeepSeekClient] = None

    async def __aenter__(self):
        """Async context manager entry."""
        self.scrapingbee = ScrapingBeeClient(
            settings=self.settings,
            metrics=self.metrics,
        )
        self.deepseek = DeepSeekClient(
            settings=self.settings,
            metrics=self.metrics,
        )

        await self.scrapingbee.__aenter__()
        await self.deepseek.__aenter__()

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.scrapingbee:
            await self.scrapingbee.close()
        if self.deepseek:
            await self.deepseek.close()

    async def scrape(self) -> Dict[str, Any]:
        """
        Execute full scraping workflow.

        Returns:
            Complete report dictionary
        """
        start_time = time.time()
        logger.info(f"Starting scrape for query='{self.query}' (category={self.category_id})")

        try:
            # Step 1: Scrape listings
            logger.info("Step 1: Scraping listings...")
            active_listings = await self._collect_listings(ListingType.ACTIVE)
            sold_listings = await self._collect_listings(ListingType.SOLD)
            all_listings = active_listings + sold_listings

            logger.info(
                f"Scraped {len(active_listings)} active, "
                f"{len(sold_listings)} sold = {len(all_listings)} total"
            )

            if not all_listings:
                logger.warning("No listings found!")
                return self._empty_report()

            # Step 2: Classify listings
            logger.info("Step 2: Classifying listings with AI...")
            classifier = ListingClassifier(
                deepseek_client=self.deepseek,
                settings=self.settings,
                metrics=self.metrics,
            )
            await classifier.classify_listings(self.query, all_listings)

            kept_listings = [l for l in all_listings if l.keep]
            logger.info(f"Classification: {len(kept_listings)}/{len(all_listings)} kept")

            # Step 3: Merge similar categories
            logger.info("Step 3: Merging similar categories...")
            vehicle_info = self._get_vehicle_info()
            merger = CategoryMerger(
                deepseek_client=self.deepseek,
                vehicle_info=vehicle_info,
                settings=self.settings,
                metrics=self.metrics,
            )
            await merger.merge_categories(all_listings)

            unique_categories = len(set(
                l.category for l in kept_listings
                if l.category and l.category != "Uncategorised"
            ))
            logger.info(f"Category merging complete: {unique_categories} unique categories")

            # Step 4: Generate report
            logger.info("Step 4: Generating report...")
            duration = time.time() - start_time
            self.metrics.duration_seconds = duration

            report = ReportBuilder.build_report(
                query=self.query,
                category_id=self.category_id,
                all_listings=all_listings,
                metrics=self.metrics,
                vehicle_year=self.vehicle_year,
                vehicle_make=self.vehicle_make,
                vehicle_model=self.vehicle_model,
                part_name=self.part_name,
            )

            logger.info(
                f"Scraping complete! Duration: {duration:.2f}s, "
                f"API calls: {self.metrics.total_api_calls}, "
                f"Cost: ${self.metrics.estimated_cost:.4f}"
            )

            return report

        except Exception as exc:
            logger.error(f"Scraping failed: {exc}", exc_info=True)
            self.metrics.add_error(str(exc))
            raise

    async def _collect_listings(self, listing_type: ListingType) -> List[Listing]:
        """
        Collect listings for a specific type (active or sold).

        Args:
            listing_type: Active or sold

        Returns:
            List of listings
        """
        all_listings: List[Listing] = []
        seen_ids: set[str] = set()

        logger.info(f"Collecting {listing_type.value} listings (max {self.max_pages} pages)...")

        # Build URLs for all pages
        page_urls = []
        for page in range(1, self.max_pages + 1):
            url = self._build_page_url(listing_type, page)
            wait_selector = "#srp-river-results" if page > 1 else ".srp-controls__count-heading"
            page_urls.append((url, wait_selector))

        # Fetch pages in parallel (with rate limiting in client)
        soups = await self.scrapingbee.fetch_pages_parallel(page_urls)

        # Parse all pages
        for page, soup in enumerate(soups, start=1):
            if soup is None:
                logger.warning(f"Failed to fetch {listing_type.value} page {page}")
                continue

            # Parse listings
            page_listings = EbayParser.parse_page(soup, page, listing_type)

            # Track unique listings
            new_items = 0
            for listing in page_listings:
                if listing.item_id not in seen_ids:
                    seen_ids.add(listing.item_id)
                    all_listings.append(listing)
                    new_items += 1

            logger.info(
                f"{listing_type.value.capitalize()} page {page}: "
                f"{len(page_listings)} found, {new_items} new (total: {len(all_listings)})"
            )

            # Early stopping if no new items
            if new_items == 0:
                logger.info(f"No new items on page {page}, stopping early")
                break

        # Update metrics
        self.metrics.pages_fetched[listing_type.value] = page

        logger.info(
            f"Collected {len(all_listings)} unique {listing_type.value} listings "
            f"from {self.metrics.pages_fetched[listing_type.value]} pages"
        )

        return all_listings

    def _build_page_url(self, listing_type: ListingType, page: int) -> str:
        """Build eBay search URL for a specific page."""
        base_url = f"https://www.ebay.com/sch/{self.category_id}/i.html"
        params = [
            f"_nkw={quote(self.query)}",
            f"_ipg={self.items_per_page}",
            "LH_ItemCondition=3000",  # Used condition
        ]

        if listing_type == ListingType.SOLD:
            params.extend(["LH_Sold=1", "LH_Complete=1", "rt=nc"])

        if page > 1:
            params.append(f"_pgn={page}")

        url = f"{base_url}?{'&'.join(params)}"

        # Ensure locale
        separator = "&" if "?" in url else "?"
        if "_ul=" not in url:
            url = f"{url}{separator}_ul=US"
            separator = "&"
        if "_fcid=" not in url:
            url = f"{url}{separator}_fcid=1"

        return url

    def _get_vehicle_info(self) -> str:
        """Get vehicle information string."""
        parts = []
        if self.vehicle_year:
            parts.append(str(self.vehicle_year))
        if self.vehicle_make:
            parts.append(self.vehicle_make)
        if self.vehicle_model:
            parts.append(self.vehicle_model)
        return " ".join(parts)

    def _empty_report(self) -> Dict[str, Any]:
        """Generate empty report when no listings found."""
        return ReportBuilder.build_report(
            query=self.query,
            category_id=self.category_id,
            all_listings=[],
            metrics=self.metrics,
            vehicle_year=self.vehicle_year,
            vehicle_make=self.vehicle_make,
            vehicle_model=self.vehicle_model,
            part_name=self.part_name,
        )


# Convenience function for easy usage
async def scrape_ebay(
    query: str,
    category_id: int = 6030,
    max_pages: int = 50,
    items_per_page: int = 240,
    **kwargs,
) -> Dict[str, Any]:
    """
    Convenience function to scrape eBay.

    Args:
        query: Search query
        category_id: eBay category ID
        max_pages: Maximum pages to scrape
        items_per_page: Items per page
        **kwargs: Additional arguments (vehicle_year, vehicle_make, etc.)

    Returns:
        Complete report dictionary

    Example:
        >>> report = await scrape_ebay("2010 Toyota Prius battery", max_pages=10)
    """
    async with EbayScraper(
        query=query,
        category_id=category_id,
        max_pages=max_pages,
        items_per_page=items_per_page,
        **kwargs,
    ) as scraper:
        return await scraper.scrape()

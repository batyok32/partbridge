"""
Compatibility layer for old bee_ai_scraper.py interface.

This module provides backward compatibility with the old ScrapingBeeAIScraper class.
"""

import asyncio
from typing import Any, Dict, Optional

from .orchestrator import EbayScraper


class ScrapingBeeAIScraper:
    """
    Compatibility wrapper for old ScrapingBeeAIScraper interface.

    This class maintains API compatibility with the old bee_ai_scraper.py
    while using the new modular architecture underneath.
    """

    def __init__(
        self,
        query: str,
        *,
        category_id: int = 6030,
        max_pages: int = 50,
        items_per_page: int = 240,
        claude_model: Optional[str] = None,
        claude_batch_size: int = 60,
        vehicle_year: Optional[int] = None,
        vehicle_make: Optional[str] = None,
        vehicle_model: Optional[str] = None,
        part_name: Optional[str] = None,
    ):
        """
        Initialize scraper with old interface.

        Args:
            query: Search query
            category_id: eBay category ID
            max_pages: Maximum pages to scrape
            items_per_page: Items per page
            claude_model: Model to use (ignored, uses settings)
            claude_batch_size: Batch size (ignored, uses settings)
            vehicle_year: Vehicle year
            vehicle_make: Vehicle make
            vehicle_model: Vehicle model
            part_name: Part name
        """
        self.query = query
        self.category_id = category_id
        self.max_pages = max_pages
        self.items_per_page = items_per_page
        self.vehicle_year = vehicle_year
        self.vehicle_make = vehicle_make
        self.vehicle_model = vehicle_model
        self.part_name = part_name

        # Create new scraper instance
        self._scraper = EbayScraper(
            query=query,
            category_id=category_id,
            max_pages=max_pages,
            items_per_page=items_per_page,
            vehicle_year=vehicle_year,
            vehicle_make=vehicle_make,
            vehicle_model=vehicle_model,
            part_name=part_name,
        )

    async def scrape(self) -> Dict[str, Any]:
        """
        Execute scraping with old interface.

        Returns:
            Report dictionary (compatible with old format)
        """
        async with self._scraper:
            return await self._scraper.scrape()


# Module-level function for direct compatibility
def main():
    """
    Main function for CLI compatibility.

    This maintains compatibility with the old command-line interface.
    """
    import argparse
    import pprint

    parser = argparse.ArgumentParser(description="Scrape eBay via ScrapingBee and analyse with DeepSeek")
    parser.add_argument("query", help="Search query to scrape")
    parser.add_argument("--pages", type=int, default=2, help="Maximum pages per listing type (default=2)")
    parser.add_argument("--items", type=int, default=240, help="Items per page (default=240)")
    parser.add_argument(
        "--batch-size",
        type=int,
        default=60,
        help="Number of listings to send to DeepSeek per batch (default=60)",
    )
    args = parser.parse_args()

    scraper = ScrapingBeeAIScraper(
        args.query,
        max_pages=args.pages,
        items_per_page=args.items,
        claude_batch_size=args.batch_size,
    )

    print(f"Scraping {args.query} with {args.pages} pages, {args.items} items per page")
    report = asyncio.run(scraper.scrape())

    # Print summary
    pprint.pprint(report.get("counts", {}))
    pprint.pprint(report.get("stats", {}))
    pprint.pprint(report.get("category_analysis", [])[:5])

    # Print metrics
    metrics = report.get("metrics", {})
    if metrics:
        print("\n=== Performance Metrics ===")
        print(f"Total API calls: {metrics.get('total_api_calls', 0)}")
        print(f"ScrapingBee calls: {metrics.get('scrapingbee_calls', 0)}")
        print(f"DeepSeek calls: {metrics.get('deepseek_calls', 0)}")
        print(f"DeepSeek tokens: {metrics.get('deepseek_tokens_used', 0):,}")
        print(f"Estimated cost: ${metrics.get('estimated_cost', 0):.4f}")
        print(f"Duration: {metrics.get('duration_seconds', 0):.2f}s")


if __name__ == "__main__":
    main()

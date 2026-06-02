"""
Refactored eBay scraper with modular architecture.

This package provides a clean, maintainable alternative to the monolithic bee_ai_scraper.py

Usage:
    >>> from analytics.services.scraper_v2 import scrape_ebay
    >>> report = await scrape_ebay("2010 Toyota Prius parts", max_pages=10)

Or with more control:
    >>> from analytics.services.scraper_v2 import EbayScraper
    >>> async with EbayScraper(query="Tesla parts", max_pages=5) as scraper:
    ...     report = await scraper.scrape()
"""

__version__ = "2.0.0"

from .orchestrator import EbayScraper, scrape_ebay

__all__ = ["EbayScraper", "scrape_ebay"]

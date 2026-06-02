"""Data models for the scraper."""

from .listing import Listing, ListingType
from .classification import (
    ClassifiedListing,
    CategorySummary,
    CategoryMergeResult,
    CategoryGroup,
)
from .report import ScraperReport, ScraperMetrics, VehicleInfo

__all__ = [
    "Listing",
    "ListingType",
    "ClassifiedListing",
    "CategorySummary",
    "CategoryMergeResult",
    "CategoryGroup",
    "ScraperReport",
    "ScraperMetrics",
    "VehicleInfo",
]

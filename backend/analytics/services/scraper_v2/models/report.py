"""Report and metrics models."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ScraperMetrics(BaseModel):
    """Metrics tracked during scraping operation."""

    total_api_calls: int = Field(default=0, ge=0, description="Total API calls made")
    scrapingbee_calls: int = Field(default=0, ge=0, description="ScrapingBee API calls")
    deepseek_calls: int = Field(default=0, ge=0, description="DeepSeek API calls")
    deepseek_tokens_used: int = Field(default=0, ge=0, description="DeepSeek tokens consumed")
    estimated_cost: float = Field(default=0.0, ge=0, description="Estimated API cost in USD")
    duration_seconds: float = Field(default=0.0, ge=0, description="Total execution time")
    errors: List[str] = Field(default_factory=list, description="Errors encountered")
    pages_fetched: Dict[str, int] = Field(default_factory=dict, description="Pages fetched by type")

    def add_scrapingbee_call(self) -> None:
        """Track a ScrapingBee API call."""
        self.scrapingbee_calls += 1
        self.total_api_calls += 1

    def add_deepseek_call(self, tokens: int = 0, cost: float = 0.0) -> None:
        """Track a DeepSeek API call."""
        self.deepseek_calls += 1
        self.total_api_calls += 1
        self.deepseek_tokens_used += tokens
        self.estimated_cost += cost

    def add_error(self, error: str) -> None:
        """Add an error to the metrics."""
        self.errors.append(error)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "total_api_calls": self.total_api_calls,
            "scrapingbee_calls": self.scrapingbee_calls,
            "deepseek_calls": self.deepseek_calls,
            "deepseek_tokens_used": self.deepseek_tokens_used,
            "estimated_cost": round(self.estimated_cost, 4),
            "duration_seconds": round(self.duration_seconds, 2),
            "errors": self.errors,
            "pages_fetched": self.pages_fetched,
        }


class VehicleInfo(BaseModel):
    """Vehicle information for part-out analysis."""

    year: Optional[int] = Field(None, description="Vehicle year")
    make: Optional[str] = Field(None, description="Vehicle make")
    model: Optional[str] = Field(None, description="Vehicle model")


class ScraperReport(BaseModel):
    """Complete scraper report."""

    query: str = Field(..., description="Search query used")
    category_id: int = Field(..., description="eBay category ID")
    scraped_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat(), description="Timestamp")
    vehicle_info: Optional[VehicleInfo] = Field(None, description="Vehicle information")
    part_name: Optional[str] = Field(None, description="Part name")

    metadata: Dict[str, Any] = Field(default_factory=dict, description="Scraping metadata")
    counts: Dict[str, Any] = Field(default_factory=dict, description="Listing counts")
    stats: Dict[str, Any] = Field(default_factory=dict, description="Statistical data")
    classification: Dict[str, Any] = Field(default_factory=dict, description="Classification results")
    category_analysis: List[Dict[str, Any]] = Field(default_factory=list, description="Category summaries")
    top_opportunities: List[Dict[str, Any]] = Field(default_factory=list, description="Top opportunities")
    part_out_summary: Dict[str, Any] = Field(default_factory=dict, description="Part-out analysis")
    seller_report: Dict[str, Any] = Field(default_factory=dict, description="Seller statistics")
    competition: Dict[str, Any] = Field(default_factory=dict, description="Competition analysis")
    price_distribution: Dict[str, Any] = Field(default_factory=dict, description="Price distribution")
    kept_listings: List[Dict[str, Any]] = Field(default_factory=list, description="Kept listings sample")
    dropped_listings: List[Dict[str, Any]] = Field(default_factory=list, description="Dropped listings sample")
    metrics: Optional[ScraperMetrics] = Field(None, description="Performance metrics")

    class Config:
        arbitrary_types_allowed = True

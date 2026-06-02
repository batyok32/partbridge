"""Classification and category models."""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class ClassifiedListing(BaseModel):
    """AI-classified listing response schema."""

    id: str = Field(..., description="Item ID")
    keep: bool = Field(..., description="Whether to keep this listing")
    category: str = Field(..., description="Assigned category name")
    reason: str = Field(..., description="Classification reasoning")
    normalized_title: Optional[str] = Field(None, description="Cleaned title")
    price: Optional[str] = Field(None, description="Price as string")
    listing_type: Optional[str] = Field(None, description="Listing type")


class CategorySummary(BaseModel):
    """Summary statistics for a category."""

    category: str = Field(..., description="Category name")
    total_listings: int = Field(..., ge=0, description="Total listings in category")
    active_count: int = Field(..., ge=0, description="Active listings")
    sold_count: int = Field(..., ge=0, description="Sold listings")
    sell_through_rate: float = Field(..., ge=0, le=100, description="Sell-through percentage")
    demand_level: str = Field(..., description="high, medium, or low")
    competition_level: str = Field(..., description="high, medium, or low")
    opportunity_score: int = Field(..., ge=0, le=100, description="Opportunity score")
    optimal_price: float = Field(..., ge=0, description="Recommended price")
    min_price: float = Field(..., ge=0, description="Minimum price found")
    max_price: float = Field(..., ge=0, description="Maximum price found")
    avg_sold_price: float = Field(..., ge=0, description="Average sold price")
    avg_active_price: float = Field(..., ge=0, description="Average active price")
    avg_shipping: float = Field(..., ge=0, description="Average shipping cost")
    recommendation: str = Field(..., description="Textual recommendation")
    sample_titles: List[str] = Field(default_factory=list, description="Sample listing titles")
    image_url: Optional[str] = Field(None, description="Representative image")
    items: List[dict] = Field(default_factory=list, description="All items in category")
    item_count: int = Field(..., ge=0, description="Number of items")

    class Config:
        validate_assignment = True


class CategoryMergeResult(BaseModel):
    """Result of category merging operation."""

    canonical_name: str = Field(..., description="Main category name")
    variations: List[str] = Field(default_factory=list, description="Merged category names")
    reason: str = Field(..., description="Why these were merged")
    should_merge: bool = Field(..., description="Whether merge was successful")


class CategoryGroup(BaseModel):
    """Group of related categories."""

    group_id: int = Field(..., description="Unique group identifier")
    group_name: str = Field(..., description="Group display name")
    categories: List[dict] = Field(default_factory=list, description="Category data")
    category_names: List[str] = Field(default_factory=list, description="Category names")
    items: List[dict] = Field(default_factory=list, description="All items in group")
    item_count: int = Field(..., ge=0, description="Total items")
    min_total_price: float = Field(..., ge=0, description="Minimum total price")
    max_total_price: float = Field(..., ge=0, description="Maximum total price")
    min_profit: float = Field(..., ge=0, description="Minimum profit")
    max_profit: float = Field(..., ge=0, description="Maximum profit")
    category_count: int = Field(..., ge=0, description="Number of categories")

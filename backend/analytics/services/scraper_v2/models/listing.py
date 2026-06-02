"""Listing data model with Pydantic validation."""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, validator


class ListingType(str, Enum):
    """Type of eBay listing."""
    ACTIVE = "active"
    SOLD = "sold"


class Listing(BaseModel):
    """Represents an eBay listing with validation."""

    item_id: str = Field(..., description="Unique eBay item ID")
    title: str = Field(..., min_length=1, description="Listing title")
    price: Optional[float] = Field(None, ge=0, description="Item price in USD")
    url: str = Field(..., description="eBay listing URL")
    shipping: Optional[float] = Field(None, ge=0, description="Shipping cost")
    page: int = Field(..., ge=1, description="Page number where found")
    listing_type: ListingType = Field(..., description="Active or sold listing")
    raw_title: str = Field(default="", description="Original unprocessed title")
    keep: bool = Field(default=True, description="Whether to keep this listing")
    category: Optional[str] = Field(None, description="Assigned category")
    classification_reason: Optional[str] = Field(None, description="Why kept or dropped")
    seller: Optional[str] = Field(None, description="Seller username")
    seller_feedback: Optional[str] = Field(None, description="Seller feedback score")
    image_url: Optional[str] = Field(None, description="Product image URL")

    @validator("title", pre=True)
    def clean_title(cls, v: str) -> str:
        """Clean up title text."""
        if not v:
            return v
        # Remove extra whitespace
        return " ".join(v.split())

    @validator("raw_title", pre=True, always=True)
    def set_raw_title(cls, v: str, values: dict) -> str:
        """Set raw_title to title if not provided."""
        if not v and "title" in values:
            return values["title"]
        return v

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "item_id": self.item_id,
            "title": self.title,
            "price": self.price,
            "url": self.url,
            "shipping": self.shipping,
            "page": self.page,
            "listing_type": self.listing_type.value,
            "keep": self.keep,
            "category": self.category,
            "classification_reason": self.classification_reason,
            "seller": self.seller,
            "seller_feedback": self.seller_feedback,
            "image_url": self.image_url,
        }

    class Config:
        use_enum_values = True

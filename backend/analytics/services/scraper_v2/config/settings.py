"""Configuration settings."""

from __future__ import annotations

from functools import lru_cache
from typing import Optional

try:
    from pydantic_settings import BaseSettings
    from pydantic import Field
except ImportError:
    # Fallback for pydantic v1
    from pydantic import BaseSettings, Field


class Settings(BaseSettings):
    """Application settings with validation."""

    # API Keys
    SCRAPING_BEE_API_KEY: str = Field(..., env="SCRAPING_BEE_API_KEY")
    DEEPSEEK_API_KEY: str = Field(..., env="DEEPSEEK_API_KEY")

    # ScrapingBee Configuration
    SCRAPINGBEE_API_URL: str = Field(
        default="https://app.scrapingbee.com/api/v1",
        description="ScrapingBee API endpoint"
    )
    SCRAPINGBEE_DEFAULT_WAIT_MS: int = Field(
        default=8000,
        description="Default wait time in milliseconds"
    )
    SCRAPINGBEE_REQUEST_DELAY: float = Field(
        default=2.0,
        description="Delay between requests in seconds"
    )
    SCRAPINGBEE_MAX_CONCURRENT: int = Field(
        default=20,
        ge=1,
        le=50,
        description="Max concurrent ScrapingBee requests"
    )
    SCRAPINGBEE_COUNTRY_CODE: str = Field(
        default="us",
        description="Country code for requests"
    )

    # DeepSeek Configuration
    DEEPSEEK_API_URL: str = Field(
        default="https://api.deepseek.com/v1",
        description="DeepSeek API endpoint"
    )
    DEEPSEEK_MODEL: str = Field(
        default="deepseek-chat",
        description="DeepSeek model to use"
    )
    DEEPSEEK_BATCH_SIZE: int = Field(
        default=60,
        ge=1,
        le=100,
        description="Items per classification batch"
    )
    DEEPSEEK_MAX_CONCURRENT: int = Field(
        default=10,
        ge=1,
        le=20,
        description="Max concurrent DeepSeek requests"
    )
    DEEPSEEK_TEMPERATURE: float = Field(
        default=0.2,
        ge=0.0,
        le=2.0,
        description="Model temperature"
    )
    DEEPSEEK_MAX_TOKENS: int = Field(
        default=8000,
        ge=1000,
        le=16000,
        description="Max tokens per response"
    )
    DEEPSEEK_COST_PER_1M_TOKENS: float = Field(
        default=0.14,
        description="Cost per 1M tokens in USD"
    )

    # Retry Configuration
    MAX_RETRIES: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Maximum retry attempts"
    )
    RETRY_INITIAL_DELAY: float = Field(
        default=0.5,
        ge=0.1,
        description="Initial retry delay in seconds"
    )
    RETRY_MAX_DELAY: float = Field(
        default=6.0,
        ge=1.0,
        description="Maximum retry delay in seconds"
    )

    # Scraping Configuration
    DEFAULT_CATEGORY_ID: int = Field(
        default=6030,
        description="Default eBay category (Car & Truck Parts)"
    )
    DEFAULT_MAX_PAGES: int = Field(
        default=50,
        ge=1,
        description="Default max pages to scrape"
    )
    DEFAULT_ITEMS_PER_PAGE: int = Field(
        default=240,
        ge=1,
        description="Default items per page"
    )

    # Category Merging Configuration
    CATEGORY_MERGE_MAX_PHASES: int = Field(
        default=5,
        ge=1,
        le=10,
        description="Max category merge iterations"
    )
    CATEGORY_MERGE_TARGET: int = Field(
        default=100,
        ge=10,
        description="Target maximum categories after merge"
    )
    CATEGORY_SIMILARITY_THRESHOLD: float = Field(
        default=0.30,
        ge=0.0,
        le=1.0,
        description="Similarity threshold for merging"
    )

    # Cache Configuration
    ENABLE_CACHE: bool = Field(
        default=True,
        description="Enable response caching"
    )
    CACHE_TTL_SECONDS: int = Field(
        default=3600,
        ge=60,
        description="Cache time-to-live in seconds"
    )

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"  # Ignore extra fields for compatibility


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    try:
        return Settings()
    except Exception:
        # If settings fail to load (e.g., in testing), try Django settings
        try:
            from django.conf import settings as django_settings

            return Settings(
                SCRAPING_BEE_API_KEY=getattr(django_settings, "SCRAPING_BEE_API_KEY", ""),
                DEEPSEEK_API_KEY=getattr(django_settings, "DEEPSEEK_API_KEY", ""),
                DEEPSEEK_MODEL=getattr(django_settings, "DEEPSEEK_MODEL", "deepseek-chat"),
            )
        except ImportError:
            raise

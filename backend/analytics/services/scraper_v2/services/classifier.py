"""Listing classification service."""

import logging
from typing import List, Optional

from pydantic import ValidationError

from ..clients import DeepSeekClient
from ..config import PromptTemplates, Settings, get_settings
from ..models import ClassifiedListing, Listing, ScraperMetrics

logger = logging.getLogger(__name__)


class ListingClassifier:
    """
    Service for classifying listings using AI.
    """

    def __init__(
        self,
        deepseek_client: DeepSeekClient,
        settings: Optional[Settings] = None,
        metrics: Optional[ScraperMetrics] = None,
    ):
        """
        Initialize classifier.

        Args:
            deepseek_client: DeepSeek API client
            settings: Configuration settings
            metrics: Metrics tracker
        """
        self.deepseek = deepseek_client
        self.settings = settings or get_settings()
        self.metrics = metrics or ScraperMetrics()

    async def classify_listings(
        self,
        query: str,
        listings: List[Listing],
    ) -> List[Listing]:
        """
        Classify all listings, marking relevance and assigning categories.

        Args:
            query: Search query
            listings: List of listings to classify

        Returns:
            Updated listings with classification
        """
        if not listings:
            return []

        logger.info(f"Classifying {len(listings)} listings in batches of {self.settings.DEEPSEEK_BATCH_SIZE}")

        # Split into batches
        batches = self._chunk_listings(listings, self.settings.DEEPSEEK_BATCH_SIZE)

        # Process batches in parallel
        batch_prompts = [
            PromptTemplates.classification_prompt(
                query,
                [self._listing_to_dict(l) for l in batch]
            )
            for batch in batches
        ]

        batch_results = await self.deepseek.complete_batch(batch_prompts)

        # Apply classifications
        all_classifications = []
        for result in batch_results:
            classified = result.get("classified_listings", [])
            all_classifications.extend(classified)

        self._apply_classifications(listings, all_classifications)

        # Handle uncategorized items (retry with smaller batches)
        uncategorized = [l for l in listings if l.category == "Uncategorised" or not l.category]
        if uncategorized:
            logger.info(f"Retrying {len(uncategorized)} uncategorized listings...")
            await self._retry_uncategorized(query, uncategorized)

        kept_count = sum(1 for l in listings if l.keep)
        logger.info(f"Classification complete: {kept_count}/{len(listings)} kept")

        return listings

    @staticmethod
    def _chunk_listings(listings: List[Listing], size: int) -> List[List[Listing]]:
        """Split listings into chunks."""
        return [listings[i:i + size] for i in range(0, len(listings), size)]

    @staticmethod
    def _listing_to_dict(listing: Listing) -> dict:
        """Convert listing to dict for prompt."""
        # Handle listing_type - could be string or enum
        listing_type = listing.listing_type
        if hasattr(listing_type, 'value'):
            listing_type = listing_type.value

        return {
            "item_id": listing.item_id,
            "title": listing.title,
            "price": listing.price,
            "listing_type": listing_type,
        }

    def _apply_classifications(
        self,
        listings: List[Listing],
        classifications: List[dict],
    ) -> None:
        """Apply AI classifications to listings."""
        # Build lookup map
        classification_map = {str(c.get("id", "")): c for c in classifications}

        for listing in listings:
            classification = classification_map.get(listing.item_id)

            if not classification:
                # No classification found - mark as uncategorized
                listing.category = "Uncategorised"
                listing.keep = True
                listing.classification_reason = "Missing from AI response"
                continue

            # Validate and apply
            try:
                validated = ClassifiedListing(**classification)
                listing.keep = validated.keep
                listing.category = validated.category or "Uncategorised"
                listing.classification_reason = validated.reason

                if validated.normalized_title:
                    listing.title = validated.normalized_title

            except ValidationError as exc:
                logger.warning(f"Invalid classification for {listing.item_id}: {exc}")
                listing.category = "Uncategorised"
                listing.keep = True
                listing.classification_reason = "Invalid AI response"

    async def _retry_uncategorized(
        self,
        query: str,
        listings: List[Listing],
    ) -> None:
        """Retry classification for uncategorized items in smaller batches."""
        if not listings:
            return

        # Use smaller batches for retry
        retry_batch_size = 5
        batches = self._chunk_listings(listings, retry_batch_size)

        batch_prompts = [
            PromptTemplates.classification_prompt(
                query,
                [self._listing_to_dict(l) for l in batch]
            )
            for batch in batches
        ]

        batch_results = await self.deepseek.complete_batch(batch_prompts)

        # Apply retry classifications
        retry_classifications = []
        for result in batch_results:
            classified = result.get("classified_listings", [])
            retry_classifications.extend(classified)

        # Only update if we got a better category
        classification_map = {str(c.get("id", "")): c for c in retry_classifications}
        for listing in listings:
            classification = classification_map.get(listing.item_id)
            if classification and classification.get("category") and classification["category"] != "Uncategorised":
                try:
                    validated = ClassifiedListing(**classification)
                    listing.keep = validated.keep
                    listing.category = validated.category
                    listing.classification_reason = validated.reason
                    if validated.normalized_title:
                        listing.title = validated.normalized_title
                except ValidationError:
                    pass

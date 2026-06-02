"""Optimized category merger - reduces API calls from 100+ to <10."""

import logging
from collections import defaultdict
from typing import Dict, List, Optional, Set

from ..clients import DeepSeekClient
from ..config import PromptTemplates, Settings, get_settings
from ..models import CategoryMergeResult, Listing, ScraperMetrics
from ..utils import calculate_similarity, extract_core_part_name

logger = logging.getLogger(__name__)


class CategoryMerger:
    """
    Optimized category merger using smart grouping to minimize API calls.

    Key optimization: Group similar categories locally first, then send only
    ambiguous groups to AI for final decision. This reduces API calls from
    100+ to typically 5-10.
    """

    def __init__(
        self,
        deepseek_client: DeepSeekClient,
        vehicle_info: Optional[str] = None,
        settings: Optional[Settings] = None,
        metrics: Optional[ScraperMetrics] = None,
    ):
        """
        Initialize category merger.

        Args:
            deepseek_client: DeepSeek API client
            vehicle_info: Vehicle information string
            settings: Configuration settings
            metrics: Metrics tracker
        """
        self.deepseek = deepseek_client
        self.vehicle_info = vehicle_info or ""
        self.settings = settings or get_settings()
        self.metrics = metrics or ScraperMetrics()

    async def merge_categories(
        self,
        listings: List[Listing],
    ) -> Dict[str, str]:
        """
        Merge similar categories efficiently.

        Strategy:
        1. Local grouping by core part name (no AI needed)
        2. Identify ambiguous groups that need AI review
        3. Send only ambiguous groups to AI (5-10 calls instead of 100+)
        4. Apply merges

        Args:
            listings: Listings with assigned categories

        Returns:
            Mapping of original category -> canonical category
        """
        # Get unique categories
        unique_categories = self._get_unique_categories(listings)
        if len(unique_categories) < 2:
            logger.info("Less than 2 categories, no merging needed")
            return {}

        logger.info(f"Starting category merge for {len(unique_categories)} categories")

        merge_mapping: Dict[str, str] = {}

        # Phase 1: Local grouping by core part name (NO API CALLS)
        core_name_groups = self._group_by_core_name(unique_categories)
        logger.info(f"Phase 1: Grouped into {len(core_name_groups)} core name groups locally")

        # Phase 2: Identify ambiguous groups (need AI review)
        ambiguous_groups = self._identify_ambiguous_groups(core_name_groups)
        clear_groups = [g for g in core_name_groups.values() if len(g) > 1 and g not in ambiguous_groups]

        logger.info(
            f"Phase 2: {len(clear_groups)} clear merges (no AI needed), "
            f"{len(ambiguous_groups)} ambiguous groups (need AI review)"
        )

        # Apply clear merges immediately (no AI needed)
        for group in clear_groups:
            canonical = self._choose_canonical(group)
            for cat in group:
                if cat != canonical:
                    merge_mapping[cat] = canonical
                    logger.debug(f"Clear merge: '{cat}' → '{canonical}'")

        # Phase 3: Send only ambiguous groups to AI (5-10 API calls)
        if ambiguous_groups:
            ai_merge_mapping = await self._ai_merge_ambiguous(ambiguous_groups)
            merge_mapping.update(ai_merge_mapping)

        # Apply merges to listings
        self._apply_merges(listings, merge_mapping)

        # Check if we're under target
        final_categories = self._get_unique_categories(listings)
        logger.info(
            f"Merge complete: {len(unique_categories)} → {len(final_categories)} categories "
            f"(target: {self.settings.CATEGORY_MERGE_TARGET})"
        )

        # If still over target, do one more aggressive merge
        if len(final_categories) > self.settings.CATEGORY_MERGE_TARGET:
            logger.info(f"Still over target, doing aggressive merge...")
            additional_merges = await self._aggressive_merge(final_categories)
            merge_mapping.update(additional_merges)
            self._apply_merges(listings, additional_merges)

            final_categories = self._get_unique_categories(listings)
            logger.info(f"After aggressive merge: {len(final_categories)} categories")

        return merge_mapping

    def _get_unique_categories(self, listings: List[Listing]) -> List[str]:
        """Get unique category names, excluding Uncategorised."""
        return list(set(
            l.category for l in listings
            if l.category and l.category != "Uncategorised"
        ))

    def _group_by_core_name(self, categories: List[str]) -> Dict[str, List[str]]:
        """
        Group categories by core part name.

        Example: "Front bumper (black)" and "Front bumper (white)" both
        have core name "bumper" so they get grouped together.

        This is done locally, no API calls needed.
        """
        groups: Dict[str, List[str]] = defaultdict(list)

        for cat in categories:
            core = extract_core_part_name(cat)
            if core:
                groups[core].append(cat)
            else:
                # No core name found, put in its own group
                groups[cat].append(cat)

        return dict(groups)

    def _identify_ambiguous_groups(
        self,
        core_groups: Dict[str, List[str]]
    ) -> List[List[str]]:
        """
        Identify which groups need AI review.

        A group is ambiguous if:
        1. It has 2-4 items (not obviously the same)
        2. The items are not highly similar (< 70% similarity)

        Returns groups that need AI review.
        """
        ambiguous = []

        for core_name, categories in core_groups.items():
            if len(categories) == 1:
                # Single item, no ambiguity
                continue

            if len(categories) > 10:
                # Large group, likely clearly the same - apply simple merge
                continue

            # Check similarity within group
            max_similarity = 0.0
            for i, cat1 in enumerate(categories):
                for cat2 in categories[i+1:]:
                    sim = calculate_similarity(cat1, cat2)
                    max_similarity = max(max_similarity, sim)

            # If similarity is low, it's ambiguous - needs AI review
            if max_similarity < 0.7:
                ambiguous.append(categories)

        return ambiguous

    async def _ai_merge_ambiguous(
        self,
        ambiguous_groups: List[List[str]],
    ) -> Dict[str, str]:
        """
        Send ambiguous groups to AI for merge decision.

        This is where we save API calls: instead of sending every category
        pair, we only send groups that need clarification.
        """
        logger.info(f"Sending {len(ambiguous_groups)} ambiguous groups to AI...")

        merge_mapping: Dict[str, str] = {}

        # Build prompts for each ambiguous group
        prompts = [
            PromptTemplates.category_merge_prompt(group, phase=1, vehicle_info=self.vehicle_info)
            for group in ambiguous_groups
        ]

        # Send all in parallel
        results = await self.deepseek.complete_batch(prompts)

        # Process results
        for group, result in zip(ambiguous_groups, results):
            if not result:
                # AI call failed, use simple merge
                canonical = self._choose_canonical(group)
                for cat in group:
                    if cat != canonical:
                        merge_mapping[cat] = canonical
                continue

            should_merge = result.get("should_merge", False)
            canonical = result.get("canonical_name")
            variations = result.get("variations", [])

            if should_merge and canonical and variations:
                for var in variations:
                    if var != canonical and var in group:
                        merge_mapping[var] = canonical
                        logger.info(f"AI merge: '{var}' → '{canonical}'")
            else:
                # AI says don't merge, leave as-is
                logger.debug(f"AI decision: Don't merge {group}")

        return merge_mapping

    async def _aggressive_merge(
        self,
        categories: List[str],
    ) -> Dict[str, str]:
        """
        Aggressive merge when we're still over target.

        Send categories in larger batches with instructions to merge aggressively.
        """
        merge_mapping: Dict[str, str] = {}

        # Group remaining categories by keyword similarity
        similarity_groups = self._group_by_similarity(categories, threshold=0.25)

        # Send larger groups for aggressive merge
        large_groups = [g for g in similarity_groups if len(g) > 1]

        if not large_groups:
            return merge_mapping

        logger.info(f"Aggressive merge: {len(large_groups)} groups")

        prompts = [
            PromptTemplates.category_merge_prompt(group, phase=2, vehicle_info=self.vehicle_info)
            for group in large_groups
        ]

        results = await self.deepseek.complete_batch(prompts)

        for group, result in zip(large_groups, results):
            if not result:
                continue

            should_merge = result.get("should_merge", True)  # Default to merge
            canonical = result.get("canonical_name")
            variations = result.get("variations", [])

            if canonical and variations:
                for var in variations:
                    if var != canonical and var in group:
                        merge_mapping[var] = canonical

        return merge_mapping

    def _group_by_similarity(
        self,
        categories: List[str],
        threshold: float,
    ) -> List[List[str]]:
        """Group categories by string similarity."""
        groups: List[List[str]] = []
        used: Set[str] = set()

        for i, cat1 in enumerate(categories):
            if cat1 in used:
                continue

            group = [cat1]
            used.add(cat1)

            for cat2 in categories[i+1:]:
                if cat2 in used:
                    continue

                if calculate_similarity(cat1, cat2) >= threshold:
                    group.append(cat2)
                    used.add(cat2)

            groups.append(group)

        return groups

    @staticmethod
    def _choose_canonical(categories: List[str]) -> str:
        """Choose the best canonical name from a group (shortest, most common)."""
        if not categories:
            return ""
        # Choose shortest name (usually most general)
        return min(categories, key=len)

    @staticmethod
    def _apply_merges(
        listings: List[Listing],
        merge_mapping: Dict[str, str],
    ) -> None:
        """Apply merge mapping to listings."""
        for listing in listings:
            if listing.category in merge_mapping:
                old_category = listing.category
                listing.category = merge_mapping[old_category]
                logger.debug(f"Applied merge: {listing.item_id} '{old_category}' → '{listing.category}'")

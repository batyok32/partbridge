"""Report generation service."""

import logging
import statistics
from collections import Counter
from datetime import datetime, timezone
from typing import Any, Dict, List

from ..models import CategorySummary, Listing, ListingType, ScraperMetrics, ScraperReport, VehicleInfo

logger = logging.getLogger(__name__)


class ReportBuilder:
    """Service for building comprehensive scraper reports."""

    @staticmethod
    def build_report(
        query: str,
        category_id: int,
        all_listings: List[Listing],
        metrics: ScraperMetrics,
        vehicle_year: int | None = None,
        vehicle_make: str | None = None,
        vehicle_model: str | None = None,
        part_name: str | None = None,
    ) -> Dict[str, Any]:
        """
        Build comprehensive scraper report.

        Args:
            query: Search query
            category_id: eBay category ID
            all_listings: All scraped listings
            metrics: Performance metrics
            vehicle_year: Vehicle year
            vehicle_make: Vehicle make
            vehicle_model: Vehicle model
            part_name: Part name

        Returns:
            Complete report dictionary
        """
        kept_listings = [l for l in all_listings if l.keep]
        dropped_listings = [l for l in all_listings if not l.keep]

        active_all = [l for l in all_listings if l.listing_type == ListingType.ACTIVE]
        sold_all = [l for l in all_listings if l.listing_type == ListingType.SOLD]
        active_kept = [l for l in kept_listings if l.listing_type == ListingType.ACTIVE]
        sold_kept = [l for l in kept_listings if l.listing_type == ListingType.SOLD]

        # Build category analysis
        category_summary = ReportBuilder._build_category_summary(kept_listings)

        # Build various report sections
        part_out_summary = ReportBuilder._build_part_out_summary(category_summary)
        seller_report = ReportBuilder._build_seller_report(sold_kept)
        competition_report = ReportBuilder._build_competition_report(kept_listings)
        price_distribution = ReportBuilder._build_price_distribution(kept_listings)
        dropped_summary = ReportBuilder._build_dropped_summary(dropped_listings)

        report = ScraperReport(
            query=query,
            category_id=category_id,
            scraped_at=datetime.now(timezone.utc).isoformat(),
            vehicle_info=VehicleInfo(
                year=vehicle_year,
                make=vehicle_make,
                model=vehicle_model,
            ) if vehicle_year or vehicle_make or vehicle_model else None,
            part_name=part_name,
            metadata={
                "pages_fetched": metrics.pages_fetched,
                "duration_seconds": metrics.duration_seconds,
            },
            counts={
                "raw": {
                    "active": len(active_all),
                    "sold": len(sold_all),
                    "total": len(all_listings),
                },
                "kept": {
                    "active": len(active_kept),
                    "sold": len(sold_kept),
                    "total": len(kept_listings),
                },
                "dropped": len(dropped_listings),
            },
            stats={
                "active": ReportBuilder._compute_stats(active_kept),
                "sold": ReportBuilder._compute_stats(sold_kept),
                "combined": ReportBuilder._compute_stats(kept_listings),
            },
            classification={
                "dropped_summary": dropped_summary,
            },
            category_analysis=[cat.dict() for cat in category_summary],
            top_opportunities=[cat.dict() for cat in category_summary[:5]],
            part_out_summary=part_out_summary,
            seller_report=seller_report,
            competition=competition_report,
            price_distribution=price_distribution,
            kept_listings=[l.to_dict() for l in kept_listings[:30]],
            dropped_listings=[l.to_dict() for l in dropped_listings[:30]],
            metrics=metrics,
        )

        logger.info(f"Report built: {len(kept_listings)} kept, {len(category_summary)} categories")

        return report.dict()

    @staticmethod
    def _build_category_summary(listings: List[Listing]) -> List[CategorySummary]:
        """Build summary statistics for each category."""
        # Group by category
        grouped: Dict[str, List[Listing]] = {}
        for listing in listings:
            category = listing.category or "Uncategorised"
            grouped.setdefault(category, []).append(listing)

        summaries = []
        for category, cat_listings in grouped.items():
            active = [l for l in cat_listings if l.listing_type == ListingType.ACTIVE and l.price]
            sold = [l for l in cat_listings if l.listing_type == ListingType.SOLD and l.price]

            active_count = len(active)
            sold_count = len(sold)
            total_count = len(cat_listings)

            sell_through = (
                (sold_count / (sold_count + active_count) * 100)
                if (sold_count + active_count) > 0
                else 0
            )

            sold_prices = [l.price for l in sold if l.price is not None]
            active_prices = [l.price for l in active if l.price is not None]
            all_prices = sold_prices + active_prices

            optimal_price = statistics.median(sold_prices) if sold_prices else 0.0
            avg_sold_price = statistics.mean(sold_prices) if sold_prices else 0.0
            avg_active_price = statistics.mean(active_prices) if active_prices else 0.0
            min_price = min(all_prices) if all_prices else 0.0
            max_price = max(all_prices) if all_prices else 0.0

            shipping_values = [l.shipping for l in sold if l.shipping]
            avg_shipping = statistics.mean(shipping_values) if shipping_values else 0.0

            demand_level = "high" if sold_count >= 10 else "medium" if sold_count >= 5 else "low"
            competition_level = "high" if active_count >= 30 else "medium" if active_count >= 15 else "low"

            opportunity_score = ReportBuilder._calculate_opportunity_score(
                sold_count, active_count, optimal_price
            )
            recommendation = ReportBuilder._category_recommendation(
                opportunity_score, sell_through, demand_level
            )

            # Get representative image
            image_url = next((l.image_url for l in cat_listings if l.image_url), None)

            summaries.append(CategorySummary(
                category=category,
                total_listings=total_count,
                active_count=active_count,
                sold_count=sold_count,
                sell_through_rate=round(sell_through, 2),
                demand_level=demand_level,
                competition_level=competition_level,
                opportunity_score=opportunity_score,
                optimal_price=round(optimal_price, 2),
                min_price=round(min_price, 2),
                max_price=round(max_price, 2),
                avg_sold_price=round(avg_sold_price, 2),
                avg_active_price=round(avg_active_price, 2),
                avg_shipping=round(avg_shipping, 2),
                recommendation=recommendation,
                sample_titles=[l.title for l in cat_listings[:10]],
                image_url=image_url,
                items=[l.to_dict() for l in cat_listings],
                item_count=len(cat_listings),
            ))

        # Sort by opportunity score
        summaries.sort(key=lambda s: s.opportunity_score, reverse=True)
        return summaries

    @staticmethod
    def _calculate_opportunity_score(sold_count: int, active_count: int, optimal_price: float) -> int:
        """Calculate opportunity score (0-100)."""
        score = 0

        # Demand component (40 points)
        if sold_count >= 20:
            score += 40
        elif sold_count >= 10:
            score += 35
        elif sold_count >= 5:
            score += 25
        elif sold_count >= 3:
            score += 15
        elif sold_count >= 1:
            score += 5

        # Competition component (30 points)
        if active_count == 0:
            score += 30
        elif active_count < 5:
            score += 30
        elif active_count < 10:
            score += 25
        elif active_count < 15:
            score += 20
        elif active_count < 25:
            score += 15
        elif active_count < 50:
            score += 10
        elif active_count < 100:
            score += 5

        # Price component (30 points)
        if optimal_price >= 500:
            score += 30
        elif optimal_price >= 200:
            score += 25
        elif optimal_price >= 100:
            score += 20
        elif optimal_price >= 50:
            score += 15
        elif optimal_price >= 25:
            score += 10
        elif optimal_price >= 10:
            score += 5

        return min(100, max(0, score))

    @staticmethod
    def _category_recommendation(score: int, sell_through: float, demand_level: str) -> str:
        """Generate recommendation text."""
        if score >= 70 and sell_through >= 50:
            return "Excellent opportunity – strong demand and manageable competition."
        if score >= 50 and sell_through >= 30:
            return "Good opportunity – consider prioritising this category."
        if score >= 35:
            return "Moderate opportunity – list selectively and monitor competition."
        if demand_level == "low":
            return "Low demand – only list if acquisition cost is minimal."
        return "Limited opportunity – focus effort elsewhere unless inventory is on hand."

    @staticmethod
    def _build_part_out_summary(category_summaries: List[CategorySummary]) -> Dict[str, Any]:
        """Build part-out financial summary."""
        parts = []
        total_net = 0.0

        for summary in category_summaries:
            if summary.optimal_price <= 0:
                continue

            fees = summary.optimal_price * 0.1325 + 0.30
            net = max(0.0, summary.optimal_price - fees - summary.avg_shipping)

            parts.append({
                "category": summary.category,
                "optimal_price": summary.optimal_price,
                "min_price": summary.min_price,
                "max_price": summary.max_price,
                "estimated_net": round(net, 2),
                "recommendation": summary.recommendation,
            })

            total_net += net

        parts.sort(key=lambda p: p["estimated_net"], reverse=True)

        return {
            "total_categories": len(parts),
            "estimated_total_net": round(total_net, 2),
            "top_parts": parts[:10],
            "recommendation": (
                "Part-out is financially attractive" if total_net >= 1000
                else "Part-out returns are modest"
            ),
        }

    @staticmethod
    def _build_seller_report(sold_listings: List[Listing]) -> Dict[str, Any]:
        """Build seller statistics report."""
        seller_stats: Dict[str, Dict[str, Any]] = {}

        for listing in sold_listings:
            seller = listing.seller or "Unknown"
            if seller not in seller_stats:
                seller_stats[seller] = {
                    "sold_count": 0,
                    "gross_revenue": 0.0,
                    "listings": [],
                }

            seller_stats[seller]["sold_count"] += 1
            if listing.price:
                seller_stats[seller]["gross_revenue"] += listing.price
            seller_stats[seller]["listings"].append(listing.title)

        sellers = [
            {
                "seller": seller,
                "parts_sold": stats["sold_count"],
                "gross_revenue": round(stats["gross_revenue"], 2),
                "sample_listings": stats["listings"][:5],
            }
            for seller, stats in seller_stats.items()
        ]

        sellers.sort(key=lambda s: s["gross_revenue"], reverse=True)

        return {
            "total_unique_sellers": len(sellers),
            "top_sellers": sellers[:10],
            "total_gross_revenue": round(sum(s["gross_revenue"] for s in sellers), 2),
        }

    @staticmethod
    def _build_competition_report(listings: List[Listing]) -> Dict[str, Any]:
        """Build competition analysis."""
        sellers = Counter(l.seller or "Unknown" for l in listings if l.keep)
        active_count = sum(1 for l in listings if l.listing_type == ListingType.ACTIVE and l.keep)
        sold_count = sum(1 for l in listings if l.listing_type == ListingType.SOLD and l.keep)

        # Calculate HHI (Herfindahl-Hirschman Index)
        total = active_count + sold_count
        market_shares = [count / max(1, total) * 100 for count in sellers.values() if count]
        hhi = sum(share ** 2 for share in market_shares)

        return {
            "total_active_listings": active_count,
            "total_sold_listings": sold_count,
            "total_unique_sellers": len(sellers),
            "hhi": round(hhi, 2),
            "top_sellers_by_volume": sellers.most_common(10),
            "active_to_sold_ratio": (
                round(active_count / max(1, sold_count), 2) if sold_count else float("inf")
            ),
        }

    @staticmethod
    def _build_price_distribution(listings: List[Listing]) -> Dict[str, Any]:
        """Build price distribution analysis."""
        prices = [l.price for l in listings if l.price and l.price > 0]
        if not prices:
            return {"count": 0}

        sorted_prices = sorted(prices)
        n = len(sorted_prices)

        def percentile(p: float) -> float:
            index = int(n * p)
            index = min(max(index, 0), n - 1)
            return sorted_prices[index]

        # Price ranges
        ranges = [
            (0, 25, "$0-$25"),
            (25, 50, "$25-$50"),
            (50, 100, "$50-$100"),
            (100, 200, "$100-$200"),
            (200, 500, "$200-$500"),
            (500, 1000, "$500-$1,000"),
            (1000, float("inf"), "$1,000+"),
        ]

        buckets = [
            {
                "range": label,
                "count": len([p for p in prices if lower <= p < upper]),
                "percentage": round(len([p for p in prices if lower <= p < upper]) / n * 100, 2),
            }
            for lower, upper, label in ranges
        ]

        return {
            "count": n,
            "min": round(sorted_prices[0], 2),
            "max": round(sorted_prices[-1], 2),
            "mean": round(statistics.mean(prices), 2),
            "median": round(statistics.median(prices), 2),
            "p25": round(percentile(0.25), 2),
            "p75": round(percentile(0.75), 2),
            "distribution": buckets,
        }

    @staticmethod
    def _build_dropped_summary(dropped_listings: List[Listing]) -> List[Dict[str, Any]]:
        """Build summary of why listings were dropped."""
        reason_counter = Counter(
            (l.classification_reason or "No reason provided").strip()
            for l in dropped_listings
        )

        return [
            {"reason": reason, "count": count}
            for reason, count in reason_counter.most_common(10)
        ]

    @staticmethod
    def _compute_stats(listings: List[Listing]) -> Dict[str, Any]:
        """Compute basic statistics for a list of listings."""
        if not listings:
            return {
                "count": 0,
                "avg_price": None,
                "median_price": None,
                "min_price": None,
                "max_price": None,
                "free_shipping_count": 0,
            }

        prices = [l.price for l in listings if l.price is not None]

        return {
            "count": len(listings),
            "avg_price": round(statistics.mean(prices), 2) if prices else None,
            "median_price": round(statistics.median(prices), 2) if prices else None,
            "min_price": round(min(prices), 2) if prices else None,
            "max_price": round(max(prices), 2) if prices else None,
            "free_shipping_count": sum(
                1 for l in listings
                if l.shipping == 0 or l.shipping is None
            ),
        }

"""eBay HTML parser."""

import logging
import re
from typing import List, Optional

from bs4 import BeautifulSoup

from ..models import Listing, ListingType
from ..utils import safe_float

logger = logging.getLogger(__name__)


class EbayParser:
    """Parser for eBay search results pages."""

    @staticmethod
    def clean_title(title: str) -> str:
        """
        Clean listing title text.

        Args:
            title: Raw title text

        Returns:
            Cleaned title
        """
        if not title:
            return title

        # Remove "Opens in a new window or tab" text
        title = re.sub(
            r"\s*Opens\s+in\s+a\s+new\s+window\s+or\s+tab\s*",
            " ",
            title,
            flags=re.IGNORECASE
        )

        # Remove "(For: ...)" patterns
        title = re.sub(r"\(For:\s*[^)]+\)", "", title, flags=re.IGNORECASE)

        # Collapse whitespace
        title = re.sub(r"\s+", " ", title).strip()

        return title

    @staticmethod
    def parse_listing_block(
        html: str,
        page: int,
        listing_type: ListingType,
    ) -> Optional[Listing]:
        """
        Parse a single listing HTML block.

        Args:
            html: HTML string for listing
            page: Page number
            listing_type: Active or sold

        Returns:
            Listing object or None if parsing fails
        """
        try:
            soup = BeautifulSoup(html, "html.parser")

            # Extract title
            title_elem = soup.select_one(".s-card__title, [class*='s-card__title']")
            if not title_elem:
                return None

            title = EbayParser.clean_title(title_elem.get_text(strip=True))
            if not title:
                return None

            # Extract URL and item ID
            link_elem = soup.find("a", href=re.compile(r"/itm/\d+"))
            if not link_elem:
                return None

            url = link_elem.get("href", "")
            if not url:
                return None

            if not url.startswith("http"):
                url = "https://www.ebay.com" + url

            # Extract item ID from URL
            id_match = re.search(r"/itm/(\d+)", url)
            item_id = id_match.group(1) if id_match else str(abs(hash(url)))

            # Extract price
            price_elem = soup.select_one(".s-card__price, [class*='s-card__price']")
            price = safe_float(price_elem.get_text() if price_elem else None)

            # Extract shipping
            shipping = EbayParser._parse_shipping(html)

            # Extract seller info
            seller, seller_feedback = EbayParser._parse_seller(soup)

            # Extract image URL
            image_url = EbayParser._parse_image(soup)

            return Listing(
                item_id=item_id,
                title=title,
                raw_title=title,
                price=price,
                url=url,
                shipping=shipping,
                page=page,
                listing_type=listing_type,
                seller=seller,
                seller_feedback=seller_feedback,
                image_url=image_url,
            )

        except Exception as exc:
            logger.warning(f"Failed to parse listing block: {exc}")
            return None

    @staticmethod
    def _parse_shipping(html: str) -> Optional[float]:
        """Parse shipping cost from HTML."""
        # Look for "+$X.XX shipping"
        shipping_match = re.search(r"\+\$([\d.,]+)\s+shipping", html, re.IGNORECASE)
        if shipping_match:
            return safe_float(shipping_match.group(1))

        # Look for "free shipping"
        if re.search(r"free\s+shipping", html, re.IGNORECASE):
            return 0.0

        return None

    @staticmethod
    def _parse_seller(soup: BeautifulSoup) -> tuple[str, str]:
        """Parse seller username and feedback."""
        seller = "Unknown"
        seller_feedback = ""

        attr_rows = soup.find_all("div", class_=re.compile(r"s-card__attribute-row"))
        for attr_row in attr_rows:
            inner_text = attr_row.get_text(separator=" ", strip=True)
            inner_text = re.sub(r"\s+", " ", inner_text)

            # Try pattern: "username 99.5% positive (123)"
            match = re.match(
                r"^([A-Za-z0-9\-_]+)\s+([\d.]+)%\s+(positive|negative)\s+\(([^)]+)\)",
                inner_text,
                re.I
            )
            if match:
                seller = match.group(1)
                seller_feedback = f"{match.group(2)}% {match.group(3)} ({match.group(4)})"
                break

            # Try alternate pattern: "username positive (123)"
            alt_match = re.match(
                r"^([A-Za-z0-9\-_]+)\s+(positive|negative)\s+\(([^)]+)\)",
                inner_text,
                re.I
            )
            if alt_match:
                seller = alt_match.group(1)
                seller_feedback = f"{alt_match.group(2)} ({alt_match.group(3)})"
                break

            # Fallback: first word that's not a price
            parts = inner_text.split()
            if parts and not parts[0].startswith("$") and not parts[0].replace(".", "").isdigit():
                seller = parts[0]

        return seller, seller_feedback

    @staticmethod
    def _parse_image(soup: BeautifulSoup) -> Optional[str]:
        """Parse product image URL."""
        # Strategy 1: Look for img with common eBay classes
        img_elem = soup.find("img", class_=re.compile(r"image|img|thumbnail|s-item__image", re.I))
        if not img_elem:
            # Strategy 2: Any img tag
            img_elem = soup.find("img")

        if not img_elem:
            return None

        # Try various attributes
        image_url = (
            img_elem.get("src")
            or img_elem.get("data-src")
            or img_elem.get("data-lazy-src")
            or img_elem.get("data-zoom-src")
            or img_elem.get("data-original")
        )

        if not image_url:
            # Try parent link
            parent_link = img_elem.find_parent("a")
            if parent_link:
                href = parent_link.get("href")
                if href and any(ext in href.lower() for ext in [".jpg", ".jpeg", ".png", ".gif", ".webp", "ebayimg"]):
                    image_url = href

        if not image_url:
            return None

        # Normalize URL
        if image_url.startswith("//"):
            image_url = "https:" + image_url
        elif image_url.startswith("/"):
            image_url = "https://www.ebay.com" + image_url

        # Clean query parameters (keep s-l size parameters)
        if "?" in image_url:
            if "s-l" in image_url:
                base, params = image_url.split("?", 1)
                keep_params = [p for p in params.split("&") if "s-l" in p]
                image_url = base + ("?" + "&".join(keep_params) if keep_params else "")
            else:
                image_url = image_url.split("?")[0]

        return image_url

    @staticmethod
    def parse_page(
        soup: BeautifulSoup,
        page: int,
        listing_type: ListingType,
    ) -> List[Listing]:
        """
        Parse all listings from a search results page.

        Args:
            soup: Parsed HTML
            page: Page number
            listing_type: Active or sold

        Returns:
            List of Listing objects
        """
        results_container = soup.find("div", id="srp-river-results")

        # Try different selectors
        selectors = ["ul li.s-card", ".s-card"]
        elements = []

        for selector in selectors:
            if results_container:
                elements = results_container.select(selector)
            else:
                elements = soup.select(selector)

            if elements:
                break

        listings = []
        for element in elements:
            listing_html = str(element)
            listing = EbayParser.parse_listing_block(listing_html, page, listing_type)
            if listing:
                listings.append(listing)

        logger.info(f"Parsed {len(listings)} listings from page {page} ({listing_type.value})")
        return listings

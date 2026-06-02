"""AI prompt templates - separated for easy maintenance and testing."""

from typing import List


class PromptTemplates:
    """Collection of AI prompt templates."""

    @staticmethod
    def classification_prompt(query: str, listings: List[dict]) -> str:
        """Build classification prompt for a batch of listings."""
        lines = [
            "You are cleaning and categorising eBay listings for an automotive parts buyer.",
            f"The user searched for: '{query}'.",
            "For each listing decide if it is genuinely relevant, then assign a specific part category.",
            "",
            "Rules:",
            "1. Set keep=false for unrelated, duplicate, accessory-only, or generic tool listings.",
            "2. Always provide a concise reason for the decision.",
            "3. Categories should be specific (e.g. 'Front bumper cover', 'HV battery pack'), not vague.",
            "4. Output JSON with key 'classified_listings' containing an array of objects",
            "   where each object has: id, keep (true/false), category, reason, normalized_title, price, listing_type.",
            "5. Return JSON only, no markdown or extra commentary.",
            "",
            "Listings:",
        ]

        for item in listings:
            price_text = f"${item['price']:.2f}" if item.get('price') else "unknown"
            lines.append(
                f"- id={item['item_id']} | type={item['listing_type']} | price={price_text} | title={item['title']}"
            )

        return "\n".join(lines)

    @staticmethod
    def category_merge_prompt(category_group: List[str], phase: int, vehicle_info: str = "") -> str:
        """Build prompt for merging similar categories."""
        if len(category_group) == 1:
            # Single category - no merge needed
            return ""

        prompt = f"""You are analyzing automotive part categories to determine if they are variations of the same part.

Vehicle: {vehicle_info if vehicle_info else 'Unknown'}

Categories to analyze (Phase {phase}):
{chr(10).join(f"- {cat}" for cat in category_group)}

CRITICAL RULES - BE FLEXIBLE AND AGGRESSIVE IN MERGING:
1. MERGE if these are variations/descriptions of the SAME part type:
   - Different naming conventions (e.g., "ABS brake pump" vs "ABS hydraulic pump" - same part)
   - Different specifications in parentheses (e.g., "Headlight (Halogen)" vs "Headlight (Xenon)" - both headlights)
   - Different word order (e.g., "ABS pump" vs "pump ABS" - same thing)
   - Core part name is the same, only specifications differ

2. DO NOT MERGE only if these are CLEARLY DIFFERENT parts:
   - Completely different part types (e.g., "Engine assembly" vs "Transmission")
   - Different components serving different functions (e.g., "Front bumper" vs "Rear bumper")

3. BE AGGRESSIVE: When in doubt, MERGE. If the core part name is the same, merge them.

Return JSON with this structure:
{{
  "should_merge": true/false,
  "canonical_name": "Best name for the merged category (use most descriptive)",
  "reason": "Brief explanation of why merge or not merge",
  "variations": ["list of ALL category names that should be merged together"]
}}

If should_merge is true, ALL categories in the list should be in variations array.
If should_merge is false, return variations as empty array.
Return JSON only, no markdown or extra commentary."""

        return prompt

    @staticmethod
    def category_tree_prompt(category_names: List[str], batch_index: int, vehicle_info: str = "") -> str:
        """Build prompt for organizing categories into a tree structure."""
        prompt = f"""You are organizing automotive parts categories into hierarchical relationships.

Vehicle: {vehicle_info if vehicle_info else 'Unknown'}

Categories to organize (batch {batch_index + 1}):
{chr(10).join(f"- {cat}" for cat in category_names)}

Your task:
1. Identify parent categories (e.g., "Engine", "Transmission", "Body Parts", "Interior", "Electrical")
2. Assign each category to a parent, or mark as standalone if it's a top-level category
3. Maximum depth: 3 levels (parent -> child -> grandchild)
4. Create logical automotive groupings

Return JSON with this structure:
{{
  "relationships": [
    {{
      "category": "Engine Block",
      "parent": "Engine",
      "level": 2
    }},
    {{
      "category": "Engine",
      "parent": null,
      "level": 1
    }}
  ],
  "parent_categories": ["Engine", "Transmission", "Body Parts", "Interior"]
}}

Rules:
- Group related categories under logical automotive parent categories
- A category can only have one parent
- Standalone categories should have parent: null and level: 1
- Return JSON only, no markdown or extra commentary."""

        return prompt

    @staticmethod
    def category_grouping_prompt(category_names: List[str], vehicle_info: str = "") -> str:
        """Build prompt for grouping categories for part-out analysis."""
        prompt = f"""You are organizing automotive parts into logical groups for a part-out analysis.

Vehicle: {vehicle_info if vehicle_info else 'Unknown'}

Categories to group:
{chr(10).join(f"- {cat}" for cat in category_names)}

CRITICAL RULES:
1. A car CANNOT have duplicate/alternative versions of the same part - these MUST go in SEPARATE groups
   - Example: "Left mirror" and "Left mirror with signal" are ALTERNATIVES - different groups
   - Example: "Base engine" and "Turbo engine" are ALTERNATIVES - different groups
2. Each group should contain parts that can coexist on the same vehicle simultaneously
3. Only group parts that are truly different parts (e.g., front bumper + rear bumper + hood together)

Return JSON with this structure:
{{
  "groups": [
    {{
      "group_id": 1,
      "group_name": "Base Model Engine Group",
      "categories": ["Engine Block", "Cylinder Head", "Oil Pan"]
    }},
    {{
      "group_id": 2,
      "group_name": "Body Parts Group",
      "categories": ["Front Bumper", "Rear Bumper", "Hood"]
    }}
  ]
}}

Return JSON only, no markdown or extra commentary."""

        return prompt

"""Helper utility functions."""

import json
import re
from difflib import SequenceMatcher
from typing import Optional, Union


def safe_float(value: Optional[str]) -> Optional[float]:
    """
    Safely convert string to float, extracting digits.

    Args:
        value: String containing a number

    Returns:
        Float value or None if conversion fails
    """
    if not value:
        return None

    # Extract digits and decimal point
    digits = "".join(ch for ch in str(value) if ch.isdigit() or ch == ".")
    if not digits:
        return None

    try:
        return float(digits)
    except ValueError:
        return None


def extract_json_from_text(text: str) -> Optional[Union[dict, list]]:
    """
    Extract JSON from text that may contain markdown fences or extra content.

    Args:
        text: Raw text containing JSON

    Returns:
        Parsed JSON object or None if extraction fails
    """
    if not text:
        return None

    text = text.strip()

    # Remove markdown code fences
    if text.startswith("```"):
        lines = text.splitlines()
        if lines:
            lines = lines[1:]  # Remove first line (```json or ```)
        while lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]  # Remove last line (```)
        text = "\n".join(lines).strip()
    else:
        text = text.replace("```json", "").replace("```", "")

    # Try to find array first (for batch responses)
    array_match = _extract_balanced_json(text, "[")
    if array_match:
        try:
            return json.loads(array_match)
        except json.JSONDecodeError:
            pass

    # Try to find object
    obj_match = _extract_balanced_json(text, "{")
    if obj_match:
        try:
            return json.loads(obj_match)
        except json.JSONDecodeError:
            # Try to repair common JSON errors
            repaired = _repair_json(obj_match)
            try:
                return json.loads(repaired)
            except json.JSONDecodeError:
                pass

    return None


def _extract_balanced_json(text: str, start_char: str) -> Optional[str]:
    """
    Extract a balanced JSON string (array or object) from text.

    Args:
        text: Text containing JSON
        start_char: Starting character ('[' or '{')

    Returns:
        Extracted JSON string or None
    """
    start_idx = text.find(start_char)
    if start_idx == -1:
        return None

    end_char = "]" if start_char == "[" else "}"
    bracket_count = 0
    in_string = False
    escape_next = False

    for i in range(start_idx, len(text)):
        char = text[i]

        if escape_next:
            escape_next = False
            continue

        if char == "\\":
            escape_next = True
            continue

        if char == '"' and not escape_next:
            in_string = not in_string

        if not in_string:
            if char == start_char:
                bracket_count += 1
            elif char == end_char:
                bracket_count -= 1
                if bracket_count == 0:
                    return text[start_idx : i + 1]

    return None


def _repair_json(json_str: str) -> str:
    """
    Attempt to repair common JSON errors.

    Args:
        json_str: Malformed JSON string

    Returns:
        Repaired JSON string
    """
    # Fix missing commas before closing braces/brackets
    json_str = re.sub(r'([}\]])\s*"', r'\1,"', json_str)

    # Remove trailing commas before closing braces/brackets
    json_str = re.sub(r',(\s*[}\]])', r'\1', json_str)

    return json_str


def calculate_similarity(str1: str, str2: str) -> float:
    """
    Calculate similarity ratio between two strings.

    Args:
        str1: First string
        str2: Second string

    Returns:
        Similarity ratio between 0 and 1
    """
    return SequenceMatcher(None, str1.lower(), str2.lower()).ratio()


def extract_core_part_name(category: str) -> str:
    """
    Extract core part name by removing specifications and normalizing.

    Args:
        category: Category name

    Returns:
        Normalized core part name
    """
    core = category.lower().strip()

    # Remove everything in parentheses
    core = re.sub(r'\([^)]*\)', '', core)

    # Remove common variant words
    variant_words = [
        'hybrid', 'halogen', 'xenon', 'hid', 'led', 'standard',
        'premium', 'base', 'turbo', 'sport'
    ]
    for word in variant_words:
        core = re.sub(rf'\b{word}\b', '', core, flags=re.IGNORECASE)

    # Remove common location/position words
    location_words = [
        'left', 'right', 'front', 'rear', 'driver', 'passenger',
        'upper', 'lower', 'inner', 'outer'
    ]
    for word in location_words:
        core = re.sub(rf'\b{word}\b', '', core, flags=re.IGNORECASE)

    # Remove extra whitespace
    core = re.sub(r'\s+', ' ', core).strip()

    # Extract key words (remove common filler words)
    words = core.split()
    filler_words = {'the', 'a', 'an', 'for', 'with', 'and', 'or', 'of', 'to', 'in', 'on', 'at', 'by'}
    key_words = [w for w in words if w not in filler_words and len(w) > 2]

    # Sort key words to normalize order
    key_words_sorted = sorted(key_words)
    return ' '.join(key_words_sorted) if key_words_sorted else core

"""
Xactimate Code Parser using Regular Expressions.
Parses and categorizes Xactimate line item codes.
"""

import re
from dataclasses import dataclass
from enum import Enum
from typing import Any


class XactimateCategory(str, Enum):
    """Standard Xactimate code categories."""

    WTR = "WTR"  # Water Remediation
    DRY = "DRY"  # Drying Equipment
    FCC = "FCC"  # Flooring - Carpet
    FNC = "FNC"  # Flooring - Non-Carpet (Hardwood, Tile, etc.)
    DRY_WALL = "DRY"  # Drywall
    PNT = "PNT"  # Painting
    CLN = "CLN"  # Cleaning
    DEM = "DEM"  # Demolition
    CNT = "CNT"  # Contents
    GEN = "GEN"  # General/Miscellaneous
    UNKNOWN = "UNKNOWN"


@dataclass
class ParsedCode:
    """Parsed Xactimate code with extracted components."""

    original_code: str
    category: XactimateCategory
    subcategory: str | None
    variant: str | None
    is_labor: bool
    is_material: bool
    is_equipment: bool
    metadata: dict[str, Any]


class XactimateParser:
    """
    Parser for Xactimate estimating codes.
    Uses regex patterns to extract category, type, and attributes.
    """

    # Core category patterns
    CATEGORY_PATTERNS: dict[str, re.Pattern[str]] = {
        "WTR": re.compile(r"^WTR[_\-]?", re.IGNORECASE),
        "DRY": re.compile(r"^DRY[_\-]?", re.IGNORECASE),
        "FCC": re.compile(r"^FCC[_\-]?", re.IGNORECASE),
        "FNC": re.compile(r"^FNC[_\-]?", re.IGNORECASE),
        "PNT": re.compile(r"^PNT[_\-]?", re.IGNORECASE),
        "CLN": re.compile(r"^CLN[_\-]?", re.IGNORECASE),
        "DEM": re.compile(r"^DEM[_\-]?", re.IGNORECASE),
        "CNT": re.compile(r"^CNT[_\-]?", re.IGNORECASE),
        "GEN": re.compile(r"^GEN[_\-]?", re.IGNORECASE),
    }

    # Equipment-specific patterns
    EQUIPMENT_PATTERNS: dict[str, re.Pattern[str]] = {
        "air_mover": re.compile(r"(AIR\s*MOVER|AIRF|AIR_F|FAN)", re.IGNORECASE),
        "dehumidifier": re.compile(r"(DEHUM|DEHU|DH\d*)", re.IGNORECASE),
        "air_scrubber": re.compile(r"(AIR\s*SCRUB|HEPA|SCRUB)", re.IGNORECASE),
        "moisture_meter": re.compile(r"(MOIST|METER|READ)", re.IGNORECASE),
    }

    # Labor indicators
    LABOR_PATTERNS: list[re.Pattern[str]] = [
        re.compile(r"LABOR", re.IGNORECASE),
        re.compile(r"\bLBR\b", re.IGNORECASE),
        re.compile(r"TECH", re.IGNORECASE),
        re.compile(r"MONITOR", re.IGNORECASE),
        re.compile(r"SUPERVISE", re.IGNORECASE),
        re.compile(r"INSPECT", re.IGNORECASE),
    ]

    # Material indicators
    MATERIAL_PATTERNS: list[re.Pattern[str]] = [
        re.compile(r"MATERIAL", re.IGNORECASE),
        re.compile(r"\bMAT\b", re.IGNORECASE),
        re.compile(r"SUPPLY", re.IGNORECASE),
    ]

    # Flooring-specific patterns
    FLOORING_PATTERNS: dict[str, re.Pattern[str]] = {
        "carpet": re.compile(r"(CARPET|CPT|CRPT)", re.IGNORECASE),
        "pad": re.compile(r"(PAD|UNDERLAYMENT|UNDERLAY)", re.IGNORECASE),
        "hardwood": re.compile(r"(HARDWOOD|HWD|WOOD\s*FLOOR)", re.IGNORECASE),
        "tile": re.compile(r"(TILE|CERAMIC|PORCELAIN)", re.IGNORECASE),
        "laminate": re.compile(r"(LAMINATE|LAM)", re.IGNORECASE),
        "vinyl": re.compile(r"(VINYL|VNL|LVP|LVT)", re.IGNORECASE),
        "tear_out": re.compile(r"(TEAR\s*OUT|REMOVE|REM|DEMO)", re.IGNORECASE),
        "install": re.compile(r"(INSTALL|INST|LAY|REPLACE)", re.IGNORECASE),
        "leveling": re.compile(r"(LEVEL|PREP|SUBFLOOR)", re.IGNORECASE),
    }

    # Water category indicators
    WATER_CATEGORY_PATTERNS: dict[int, list[re.Pattern[str]]] = {
        1: [re.compile(r"(CAT\s*1|CATEGORY\s*1|CLEAN\s*WATER)", re.IGNORECASE)],
        2: [re.compile(r"(CAT\s*2|CATEGORY\s*2|GRAY\s*WATER|GREY\s*WATER)", re.IGNORECASE)],
        3: [
            re.compile(
                r"(CAT\s*3|CATEGORY\s*3|BLACK\s*WATER|SEWAGE|CONTAM)", re.IGNORECASE
            )
        ],
    }

    # PPE/Safety patterns
    PPE_PATTERNS: list[re.Pattern[str]] = [
        re.compile(r"(PPE|TYVEK|RESPIRATOR|GLOVE|GOGG)", re.IGNORECASE),
        re.compile(r"(HAZMAT|HAZ\s*MAT|BIOHAZ)", re.IGNORECASE),
        re.compile(r"(CONTAINMENT|BARRIER|POLY)", re.IGNORECASE),
    ]

    # Double-dip detection patterns (items commonly billed redundantly)
    DOUBLE_DIP_GROUPS: list[tuple[str, list[re.Pattern[str]]]] = [
        (
            "door_hardware",
            [
                re.compile(r"(PRE\s*HUNG|PREHUNG)", re.IGNORECASE),
                re.compile(r"(HINGE|DOOR\s*HARDWARE)", re.IGNORECASE),
            ],
        ),
        (
            "wallboard_removal",
            [
                re.compile(r"(WALLBOARD|DRYWALL).*(REMOVE|DEMO|TEAR)", re.IGNORECASE),
                re.compile(r"(WALLPAPER).*(REMOVE|DEMO|TEAR)", re.IGNORECASE),
            ],
        ),
        (
            "carpet_pad",
            [
                re.compile(r"(CARPET).*(TEAR|REMOVE|DEMO)", re.IGNORECASE),
                re.compile(r"(PAD).*(TEAR|REMOVE|DEMO)", re.IGNORECASE),
            ],
        ),
    ]

    def __init__(self) -> None:
        """Initialize the parser."""
        self._code_cache: dict[str, ParsedCode] = {}

    def parse_code(self, code: str, description: str = "") -> ParsedCode:
        """
        Parse an Xactimate code and extract its components.

        Args:
            code: The Xactimate code to parse
            description: Optional description for additional context

        Returns:
            ParsedCode with extracted components
        """
        cache_key = f"{code}|{description}"
        if cache_key in self._code_cache:
            return self._code_cache[cache_key]

        # Determine category
        category = XactimateCategory.UNKNOWN
        for cat_name, pattern in self.CATEGORY_PATTERNS.items():
            if pattern.search(code):
                category = XactimateCategory(cat_name)
                break

        # Check if it's labor, material, or equipment
        combined_text = f"{code} {description}"
        is_labor = any(p.search(combined_text) for p in self.LABOR_PATTERNS)
        is_material = any(p.search(combined_text) for p in self.MATERIAL_PATTERNS)
        is_equipment = any(
            p.search(combined_text) for p in self.EQUIPMENT_PATTERNS.values()
        )

        # Extract metadata
        metadata: dict[str, Any] = {}

        # Check for equipment types
        for equip_type, pattern in self.EQUIPMENT_PATTERNS.items():
            if pattern.search(combined_text):
                metadata["equipment_type"] = equip_type

        # Check for flooring types
        for floor_type, pattern in self.FLOORING_PATTERNS.items():
            if pattern.search(combined_text):
                metadata.setdefault("flooring_attributes", []).append(floor_type)

        # Check for water category
        for cat_num, patterns in self.WATER_CATEGORY_PATTERNS.items():
            if any(p.search(combined_text) for p in patterns):
                metadata["water_category"] = cat_num

        # Check for PPE
        if any(p.search(combined_text) for p in self.PPE_PATTERNS):
            metadata["requires_ppe"] = True

        parsed = ParsedCode(
            original_code=code,
            category=category,
            subcategory=self._extract_subcategory(code, category),
            variant=None,
            is_labor=is_labor,
            is_material=is_material,
            is_equipment=is_equipment,
            metadata=metadata,
        )

        self._code_cache[cache_key] = parsed
        return parsed

    def _extract_subcategory(
        self, code: str, category: XactimateCategory
    ) -> str | None:
        """Extract subcategory from code."""
        # Remove category prefix
        remaining = code
        if category != XactimateCategory.UNKNOWN:
            remaining = re.sub(
                rf"^{category.value}[_\-]?", "", code, flags=re.IGNORECASE
            )

        # Return first segment as subcategory
        parts = re.split(r"[_\-]", remaining)
        return parts[0] if parts and parts[0] else None

    def find_equipment_items(
        self, codes_with_descriptions: list[tuple[str, str]]
    ) -> dict[str, list[tuple[str, str]]]:
        """
        Find all equipment items grouped by type.

        Args:
            codes_with_descriptions: List of (code, description) tuples

        Returns:
            Dictionary mapping equipment type to list of matching items
        """
        results: dict[str, list[tuple[str, str]]] = {
            equip_type: [] for equip_type in self.EQUIPMENT_PATTERNS
        }

        for code, description in codes_with_descriptions:
            combined = f"{code} {description}"
            for equip_type, pattern in self.EQUIPMENT_PATTERNS.items():
                if pattern.search(combined):
                    results[equip_type].append((code, description))

        return results

    def find_double_dip_candidates(
        self, codes_with_descriptions: list[tuple[str, str]]
    ) -> list[dict[str, Any]]:
        """
        Find potential double-dip billing situations.

        Returns list of potential issues with matched items.
        """
        candidates: list[dict[str, Any]] = []

        for group_name, patterns in self.DOUBLE_DIP_GROUPS:
            matches: list[list[tuple[str, str]]] = [[] for _ in patterns]

            for code, description in codes_with_descriptions:
                combined = f"{code} {description}"
                for i, pattern in enumerate(patterns):
                    if pattern.search(combined):
                        matches[i].append((code, description))

            # If multiple patterns in a group have matches, it's a candidate
            matched_count = sum(1 for m in matches if m)
            if matched_count > 1:
                candidates.append(
                    {
                        "group": group_name,
                        "matches": {
                            f"pattern_{i}": m for i, m in enumerate(matches) if m
                        },
                    }
                )

        return candidates

    def extract_category_items(
        self, codes_with_descriptions: list[tuple[str, str]], category: XactimateCategory
    ) -> list[ParsedCode]:
        """Extract all items belonging to a specific category."""
        return [
            self.parse_code(code, desc)
            for code, desc in codes_with_descriptions
            if self.parse_code(code, desc).category == category
        ]

    def has_pattern(self, text: str, pattern_name: str) -> bool:
        """Check if text matches a named pattern."""
        # Check equipment patterns
        if pattern_name in self.EQUIPMENT_PATTERNS:
            return bool(self.EQUIPMENT_PATTERNS[pattern_name].search(text))

        # Check flooring patterns
        if pattern_name in self.FLOORING_PATTERNS:
            return bool(self.FLOORING_PATTERNS[pattern_name].search(text))

        return False


# Singleton instance
_parser_instance: XactimateParser | None = None


def get_parser() -> XactimateParser:
    """Get the singleton parser instance."""
    global _parser_instance
    if _parser_instance is None:
        _parser_instance = XactimateParser()
    return _parser_instance

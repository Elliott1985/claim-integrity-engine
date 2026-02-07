"""
Phase 3: Flooring & Finish Module (FCC/FNC).
Audits waste percentages, overlap billing, and floor preparation.
"""

import re
from decimal import Decimal
from typing import Any

from ..core.models import (
    AuditCategory,
    AuditFinding,
    AuditSeverity,
    ClaimData,
)
from ..core.rule_engine import AuditRule, RuleEngine
from ..core.xactimate_parser import get_parser


class FlooringValidator:
    """
    Validates flooring claims for waste percentages,
    overlap billing, and proper floor preparation.
    """

    # Maximum acceptable waste percentages for simple room profiles
    MAX_HARDWOOD_WASTE = 0.15  # 15%
    MAX_CARPET_WASTE = 0.10  # 10%
    MAX_TILE_WASTE = 0.15  # 15%
    MAX_VINYL_WASTE = 0.10  # 10%

    # Patterns for flooring identification
    CARPET_PATTERN = re.compile(r"(CARPET|CPT|CRPT)", re.IGNORECASE)
    PAD_PATTERN = re.compile(r"\b(PAD|CUSHION|UNDERLAY)\b", re.IGNORECASE)
    HARDWOOD_PATTERN = re.compile(r"(HARDWOOD|HWD|WOOD\s*FLOOR|ENGINEERED)", re.IGNORECASE)
    TILE_PATTERN = re.compile(r"(TILE|CERAMIC|PORCELAIN|STONE)", re.IGNORECASE)
    LAMINATE_PATTERN = re.compile(r"(LAMINATE|LAM\s*FLOOR)", re.IGNORECASE)
    VINYL_PATTERN = re.compile(r"(VINYL|VNL|LVP|LVT|SHEET)", re.IGNORECASE)

    # Action patterns
    TEAR_OUT_PATTERN = re.compile(r"(TEAR\s*OUT|REMOVE|REM\s|R&R|DEMO)", re.IGNORECASE)
    INSTALL_PATTERN = re.compile(r"(INSTALL|INST|LAY|REPLACE)", re.IGNORECASE)
    WASTE_PATTERN = re.compile(r"(WASTE|CUTOFF|CUT\s*OFF|OVERAGE)", re.IGNORECASE)
    LEVELING_PATTERN = re.compile(r"(LEVEL|PREP|SUBFLOOR|SELF\s*LEVEL|FLOAT)", re.IGNORECASE)

    def __init__(self, rule_engine: RuleEngine | None = None) -> None:
        self.engine = rule_engine or RuleEngine()
        self.parser = get_parser()
        self._register_rules()

    def _register_rules(self) -> None:
        """Register all flooring validation rules."""
        # Waste audit
        self.engine.add_rule(
            AuditRule(
                rule_id="FLR-001",
                name="Flooring Waste Audit",
                description="Calculate and flag excessive waste percentages (>10-15% for simple rooms)",
                category=AuditCategory.LEAKAGE,
                severity=AuditSeverity.WARNING,
                code_patterns=[r"^FCC", r"^FNC", r"WASTE"],
                validator=self._validate_waste,
            )
        )

        # Carpet/Pad overlap audit
        self.engine.add_rule(
            AuditRule(
                rule_id="FLR-002",
                name="Carpet/Pad Tear-Out Overlap",
                description="Flag if carpet and pad tear-out are billed separately (pad usually included)",
                category=AuditCategory.LEAKAGE,
                severity=AuditSeverity.WARNING,
                code_patterns=[r"CARPET.*TEAR", r"PAD.*TEAR"],
                validator=self._validate_carpet_pad_overlap,
            )
        )

        # Floor preparation check
        self.engine.add_rule(
            AuditRule(
                rule_id="FLR-003",
                name="Floor Preparation Check",
                description="Flag missing floor leveling/prep for hardwood or tile replacement",
                category=AuditCategory.SUPPLEMENT_RISK,
                severity=AuditSeverity.INFO,
                code_patterns=[r"HARDWOOD.*REPLACE", r"TILE.*REPLACE", r"LEVEL"],
                validator=self._validate_floor_prep,
            )
        )

        # Matching materials
        self.engine.add_rule(
            AuditRule(
                rule_id="FLR-004",
                name="Material Matching Check",
                description="Check if flooring replacement matches existing or includes transition strips",
                category=AuditCategory.SUPPLEMENT_RISK,
                severity=AuditSeverity.INFO,
                validator=self._validate_material_matching,
            )
        )

    def _validate_waste(
        self, claim: ClaimData, context: dict[str, Any]
    ) -> list[AuditFinding]:
        """Validate flooring waste percentages."""
        findings: list[AuditFinding] = []

        # Group flooring items by type
        flooring_by_type: dict[str, dict[str, Decimal]] = {}

        for item in claim.line_items:
            combined = f"{item.code} {item.description}"

            # Determine flooring type
            floor_type = None
            max_waste = 0.15  # Default

            if self.CARPET_PATTERN.search(combined):
                floor_type = "carpet"
                max_waste = self.MAX_CARPET_WASTE
            elif self.HARDWOOD_PATTERN.search(combined):
                floor_type = "hardwood"
                max_waste = self.MAX_HARDWOOD_WASTE
            elif self.TILE_PATTERN.search(combined):
                floor_type = "tile"
                max_waste = self.MAX_TILE_WASTE
            elif self.VINYL_PATTERN.search(combined) or self.LAMINATE_PATTERN.search(combined):
                floor_type = "vinyl_laminate"
                max_waste = self.MAX_VINYL_WASTE

            if floor_type:
                if floor_type not in flooring_by_type:
                    flooring_by_type[floor_type] = {
                        "material": Decimal("0"),
                        "waste": Decimal("0"),
                        "max_waste": Decimal(str(max_waste)),
                    }

                if self.WASTE_PATTERN.search(combined):
                    flooring_by_type[floor_type]["waste"] += item.total or Decimal("0")
                elif self.INSTALL_PATTERN.search(combined):
                    flooring_by_type[floor_type]["material"] += item.total or Decimal("0")

        # Check waste percentages
        for floor_type, amounts in flooring_by_type.items():
            if amounts["material"] > 0 and amounts["waste"] > 0:
                waste_pct = amounts["waste"] / amounts["material"]
                max_waste_pct = amounts["max_waste"]

                if waste_pct > max_waste_pct:
                    excess_waste = amounts["waste"] - (amounts["material"] * max_waste_pct)
                    findings.append(
                        AuditFinding(
                            finding_id=self.engine.generate_finding_id(),
                            category=AuditCategory.LEAKAGE,
                            severity=AuditSeverity.WARNING,
                            rule_name="Flooring Waste Audit",
                            title=f"Excessive {floor_type.title()} Waste",
                            description=(
                                f"{floor_type.title()} waste is {waste_pct:.1%} of material cost, "
                                f"exceeding the {max_waste_pct:.0%} threshold for simple room profiles."
                            ),
                            potential_impact=excess_waste,
                            evidence={
                                "floor_type": floor_type,
                                "material_cost": str(amounts["material"]),
                                "waste_cost": str(amounts["waste"]),
                                "waste_percentage": f"{waste_pct:.1%}",
                                "threshold": f"{max_waste_pct:.0%}",
                            },
                            recommendation=(
                                "Review room layout complexity. Higher waste may be justified "
                                "for irregular rooms, stairs, or pattern matching."
                            ),
                        )
                    )

        return findings

    def _validate_carpet_pad_overlap(
        self, claim: ClaimData, context: dict[str, Any]
    ) -> list[AuditFinding]:
        """Validate carpet and pad tear-out are not double-billed."""
        findings: list[AuditFinding] = []

        carpet_tearout_items: list[str] = []
        pad_tearout_items: list[str] = []
        carpet_tearout_total = Decimal("0")
        pad_tearout_total = Decimal("0")

        for item in claim.line_items:
            combined = f"{item.code} {item.description}"

            if self.TEAR_OUT_PATTERN.search(combined):
                if self.CARPET_PATTERN.search(combined) and not self.PAD_PATTERN.search(combined):
                    carpet_tearout_items.append(f"{item.code}: {item.description}")
                    carpet_tearout_total += item.total or Decimal("0")
                elif self.PAD_PATTERN.search(combined) and not self.CARPET_PATTERN.search(combined):
                    pad_tearout_items.append(f"{item.code}: {item.description}")
                    pad_tearout_total += item.total or Decimal("0")

        if carpet_tearout_items and pad_tearout_items:
            findings.append(
                AuditFinding(
                    finding_id=self.engine.generate_finding_id(),
                    category=AuditCategory.LEAKAGE,
                    severity=AuditSeverity.WARNING,
                    rule_name="Carpet/Pad Tear-Out Overlap",
                    title="Separate Carpet and Pad Tear-Out",
                    description=(
                        "Carpet tear-out and pad tear-out are billed as separate line items. "
                        "Standard practice includes pad removal with carpet tear-out."
                    ),
                    affected_items=carpet_tearout_items + pad_tearout_items,
                    potential_impact=pad_tearout_total,
                    evidence={
                        "carpet_tearout_count": len(carpet_tearout_items),
                        "pad_tearout_count": len(pad_tearout_items),
                        "pad_tearout_total": str(pad_tearout_total),
                    },
                    recommendation=(
                        "Verify if pad tear-out is separate scope or if it should be "
                        "included in carpet removal."
                    ),
                )
            )

        return findings

    def _validate_floor_prep(
        self, claim: ClaimData, context: dict[str, Any]
    ) -> list[AuditFinding]:
        """Validate floor preparation is included for hard surface flooring."""
        findings: list[AuditFinding] = []

        # Check for hardwood/tile replacement
        has_hardwood_replace = False
        has_tile_replace = False
        has_floor_leveling = False

        hardwood_items: list[str] = []
        tile_items: list[str] = []

        for item in claim.line_items:
            combined = f"{item.code} {item.description}"

            if self.INSTALL_PATTERN.search(combined) or "REPLACE" in combined.upper():
                if self.HARDWOOD_PATTERN.search(combined):
                    has_hardwood_replace = True
                    hardwood_items.append(f"{item.code}: {item.description}")
                elif self.TILE_PATTERN.search(combined):
                    has_tile_replace = True
                    tile_items.append(f"{item.code}: {item.description}")

            if self.LEVELING_PATTERN.search(combined):
                has_floor_leveling = True

        if has_hardwood_replace and not has_floor_leveling:
            findings.append(
                AuditFinding(
                    finding_id=self.engine.generate_finding_id(),
                    category=AuditCategory.SUPPLEMENT_RISK,
                    severity=AuditSeverity.INFO,
                    rule_name="Floor Preparation Check",
                    title="Missing Floor Prep for Hardwood",
                    description=(
                        "Hardwood flooring replacement found but no floor leveling/preparation. "
                        "This may result in a supplement if subfloor prep is needed."
                    ),
                    affected_items=hardwood_items,
                    evidence={
                        "hardwood_replace": has_hardwood_replace,
                        "floor_leveling": has_floor_leveling,
                    },
                    recommendation=(
                        "Verify subfloor condition and include prep work if needed "
                        "to avoid supplements."
                    ),
                )
            )

        if has_tile_replace and not has_floor_leveling:
            findings.append(
                AuditFinding(
                    finding_id=self.engine.generate_finding_id(),
                    category=AuditCategory.SUPPLEMENT_RISK,
                    severity=AuditSeverity.INFO,
                    rule_name="Floor Preparation Check",
                    title="Missing Floor Prep for Tile",
                    description=(
                        "Tile flooring replacement found but no floor leveling/preparation. "
                        "Tile installation typically requires flat, level subfloor."
                    ),
                    affected_items=tile_items,
                    evidence={
                        "tile_replace": has_tile_replace,
                        "floor_leveling": has_floor_leveling,
                    },
                    recommendation=(
                        "Verify subfloor flatness and include self-leveling compound "
                        "if needed."
                    ),
                )
            )

        return findings

    def _validate_material_matching(
        self, claim: ClaimData, context: dict[str, Any]
    ) -> list[AuditFinding]:
        """Check for material matching or transition considerations."""
        findings: list[AuditFinding] = []

        # Look for partial flooring replacement
        flooring_rooms: list[str] = []
        has_transition = False

        transition_pattern = re.compile(r"(TRANSITION|T-MOLD|REDUCER|THRESHOLD)", re.IGNORECASE)

        for item in claim.line_items:
            combined = f"{item.code} {item.description}"

            # Check for flooring installation
            if self.INSTALL_PATTERN.search(combined):
                is_flooring = (
                    self.CARPET_PATTERN.search(combined)
                    or self.HARDWOOD_PATTERN.search(combined)
                    or self.TILE_PATTERN.search(combined)
                    or self.VINYL_PATTERN.search(combined)
                    or self.LAMINATE_PATTERN.search(combined)
                )
                if is_flooring and item.room:
                    flooring_rooms.append(item.room)

            if transition_pattern.search(combined):
                has_transition = True

        # If flooring in multiple rooms but no transitions
        unique_rooms = set(flooring_rooms)
        if len(unique_rooms) > 1 and not has_transition:
            findings.append(
                AuditFinding(
                    finding_id=self.engine.generate_finding_id(),
                    category=AuditCategory.SUPPLEMENT_RISK,
                    severity=AuditSeverity.INFO,
                    rule_name="Material Matching Check",
                    title="Missing Transition Strips",
                    description=(
                        f"Flooring in {len(unique_rooms)} rooms but no transition strips found. "
                        "Transitions may be needed between rooms or flooring types."
                    ),
                    evidence={
                        "rooms_with_flooring": list(unique_rooms),
                        "transition_found": has_transition,
                    },
                    recommendation=(
                        "Verify if transition strips are needed between rooms "
                        "or at flooring type changes."
                    ),
                )
            )

        return findings

    def validate(self, claim: ClaimData) -> list[AuditFinding]:
        """Run all flooring validations on a claim."""
        return self.engine.execute_all(claim)

"""
Phase 4: General Repair & Remediation Module.
Audits double-dip billing and content protection.
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


class GeneralRepairValidator:
    """
    Validates general repair claims for double-dip billing
    and proper content protection.
    """

    # Double-dip detection patterns - items commonly billed redundantly
    DOUBLE_DIP_GROUPS: list[dict[str, Any]] = [
        {
            "name": "pre_hung_door_hardware",
            "description": "Pre-hung door includes hinges by default",
            "patterns": [
                ("pre_hung_door", re.compile(r"(PRE\s*HUNG|PREHUNG)\s*DOOR", re.IGNORECASE)),
                ("hinges", re.compile(r"\bHINGE", re.IGNORECASE)),
            ],
            "overlap_item": "hinges",
        },
        {
            "name": "wallboard_wallpaper_removal",
            "description": "Drywall removal inherently removes any attached wallpaper",
            "patterns": [
                ("wallboard_remove", re.compile(r"(WALLBOARD|DRYWALL).*(REMOVE|DEMO|TEAR)", re.IGNORECASE)),
                ("wallpaper_remove", re.compile(r"WALLPAPER.*(REMOVE|STRIP)", re.IGNORECASE)),
            ],
            "overlap_item": "wallpaper_remove",
        },
        {
            "name": "paint_primer",
            "description": "Paint with primer may duplicate separate primer line item",
            "patterns": [
                ("paint_primer", re.compile(r"PAINT.*PRIMER|PRIMER.*PAINT", re.IGNORECASE)),
                ("primer_only", re.compile(r"\bPRIMER\b(?!.*PAINT)", re.IGNORECASE)),
            ],
            "overlap_item": "primer_only",
        },
        {
            "name": "demo_disposal",
            "description": "Demolition often includes disposal; check for separate haul-off",
            "patterns": [
                ("demolition", re.compile(r"\b(DEMO|DEMOLITION)\b", re.IGNORECASE)),
                ("disposal", re.compile(r"(HAUL\s*OFF|DISPOSAL|DUMP|DEBRIS\s*REMOVAL)", re.IGNORECASE)),
            ],
            "overlap_item": "disposal",
        },
        {
            "name": "base_cap_molding",
            "description": "Base molding replacement may already include cap molding",
            "patterns": [
                ("base_molding", re.compile(r"BASE\s*(BOARD|MOLDING|MOULDING)", re.IGNORECASE)),
                ("cap_molding", re.compile(r"(CAP|SHOE)\s*(MOLDING|MOULDING)", re.IGNORECASE)),
            ],
            "overlap_item": None,  # Both could be legitimate
        },
    ]

    # Content protection patterns
    CONTENT_MANIPULATION_PATTERN = re.compile(
        r"(CONTENT\s*MANIP|MOVE\s*CONTENT|FURNITURE\s*MOVE|MOVE\s*OUT)", re.IGNORECASE
    )
    BLOCKING_PADDING_PATTERN = re.compile(
        r"(BLOCK|PAD|PROTECT|COVER|MASK).*?(CONTENT|FURNITURE|APPLIANCE)", re.IGNORECASE
    )
    FLOORING_WORK_PATTERN = re.compile(
        r"(FLOOR|CARPET|HARDWOOD|TILE|VINYL|LAMINATE).*(INSTALL|REPLACE|TEAR|REMOVE)", re.IGNORECASE
    )

    def __init__(self, rule_engine: RuleEngine | None = None) -> None:
        self.engine = rule_engine or RuleEngine()
        self.parser = get_parser()
        self._register_rules()

    def _register_rules(self) -> None:
        """Register all general repair validation rules."""
        # Double-dip checks
        self.engine.add_rule(
            AuditRule(
                rule_id="GEN-001",
                name="Double-Dip Detection",
                description="Flag overlapping charges like pre-hung door + hinges",
                category=AuditCategory.LEAKAGE,
                severity=AuditSeverity.WARNING,
                validator=self._validate_double_dip,
            )
        )

        # Content protection check
        self.engine.add_rule(
            AuditRule(
                rule_id="GEN-002",
                name="Content Protection Check",
                description="Verify content manipulation/protection when flooring is replaced",
                category=AuditCategory.SUPPLEMENT_RISK,
                severity=AuditSeverity.INFO,
                validator=self._validate_content_protection,
            )
        )

        # Labor minimums
        self.engine.add_rule(
            AuditRule(
                rule_id="GEN-003",
                name="Labor Minimum Check",
                description="Flag multiple labor minimums for same trade",
                category=AuditCategory.LEAKAGE,
                severity=AuditSeverity.WARNING,
                validator=self._validate_labor_minimums,
            )
        )

        # Same day different trades
        self.engine.add_rule(
            AuditRule(
                rule_id="GEN-004",
                name="Trade Coordination Check",
                description="Check for multiple trade minimums that could share mobilization",
                category=AuditCategory.LEAKAGE,
                severity=AuditSeverity.INFO,
                validator=self._validate_trade_coordination,
            )
        )

    def _validate_double_dip(
        self, claim: ClaimData, context: dict[str, Any]
    ) -> list[AuditFinding]:
        """Detect double-dip billing situations."""
        findings: list[AuditFinding] = []

        for group in self.DOUBLE_DIP_GROUPS:
            matches: dict[str, list[tuple[str, str, Decimal]]] = {
                name: [] for name, _ in group["patterns"]
            }

            for item in claim.line_items:
                combined = f"{item.code} {item.description}"

                for pattern_name, pattern in group["patterns"]:
                    if pattern.search(combined):
                        matches[pattern_name].append(
                            (item.code, item.description, item.total or Decimal("0"))
                        )

            # Check if multiple patterns in the group have matches
            matched_patterns = {k: v for k, v in matches.items() if v}

            if len(matched_patterns) > 1:
                overlap_item = group.get("overlap_item")
                potential_impact = Decimal("0")
                affected_items: list[str] = []

                for pattern_name, items in matched_patterns.items():
                    for code, desc, total in items:
                        affected_items.append(f"{code}: {desc}")
                        if overlap_item and pattern_name == overlap_item:
                            potential_impact += total

                findings.append(
                    AuditFinding(
                        finding_id=self.engine.generate_finding_id(),
                        category=AuditCategory.LEAKAGE,
                        severity=AuditSeverity.WARNING,
                        rule_name="Double-Dip Detection",
                        title=f"Potential Overlap: {group['name'].replace('_', ' ').title()}",
                        description=group["description"],
                        affected_items=affected_items,
                        potential_impact=potential_impact if potential_impact > 0 else None,
                        evidence={
                            "group": group["name"],
                            "matched_patterns": list(matched_patterns.keys()),
                        },
                        recommendation=(
                            "Review line items for potential overlap. "
                            "Verify if both charges are justified."
                        ),
                    )
                )

        return findings

    def _validate_content_protection(
        self, claim: ClaimData, context: dict[str, Any]
    ) -> list[AuditFinding]:
        """Validate content protection is included when flooring is replaced."""
        findings: list[AuditFinding] = []

        has_flooring_work = False
        has_content_manipulation = False
        has_blocking_padding = False

        flooring_items: list[str] = []

        for item in claim.line_items:
            combined = f"{item.code} {item.description}"

            if self.FLOORING_WORK_PATTERN.search(combined):
                has_flooring_work = True
                flooring_items.append(f"{item.code}: {item.description}")

            if self.CONTENT_MANIPULATION_PATTERN.search(combined):
                has_content_manipulation = True

            if self.BLOCKING_PADDING_PATTERN.search(combined):
                has_blocking_padding = True

        if has_flooring_work and not (has_content_manipulation or has_blocking_padding):
            findings.append(
                AuditFinding(
                    finding_id=self.engine.generate_finding_id(),
                    category=AuditCategory.SUPPLEMENT_RISK,
                    severity=AuditSeverity.INFO,
                    rule_name="Content Protection Check",
                    title="Missing Content Protection for Flooring Work",
                    description=(
                        "Flooring replacement found but no content manipulation or "
                        "blocking/padding charges. Furniture may need to be moved."
                    ),
                    affected_items=flooring_items,
                    evidence={
                        "flooring_work": has_flooring_work,
                        "content_manipulation": has_content_manipulation,
                        "blocking_padding": has_blocking_padding,
                    },
                    recommendation=(
                        "Verify if contents need to be moved or protected. "
                        "May result in supplement if not included."
                    ),
                )
            )

        return findings

    def _validate_labor_minimums(
        self, claim: ClaimData, context: dict[str, Any]
    ) -> list[AuditFinding]:
        """Check for multiple labor minimums for the same trade."""
        findings: list[AuditFinding] = []

        # Patterns for labor minimums by trade
        labor_min_patterns = {
            "plumber": re.compile(r"PLUMB.*MIN|MIN.*PLUMB", re.IGNORECASE),
            "electrician": re.compile(r"ELEC.*MIN|MIN.*ELEC", re.IGNORECASE),
            "hvac": re.compile(r"HVAC.*MIN|MIN.*HVAC", re.IGNORECASE),
            "general": re.compile(r"(LABOR|LBR).*MIN|MIN.*(LABOR|LBR)", re.IGNORECASE),
        }

        labor_minimums: dict[str, list[tuple[str, str, Decimal]]] = {
            trade: [] for trade in labor_min_patterns
        }

        for item in claim.line_items:
            combined = f"{item.code} {item.description}"

            for trade, pattern in labor_min_patterns.items():
                if pattern.search(combined):
                    labor_minimums[trade].append(
                        (item.code, item.description, item.total or Decimal("0"))
                    )

        for trade, items in labor_minimums.items():
            if len(items) > 1:
                total_minimums = sum(total for _, _, total in items)
                affected = [f"{code}: {desc}" for code, desc, _ in items]

                findings.append(
                    AuditFinding(
                        finding_id=self.engine.generate_finding_id(),
                        category=AuditCategory.LEAKAGE,
                        severity=AuditSeverity.WARNING,
                        rule_name="Labor Minimum Check",
                        title=f"Multiple {trade.title()} Labor Minimums",
                        description=(
                            f"Found {len(items)} labor minimum charges for {trade}. "
                            "Multiple minimums for the same trade may not be appropriate."
                        ),
                        affected_items=affected,
                        potential_impact=total_minimums - (items[0][2] if items else Decimal("0")),
                        evidence={
                            "trade": trade,
                            "minimum_count": len(items),
                        },
                        recommendation=(
                            "Review if multiple labor minimums are justified. "
                            "Typically only one minimum per trade per project."
                        ),
                    )
                )

        return findings

    def _validate_trade_coordination(
        self, claim: ClaimData, context: dict[str, Any]
    ) -> list[AuditFinding]:
        """Check for multiple trades that could coordinate."""
        findings: list[AuditFinding] = []

        # Look for service call / trip charge patterns
        service_call_pattern = re.compile(
            r"(SERVICE\s*CALL|TRIP\s*CHARGE|MOBILIZATION|SETUP)", re.IGNORECASE
        )

        service_calls: list[tuple[str, str, Decimal]] = []

        for item in claim.line_items:
            combined = f"{item.code} {item.description}"
            if service_call_pattern.search(combined):
                service_calls.append(
                    (item.code, item.description, item.total or Decimal("0"))
                )

        if len(service_calls) > 2:
            total_service = sum(total for _, _, total in service_calls)
            affected = [f"{code}: {desc}" for code, desc, _ in service_calls]

            findings.append(
                AuditFinding(
                    finding_id=self.engine.generate_finding_id(),
                    category=AuditCategory.LEAKAGE,
                    severity=AuditSeverity.INFO,
                    rule_name="Trade Coordination Check",
                    title="Multiple Service Calls",
                    description=(
                        f"Found {len(service_calls)} service call/trip charges. "
                        "Some trades may be able to coordinate visits."
                    ),
                    affected_items=affected,
                    potential_impact=total_service * Decimal("0.25"),  # Estimate 25% savings
                    evidence={
                        "service_call_count": len(service_calls),
                        "total_charges": str(total_service),
                    },
                    recommendation=(
                        "Review if any trades can combine visits to reduce "
                        "service call charges."
                    ),
                )
            )

        return findings

    def validate(self, claim: ClaimData) -> list[AuditFinding]:
        """Run all general repair validations on a claim."""
        return self.engine.execute_all(claim)

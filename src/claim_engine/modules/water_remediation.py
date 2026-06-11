"""
Phase 2: Water Remediation Module (WTR).
Audits equipment counts, monitoring labor, and category-based billing.
"""

import re
from decimal import Decimal
from typing import Any

from ..core.models import (
    AuditCategory,
    AuditFinding,
    AuditSeverity,
    ClaimData,
    WaterCategory,
)
from ..core.rule_engine import AuditRule, RuleEngine
from ..core.xactimate_parser import get_parser


class WaterRemediationValidator:
    """
    Validates water remediation claims for proper equipment,
    labor, and category-appropriate billing.
    """

    # Industry standards for equipment per square footage
    AIR_MOVER_SQFT_MIN = 50  # Minimum: 1 air mover per 50 sq ft
    AIR_MOVER_SQFT_MAX = 70  # Maximum: 1 air mover per 70 sq ft
    DEHUMIDIFIER_SQFT = 1000  # 1 dehumidifier per 1000 sq ft (approx)

    # Patterns for identifying WTR line items
    AIR_MOVER_PATTERN = re.compile(r"(AIR\s*MOVER|AIRF|FAN)", re.IGNORECASE)
    DEHUMIDIFIER_PATTERN = re.compile(r"(DEHUM|DEHU|DH\d*)", re.IGNORECASE)
    DAILY_MONITOR_PATTERN = re.compile(r"(DAILY\s*MONITOR|MONITOR.*DAILY|MOISTURE\s*READ)", re.IGNORECASE)
    PPE_CAT3_PATTERN = re.compile(r"(PPE|TYVEK|RESPIRATOR|HAZMAT|BIOHAZ)", re.IGNORECASE)
    CAT3_CLEANING_PATTERN = re.compile(r"(ANTIMICROBIAL|DISINFECT|SANITIZE|BIOCIDE)", re.IGNORECASE)

    def __init__(self, rule_engine: RuleEngine | None = None) -> None:
        self.engine = rule_engine or RuleEngine()
        self.parser = get_parser()
        self._register_rules()

    def _register_rules(self) -> None:
        """Register all water remediation rules."""
        # Equipment audit - Air Movers
        self.engine.add_rule(
            AuditRule(
                rule_id="WTR-001",
                name="Air Mover Count Audit",
                description="Verify air mover count against room square footage (1 per 50-70 sq ft)",
                category=AuditCategory.LEAKAGE,
                severity=AuditSeverity.WARNING,
                code_patterns=[r"^WTR.*AIR", r"AIRF", r"FAN"],
                validator=self._validate_air_movers,
            )
        )

        # Equipment audit - Dehumidifiers
        self.engine.add_rule(
            AuditRule(
                rule_id="WTR-002",
                name="Dehumidifier Count Audit",
                description="Verify dehumidifier count is appropriate for affected area",
                category=AuditCategory.LEAKAGE,
                severity=AuditSeverity.WARNING,
                code_patterns=[r"DEHUM", r"DEHU", r"DH\d+"],
                validator=self._validate_dehumidifiers,
            )
        )

        # Monitoring labor audit
        self.engine.add_rule(
            AuditRule(
                rule_id="WTR-003",
                name="Monitoring Labor Audit",
                description="Flag daily monitoring labor billed without corresponding equipment days",
                category=AuditCategory.LEAKAGE,
                severity=AuditSeverity.ERROR,
                code_patterns=[r"MONITOR", r"MOISTURE.*READ"],
                validator=self._validate_monitoring_labor,
            )
        )

        # Category logic - Cat 3 billing for Cat 1
        self.engine.add_rule(
            AuditRule(
                rule_id="WTR-004",
                name="Water Category Mismatch",
                description="Flag Category 3 (Black Water) PPE/cleaning billed for Category 1 (Clean Water) loss",
                category=AuditCategory.LEAKAGE,
                severity=AuditSeverity.ERROR,
                code_patterns=[r"PPE", r"HAZMAT", r"ANTIMICROBIAL"],
                validator=self._validate_category_billing,
            )
        )

            # Cat 2 — Black Water PPE billed on Gray Water loss
        self.engine.add_rule(
            AuditRule(
                rule_id="WTR-006",
                name="Cat 2 Black Water Upcharge",
                description="Flag Category 3 (Black Water) PPE/biohazard items billed for Category 2 (Gray Water) loss",
                category=AuditCategory.LEAKAGE,
                severity=AuditSeverity.WARNING,
                code_patterns=[r"PPE", r"HAZMAT", r"BIOHAZ", r"ANTIMICROBIAL"],
                validator=self._validate_cat2_upcharge,
            )
        )

        # Cat 2 — missing containment/antimicrobial
        self.engine.add_rule(
            AuditRule(
                rule_id="WTR-007",
                name="Cat 2 Missing Containment",
                description="Flag Category 2 (Gray Water) losses that lack containment or antimicrobial treatment",
                category=AuditCategory.SUPPLEMENT_RISK,
                severity=AuditSeverity.INFO,
                validator=self._validate_cat2_containment,
            )
        )

        # Equipment days vs labor days
        self.engine.add_rule(
            AuditRule(
                rule_id="WTR-005",
                name="Equipment Days Consistency",
                description="Verify equipment rental days are consistent across all equipment types",
                category=AuditCategory.LEAKAGE,
                severity=AuditSeverity.WARNING,
                validator=self._validate_equipment_days,
            )
        )

    def _validate_air_movers(
        self, claim: ClaimData, context: dict[str, Any]
    ) -> list[AuditFinding]:
        """Validate air mover count against square footage."""
        findings: list[AuditFinding] = []

        # Find air mover line items
        air_mover_count = 0
        air_mover_items: list[str] = []

        for item in claim.line_items:
            combined = f"{item.code} {item.description}"
            if self.AIR_MOVER_PATTERN.search(combined):
                air_mover_count += round(item.quantity)
                air_mover_items.append(f"{item.code}: {item.quantity}")

        if air_mover_count == 0:
            return findings

        # Get affected square footage
        total_sqft = claim.property_details.total_affected_sqft
        if not total_sqft or total_sqft <= 0:
            return findings

        # Calculate expected range
        min_expected = total_sqft / self.AIR_MOVER_SQFT_MAX
        max_expected = total_sqft / self.AIR_MOVER_SQFT_MIN

        import math
        # Use ceiling for expected max to avoid flagging borderline-legitimate counts
        expected_max_rounded = math.ceil(max_expected)
        if air_mover_count > expected_max_rounded * 1.2:  # 20% tolerance
            excess = air_mover_count - expected_max_rounded
            findings.append(
                AuditFinding(
                    finding_id=self.engine.generate_finding_id(),
                    category=AuditCategory.LEAKAGE,
                    severity=AuditSeverity.WARNING,
                    rule_name="Air Mover Count Audit",
                    title="Excessive Air Mover Count",
                    description=(
                        f"Billed {air_mover_count} air movers for {total_sqft:.0f} sq ft. "
                        f"Industry standard is 1 per 50-70 sq ft (expected {math.floor(min_expected)}-{expected_max_rounded})"
                    ),
                    affected_items=air_mover_items,
                    potential_impact=Decimal(str(excess * 35)),  # Approx $35/day per unit
                    evidence={
                        "air_mover_count": air_mover_count,
                        "affected_sqft": total_sqft,
                        "expected_min": int(min_expected),
                        "expected_max": int(max_expected),
                    },
                    recommendation="Review air mover count against actual affected area.",
                )
            )
        elif air_mover_count < min_expected * 0.5:  # Significantly under
            findings.append(
                AuditFinding(
                    finding_id=self.engine.generate_finding_id(),
                    category=AuditCategory.SUPPLEMENT_RISK,
                    severity=AuditSeverity.INFO,
                    rule_name="Air Mover Count Audit",
                    title="Low Air Mover Count",
                    description=(
                        f"Only {air_mover_count} air movers for {total_sqft:.0f} sq ft may be insufficient. "
                        f"Industry standard is 1 per 50-70 sq ft."
                    ),
                    affected_items=air_mover_items,
                    evidence={
                        "air_mover_count": air_mover_count,
                        "affected_sqft": total_sqft,
                    },
                    recommendation="Verify drying coverage is adequate for affected area.",
                )
            )

        return findings

    def _validate_dehumidifiers(
        self, claim: ClaimData, context: dict[str, Any]
    ) -> list[AuditFinding]:
        """Validate dehumidifier count against square footage."""
        findings: list[AuditFinding] = []

        # Find dehumidifier line items
        dehumidifier_count = 0
        dehumidifier_items: list[str] = []

        for item in claim.line_items:
            combined = f"{item.code} {item.description}"
            if self.DEHUMIDIFIER_PATTERN.search(combined):
                dehumidifier_count += round(item.quantity)
                dehumidifier_items.append(f"{item.code}: {item.quantity}")

        if dehumidifier_count == 0:
            return findings

        total_sqft = claim.property_details.total_affected_sqft
        if not total_sqft or total_sqft <= 0:
            return findings

        # Calculate expected (roughly 1 per 1000 sq ft, minimum 1)
        expected = max(1, total_sqft / self.DEHUMIDIFIER_SQFT)

        if dehumidifier_count > expected * 2:  # More than double expected
            findings.append(
                AuditFinding(
                    finding_id=self.engine.generate_finding_id(),
                    category=AuditCategory.LEAKAGE,
                    severity=AuditSeverity.WARNING,
                    rule_name="Dehumidifier Count Audit",
                    title="Excessive Dehumidifier Count",
                    description=(
                        f"Billed {dehumidifier_count} dehumidifiers for {total_sqft:.0f} sq ft. "
                        f"Typical is ~1 per 1000 sq ft (expected ~{int(expected)})"
                    ),
                    affected_items=dehumidifier_items,
                    evidence={
                        "dehumidifier_count": dehumidifier_count,
                        "affected_sqft": total_sqft,
                        "expected": int(expected),
                    },
                    recommendation="Review dehumidifier count against actual drying needs.",
                )
            )

        return findings

    def _validate_monitoring_labor(
        self, claim: ClaimData, context: dict[str, Any]
    ) -> list[AuditFinding]:
        """Validate monitoring labor against equipment days."""
        findings: list[AuditFinding] = []

        # Find monitoring labor items
        monitoring_days = 0
        monitoring_items: list[str] = []

        for item in claim.line_items:
            combined = f"{item.code} {item.description}"
            if self.DAILY_MONITOR_PATTERN.search(combined):
                monitoring_days += round(item.quantity)
                monitoring_items.append(f"{item.code}: {item.quantity} days")

        if monitoring_days == 0:
            return findings

        # Find equipment days (air movers or dehumidifiers).
        # IMPORTANT: equipment quantity = units placed, NOT days.
        # Reliable day counts require the item.days field to be populated.
        equipment_days = 0
        missing_days_items: list[str] = []
        for item in claim.line_items:
            combined = f"{item.code} {item.description}"
            if self.AIR_MOVER_PATTERN.search(combined) or self.DEHUMIDIFIER_PATTERN.search(combined):
                if item.days:
                    equipment_days = max(equipment_days, item.days)
                else:
                    # days field not populated — cannot reliably compare
                    missing_days_items.append(item.code)

        # If days are missing on equipment, flag as data quality issue and skip comparison
        if missing_days_items and monitoring_days > 0:
            findings.append(
                AuditFinding(
                    finding_id=self.engine.generate_finding_id(),
                    category=AuditCategory.LEAKAGE,
                    severity=AuditSeverity.INFO,
                    rule_name="Monitoring Labor Audit",
                    title="Equipment Days Not Documented",
                    description=(
                        f"{len(missing_days_items)} equipment line item(s) are missing the 'days' field. "
                        "Cannot validate monitoring labor against equipment rental period."
                    ),
                    affected_items=missing_days_items,
                    evidence={"missing_days_count": len(missing_days_items)},
                    recommendation="Ensure all equipment line items include the rental days field.",
                )
            )
            return findings

        if equipment_days == 0 and monitoring_days > 0:
            findings.append(
                AuditFinding(
                    finding_id=self.engine.generate_finding_id(),
                    category=AuditCategory.LEAKAGE,
                    severity=AuditSeverity.ERROR,
                    rule_name="Monitoring Labor Audit",
                    title="Monitoring Without Equipment",
                    description=(
                        f"Daily monitoring labor billed for {monitoring_days} days "
                        "but no drying equipment found on claim."
                    ),
                    affected_items=monitoring_items,
                    potential_impact=Decimal(str(monitoring_days * 75)),  # Approx cost
                    evidence={
                        "monitoring_days": monitoring_days,
                        "equipment_days": equipment_days,
                    },
                    recommendation="Verify equipment is properly documented or remove monitoring charges.",
                )
            )
        elif monitoring_days > equipment_days + 2:  # Allow 2 day variance
            excess_days = monitoring_days - equipment_days
            findings.append(
                AuditFinding(
                    finding_id=self.engine.generate_finding_id(),
                    category=AuditCategory.LEAKAGE,
                    severity=AuditSeverity.WARNING,
                    rule_name="Monitoring Labor Audit",
                    title="Excess Monitoring Days",
                    description=(
                        f"Monitoring labor ({monitoring_days} days) exceeds equipment days ({equipment_days}). "
                        "Monitoring should align with active drying period."
                    ),
                    affected_items=monitoring_items,
                    potential_impact=Decimal(str(excess_days * 75)),
                    evidence={
                        "monitoring_days": monitoring_days,
                        "equipment_days": equipment_days,
                        "excess_days": excess_days,
                    },
                    recommendation="Align monitoring days with equipment rental period.",
                )
            )

        return findings

    def _validate_category_billing(
        self, claim: ClaimData, context: dict[str, Any]
    ) -> list[AuditFinding]:
        """Validate category-appropriate billing (Cat 3 vs Cat 1)."""
        findings: list[AuditFinding] = []

        water_category = claim.property_details.water_category
        if water_category is None:
            return findings

        # If Category 1 (clean water), flag Cat 3 specific items
        if water_category == WaterCategory.CATEGORY_1:
            cat3_items: list[str] = []
            cat3_total = Decimal("0")

            for item in claim.line_items:
                combined = f"{item.code} {item.description}"
                if self.PPE_CAT3_PATTERN.search(combined) or self.CAT3_CLEANING_PATTERN.search(combined):
                    cat3_items.append(f"{item.code}: {item.description}")
                    if item.total:
                        cat3_total += item.total

            if cat3_items:
                findings.append(
                    AuditFinding(
                        finding_id=self.engine.generate_finding_id(),
                        category=AuditCategory.LEAKAGE,
                        severity=AuditSeverity.ERROR,
                        rule_name="Water Category Mismatch",
                        title="Category 3 Items Billed for Category 1 Loss",
                        description=(
                            f"Claim is documented as Category 1 (Clean Water) but includes "
                            f"{len(cat3_items)} Category 3 (Black Water) PPE/cleaning items."
                        ),
                        affected_items=cat3_items,
                        potential_impact=cat3_total,
                        evidence={
                            "documented_category": water_category.value,
                            "flagged_item_count": len(cat3_items),
                        },
                        recommendation=(
                            "Verify water category classification or remove "
                            "Category 3-specific charges."
                        ),
                    )
                )

        return findings

    def _validate_equipment_days(
        self, claim: ClaimData, context: dict[str, Any]
    ) -> list[AuditFinding]:
        """Validate equipment days are consistent across equipment types."""
        findings: list[AuditFinding] = []

        equipment_days_by_type: dict[str, int] = {}

        for item in claim.line_items:
            combined = f"{item.code} {item.description}"

            equip_type = None
            if self.AIR_MOVER_PATTERN.search(combined):
                equip_type = "air_mover"
            elif self.DEHUMIDIFIER_PATTERN.search(combined):
                equip_type = "dehumidifier"

            if equip_type:
                days = item.days if item.days else int(item.quantity)
                equipment_days_by_type[equip_type] = max(
                    equipment_days_by_type.get(equip_type, 0), days
                )

        if len(equipment_days_by_type) > 1:
            days_values = list(equipment_days_by_type.values())
            max_diff = max(days_values) - min(days_values)

            if max_diff > 2:  # More than 2 day difference
                findings.append(
                    AuditFinding(
                        finding_id=self.engine.generate_finding_id(),
                        category=AuditCategory.LEAKAGE,
                        severity=AuditSeverity.INFO,
                        rule_name="Equipment Days Consistency",
                        title="Inconsistent Equipment Days",
                        description=(
                            f"Equipment days vary by {max_diff} days across equipment types. "
                            "Typically all drying equipment runs for the same duration."
                        ),
                        evidence=equipment_days_by_type,
                        recommendation="Verify equipment days are accurate for each type.",
                    )
                )

        return findings

    def _validate_cat2_upcharge(
        self, claim: ClaimData, context: dict[str, Any]
    ) -> list[AuditFinding]:
        """Flag Cat 3 PPE/biohazard items on a documented Cat 2 loss."""
        findings: list[AuditFinding] = []

        water_category = claim.property_details.water_category
        if water_category != WaterCategory.CATEGORY_2:
            return findings

        # Cat 3-specific items that are not appropriate for gray water
        cat3_only_pattern = re.compile(
            r"(BIOHAZ|HAZMAT|TYVEK|FULL\s*FACE|RESPIRATOR|SEWAGE\s*CLEAN)", re.IGNORECASE
        )
        flagged: list[str] = []
        flagged_total = Decimal("0")

        for item in claim.line_items:
            combined = f"{item.code} {item.description}"
            if cat3_only_pattern.search(combined):
                flagged.append(f"{item.code}: {item.description}")
                if item.total:
                    flagged_total += item.total

        if flagged:
            findings.append(
                AuditFinding(
                    finding_id=self.engine.generate_finding_id(),
                    category=AuditCategory.LEAKAGE,
                    severity=AuditSeverity.WARNING,
                    rule_name="Cat 2 Black Water Upcharge",
                    title="Category 3 Items Billed for Category 2 Loss",
                    description=(
                        f"Claim is documented as Category 2 (Gray Water) but includes "
                        f"{len(flagged)} biohazard/Category 3-specific item(s). "
                        "Verify if contamination escalated scope to Cat 3."
                    ),
                    affected_items=flagged,
                    potential_impact=flagged_total,
                    evidence={
                        "documented_category": water_category.value,
                        "flagged_item_count": len(flagged),
                    },
                    recommendation=(
                        "Confirm water category classification. If scope was escalated to Cat 3, "
                        "update the documented water category accordingly."
                    ),
                )
            )

        return findings

    def _validate_cat2_containment(
        self, claim: ClaimData, context: dict[str, Any]
    ) -> list[AuditFinding]:
        """Flag Cat 2 losses missing containment or antimicrobial treatment."""
        findings: list[AuditFinding] = []

        water_category = claim.property_details.water_category
        if water_category != WaterCategory.CATEGORY_2:
            return findings

        containment_pattern = re.compile(
            r"(CONTAINMENT|BARRIER|POLY\s*BARRIER|CRITICAL\s*BARRIER)", re.IGNORECASE
        )
        antimicrobial_pattern = re.compile(
            r"(ANTIMICROBIAL|DISINFECT|SANITIZE|BIOCIDE|MICROBIAL\s*TREAT)", re.IGNORECASE
        )

        has_containment = False
        has_antimicrobial = False

        for item in claim.line_items:
            combined = f"{item.code} {item.description}"
            if containment_pattern.search(combined):
                has_containment = True
            if antimicrobial_pattern.search(combined):
                has_antimicrobial = True

        missing: list[str] = []
        if not has_containment:
            missing.append("containment barrier")
        if not has_antimicrobial:
            missing.append("antimicrobial treatment")

        if missing:
            findings.append(
                AuditFinding(
                    finding_id=self.engine.generate_finding_id(),
                    category=AuditCategory.SUPPLEMENT_RISK,
                    severity=AuditSeverity.INFO,
                    rule_name="Cat 2 Missing Containment",
                    title="Cat 2 Loss Missing Standard Remediation Items",
                    description=(
                        f"Category 2 (Gray Water) loss is missing: {', '.join(missing)}. "
                        "IICRC S500 guidelines recommend both for gray water losses."
                    ),
                    evidence={
                        "has_containment": has_containment,
                        "has_antimicrobial": has_antimicrobial,
                        "missing_items": missing,
                    },
                    recommendation=(
                        "Verify if containment and antimicrobial application were performed. "
                        "If so, add appropriate line items to prevent supplements."
                    ),
                )
            )

        return findings

    def validate(self, claim: ClaimData) -> list[AuditFinding]:
        """Run only WTR-series rules against the claim."""
        wtr_rule_ids = [rid for rid in self.engine._rules if rid.startswith("WTR-")]
        findings: list[AuditFinding] = []
        for rid in wtr_rule_ids:
            rule = self.engine.get_rule(rid)
            if rule:
                findings.extend(self.engine.execute_rule(rule, claim))
        return findings

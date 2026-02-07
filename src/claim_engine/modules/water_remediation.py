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
                air_mover_count += int(item.quantity)
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

        if air_mover_count > max_expected * 1.2:  # 20% tolerance
            excess = air_mover_count - int(max_expected)
            findings.append(
                AuditFinding(
                    finding_id=self.engine.generate_finding_id(),
                    category=AuditCategory.LEAKAGE,
                    severity=AuditSeverity.WARNING,
                    rule_name="Air Mover Count Audit",
                    title="Excessive Air Mover Count",
                    description=(
                        f"Billed {air_mover_count} air movers for {total_sqft:.0f} sq ft. "
                        f"Industry standard is 1 per 50-70 sq ft (expected {int(min_expected)}-{int(max_expected)})"
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
                dehumidifier_count += int(item.quantity)
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
                monitoring_days += int(item.quantity)
                monitoring_items.append(f"{item.code}: {item.quantity} days")

        if monitoring_days == 0:
            return findings

        # Find equipment days (air movers or dehumidifiers)
        equipment_days = 0
        for item in claim.line_items:
            combined = f"{item.code} {item.description}"
            if self.AIR_MOVER_PATTERN.search(combined) or self.DEHUMIDIFIER_PATTERN.search(combined):
                # Equipment is typically billed as quantity * days
                if item.days:
                    equipment_days = max(equipment_days, item.days)
                else:
                    # If no days field, estimate from description or assume quantity is total days
                    equipment_days = max(equipment_days, int(item.quantity))

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

    def validate(self, claim: ClaimData) -> list[AuditFinding]:
        """Run all water remediation validations on a claim."""
        return self.engine.execute_all(claim)

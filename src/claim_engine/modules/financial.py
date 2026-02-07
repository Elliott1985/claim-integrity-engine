"""
Phase 1: Financial & Policy Validation Module.
Validates deductibles, coverage limits, and sub-limits.
"""

from decimal import Decimal
from typing import Any

from ..core.models import (
    AuditCategory,
    AuditFinding,
    AuditSeverity,
    ClaimData,
)
from ..core.rule_engine import AuditRule, RuleEngine


class FinancialValidator:
    """
    Validates financial aspects of insurance claims against policy terms.
    """

    def __init__(self, rule_engine: RuleEngine | None = None) -> None:
        self.engine = rule_engine or RuleEngine()
        self._register_rules()

    def _register_rules(self) -> None:
        """Register all financial validation rules."""
        # Deductible validation
        self.engine.add_rule(
            AuditRule(
                rule_id="FIN-001",
                name="Deductible Application",
                description="Verify deductible is correctly applied to net claim",
                category=AuditCategory.FINANCIAL,
                severity=AuditSeverity.ERROR,
                validator=self._validate_deductible,
            )
        )

        # Coverage A limit
        self.engine.add_rule(
            AuditRule(
                rule_id="FIN-002",
                name="Coverage A Limit",
                description="Verify dwelling coverage (Coverage A) limit is not exceeded",
                category=AuditCategory.FINANCIAL,
                severity=AuditSeverity.CRITICAL,
                validator=self._validate_coverage_a,
            )
        )

        # Coverage B limit
        self.engine.add_rule(
            AuditRule(
                rule_id="FIN-003",
                name="Coverage B Limit",
                description="Verify other structures coverage (Coverage B) limit is not exceeded",
                category=AuditCategory.FINANCIAL,
                severity=AuditSeverity.ERROR,
                validator=self._validate_coverage_b,
            )
        )

        # Coverage C limit
        self.engine.add_rule(
            AuditRule(
                rule_id="FIN-004",
                name="Coverage C Limit",
                description="Verify personal property coverage (Coverage C) limit is not exceeded",
                category=AuditCategory.FINANCIAL,
                severity=AuditSeverity.ERROR,
                validator=self._validate_coverage_c,
            )
        )

        # Water damage sub-limit
        self.engine.add_rule(
            AuditRule(
                rule_id="FIN-005",
                name="Water Damage Sub-Limit",
                description="Verify water damage sub-limit is not exceeded",
                category=AuditCategory.FINANCIAL,
                severity=AuditSeverity.WARNING,
                validator=self._validate_water_sublimit,
            )
        )

        # Mold sub-limit
        self.engine.add_rule(
            AuditRule(
                rule_id="FIN-006",
                name="Mold Sub-Limit",
                description="Verify mold remediation sub-limit is not exceeded",
                category=AuditCategory.FINANCIAL,
                severity=AuditSeverity.WARNING,
                validator=self._validate_mold_sublimit,
            )
        )

        # Net claim calculation
        self.engine.add_rule(
            AuditRule(
                rule_id="FIN-007",
                name="Net Claim Calculation",
                description="Verify net claim is correctly calculated (gross - deductible)",
                category=AuditCategory.FINANCIAL,
                severity=AuditSeverity.ERROR,
                validator=self._validate_net_claim,
            )
        )

    def _validate_deductible(
        self, claim: ClaimData, context: dict[str, Any]
    ) -> list[AuditFinding]:
        """Validate that deductible is properly applied."""
        findings: list[AuditFinding] = []

        if claim.policy.deductible <= 0:
            findings.append(
                AuditFinding(
                    finding_id=self.engine.generate_finding_id(),
                    category=AuditCategory.FINANCIAL,
                    severity=AuditSeverity.WARNING,
                    rule_name="Deductible Application",
                    title="Zero or Missing Deductible",
                    description="Policy shows zero or no deductible. Verify this is correct.",
                    evidence={"deductible": str(claim.policy.deductible)},
                    recommendation="Confirm policy terms show $0 deductible or update claim data.",
                )
            )

        return findings

    def _validate_coverage_a(
        self, claim: ClaimData, context: dict[str, Any]
    ) -> list[AuditFinding]:
        """Validate dwelling coverage limit."""
        findings: list[AuditFinding] = []

        # Calculate dwelling-related charges
        dwelling_codes = ["DRY", "PNT", "DEM", "WTR", "FCC", "FNC", "GEN"]
        dwelling_total = Decimal("0")

        for item in claim.line_items:
            code_prefix = item.code[:3].upper() if len(item.code) >= 3 else item.code.upper()
            if code_prefix in dwelling_codes and item.total:
                dwelling_total += item.total

        if dwelling_total > claim.policy.coverage_a:
            overage = dwelling_total - claim.policy.coverage_a
            findings.append(
                AuditFinding(
                    finding_id=self.engine.generate_finding_id(),
                    category=AuditCategory.FINANCIAL,
                    severity=AuditSeverity.CRITICAL,
                    rule_name="Coverage A Limit",
                    title="Coverage A Limit Exceeded",
                    description=(
                        f"Dwelling repairs total ${dwelling_total:,.2f} exceeds "
                        f"Coverage A limit of ${claim.policy.coverage_a:,.2f}"
                    ),
                    potential_impact=overage,
                    evidence={
                        "dwelling_total": str(dwelling_total),
                        "coverage_a_limit": str(claim.policy.coverage_a),
                        "overage": str(overage),
                    },
                    recommendation="Review scope or discuss coverage limits with adjuster.",
                )
            )

        return findings

    def _validate_coverage_b(
        self, claim: ClaimData, context: dict[str, Any]
    ) -> list[AuditFinding]:
        """Validate other structures coverage limit."""
        findings: list[AuditFinding] = []

        # Look for other structures items (detached garage, fence, shed, etc.)
        other_structures_keywords = ["detached", "garage", "fence", "shed", "outbuilding"]
        other_structures_total = Decimal("0")

        for item in claim.line_items:
            desc_lower = item.description.lower()
            if any(kw in desc_lower for kw in other_structures_keywords) and item.total:
                other_structures_total += item.total

        if other_structures_total > claim.policy.coverage_b:
            overage = other_structures_total - claim.policy.coverage_b
            findings.append(
                AuditFinding(
                    finding_id=self.engine.generate_finding_id(),
                    category=AuditCategory.FINANCIAL,
                    severity=AuditSeverity.ERROR,
                    rule_name="Coverage B Limit",
                    title="Coverage B Limit Exceeded",
                    description=(
                        f"Other structures total ${other_structures_total:,.2f} exceeds "
                        f"Coverage B limit of ${claim.policy.coverage_b:,.2f}"
                    ),
                    potential_impact=overage,
                    evidence={
                        "other_structures_total": str(other_structures_total),
                        "coverage_b_limit": str(claim.policy.coverage_b),
                    },
                    recommendation="Review other structures scope or policy limits.",
                )
            )

        return findings

    def _validate_coverage_c(
        self, claim: ClaimData, context: dict[str, Any]
    ) -> list[AuditFinding]:
        """Validate personal property coverage limit."""
        findings: list[AuditFinding] = []

        # Look for contents/personal property items
        contents_total = Decimal("0")
        for item in claim.line_items:
            code_upper = item.code.upper()
            if code_upper.startswith("CNT") and item.total:
                contents_total += item.total

        if contents_total > claim.policy.coverage_c:
            overage = contents_total - claim.policy.coverage_c
            findings.append(
                AuditFinding(
                    finding_id=self.engine.generate_finding_id(),
                    category=AuditCategory.FINANCIAL,
                    severity=AuditSeverity.ERROR,
                    rule_name="Coverage C Limit",
                    title="Coverage C Limit Exceeded",
                    description=(
                        f"Personal property total ${contents_total:,.2f} exceeds "
                        f"Coverage C limit of ${claim.policy.coverage_c:,.2f}"
                    ),
                    potential_impact=overage,
                    evidence={
                        "contents_total": str(contents_total),
                        "coverage_c_limit": str(claim.policy.coverage_c),
                    },
                    recommendation="Review contents inventory or policy limits.",
                )
            )

        return findings

    def _validate_water_sublimit(
        self, claim: ClaimData, context: dict[str, Any]
    ) -> list[AuditFinding]:
        """Validate water damage sub-limit if applicable."""
        findings: list[AuditFinding] = []

        if claim.policy.water_damage_limit is None:
            return findings

        water_total = Decimal("0")
        for item in claim.line_items:
            code_upper = item.code.upper()
            if code_upper.startswith("WTR") and item.total:
                water_total += item.total

        if water_total > claim.policy.water_damage_limit:
            overage = water_total - claim.policy.water_damage_limit
            findings.append(
                AuditFinding(
                    finding_id=self.engine.generate_finding_id(),
                    category=AuditCategory.FINANCIAL,
                    severity=AuditSeverity.WARNING,
                    rule_name="Water Damage Sub-Limit",
                    title="Water Damage Sub-Limit Exceeded",
                    description=(
                        f"Water remediation total ${water_total:,.2f} exceeds "
                        f"sub-limit of ${claim.policy.water_damage_limit:,.2f}"
                    ),
                    potential_impact=overage,
                    evidence={
                        "water_total": str(water_total),
                        "sublimit": str(claim.policy.water_damage_limit),
                    },
                    recommendation="Review water damage scope against policy sub-limits.",
                )
            )

        return findings

    def _validate_mold_sublimit(
        self, claim: ClaimData, context: dict[str, Any]
    ) -> list[AuditFinding]:
        """Validate mold remediation sub-limit if applicable."""
        findings: list[AuditFinding] = []

        if claim.policy.mold_limit is None:
            return findings

        mold_keywords = ["mold", "fungus", "microbial"]
        mold_total = Decimal("0")

        for item in claim.line_items:
            desc_lower = item.description.lower()
            if any(kw in desc_lower for kw in mold_keywords) and item.total:
                mold_total += item.total

        if mold_total > claim.policy.mold_limit:
            overage = mold_total - claim.policy.mold_limit
            findings.append(
                AuditFinding(
                    finding_id=self.engine.generate_finding_id(),
                    category=AuditCategory.FINANCIAL,
                    severity=AuditSeverity.WARNING,
                    rule_name="Mold Sub-Limit",
                    title="Mold Remediation Sub-Limit Exceeded",
                    description=(
                        f"Mold remediation total ${mold_total:,.2f} exceeds "
                        f"sub-limit of ${claim.policy.mold_limit:,.2f}"
                    ),
                    potential_impact=overage,
                    evidence={
                        "mold_total": str(mold_total),
                        "sublimit": str(claim.policy.mold_limit),
                    },
                    recommendation="Review mold remediation scope against policy sub-limits.",
                )
            )

        return findings

    def _validate_net_claim(
        self, claim: ClaimData, context: dict[str, Any]
    ) -> list[AuditFinding]:
        """Validate net claim calculation."""
        findings: list[AuditFinding] = []

        if claim.gross_claim is None or claim.net_claim is None:
            return findings

        expected_net = max(Decimal("0"), claim.gross_claim - claim.policy.deductible)
        tolerance = Decimal("0.01")

        if abs(claim.net_claim - expected_net) > tolerance:
            findings.append(
                AuditFinding(
                    finding_id=self.engine.generate_finding_id(),
                    category=AuditCategory.FINANCIAL,
                    severity=AuditSeverity.ERROR,
                    rule_name="Net Claim Calculation",
                    title="Net Claim Calculation Error",
                    description=(
                        f"Net claim ${claim.net_claim:,.2f} does not match expected "
                        f"${expected_net:,.2f} (gross ${claim.gross_claim:,.2f} - "
                        f"deductible ${claim.policy.deductible:,.2f})"
                    ),
                    evidence={
                        "stated_net": str(claim.net_claim),
                        "expected_net": str(expected_net),
                        "gross_claim": str(claim.gross_claim),
                        "deductible": str(claim.policy.deductible),
                    },
                    recommendation="Recalculate net claim amount.",
                )
            )

        return findings

    def validate(self, claim: ClaimData) -> list[AuditFinding]:
        """Run all financial validations on a claim."""
        return self.engine.execute_category(AuditCategory.FINANCIAL, claim)

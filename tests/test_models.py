"""
Tests for core data models.
"""

from decimal import Decimal

import pytest

from claim_engine.core.models import (
    AuditCategory,
    AuditFinding,
    AuditScorecard,
    AuditSeverity,
    ClaimData,
    LineItem,
    PolicyCoverage,
    PropertyDetails,
    Room,
    WaterCategory,
)


class TestLineItem:
    """Tests for LineItem model."""

    def test_total_calculation(self) -> None:
        """Test automatic total calculation."""
        item = LineItem(
            code="TEST",
            description="Test Item",
            quantity=10,
            unit_price=Decimal("5.00"),
        )
        assert item.total == Decimal("50.00")

    def test_explicit_total(self) -> None:
        """Test explicit total override."""
        item = LineItem(
            code="TEST",
            description="Test Item",
            quantity=10,
            unit_price=Decimal("5.00"),
            total=Decimal("100.00"),
        )
        assert item.total == Decimal("100.00")


class TestPolicyCoverage:
    """Tests for PolicyCoverage model."""

    def test_coverage_limits(self) -> None:
        """Test policy coverage creation."""
        policy = PolicyCoverage(
            deductible=Decimal("1000"),
            coverage_a=Decimal("250000"),
            coverage_b=Decimal("25000"),
            coverage_c=Decimal("125000"),
        )
        assert policy.deductible == Decimal("1000")
        assert policy.coverage_a == Decimal("250000")


class TestPropertyDetails:
    """Tests for PropertyDetails model."""

    def test_sqft_calculation(self) -> None:
        """Test automatic square footage calculation."""
        details = PropertyDetails(
            affected_rooms=[
                Room(name="Room1", sqft=100),
                Room(name="Room2", sqft=200),
            ]
        )
        assert details.total_affected_sqft == 300

    def test_sqft_excludes_unaffected(self) -> None:
        """Test that unaffected rooms are excluded."""
        details = PropertyDetails(
            affected_rooms=[
                Room(name="Room1", sqft=100, affected=True),
                Room(name="Room2", sqft=200, affected=False),
            ]
        )
        assert details.total_affected_sqft == 100


class TestClaimData:
    """Tests for ClaimData model."""

    def test_gross_claim_calculation(self) -> None:
        """Test automatic gross claim calculation."""
        claim = ClaimData(
            claim_id="TEST-001",
            policy=PolicyCoverage(
                deductible=Decimal("1000"),
                coverage_a=Decimal("100000"),
                coverage_b=Decimal("10000"),
                coverage_c=Decimal("50000"),
            ),
            line_items=[
                LineItem(
                    code="A",
                    description="Item A",
                    quantity=1,
                    unit_price=Decimal("500"),
                ),
                LineItem(
                    code="B",
                    description="Item B",
                    quantity=2,
                    unit_price=Decimal("250"),
                ),
            ],
        )
        assert claim.gross_claim == Decimal("1000")
        assert claim.net_claim == Decimal("0")  # Gross - Deductible

    def test_net_claim_with_positive_result(self) -> None:
        """Test net claim when gross exceeds deductible."""
        claim = ClaimData(
            claim_id="TEST-002",
            policy=PolicyCoverage(
                deductible=Decimal("500"),
                coverage_a=Decimal("100000"),
                coverage_b=Decimal("10000"),
                coverage_c=Decimal("50000"),
            ),
            line_items=[
                LineItem(
                    code="A",
                    description="Item A",
                    quantity=1,
                    unit_price=Decimal("2000"),
                ),
            ],
        )
        assert claim.gross_claim == Decimal("2000")
        assert claim.net_claim == Decimal("1500")


class TestAuditScorecard:
    """Tests for AuditScorecard model."""

    def test_add_finding(self) -> None:
        """Test adding findings to scorecard."""
        scorecard = AuditScorecard(claim_id="TEST-001")

        finding = AuditFinding(
            finding_id="FND-001",
            category=AuditCategory.LEAKAGE,
            severity=AuditSeverity.WARNING,
            rule_name="Test Rule",
            title="Test Finding",
            description="Test description",
            potential_impact=Decimal("100"),
        )

        scorecard.add_finding(finding)

        assert scorecard.summary.total_findings == 1
        assert scorecard.summary.leakage_findings == 1
        assert scorecard.summary.total_potential_leakage == Decimal("100")

    def test_risk_score_calculation(self) -> None:
        """Test risk score calculation."""
        scorecard = AuditScorecard(claim_id="TEST-001")

        # Add findings of different severities
        for severity in [AuditSeverity.INFO, AuditSeverity.WARNING, AuditSeverity.ERROR]:
            finding = AuditFinding(
                finding_id=f"FND-{severity.value}",
                category=AuditCategory.LEAKAGE,
                severity=severity,
                rule_name="Test Rule",
                title="Test Finding",
                description="Test description",
            )
            scorecard.add_finding(finding)

        score = scorecard.calculate_risk_score()
        assert score > 0
        assert score <= 100

"""
Tests for the main ClaimIntegrityEngine.
"""

from decimal import Decimal

import pytest

from claim_engine import (
    ClaimData,
    ClaimIntegrityEngine,
    LineItem,
    PolicyCoverage,
    PropertyDetails,
    Room,
    WaterCategory,
    audit_claim,
)


@pytest.fixture
def sample_claim() -> ClaimData:
    """Create a sample claim for testing."""
    return ClaimData(
        claim_id="TEST-CLM-001",
        policy=PolicyCoverage(
            deductible=Decimal("1000"),
            coverage_a=Decimal("250000"),
            coverage_b=Decimal("25000"),
            coverage_c=Decimal("125000"),
        ),
        line_items=[
            LineItem(
                code="WTR_AIRF",
                description="Air Mover",
                quantity=5,
                unit_price=Decimal("35.00"),
            ),
            LineItem(
                code="WTR_DEHUM",
                description="Dehumidifier",
                quantity=2,
                unit_price=Decimal("75.00"),
            ),
        ],
        property_details=PropertyDetails(
            affected_rooms=[
                Room(name="Living Room", sqft=250),
            ],
            water_category=WaterCategory.CATEGORY_1,
        ),
    )


class TestClaimIntegrityEngine:
    """Tests for ClaimIntegrityEngine."""

    def test_engine_initialization(self) -> None:
        """Test engine initializes with default settings."""
        engine = ClaimIntegrityEngine()

        assert engine.enable_financial is True
        assert engine.enable_water_remediation is True
        assert engine.enable_flooring is True
        assert engine.enable_general_repair is True
        assert engine.auto_redact_pii is False

    def test_engine_configuration(self) -> None:
        """Test engine configuration method."""
        engine = ClaimIntegrityEngine()
        engine.configure(
            enable_financial=False,
            auto_redact_pii=True,
        )

        assert engine.enable_financial is False
        assert engine.auto_redact_pii is True

    def test_get_enabled_modules(self) -> None:
        """Test getting list of enabled modules."""
        engine = ClaimIntegrityEngine()
        modules = engine.get_enabled_modules()

        assert "Financial Validation" in modules
        assert "Water Remediation (WTR)" in modules
        assert "Flooring (FCC/FNC)" in modules
        assert "General Repair" in modules

    def test_audit_returns_scorecard(self, sample_claim: ClaimData) -> None:
        """Test that audit returns a valid scorecard."""
        engine = ClaimIntegrityEngine()
        scorecard = engine.audit(sample_claim)

        assert scorecard.claim_id == "TEST-CLM-001"
        assert len(scorecard.modules_executed) > 0

    def test_audit_from_dict(self) -> None:
        """Test auditing from dictionary input."""
        engine = ClaimIntegrityEngine()

        claim_dict = {
            "claim_id": "DICT-001",
            "policy": {
                "deductible": 500,
                "coverage_a": 100000,
                "coverage_b": 10000,
                "coverage_c": 50000,
            },
            "line_items": [
                {
                    "code": "TEST",
                    "description": "Test Item",
                    "quantity": 1,
                    "unit_price": 100,
                }
            ],
        }

        scorecard = engine.audit(claim_dict)
        assert scorecard.claim_id == "DICT-001"

    def test_audit_with_pii_redaction(self, sample_claim: ClaimData) -> None:
        """Test audit with PII redaction enabled."""
        engine = ClaimIntegrityEngine()
        scorecard = engine.audit(sample_claim, redact_pii=True)

        assert scorecard.redacted is True

    def test_audit_with_formatter(self, sample_claim: ClaimData) -> None:
        """Test audit_with_formatter returns formatter."""
        engine = ClaimIntegrityEngine()
        formatter = engine.audit_with_formatter(sample_claim)

        # Should be able to get various output formats
        text = formatter.to_text()
        assert "CLAIM INTEGRITY AUDIT SCORECARD" in text

        json_output = formatter.to_json()
        assert "claim_id" in json_output

    def test_selective_module_execution(self, sample_claim: ClaimData) -> None:
        """Test running with only specific modules."""
        engine = ClaimIntegrityEngine(
            enable_financial=True,
            enable_water_remediation=False,
            enable_flooring=False,
            enable_general_repair=False,
        )

        scorecard = engine.audit(sample_claim)

        assert "Financial Validation" in scorecard.modules_executed
        assert "Water Remediation (WTR)" not in scorecard.modules_executed


class TestAuditClaimFunction:
    """Tests for the convenience audit_claim function."""

    def test_audit_claim_basic(self, sample_claim: ClaimData) -> None:
        """Test basic usage of audit_claim function."""
        scorecard = audit_claim(sample_claim)

        assert scorecard.claim_id == "TEST-CLM-001"
        assert scorecard.redacted is False

    def test_audit_claim_with_redaction(self, sample_claim: ClaimData) -> None:
        """Test audit_claim with PII redaction."""
        scorecard = audit_claim(sample_claim, redact_pii=True)

        assert scorecard.redacted is True

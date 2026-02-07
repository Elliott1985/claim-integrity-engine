"""
Core data models for the Claim Integrity Engine.
Uses Pydantic for validation and serialization.
"""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class WaterCategory(int, Enum):
    """Water damage categories per IICRC S500 standard."""

    CATEGORY_1 = 1  # Clean water
    CATEGORY_2 = 2  # Gray water
    CATEGORY_3 = 3  # Black water (sewage/contaminated)


class AuditCategory(str, Enum):
    """Categories for audit findings."""

    FINANCIAL = "financial"
    LEAKAGE = "leakage"
    SUPPLEMENT_RISK = "supplement_risk"


class AuditSeverity(str, Enum):
    """Severity levels for audit findings."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class Room(BaseModel):
    """Room details for property assessment."""

    name: str
    sqft: float = Field(gt=0, description="Square footage of the room")
    room_type: str = "standard"
    floor_type: str | None = None
    affected: bool = True


class LineItem(BaseModel):
    """Individual line item from an estimate/invoice."""

    code: str = Field(description="Xactimate or proprietary code")
    description: str
    quantity: float = Field(ge=0)
    unit: str = "EA"
    unit_price: Decimal = Field(ge=0)
    total: Decimal | None = None
    category: str | None = None
    room: str | None = None
    days: int | None = None  # For equipment rental items

    def model_post_init(self, __context: Any) -> None:
        """Calculate total if not provided."""
        if self.total is None:
            self.total = Decimal(str(self.quantity)) * self.unit_price


class PolicyCoverage(BaseModel):
    """Insurance policy coverage details."""

    deductible: Decimal = Field(ge=0)
    coverage_a: Decimal = Field(ge=0, description="Dwelling coverage")
    coverage_b: Decimal = Field(ge=0, description="Other structures")
    coverage_c: Decimal = Field(ge=0, description="Personal property")
    coverage_d: Decimal | None = Field(default=None, description="Loss of use")

    # Sub-limits
    water_damage_limit: Decimal | None = None
    mold_limit: Decimal | None = None
    contents_limit: Decimal | None = None


class PropertyDetails(BaseModel):
    """Property-specific details for the claim."""

    affected_rooms: list[Room] = Field(default_factory=list)
    water_category: WaterCategory | None = None
    total_affected_sqft: float | None = None
    property_type: str = "residential"

    def model_post_init(self, __context: Any) -> None:
        """Calculate total affected sqft if not provided."""
        if self.total_affected_sqft is None and self.affected_rooms:
            self.total_affected_sqft = sum(
                room.sqft for room in self.affected_rooms if room.affected
            )


class ClaimData(BaseModel):
    """Complete claim data for auditing."""

    claim_id: str
    claim_date: datetime | None = None
    policy: PolicyCoverage
    line_items: list[LineItem] = Field(default_factory=list)
    property_details: PropertyDetails = Field(default_factory=PropertyDetails)
    gross_claim: Decimal | None = None
    net_claim: Decimal | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    def model_post_init(self, __context: Any) -> None:
        """Calculate claim totals if not provided."""
        if self.gross_claim is None and self.line_items:
            self.gross_claim = sum(
                item.total for item in self.line_items if item.total is not None
            )
        if self.net_claim is None and self.gross_claim is not None:
            self.net_claim = max(
                Decimal("0"), self.gross_claim - self.policy.deductible
            )


class AuditFinding(BaseModel):
    """Individual audit finding/flag."""

    finding_id: str
    category: AuditCategory
    severity: AuditSeverity
    rule_name: str
    title: str
    description: str
    affected_items: list[str] = Field(default_factory=list)
    potential_impact: Decimal | None = None
    recommendation: str | None = None
    evidence: dict[str, Any] = Field(default_factory=dict)


class AuditSummary(BaseModel):
    """Summary statistics for an audit."""

    total_findings: int = 0
    financial_findings: int = 0
    leakage_findings: int = 0
    supplement_risk_findings: int = 0
    total_potential_leakage: Decimal = Decimal("0")
    total_supplement_risk: Decimal = Decimal("0")
    risk_score: float = 0.0  # 0-100 scale


class AuditScorecard(BaseModel):
    """Complete audit scorecard output."""

    claim_id: str
    audit_timestamp: datetime = Field(default_factory=datetime.utcnow)
    claim_summary: dict[str, Any] = Field(default_factory=dict)
    findings: list[AuditFinding] = Field(default_factory=list)
    summary: AuditSummary = Field(default_factory=AuditSummary)
    modules_executed: list[str] = Field(default_factory=list)
    redacted: bool = False

    def add_finding(self, finding: AuditFinding) -> None:
        """Add a finding and update summary statistics."""
        self.findings.append(finding)
        self.summary.total_findings += 1

        if finding.category == AuditCategory.FINANCIAL:
            self.summary.financial_findings += 1
        elif finding.category == AuditCategory.LEAKAGE:
            self.summary.leakage_findings += 1
            if finding.potential_impact:
                self.summary.total_potential_leakage += finding.potential_impact
        elif finding.category == AuditCategory.SUPPLEMENT_RISK:
            self.summary.supplement_risk_findings += 1
            if finding.potential_impact:
                self.summary.total_supplement_risk += finding.potential_impact

    def calculate_risk_score(self) -> float:
        """Calculate overall risk score (0-100)."""
        if not self.findings:
            self.summary.risk_score = 0.0
            return 0.0

        severity_weights = {
            AuditSeverity.INFO: 5,
            AuditSeverity.WARNING: 15,
            AuditSeverity.ERROR: 30,
            AuditSeverity.CRITICAL: 50,
        }

        total_weight = sum(
            severity_weights.get(f.severity, 10) for f in self.findings
        )

        # Normalize to 0-100 scale (cap at 100)
        self.summary.risk_score = min(100.0, total_weight)
        return self.summary.risk_score

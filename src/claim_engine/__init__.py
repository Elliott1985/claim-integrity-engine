"""
Universal Claim Integrity & Leakage Engine.

A modular insurance claim auditing system for detecting billing
discrepancies, policy violations, and leakage risks.
"""

from .core.models import (
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
from .engine import ClaimIntegrityEngine, audit_claim
from .reporting.scorecard import ScorecardBuilder, ScorecardFormatter
from .utils.pii_redaction import PIIRedactor, redact_pii

__version__ = "0.1.0"

__all__ = [
    # Main Engine
    "ClaimIntegrityEngine",
    "audit_claim",
    # Models
    "AuditCategory",
    "AuditFinding",
    "AuditScorecard",
    "AuditSeverity",
    "ClaimData",
    "LineItem",
    "PolicyCoverage",
    "PropertyDetails",
    "Room",
    "WaterCategory",
    # Reporting
    "ScorecardBuilder",
    "ScorecardFormatter",
    # Utils
    "PIIRedactor",
    "redact_pii",
]

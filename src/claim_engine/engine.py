"""
Claim Integrity Engine - Main Orchestrator.
Coordinates all audit modules to perform comprehensive claim audits.
"""

from typing import Any

from .core.models import AuditFinding, AuditScorecard, ClaimData
from .core.rule_engine import RuleEngine
from .modules.financial import FinancialValidator
from .modules.flooring import FlooringValidator
from .modules.general_repair import GeneralRepairValidator
from .modules.water_remediation import WaterRemediationValidator
from .reporting.scorecard import ScorecardBuilder, ScorecardFormatter
from .utils.pii_redaction import PIIRedactor


class ClaimIntegrityEngine:
    """
    Main orchestrator for the Universal Claim Integrity & Leakage Engine.

    Coordinates all audit modules and generates comprehensive scorecards.
    """

    def __init__(
        self,
        enable_financial: bool = True,
        enable_water_remediation: bool = True,
        enable_flooring: bool = True,
        enable_general_repair: bool = True,
        auto_redact_pii: bool = False,
    ) -> None:
        """
        Initialize the Claim Integrity Engine.

        Args:
            enable_financial: Enable financial validation module
            enable_water_remediation: Enable water remediation audit module
            enable_flooring: Enable flooring audit module
            enable_general_repair: Enable general repair audit module
            auto_redact_pii: Automatically redact PII from output
        """
        self.enable_financial = enable_financial
        self.enable_water_remediation = enable_water_remediation
        self.enable_flooring = enable_flooring
        self.enable_general_repair = enable_general_repair
        self.auto_redact_pii = auto_redact_pii

        # Initialize validators lazily
        self._financial_validator: FinancialValidator | None = None
        self._water_remediation_validator: WaterRemediationValidator | None = None
        self._flooring_validator: FlooringValidator | None = None
        self._general_repair_validator: GeneralRepairValidator | None = None
        self._pii_redactor: PIIRedactor | None = None

    @property
    def financial_validator(self) -> FinancialValidator:
        """Get or create the financial validator."""
        if self._financial_validator is None:
            self._financial_validator = FinancialValidator()
        return self._financial_validator

    @property
    def water_remediation_validator(self) -> WaterRemediationValidator:
        """Get or create the water remediation validator."""
        if self._water_remediation_validator is None:
            self._water_remediation_validator = WaterRemediationValidator()
        return self._water_remediation_validator

    @property
    def flooring_validator(self) -> FlooringValidator:
        """Get or create the flooring validator."""
        if self._flooring_validator is None:
            self._flooring_validator = FlooringValidator()
        return self._flooring_validator

    @property
    def general_repair_validator(self) -> GeneralRepairValidator:
        """Get or create the general repair validator."""
        if self._general_repair_validator is None:
            self._general_repair_validator = GeneralRepairValidator()
        return self._general_repair_validator

    @property
    def pii_redactor(self) -> PIIRedactor:
        """Get or create the PII redactor."""
        if self._pii_redactor is None:
            self._pii_redactor = PIIRedactor()
        return self._pii_redactor

    def audit(
        self,
        claim: ClaimData | dict[str, Any],
        redact_pii: bool | None = None,
    ) -> AuditScorecard:
        """
        Perform a comprehensive audit on a claim.

        Args:
            claim: The claim data to audit (ClaimData or dict)
            redact_pii: Override PII redaction setting (None uses default)

        Returns:
            Complete audit scorecard with all findings
        """
        # Convert dict to ClaimData if needed
        if isinstance(claim, dict):
            claim = ClaimData.model_validate(claim)

        # Build scorecard
        builder = ScorecardBuilder(claim)
        all_findings: list[AuditFinding] = []

        # Phase 1: Financial Validation
        if self.enable_financial:
            findings = self.financial_validator.validate(claim)
            all_findings.extend(findings)
            builder.add_module("Financial Validation")

        # Phase 2: Water Remediation
        if self.enable_water_remediation:
            findings = self.water_remediation_validator.validate(claim)
            all_findings.extend(findings)
            builder.add_module("Water Remediation (WTR)")

        # Phase 3: Flooring
        if self.enable_flooring:
            findings = self.flooring_validator.validate(claim)
            all_findings.extend(findings)
            builder.add_module("Flooring (FCC/FNC)")

        # Phase 4: General Repair
        if self.enable_general_repair:
            findings = self.general_repair_validator.validate(claim)
            all_findings.extend(findings)
            builder.add_module("General Repair")

        # Add all findings and build scorecard
        builder.add_findings(all_findings)
        scorecard = builder.build()

        # Apply PII redaction if enabled
        should_redact = redact_pii if redact_pii is not None else self.auto_redact_pii
        if should_redact:
            scorecard = self.pii_redactor.redact_scorecard(scorecard)

        return scorecard

    def audit_with_formatter(
        self,
        claim: ClaimData | dict[str, Any],
        redact_pii: bool | None = None,
    ) -> ScorecardFormatter:
        """
        Perform audit and return a formatter for output.

        Args:
            claim: The claim data to audit
            redact_pii: Override PII redaction setting

        Returns:
            ScorecardFormatter for flexible output formatting
        """
        scorecard = self.audit(claim, redact_pii)
        return ScorecardFormatter(scorecard)

    def get_enabled_modules(self) -> list[str]:
        """Get list of enabled modules."""
        modules = []
        if self.enable_financial:
            modules.append("Financial Validation")
        if self.enable_water_remediation:
            modules.append("Water Remediation (WTR)")
        if self.enable_flooring:
            modules.append("Flooring (FCC/FNC)")
        if self.enable_general_repair:
            modules.append("General Repair")
        return modules

    def configure(
        self,
        enable_financial: bool | None = None,
        enable_water_remediation: bool | None = None,
        enable_flooring: bool | None = None,
        enable_general_repair: bool | None = None,
        auto_redact_pii: bool | None = None,
    ) -> "ClaimIntegrityEngine":
        """
        Configure the engine settings.

        Args:
            enable_financial: Enable/disable financial validation
            enable_water_remediation: Enable/disable water remediation audit
            enable_flooring: Enable/disable flooring audit
            enable_general_repair: Enable/disable general repair audit
            auto_redact_pii: Enable/disable automatic PII redaction

        Returns:
            Self for method chaining
        """
        if enable_financial is not None:
            self.enable_financial = enable_financial
        if enable_water_remediation is not None:
            self.enable_water_remediation = enable_water_remediation
        if enable_flooring is not None:
            self.enable_flooring = enable_flooring
        if enable_general_repair is not None:
            self.enable_general_repair = enable_general_repair
        if auto_redact_pii is not None:
            self.auto_redact_pii = auto_redact_pii
        return self


# Convenience function for quick audits
def audit_claim(
    claim: ClaimData | dict[str, Any],
    redact_pii: bool = False,
) -> AuditScorecard:
    """
    Convenience function for quick claim audits.

    Args:
        claim: The claim data to audit
        redact_pii: Whether to redact PII from output

    Returns:
        Complete audit scorecard
    """
    engine = ClaimIntegrityEngine(auto_redact_pii=redact_pii)
    return engine.audit(claim)

"""
Audit Scorecard Reporting Module.
Generates comprehensive audit reports and scorecards.
"""

import json
from datetime import datetime
from decimal import Decimal
from typing import Any

from ..core.models import (
    AuditCategory,
    AuditFinding,
    AuditScorecard,
    AuditSeverity,
    ClaimData,
)


class ScorecardFormatter:
    """
    Formats audit scorecards for various output formats.
    """

    SEVERITY_ICONS = {
        AuditSeverity.INFO: "ℹ️",
        AuditSeverity.WARNING: "⚠️",
        AuditSeverity.ERROR: "❌",
        AuditSeverity.CRITICAL: "🚨",
    }

    CATEGORY_LABELS = {
        AuditCategory.FINANCIAL: "Financial Validation",
        AuditCategory.LEAKAGE: "Potential Leakage",
        AuditCategory.SUPPLEMENT_RISK: "Supplement Risk",
    }

    def __init__(self, scorecard: AuditScorecard) -> None:
        self.scorecard = scorecard

    def to_text(self, include_details: bool = True) -> str:
        """
        Format scorecard as plain text report.

        Args:
            include_details: Whether to include detailed findings

        Returns:
            Formatted text report
        """
        lines: list[str] = []

        # Header
        lines.append("=" * 70)
        lines.append("CLAIM INTEGRITY AUDIT SCORECARD")
        lines.append("=" * 70)
        lines.append("")

        # Claim info
        lines.append(f"Claim ID: {self.scorecard.claim_id}")
        lines.append(f"Audit Date: {self.scorecard.audit_timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        if self.scorecard.redacted:
            lines.append("*** PII REDACTED FOR COMPLIANCE ***")
        lines.append("")

        # Summary section
        lines.append("-" * 70)
        lines.append("SUMMARY")
        lines.append("-" * 70)
        summary = self.scorecard.summary
        lines.append(f"Total Findings: {summary.total_findings}")
        lines.append(f"  - Financial: {summary.financial_findings}")
        lines.append(f"  - Leakage: {summary.leakage_findings}")
        lines.append(f"  - Supplement Risk: {summary.supplement_risk_findings}")
        lines.append("")
        lines.append(f"Potential Leakage Amount: ${summary.total_potential_leakage:,.2f}")
        lines.append(f"Potential Supplement Risk: ${summary.total_supplement_risk:,.2f}")
        lines.append(f"Risk Score: {summary.risk_score:.1f}/100")
        lines.append("")

        # Modules executed
        if self.scorecard.modules_executed:
            lines.append(f"Modules Executed: {', '.join(self.scorecard.modules_executed)}")
            lines.append("")

        # Findings by category
        if include_details and self.scorecard.findings:
            for category in AuditCategory:
                category_findings = [
                    f for f in self.scorecard.findings if f.category == category
                ]
                if category_findings:
                    lines.append("-" * 70)
                    lines.append(self.CATEGORY_LABELS[category].upper())
                    lines.append("-" * 70)

                    for finding in category_findings:
                        lines.append("")
                        lines.append(
                            f"{self.SEVERITY_ICONS.get(finding.severity, '•')} "
                            f"[{finding.severity.value.upper()}] {finding.title}"
                        )
                        lines.append(f"   Rule: {finding.rule_name}")
                        lines.append(f"   {finding.description}")

                        if finding.potential_impact:
                            lines.append(f"   Potential Impact: ${finding.potential_impact:,.2f}")

                        if finding.affected_items:
                            lines.append("   Affected Items:")
                            for item in finding.affected_items[:5]:  # Limit to 5
                                lines.append(f"     - {item}")
                            if len(finding.affected_items) > 5:
                                lines.append(f"     ... and {len(finding.affected_items) - 5} more")

                        if finding.recommendation:
                            lines.append(f"   Recommendation: {finding.recommendation}")

                    lines.append("")

        # Footer
        lines.append("=" * 70)
        lines.append("END OF REPORT")
        lines.append("=" * 70)

        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        """
        Convert scorecard to dictionary format.

        Returns:
            Dictionary representation of the scorecard
        """

        def serialize_value(v: Any) -> Any:
            if isinstance(v, Decimal):
                return float(v)
            elif isinstance(v, datetime):
                return v.isoformat()
            elif hasattr(v, "value"):  # Enum
                return v.value
            return v

        def serialize_dict(d: dict[str, Any]) -> dict[str, Any]:
            return {k: serialize_value(v) for k, v in d.items()}

        findings_list = []
        for f in self.scorecard.findings:
            finding_dict = {
                "finding_id": f.finding_id,
                "category": f.category.value,
                "severity": f.severity.value,
                "rule_name": f.rule_name,
                "title": f.title,
                "description": f.description,
                "affected_items": f.affected_items,
                "potential_impact": float(f.potential_impact) if f.potential_impact else None,
                "recommendation": f.recommendation,
                "evidence": serialize_dict(f.evidence) if f.evidence else {},
            }
            findings_list.append(finding_dict)

        return {
            "claim_id": self.scorecard.claim_id,
            "audit_timestamp": self.scorecard.audit_timestamp.isoformat(),
            "redacted": self.scorecard.redacted,
            "summary": {
                "total_findings": self.scorecard.summary.total_findings,
                "financial_findings": self.scorecard.summary.financial_findings,
                "leakage_findings": self.scorecard.summary.leakage_findings,
                "supplement_risk_findings": self.scorecard.summary.supplement_risk_findings,
                "total_potential_leakage": float(self.scorecard.summary.total_potential_leakage),
                "total_supplement_risk": float(self.scorecard.summary.total_supplement_risk),
                "risk_score": self.scorecard.summary.risk_score,
            },
            "modules_executed": self.scorecard.modules_executed,
            "findings": findings_list,
            "claim_summary": serialize_dict(self.scorecard.claim_summary),
        }

    def to_json(self, indent: int = 2) -> str:
        """
        Convert scorecard to JSON format.

        Args:
            indent: JSON indentation level

        Returns:
            JSON string representation
        """
        return json.dumps(self.to_dict(), indent=indent)

    def to_html(self) -> str:
        """
        Convert scorecard to HTML format.

        Returns:
            HTML string representation
        """
        severity_colors = {
            AuditSeverity.INFO: "#17a2b8",
            AuditSeverity.WARNING: "#ffc107",
            AuditSeverity.ERROR: "#dc3545",
            AuditSeverity.CRITICAL: "#721c24",
        }

        html_parts: list[str] = []

        # Header
        html_parts.append("""
        <div class="audit-scorecard" style="font-family: Arial, sans-serif; max-width: 900px; margin: 0 auto;">
            <style>
                .finding-card { border: 1px solid #ddd; border-radius: 4px; margin: 10px 0; padding: 15px; }
                .summary-box { background: #f8f9fa; padding: 20px; border-radius: 4px; margin: 20px 0; }
                .metric { display: inline-block; margin-right: 30px; }
                .metric-value { font-size: 24px; font-weight: bold; }
                .metric-label { color: #666; font-size: 12px; }
            </style>
        """)

        # Title
        html_parts.append(f"""
            <h1>Claim Integrity Audit Scorecard</h1>
            <p><strong>Claim ID:</strong> {self.scorecard.claim_id}</p>
            <p><strong>Audit Date:</strong> {self.scorecard.audit_timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}</p>
        """)

        if self.scorecard.redacted:
            html_parts.append('<p style="color: #dc3545;"><strong>⚠️ PII REDACTED FOR COMPLIANCE</strong></p>')

        # Summary
        summary = self.scorecard.summary
        html_parts.append(f"""
            <div class="summary-box">
                <h2>Summary</h2>
                <div class="metric">
                    <div class="metric-value">{summary.total_findings}</div>
                    <div class="metric-label">Total Findings</div>
                </div>
                <div class="metric">
                    <div class="metric-value" style="color: #dc3545;">${summary.total_potential_leakage:,.2f}</div>
                    <div class="metric-label">Potential Leakage</div>
                </div>
                <div class="metric">
                    <div class="metric-value" style="color: #ffc107;">${summary.total_supplement_risk:,.2f}</div>
                    <div class="metric-label">Supplement Risk</div>
                </div>
                <div class="metric">
                    <div class="metric-value">{summary.risk_score:.1f}</div>
                    <div class="metric-label">Risk Score (0-100)</div>
                </div>
            </div>
        """)

        # Findings by category
        for category in AuditCategory:
            category_findings = [f for f in self.scorecard.findings if f.category == category]
            if category_findings:
                html_parts.append(f"<h2>{self.CATEGORY_LABELS[category]}</h2>")

                for finding in category_findings:
                    color = severity_colors.get(finding.severity, "#666")
                    html_parts.append(f"""
                        <div class="finding-card" style="border-left: 4px solid {color};">
                            <h3 style="margin-top: 0; color: {color};">
                                {self.SEVERITY_ICONS.get(finding.severity, '•')} {finding.title}
                            </h3>
                            <p><strong>Rule:</strong> {finding.rule_name}</p>
                            <p>{finding.description}</p>
                    """)

                    if finding.potential_impact:
                        html_parts.append(f"<p><strong>Potential Impact:</strong> ${finding.potential_impact:,.2f}</p>")

                    if finding.recommendation:
                        html_parts.append(f"<p><strong>Recommendation:</strong> {finding.recommendation}</p>")

                    html_parts.append("</div>")

        html_parts.append("</div>")

        return "\n".join(html_parts)

    def print_summary(self) -> None:
        """Print a brief summary to stdout."""
        print(self.to_text(include_details=False))

    def print_full(self) -> None:
        """Print the full report to stdout."""
        print(self.to_text(include_details=True))


class ScorecardBuilder:
    """
    Builder for constructing audit scorecards.
    """

    def __init__(self, claim: ClaimData) -> None:
        self.claim = claim
        self.scorecard = AuditScorecard(
            claim_id=claim.claim_id,
            claim_summary={
                "gross_claim": str(claim.gross_claim) if claim.gross_claim else None,
                "net_claim": str(claim.net_claim) if claim.net_claim else None,
                "line_item_count": len(claim.line_items),
                "deductible": str(claim.policy.deductible),
            },
        )

    def add_finding(self, finding: AuditFinding) -> "ScorecardBuilder":
        """Add a finding to the scorecard."""
        self.scorecard.add_finding(finding)
        return self

    def add_findings(self, findings: list[AuditFinding]) -> "ScorecardBuilder":
        """Add multiple findings to the scorecard."""
        for finding in findings:
            self.scorecard.add_finding(finding)
        return self

    def add_module(self, module_name: str) -> "ScorecardBuilder":
        """Record that a module was executed."""
        if module_name not in self.scorecard.modules_executed:
            self.scorecard.modules_executed.append(module_name)
        return self

    def calculate_risk(self) -> "ScorecardBuilder":
        """Calculate the risk score."""
        self.scorecard.calculate_risk_score()
        return self

    def build(self) -> AuditScorecard:
        """Build and return the final scorecard."""
        self.calculate_risk()
        return self.scorecard

    def get_formatter(self) -> ScorecardFormatter:
        """Get a formatter for the built scorecard."""
        return ScorecardFormatter(self.build())

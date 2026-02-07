"""
Claim Integrity Engine - Streamlit Dashboard.
Professional UI for auditing Xactimate estimates.
"""

import json
from decimal import Decimal
from typing import Any

import pandas as pd
import streamlit as st

from claim_engine import (
    AuditCategory,
    AuditScorecard,
    AuditSeverity,
    ClaimData,
    ClaimIntegrityEngine,
    ScorecardFormatter,
)
from claim_engine.utils.pii_redaction import PIIRedactor


# =============================================================================
# Page Configuration
# =============================================================================
st.set_page_config(
    page_title="Claim Integrity Auditor",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS for professional styling
st.markdown(
    """
    <style>
    .main-header {
        font-size: 2.5rem;
        font-weight: 700;
        color: #1E3A5F;
        margin-bottom: 0.5rem;
    }
    .sub-header {
        font-size: 1rem;
        color: #6B7280;
        margin-bottom: 2rem;
    }
    .kpi-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1.5rem;
        border-radius: 12px;
        color: white;
        text-align: center;
    }
    .kpi-value {
        font-size: 2.5rem;
        font-weight: 700;
    }
    .kpi-label {
        font-size: 0.875rem;
        opacity: 0.9;
    }
    .leakage-value {
        color: #EF4444 !important;
        font-weight: 700;
    }
    .risk-low { color: #10B981; }
    .risk-medium { color: #F59E0B; }
    .risk-high { color: #EF4444; }
    .stMetric > div {
        background-color: #F8FAFC;
        padding: 1rem;
        border-radius: 8px;
        border: 1px solid #E2E8F0;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# =============================================================================
# Helper Functions
# =============================================================================
def parse_uploaded_file(uploaded_file) -> dict[str, Any] | None:
    """Parse uploaded JSON or CSV file into claim data format."""
    if uploaded_file is None:
        return None

    try:
        if uploaded_file.name.endswith(".json"):
            content = uploaded_file.read().decode("utf-8")
            return json.loads(content)
        elif uploaded_file.name.endswith(".csv"):
            df = pd.read_csv(uploaded_file)
            return convert_csv_to_claim_data(df)
        else:
            st.error("Unsupported file format. Please upload JSON or CSV.")
            return None
    except Exception as e:
        st.error(f"Error parsing file: {str(e)}")
        return None


def convert_csv_to_claim_data(df: pd.DataFrame) -> dict[str, Any]:
    """Convert CSV DataFrame to claim data format."""
    line_items = []
    for _, row in df.iterrows():
        item = {
            "code": str(row.get("code", row.get("Code", "UNKNOWN"))),
            "description": str(row.get("description", row.get("Description", ""))),
            "quantity": float(row.get("quantity", row.get("Quantity", 1))),
            "unit_price": float(row.get("unit_price", row.get("Unit Price", 0))),
        }
        if "room" in row or "Room" in row:
            item["room"] = str(row.get("room", row.get("Room")))
        line_items.append(item)

    return {
        "claim_id": "UPLOADED-CLAIM",
        "policy": {
            "deductible": 1000,
            "coverage_a": 250000,
            "coverage_b": 25000,
            "coverage_c": 125000,
        },
        "line_items": line_items,
        "property_details": {
            "affected_rooms": [{"name": "Uploaded Area", "sqft": 500}],
        },
    }


def calculate_financial_accuracy(scorecard: AuditScorecard) -> float:
    """Calculate financial accuracy score (100 - risk_score)."""
    return max(0, 100 - scorecard.summary.risk_score)


def get_risk_level(scorecard: AuditScorecard) -> tuple[str, str]:
    """Determine supplement risk level based on findings."""
    supplement_count = scorecard.summary.supplement_risk_findings
    if supplement_count == 0:
        return "Low", "risk-low"
    elif supplement_count <= 2:
        return "Medium", "risk-medium"
    else:
        return "High", "risk-high"


def run_audit(data: dict[str, Any], claim_type: str, redact_pii: bool) -> AuditScorecard:
    """
    Run the audit using the Claim Integrity Engine.

    Args:
        data: Claim data dictionary
        claim_type: Type of claim (Water, Roof, Flooring)
        redact_pii: Whether to redact PII from results

    Returns:
        AuditScorecard with all findings
    """
    # Configure engine based on claim type
    engine = ClaimIntegrityEngine(
        enable_financial=True,
        enable_water_remediation=(claim_type == "Water"),
        enable_flooring=(claim_type in ["Water", "Flooring"]),
        enable_general_repair=True,
        auto_redact_pii=redact_pii,
    )

    # Set water category based on claim type
    if "property_details" not in data:
        data["property_details"] = {}
    if claim_type == "Water" and "water_category" not in data.get("property_details", {}):
        data["property_details"]["water_category"] = 1

    return engine.audit(data)


def create_cost_comparison_chart(scorecard: AuditScorecard) -> pd.DataFrame:
    """Create data for estimated vs audited cost comparison."""
    # Calculate totals from claim summary
    gross_claim = float(scorecard.claim_summary.get("gross_claim", 0) or 0)
    leakage = float(scorecard.summary.total_potential_leakage)

    return pd.DataFrame(
        {
            "Category": ["Estimated Cost", "Audited Cost", "Potential Savings"],
            "Amount": [gross_claim, gross_claim - leakage, leakage],
        }
    )


# =============================================================================
# Sidebar
# =============================================================================
with st.sidebar:
    st.image(
        "https://img.icons8.com/fluency/96/audit.png",
        width=64,
    )
    st.title("Claim Auditor")
    st.markdown("---")

    # File Uploader
    st.subheader("📁 Upload Estimate")
    uploaded_file = st.file_uploader(
        "Upload Xactimate JSON/CSV",
        type=["json", "csv"],
        help="Upload your Xactimate estimate export file",
    )

    st.markdown("---")

    # Claim Type Selection
    st.subheader("⚙️ Audit Settings")
    claim_type = st.selectbox(
        "Claim Type",
        options=["Water", "Roof", "Flooring"],
        help="Select the type of claim to optimize audit rules",
    )

    # PII Protection Toggle
    st.markdown("---")
    st.subheader("🔒 Privacy Settings")
    hide_pii = st.toggle(
        "Hide Sensitive Data",
        value=False,
        help="Enable PII redaction for SOC2 compliance",
    )

    st.markdown("---")

    # Run Audit Button
    run_audit_btn = st.button(
        "🔍 Run Audit",
        type="primary",
        use_container_width=True,
        disabled=uploaded_file is None,
    )

    # Demo Mode
    st.markdown("---")
    st.caption("Or try with sample data:")
    demo_btn = st.button("📊 Run Demo Audit", use_container_width=True)


# =============================================================================
# Main Content
# =============================================================================
st.markdown('<p class="main-header">🔍 Claim Integrity Auditor</p>', unsafe_allow_html=True)
st.markdown(
    '<p class="sub-header">Automated audit system for detecting billing discrepancies and leakage risks</p>',
    unsafe_allow_html=True,
)

# Initialize session state
if "scorecard" not in st.session_state:
    st.session_state.scorecard = None
if "claim_data" not in st.session_state:
    st.session_state.claim_data = None

# Handle Demo Button
if demo_btn:
    st.session_state.claim_data = {
        "claim_id": "DEMO-2024-WTR-001",
        "policy": {
            "deductible": 1000,
            "coverage_a": 250000,
            "coverage_b": 25000,
            "coverage_c": 125000,
        },
        "line_items": [
            {"code": "WTR_AIRF", "description": "Air Mover - per unit/day", "quantity": 12, "unit_price": 35.00},
            {"code": "WTR_DEHUM", "description": "Dehumidifier - Large", "quantity": 3, "unit_price": 75.00},
            {"code": "WTR_MONITOR", "description": "Daily Monitoring - Technician", "quantity": 7, "unit_price": 85.00},
            {"code": "WTR_PPE", "description": "PPE - Tyvek Suits, Respirators", "quantity": 10, "unit_price": 45.00},
            {"code": "FCC_CPTREM", "description": "Tear out Carpet", "quantity": 300, "unit_price": 0.85},
            {"code": "FCC_PADREM", "description": "Tear out Pad", "quantity": 300, "unit_price": 0.35},
            {"code": "FCC_CPTINST", "description": "Install Carpet", "quantity": 300, "unit_price": 4.50},
            {"code": "GEN_DOOR", "description": "Pre-hung Interior Door", "quantity": 2, "unit_price": 285.00},
            {"code": "GEN_HINGE", "description": "Door Hinges - 3.5 inch", "quantity": 6, "unit_price": 8.50},
            {"code": "DEM_DRYWALL", "description": "Demo Drywall", "quantity": 200, "unit_price": 1.25},
        ],
        "property_details": {
            "affected_rooms": [
                {"name": "Living Room", "sqft": 300},
                {"name": "Kitchen", "sqft": 150},
            ],
            "water_category": 1,
        },
    }
    st.session_state.scorecard = run_audit(st.session_state.claim_data, "Water", hide_pii)

# Handle Run Audit Button
if run_audit_btn and uploaded_file is not None:
    with st.spinner("Analyzing estimate..."):
        claim_data = parse_uploaded_file(uploaded_file)
        if claim_data:
            st.session_state.claim_data = claim_data
            st.session_state.scorecard = run_audit(claim_data, claim_type, hide_pii)

# Display Results
if st.session_state.scorecard is not None:
    scorecard = st.session_state.scorecard

    # ==========================================================================
    # KPI Section
    # ==========================================================================
    st.markdown("### 📊 Key Performance Indicators")

    kpi1, kpi2, kpi3, kpi4 = st.columns(4)

    with kpi1:
        accuracy = calculate_financial_accuracy(scorecard)
        st.metric(
            label="Financial Accuracy",
            value=f"{accuracy:.0f}/100",
            delta=f"{accuracy - 70:.0f} vs benchmark" if accuracy >= 70 else f"{accuracy - 70:.0f} below benchmark",
            delta_color="normal" if accuracy >= 70 else "inverse",
        )

    with kpi2:
        leakage = scorecard.summary.total_potential_leakage
        st.metric(
            label="🚨 Total Leakage Found",
            value=f"${leakage:,.2f}",
            delta=f"{scorecard.summary.leakage_findings} issues",
            delta_color="inverse" if leakage > 0 else "off",
        )

    with kpi3:
        risk_level, risk_class = get_risk_level(scorecard)
        st.metric(
            label="Supplement Risk",
            value=risk_level,
            delta=f"{scorecard.summary.supplement_risk_findings} flags",
        )

    with kpi4:
        st.metric(
            label="Total Findings",
            value=scorecard.summary.total_findings,
            delta=f"Risk Score: {scorecard.summary.risk_score:.0f}",
        )

    st.markdown("---")

    # ==========================================================================
    # Main Audit Results
    # ==========================================================================
    col1, col2 = st.columns([2, 1])

    with col1:
        st.markdown("### 📋 Audit Scorecard")

        # Group findings by category
        financial_findings = [f for f in scorecard.findings if f.category == AuditCategory.FINANCIAL]
        leakage_findings = [f for f in scorecard.findings if f.category == AuditCategory.LEAKAGE]
        supplement_findings = [f for f in scorecard.findings if f.category == AuditCategory.SUPPLEMENT_RISK]

        # Financial Findings
        if financial_findings:
            st.markdown("#### 💰 Financial Validation")
            for finding in financial_findings:
                if finding.severity == AuditSeverity.CRITICAL:
                    st.error(f"**{finding.title}**\n\n{finding.description}")
                elif finding.severity == AuditSeverity.ERROR:
                    st.error(f"**{finding.title}**\n\n{finding.description}")
                elif finding.severity == AuditSeverity.WARNING:
                    st.warning(f"**{finding.title}**\n\n{finding.description}")
                else:
                    st.info(f"**{finding.title}**\n\n{finding.description}")

        # Leakage Findings
        if leakage_findings:
            st.markdown("#### 🔴 Potential Leakage")
            for finding in leakage_findings:
                impact_str = f" • **Impact: ${finding.potential_impact:,.2f}**" if finding.potential_impact else ""
                if finding.severity in [AuditSeverity.CRITICAL, AuditSeverity.ERROR]:
                    st.error(f"**{finding.title}**{impact_str}\n\n{finding.description}")
                else:
                    st.warning(f"**{finding.title}**{impact_str}\n\n{finding.description}")

        # Supplement Risk Findings
        if supplement_findings:
            st.markdown("#### ⚠️ Supplement Risk")
            for finding in supplement_findings:
                st.warning(f"**{finding.title}**\n\n{finding.description}\n\n*Recommendation: {finding.recommendation}*")

        # Success message if no critical issues
        if not financial_findings and not leakage_findings:
            st.success("✅ **All checks passed!** No significant issues detected in this estimate.")

    with col2:
        st.markdown("### 📈 Cost Analysis")

        # Create cost comparison chart
        chart_data = create_cost_comparison_chart(scorecard)

        # Use Streamlit's native bar chart
        st.bar_chart(
            chart_data.set_index("Category"),
            height=300,
        )

        # Summary stats
        st.markdown("#### 📊 Summary")
        gross = float(scorecard.claim_summary.get("gross_claim", 0) or 0)
        leakage_amt = float(scorecard.summary.total_potential_leakage)

        st.markdown(
            f"""
            | Metric | Value |
            |--------|-------|
            | **Gross Claim** | ${gross:,.2f} |
            | **Potential Leakage** | ${leakage_amt:,.2f} |
            | **Adjusted Estimate** | ${gross - leakage_amt:,.2f} |
            | **Savings %** | {(leakage_amt / gross * 100) if gross > 0 else 0:.1f}% |
            """
        )

    st.markdown("---")

    # ==========================================================================
    # Detailed Findings Table
    # ==========================================================================
    with st.expander("📑 View Detailed Findings Table", expanded=False):
        if scorecard.findings:
            findings_data = []
            for f in scorecard.findings:
                findings_data.append(
                    {
                        "ID": f.finding_id,
                        "Category": f.category.value.replace("_", " ").title(),
                        "Severity": f.severity.value.upper(),
                        "Rule": f.rule_name,
                        "Title": f.title,
                        "Impact": f"${f.potential_impact:,.2f}" if f.potential_impact else "-",
                    }
                )
            st.dataframe(
                pd.DataFrame(findings_data),
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("No findings to display.")

    # ==========================================================================
    # Export Options
    # ==========================================================================
    st.markdown("### 📤 Export Results")
    exp1, exp2, exp3 = st.columns(3)

    formatter = ScorecardFormatter(scorecard)

    with exp1:
        st.download_button(
            label="📄 Download JSON",
            data=formatter.to_json(),
            file_name=f"audit_{scorecard.claim_id}.json",
            mime="application/json",
        )

    with exp2:
        st.download_button(
            label="📝 Download Text Report",
            data=formatter.to_text(),
            file_name=f"audit_{scorecard.claim_id}.txt",
            mime="text/plain",
        )

    with exp3:
        st.download_button(
            label="🌐 Download HTML",
            data=formatter.to_html(),
            file_name=f"audit_{scorecard.claim_id}.html",
            mime="text/html",
        )

else:
    # ==========================================================================
    # Welcome Screen
    # ==========================================================================
    st.markdown("---")

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown(
            """
            <div style="text-align: center; padding: 3rem; background: linear-gradient(135deg, #f5f7fa 0%, #e4e8ec 100%); border-radius: 16px;">
                <h2>👋 Welcome to the Claim Integrity Auditor</h2>
                <p style="color: #6B7280; margin-top: 1rem;">
                    Upload your Xactimate estimate file to begin automated auditing for:
                </p>
                <div style="display: flex; justify-content: center; gap: 2rem; margin-top: 2rem; flex-wrap: wrap;">
                    <div style="text-align: center;">
                        <span style="font-size: 2rem;">💰</span>
                        <p><strong>Financial Accuracy</strong></p>
                    </div>
                    <div style="text-align: center;">
                        <span style="font-size: 2rem;">🔍</span>
                        <p><strong>Leakage Detection</strong></p>
                    </div>
                    <div style="text-align: center;">
                        <span style="font-size: 2rem;">⚠️</span>
                        <p><strong>Supplement Risk</strong></p>
                    </div>
                </div>
                <p style="margin-top: 2rem; color: #9CA3AF;">
                    Supported formats: JSON, CSV
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("---")

    # Quick Start Guide
    st.markdown("### 🚀 Quick Start Guide")

    guide1, guide2, guide3 = st.columns(3)

    with guide1:
        st.markdown(
            """
            **Step 1: Upload**

            Upload your Xactimate estimate export in JSON or CSV format using the sidebar.
            """
        )

    with guide2:
        st.markdown(
            """
            **Step 2: Configure**

            Select the claim type (Water, Roof, or Flooring) to optimize audit rules.
            """
        )

    with guide3:
        st.markdown(
            """
            **Step 3: Analyze**

            Click "Run Audit" to analyze the estimate and view the comprehensive scorecard.
            """
        )


# =============================================================================
# Footer
# =============================================================================
st.markdown("---")
st.markdown(
    """
    <div style="text-align: center; color: #9CA3AF; padding: 1rem;">
        <p>Claim Integrity Engine v0.1.0 | Built with Streamlit</p>
        <p style="font-size: 0.75rem;">SOC2 Compliant • PII Protection Available</p>
    </div>
    """,
    unsafe_allow_html=True,
)

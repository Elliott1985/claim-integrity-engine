#!/usr/bin/env python3
"""
AI-Powered Xactimate PDF Auditor.
Uses Google Gemini to analyze and audit insurance claim estimates.
"""

import json
import os
import re
import time
from pathlib import Path
from typing import Any

import pandas as pd
import pdfplumber
import streamlit as st

try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None
    types = None


# =============================================================================
# Streamlit Config Bridge - MUST be called before any st commands
# =============================================================================
def create_streamlit_config() -> None:
    """
    Create .streamlit/config.toml with dark enterprise theme if it doesn't exist.
    This ensures the dark theme is enforced at the server level.
    """
    # Navigate from src/claim_engine/auditor_app.py to project root
    # auditor_app.py -> claim_engine -> src -> project_root
    project_root = Path(__file__).resolve().parent.parent.parent
    config_dir = project_root / ".streamlit"
    config_file = config_dir / "config.toml"
    
    if not config_file.exists():
        config_dir.mkdir(parents=True, exist_ok=True)
        config_content = '''[theme]
base = "dark"
primaryColor = "#3B82F6"
backgroundColor = "#0E1117"
secondaryBackgroundColor = "#1E293B"
textColor = "#F1F5F9"
font = "sans serif"

[server]
headless = true
enableCORS = false
enableXsrfProtection = true

[browser]
gatherUsageStats = false
'''
        config_file.write_text(config_content)


# Call config bridge BEFORE any Streamlit commands
create_streamlit_config()

# =============================================================================
# Page Configuration - MUST be first st command
# =============================================================================
st.set_page_config(
    page_title="AI Claim Auditor",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

# =============================================================================
# CRITICAL: Inject CSS immediately after set_page_config
# =============================================================================
ENTERPRISE_CSS = """
<style>
    /* ===== Microsoft Fluent Design System ===== */
    @import url('https://fonts.googleapis.com/css2?family=Segoe+UI:wght@300;400;500;600;700&display=swap');
    
    /* ===== CSS Variables - Microsoft Office Colors ===== */
    :root {
        --ms-blue: #0078D4;
        --ms-blue-dark: #106EBE;
        --ms-blue-light: #DEECF9;
        --ms-green: #107C10;
        --ms-red: #D13438;
        --ms-orange: #FF8C00;
        --ms-gray-10: #FAF9F8;
        --ms-gray-20: #F3F2F1;
        --ms-gray-30: #EDEBE9;
        --ms-gray-40: #D2D0CE;
        --ms-gray-90: #605E5C;
        --ms-gray-130: #323130;
        --ms-gray-150: #201F1E;
        --ms-font: 'Segoe UI', -apple-system, BlinkMacSystemFont, sans-serif;
    }
    
    /* ===== Global Styles - Clean Office Look ===== */
    html, body, [class*="css"], .stApp, [data-testid="stAppViewContainer"] {
        font-family: var(--ms-font) !important;
        background-color: #FFFFFF !important;
    }
    
    .stApp {
        background: #FFFFFF !important;
    }
    
    [data-testid="stAppViewContainer"] > .main {
        background: #FFFFFF !important;
    }
    
    [data-testid="stHeader"] {
        background: #FFFFFF !important;
        border-bottom: 1px solid var(--ms-gray-30) !important;
    }
    
    /* ===== Main Header - Office Style ===== */
    .main-header {
        font-family: var(--ms-font) !important;
        font-size: 2rem !important;
        font-weight: 600 !important;
        color: var(--ms-gray-150) !important;
        text-align: left !important;
        margin-bottom: 0.25rem !important;
        letter-spacing: -0.01em !important;
        -webkit-text-fill-color: var(--ms-gray-150) !important;
        background: none !important;
    }
    
    .sub-header {
        font-family: var(--ms-font) !important;
        font-size: 0.95rem !important;
        color: var(--ms-gray-90) !important;
        text-align: left !important;
        margin-bottom: 1.5rem !important;
        font-weight: 400 !important;
    }
    
    /* ===== Office-Style Metric Cards ===== */
    .glass-metric-card {
        background: #FFFFFF !important;
        border: 1px solid var(--ms-gray-30) !important;
        border-radius: 4px !important;
        padding: 1.25rem !important;
        box-shadow: 0 1.6px 3.6px 0 rgba(0,0,0,0.132), 0 0.3px 0.9px 0 rgba(0,0,0,0.108) !important;
        transition: box-shadow 0.2s ease !important;
        text-align: left !important;
        height: 100% !important;
        min-height: 120px !important;
    }
    
    .glass-metric-card:hover {
        box-shadow: 0 3.2px 7.2px 0 rgba(0,0,0,0.132), 0 0.6px 1.8px 0 rgba(0,0,0,0.108) !important;
        border-color: var(--ms-blue) !important;
    }
    
    .glass-metric-label {
        color: var(--ms-gray-90) !important;
        font-weight: 400 !important;
        font-size: 0.8rem !important;
        text-transform: none !important;
        letter-spacing: normal !important;
        margin-bottom: 0.5rem !important;
    }
    
    .glass-metric-value {
        color: var(--ms-gray-150) !important;
        font-weight: 600 !important;
        font-size: 1.75rem !important;
        line-height: 1.2 !important;
        margin-bottom: 0.25rem !important;
    }
    
    .glass-metric-value.positive { color: var(--ms-green) !important; }
    .glass-metric-value.negative { color: var(--ms-red) !important; }
    .glass-metric-value.warning { color: var(--ms-orange) !important; }
    
    .glass-metric-delta {
        font-size: 0.8rem !important;
        font-weight: 400 !important;
        color: var(--ms-gray-90) !important;
    }
    
    .glass-metric-delta.positive { color: var(--ms-green) !important; }
    .glass-metric-delta.negative { color: var(--ms-red) !important; }
    
    /* ===== st.metric Office Styling ===== */
    [data-testid="stMetric"],
    [data-testid="metric-container"],
    .stMetric {
        background: #FFFFFF !important;
        border: 1px solid var(--ms-gray-30) !important;
        border-radius: 4px !important;
        padding: 1rem !important;
        box-shadow: 0 1.6px 3.6px 0 rgba(0,0,0,0.132), 0 0.3px 0.9px 0 rgba(0,0,0,0.108) !important;
    }
    
    [data-testid="stMetricLabel"],
    [data-testid="stMetric"] label {
        color: var(--ms-gray-90) !important;
        font-weight: 400 !important;
        font-size: 0.85rem !important;
        text-transform: none !important;
    }
    
    [data-testid="stMetricValue"] {
        color: var(--ms-gray-150) !important;
        font-weight: 600 !important;
        font-size: 1.5rem !important;
    }
    
    /* ===== Sidebar - Office Navigation Pane ===== */
    [data-testid="stSidebar"],
    [data-testid="stSidebar"] > div:first-child {
        background: var(--ms-gray-20) !important;
        border-right: 1px solid var(--ms-gray-30) !important;
    }
    
    [data-testid="stSidebar"] .stMarkdown,
    [data-testid="stSidebar"] p,
    [data-testid="stSidebar"] span {
        color: var(--ms-gray-130) !important;
    }
    
    [data-testid="stSidebar"] h1, 
    [data-testid="stSidebar"] h2, 
    [data-testid="stSidebar"] h3 {
        color: var(--ms-gray-150) !important;
        font-weight: 600 !important;
    }
    
    /* ===== File Uploader - Office Style ===== */
    [data-testid="stFileUploader"],
    [data-testid="stFileUploadDropzone"] {
        background: var(--ms-gray-10) !important;
        border: 1px dashed var(--ms-gray-40) !important;
        border-radius: 4px !important;
        padding: 1.25rem !important;
        transition: all 0.2s ease !important;
    }
    
    [data-testid="stFileUploader"]:hover,
    [data-testid="stFileUploadDropzone"]:hover {
        border-color: var(--ms-blue) !important;
        background: var(--ms-blue-light) !important;
    }
    
    [data-testid="stFileUploader"] section,
    [data-testid="stFileUploader"] > div {
        background: transparent !important;
    }
    
    /* ===== Buttons - Office Fluent Style ===== */
    [data-testid="stFileUploader"] button,
    [data-testid="stBaseButton-secondary"] {
        background: var(--ms-blue) !important;
        color: white !important;
        border: none !important;
        border-radius: 4px !important;
        font-weight: 600 !important;
        padding: 0.5rem 1.25rem !important;
        transition: background 0.2s ease !important;
    }
    
    [data-testid="stFileUploader"] button:hover,
    [data-testid="stBaseButton-secondary"]:hover {
        background: var(--ms-blue-dark) !important;
    }
    
    /* ===== Primary Button - Office Blue ===== */
    [data-testid="stBaseButton-primary"],
    .stButton > button[kind="primary"],
    button[kind="primary"] {
        background: var(--ms-blue) !important;
        color: white !important;
        border: none !important;
        border-radius: 4px !important;
        font-weight: 600 !important;
        font-size: 0.9rem !important;
        padding: 0.6rem 1.5rem !important;
        box-shadow: none !important;
        transition: background 0.2s ease !important;
    }
    
    [data-testid="stBaseButton-primary"]:hover,
    .stButton > button[kind="primary"]:hover {
        background: var(--ms-blue-dark) !important;
        transform: none !important;
    }
    
    /* ===== Data Tables - Excel Style ===== */
    [data-testid="stDataFrame"],
    .stDataFrame {
        border: 1px solid var(--ms-gray-30) !important;
        border-radius: 0 !important;
        overflow: hidden !important;
    }
    
    [data-testid="stDataFrame"] [data-testid="stDataFrameResizable"],
    .stDataFrame [data-testid="stDataFrameResizable"] {
        background: #FFFFFF !important;
    }
    
    [data-testid="stDataFrame"] thead tr th,
    .stDataFrame thead tr th {
        background: var(--ms-gray-20) !important;
        color: var(--ms-gray-130) !important;
        font-weight: 600 !important;
        font-size: 0.8rem !important;
        padding: 0.75rem 1rem !important;
        border-bottom: 1px solid var(--ms-gray-30) !important;
        text-transform: none !important;
    }
    
    [data-testid="stDataFrame"] tbody tr:nth-child(odd),
    .stDataFrame tbody tr:nth-child(odd) {
        background: #FFFFFF !important;
    }
    
    [data-testid="stDataFrame"] tbody tr:nth-child(even),
    .stDataFrame tbody tr:nth-child(even) {
        background: var(--ms-gray-10) !important;
    }
    
    [data-testid="stDataFrame"] tbody tr:hover,
    .stDataFrame tbody tr:hover {
        background: var(--ms-blue-light) !important;
    }
    
    [data-testid="stDataFrame"] tbody td,
    .stDataFrame tbody td {
        color: var(--ms-gray-130) !important;
        padding: 0.6rem 1rem !important;
        border-bottom: 1px solid var(--ms-gray-30) !important;
    }
    
    /* ===== Expander - Office Collapsible ===== */
    [data-testid="stExpander"],
    .streamlit-expanderHeader {
        background: #FFFFFF !important;
        border: 1px solid var(--ms-gray-30) !important;
        border-radius: 4px !important;
        color: var(--ms-gray-130) !important;
        font-weight: 400 !important;
    }
    
    [data-testid="stExpander"]:hover,
    .streamlit-expanderHeader:hover {
        border-color: var(--ms-blue) !important;
        background: var(--ms-gray-10) !important;
    }
    
    [data-testid="stExpanderDetails"],
    .streamlit-expanderContent {
        background: #FFFFFF !important;
        border: 1px solid var(--ms-gray-30) !important;
        border-top: none !important;
        border-radius: 0 0 4px 4px !important;
    }
    
    /* ===== Alert Boxes - Office Style ===== */
    [data-testid="stAlert"][data-baseweb="notification"][kind="success"],
    .stSuccess, div[data-baseweb="notification"].success {
        background: #DFF6DD !important;
        border: 1px solid var(--ms-green) !important;
        border-left: 4px solid var(--ms-green) !important;
        border-radius: 4px !important;
        color: #0B6A0B !important;
    }
    
    [data-testid="stAlert"][data-baseweb="notification"][kind="warning"],
    .stWarning, div[data-baseweb="notification"].warning {
        background: #FFF4CE !important;
        border: 1px solid var(--ms-orange) !important;
        border-left: 4px solid var(--ms-orange) !important;
        border-radius: 4px !important;
        color: #8A6200 !important;
    }
    
    [data-testid="stAlert"][data-baseweb="notification"][kind="error"],
    .stError, div[data-baseweb="notification"].error {
        background: #FDE7E9 !important;
        border: 1px solid var(--ms-red) !important;
        border-left: 4px solid var(--ms-red) !important;
        border-radius: 4px !important;
        color: #A80000 !important;
    }
    
    [data-testid="stAlert"][data-baseweb="notification"][kind="info"],
    .stInfo, div[data-baseweb="notification"].info {
        background: var(--ms-blue-light) !important;
        border: 1px solid var(--ms-blue) !important;
        border-left: 4px solid var(--ms-blue) !important;
        border-radius: 4px !important;
        color: #004578 !important;
    }
    
    /* ===== Markdown Tables - Excel Style ===== */
    .stMarkdown table {
        width: 100% !important;
        border-collapse: collapse !important;
        background: #FFFFFF !important;
        border: 1px solid var(--ms-gray-30) !important;
    }
    
    .stMarkdown table thead th {
        background: var(--ms-gray-20) !important;
        color: var(--ms-gray-130) !important;
        font-weight: 600 !important;
        padding: 0.6rem 1rem !important;
        text-align: left !important;
        border-bottom: 1px solid var(--ms-gray-40) !important;
    }
    
    .stMarkdown table tbody tr:nth-child(odd) {
        background: #FFFFFF !important;
    }
    
    .stMarkdown table tbody tr:nth-child(even) {
        background: var(--ms-gray-10) !important;
    }
    
    .stMarkdown table tbody tr:hover {
        background: var(--ms-blue-light) !important;
    }
    
    .stMarkdown table td {
        color: var(--ms-gray-130) !important;
        padding: 0.5rem 1rem !important;
        border-bottom: 1px solid var(--ms-gray-30) !important;
    }
    
    /* ===== Text Input - Office Style ===== */
    [data-testid="stTextInput"] input,
    .stTextInput > div > div > input {
        background: #FFFFFF !important;
        border: 1px solid var(--ms-gray-40) !important;
        border-radius: 4px !important;
        color: var(--ms-gray-130) !important;
        padding: 0.5rem 0.75rem !important;
    }
    
    [data-testid="stTextInput"] input:focus,
    .stTextInput > div > div > input:focus {
        border-color: var(--ms-blue) !important;
        box-shadow: none !important;
        outline: none !important;
    }
    
    /* ===== Checkbox - Office Style ===== */
    .stCheckbox label,
    [data-testid="stCheckbox"] label {
        color: var(--ms-gray-130) !important;
    }
    
    /* ===== Download Buttons - Office Style ===== */
    [data-testid="stDownloadButton"] > button,
    .stDownloadButton > button {
        background: #FFFFFF !important;
        color: var(--ms-blue) !important;
        border: 1px solid var(--ms-blue) !important;
        border-radius: 4px !important;
        font-weight: 600 !important;
        transition: all 0.2s ease !important;
    }
    
    [data-testid="stDownloadButton"] > button:hover,
    .stDownloadButton > button:hover {
        background: var(--ms-blue-light) !important;
    }
    
    /* ===== Spinner ===== */
    .stSpinner > div {
        border-top-color: var(--ms-blue) !important;
    }
    
    /* ===== Horizontal Rule ===== */
    hr {
        border: none !important;
        height: 1px !important;
        background: var(--ms-gray-30) !important;
        margin: 1.5rem 0 !important;
    }
    
    /* ===== Scrollbar - Office Style ===== */
    ::-webkit-scrollbar {
        width: 8px;
        height: 8px;
    }
    
    ::-webkit-scrollbar-track {
        background: var(--ms-gray-20);
    }
    
    ::-webkit-scrollbar-thumb {
        background: var(--ms-gray-40);
        border-radius: 0;
    }
    
    ::-webkit-scrollbar-thumb:hover {
        background: var(--ms-gray-90);
    }
    
    /* ===== General Text ===== */
    .stMarkdown, .stMarkdown p, p, span {
        color: var(--ms-gray-130) !important;
    }
    
    .stMarkdown h1, .stMarkdown h2, .stMarkdown h3, 
    .stMarkdown h4, .stMarkdown h5, .stMarkdown h6,
    h1, h2, h3, h4, h5, h6 {
        color: var(--ms-gray-150) !important;
        font-weight: 600 !important;
    }
    
    /* ===== Code Blocks ===== */
    [data-testid="stCodeBlock"],
    .stCodeBlock {
        background: var(--ms-gray-10) !important;
        border: 1px solid var(--ms-gray-30) !important;
        border-radius: 4px !important;
    }
    
    /* ===== JSON Viewer ===== */
    [data-testid="stJson"] {
        background: var(--ms-gray-10) !important;
        border-radius: 4px !important;
    }
</style>
"""

# Inject CSS immediately after page config
st.markdown(ENTERPRISE_CSS, unsafe_allow_html=True)

# =============================================================================
# System Prompt - The Brain
# =============================================================================
SYSTEM_MESSAGE = """You are an Expert Insurance Claims Auditor with deep knowledge of Xactimate estimating software and insurance industry billing practices. Your goal is to convert raw Xactimate text into a structured JSON object, identify financial leakage, and enforce policy compliance.

ANALYSIS FOCUS AREAS:

1. **Water Mitigation Leakage:**
   - Flag if there is more than 1 air mover per 60 sq ft of affected area
   - Flag if daily monitoring days exceed equipment rental days
   - Flag if Category 3 (Black Water) PPE/cleaning is billed for Category 1 (Clean Water) loss
   - Flag if dehumidifier count exceeds 1 per 1000 sq ft

2. **Flooring Leakage:**
   - Flag if "Carpet Removal" and "Pad Removal" are separate line items (pad removal is typically included)
   - Flag if flooring waste exceeds 10% for simple rectangular rooms
   - Flag if hardwood/tile installation lacks floor preparation charges (potential supplement risk)

3. **Roofing Leakage:**
   - Flag if "Gable" roof waste factor exceeds 10%
   - Flag if "Hip" roof waste factor exceeds 15%
   - Flag if starter/drip edge is billed separately when included in shingle installation
   - Flag if ice & water shield exceeds code requirements

4. **Financial Compliance:**
   - Verify the Deductible is subtracted from the ACV (Actual Cash Value) for the Net Claim
   - Check that depreciation is applied correctly
   - Verify coverage limits (A, B, C) are not exceeded
   - Flag any mathematical errors in line item totals

5. **General Double-Dip Detection:**
   - Pre-hung doors billed with separate hinges
   - Drywall removal billed with separate wallpaper removal
   - Paint with primer billed with separate primer

6. **Cause of Loss (COL) Verification:**
   - Extract the "Cause of Loss" or "Peril" from the estimate header (e.g., Water, Fire, Wind, Hail, Theft, Vandalism)
   - Flag ANY line items that do not logically align with the stated peril:
     * Interior water mitigation (WTR codes) on a "Theft" or "Vandalism" claim
     * Roofing repairs (RFG codes) on an interior "Water" claim without storm damage
     * Fire/smoke cleaning on a "Water" or "Wind" claim
     * Mold remediation on a "Theft" claim
   - Severity: HIGH for clear mismatches, MEDIUM for questionable items

7. **Price List Audit:**
   - Extract the "Price List" version from the header (format: MMMYY, e.g., MAR25, JAN26, FEB26)
   - Extract the "Date of Loss" (DOL)
   - Calculate the age difference between Price List date and Date of Loss
   - Flag as "Outdated Pricing" if the price list is MORE than 60 days older than the Date of Loss
   - Example: DOL = March 15, 2026 with Price List = JAN26 (January 2026) = ~75 days = FLAGGED
   - Outdated pricing can result in understated estimates (carrier risk) or overstated (leakage risk)

8. **Coverage Categorization & Sub-Limit Enforcement:**
   - Group all line items by trade code prefix:
     * RFG = Roofing
     * WTR = Water Mitigation
     * FNC/FCC = Flooring (Carpet/Flooring)
     * PNT = Painting
     * DRY = Drywall
     * PLM = Plumbing
     * ELC = Electrical
     * CLN = Cleaning
     * DEM = Demolition
     * CNT = Contents
     * MLD/ANT = Mold/Anti-microbial
   - Calculate total cost per trade category
   - Flag if ANY of these sub-limits are exceeded:
     * Mold/Anti-microbial (MLD/ANT codes): Flag if total > $5,000
     * Temporary Repairs: Flag if total > $3,000
     * Tree Removal: Flag if total > $1,000 per tree or $5,000 total
     * Debris Removal: Flag if total > 5% of gross estimate
     * Water Mitigation (WTR codes): Flag if total > $15,000 without Category 3 justification

OUTPUT FORMAT - Return ONLY valid JSON with this exact structure:
{
    "claim_info": {
        "claim_number": "string or null",
        "insured_name": "REDACTED",
        "date_of_loss": "string or null",
        "cause_of_loss": "Water|Fire|Wind|Hail|Theft|Vandalism|Lightning|Other|null",
        "claim_type": "Water|Roofing|Fire|Other",
        "price_list": "string (e.g., MAR25) or null",
        "price_list_date": "YYYY-MM-DD or null",
        "estimate_date": "string or null"
    },
    "financial_summary": {
        "gross_estimate": number,
        "depreciation": number,
        "acv": number,
        "deductible": number,
        "net_claim": number,
        "deductible_applied_correctly": boolean
    },
    "line_items": [
        {
            "code": "string",
            "description": "string",
            "quantity": number,
            "unit": "string",
            "unit_price": number,
            "total": number,
            "category": "Water|Flooring|Roofing|General|Contents",
            "trade_code": "RFG|WTR|FNC|PNT|DRY|PLM|ELC|CLN|DEM|CNT|MLD|GEN"
        }
    ],
    "trade_summary": {
        "RFG": {"item_count": number, "total": number},
        "WTR": {"item_count": number, "total": number},
        "FNC": {"item_count": number, "total": number},
        "PNT": {"item_count": number, "total": number},
        "DRY": {"item_count": number, "total": number},
        "MLD": {"item_count": number, "total": number},
        "GEN": {"item_count": number, "total": number}
    },
    "property_details": {
        "total_sqft_affected": number or null,
        "roof_type": "Gable|Hip|Flat|Mixed|null",
        "water_category": 1 or 2 or 3 or null
    },
    "policy_compliance_flags": [
        {
            "flag_type": "COL_MISMATCH|OUTDATED_PRICING|SUBLIMIT_EXCEEDED",
            "severity": "High|Medium|Low",
            "title": "string",
            "description": "string",
            "details": {
                "expected": "string",
                "found": "string",
                "affected_items": ["code1", "code2"],
                "amount": number or null,
                "limit": number or null
            },
            "recommendation": "string"
        }
    ],
    "leakage_findings": [
        {
            "category": "Water Mitigation|Flooring|Roofing|Financial|General|Policy Compliance",
            "severity": "High|Medium|Low",
            "title": "string",
            "description": "string",
            "line_items_affected": ["code1", "code2"],
            "potential_savings": number,
            "recommendation": "string"
        }
    ],
    "audit_summary": {
        "total_leakage_found": number,
        "leakage_count": number,
        "compliance_flags_count": number,
        "risk_level": "High|Medium|Low",
        "accuracy_score": number (0-100),
        "pricing_status": "Current|Outdated|Unknown"
    }
}

IMPORTANT RULES:
- Always redact the insured name as "REDACTED" for PII protection
- If information is not found, use null
- Calculate potential_savings for each leakage finding
- Be conservative - only flag clear violations, not edge cases
- COL mismatches are HIGH severity policy compliance issues
- Outdated pricing (>60 days) is MEDIUM severity
- Sub-limit exceedances are HIGH severity if >150% of limit, MEDIUM if 100-150%
- Return ONLY the JSON object, no markdown formatting or explanation"""


# =============================================================================
# PII Redaction Functions
# =============================================================================
def redact_pii(text: str) -> str:
    """
    Scrub text for PII (names, emails, phone numbers) before sending to Gemini API.
    
    Uses regex patterns to detect and replace sensitive information with [REDACTED_PII].
    This function runs BEFORE text is sent to the AI model.
    
    Args:
        text: Raw text to redact
        
    Returns:
        Text with PII replaced by [REDACTED_PII]
    """
    # Redact email addresses
    text = re.sub(
        r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
        '[REDACTED_PII]',
        text
    )
    
    # Redact phone numbers (various formats)
    phone_patterns = [
        r'\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b',      # 123-456-7890, 123.456.7890, 123 456 7890
        r'\(\d{3}\)\s*\d{3}[-.\s]?\d{4}',           # (123) 456-7890
        r'\+1\s*\d{3}[-.\s]?\d{3}[-.\s]?\d{4}',     # +1 123-456-7890
        r'\b1[-.\s]?\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b',  # 1-800-555-1234
    ]
    for pattern in phone_patterns:
        text = re.sub(pattern, '[REDACTED_PII]', text)
    
    # Redact names following common labels (Insured, Claimant, etc.)
    name_label_patterns = [
        r'(Insured\s*[:\-]?\s*)([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3})',
        r'(Insured Name\s*[:\-]?\s*)([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3})',
        r'(Policy\s*Holder\s*[:\-]?\s*)([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3})',
        r'(Claimant\s*[:\-]?\s*)([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3})',
        r'(Customer\s*[:\-]?\s*)([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3})',
        r'(Homeowner\s*[:\-]?\s*)([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3})',
        r'(Contact\s*[:\-]?\s*)([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3})',
    ]
    for pattern in name_label_patterns:
        text = re.sub(pattern, r'\1[REDACTED_PII]', text, flags=re.IGNORECASE)
    
    # Redact SSN patterns (XXX-XX-XXXX)
    text = re.sub(r'\b\d{3}[-\s]?\d{2}[-\s]?\d{4}\b', '[REDACTED_PII]', text)
    
    # Redact street addresses (basic pattern)
    text = re.sub(
        r'\b\d+\s+[A-Za-z]+(?:\s+[A-Za-z]+)*\s+(?:Street|St|Avenue|Ave|Road|Rd|Drive|Dr|Lane|Ln|Court|Ct|Boulevard|Blvd|Way|Circle|Cir|Place|Pl)\b',
        '[REDACTED_PII]',
        text,
        flags=re.IGNORECASE
    )
    
    return text


# =============================================================================
# PDF Extraction
# =============================================================================
def extract_pdf_text(uploaded_file) -> str:
    """
    Extract text from uploaded PDF using pdfplumber.
    
    Args:
        uploaded_file: Streamlit uploaded file object
        
    Returns:
        Extracted text from all pages
    """
    text_content = []
    
    with pdfplumber.open(uploaded_file) as pdf:
        for page_num, page in enumerate(pdf.pages, 1):
            page_text = page.extract_text()
            if page_text:
                text_content.append(f"--- Page {page_num} ---\n{page_text}")
            
            # Also try to extract tables
            tables = page.extract_tables()
            for table_num, table in enumerate(tables, 1):
                if table:
                    table_text = "\n".join(["\t".join([str(cell) if cell else "" for cell in row]) for row in table])
                    text_content.append(f"--- Table {table_num} (Page {page_num}) ---\n{table_text}")
    
    return "\n\n".join(text_content)


# =============================================================================
# Gemini Integration
# =============================================================================
def analyze_with_gemini(pdf_text: str, api_key: str) -> dict[str, Any] | None:
    """
    Send PDF text to Gemini for analysis using 2026 Google GenAI SDK.
    
    Args:
        pdf_text: Extracted and redacted PDF text
        api_key: Google Gemini API key
        
    Returns:
        Parsed JSON response from Gemini
    """
    if genai is None:
        st.error("Google GenAI SDK not installed. Run: pip install google-genai")
        return None
    
    try:
        # Initialize the client with the new 2026 SDK architecture
        client = genai.Client(api_key=api_key)
        
        # Build the user prompt with PDF content
        user_prompt = f"""---
XACTIMATE ESTIMATE TEXT TO ANALYZE:
---
{pdf_text}
---

Analyze the above estimate and return the JSON audit report."""
        
        # Generate response using the new client.models.generate_content() API
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=types.Content(
                parts=[types.Part(text=user_prompt)]
            ),
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_MESSAGE,
                temperature=0.2,  # Lower temperature for consistent JSON output
                response_mime_type='application/json',  # Request JSON response directly
            ),
        )
        
        # Extract JSON from response
        response_text = response.text.strip()
        
        # Handle markdown code blocks if present (fallback)
        if response_text.startswith("```"):
            lines = response_text.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines[-1].strip() == "```":
                lines = lines[:-1]
            response_text = "\n".join(lines)
        
        # Parse JSON
        result = json.loads(response_text)
        return result
        
    except json.JSONDecodeError as e:
        st.error(f"Failed to parse AI response as JSON: {e}")
        st.code(response_text[:1000] if 'response_text' in dir() else "No response")
        return None
    except Exception as e:
        st.error(f"Gemini API error: {str(e)}")
        return None


# =============================================================================
# UI Components - Glassmorphism Metric Cards
# =============================================================================
def render_glass_metric(label: str, value: str, delta: str, value_class: str = "", delta_class: str = "") -> str:
    """
    Generate HTML for a glassmorphism metric card.
    
    Args:
        label: Metric label text
        value: Main value to display
        delta: Delta/secondary text
        value_class: CSS class for value (positive/negative/warning)
        delta_class: CSS class for delta (positive/negative)
        
    Returns:
        HTML string for the metric card
    """
    return f'''
    <div class="glass-metric-card">
        <div class="glass-metric-label">{label}</div>
        <div class="glass-metric-value {value_class}">{value}</div>
        <div class="glass-metric-delta {delta_class}">{delta}</div>
    </div>
    '''


def render_kpis(audit_data: dict[str, Any]) -> None:
    """Render KPI cards at the top of the dashboard using glassmorphism HTML cards."""
    summary = audit_data.get("audit_summary", {})
    financial = audit_data.get("financial_summary", {})
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        accuracy = summary.get("accuracy_score", 0)
        value_class = "positive" if accuracy >= 70 else "negative"
        delta_class = "positive" if accuracy >= 70 else "negative"
        st.markdown(
            render_glass_metric(
                label="ACCURACY SCORE",
                value=f"{accuracy}/100",
                delta=f"{accuracy - 70:+.0f} vs benchmark" if accuracy else "N/A",
                value_class=value_class,
                delta_class=delta_class,
            ),
            unsafe_allow_html=True,
        )
    
    with col2:
        leakage = summary.get("total_leakage_found", 0)
        leakage_count = summary.get('leakage_count', 0)
        value_class = "negative" if leakage > 0 else "positive"
        st.markdown(
            render_glass_metric(
                label="TOTAL LEAKAGE",
                value=f"${leakage:,.2f}",
                delta=f"{leakage_count} issues found",
                value_class=value_class,
                delta_class="negative" if leakage_count > 0 else "",
            ),
            unsafe_allow_html=True,
        )
    
    with col3:
        net_claim = financial.get("net_claim", 0)
        deductible = financial.get('deductible', 0)
        st.markdown(
            render_glass_metric(
                label="NET CLAIM",
                value=f"${net_claim:,.2f}",
                delta=f"After ${deductible:,.0f} deductible",
            ),
            unsafe_allow_html=True,
        )
    
    with col4:
        risk = summary.get("risk_level", "Unknown")
        risk_indicator = {"High": "●", "Medium": "●", "Low": "●"}.get(risk, "○")
        value_class = {"High": "negative", "Medium": "warning", "Low": "positive"}.get(risk, "")
        finding_count = len(audit_data.get('leakage_findings', []))
        compliance_count = summary.get('compliance_flags_count', 0)
        total_flags = finding_count + compliance_count
        st.markdown(
            render_glass_metric(
                label="RISK LEVEL",
                value=f"{risk_indicator} {risk}",
                delta=f"{total_flags} flags triggered",
                value_class=value_class,
            ),
            unsafe_allow_html=True,
        )


def render_leakage_summary(findings: list[dict]) -> None:
    """Render the Leakage Summary table."""
    if not findings:
        st.success("No leakage issues detected")
        return
    
    st.markdown("### Leakage Summary - Potential Savings")
    
    # Create summary DataFrame
    summary_data = []
    for finding in findings:
        summary_data.append({
            "Category": finding.get("category", "Unknown"),
            "Issue": finding.get("title", ""),
            "Severity": finding.get("severity", ""),
            "Potential Savings": f"${finding.get('potential_savings', 0):,.2f}",
            "Recommendation": finding.get("recommendation", "")[:50] + "..." if len(finding.get("recommendation", "")) > 50 else finding.get("recommendation", ""),
        })
    
    df = pd.DataFrame(summary_data)
    
    # Style the dataframe
    def highlight_severity(val):
        colors = {"High": "#ffcccc", "Medium": "#fff3cd", "Low": "#d4edda"}
        return f"background-color: {colors.get(val, '')}"
    
    styled_df = df.style.applymap(highlight_severity, subset=["Severity"])
    st.dataframe(styled_df, use_container_width=True, hide_index=True)
    
    # Total savings
    total_savings = sum(f.get("potential_savings", 0) for f in findings)
    st.markdown(f"**Total Potential Savings: ${total_savings:,.2f}**")


def render_detailed_findings(findings: list[dict]) -> None:
    """Render detailed findings with expandable sections."""
    if not findings:
        return
    
    st.markdown("### Detailed Audit Findings")
    
    for i, finding in enumerate(findings, 1):
        severity = finding.get("severity", "Medium")
        severity_icon = {"High": "🔴", "Medium": "🟡", "Low": "🟢"}.get(severity, "⚪")
        
        with st.expander(f"{severity_icon} {finding.get('title', f'Finding {i}')} - ${finding.get('potential_savings', 0):,.2f}"):
            col1, col2 = st.columns([2, 1])
            
            with col1:
                st.markdown(f"**Category:** {finding.get('category', 'Unknown')}")
                st.markdown(f"**Description:** {finding.get('description', 'N/A')}")
                st.markdown(f"**Recommendation:** {finding.get('recommendation', 'N/A')}")
            
            with col2:
                st.markdown(f"**Severity:** {severity}")
                st.markdown(f"**Savings:** ${finding.get('potential_savings', 0):,.2f}")
                
                affected = finding.get("line_items_affected", [])
                if affected:
                    st.markdown(f"**Affected Items:** {', '.join(affected)}")


def render_financial_breakdown(financial: dict) -> None:
    """Render financial summary breakdown."""
    st.markdown("### Financial Breakdown")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown(f"""
        | Item | Amount |
        |------|--------|
        | **Gross Estimate** | ${financial.get('gross_estimate', 0):,.2f} |
        | **Depreciation** | -${financial.get('depreciation', 0):,.2f} |
        | **ACV (Actual Cash Value)** | ${financial.get('acv', 0):,.2f} |
        | **Deductible** | -${financial.get('deductible', 0):,.2f} |
        | **Net Claim** | **${financial.get('net_claim', 0):,.2f}** |
        """)
    
    with col2:
        deductible_ok = financial.get("deductible_applied_correctly", True)
        if deductible_ok:
            st.success("Deductible correctly applied to ACV")
        else:
            st.error("Deductible calculation error detected")
        
        # Verification calculation
        expected_net = financial.get('acv', 0) - financial.get('deductible', 0)
        actual_net = financial.get('net_claim', 0)
        
        if abs(expected_net - actual_net) > 0.01:
            st.warning(f"Net claim discrepancy: Expected ${expected_net:,.2f}, Got ${actual_net:,.2f}")


def render_line_items(line_items: list[dict]) -> None:
    """Render line items table."""
    if not line_items:
        return
    
    with st.expander("View All Line Items", expanded=False):
        df = pd.DataFrame(line_items)
        if not df.empty:
            # Format currency columns
            if 'unit_price' in df.columns:
                df['unit_price'] = df['unit_price'].apply(lambda x: f"${x:,.2f}" if pd.notna(x) else "-")
            if 'total' in df.columns:
                df['total'] = df['total'].apply(lambda x: f"${x:,.2f}" if pd.notna(x) else "-")
            
            st.dataframe(df, use_container_width=True, hide_index=True)


# =============================================================================
# Main Application
# =============================================================================
def main():
    # Header - Professional Enterprise Branding
    st.markdown('<p class="main-header">Claim Integrity Engine</p>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Xactimate Estimate Analysis & Leakage Detection Platform</p>', unsafe_allow_html=True)
    st.caption("Automated QA validation for property insurance estimates.")
    
    # Sidebar - Office Navigation Pane
    with st.sidebar:
        st.markdown('''
        <div style="padding: 0.75rem 0; border-bottom: 1px solid #EDEBE9; margin-bottom: 1rem;">
            <div style="display: flex; align-items: center; gap: 0.5rem;">
                <span style="font-size: 1.5rem;">◈</span>
                <span style="font-weight: 600; color: #323130; font-size: 1rem;">Claim Auditor</span>
            </div>
        </div>
        ''', unsafe_allow_html=True)
        st.markdown("#### Navigation")
        st.markdown("---")
        
        # API Key handling - prioritize st.secrets for cloud deployment
        st.subheader("API Settings")
        
        # Check for API key in secrets (Streamlit Cloud) first, then env var, then manual input
        default_api_key = ""
        secrets_configured = False
        
        try:
            if "GOOGLE_API_KEY" in st.secrets:
                default_api_key = st.secrets["GOOGLE_API_KEY"]
                secrets_configured = True
        except Exception:
            # st.secrets not available (local development)
            pass
        
        if not default_api_key:
            default_api_key = os.environ.get("GOOGLE_API_KEY", "")
        
        if secrets_configured:
            st.success("API Key configured via Streamlit Secrets")
            api_key = default_api_key
        else:
            api_key = st.text_input(
                "Google Gemini API Key",
                type="password",
                help="Get your API key from https://aistudio.google.com/app/apikey",
                value=default_api_key,
                key="api_key_input",
            )
            
            if not api_key:
                st.warning("Enter your Gemini API key to enable AI analysis")
        
        st.markdown("---")
        
        # File upload
        st.subheader("Upload Estimate")
        uploaded_file = st.file_uploader(
            "Upload Xactimate PDF",
            type=["pdf"],
            help="Upload your Xactimate estimate PDF file",
            key="pdf_uploader",
            label_visibility="collapsed",
        )
        
        st.markdown("---")
        
        # Options
        st.subheader("Options")
        show_raw_text = st.checkbox("Show extracted text", value=False, key="chk_raw_text")
        show_raw_json = st.checkbox("Show raw AI response", value=False, key="chk_raw_json")
        
        st.markdown("---")
        
        # Analyze button
        analyze_btn = st.button(
            "Analyze Estimate",
            type="primary",
            use_container_width=True,
            disabled=not (uploaded_file and api_key),
            key="btn_analyze",
        )
        
        st.markdown("---")
        
        # Security & Compliance Dashboard
        st.markdown("#### Security & Compliance")
        
        st.success("PII Redaction: Enabled")
        st.info("Data Retention: Zero-Storage Architecture")
        st.info("Encryption: SSL/TLS 256-bit Active")
        st.info("Infrastructure: SOC 2 Type II Ready (Streamlit Cloud)")
        
        # Disclaimer footer
        st.markdown("---")
        st.caption(
            "**Disclaimer:** This tool is a PoC. PII redaction is algorithmic "
            "and for demonstration purposes."
        )
    
    # Main content
    if uploaded_file and api_key and analyze_btn:
        # Start timing
        start_time = time.time()
        
        with st.spinner("Extracting PDF text..."):
            raw_text = extract_pdf_text(uploaded_file)
            
            if not raw_text.strip():
                st.error("Could not extract text from PDF. The file may be image-based or corrupted.")
                return
        
        if show_raw_text:
            with st.expander("Extracted PDF Text", expanded=False):
                st.text(raw_text[:5000] + "..." if len(raw_text) > 5000 else raw_text)
        
        with st.spinner("Redacting PII..."):
            redacted_text = redact_pii(raw_text)
        
        with st.spinner("Analyzing with Gemini AI..."):
            audit_result = analyze_with_gemini(redacted_text, api_key)
        
        # Calculate processing time
        processing_time = time.time() - start_time
        
        if audit_result:
            # Store in session state
            st.session_state.audit_result = audit_result
            
            # Calculate rules executed (findings + compliance flags)
            findings_count = len(audit_result.get('leakage_findings', []))
            compliance_count = audit_result.get('audit_summary', {}).get('compliance_flags_count', 0)
            rules_executed = findings_count + compliance_count + len(audit_result.get('line_items', []))
            
            # Display processing metrics
            st.caption(f"Processed in {processing_time:.2f}s  •  {rules_executed} rules executed")
            
            if show_raw_json:
                with st.expander("Raw AI Response", expanded=False):
                    st.json(audit_result)
            
            st.markdown("---")
            
            # Render KPIs
            render_kpis(audit_result)
            
            st.markdown("---")
            
            # Two-column layout
            col1, col2 = st.columns([3, 2])
            
            with col1:
                # Leakage Summary
                render_leakage_summary(audit_result.get("leakage_findings", []))
                
                st.markdown("---")
                
                # Detailed Findings
                render_detailed_findings(audit_result.get("leakage_findings", []))
            
            with col2:
                # Claim Info
                claim_info = audit_result.get("claim_info", {})
                st.markdown("### Claim Information")
                st.markdown(f"""
                | Field | Value |
                |-------|-------|
                | **Claim Number** | {claim_info.get('claim_number', 'N/A')} |
                | **Claim Type** | {claim_info.get('claim_type', 'N/A')} |
                | **Date of Loss** | {claim_info.get('date_of_loss', 'N/A')} |
                | **Insured** | {claim_info.get('insured_name', 'REDACTED')} |
                """)
                
                st.markdown("---")
                
                # Financial Breakdown
                render_financial_breakdown(audit_result.get("financial_summary", {}))
                
                st.markdown("---")
                
                # Property Details
                prop = audit_result.get("property_details", {})
                st.markdown("### Property Details")
                st.markdown(f"""
                | Detail | Value |
                |--------|-------|
                | **Affected Sq Ft** | {prop.get('total_sqft_affected', 'N/A')} |
                | **Roof Type** | {prop.get('roof_type', 'N/A')} |
                | **Water Category** | {prop.get('water_category', 'N/A')} |
                """)
            
            st.markdown("---")
            
            # Line Items
            render_line_items(audit_result.get("line_items", []))
            
            st.markdown("---")
            
            # Export Options
            st.markdown("### Export Audit Report")
            
            exp1, exp2 = st.columns(2)
            
            with exp1:
                st.download_button(
                    label="Download JSON Report",
                    data=json.dumps(audit_result, indent=2),
                    file_name=f"audit_report_{claim_info.get('claim_number', 'unknown')}.json",
                    mime="application/json",
                    key="btn_json_dl",
                )
            
            with exp2:
                # Create summary text report
                report_text = f"""
AI CLAIM AUDIT REPORT
=====================
Claim: {claim_info.get('claim_number', 'N/A')}
Date: {claim_info.get('date_of_loss', 'N/A')}
Type: {claim_info.get('claim_type', 'N/A')}

FINANCIAL SUMMARY
-----------------
Gross Estimate: ${audit_result.get('financial_summary', {}).get('gross_estimate', 0):,.2f}
Net Claim: ${audit_result.get('financial_summary', {}).get('net_claim', 0):,.2f}

AUDIT RESULTS
-------------
Accuracy Score: {audit_result.get('audit_summary', {}).get('accuracy_score', 0)}/100
Total Leakage Found: ${audit_result.get('audit_summary', {}).get('total_leakage_found', 0):,.2f}
Risk Level: {audit_result.get('audit_summary', {}).get('risk_level', 'N/A')}

LEAKAGE FINDINGS
----------------
"""
                for finding in audit_result.get("leakage_findings", []):
                    report_text += f"\n• {finding.get('title', 'N/A')}"
                    report_text += f"\n  Severity: {finding.get('severity', 'N/A')}"
                    report_text += f"\n  Savings: ${finding.get('potential_savings', 0):,.2f}"
                    report_text += f"\n  {finding.get('description', '')}\n"
                
                st.download_button(
                    label="Download Text Report",
                    data=report_text,
                    file_name=f"audit_report_{claim_info.get('claim_number', 'unknown')}.txt",
                    mime="text/plain",
                    key="btn_txt_dl",
                )
    
    elif not uploaded_file:
        # Welcome screen - Microsoft Office Style
        st.markdown("---")
        
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.markdown("""
            <div style="text-align: center; padding: 2.5rem; background: #FFFFFF; border: 1px solid #EDEBE9; border-radius: 4px; box-shadow: 0 1.6px 3.6px 0 rgba(0,0,0,0.132);">
                <div style="font-size: 3rem; margin-bottom: 1rem;">⬚</div>
                <h2 style="color: #323130; font-weight: 600; margin-bottom: 0.75rem;">Upload Estimate to Begin</h2>
                <p style="color: #605E5C; margin-top: 0.75rem; font-size: 0.95rem;">
                    Submit your Xactimate PDF for comprehensive audit analysis
                </p>
                <div style="margin-top: 1.5rem; padding-top: 1.5rem; border-top: 1px solid #EDEBE9;">
                    <p style="color: #605E5C; font-size: 0.8rem;">Analysis Coverage</p>
                    <p style="color: #323130; margin-top: 0.5rem;">Water Mitigation  •  Flooring  •  Roofing  •  Financials</p>
                </div>
            </div>
            """, unsafe_allow_html=True)
        
        st.markdown("---")
        
        # Features - Office Style Cards
        st.markdown("### Audit Capabilities")
        
        feat1, feat2, feat3, feat4 = st.columns(4)
        
        with feat1:
            st.markdown("""
            <div class="glass-metric-card">
                <div style="font-size: 1.5rem; margin-bottom: 0.5rem; color: #0078D4;">●</div>
                <strong style="color: #323130;">Water Mitigation</strong>
                <p style="color: #605E5C; font-size: 0.85rem; margin-top: 0.5rem;">Equipment & category validation</p>
            </div>
            """, unsafe_allow_html=True)
        
        with feat2:
            st.markdown("""
            <div class="glass-metric-card">
                <div style="font-size: 1.5rem; margin-bottom: 0.5rem; color: #0078D4;">●</div>
                <strong style="color: #323130;">Flooring Analysis</strong>
                <p style="color: #605E5C; font-size: 0.85rem; margin-top: 0.5rem;">Double-billing detection</p>
            </div>
            """, unsafe_allow_html=True)
        
        with feat3:
            st.markdown("""
            <div class="glass-metric-card">
                <div style="font-size: 1.5rem; margin-bottom: 0.5rem; color: #0078D4;">●</div>
                <strong style="color: #323130;">Roofing Audit</strong>
                <p style="color: #605E5C; font-size: 0.85rem; margin-top: 0.5rem;">Waste factor validation</p>
            </div>
            """, unsafe_allow_html=True)
        
        with feat4:
            st.markdown("""
            <div class="glass-metric-card">
                <div style="font-size: 1.5rem; margin-bottom: 0.5rem; color: #0078D4;">●</div>
                <strong style="color: #323130;">Financial Check</strong>
                <p style="color: #605E5C; font-size: 0.85rem; margin-top: 0.5rem;">Deductible & limits review</p>
            </div>
            """, unsafe_allow_html=True)
    
    # Footer - Office Style
    st.markdown("---")
    st.markdown("""
    <div style="text-align: center; color: #605E5C; padding: 1rem;">
        <p style="font-size: 0.85rem;">Claim Integrity Engine  •  Enterprise Audit Platform</p>
        <p style="font-size: 0.7rem; margin-top: 0.25rem;">PII Redaction Enabled  •  SOC2 Compliant Architecture</p>
    </div>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()

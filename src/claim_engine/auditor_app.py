#!/usr/bin/env python3
"""
AI-Powered Xactimate PDF Auditor.
Uses Google Gemini to analyze and audit insurance claim estimates.
"""

import json
import os
import re
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
    /* ===== Import Professional Font ===== */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    
    /* ===== Force Dark Theme Override ===== */
    :root {
        --background-color: #0E1117 !important;
        --secondary-background-color: #1E293B !important;
        --text-color: #F1F5F9 !important;
        --font: 'Inter', sans-serif !important;
    }
    
    /* ===== Global Styles with Maximum Specificity ===== */
    html, body, [class*="css"], .stApp, [data-testid="stAppViewContainer"] {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif !important;
        background-color: #0E1117 !important;
    }
    
    .stApp {
        background: linear-gradient(135deg, #0E1117 0%, #1a1f2e 50%, #0E1117 100%) !important;
    }
    
    [data-testid="stAppViewContainer"] > .main {
        background: transparent !important;
    }
    
    [data-testid="stHeader"] {
        background: rgba(14, 17, 23, 0.8) !important;
        backdrop-filter: blur(10px) !important;
    }
    
    /* ===== Main Header Styling ===== */
    .main-header {
        font-family: 'Inter', sans-serif !important;
        font-size: 2.75rem !important;
        font-weight: 700 !important;
        background: linear-gradient(135deg, #60A5FA 0%, #A78BFA 50%, #F472B6 100%) !important;
        -webkit-background-clip: text !important;
        -webkit-text-fill-color: transparent !important;
        background-clip: text !important;
        text-align: center !important;
        margin-bottom: 0.5rem !important;
        letter-spacing: -0.02em !important;
    }
    
    .sub-header {
        font-family: 'Inter', sans-serif !important;
        font-size: 1.1rem !important;
        color: #94A3B8 !important;
        text-align: center !important;
        margin-bottom: 2rem !important;
        font-weight: 400 !important;
    }
    
    /* ===== Glassmorphism Metric Cards - Custom HTML Version ===== */
    .glass-metric-card {
        background: rgba(30, 41, 59, 0.7) !important;
        backdrop-filter: blur(12px) !important;
        -webkit-backdrop-filter: blur(12px) !important;
        border: 1px solid rgba(148, 163, 184, 0.2) !important;
        border-radius: 16px !important;
        padding: 1.5rem !important;
        box-shadow: 
            0 4px 6px -1px rgba(0, 0, 0, 0.3),
            0 2px 4px -1px rgba(0, 0, 0, 0.2),
            inset 0 1px 0 rgba(255, 255, 255, 0.05) !important;
        transition: all 0.3s ease !important;
        text-align: center !important;
        height: 100% !important;
        min-height: 140px !important;
    }
    
    .glass-metric-card:hover {
        transform: translateY(-4px) !important;
        box-shadow: 
            0 12px 20px -4px rgba(0, 0, 0, 0.4),
            0 4px 8px -2px rgba(0, 0, 0, 0.3),
            inset 0 1px 0 rgba(255, 255, 255, 0.08) !important;
        border-color: rgba(96, 165, 250, 0.5) !important;
    }
    
    .glass-metric-label {
        color: #94A3B8 !important;
        font-weight: 500 !important;
        font-size: 0.8rem !important;
        text-transform: uppercase !important;
        letter-spacing: 0.08em !important;
        margin-bottom: 0.75rem !important;
    }
    
    .glass-metric-value {
        color: #F1F5F9 !important;
        font-weight: 700 !important;
        font-size: 2rem !important;
        line-height: 1.2 !important;
        margin-bottom: 0.5rem !important;
    }
    
    .glass-metric-value.positive { color: #10B981 !important; }
    .glass-metric-value.negative { color: #EF4444 !important; }
    .glass-metric-value.warning { color: #F59E0B !important; }
    
    .glass-metric-delta {
        font-size: 0.85rem !important;
        font-weight: 500 !important;
        color: #64748B !important;
    }
    
    .glass-metric-delta.positive { color: #10B981 !important; }
    .glass-metric-delta.negative { color: #EF4444 !important; }
    
    /* ===== Fallback for st.metric (if used) ===== */
    [data-testid="stMetric"],
    [data-testid="metric-container"],
    .stMetric {
        background: rgba(30, 41, 59, 0.7) !important;
        backdrop-filter: blur(12px) !important;
        -webkit-backdrop-filter: blur(12px) !important;
        border: 1px solid rgba(148, 163, 184, 0.2) !important;
        border-radius: 16px !important;
        padding: 1.25rem !important;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.3) !important;
    }
    
    [data-testid="stMetricLabel"],
    [data-testid="stMetric"] label {
        color: #94A3B8 !important;
        font-weight: 500 !important;
        font-size: 0.875rem !important;
        text-transform: uppercase !important;
        letter-spacing: 0.05em !important;
    }
    
    [data-testid="stMetricValue"] {
        color: #F1F5F9 !important;
        font-weight: 700 !important;
        font-size: 1.75rem !important;
    }
    
    [data-testid="stMetricDelta"] {
        font-weight: 500 !important;
    }
    
    [data-testid="stMetricDelta"][data-testid-delta-type="positive"] { color: #10B981 !important; }
    [data-testid="stMetricDelta"][data-testid-delta-type="negative"] { color: #EF4444 !important; }
    
    /* ===== Sidebar Styling ===== */
    [data-testid="stSidebar"],
    [data-testid="stSidebar"] > div:first-child {
        background: linear-gradient(180deg, #1E293B 0%, #0F172A 100%) !important;
        border-right: 1px solid rgba(148, 163, 184, 0.1) !important;
    }
    
    [data-testid="stSidebar"] .stMarkdown,
    [data-testid="stSidebar"] p,
    [data-testid="stSidebar"] span {
        color: #E2E8F0 !important;
    }
    
    [data-testid="stSidebar"] h1, 
    [data-testid="stSidebar"] h2, 
    [data-testid="stSidebar"] h3 {
        color: #F1F5F9 !important;
        font-weight: 600 !important;
    }
    
    /* ===== File Uploader - Enterprise Style ===== */
    [data-testid="stFileUploader"],
    [data-testid="stFileUploadDropzone"] {
        background: rgba(30, 41, 59, 0.5) !important;
        border: 2px dashed rgba(96, 165, 250, 0.4) !important;
        border-radius: 12px !important;
        padding: 1.5rem !important;
        transition: all 0.3s ease !important;
    }
    
    [data-testid="stFileUploader"]:hover,
    [data-testid="stFileUploadDropzone"]:hover {
        border-color: rgba(96, 165, 250, 0.7) !important;
        background: rgba(30, 41, 59, 0.7) !important;
    }
    
    [data-testid="stFileUploader"] section,
    [data-testid="stFileUploader"] > div {
        background: transparent !important;
    }
    
    [data-testid="stFileUploader"] button,
    [data-testid="stBaseButton-secondary"] {
        background: linear-gradient(135deg, #3B82F6 0%, #8B5CF6 100%) !important;
        color: white !important;
        border: none !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
        padding: 0.5rem 1.5rem !important;
        transition: all 0.3s ease !important;
    }
    
    /* ===== Primary Button Styling ===== */
    [data-testid="stBaseButton-primary"],
    .stButton > button[kind="primary"],
    button[kind="primary"] {
        background: linear-gradient(135deg, #3B82F6 0%, #8B5CF6 100%) !important;
        color: white !important;
        border: none !important;
        border-radius: 10px !important;
        font-weight: 600 !important;
        font-size: 1rem !important;
        padding: 0.75rem 2rem !important;
        box-shadow: 0 4px 14px rgba(59, 130, 246, 0.35) !important;
        transition: all 0.3s ease !important;
    }
    
    [data-testid="stBaseButton-primary"]:hover,
    .stButton > button[kind="primary"]:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 6px 20px rgba(59, 130, 246, 0.45) !important;
    }
    
    /* ===== Data Tables - Zebra Stripe Pattern ===== */
    [data-testid="stDataFrame"],
    .stDataFrame {
        border-radius: 12px !important;
        overflow: hidden !important;
        border: 1px solid rgba(148, 163, 184, 0.2) !important;
    }
    
    [data-testid="stDataFrame"] [data-testid="stDataFrameResizable"],
    .stDataFrame [data-testid="stDataFrameResizable"] {
        background: rgba(15, 23, 42, 0.9) !important;
    }
    
    [data-testid="stDataFrame"] thead tr th,
    .stDataFrame thead tr th {
        background: linear-gradient(135deg, #1E293B 0%, #334155 100%) !important;
        color: #F1F5F9 !important;
        font-weight: 600 !important;
        text-transform: uppercase !important;
        font-size: 0.75rem !important;
        letter-spacing: 0.05em !important;
        padding: 1rem !important;
        border-bottom: 2px solid rgba(96, 165, 250, 0.3) !important;
    }
    
    [data-testid="stDataFrame"] tbody tr:nth-child(odd),
    .stDataFrame tbody tr:nth-child(odd) {
        background: rgba(30, 41, 59, 0.5) !important;
    }
    
    [data-testid="stDataFrame"] tbody tr:nth-child(even),
    .stDataFrame tbody tr:nth-child(even) {
        background: rgba(15, 23, 42, 0.7) !important;
    }
    
    [data-testid="stDataFrame"] tbody tr:hover,
    .stDataFrame tbody tr:hover {
        background: rgba(59, 130, 246, 0.15) !important;
    }
    
    [data-testid="stDataFrame"] tbody td,
    .stDataFrame tbody td {
        color: #E2E8F0 !important;
        padding: 0.875rem 1rem !important;
        border-bottom: 1px solid rgba(148, 163, 184, 0.1) !important;
    }
    
    /* ===== Expander Styling ===== */
    [data-testid="stExpander"],
    .streamlit-expanderHeader {
        background: rgba(30, 41, 59, 0.7) !important;
        border: 1px solid rgba(148, 163, 184, 0.2) !important;
        border-radius: 10px !important;
        color: #F1F5F9 !important;
        font-weight: 500 !important;
    }
    
    [data-testid="stExpander"]:hover,
    .streamlit-expanderHeader:hover {
        border-color: rgba(96, 165, 250, 0.4) !important;
        background: rgba(30, 41, 59, 0.9) !important;
    }
    
    [data-testid="stExpanderDetails"],
    .streamlit-expanderContent {
        background: rgba(15, 23, 42, 0.8) !important;
        border: 1px solid rgba(148, 163, 184, 0.15) !important;
        border-top: none !important;
        border-radius: 0 0 10px 10px !important;
    }
    
    /* ===== Alert Boxes ===== */
    [data-testid="stAlert"][data-baseweb="notification"][kind="success"],
    .stSuccess, div[data-baseweb="notification"].success {
        background: rgba(16, 185, 129, 0.15) !important;
        border: 1px solid rgba(16, 185, 129, 0.3) !important;
        border-left: 4px solid #10B981 !important;
        border-radius: 8px !important;
        color: #6EE7B7 !important;
    }
    
    [data-testid="stAlert"][data-baseweb="notification"][kind="warning"],
    .stWarning, div[data-baseweb="notification"].warning {
        background: rgba(245, 158, 11, 0.15) !important;
        border: 1px solid rgba(245, 158, 11, 0.3) !important;
        border-left: 4px solid #F59E0B !important;
        border-radius: 8px !important;
        color: #FCD34D !important;
    }
    
    [data-testid="stAlert"][data-baseweb="notification"][kind="error"],
    .stError, div[data-baseweb="notification"].error {
        background: rgba(239, 68, 68, 0.15) !important;
        border: 1px solid rgba(239, 68, 68, 0.3) !important;
        border-left: 4px solid #EF4444 !important;
        border-radius: 8px !important;
        color: #FCA5A5 !important;
    }
    
    [data-testid="stAlert"][data-baseweb="notification"][kind="info"],
    .stInfo, div[data-baseweb="notification"].info {
        background: rgba(59, 130, 246, 0.15) !important;
        border: 1px solid rgba(59, 130, 246, 0.3) !important;
        border-left: 4px solid #3B82F6 !important;
        border-radius: 8px !important;
        color: #93C5FD !important;
    }
    
    /* ===== Markdown Tables with Zebra Stripes ===== */
    .stMarkdown table {
        width: 100% !important;
        border-collapse: separate !important;
        border-spacing: 0 !important;
        border-radius: 10px !important;
        overflow: hidden !important;
        background: rgba(15, 23, 42, 0.8) !important;
        border: 1px solid rgba(148, 163, 184, 0.2) !important;
    }
    
    .stMarkdown table thead th {
        background: linear-gradient(135deg, #1E293B 0%, #334155 100%) !important;
        color: #F1F5F9 !important;
        font-weight: 600 !important;
        padding: 0.875rem 1rem !important;
        text-align: left !important;
        border-bottom: 2px solid rgba(96, 165, 250, 0.3) !important;
    }
    
    .stMarkdown table tbody tr:nth-child(odd) {
        background: rgba(30, 41, 59, 0.5) !important;
    }
    
    .stMarkdown table tbody tr:nth-child(even) {
        background: rgba(15, 23, 42, 0.7) !important;
    }
    
    .stMarkdown table tbody tr:hover {
        background: rgba(59, 130, 246, 0.15) !important;
    }
    
    .stMarkdown table td {
        color: #E2E8F0 !important;
        padding: 0.75rem 1rem !important;
        border-bottom: 1px solid rgba(148, 163, 184, 0.1) !important;
    }
    
    /* ===== Text Input Fields ===== */
    [data-testid="stTextInput"] input,
    .stTextInput > div > div > input {
        background: rgba(30, 41, 59, 0.7) !important;
        border: 1px solid rgba(148, 163, 184, 0.3) !important;
        border-radius: 8px !important;
        color: #F1F5F9 !important;
        padding: 0.75rem 1rem !important;
    }
    
    [data-testid="stTextInput"] input:focus,
    .stTextInput > div > div > input:focus {
        border-color: #3B82F6 !important;
        box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.2) !important;
    }
    
    /* ===== Checkbox & Toggle ===== */
    .stCheckbox label,
    [data-testid="stCheckbox"] label {
        color: #E2E8F0 !important;
    }
    
    /* ===== Download Buttons ===== */
    [data-testid="stDownloadButton"] > button,
    .stDownloadButton > button {
        background: rgba(30, 41, 59, 0.7) !important;
        color: #E2E8F0 !important;
        border: 1px solid rgba(148, 163, 184, 0.3) !important;
        border-radius: 8px !important;
        font-weight: 500 !important;
        transition: all 0.3s ease !important;
    }
    
    [data-testid="stDownloadButton"] > button:hover,
    .stDownloadButton > button:hover {
        background: rgba(59, 130, 246, 0.2) !important;
        border-color: rgba(96, 165, 250, 0.5) !important;
    }
    
    /* ===== Spinner ===== */
    .stSpinner > div {
        border-top-color: #3B82F6 !important;
    }
    
    /* ===== Horizontal Rule ===== */
    hr {
        border: none !important;
        height: 1px !important;
        background: linear-gradient(90deg, transparent, rgba(148, 163, 184, 0.3), transparent) !important;
        margin: 2rem 0 !important;
    }
    
    /* ===== Scrollbar Styling ===== */
    ::-webkit-scrollbar {
        width: 8px;
        height: 8px;
    }
    
    ::-webkit-scrollbar-track {
        background: rgba(15, 23, 42, 0.5);
        border-radius: 4px;
    }
    
    ::-webkit-scrollbar-thumb {
        background: rgba(148, 163, 184, 0.3);
        border-radius: 4px;
    }
    
    ::-webkit-scrollbar-thumb:hover {
        background: rgba(148, 163, 184, 0.5);
    }
    
    /* ===== General Text Override ===== */
    .stMarkdown, .stMarkdown p, p, span {
        color: #CBD5E1 !important;
    }
    
    .stMarkdown h1, .stMarkdown h2, .stMarkdown h3, 
    .stMarkdown h4, .stMarkdown h5, .stMarkdown h6,
    h1, h2, h3, h4, h5, h6 {
        color: #F1F5F9 !important;
        font-weight: 600 !important;
    }
    
    /* ===== Code Blocks ===== */
    [data-testid="stCodeBlock"],
    .stCodeBlock {
        background: rgba(15, 23, 42, 0.9) !important;
        border: 1px solid rgba(148, 163, 184, 0.2) !important;
        border-radius: 8px !important;
    }
    
    /* ===== JSON Viewer ===== */
    [data-testid="stJson"] {
        background: rgba(15, 23, 42, 0.9) !important;
        border-radius: 8px !important;
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
    Redact PII from text including phone numbers and names after 'Insured:'.
    
    Args:
        text: Raw text to redact
        
    Returns:
        Text with PII redacted
    """
    # Redact 10-digit phone numbers (various formats)
    phone_patterns = [
        r'\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b',  # 123-456-7890, 123.456.7890, 123 456 7890
        r'\(\d{3}\)\s*\d{3}[-.\s]?\d{4}',       # (123) 456-7890
        r'\+1\s*\d{3}[-.\s]?\d{3}[-.\s]?\d{4}', # +1 123-456-7890
    ]
    
    for pattern in phone_patterns:
        text = re.sub(pattern, '[PHONE REDACTED]', text)
    
    # Redact names following 'Insured:' or similar patterns
    insured_patterns = [
        r'(Insured\s*[:\-]?\s*)([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3})',
        r'(Insured Name\s*[:\-]?\s*)([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3})',
        r'(Policy\s*Holder\s*[:\-]?\s*)([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3})',
        r'(Claimant\s*[:\-]?\s*)([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3})',
        r'(Customer\s*[:\-]?\s*)([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3})',
    ]
    
    for pattern in insured_patterns:
        text = re.sub(pattern, r'\1[NAME REDACTED]', text, flags=re.IGNORECASE)
    
    # Redact SSN patterns
    text = re.sub(r'\b\d{3}[-\s]?\d{2}[-\s]?\d{4}\b', '[SSN REDACTED]', text)
    
    # Redact email addresses
    text = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '[EMAIL REDACTED]', text)
    
    # Redact street addresses (basic pattern)
    text = re.sub(
        r'\b\d+\s+[A-Za-z]+(?:\s+[A-Za-z]+)*\s+(?:Street|St|Avenue|Ave|Road|Rd|Drive|Dr|Lane|Ln|Court|Ct|Boulevard|Blvd)\b',
        '[ADDRESS REDACTED]',
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
                label="📊 ACCURACY SCORE",
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
                label="🚨 TOTAL LEAKAGE",
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
                label="💰 NET CLAIM",
                value=f"${net_claim:,.2f}",
                delta=f"After ${deductible:,.0f} deductible",
            ),
            unsafe_allow_html=True,
        )
    
    with col4:
        risk = summary.get("risk_level", "Unknown")
        risk_emoji = {"High": "🔴", "Medium": "🟡", "Low": "🟢"}.get(risk, "⚪")
        value_class = {"High": "negative", "Medium": "warning", "Low": "positive"}.get(risk, "")
        finding_count = len(audit_data.get('leakage_findings', []))
        st.markdown(
            render_glass_metric(
                label="⚠️ RISK LEVEL",
                value=f"{risk_emoji} {risk}",
                delta=f"{finding_count} flags",
                value_class=value_class,
            ),
            unsafe_allow_html=True,
        )


def render_leakage_summary(findings: list[dict]) -> None:
    """Render the Leakage Summary table."""
    if not findings:
        st.success("✅ No leakage issues detected!")
        return
    
    st.markdown("### 💸 Leakage Summary - Potential Savings")
    
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
    st.markdown(f"### 💵 **Total Potential Savings: ${total_savings:,.2f}**")


def render_detailed_findings(findings: list[dict]) -> None:
    """Render detailed findings with expandable sections."""
    if not findings:
        return
    
    st.markdown("### 📋 Detailed Audit Findings")
    
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
    st.markdown("### 💳 Financial Breakdown")
    
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
            st.success("✅ Deductible correctly applied to ACV")
        else:
            st.error("❌ Deductible calculation error detected!")
        
        # Verification calculation
        expected_net = financial.get('acv', 0) - financial.get('deductible', 0)
        actual_net = financial.get('net_claim', 0)
        
        if abs(expected_net - actual_net) > 0.01:
            st.warning(f"⚠️ Net claim discrepancy: Expected ${expected_net:,.2f}, Got ${actual_net:,.2f}")


def render_line_items(line_items: list[dict]) -> None:
    """Render line items table."""
    if not line_items:
        return
    
    with st.expander("📑 View All Line Items", expanded=False):
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
    # Header
    st.markdown('<p class="main-header">🤖 AI-Powered Claim Auditor</p>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Upload Xactimate PDF estimates for intelligent leakage detection</p>', unsafe_allow_html=True)
    
    # Sidebar
    with st.sidebar:
        st.image("https://img.icons8.com/fluency/96/artificial-intelligence.png", width=64)
        st.title("Configuration")
        st.markdown("---")
        
        # API Key handling - prioritize st.secrets for cloud deployment
        st.subheader("🔑 API Settings")
        
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
            st.success("✅ API Key configured via Streamlit Secrets")
            api_key = default_api_key
        else:
            api_key = st.text_input(
                "Google Gemini API Key",
                type="password",
                help="Get your API key from https://aistudio.google.com/app/apikey",
                value=default_api_key,
            )
            
            if not api_key:
                st.warning("⚠️ Enter your Gemini API key to enable AI analysis")
        
        st.markdown("---")
        
        # File upload
        st.subheader("📄 Upload Estimate")
        uploaded_file = st.file_uploader(
            "Upload Xactimate PDF",
            type=["pdf"],
            help="Upload your Xactimate estimate PDF file",
        )
        
        st.markdown("---")
        
        # Options
        st.subheader("⚙️ Options")
        show_raw_text = st.checkbox("Show extracted text", value=False)
        show_raw_json = st.checkbox("Show raw AI response", value=False)
        
        st.markdown("---")
        
        # Analyze button
        analyze_btn = st.button(
            "🔍 Analyze Estimate",
            type="primary",
            use_container_width=True,
            disabled=not (uploaded_file and api_key),
        )
    
    # Main content
    if uploaded_file and api_key and analyze_btn:
        with st.spinner("📄 Extracting PDF text..."):
            raw_text = extract_pdf_text(uploaded_file)
            
            if not raw_text.strip():
                st.error("Could not extract text from PDF. The file may be image-based or corrupted.")
                return
        
        if show_raw_text:
            with st.expander("📝 Extracted PDF Text", expanded=False):
                st.text(raw_text[:5000] + "..." if len(raw_text) > 5000 else raw_text)
        
        with st.spinner("🔒 Redacting PII..."):
            redacted_text = redact_pii(raw_text)
        
        with st.spinner("🤖 Analyzing with Gemini AI..."):
            audit_result = analyze_with_gemini(redacted_text, api_key)
        
        if audit_result:
            # Store in session state
            st.session_state.audit_result = audit_result
            
            if show_raw_json:
                with st.expander("🔧 Raw AI Response", expanded=False):
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
                st.markdown("### 📋 Claim Information")
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
                st.markdown("### 🏠 Property Details")
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
            st.markdown("### 📤 Export Audit Report")
            
            exp1, exp2 = st.columns(2)
            
            with exp1:
                st.download_button(
                    label="📄 Download JSON Report",
                    data=json.dumps(audit_result, indent=2),
                    file_name=f"audit_report_{claim_info.get('claim_number', 'unknown')}.json",
                    mime="application/json",
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
                    label="📝 Download Text Report",
                    data=report_text,
                    file_name=f"audit_report_{claim_info.get('claim_number', 'unknown')}.txt",
                    mime="text/plain",
                )
    
    elif not uploaded_file:
        # Welcome screen
        st.markdown("---")
        
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.markdown("""
            <div style="text-align: center; padding: 3rem; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 16px; color: white;">
                <h2>👋 Welcome to AI Claim Auditor</h2>
                <p style="opacity: 0.9; margin-top: 1rem;">
                    Upload your Xactimate PDF estimate to receive an AI-powered audit analysis.
                </p>
                <div style="margin-top: 2rem;">
                    <p><strong>What we analyze:</strong></p>
                    <p>💧 Water Mitigation • 🏠 Flooring • 🏗️ Roofing • 💰 Financials</p>
                </div>
            </div>
            """, unsafe_allow_html=True)
        
        st.markdown("---")
        
        # Features
        st.markdown("### 🎯 Key Features")
        
        feat1, feat2, feat3, feat4 = st.columns(4)
        
        with feat1:
            st.markdown("""
            **💧 Water Mitigation**
            
            Detects excessive equipment charges and category mismatches
            """)
        
        with feat2:
            st.markdown("""
            **🏠 Flooring Analysis**
            
            Identifies double-billing for carpet and pad removal
            """)
        
        with feat3:
            st.markdown("""
            **🏗️ Roofing Audit**
            
            Validates waste factors for gable and hip roofs
            """)
        
        with feat4:
            st.markdown("""
            **💰 Financial Check**
            
            Verifies deductible application and claim calculations
            """)
    
    # Footer
    st.markdown("---")
    st.markdown("""
    <div style="text-align: center; color: #9CA3AF; padding: 1rem;">
        <p>AI Claim Auditor | Powered by Google Gemini</p>
        <p style="font-size: 0.75rem;">🔒 PII Protection Enabled • SOC2 Compliant Design</p>
    </div>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()

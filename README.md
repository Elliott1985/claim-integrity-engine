# Claim Integrity Engine  
AI-Assisted Claim Leakage Detection & QA Automation System

A modular Python-based insurance claim auditing engine designed to detect billing discrepancies, policy violations, and potential claim leakage risks in property insurance estimates.

Built to simulate enterprise-grade QA validation logic for claims operations and insurtech automation workflows.

---

## Overview

Claim Integrity Engine analyzes structured claim data and applies domain-specific validation rules to flag high-risk indicators such as deductible misapplication, duplicate line items, excessive remediation equipment usage, and coverage limit violations.

Designed for:

- Claims QA Reviewers  
- Audit & Compliance Teams  
- Claims Operations Leaders  
- Insurtech Product Teams  
- Workflow Automation Engineers  

---

## Core Capabilities

### Financial & Policy Validation
- Deductible verification
- Coverage A / B / C validation
- Sub-limit enforcement
- Net claim recalculation checks
- Payment discrepancy detection

### Water Remediation Module (WTR)
- Equipment-to-square-footage validation (Air Movers / Dehumidifiers)
- Category-based (Cat 1 / 2 / 3) billing verification
- Daily monitoring labor validation
- Equipment overuse risk flagging

### Flooring & Finish Module (FCC / FNC)
- Waste percentage calculation and anomaly detection
- Overlap detection (e.g., carpet + pad removal double-billing)
- Floor preparation gap analysis

### General Repair & Remediation
- Double-dip detection (redundant or overlapping line items)
- Content protection verification
- Rule-based anomaly flagging

---

## Business Objective

This engine demonstrates how structured rule-based automation can:

- Standardize QA review logic across files
- Reduce manual audit time
- Identify potential overpayment indicators
- Improve estimate validation consistency
- Detect claim leakage patterns prior to payment issuance

The project serves as a prototype for scalable insurance workflow automation and structured audit intelligence systems.

---

## Compliance & Security

- PII redaction module (SOC2-conscious design)
- Structured audit scorecard output
- Modular rule engine architecture
- Extensible validation framework

---

## Installation

```bash
# Clone the repository
git clone <repository-url>
cd claim-integrity-engine

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -e ".[dev]"
```

---

## Usage

```python
from claim_engine import ClaimIntegrityEngine

# Initialize the engine
engine = ClaimIntegrityEngine()

# Load and audit a claim
claim_data = {
    "claim_id": "CLM-2024-001",
    "policy": {
        "deductible": 1000,
        "coverage_a": 250000,
        "coverage_b": 25000,
        "coverage_c": 125000
    },
    "line_items": [
        {"code": "WTR_AIRF", "description": "Air Mover - per unit/day", "quantity": 5, "unit_price": 35.00},
        {"code": "WTR_DEHUM", "description": "Dehumidifier - per unit/day", "quantity": 2, "unit_price": 75.00}
    ],
    "property_details": {
        "affected_rooms": [
            {"name": "Living Room", "sqft": 300},
            {"name": "Kitchen", "sqft": 150}
        ],
        "water_category": 1
    }
}

# Run audit
scorecard = engine.audit(claim_data)

# View results
scorecard.print_summary()
```

---

## Architecture

```
src/claim_engine/
├── core/
│   ├── rule_engine.py      # Dictionary-based rule engine
│   ├── xactimate_parser.py # Regex-based code parsing
│   └── models.py           # Pydantic data models
├── modules/
│   ├── financial.py        # Financial validation
│   ├── water_remediation.py# WTR audits
│   ├── flooring.py         # FCC/FNC audits
│   └── general_repair.py   # General repair audits
├── utils/
│   └── pii_redaction.py    # SOC2-aligned redaction utilities
├── reporting/
│   └── scorecard.py        # Audit scorecard generation
└── engine.py               # Main orchestration layer
```

---

## Design Principles

- Modular rule-based architecture  
- Domain-specific validation logic  
- Extensible rule injection framework  
- Separation of financial vs operational audits  
- Automation-ready reporting output  

---

## Adding Custom Rules

The rule engine supports dynamic extensibility:

```python
from claim_engine.core.rule_engine import RuleEngine

RuleEngine.add_rule(
    code_pattern=r"WTR_.*",
    rule_name="custom_water_rule",
    validator=my_custom_validator,
    category="leakage"
)
```

Designed to simulate scalable enterprise audit rule frameworks.

---

## Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=claim_engine
```

---

## Future Enhancements

- ML-based anomaly scoring
- Historical claim pattern analysis
- API integration for live estimate ingestion
- Dashboard visualization layer
- Severity-based risk scoring engine

---

## License

MIT License


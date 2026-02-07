# Universal Claim Integrity & Leakage Engine

A Python-based modular insurance claim auditing system designed to detect billing discrepancies, policy violations, and leakage risks in property insurance claims.

## Features

### Phase 1: Financial & Policy Validation
- Deductible verification
- Coverage Limits (A, B, C) validation
- Sub-limits enforcement
- Net claim calculations

### Phase 2: Water Remediation Module (WTR)
- Equipment audit (Air Movers, Dehumidifiers vs. room square footage)
- Daily monitoring labor validation
- Category-based (Cat 1/2/3) billing verification

### Phase 3: Flooring & Finish Module (FCC/FNC)
- Waste percentage calculations and auditing
- Overlap detection (e.g., carpet + pad removal)
- Floor preparation gap analysis

### Phase 4: General Repair & Remediation
- Double-dip detection (redundant line items)
- Content protection verification

### Compliance & Security
- PII Redaction for SOC2 compliance
- Comprehensive Audit Scorecard output

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
        {"code": "WTR_DEHUM", "description": "Dehumidifier - per unit/day", "quantity": 2, "unit_price": 75.00},
        # ... more line items
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

## Architecture

```
src/claim_engine/
├── core/
│   ├── rule_engine.py      # Dictionary-based rule engine
│   ├── xactimate_parser.py # Regex-based code parsing
│   └── models.py           # Pydantic data models
├── modules/
│   ├── financial.py        # Phase 1: Financial validation
│   ├── water_remediation.py# Phase 2: WTR audits
│   ├── flooring.py         # Phase 3: FCC/FNC audits
│   └── general_repair.py   # Phase 4: General repairs
├── utils/
│   └── pii_redaction.py    # SOC2 compliance
├── reporting/
│   └── scorecard.py        # Audit scorecard generation
└── engine.py               # Main orchestrator
```

## Adding Custom Rules

The rule engine uses a dictionary-based approach for easy extensibility:

```python
from claim_engine.core.rule_engine import RuleEngine

# Add a new rule
RuleEngine.add_rule(
    code_pattern=r"WTR_.*",
    rule_name="custom_water_rule",
    validator=my_custom_validator,
    category="leakage"
)
```

## Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=claim_engine
```

## License

MIT License

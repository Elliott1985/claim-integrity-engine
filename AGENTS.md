# AGENTS.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

## Build & Development Commands

```bash
# Install package in development mode
pip3 install -e ".[dev]"

# Run all tests
pytest

# Run single test file
pytest tests/test_engine.py

# Run single test
pytest tests/test_engine.py::TestClaimIntegrityEngine::test_audit_returns_scorecard

# Run with coverage
pytest --cov=claim_engine

# Lint and format
black src/ tests/
ruff check src/ tests/
mypy src/
```

## Architecture Overview

### Audit Pipeline

The engine executes 4 audit phases sequentially via `ClaimIntegrityEngine.audit()`:

1. **Financial Validation** (`modules/financial.py`) - Policy limits, deductibles, sub-limits
2. **Water Remediation** (`modules/water_remediation.py`) - Equipment counts vs sqft, monitoring labor, water category billing
3. **Flooring** (`modules/flooring.py`) - Waste percentages, carpet/pad overlap, floor prep gaps
4. **General Repair** (`modules/general_repair.py`) - Double-dip detection, content protection

Each module is independently toggleable via engine constructor flags.

### Rule Engine Pattern

Each validator module follows this pattern:
1. Creates its own `RuleEngine` instance in `__init__`
2. Registers `AuditRule` objects via `_register_rules()` with rule ID, name, category, severity, and validator function
3. Validator functions receive `ClaimData` and return `list[AuditFinding]`
4. `validate()` method executes all registered rules

To add a new rule to an existing module:
```python
self.engine.add_rule(
    AuditRule(
        rule_id="WTR-006",
        name="Rule Name",
        description="What it checks",
        category=AuditCategory.LEAKAGE,  # or FINANCIAL, SUPPLEMENT_RISK
        severity=AuditSeverity.WARNING,  # INFO, WARNING, ERROR, CRITICAL
        validator=self._my_validator_method,
    )
)
```

### Xactimate Code Detection

`core/xactimate_parser.py` uses compiled regex patterns to identify line item types:
- Category patterns: `WTR`, `FCC`, `FNC`, `DRY`, `PNT`, `CLN`, `DEM`, `CNT`, `GEN`
- Equipment patterns: air movers, dehumidifiers, air scrubbers
- Flooring patterns: carpet, hardwood, tile, vinyl, tear-out, install, leveling
- Double-dip groups: pre-defined pattern pairs that indicate potential billing overlap

Validators use `get_parser()` singleton and match against `item.code` + `item.description`.

### Scorecard Construction

`ScorecardBuilder` aggregates findings and computes summary stats. `ScorecardFormatter` outputs to text, JSON, or HTML. Risk score is calculated from severity weights (INFO=5, WARNING=15, ERROR=30, CRITICAL=50).

### Data Flow

```
dict/ClaimData → ClaimIntegrityEngine.audit()
    → FinancialValidator.validate() → list[AuditFinding]
    → WaterRemediationValidator.validate() → list[AuditFinding]
    → FlooringValidator.validate() → list[AuditFinding]
    → GeneralRepairValidator.validate() → list[AuditFinding]
    → ScorecardBuilder.add_findings() → AuditScorecard
    → PIIRedactor.redact_scorecard() (optional)
    → AuditScorecard
```

### Adding a New Audit Module

1. Create `modules/new_module.py` with a validator class following existing pattern
2. Register rules in `_register_rules()` with appropriate categories
3. Add validator property and enable flag to `ClaimIntegrityEngine`
4. Add module execution in `engine.audit()` between appropriate phases
5. Export from `modules/__init__.py`

#!/usr/bin/env python3
"""
Sample Audit Script.
Demonstrates usage of the Claim Integrity Engine.
"""

from decimal import Decimal

from claim_engine import (
    ClaimData,
    ClaimIntegrityEngine,
    LineItem,
    PolicyCoverage,
    PropertyDetails,
    Room,
    WaterCategory,
)


def create_sample_claim() -> ClaimData:
    """Create a sample claim for demonstration."""
    return ClaimData(
        claim_id="CLM-2024-WTR-001",
        policy=PolicyCoverage(
            deductible=Decimal("1000"),
            coverage_a=Decimal("250000"),
            coverage_b=Decimal("25000"),
            coverage_c=Decimal("125000"),
            water_damage_limit=Decimal("15000"),
        ),
        line_items=[
            # Water Remediation Items
            LineItem(
                code="WTR_AIRF",
                description="Air Mover - per unit/day",
                quantity=12,  # Excessive for the sqft
                unit="EA",
                unit_price=Decimal("35.00"),
                days=5,
            ),
            LineItem(
                code="WTR_DEHUM",
                description="Dehumidifier - Large",
                quantity=3,
                unit="EA",
                unit_price=Decimal("75.00"),
                days=5,
            ),
            LineItem(
                code="WTR_MONITOR",
                description="Daily Monitoring - Technician",
                quantity=7,  # More days than equipment
                unit="DAY",
                unit_price=Decimal("85.00"),
            ),
            LineItem(
                code="WTR_PPE",
                description="PPE - Tyvek Suits, Respirators",  # Cat 3 item for Cat 1 loss
                quantity=10,
                unit="EA",
                unit_price=Decimal("45.00"),
            ),
            # Flooring Items
            LineItem(
                code="FCC_CPTREM",
                description="Tear out Carpet - Living Room",
                quantity=300,
                unit="SF",
                unit_price=Decimal("0.85"),
                room="Living Room",
            ),
            LineItem(
                code="FCC_PADREM",
                description="Tear out Pad - Living Room",  # Separate pad removal (potential overlap)
                quantity=300,
                unit="SF",
                unit_price=Decimal("0.35"),
                room="Living Room",
            ),
            LineItem(
                code="FCC_CPTINST",
                description="Install Carpet - Living Room",
                quantity=300,
                unit="SF",
                unit_price=Decimal("4.50"),
                room="Living Room",
            ),
            LineItem(
                code="FCC_WASTE",
                description="Carpet Waste/Cutoff",
                quantity=60,  # 20% waste - excessive
                unit="SF",
                unit_price=Decimal("4.50"),
                room="Living Room",
            ),
            LineItem(
                code="FNC_HWDINST",
                description="Install Hardwood Flooring - Kitchen",
                quantity=150,
                unit="SF",
                unit_price=Decimal("8.50"),
                room="Kitchen",
            ),
            # General Repair Items
            LineItem(
                code="GEN_DOOR",
                description="Pre-hung Interior Door",
                quantity=2,
                unit="EA",
                unit_price=Decimal("285.00"),
            ),
            LineItem(
                code="GEN_HINGE",
                description="Door Hinges - 3.5 inch",  # Double-dip with pre-hung door
                quantity=6,
                unit="EA",
                unit_price=Decimal("8.50"),
            ),
            LineItem(
                code="DEM_DRYWALL",
                description="Demo Drywall - water damaged",
                quantity=200,
                unit="SF",
                unit_price=Decimal("1.25"),
            ),
            LineItem(
                code="DEM_WALLPAPER",
                description="Remove Wallpaper",  # Double-dip - wallpaper comes off with drywall
                quantity=100,
                unit="SF",
                unit_price=Decimal("0.75"),
            ),
        ],
        property_details=PropertyDetails(
            affected_rooms=[
                Room(name="Living Room", sqft=300, floor_type="carpet"),
                Room(name="Kitchen", sqft=150, floor_type="hardwood"),
            ],
            water_category=WaterCategory.CATEGORY_1,  # Clean water
            property_type="residential",
        ),
    )


def main() -> None:
    """Run sample audit demonstration."""
    print("=" * 70)
    print("CLAIM INTEGRITY ENGINE - SAMPLE AUDIT")
    print("=" * 70)
    print()

    # Create sample claim
    claim = create_sample_claim()
    print(f"Auditing Claim: {claim.claim_id}")
    print(f"Gross Claim: ${claim.gross_claim:,.2f}")
    print(f"Line Items: {len(claim.line_items)}")
    print()

    # Initialize engine
    engine = ClaimIntegrityEngine()
    print(f"Enabled Modules: {', '.join(engine.get_enabled_modules())}")
    print()

    # Run audit
    print("Running audit...")
    formatter = engine.audit_with_formatter(claim)

    # Print full report
    print()
    formatter.print_full()

    # Also save as JSON
    print()
    print("-" * 70)
    print("JSON Output (first 500 chars):")
    print("-" * 70)
    json_output = formatter.to_json()
    print(json_output[:500] + "..." if len(json_output) > 500 else json_output)

    # Demonstrate PII redaction
    print()
    print("-" * 70)
    print("PII REDACTION DEMO")
    print("-" * 70)

    # Add some PII to metadata for demo
    claim_with_pii = create_sample_claim()
    claim_with_pii.metadata = {
        "insured_name": "John Smith",
        "phone": "555-123-4567",
        "email": "john.smith@example.com",
        "property_address": "123 Main Street",
    }

    # Audit with PII redaction
    redacted_scorecard = engine.audit(claim_with_pii, redact_pii=True)
    print(f"Redacted: {redacted_scorecard.redacted}")
    print("PII has been automatically redacted from the scorecard.")


if __name__ == "__main__":
    main()

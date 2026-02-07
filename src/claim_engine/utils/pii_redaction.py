"""
PII Redaction Module for SOC2 Compliance.
Redacts personally identifiable information from claim data.
"""

import re
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from ..core.models import AuditScorecard, ClaimData


@dataclass
class RedactionResult:
    """Result of a redaction operation."""

    original_value: str
    redacted_value: str
    pii_type: str
    field_path: str


class PIIRedactor:
    """
    Redacts PII from claim data for SOC2 compliance.

    Supports redaction of:
    - Names
    - Social Security Numbers (SSN)
    - Phone numbers
    - Email addresses
    - Street addresses
    - Credit card numbers
    - Bank account numbers
    - Driver's license numbers
    """

    # Redaction placeholder
    REDACTED = "[REDACTED]"

    # PII detection patterns
    PATTERNS: dict[str, re.Pattern[str]] = {
        "ssn": re.compile(r"\b\d{3}[-\s]?\d{2}[-\s]?\d{4}\b"),
        "phone": re.compile(
            r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"
        ),
        "email": re.compile(
            r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"
        ),
        "credit_card": re.compile(
            r"\b(?:\d{4}[-\s]?){3}\d{4}\b|\b\d{15,16}\b"
        ),
        "bank_account": re.compile(r"\b\d{8,17}\b"),  # Broad pattern, use with caution
        "drivers_license": re.compile(
            r"\b[A-Z]{1,2}\d{5,8}\b"  # Simplified pattern, varies by state
        ),
        "date_of_birth": re.compile(
            r"\b(?:0?[1-9]|1[0-2])[/\-](?:0?[1-9]|[12]\d|3[01])[/\-](?:19|20)\d{2}\b"
        ),
        "zip_code": re.compile(r"\b\d{5}(?:-\d{4})?\b"),
    }

    # Address pattern (more complex)
    ADDRESS_PATTERN = re.compile(
        r"\b\d+\s+[\w\s]+(?:street|st|avenue|ave|road|rd|boulevard|blvd|"
        r"drive|dr|court|ct|lane|ln|way|circle|cir|place|pl)\b",
        re.IGNORECASE,
    )

    # Name patterns (common titles followed by words)
    NAME_TITLE_PATTERN = re.compile(
        r"\b(?:Mr\.|Mrs\.|Ms\.|Dr\.|Prof\.)\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?",
        re.IGNORECASE,
    )

    # Fields that commonly contain PII
    PII_FIELDS: set[str] = {
        "name",
        "first_name",
        "last_name",
        "full_name",
        "insured_name",
        "claimant_name",
        "policyholder",
        "ssn",
        "social_security",
        "phone",
        "telephone",
        "mobile",
        "email",
        "email_address",
        "address",
        "street_address",
        "mailing_address",
        "property_address",
        "date_of_birth",
        "dob",
        "birth_date",
        "driver_license",
        "drivers_license",
        "dl_number",
        "account_number",
        "routing_number",
        "credit_card",
        "card_number",
    }

    def __init__(
        self,
        redact_names: bool = True,
        redact_addresses: bool = True,
        custom_patterns: dict[str, re.Pattern[str]] | None = None,
    ) -> None:
        """
        Initialize the PII redactor.

        Args:
            redact_names: Whether to redact detected names
            redact_addresses: Whether to redact detected addresses
            custom_patterns: Additional custom patterns to redact
        """
        self.redact_names = redact_names
        self.redact_addresses = redact_addresses
        self.custom_patterns = custom_patterns or {}
        self._redaction_log: list[RedactionResult] = []

    def redact_string(self, value: str, field_path: str = "") -> str:
        """
        Redact PII from a string value.

        Args:
            value: The string to redact
            field_path: The path to this field (for logging)

        Returns:
            The redacted string
        """
        if not isinstance(value, str) or not value:
            return value

        result = value

        # Apply standard patterns
        for pii_type, pattern in self.PATTERNS.items():
            matches = pattern.findall(result)
            for match in matches:
                if match:
                    self._redaction_log.append(
                        RedactionResult(
                            original_value=match,
                            redacted_value=self.REDACTED,
                            pii_type=pii_type,
                            field_path=field_path,
                        )
                    )
                    result = result.replace(match, self.REDACTED)

        # Apply custom patterns
        for pii_type, pattern in self.custom_patterns.items():
            matches = pattern.findall(result)
            for match in matches:
                if match:
                    self._redaction_log.append(
                        RedactionResult(
                            original_value=match,
                            redacted_value=self.REDACTED,
                            pii_type=f"custom_{pii_type}",
                            field_path=field_path,
                        )
                    )
                    result = result.replace(match, self.REDACTED)

        # Redact addresses if enabled
        if self.redact_addresses:
            matches = self.ADDRESS_PATTERN.findall(result)
            for match in matches:
                if match:
                    self._redaction_log.append(
                        RedactionResult(
                            original_value=match,
                            redacted_value=self.REDACTED,
                            pii_type="address",
                            field_path=field_path,
                        )
                    )
                    result = result.replace(match, self.REDACTED)

        # Redact names with titles if enabled
        if self.redact_names:
            matches = self.NAME_TITLE_PATTERN.findall(result)
            for match in matches:
                if match:
                    self._redaction_log.append(
                        RedactionResult(
                            original_value=match,
                            redacted_value=self.REDACTED,
                            pii_type="name",
                            field_path=field_path,
                        )
                    )
                    result = result.replace(match, self.REDACTED)

        return result

    def redact_dict(
        self, data: dict[str, Any], path_prefix: str = ""
    ) -> dict[str, Any]:
        """
        Recursively redact PII from a dictionary.

        Args:
            data: The dictionary to redact
            path_prefix: Current path prefix for logging

        Returns:
            The redacted dictionary
        """
        result = {}

        for key, value in data.items():
            field_path = f"{path_prefix}.{key}" if path_prefix else key
            key_lower = key.lower()

            # Check if this is a known PII field
            is_pii_field = key_lower in self.PII_FIELDS or any(
                pii_key in key_lower for pii_key in self.PII_FIELDS
            )

            if isinstance(value, dict):
                result[key] = self.redact_dict(value, field_path)
            elif isinstance(value, list):
                result[key] = self.redact_list(value, field_path)
            elif isinstance(value, str):
                if is_pii_field:
                    # Redact entire field if it's a known PII field
                    self._redaction_log.append(
                        RedactionResult(
                            original_value=value,
                            redacted_value=self.REDACTED,
                            pii_type="pii_field",
                            field_path=field_path,
                        )
                    )
                    result[key] = self.REDACTED
                else:
                    result[key] = self.redact_string(value, field_path)
            else:
                result[key] = value

        return result

    def redact_list(self, data: list[Any], path_prefix: str = "") -> list[Any]:
        """
        Recursively redact PII from a list.

        Args:
            data: The list to redact
            path_prefix: Current path prefix for logging

        Returns:
            The redacted list
        """
        result = []

        for i, item in enumerate(data):
            field_path = f"{path_prefix}[{i}]"

            if isinstance(item, dict):
                result.append(self.redact_dict(item, field_path))
            elif isinstance(item, list):
                result.append(self.redact_list(item, field_path))
            elif isinstance(item, str):
                result.append(self.redact_string(item, field_path))
            else:
                result.append(item)

        return result

    def redact_claim(self, claim: ClaimData) -> ClaimData:
        """
        Redact PII from claim data.

        Args:
            claim: The claim data to redact

        Returns:
            A new ClaimData instance with PII redacted
        """
        # Convert to dict, redact, and reconstruct
        claim_dict = claim.model_dump()
        redacted_dict = self.redact_dict(claim_dict)

        # Handle claim_id specially (preserve structure but redact if it looks like PII)
        if "claim_id" in redacted_dict:
            claim_id = redacted_dict["claim_id"]
            # Only redact if it looks like it contains PII
            if any(p.search(str(claim_id)) for p in self.PATTERNS.values()):
                redacted_dict["claim_id"] = f"CLM-{self.REDACTED}"

        return ClaimData.model_validate(redacted_dict)

    def redact_scorecard(self, scorecard: AuditScorecard) -> AuditScorecard:
        """
        Redact PII from an audit scorecard.

        Args:
            scorecard: The scorecard to redact

        Returns:
            A new AuditScorecard instance with PII redacted
        """
        scorecard_dict = scorecard.model_dump()
        redacted_dict = self.redact_dict(scorecard_dict)
        redacted_dict["redacted"] = True

        return AuditScorecard.model_validate(redacted_dict)

    def get_redaction_log(self) -> list[RedactionResult]:
        """Get the log of all redactions performed."""
        return self._redaction_log.copy()

    def clear_redaction_log(self) -> None:
        """Clear the redaction log."""
        self._redaction_log.clear()

    def get_redaction_summary(self) -> dict[str, int]:
        """Get a summary of redactions by type."""
        summary: dict[str, int] = {}
        for result in self._redaction_log:
            summary[result.pii_type] = summary.get(result.pii_type, 0) + 1
        return summary


# Convenience function
def redact_pii(data: ClaimData | AuditScorecard | dict[str, Any]) -> Any:
    """
    Convenience function to redact PII from various data types.

    Args:
        data: The data to redact (ClaimData, AuditScorecard, or dict)

    Returns:
        The redacted data of the same type
    """
    redactor = PIIRedactor()

    if isinstance(data, ClaimData):
        return redactor.redact_claim(data)
    elif isinstance(data, AuditScorecard):
        return redactor.redact_scorecard(data)
    elif isinstance(data, dict):
        return redactor.redact_dict(data)
    else:
        raise TypeError(f"Unsupported data type: {type(data)}")

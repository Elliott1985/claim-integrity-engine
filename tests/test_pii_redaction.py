"""
Tests for PII redaction functionality.
"""

import pytest

from claim_engine.utils.pii_redaction import PIIRedactor, redact_pii


class TestPIIRedactor:
    """Tests for PIIRedactor class."""

    @pytest.fixture
    def redactor(self) -> PIIRedactor:
        """Create a redactor instance."""
        return PIIRedactor()

    def test_redact_ssn(self, redactor: PIIRedactor) -> None:
        """Test SSN redaction."""
        text = "SSN: 123-45-6789"
        result = redactor.redact_string(text)

        assert "123-45-6789" not in result
        assert "[REDACTED]" in result

    def test_redact_phone(self, redactor: PIIRedactor) -> None:
        """Test phone number redaction."""
        text = "Call me at 555-123-4567"
        result = redactor.redact_string(text)

        assert "555-123-4567" not in result
        assert "[REDACTED]" in result

    def test_redact_email(self, redactor: PIIRedactor) -> None:
        """Test email redaction."""
        text = "Email: john.doe@example.com"
        result = redactor.redact_string(text)

        assert "john.doe@example.com" not in result
        assert "[REDACTED]" in result

    def test_redact_dict(self, redactor: PIIRedactor) -> None:
        """Test dictionary redaction."""
        data = {
            "name": "John Smith",
            "phone": "555-123-4567",
            "notes": "Clean water damage",
        }

        result = redactor.redact_dict(data)

        # Known PII fields should be redacted
        assert result["phone"] == "[REDACTED]"
        # Non-PII should be preserved
        assert result["notes"] == "Clean water damage"

    def test_redact_nested_dict(self, redactor: PIIRedactor) -> None:
        """Test nested dictionary redaction."""
        data = {
            "customer": {
                "email": "test@example.com",
                "address": "123 Main St",
            },
            "claim_type": "water",
        }

        result = redactor.redact_dict(data)

        # Nested PII fields should be redacted
        assert "[REDACTED]" in result["customer"]["email"]
        # Non-PII preserved
        assert result["claim_type"] == "water"

    def test_redaction_log(self, redactor: PIIRedactor) -> None:
        """Test that redaction log is maintained."""
        text = "Call 555-123-4567 or email test@example.com"
        redactor.redact_string(text)

        log = redactor.get_redaction_log()
        assert len(log) >= 2

    def test_redaction_summary(self, redactor: PIIRedactor) -> None:
        """Test redaction summary."""
        text = "SSN: 123-45-6789, Phone: 555-123-4567"
        redactor.redact_string(text)

        summary = redactor.get_redaction_summary()
        assert "ssn" in summary or "phone" in summary

    def test_clear_log(self, redactor: PIIRedactor) -> None:
        """Test clearing redaction log."""
        text = "Phone: 555-123-4567"
        redactor.redact_string(text)

        assert len(redactor.get_redaction_log()) > 0

        redactor.clear_redaction_log()
        assert len(redactor.get_redaction_log()) == 0


class TestRedactPiiFunction:
    """Tests for the redact_pii convenience function."""

    def test_redact_dict(self) -> None:
        """Test redacting a dictionary."""
        data = {"phone": "555-123-4567", "status": "active"}
        result = redact_pii(data)

        assert result["phone"] == "[REDACTED]"
        assert result["status"] == "active"

    def test_unsupported_type(self) -> None:
        """Test that unsupported types raise error."""
        with pytest.raises(TypeError):
            redact_pii("just a string")  # type: ignore

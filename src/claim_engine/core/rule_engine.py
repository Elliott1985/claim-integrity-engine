"""
Dictionary-based Rule Engine for the Claim Integrity Engine.
Allows easy addition and management of audit rules.
"""

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from .models import AuditCategory, AuditFinding, AuditSeverity, ClaimData


@dataclass
class AuditRule:
    """Definition of an audit rule."""

    rule_id: str
    name: str
    description: str
    category: AuditCategory
    severity: AuditSeverity
    code_patterns: list[str] = field(default_factory=list)
    validator: Callable[[ClaimData, dict[str, Any]], list[AuditFinding]] | None = None
    enabled: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)


class RuleEngine:
    """
    Dictionary-based rule engine for managing and executing audit rules.

    Rules are organized by category and can be easily added, removed,
    or modified at runtime.
    """

    def __init__(self) -> None:
        self._rules: dict[str, AuditRule] = {}
        self._category_index: dict[AuditCategory, list[str]] = {
            cat: [] for cat in AuditCategory
        }
        self._pattern_cache: dict[str, re.Pattern[str]] = {}
        self._finding_counter: int = 0

    def add_rule(self, rule: AuditRule) -> None:
        """Add a rule to the engine."""
        self._rules[rule.rule_id] = rule
        self._category_index[rule.category].append(rule.rule_id)

        # Pre-compile regex patterns
        for pattern in rule.code_patterns:
            if pattern not in self._pattern_cache:
                self._pattern_cache[pattern] = re.compile(pattern, re.IGNORECASE)

    def remove_rule(self, rule_id: str) -> bool:
        """Remove a rule from the engine."""
        if rule_id not in self._rules:
            return False

        rule = self._rules[rule_id]
        self._category_index[rule.category].remove(rule_id)
        del self._rules[rule_id]
        return True

    def get_rule(self, rule_id: str) -> AuditRule | None:
        """Get a specific rule by ID."""
        return self._rules.get(rule_id)

    def get_rules_by_category(self, category: AuditCategory) -> list[AuditRule]:
        """Get all rules in a specific category."""
        return [
            self._rules[rule_id]
            for rule_id in self._category_index[category]
            if self._rules[rule_id].enabled
        ]

    def enable_rule(self, rule_id: str) -> bool:
        """Enable a specific rule."""
        if rule_id in self._rules:
            self._rules[rule_id].enabled = True
            return True
        return False

    def disable_rule(self, rule_id: str) -> bool:
        """Disable a specific rule."""
        if rule_id in self._rules:
            self._rules[rule_id].enabled = False
            return True
        return False

    def match_codes(self, pattern: str, codes: list[str]) -> list[str]:
        """Find all codes matching a pattern."""
        if pattern not in self._pattern_cache:
            self._pattern_cache[pattern] = re.compile(pattern, re.IGNORECASE)

        compiled = self._pattern_cache[pattern]
        return [code for code in codes if compiled.search(code)]

    def generate_finding_id(self) -> str:
        """Generate a unique finding ID."""
        self._finding_counter += 1
        return f"FND-{self._finding_counter:06d}"

    def create_finding(
        self,
        rule: AuditRule,
        title: str,
        description: str,
        affected_items: list[str] | None = None,
        potential_impact: float | None = None,
        recommendation: str | None = None,
        evidence: dict[str, Any] | None = None,
    ) -> AuditFinding:
        """Create a standardized audit finding from a rule."""
        from decimal import Decimal

        return AuditFinding(
            finding_id=self.generate_finding_id(),
            category=rule.category,
            severity=rule.severity,
            rule_name=rule.name,
            title=title,
            description=description,
            affected_items=affected_items or [],
            potential_impact=Decimal(str(potential_impact)) if potential_impact else None,
            recommendation=recommendation,
            evidence=evidence or {},
        )

    def execute_rule(
        self, rule: AuditRule, claim: ClaimData, context: dict[str, Any] | None = None
    ) -> list[AuditFinding]:
        """Execute a single rule against a claim."""
        if not rule.enabled or rule.validator is None:
            return []

        try:
            return rule.validator(claim, context or {})
        except Exception as e:
            # Log error but don't fail the entire audit
            return [
                self.create_finding(
                    rule=rule,
                    title=f"Rule Execution Error: {rule.name}",
                    description=f"Error executing rule: {str(e)}",
                    evidence={"error": str(e), "error_type": type(e).__name__},
                )
            ]

    def execute_all(
        self, claim: ClaimData, context: dict[str, Any] | None = None
    ) -> list[AuditFinding]:
        """Execute all enabled rules against a claim."""
        findings: list[AuditFinding] = []
        ctx = context or {}

        for rule in self._rules.values():
            if rule.enabled:
                findings.extend(self.execute_rule(rule, claim, ctx))

        return findings

    def execute_category(
        self,
        category: AuditCategory,
        claim: ClaimData,
        context: dict[str, Any] | None = None,
    ) -> list[AuditFinding]:
        """Execute all rules in a specific category."""
        findings: list[AuditFinding] = []
        ctx = context or {}

        for rule in self.get_rules_by_category(category):
            findings.extend(self.execute_rule(rule, claim, ctx))

        return findings

    def list_rules(self) -> list[dict[str, Any]]:
        """List all rules with their status."""
        return [
            {
                "rule_id": rule.rule_id,
                "name": rule.name,
                "category": rule.category.value,
                "severity": rule.severity.value,
                "enabled": rule.enabled,
                "description": rule.description,
            }
            for rule in self._rules.values()
        ]


# Singleton instance for global rule registration
_default_engine: RuleEngine | None = None


def get_default_engine() -> RuleEngine:
    """Get the default rule engine instance."""
    global _default_engine
    if _default_engine is None:
        _default_engine = RuleEngine()
    return _default_engine


def register_rule(
    rule_id: str,
    name: str,
    description: str,
    category: AuditCategory,
    severity: AuditSeverity = AuditSeverity.WARNING,
    code_patterns: list[str] | None = None,
) -> Callable[
    [Callable[[ClaimData, dict[str, Any]], list[AuditFinding]]],
    Callable[[ClaimData, dict[str, Any]], list[AuditFinding]],
]:
    """Decorator for registering audit rules."""

    def decorator(
        func: Callable[[ClaimData, dict[str, Any]], list[AuditFinding]],
    ) -> Callable[[ClaimData, dict[str, Any]], list[AuditFinding]]:
        rule = AuditRule(
            rule_id=rule_id,
            name=name,
            description=description,
            category=category,
            severity=severity,
            code_patterns=code_patterns or [],
            validator=func,
        )
        get_default_engine().add_rule(rule)
        return func

    return decorator

"""Generation metrics only: no target API execution or code coverage."""

from collections import Counter
from dataclasses import dataclass, field

from .schemas import TestCase


@dataclass
class GenerationMetrics:
    operations_analyzed: int
    proposed_tests: int = 0
    structurally_valid_tests: int = 0
    semantically_accepted_tests: int = 0
    structurally_rejected_tests: int = 0
    semantically_rejected_tests: int = 0
    hypothetical_tests: int = 0
    duplicates: int = 0
    llm_attempts: int = 0
    llm_failures: int = 0
    mock_playbacks: int = 0
    generation_seconds: float = 0.0
    tests: list[TestCase] = field(default_factory=list, repr=False)

    def report(self) -> dict:
        covered = {(test.method, test.endpoint) for test in self.tests}
        def rate(numerator: int, denominator: int) -> float | None:
            return round(100 * numerator / denominator, 4) if denominator else None
        return {
            "operations_analyzed": self.operations_analyzed,
            "proposed_tests": self.proposed_tests,
            "structurally_valid_tests": self.structurally_valid_tests,
            "structurally_rejected_tests": self.structurally_rejected_tests,
            "semantically_accepted_tests_before_deduplication": self.semantically_accepted_tests,
            "semantically_rejected_tests": self.semantically_rejected_tests,
            "hypothetical_tests": self.hypothetical_tests,
            "validated_tests": len(self.tests),
            "rejected_tests": self.structurally_rejected_tests + self.semantically_rejected_tests + self.hypothetical_tests,
            "duplicates": self.duplicates,
            "structural_validity_percent": rate(self.structurally_valid_tests, self.proposed_tests),
            "semantic_acceptance_percent": rate(self.semantically_accepted_tests, self.structurally_valid_tests),
            "operations_covered": len(covered),
            "operation_generation_coverage_percent": rate(len(covered), self.operations_analyzed),
            "category_distribution": {key: Counter(test.test_type for test in self.tests)[key] for key in ("positive", "negative", "boundary")},
            "generation_seconds": round(self.generation_seconds, 6),
            "llm_attempts": self.llm_attempts,
            "llm_failures": self.llm_failures,
            "mock_playbacks": self.mock_playbacks,
            "denominators": {
                "structural_validity_percent": "all candidate items in successfully decoded v1.0 envelopes",
                "semantic_acceptance_percent": "structurally valid candidate items, before deduplication",
                "operation_generation_coverage_percent": "all parsed OpenAPI operations, including unsupported ones",
                "category_distribution": "validated unique exported tests (counts, not percentages)",
            },
            "accounting": "proposed_tests = validated_tests + rejected_tests + duplicates; failed envelopes contribute no candidate items",
            "coverage_scope": "generation coverage of declared operations; no API execution, behavior or code coverage",
        }


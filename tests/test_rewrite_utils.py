"""
Unit tests for rewrite utilities
"""
import pytest
from handlers.rewrite_utils import FindingType, FindingProcessor, extract_reasoning_findings


class TestFindingType:
    """Test suite for FindingType enum"""

    def test_finding_type_keys(self):
        """Test that all finding types have correct keys"""
        assert FindingType.VALID.key == "VALID"
        assert FindingType.INVALID.key == "INVALID"
        assert FindingType.SATISFIABLE.key == "SATISFIABLE"
        assert FindingType.NO_DATA.key == "NO_DATA"
        assert FindingType.TRANSLATION_AMBIGUOUS.key == "TRANSLATION_AMBIGUOUS"
        assert FindingType.TOO_COMPLEX.key == "TOO_COMPLEX"

    def test_finding_type_priorities(self):
        """Test that priorities are assigned correctly"""
        assert FindingType.INVALID.priority == 10  # Highest priority
        assert FindingType.VALID.priority == 0  # Lowest priority

    def test_from_string(self):
        """Test finding type creation from string"""
        ft = FindingType.from_string("INVALID")
        assert ft == FindingType.INVALID

        ft = FindingType.from_string("UNKNOWN")
        assert ft is None


class TestFindingProcessor:
    """Test suite for FindingProcessor"""

    def test_categorize_findings(self):
        """Test findings categorization"""
        processor = FindingProcessor()

        findings = [
            {"result": "INVALID", "explanation": "Violation 1"},
            {"result": "INVALID", "explanation": "Violation 2"},
            {"result": "VALID", "explanation": "Valid case"}
        ]

        categorized = processor.categorize_findings(findings)

        assert len(categorized) == 2
        assert FindingType.INVALID in categorized
        assert FindingType.VALID in categorized
        assert len(categorized[FindingType.INVALID]) == 2
        assert len(categorized[FindingType.VALID]) == 1

    def test_get_priority_types(self):
        """Test priority type ordering"""
        processor = FindingProcessor()

        findings_by_type = {
            FindingType.VALID: [{"result": "VALID"}],
            FindingType.INVALID: [{"result": "INVALID"}],
            FindingType.SATISFIABLE: [{"result": "SATISFIABLE"}]
        }

        priority_types = processor.get_priority_types(findings_by_type)

        # Should be ordered by priority (highest first)
        assert priority_types[0] == FindingType.INVALID
        assert priority_types[-1] == FindingType.VALID

    def test_process_finding_data(self):
        """Test finding data processing for templates"""
        processor = FindingProcessor()

        findings = [
            {
                "violations": ["Policy violation 1", "Policy violation 2"],
                "suggestions": ["Fix suggestion 1"],
                "appliedRules": ["Rule1", "Rule2"]
            }
        ]

        data = processor.process_finding_data(FindingType.INVALID, findings)

        assert "violations" in data
        assert "suggestions" in data
        assert "applied_rules" in data
        assert "Policy violation 1" in data["violations"]
        assert "Rule1" in data["applied_rules"]

    def test_process_finding_data_empty(self):
        """Test finding data processing with empty findings"""
        processor = FindingProcessor()

        findings = [{}]

        data = processor.process_finding_data(FindingType.INVALID, findings)

        assert "violations" in data
        assert "suggestions" in data
        assert data["violations"] == "No specific violations found"


class TestExtractReasoningFindings:
    """Test suite for extract_reasoning_findings"""

    def test_extract_findings(self):
        """Test extraction of findings from guardrail response"""
        guardrail_response = {
            "assessments": [
                {
                    "automatedReasoningPolicy": {
                        "findings": [
                            {
                                "result": "INVALID",
                                "explanation": "Test violation",
                                "variables": {"age": 15},
                                "appliedRules": ["MinAgeRule"],
                                "violations": ["Age too low"],
                                "suggestions": ["Set age to 18+"]
                            }
                        ]
                    }
                }
            ]
        }

        findings = extract_reasoning_findings(guardrail_response)

        assert len(findings) == 1
        assert findings[0]["result"] == "INVALID"
        assert findings[0]["explanation"] == "Test violation"
        assert findings[0]["variables"]["age"] == 15
        assert len(findings[0]["violations"]) == 1

    def test_extract_findings_empty(self):
        """Test extraction with no findings"""
        guardrail_response = {"assessments": []}

        findings = extract_reasoning_findings(guardrail_response)

        assert len(findings) == 0

    def test_extract_findings_no_arc(self):
        """Test extraction with no ARC assessment"""
        guardrail_response = {
            "assessments": [
                {
                    "contentPolicy": {
                        "filters": []
                    }
                }
            ]
        }

        findings = extract_reasoning_findings(guardrail_response)

        assert len(findings) == 0

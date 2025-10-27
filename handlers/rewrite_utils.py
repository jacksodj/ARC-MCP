"""
Utilities for processing ARC findings and response rewriting
"""
from enum import Enum
from typing import Dict, Any, List, Optional


class FindingType(Enum):
    """ARC Finding Types with priority ordering"""
    VALID = ("VALID", 0)
    INVALID = ("INVALID", 10)
    SATISFIABLE = ("SATISFIABLE", 8)
    NO_DATA = ("NO_DATA", 7)
    TRANSLATION_AMBIGUOUS = ("TRANSLATION_AMBIGUOUS", 6)
    TOO_COMPLEX = ("TOO_COMPLEX", 5)

    def __init__(self, key: str, priority: int):
        self.key = key
        self.priority = priority

    @classmethod
    def from_string(cls, value: str):
        """Get FindingType from string value"""
        for finding_type in cls:
            if finding_type.key == value:
                return finding_type
        return None


class FindingProcessor:
    """Processes and categorizes ARC findings"""

    def __init__(self, policy_definition: Optional[str] = None):
        self.policy_definition = policy_definition

    def categorize_findings(self, findings: List[Dict[str, Any]]) -> Dict[FindingType, List[Dict[str, Any]]]:
        """Categorize findings by type"""
        categorized = {}

        for finding in findings:
            result = finding.get('result', 'UNKNOWN')
            finding_type = FindingType.from_string(result)

            if finding_type:
                if finding_type not in categorized:
                    categorized[finding_type] = []
                categorized[finding_type].append(finding)

        return categorized

    def get_priority_types(self, findings_by_type: Dict[FindingType, List[Dict[str, Any]]]) -> List[FindingType]:
        """Get finding types sorted by priority (highest priority first)"""
        if not findings_by_type:
            return []

        # Sort by priority (higher priority value = more important)
        sorted_types = sorted(
            findings_by_type.keys(),
            key=lambda ft: ft.priority,
            reverse=True
        )

        return sorted_types

    def process_finding_data(self, finding_type: FindingType, findings: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Extract relevant data from findings for template formatting"""
        template_data = {}

        if not findings:
            return template_data

        # Aggregate all violations and suggestions
        all_violations = []
        all_suggestions = []
        all_rules = []

        for finding in findings:
            violations = finding.get('violations', [])
            suggestions = finding.get('suggestions', [])
            rules = finding.get('appliedRules', [])

            all_violations.extend(violations)
            all_suggestions.extend(suggestions)
            all_rules.extend(rules)

        # Format for template
        if all_violations:
            template_data['violations'] = '\n'.join([f"- {v}" for v in all_violations])
        else:
            template_data['violations'] = "No specific violations found"

        if all_suggestions:
            template_data['suggestions'] = '\n'.join([f"- {s}" for s in all_suggestions])
        else:
            template_data['suggestions'] = "Ensure compliance with policy requirements"

        if all_rules:
            template_data['applied_rules'] = ', '.join(all_rules)
        else:
            template_data['applied_rules'] = "Policy rules"

        # Add policy definition if available
        if self.policy_definition:
            template_data['policy'] = self.policy_definition

        return template_data


def extract_reasoning_findings(guardrail_response: Dict[str, Any], policy_definition: Optional[str] = None) -> List[Dict[str, Any]]:
    """Extract and format ARC findings from guardrail response"""
    formatted_findings = []

    if 'assessments' not in guardrail_response:
        return formatted_findings

    for assessment in guardrail_response.get('assessments', []):
        if 'automatedReasoningPolicy' not in assessment:
            continue

        arc_policy = assessment['automatedReasoningPolicy']
        findings = arc_policy.get('findings', [])

        for finding in findings:
            formatted_finding = {
                'result': finding.get('result', 'UNKNOWN'),
                'explanation': finding.get('explanation', ''),
                'variables': finding.get('variables', {}),
                'appliedRules': finding.get('appliedRules', []),
                'violations': finding.get('violations', []),
                'suggestions': finding.get('suggestions', [])
            }

            formatted_findings.append(formatted_finding)

    return formatted_findings

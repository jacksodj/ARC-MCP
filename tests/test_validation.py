"""
Unit tests for ARC validation handler
"""
import pytest
from unittest.mock import Mock
from handlers.validation import validate_content_handler, _extract_arc_assessment


class TestValidationHandler:
    """Test suite for validation handler"""

    def test_successful_validation(self):
        """Test successful validation with VALID result"""
        # Mock boto3 client response
        mock_response = {
            'action': 'NONE',
            'assessments': [{
                'automatedReasoningPolicy': {
                    'findings': [{
                        'result': 'VALID',
                        'variables': {'tenure_months': 6},
                        'appliedRules': ['MinimumTenureRule'],
                        'explanation': 'Statement verified'
                    }]
                },
                'invocationMetrics': {
                    'guardrailProcessingLatency': 0.245
                }
            }],
            'usage': {
                'automatedReasoningPolicies': 1,
                'automatedReasoningPolicyUnits': 3
            }
        }

        mock_client = Mock()
        mock_client.apply_guardrail.return_value = mock_response
        mock_logger = Mock()

        result = validate_content_handler(
            bedrock_runtime=mock_client,
            guardrail_id='test-guardrail',
            content='Test content',
            version='1',
            source='OUTPUT',
            logger=mock_logger
        )

        assert result['valid'] == True
        assert result['action'] == 'NONE'
        assert result['usage']['automatedReasoningPolicyUnits'] == 3
        assert result['usage']['processingTimeMs'] == 245

    def test_invalid_validation(self):
        """Test validation with INVALID result"""
        mock_response = {
            'action': 'GUARDRAIL_INTERVENED',
            'assessments': [{
                'automatedReasoningPolicy': {
                    'findings': [{
                        'result': 'INVALID',
                        'violations': ['Insufficient tenure'],
                        'suggestions': ['Employee needs 6 months minimum']
                    }]
                }
            }],
            'usage': {
                'automatedReasoningPolicyUnits': 2
            }
        }

        mock_client = Mock()
        mock_client.apply_guardrail.return_value = mock_response
        mock_logger = Mock()

        result = validate_content_handler(
            bedrock_runtime=mock_client,
            guardrail_id='test-guardrail',
            content='Invalid content',
            version='1',
            source='OUTPUT',
            logger=mock_logger
        )

        assert result['valid'] == False
        assert result['action'] == 'GUARDRAIL_INTERVENED'
        assert 'violations' in result['assessments']['automatedReasoningPolicy']['findings'][0]

    def test_api_error_handling(self):
        """Test handling of AWS API errors"""
        from botocore.exceptions import ClientError

        mock_client = Mock()
        mock_client.apply_guardrail.side_effect = ClientError(
            {'Error': {'Code': 'ResourceNotFoundException', 'Message': 'Guardrail not found'}},
            'ApplyGuardrail'
        )
        mock_logger = Mock()

        result = validate_content_handler(
            bedrock_runtime=mock_client,
            guardrail_id='nonexistent',
            content='Test',
            version='1',
            source='OUTPUT',
            logger=mock_logger
        )

        assert result['error'] == True
        assert result['error_type'] == 'ResourceNotFoundException'


class TestARCAssessmentExtraction:
    """Test suite for ARC assessment extraction"""

    def test_extract_valid_finding(self):
        """Test extraction of valid ARC finding"""
        assessment = {
            'automatedReasoningPolicy': {
                'findings': [{
                    'result': 'VALID',
                    'variables': {'age': 25},
                    'appliedRules': ['AgeVerificationRule'],
                    'explanation': 'Age meets requirement'
                }]
            }
        }

        result = _extract_arc_assessment(assessment)

        assert result is not None
        assert len(result['findings']) == 1
        assert result['findings'][0]['result'] == 'VALID'

    def test_extract_with_violations(self):
        """Test extraction with violations present"""
        assessment = {
            'automatedReasoningPolicy': {
                'findings': [{
                    'result': 'INVALID',
                    'violations': ['Age too low'],
                    'suggestions': ['Minimum age is 18']
                }]
            }
        }

        result = _extract_arc_assessment(assessment)

        assert 'violations' in result['findings'][0]
        assert 'suggestions' in result['findings'][0]

    def test_no_arc_policy(self):
        """Test extraction when no ARC policy present"""
        assessment = {
            'contentPolicy': {
                'filters': []
            }
        }

        result = _extract_arc_assessment(assessment)

        assert result is None

    def test_empty_findings(self):
        """Test extraction when findings list is empty"""
        assessment = {
            'automatedReasoningPolicy': {
                'findings': []
            }
        }

        result = _extract_arc_assessment(assessment)

        assert result is None

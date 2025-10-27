"""
Unit tests for guardrail discovery handler
"""
import pytest
from unittest.mock import Mock
from datetime import datetime
from handlers.discovery import list_guardrails_handler, get_guardrail_info_handler


class TestListGuardrailsHandler:
    """Test suite for list guardrails handler"""

    def test_list_guardrails_with_arc(self):
        """Test listing guardrails that have ARC policies"""
        mock_list_response = {
            'guardrails': [
                {
                    'id': 'test-guardrail-1',
                    'name': 'Test Guardrail 1',
                    'arn': 'arn:aws:bedrock:us-east-1:123456789012:guardrail/test-guardrail-1',
                    'description': 'Test guardrail with ARC',
                    'status': 'READY',
                    'version': '1',
                    'createdAt': datetime(2025, 1, 1),
                    'updatedAt': datetime(2025, 10, 27)
                }
            ]
        }

        mock_get_response = {
            'guardrailId': 'test-guardrail-1',
            'name': 'Test Guardrail 1',
            'guardrailArn': 'arn:aws:bedrock:us-east-1:123456789012:guardrail/test-guardrail-1',
            'automatedReasoningPolicyConfig': {
                'policies': ['arn:aws:bedrock:us-east-1:123456789012:policy/test-policy']
            }
        }

        mock_client = Mock()
        mock_client.list_guardrails.return_value = mock_list_response
        mock_client.get_guardrail.return_value = mock_get_response
        mock_logger = Mock()

        result = list_guardrails_handler(
            bedrock=mock_client,
            max_results=20,
            logger=mock_logger
        )

        assert result['count'] == 1
        assert len(result['guardrails']) == 1
        assert result['guardrails'][0]['id'] == 'test-guardrail-1'
        assert result['guardrails'][0]['has_arc_policies'] == True
        assert result['guardrails'][0]['arc_policy_count'] == 1

    def test_list_guardrails_filters_non_arc(self):
        """Test that guardrails without ARC policies are filtered out"""
        mock_list_response = {
            'guardrails': [
                {
                    'id': 'test-guardrail-no-arc',
                    'name': 'Test Guardrail No ARC',
                    'arn': 'arn:aws:bedrock:us-east-1:123456789012:guardrail/test-guardrail-no-arc'
                }
            ]
        }

        mock_get_response = {
            'guardrailId': 'test-guardrail-no-arc',
            'name': 'Test Guardrail No ARC',
            'guardrailArn': 'arn:aws:bedrock:us-east-1:123456789012:guardrail/test-guardrail-no-arc'
            # No automatedReasoningPolicyConfig
        }

        mock_client = Mock()
        mock_client.list_guardrails.return_value = mock_list_response
        mock_client.get_guardrail.return_value = mock_get_response
        mock_logger = Mock()

        result = list_guardrails_handler(
            bedrock=mock_client,
            max_results=20,
            logger=mock_logger
        )

        assert result['count'] == 0
        assert len(result['guardrails']) == 0

    def test_list_guardrails_api_error(self):
        """Test handling of AWS API errors"""
        from botocore.exceptions import ClientError

        mock_client = Mock()
        mock_client.list_guardrails.side_effect = ClientError(
            {'Error': {'Code': 'AccessDeniedException', 'Message': 'Access denied'}},
            'ListGuardrails'
        )
        mock_logger = Mock()

        result = list_guardrails_handler(
            bedrock=mock_client,
            max_results=20,
            logger=mock_logger
        )

        assert result['error'] == True
        assert 'guardrails' in result
        assert len(result['guardrails']) == 0


class TestGetGuardrailInfoHandler:
    """Test suite for get guardrail info handler"""

    def test_get_guardrail_with_arc(self):
        """Test getting guardrail info with ARC policies"""
        mock_response = {
            'guardrailId': 'test-guardrail',
            'name': 'Test Guardrail',
            'guardrailArn': 'arn:aws:bedrock:us-east-1:123456789012:guardrail/test-guardrail',
            'description': 'Test guardrail description',
            'status': 'READY',
            'version': '1',
            'createdAt': datetime(2025, 1, 1),
            'updatedAt': datetime(2025, 10, 27),
            'automatedReasoningPolicyConfig': {
                'policies': [
                    'arn:aws:bedrock:us-east-1:123456789012:policy/policy1',
                    'arn:aws:bedrock:us-east-1:123456789012:policy/policy2'
                ],
                'confidenceThreshold': 0.9
            }
        }

        mock_client = Mock()
        mock_client.get_guardrail.return_value = mock_response
        mock_logger = Mock()

        result = get_guardrail_info_handler(
            bedrock=mock_client,
            guardrail_id='test-guardrail',
            version='1',
            logger=mock_logger
        )

        assert result['id'] == 'test-guardrail'
        assert result['name'] == 'Test Guardrail'
        assert result['arc_policies'] is not None
        assert result['arc_policies']['count'] == 2
        assert result['arc_policies']['confidence_threshold'] == 0.9

    def test_get_guardrail_without_arc(self):
        """Test getting guardrail info without ARC policies"""
        mock_response = {
            'guardrailId': 'test-guardrail-no-arc',
            'name': 'Test Guardrail No ARC',
            'guardrailArn': 'arn:aws:bedrock:us-east-1:123456789012:guardrail/test-guardrail-no-arc',
            'description': 'Guardrail without ARC',
            'status': 'READY',
            'version': '1',
            'createdAt': datetime(2025, 1, 1),
            'updatedAt': datetime(2025, 10, 27)
            # No automatedReasoningPolicyConfig
        }

        mock_client = Mock()
        mock_client.get_guardrail.return_value = mock_response
        mock_logger = Mock()

        result = get_guardrail_info_handler(
            bedrock=mock_client,
            guardrail_id='test-guardrail-no-arc',
            version='1',
            logger=mock_logger
        )

        assert result['id'] == 'test-guardrail-no-arc'
        assert result['arc_policies'] is None

    def test_get_guardrail_not_found(self):
        """Test handling of guardrail not found error"""
        from botocore.exceptions import ClientError

        mock_client = Mock()
        mock_client.get_guardrail.side_effect = ClientError(
            {'Error': {'Code': 'ResourceNotFoundException', 'Message': 'Guardrail not found'}},
            'GetGuardrail'
        )
        mock_logger = Mock()

        result = get_guardrail_info_handler(
            bedrock=mock_client,
            guardrail_id='nonexistent',
            version='1',
            logger=mock_logger
        )

        assert result['error'] == True
        assert result['guardrail_id'] == 'nonexistent'

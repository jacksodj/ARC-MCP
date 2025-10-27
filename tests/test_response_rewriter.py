"""
Unit tests for ResponseRewriter
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from handlers.response_rewriter import ResponseRewriter
from handlers.rewrite_utils import FindingType


class TestResponseRewriter:
    """Test suite for ResponseRewriter"""

    @pytest.fixture
    def rewriter(self):
        """Create a ResponseRewriter instance for testing"""
        with patch('handlers.response_rewriter.TemplateManager'):
            return ResponseRewriter(domain="Test")

    def test_initialization(self, rewriter):
        """Test ResponseRewriter initialization"""
        assert rewriter.domain == "Test"
        assert rewriter.template_manager is not None
        assert rewriter.finding_processor is not None

    def test_prepare_rewrite_prompt_no_template(self, rewriter):
        """Test prompt preparation when template is not available"""
        rewriter.template_manager.get_template = Mock(return_value=None)

        result = rewriter.prepare_rewrite_prompt(
            "Question?",
            "Answer",
            FindingType.VALID,
            []
        )

        assert result is None

    def test_prepare_rewrite_prompt_with_template(self, rewriter):
        """Test prompt preparation with valid template"""
        template = "Domain: {domain}\nQuestion: {question}\nAnswer: {original_answer}\n{violations}"
        rewriter.template_manager.get_template = Mock(return_value=template)
        rewriter.template_manager.format_template = Mock(side_effect=lambda t, **kw: t.format(**kw))
        rewriter.finding_processor.process_finding_data = Mock(return_value={"violations": "Test violation"})

        result = rewriter.prepare_rewrite_prompt(
            "Test question?",
            "Test answer",
            FindingType.INVALID,
            [{"result": "INVALID"}]
        )

        assert result is not None
        assert "Test" in result  # domain
        assert "Test question" in result
        assert "Test answer" in result

    def test_rewrite_response_no_findings(self, rewriter):
        """Test rewrite when there are no findings"""
        result = rewriter.rewrite_response(
            "Question?",
            "Answer",
            {},  # Empty findings
            "model-id",
            Mock()
        )

        assert result["rewritten"] is False
        assert result["rewritten_response"] is None
        assert "message" in result

    def test_rewrite_response_valid_only(self, rewriter):
        """Test rewrite when only VALID findings (no rewrite needed)"""
        ar_findings = {
            "findings": [
                {"result": "VALID", "explanation": "All good"}
            ]
        }

        result = rewriter.rewrite_response(
            "Question?",
            "Answer",
            ar_findings,
            "model-id",
            Mock()
        )

        assert result["rewritten"] is False
        assert result["finding_types"] == ["VALID"]
        assert "No rewrite needed" in result["message"]

    def test_rewrite_response_too_complex_only(self, rewriter):
        """Test rewrite when only TOO_COMPLEX finding"""
        ar_findings = {
            "findings": [
                {"result": "TOO_COMPLEX", "explanation": "Too complex"}
            ]
        }

        result = rewriter.rewrite_response(
            "Question?",
            "Answer",
            ar_findings,
            "model-id",
            Mock()
        )

        assert result["rewritten"] is True
        assert result["finding_types"] == ["TOO_COMPLEX"]
        assert "too much information" in result["rewritten_response"].lower()

    def test_rewrite_response_invalid(self, rewriter):
        """Test rewrite with INVALID finding"""
        ar_findings = {
            "findings": [
                {
                    "result": "INVALID",
                    "explanation": "Policy violation",
                    "violations": ["Violation 1"],
                    "suggestions": ["Fix suggestion"]
                }
            ]
        }

        # Mock the template manager
        template = "Fix: {violations}"
        rewriter.template_manager.get_template = Mock(return_value=template)
        rewriter.template_manager.format_template = Mock(side_effect=lambda t, **kw: t.format(**kw))
        rewriter.finding_processor.process_finding_data = Mock(
            return_value={"violations": "Violation 1"}
        )

        # Mock bedrock runtime client
        mock_client = Mock()
        mock_client.converse.return_value = {
            "output": {
                "message": {
                    "content": [{"text": "Rewritten response text"}]
                }
            }
        }

        result = rewriter.rewrite_response(
            "Question?",
            "Answer",
            ar_findings,
            "model-id",
            mock_client
        )

        assert result["rewritten"] is True
        assert result["rewritten_response"] == "Rewritten response text"
        assert "INVALID" in result["finding_types"]

    def test_combine_rewrites(self, rewriter):
        """Test combining multiple rewrites"""
        rewrites = [
            {"finding_type": "INVALID", "rewritten_text": "Fixed text 1"},
            {"finding_type": "NO_DATA", "rewritten_text": "Fixed text 2"}
        ]

        mock_client = Mock()
        mock_client.converse.return_value = {
            "output": {
                "message": {
                    "content": [{"text": "Combined response"}]
                }
            }
        }

        result = rewriter._combine_rewrites(
            "Question?",
            "Original",
            rewrites,
            mock_client,
            "model-id"
        )

        assert result == "Combined response"
        mock_client.converse.assert_called_once()

    def test_combine_rewrites_error(self, rewriter):
        """Test combining rewrites with error"""
        rewrites = [
            {"finding_type": "INVALID", "rewritten_text": "Text"}
        ]

        mock_client = Mock()
        mock_client.converse.side_effect = Exception("API Error")

        result = rewriter._combine_rewrites(
            "Question?",
            "Original",
            rewrites,
            mock_client,
            "model-id"
        )

        assert result is None

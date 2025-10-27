"""
Response Rewriting Handler
Validates content and rewrites based on ARC findings
"""
from typing import Dict, Any, Optional
import logging
from handlers.response_rewriter import ResponseRewriter
from handlers.rewrite_utils import extract_reasoning_findings


def summarize_results(
    user_query: str,
    llm_response: str,
    guardrail_id: str,
    guardrail_version: str,
    bedrock_runtime_client,
    model_id: str = "anthropic.claude-3-5-sonnet-20241022-v2:0",
    domain: Optional[str] = None,
    policy_definition: Optional[str] = None,
    logger: Optional[logging.Logger] = None
) -> Dict[str, Any]:
    """
    Validate content and rewrite response based on ARC findings.

    Args:
        user_query: The original user question
        llm_response: The LLM's response to validate and potentially rewrite
        guardrail_id: Guardrail identifier
        guardrail_version: Guardrail version
        bedrock_runtime_client: Boto3 bedrock-runtime client
        model_id: Model ID for rewriting (default: Claude 3.5 Sonnet)
        domain: Domain context (e.g., "Healthcare", "Finance")
        policy_definition: Optional policy text for context
        logger: Optional logger instance

    Returns:
        Dict containing query, responses, findings, and metadata
    """
    if logger is None:
        logger = logging.getLogger(__name__)

    if domain is None:
        domain = "General"

    try:
        logger.info(f"Validating and rewriting response for guardrail {guardrail_id}")

        # Prepare content for validation
        # Include both query and response for comprehensive validation
        content_to_validate = [
            {"text": {"text": user_query, "qualifiers": ["query"]}},
            {"text": {"text": llm_response, "qualifiers": ["guard_content"]}}
        ]

        # Apply guardrail
        apply_guardrail_response = bedrock_runtime_client.apply_guardrail(
            guardrailIdentifier=guardrail_id,
            guardrailVersion=guardrail_version,
            source="OUTPUT",
            content=content_to_validate
        )

        # Extract ARC findings
        ar_findings = None
        if 'assessments' in apply_guardrail_response and apply_guardrail_response['assessments']:
            for assessment in apply_guardrail_response['assessments']:
                if 'automatedReasoningPolicy' in assessment:
                    ar_findings = assessment['automatedReasoningPolicy']
                    break

        # Format findings for readability
        formatted_findings = extract_reasoning_findings(
            apply_guardrail_response,
            policy_definition
        )

        # Initialize rewriter
        rewriter = ResponseRewriter(
            policy_definition=policy_definition,
            domain=domain
        )

        # Rewrite response based on findings
        rewrite_result = rewriter.rewrite_response(
            user_query=user_query,
            llm_response=llm_response,
            ar_findings=ar_findings,
            model_id=model_id,
            bedrock_runtime_client=bedrock_runtime_client
        )

        # Build comprehensive result
        result = {
            "query": user_query,
            "original_response": llm_response,
            "rewritten_response": rewrite_result.get("rewritten_response"),
            "rewritten": rewrite_result.get("rewritten", False),
            "findings": formatted_findings,
            "finding_types": rewrite_result.get("finding_types", []),
            "findings_count": rewrite_result.get("findings_count", 0),
            "domain": domain,
            "message": rewrite_result.get("message"),
            "guardrail_id": guardrail_id,
            "guardrail_version": guardrail_version
        }

        # Add usage metrics if available
        if 'usage' in apply_guardrail_response:
            result['usage'] = {
                'automatedReasoningPolicies': apply_guardrail_response['usage'].get('automatedReasoningPolicies', 0),
                'automatedReasoningPolicyUnits': apply_guardrail_response['usage'].get('automatedReasoningPolicyUnits', 0)
            }

        logger.info(
            f"Rewrite complete: rewritten={result['rewritten']}, "
            f"finding_types={result['finding_types']}, "
            f"findings_count={result['findings_count']}"
        )

        return result

    except Exception as e:
        logger.error(f"Error in summarize_results: {e}")
        return {
            "error": True,
            "error_type": type(e).__name__,
            "error_message": str(e),
            "query": user_query,
            "original_response": llm_response,
            "guardrail_id": guardrail_id
        }

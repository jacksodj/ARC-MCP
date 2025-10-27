"""
ARC Validation Handler
Implements content validation against Bedrock ARC policies
"""
from typing import Dict, Any
import logging
from botocore.exceptions import ClientError


def validate_content_handler(
    bedrock_runtime,
    guardrail_id: str,
    content: str,
    version: str,
    source: str,
    logger: logging.Logger
) -> Dict[str, Any]:
    """
    Validate content using ApplyGuardrail API.

    Calls AWS Bedrock Runtime ApplyGuardrail with ARC-configured guardrail
    and returns structured validation results.
    """
    try:
        logger.info(f"Validating content against guardrail {guardrail_id} v{version}")

        # Call ApplyGuardrail API
        response = bedrock_runtime.apply_guardrail(
            guardrailIdentifier=guardrail_id,
            guardrailVersion=version,
            source=source.upper(),
            content=[
                {
                    'text': {
                        'text': content
                    }
                }
            ]
        )

        # Extract action and assessments
        action = response.get('action', 'NONE')
        assessments = response.get('assessments', [])
        usage = response.get('usage', {})

        # Format result
        result = {
            'action': action,
            'valid': action == 'NONE',
            'guardrail_id': guardrail_id,
            'guardrail_version': version,
            'content_length': len(content)
        }

        # Extract ARC findings if present
        if assessments:
            arc_assessment = _extract_arc_assessment(assessments[0])
            if arc_assessment:
                result['assessments'] = {
                    'automatedReasoningPolicy': arc_assessment
                }

        # Add usage metrics
        result['usage'] = {
            'automatedReasoningPolicies': usage.get('automatedReasoningPolicies', 0),
            'automatedReasoningPolicyUnits': usage.get('automatedReasoningPolicyUnits', 0)
        }

        # Add processing latency if available
        if assessments and 'invocationMetrics' in assessments[0]:
            latency = assessments[0]['invocationMetrics'].get('guardrailProcessingLatency', 0)
            result['usage']['processingTimeMs'] = int(latency * 1000)

        logger.info(f"Validation complete: action={action}, units={result['usage']['automatedReasoningPolicyUnits']}")
        return result

    except ClientError as e:
        error_code = e.response['Error']['Code']
        error_message = e.response['Error']['Message']
        logger.error(f"AWS API error: {error_code} - {error_message}")

        return {
            'error': True,
            'error_type': error_code,
            'error_message': error_message,
            'guardrail_id': guardrail_id
        }

    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return {
            'error': True,
            'error_type': 'UnexpectedError',
            'error_message': str(e),
            'guardrail_id': guardrail_id
        }


def _extract_arc_assessment(assessment: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract and format ARC-specific assessment data.

    The ApplyGuardrail response includes automatedReasoningPolicy within
    assessments. This extracts and structures those findings.
    """
    arc_policy = assessment.get('automatedReasoningPolicy')
    if not arc_policy:
        return None

    findings = arc_policy.get('findings', [])
    if not findings:
        return None

    # Format findings with clear structure
    formatted_findings = []
    for finding in findings:
        formatted_finding = {
            'result': finding.get('result', 'UNKNOWN'),
            'variables': finding.get('variables', {}),
            'appliedRules': finding.get('appliedRules', []),
            'explanation': finding.get('explanation', '')
        }

        # Add violation details if present
        if finding.get('violations'):
            formatted_finding['violations'] = finding['violations']

        # Add suggestions if present
        if finding.get('suggestions'):
            formatted_finding['suggestions'] = finding['suggestions']

        formatted_findings.append(formatted_finding)

    return {
        'findings': formatted_findings
    }

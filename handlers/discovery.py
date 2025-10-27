"""
Guardrail Discovery Handler
Lists and retrieves guardrail information
"""
from typing import Dict, Any
import logging
from botocore.exceptions import ClientError


def list_guardrails_handler(
    bedrock,
    max_results: int,
    logger: logging.Logger
) -> Dict[str, Any]:
    """
    List guardrails with ARC policies.

    Calls ListGuardrails API and filters for those with ARC configurations.
    """
    try:
        logger.info(f"Listing guardrails (max: {max_results})")

        response = bedrock.list_guardrails(
            maxResults=min(max_results, 100)
        )

        guardrails = []
        for item in response.get('guardrails', []):
            # Get full details to check for ARC policies
            try:
                detail = bedrock.get_guardrail(
                    guardrailIdentifier=item['id'],
                    guardrailVersion='DRAFT'
                )

                # Check if has ARC policies
                arc_config = detail.get('automatedReasoningPolicyConfig')
                has_arc = bool(arc_config and arc_config.get('policies'))

                if has_arc:  # Only include guardrails with ARC
                    guardrails.append({
                        'id': item['id'],
                        'name': item.get('name', ''),
                        'arn': item.get('arn', ''),
                        'description': item.get('description', ''),
                        'status': item.get('status', ''),
                        'has_arc_policies': True,
                        'arc_policy_count': len(arc_config.get('policies', [])),
                        'latest_version': item.get('version', 'DRAFT'),
                        'created_at': item.get('createdAt', '').isoformat() if item.get('createdAt') else None,
                        'updated_at': item.get('updatedAt', '').isoformat() if item.get('updatedAt') else None
                    })
            except ClientError as e:
                # Skip guardrails we can't access
                logger.warning(f"Could not retrieve details for guardrail {item['id']}: {e}")
                continue

        logger.info(f"Found {len(guardrails)} guardrails with ARC policies")
        return {
            'guardrails': guardrails,
            'count': len(guardrails)
        }

    except ClientError as e:
        logger.error(f"AWS API error: {e}")
        return {
            'error': True,
            'error_message': str(e),
            'guardrails': []
        }


def get_guardrail_info_handler(
    bedrock,
    guardrail_id: str,
    version: str,
    logger: logging.Logger
) -> Dict[str, Any]:
    """
    Get detailed guardrail information.

    Retrieves guardrail configuration including ARC policy details.
    """
    try:
        logger.info(f"Fetching guardrail info: {guardrail_id} v{version}")

        response = bedrock.get_guardrail(
            guardrailIdentifier=guardrail_id,
            guardrailVersion=version
        )

        # Extract relevant fields
        result = {
            'id': response['guardrailId'],
            'name': response['name'],
            'arn': response['guardrailArn'],
            'description': response.get('description', ''),
            'status': response.get('status', ''),
            'version': response['version'],
            'created_at': response['createdAt'].isoformat(),
            'updated_at': response['updatedAt'].isoformat()
        }

        # Extract ARC policy configuration
        arc_config = response.get('automatedReasoningPolicyConfig')
        if arc_config:
            policies = arc_config.get('policies', [])
            result['arc_policies'] = {
                'count': len(policies),
                'policy_arns': policies,
                'confidence_threshold': arc_config.get('confidenceThreshold', 0.8)
            }
        else:
            result['arc_policies'] = None

        logger.info(f"Retrieved guardrail info: {result['name']}")
        return result

    except ClientError as e:
        logger.error(f"AWS API error: {e}")
        return {
            'error': True,
            'error_message': str(e),
            'guardrail_id': guardrail_id
        }

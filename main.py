"""
AWS Bedrock ARC MCP Server
Provides validation tools for Automated Reasoning Checks via MCP protocol
"""
from fastmcp import FastMCP
import boto3
import os
import logging
from typing import Dict, Any

# Initialize FastMCP server
mcp = FastMCP("bedrock-arc-validator")

# Initialize AWS clients
bedrock_runtime = boto3.client(
    'bedrock-runtime',
    region_name=os.environ.get('AWS_REGION', 'us-east-1')
)
bedrock = boto3.client(
    'bedrock',
    region_name=os.environ.get('AWS_REGION', 'us-east-1')
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import handlers
from handlers.validation import validate_content_handler
from handlers.discovery import list_guardrails_handler, get_guardrail_info_handler
from handlers.rewrite_handler import summarize_results


@mcp.tool()
def validate_content(
    guardrail_id: str,
    content: str,
    guardrail_version: str = "DRAFT",
    source: str = "OUTPUT"
) -> Dict[str, Any]:
    """
    Validate text content against an AWS Bedrock ARC policy.

    Args:
        guardrail_id: Guardrail identifier (ID or ARN)
        content: Text content to validate
        guardrail_version: Version number or 'DRAFT' (default: DRAFT)
        source: Whether content is INPUT or OUTPUT (default: OUTPUT)

    Returns:
        Validation result with findings and usage metrics
    """
    return validate_content_handler(
        bedrock_runtime=bedrock_runtime,
        guardrail_id=guardrail_id,
        content=content,
        version=guardrail_version,
        source=source,
        logger=logger
    )


@mcp.tool()
def list_guardrails(max_results: int = 20) -> Dict[str, Any]:
    """
    List available AWS Bedrock Guardrails with ARC policies.

    Args:
        max_results: Maximum number of guardrails to return (default: 20)

    Returns:
        List of guardrails with metadata
    """
    return list_guardrails_handler(
        bedrock=bedrock,
        max_results=max_results,
        logger=logger
    )


@mcp.tool()
def get_guardrail_info(
    guardrail_id: str,
    version: str = "DRAFT"
) -> Dict[str, Any]:
    """
    Get detailed information about a specific guardrail.

    Args:
        guardrail_id: Guardrail identifier
        version: Specific version or 'DRAFT' (default: DRAFT)

    Returns:
        Detailed guardrail configuration
    """
    return get_guardrail_info_handler(
        bedrock=bedrock,
        guardrail_id=guardrail_id,
        version=version,
        logger=logger
    )


@mcp.tool()
def rewrite_response(
    user_query: str,
    llm_response: str,
    guardrail_id: str,
    guardrail_version: str = "DRAFT",
    model_id: str = "anthropic.claude-3-5-sonnet-20241022-v2:0",
    domain: str = "General",
    policy_definition: str = None
) -> Dict[str, Any]:
    """
    Validate LLM response and rewrite based on ARC findings.

    This tool validates a response against an ARC policy and automatically
    rewrites it to fix any policy violations or issues detected.

    Args:
        user_query: The original user question/prompt
        llm_response: The LLM's response to validate and potentially rewrite
        guardrail_id: Guardrail identifier (ID or ARN)
        guardrail_version: Version number or 'DRAFT' (default: DRAFT)
        model_id: Model ID for rewriting (default: Claude 3.5 Sonnet)
        domain: Domain context like 'Healthcare', 'Finance' (default: General)
        policy_definition: Optional policy text for additional context

    Returns:
        Dict containing original response, rewritten response (if needed),
        findings, finding types, and rewrite metadata
    """
    return summarize_results(
        user_query=user_query,
        llm_response=llm_response,
        guardrail_id=guardrail_id,
        guardrail_version=guardrail_version,
        bedrock_runtime_client=bedrock_runtime,
        model_id=model_id,
        domain=domain,
        policy_definition=policy_definition,
        logger=logger
    )


# Run server (AgentCore expects stateless HTTP MCP protocol)
if __name__ == "__main__":
    mcp.run(transport="http", stateless_http=True, host="0.0.0.0")

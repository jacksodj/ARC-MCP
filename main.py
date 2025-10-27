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


# Run server (AgentCore expects server at 0.0.0.0:8000/mcp)
if __name__ == "__main__":
    mcp.run(transport="streamable-http")

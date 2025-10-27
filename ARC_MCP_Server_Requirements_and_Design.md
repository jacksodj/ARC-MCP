# AWS Bedrock ARC MCP Server: Requirements and Design Document

**Version:** 1.0  
**Date:** October 27, 2025  
**Document Type:** Requirements & Design Specification  
**Target Platform:** Amazon Bedrock AgentCore Runtime  
**Implementation Language:** Python  

---

## Executive Summary

This document specifies the requirements and design for a Model Context Protocol (MCP) server that provides standardized access to AWS Bedrock Automated Reasoning Checks (ARC). The server enables AI agents and applications to validate content against formal logic policies with mathematical precision, achieving up to 99% verification accuracy.

**Key Features:**
- MCP-compliant server exposing ARC validation as Tools
- Simple Python implementation using FastMCP framework
- Deployable on Amazon Bedrock AgentCore Runtime
- Serverless, scalable, and secure
- Supports multiple guardrails and policies
- Returns structured validation results with explanations

**Primary Use Cases:**
- LLM output validation against business rules
- Content verification in regulated industries
- Multi-step reasoning validation
- Policy compliance checking
- Hallucination detection with mathematical proof

---

## 1. Project Overview

### 1.1 Problem Statement

AI agents and LLM applications need to validate outputs against complex business rules, but:

1. **No Standard Interface**: Each validation system requires custom integration
2. **Fragmented Tools**: Different validation approaches lack interoperability
3. **Limited Reusability**: Hard to share validation capabilities across agents
4. **Manual Integration**: Connecting ARC to agents requires custom code

### 1.2 Solution

An MCP server that:
- Exposes ARC validation as standardized MCP Tools
- Provides simple, reusable interface for any MCP-compatible agent
- Deploys on AgentCore Runtime for enterprise-grade scalability
- Abstracts AWS API complexity behind clean Tool interfaces

### 1.3 Scope

**In Scope:**
- MCP server implementation with FastMCP
- ARC validation via `ApplyGuardrail` API
- Guardrail discovery and listing
- Policy information retrieval
- Structured validation result formatting
- AgentCore Runtime deployment configuration
- OAuth 2.0 authentication support
- Basic error handling and logging

**Out of Scope:**
- Guardrail/policy creation or modification (use AWS Console or SDK directly)
- Policy testing workflows (separate tooling)
- Streaming validation support (ARC limitation)
- Integration with other guardrail types beyond ARC
- Advanced observability dashboards (use AgentCore Observability)

---

## 2. System Requirements

### 2.1 Functional Requirements

#### FR-1: Validate Content Against ARC Policies
**Priority:** CRITICAL  
**Description:** Server MUST validate text content against specified ARC guardrails and return structured results.

**Acceptance Criteria:**
- Accepts guardrail identifier, version, and content as inputs
- Calls AWS Bedrock Runtime `ApplyGuardrail` API
- Returns validation result (VALID/INVALID) with findings
- Provides detailed violation explanations when applicable
- Includes usage metrics and processing time

**MCP Tool Specification:**
```json
{
  "name": "validate_content",
  "description": "Validate text content against an AWS Bedrock Automated Reasoning Check policy",
  "inputSchema": {
    "type": "object",
    "properties": {
      "guardrail_id": {
        "type": "string",
        "description": "Guardrail identifier (ID or ARN)"
      },
      "guardrail_version": {
        "type": "string",
        "description": "Guardrail version (number or 'DRAFT')",
        "default": "DRAFT"
      },
      "content": {
        "type": "string",
        "description": "Text content to validate"
      },
      "source": {
        "type": "string",
        "enum": ["INPUT", "OUTPUT"],
        "description": "Whether content is user input or model output",
        "default": "OUTPUT"
      }
    },
    "required": ["guardrail_id", "content"]
  }
}
```

**Example Usage:**
```python
# AI agent using the MCP tool
result = await mcp_client.call_tool(
    "validate_content",
    {
        "guardrail_id": "abc123xyz",
        "guardrail_version": "1",
        "content": "Employee with 6 months tenure is eligible for benefits",
        "source": "OUTPUT"
    }
)
```

**Expected Response:**
```json
{
  "action": "NONE",
  "valid": true,
  "assessments": {
    "automatedReasoningPolicy": {
      "findings": [
        {
          "result": "VALID",
          "variables": {
            "tenure_months": 6,
            "is_eligible": true
          },
          "appliedRules": ["MinimumTenureRule"],
          "explanation": "Statement verified: Employee tenure of 6 months meets minimum requirement of 6 months for benefits eligibility"
        }
      ]
    }
  },
  "usage": {
    "automatedReasoningPolicyUnits": 3,
    "processingTimeMs": 245
  }
}
```

#### FR-2: List Available Guardrails
**Priority:** HIGH  
**Description:** Server SHOULD provide discovery of available ARC guardrails.

**MCP Tool Specification:**
```json
{
  "name": "list_guardrails",
  "description": "List available AWS Bedrock Guardrails with ARC policies in the account",
  "inputSchema": {
    "type": "object",
    "properties": {
      "max_results": {
        "type": "integer",
        "description": "Maximum number of guardrails to return",
        "default": 20,
        "minimum": 1,
        "maximum": 100
      }
    }
  }
}
```

**Expected Response:**
```json
{
  "guardrails": [
    {
      "id": "abc123xyz",
      "name": "HR-Benefits-Policy",
      "arn": "arn:aws:bedrock:us-east-1:123456789012:guardrail/abc123xyz",
      "description": "Validates HR benefits eligibility rules",
      "status": "READY",
      "has_arc_policies": true,
      "arc_policy_count": 1,
      "latest_version": "3",
      "created_at": "2025-09-15T10:30:00Z",
      "updated_at": "2025-10-20T14:22:00Z"
    }
  ]
}
```

#### FR-3: Get Guardrail Details
**Priority:** MEDIUM  
**Description:** Server SHOULD retrieve detailed information about a specific guardrail.

**MCP Tool Specification:**
```json
{
  "name": "get_guardrail_info",
  "description": "Get detailed information about a specific guardrail including its ARC policies",
  "inputSchema": {
    "type": "object",
    "properties": {
      "guardrail_id": {
        "type": "string",
        "description": "Guardrail identifier"
      },
      "version": {
        "type": "string",
        "description": "Specific version or 'DRAFT'",
        "default": "DRAFT"
      }
    },
    "required": ["guardrail_id"]
  }
}
```

#### FR-4: Batch Validation (Optional)
**Priority:** LOW  
**Description:** Server MAY support validating multiple content items in a single request.

**MCP Tool Specification:**
```json
{
  "name": "batch_validate",
  "description": "Validate multiple content items against the same guardrail",
  "inputSchema": {
    "type": "object",
    "properties": {
      "guardrail_id": {"type": "string"},
      "guardrail_version": {"type": "string", "default": "DRAFT"},
      "content_items": {
        "type": "array",
        "items": {
          "type": "object",
          "properties": {
            "id": {"type": "string"},
            "content": {"type": "string"},
            "source": {"type": "string", "enum": ["INPUT", "OUTPUT"]}
          }
        }
      }
    },
    "required": ["guardrail_id", "content_items"]
  }
}
```

### 2.2 Non-Functional Requirements

#### NFR-1: Performance
- **Latency**: Tool invocations MUST complete within 30 seconds (accounting for ARC processing ~200-800ms + network overhead)
- **Throughput**: Support up to 50 concurrent validation requests (AgentCore default TPS limit)
- **Caching**: MAY implement response caching for identical validation requests

#### NFR-2: Reliability
- **Availability**: Target 99.9% uptime (inherited from AgentCore Runtime SLA)
- **Error Handling**: MUST gracefully handle AWS API errors and return meaningful error messages
- **Retry Logic**: SHOULD implement exponential backoff for transient failures

#### NFR-3: Security
- **Authentication**: MUST support OAuth 2.0 via Amazon Cognito
- **Authorization**: MUST use AWS IAM for Bedrock API access
- **Credentials**: MUST NOT log or expose AWS credentials
- **Least Privilege**: Execution role MUST only have necessary ARC permissions

#### NFR-4: Observability
- **Logging**: MUST log all validation requests with guardrail ID, result, and latency
- **Metrics**: SHOULD emit CloudWatch metrics for validation counts and error rates
- **Tracing**: SHOULD support OpenTelemetry distributed tracing (via AgentCore)

#### NFR-5: Maintainability
- **Code Quality**: Python code MUST follow PEP 8 style guidelines
- **Documentation**: All functions MUST have docstrings
- **Testing**: Unit tests MUST cover >80% of code paths
- **Dependencies**: Minimize external dependencies, prefer boto3 and FastMCP

---

## 3. Architecture Design

### 3.1 High-Level Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                      MCP Client Layer                                │
│  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐          │
│  │ Claude Desktop│  │ Cursor IDE    │  │ Custom Agent  │          │
│  │ (via MCP)     │  │ (via MCP)     │  │ (via MCP)     │          │
│  └───────┬───────┘  └───────┬───────┘  └───────┬───────┘          │
└──────────┼──────────────────┼──────────────────┼───────────────────┘
           │                  │                  │
           │ HTTP/SSE         │ HTTP/SSE         │ HTTP/SSE
           │ (OAuth Bearer)   │ (OAuth Bearer)   │ (OAuth Bearer)
           └──────────────────┴──────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│           Amazon Bedrock AgentCore Runtime                          │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  ARC MCP Server (Python + FastMCP)                           │  │
│  │  ┌─────────────────────────────────────────────────────────┐ │  │
│  │  │  MCP Protocol Handler (FastMCP)                         │ │  │
│  │  │  - Tool registration                                    │ │  │
│  │  │  - Request parsing                                      │ │  │
│  │  │  - Response formatting                                  │ │  │
│  │  └─────────────────┬───────────────────────────────────────┘ │  │
│  │                    │                                           │  │
│  │  ┌─────────────────▼───────────────────────────────────────┐ │  │
│  │  │  ARC Service Layer                                      │ │  │
│  │  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │ │  │
│  │  │  │ Validation   │  │ Guardrail    │  │ Result       │ │ │  │
│  │  │  │ Handler      │  │ Discovery    │  │ Formatter    │ │ │  │
│  │  │  └──────────────┘  └──────────────┘  └──────────────┘ │ │  │
│  │  └─────────────────┬───────────────────────────────────────┘ │  │
│  │                    │                                           │  │
│  │  ┌─────────────────▼───────────────────────────────────────┐ │  │
│  │  │  AWS SDK Layer (boto3)                                  │ │  │
│  │  │  - bedrock-runtime client                               │ │  │
│  │  │  - bedrock client                                       │ │  │
│  │  └──────────────────────────────────────────────────────────┘ │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  AgentCore Services                                          │  │
│  │  - OAuth 2.0 Authentication (Cognito)                       │  │
│  │  - IAM Execution Role Management                            │  │
│  │  - CloudWatch Logging & Metrics                             │  │
│  │  - Session Isolation (microVM per session)                  │  │
│  └──────────────────────────────────────────────────────────────┘  │
└─────────────────────────┬───────────────────────────────────────────┘
                          │ AWS IAM (SigV4)
                          ▼
┌─────────────────────────────────────────────────────────────────────┐
│              AWS Bedrock Service                                    │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  Bedrock Runtime API                                         │  │
│  │  - ApplyGuardrail                                            │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  Bedrock Guardrails + ARC Engine                             │  │
│  │  - Policy storage                                            │  │
│  │  - SMT-LIB formal verification                               │  │
│  │  - Variable extraction & translation                         │  │
│  │  - Mathematical proof generation                             │  │
│  └──────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

### 3.2 Component Design

#### 3.2.1 MCP Server Entry Point

**File:** `main.py`

```python
"""
AWS Bedrock ARC MCP Server
Provides validation tools for Automated Reasoning Checks via MCP protocol
"""
from fastmcp import FastMCP
import boto3
import os
import logging
from typing import Dict, Any, List

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

# Register MCP tools
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
```

#### 3.2.2 Validation Handler

**File:** `handlers/validation.py`

```python
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
        if 'invocationMetrics' in assessments[0]:
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
```

#### 3.2.3 Discovery Handler

**File:** `handlers/discovery.py`

```python
"""
Guardrail Discovery Handler
Lists and retrieves guardrail information
"""
from typing import Dict, Any, List
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
```

### 3.3 Project Structure

```
bedrock-arc-mcp-server/
├── main.py                    # MCP server entry point
├── handlers/
│   ├── __init__.py
│   ├── validation.py          # ARC validation logic
│   └── discovery.py           # Guardrail discovery
├── requirements.txt           # Python dependencies
├── tests/
│   ├── __init__.py
│   ├── test_validation.py
│   └── test_discovery.py
├── .agentcore/
│   └── config.json           # AgentCore deployment config
├── README.md
└── LICENSE
```

---

## 4. Deployment Configuration

### 4.1 Dependencies

**File:** `requirements.txt`

```
fastmcp>=1.0.0
boto3>=1.35.0
botocore>=1.35.0
```

### 4.2 IAM Execution Role

**Required Permissions:**

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "BedrockARCAccess",
      "Effect": "Allow",
      "Action": [
        "bedrock:ApplyGuardrail",
        "bedrock:GetGuardrail",
        "bedrock:ListGuardrails"
      ],
      "Resource": [
        "arn:aws:bedrock:*:*:guardrail/*"
      ]
    },
    {
      "Sid": "InvokeAutomatedReasoningPolicy",
      "Effect": "Allow",
      "Action": [
        "bedrock:InvokeAutomatedReasoningPolicy"
      ],
      "Resource": [
        "arn:aws:bedrock:*:*:automated-reasoning-policy/*"
      ]
    },
    {
      "Sid": "CloudWatchLogs",
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "arn:aws:logs:*:*:log-group:/aws/bedrock-agentcore/*"
    },
    {
      "Sid": "XRayTracing",
      "Effect": "Allow",
      "Action": [
        "xray:PutTraceSegments",
        "xray:PutTelemetryRecords"
      ],
      "Resource": "*"
    }
  ]
}
```

### 4.3 AgentCore Deployment Steps

**Prerequisites:**
1. AWS CLI configured with appropriate credentials
2. `bedrock-agentcore-starter-toolkit` installed (`uv add --dev bedrock-agentcore-starter-toolkit`)
3. Amazon Cognito User Pool created for OAuth authentication
4. IAM Execution Role created with permissions above

**Deployment Commands:**

```bash
# 1. Set environment variables
export EXECUTION_ROLE_ARN="arn:aws:iam::123456789012:role/ArcMcpServerRole"
export COGNITO_USER_POOL_ID="us-east-1_XXXXXXXXX"
export COGNITO_CLIENT_ID="xxxxxxxxxxxxxxxxxxxxxxxxxx"
export AWS_REGION="us-east-1"

# 2. Configure deployment
agentcore configure \
  --name arc-mcp-server \
  --entrypoint main.py \
  --execution-role $EXECUTION_ROLE_ARN \
  --authorizer-config "{
    \"customJWTAuthorizer\": {
      \"discoveryUrl\": \"https://cognito-idp.${AWS_REGION}.amazonaws.com/${COGNITO_USER_POOL_ID}/.well-known/openid-configuration\",
      \"allowedClients\": [\"${COGNITO_CLIENT_ID}\"]
    }
  }" \
  --protocol MCP

# 3. Deploy to AgentCore Runtime
agentcore launch

# 4. Get deployment details
agentcore status --agent arc-mcp-server

# 5. Test locally first (optional)
agentcore launch --local
```

**Configuration File Generated:**

**File:** `.agentcore/config.json`

```json
{
  "name": "arc-mcp-server",
  "entrypoint": "main.py",
  "protocol": "MCP",
  "runtime": {
    "python_version": "3.11"
  },
  "execution_role": "arn:aws:iam::123456789012:role/ArcMcpServerRole",
  "authorizer": {
    "type": "customJWTAuthorizer",
    "discoveryUrl": "https://cognito-idp.us-east-1.amazonaws.com/us-east-1_XXXXXXXXX/.well-known/openid-configuration",
    "allowedClients": ["xxxxxxxxxxxxxxxxxxxxxxxxxx"]
  },
  "environment": {
    "AWS_REGION": "us-east-1"
  }
}
```

### 4.4 Cognito Setup Script

**File:** `scripts/setup_cognito.sh`

```bash
#!/bin/bash
# Setup Amazon Cognito for OAuth authentication

REGION="${AWS_REGION:-us-east-1}"
POOL_NAME="arc-mcp-server-users"
CLIENT_NAME="arc-mcp-client"
USER_NAME="testuser"
PASSWORD="TempPassword123!"

echo "Creating Cognito User Pool..."
POOL_ID=$(aws cognito-idp create-user-pool \
  --pool-name "$POOL_NAME" \
  --region "$REGION" \
  --query 'UserPool.Id' \
  --output text)

echo "User Pool ID: $POOL_ID"

echo "Creating App Client..."
CLIENT_ID=$(aws cognito-idp create-user-pool-client \
  --user-pool-id "$POOL_ID" \
  --client-name "$CLIENT_NAME" \
  --explicit-auth-flows ALLOW_USER_PASSWORD_AUTH ALLOW_REFRESH_TOKEN_AUTH \
  --region "$REGION" \
  --query 'UserPoolClient.ClientId' \
  --output text)

echo "Client ID: $CLIENT_ID"

echo "Creating test user..."
aws cognito-idp admin-create-user \
  --user-pool-id "$POOL_ID" \
  --username "$USER_NAME" \
  --temporary-password "$PASSWORD" \
  --region "$REGION"

echo "Setting permanent password..."
aws cognito-idp admin-set-user-password \
  --user-pool-id "$POOL_ID" \
  --username "$USER_NAME" \
  --password "$PASSWORD" \
  --permanent \
  --region "$REGION"

echo ""
echo "===== Setup Complete ====="
echo "User Pool ID: $POOL_ID"
echo "Client ID: $CLIENT_ID"
echo "Test Username: $USER_NAME"
echo "Test Password: $PASSWORD"
echo ""
echo "To get Bearer token:"
echo "aws cognito-idp initiate-auth \\"
echo "  --auth-flow USER_PASSWORD_AUTH \\"
echo "  --client-id $CLIENT_ID \\"
echo "  --auth-parameters USERNAME=$USER_NAME,PASSWORD=$PASSWORD \\"
echo "  --region $REGION \\"
echo "  --query 'AuthenticationResult.IdToken' \\"
echo "  --output text"
```

---

## 5. Usage Examples

### 5.1 MCP Client Integration (Python)

```python
"""
Example: Using ARC MCP Server from a Python MCP client
"""
import asyncio
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
import os

async def validate_with_arc():
    """
    Example of validating content using the ARC MCP server.
    """
    # Get configuration from environment
    agent_arn = os.getenv('AGENT_ARN')  # From agentcore status output
    bearer_token = os.getenv('BEARER_TOKEN')  # From Cognito auth
    region = os.getenv('AWS_REGION', 'us-east-1')
    
    # Construct endpoint URL (URL-encode the ARN)
    encoded_arn = agent_arn.replace(':', '%3A').replace('/', '%2F')
    mcp_url = f"https://bedrock-agentcore.{region}.amazonaws.com/runtimes/{encoded_arn}/invocations?qualifier=DEFAULT"
    
    # Setup headers
    headers = {
        "authorization": f"Bearer {bearer_token}",
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream"
    }
    
    # Connect to MCP server
    async with streamablehttp_client(mcp_url, headers, timeout=120) as (read_stream, write_stream, _):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            
            # List available tools
            tools = await session.list_tools()
            print(f"Available tools: {[t.name for t in tools]}")
            
            # Call validate_content tool
            result = await session.call_tool(
                "validate_content",
                {
                    "guardrail_id": "abc123xyz",
                    "guardrail_version": "1",
                    "content": "Employee with 8 months tenure is eligible for parental leave",
                    "source": "OUTPUT"
                }
            )
            
            print(f"Validation result: {result}")
            
            # Check if valid
            if result['valid']:
                print("✓ Content validated successfully")
                print(f"Applied rules: {result['assessments']['automatedReasoningPolicy']['findings'][0]['appliedRules']}")
            else:
                print("✗ Content validation failed")
                print(f"Violations: {result['assessments']['automatedReasoningPolicy']['findings'][0]['violations']}")

if __name__ == "__main__":
    asyncio.run(validate_with_arc())
```

### 5.2 Claude Desktop Integration

**File:** `claude_desktop_config.json`

```json
{
  "mcpServers": {
    "bedrock-arc-validator": {
      "disabled": false,
      "timeout": 60,
      "type": "streamable-http",
      "url": "https://bedrock-agentcore.us-east-1.amazonaws.com/runtimes/arn%3Aaws%3Abedrock-agentcore%3Aus-east-1%3A123456789012%3Aruntime%2Farc-mcp-server/invocations?qualifier=DEFAULT",
      "headers": {
        "authorization": "Bearer YOUR_BEARER_TOKEN",
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream"
      },
      "autoApprove": []
    }
  }
}
```

**Usage in Claude Desktop:**

```
User: Please validate this statement against our HR policy guardrail:
"Employee with 3 months tenure can take unpaid leave"

Claude: I'll validate that against the HR policy using the ARC validator.

[Claude calls validate_content tool]

The statement has been validated. According to the HR benefits policy 
(guardrail abc123xyz v1), this statement is VALID. 

The automated reasoning system verified that:
- Employee tenure of 3 months meets the minimum requirement
- Unpaid leave eligibility is confirmed for employees with 3+ months tenure
- The applied rule was: MinimumTenureForUnpaidLeave

The validation used 3 automated reasoning units and completed in 287ms.
```

### 5.3 Cursor IDE Integration

**File:** `.cursor/config.json` (or equivalent)

```json
{
  "mcpServers": {
    "bedrock-arc-validator": {
      "command": "python",
      "args": ["-m", "mcp_client", "connect"],
      "env": {
        "AGENT_ARN": "arn:aws:bedrock-agentcore:us-east-1:123456789012:runtime/arc-mcp-server",
        "BEARER_TOKEN": "YOUR_BEARER_TOKEN",
        "AWS_REGION": "us-east-1"
      }
    }
  }
}
```

---

## 6. Testing Strategy

### 6.1 Unit Tests

**File:** `tests/test_validation.py`

```python
"""
Unit tests for ARC validation handler
"""
import pytest
from unittest.mock import Mock, patch
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
```

### 6.2 Integration Tests

**File:** `tests/test_integration.py`

```python
"""
Integration tests against actual AWS Bedrock service
Requires: AWS credentials configured, test guardrail deployed
"""
import pytest
import boto3
import os
from handlers.validation import validate_content_handler
import logging

# Skip if no AWS credentials or test guardrail
pytestmark = pytest.mark.skipif(
    not os.getenv('TEST_GUARDRAIL_ID'),
    reason="TEST_GUARDRAIL_ID not set"
)

class TestBedrockIntegration:
    """Integration tests against real AWS Bedrock"""
    
    @pytest.fixture
    def bedrock_client(self):
        """Create real bedrock-runtime client"""
        return boto3.client('bedrock-runtime', region_name='us-east-1')
    
    @pytest.fixture
    def test_guardrail_id(self):
        """Get test guardrail ID from environment"""
        return os.getenv('TEST_GUARDRAIL_ID')
    
    def test_real_validation(self, bedrock_client, test_guardrail_id):
        """Test validation against real guardrail"""
        logger = logging.getLogger(__name__)
        
        result = validate_content_handler(
            bedrock_runtime=bedrock_client,
            guardrail_id=test_guardrail_id,
            content="Test content for validation",
            version='DRAFT',
            source='OUTPUT',
            logger=logger
        )
        
        # Basic assertions
        assert 'error' not in result or result['error'] == False
        assert 'action' in result
        assert 'valid' in result
        assert 'usage' in result
        
        # Log result for inspection
        print(f"Validation result: {result}")
```

### 6.3 End-to-End Tests

```python
"""
End-to-end test via deployed MCP server
Requires: Server deployed to AgentCore, bearer token available
"""
import asyncio
import pytest
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
import os

pytestmark = pytest.mark.skipif(
    not os.getenv('AGENT_ARN'),
    reason="AGENT_ARN not set - server not deployed"
)

async def test_mcp_server_tools():
    """Test MCP server tools end-to-end"""
    agent_arn = os.getenv('AGENT_ARN')
    bearer_token = os.getenv('BEARER_TOKEN')
    region = os.getenv('AWS_REGION', 'us-east-1')
    
    encoded_arn = agent_arn.replace(':', '%3A').replace('/', '%2F')
    mcp_url = f"https://bedrock-agentcore.{region}.amazonaws.com/runtimes/{encoded_arn}/invocations?qualifier=DEFAULT"
    
    headers = {
        "authorization": f"Bearer {bearer_token}",
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream"
    }
    
    async with streamablehttp_client(mcp_url, headers) as (read_stream, write_stream, _):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            
            # Test: List tools
            tools = await session.list_tools()
            tool_names = [t.name for t in tools]
            
            assert 'validate_content' in tool_names
            assert 'list_guardrails' in tool_names
            assert 'get_guardrail_info' in tool_names
            
            # Test: List guardrails
            result = await session.call_tool('list_guardrails', {'max_results': 5})
            assert 'guardrails' in result
            assert isinstance(result['guardrails'], list)
            
            print(f"✓ End-to-end test passed - {len(tools)} tools available")

if __name__ == "__main__":
    asyncio.run(test_mcp_server_tools())
```

---

## 7. Monitoring and Operations

### 7.1 CloudWatch Metrics

The server automatically emits metrics to CloudWatch via AgentCore:

**Standard Metrics:**
- `InvocationCount` - Total MCP tool invocations
- `InvocationErrors` - Failed tool invocations
- `InvocationDuration` - Tool execution time (ms)

**Custom Application Metrics:**
```python
import boto3

cloudwatch = boto3.client('cloudwatch')

# Emit custom metric
cloudwatch.put_metric_data(
    Namespace='BedrockARCMCP',
    MetricData=[
        {
            'MetricName': 'ValidationCount',
            'Value': 1,
            'Unit': 'Count',
            'Dimensions': [
                {'Name': 'GuardrailId', 'Value': guardrail_id},
                {'Name': 'ValidationResult', 'Value': 'VALID'}
            ]
        },
        {
            'MetricName': 'ARCUnitsConsumed',
            'Value': units_consumed,
            'Unit': 'Count'
        }
    ]
)
```

### 7.2 Logging Best Practices

**Structured Logging:**

```python
import logging
import json

logger = logging.getLogger(__name__)

# Log validation request
logger.info(json.dumps({
    'event': 'validation_request',
    'guardrail_id': guardrail_id,
    'content_length': len(content),
    'source': source,
    'timestamp': datetime.utcnow().isoformat()
}))

# Log validation result
logger.info(json.dumps({
    'event': 'validation_complete',
    'guardrail_id': guardrail_id,
    'result': 'VALID',
    'units_consumed': units,
    'latency_ms': latency,
    'timestamp': datetime.utcnow().isoformat()
}))
```

### 7.3 Cost Tracking

**ARC Pricing:** $0.17 per 1,000 text units (1 text unit = up to 1,000 characters)

**Example Cost Calculation:**
```python
def calculate_arc_cost(content_length: int, policy_count: int = 1) -> float:
    """
    Calculate estimated ARC validation cost.
    
    Args:
        content_length: Number of characters in content
        policy_count: Number of ARC policies in guardrail (max 2)
    
    Returns:
        Cost in USD
    """
    # Round up to nearest text unit
    text_units = (content_length + 999) // 1000
    
    # Cost per policy
    cost_per_thousand = 0.17
    cost = (text_units / 1000) * cost_per_thousand * policy_count
    
    return cost

# Example: 5000 character validation with 1 policy
cost = calculate_arc_cost(5000, 1)
print(f"Estimated cost: ${cost:.6f}")  # ~$0.00085
```

**Monitoring Costs:**

```python
# Query CloudWatch metrics for total units consumed
cloudwatch = boto3.client('cloudwatch')

response = cloudwatch.get_metric_statistics(
    Namespace='BedrockARCMCP',
    MetricName='ARCUnitsConsumed',
    StartTime=datetime.utcnow() - timedelta(days=1),
    EndTime=datetime.utcnow(),
    Period=3600,  # 1 hour
    Statistics=['Sum']
)

total_units = sum(d['Sum'] for d in response['Datapoints'])
estimated_cost = (total_units / 1000) * 0.17

print(f"Total units (24h): {total_units}")
print(f"Estimated cost (24h): ${estimated_cost:.2f}")
```

---

## 8. Security Considerations

### 8.1 Authentication Flow

```
1. Client authenticates with Cognito
   ↓
2. Cognito returns JWT token (IdToken)
   ↓
3. Client includes token in Authorization header
   ↓
4. AgentCore validates JWT against Cognito
   ↓
5. If valid, request proceeds to MCP server
   ↓
6. Server uses IAM execution role for AWS API calls
```

### 8.2 Secrets Management

**Never hardcode:**
- AWS credentials (use IAM execution role)
- Bearer tokens (obtain dynamically)
- Guardrail IDs (pass as parameters)

**Best Practices:**
```python
# ✓ GOOD: Use IAM execution role
bedrock_runtime = boto3.client('bedrock-runtime')  # Auto-uses execution role

# ✗ BAD: Hardcode credentials
bedrock_runtime = boto3.client(
    'bedrock-runtime',
    aws_access_key_id='AKIA...',  # Never do this!
    aws_secret_access_key='...'
)
```

### 8.3 Input Validation

```python
def validate_inputs(guardrail_id: str, content: str, version: str) -> None:
    """
    Validate user inputs before processing.
    """
    # Guardrail ID format check
    if not (guardrail_id.isalnum() or guardrail_id.startswith('arn:aws:bedrock')):
        raise ValueError(f"Invalid guardrail_id format: {guardrail_id}")
    
    # Content length check
    if len(content) > 100000:  # 100KB limit
        raise ValueError(f"Content too large: {len(content)} chars (max 100000)")
    
    # Version format check
    if version != 'DRAFT' and not version.isdigit():
        raise ValueError(f"Invalid version format: {version}")
```

### 8.4 Rate Limiting

**AgentCore Built-in Limits:**
- 50 TPS per runtime by default
- Configurable via service quotas

**Application-Level Rate Limiting:**

```python
from functools import wraps
from time import time
from threading import Lock

class RateLimiter:
    """Simple token bucket rate limiter"""
    
    def __init__(self, rate: int = 50, per: int = 1):
        self.rate = rate  # requests
        self.per = per    # seconds
        self.allowance = rate
        self.last_check = time()
        self.lock = Lock()
    
    def allow(self) -> bool:
        with self.lock:
            current = time()
            time_passed = current - self.last_check
            self.last_check = current
            self.allowance += time_passed * (self.rate / self.per)
            
            if self.allowance > self.rate:
                self.allowance = self.rate
            
            if self.allowance < 1:
                return False
            
            self.allowance -= 1
            return True

limiter = RateLimiter(rate=50, per=1)

@mcp.tool()
def validate_content(guardrail_id: str, content: str, **kwargs):
    if not limiter.allow():
        return {
            'error': True,
            'error_type': 'RateLimitExceeded',
            'error_message': 'Too many requests. Please try again later.'
        }
    
    return validate_content_handler(...)
```

---

## 9. Troubleshooting Guide

### 9.1 Common Issues

#### Issue: "ResourceNotFoundException: Guardrail not found"

**Cause:** Guardrail ID incorrect or not accessible

**Resolution:**
```bash
# List available guardrails
aws bedrock list-guardrails --region us-east-1

# Verify guardrail has ARC policies
aws bedrock get-guardrail \
  --guardrail-identifier YOUR_GUARDRAIL_ID \
  --guardrail-version DRAFT \
  --region us-east-1 \
  --query 'automatedReasoningPolicyConfig'
```

#### Issue: "AccessDeniedException"

**Cause:** IAM execution role lacks permissions

**Resolution:**
```bash
# Check execution role permissions
aws iam get-role-policy \
  --role-name ArcMcpServerRole \
  --policy-name BedrockARCAccess

# Verify role has required actions
# Should include: bedrock:ApplyGuardrail, bedrock:InvokeAutomatedReasoningPolicy
```

#### Issue: "ValidationException: Invalid content"

**Cause:** Content format or length issues

**Resolution:**
```python
# Ensure content is plain text
content = str(content_obj)

# Check length
if len(content) > 100000:
    content = content[:100000]  # Truncate

# Validate no special characters causing issues
content = content.encode('utf-8').decode('utf-8')
```

#### Issue: "ThrottlingException"

**Cause:** Exceeded API rate limits

**Resolution:**
```python
# Implement exponential backoff
import time
from botocore.exceptions import ClientError

def call_with_retry(func, max_retries=3):
    for attempt in range(max_retries):
        try:
            return func()
        except ClientError as e:
            if e.response['Error']['Code'] == 'ThrottlingException':
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    time.sleep(wait_time)
                else:
                    raise
            else:
                raise
```

### 9.2 Debugging Tools

**Enable Debug Logging:**

```python
import logging

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Set boto3 debug logging
boto3.set_stream_logger('', logging.DEBUG)
```

**Test MCP Connection:**

```bash
# Test MCP server connectivity
curl -X POST \
  "https://bedrock-agentcore.us-east-1.amazonaws.com/runtimes/${ENCODED_ARN}/invocations?qualifier=DEFAULT" \
  -H "Authorization: Bearer ${BEARER_TOKEN}" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{
    "method": "tools/list",
    "params": {}
  }'
```

**Validate JWT Token:**

```bash
# Decode JWT token (without signature verification)
echo $BEARER_TOKEN | cut -d'.' -f2 | base64 -d | jq .

# Check token expiration
# exp claim should be in the future (Unix timestamp)
```

---

## 10. Future Enhancements

### 10.1 Planned Features (Phase 2)

1. **Response Caching**
   - Cache validation results for identical content
   - Configurable TTL
   - Reduce API calls and costs

2. **Batch Validation Support**
   - Validate multiple items in single request
   - Parallel processing
   - Aggregate results

3. **Policy Testing Tools**
   - MCP tool to test policy against sample content
   - Dry-run mode
   - Test case management

4. **Enhanced Observability**
   - Detailed metrics dashboard
   - Performance analytics
   - Cost attribution by guardrail

5. **Multi-Region Support**
   - Automatic region failover
   - Latency-based routing
   - Cross-region policy replication

### 10.2 Potential Integrations

1. **Other MCP Servers**
   - Chain with document retrieval servers
   - Combine with data transformation servers
   - Integrate with notification systems

2. **CI/CD Pipelines**
   - Validate policy changes
   - Automated testing
   - Deployment guards

3. **Monitoring Platforms**
   - Datadog integration
   - Splunk forwarding
   - Custom dashboards

---

## 11. Appendix

### 11.1 API Reference

#### validate_content

**Parameters:**
- `guardrail_id` (string, required): Guardrail identifier
- `content` (string, required): Text content to validate
- `guardrail_version` (string, optional): Version number or 'DRAFT' (default: 'DRAFT')
- `source` (string, optional): 'INPUT' or 'OUTPUT' (default: 'OUTPUT')

**Returns:**
```typescript
{
  action: 'NONE' | 'GUARDRAIL_INTERVENED',
  valid: boolean,
  guardrail_id: string,
  guardrail_version: string,
  content_length: number,
  assessments?: {
    automatedReasoningPolicy: {
      findings: Array<{
        result: 'VALID' | 'INVALID' | 'SATISFIABLE' | 'NO_DATA' | 'TRANSLATION_AMBIGUOUS' | 'TOO_COMPLEX',
        variables: Record<string, any>,
        appliedRules: string[],
        explanation: string,
        violations?: string[],
        suggestions?: string[]
      }>
    }
  },
  usage: {
    automatedReasoningPolicies: number,
    automatedReasoningPolicyUnits: number,
    processingTimeMs?: number
  },
  error?: boolean,
  error_type?: string,
  error_message?: string
}
```

#### list_guardrails

**Parameters:**
- `max_results` (integer, optional): Maximum results to return (default: 20, max: 100)

**Returns:**
```typescript
{
  guardrails: Array<{
    id: string,
    name: string,
    arn: string,
    description: string,
    status: string,
    has_arc_policies: boolean,
    arc_policy_count: number,
    latest_version: string,
    created_at: string,
    updated_at: string
  }>,
  count: number
}
```

#### get_guardrail_info

**Parameters:**
- `guardrail_id` (string, required): Guardrail identifier
- `version` (string, optional): Version number or 'DRAFT' (default: 'DRAFT')

**Returns:**
```typescript
{
  id: string,
  name: string,
  arn: string,
  description: string,
  status: string,
  version: string,
  created_at: string,
  updated_at: string,
  arc_policies: {
    count: number,
    policy_arns: string[],
    confidence_threshold: number
  } | null
}
```

### 11.2 Glossary

- **ARC (Automated Reasoning Checks)**: Formal verification system using SMT solvers to mathematically validate LLM outputs
- **MCP (Model Context Protocol)**: Open standard for connecting AI systems to external tools and data
- **AgentCore**: AWS Bedrock service for deploying and scaling AI agents
- **Guardrail**: AWS Bedrock policy container for content moderation and validation
- **SMT-LIB**: Satisfiability Modulo Theories Library - formal logic language
- **FastMCP**: Python framework for building MCP servers
- **OAuth 2.0**: Industry-standard protocol for authorization
- **IAM**: AWS Identity and Access Management
- **SigV4**: AWS Signature Version 4 authentication

### 11.3 References

- [AWS Bedrock ARC Documentation](https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails-automated-reasoning-checks.html)
- [Model Context Protocol Specification](https://spec.modelcontextprotocol.io/)
- [Amazon Bedrock AgentCore Documentation](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/)
- [FastMCP Framework](https://github.com/modelcontextprotocol/python-sdk)
- [Boto3 Documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/index.html)

---

## Document Control

**Version History:**

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2025-10-27 | System Architect | Initial requirements and design |

**Review Status:** Draft - Pending Stakeholder Review

**Approval:** _Pending_

---

**END OF DOCUMENT**

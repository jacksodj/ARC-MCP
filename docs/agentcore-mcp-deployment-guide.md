# AgentCore MCP Server Deployment Guide

## Lessons Learned from Building and Deploying MCP Servers on AWS Bedrock AgentCore

This document captures practical knowledge gained from deploying an MCP (Model Context Protocol) server to AWS Bedrock AgentCore, including infrastructure setup, common pitfalls, and solutions.

---

## 🔥 CRITICAL: Essential Requirements (Read This First!)

### The Three Non-Negotiables

If you only remember three things about deploying MCP servers to AgentCore, remember these:

#### 1. Transport Configuration (MANDATORY)
**Your MCP server MUST use stateless streamable-http transport:**
```python
# main.py - CORRECT configuration
if __name__ == "__main__":
    mcp.run(transport="streamable-http", stateless_http=True, host="0.0.0.0")
```

❌ **Wrong**: `transport="http"` → Results in 406 errors
❌ **Wrong**: `transport="streamable-http"` without `stateless_http=True` → Session management issues
❌ **Wrong**: `host="127.0.0.1"` → Won't work in Docker containers

**AWS Documentation Quote**: "Stateless streamable-http only for compatibility with AWS session management"

#### 2. Invocation Method (CRITICAL)
**You CANNOT invoke MCP servers using raw boto3 API calls:**

❌ **Wrong**:
```python
# This will NEVER work for MCP protocol
client = boto3.client('bedrock-agentcore')
response = client.invoke_agent_runtime(
    agentRuntimeArn=arn,
    payload=json.dumps({"jsonrpc": "2.0", "method": "tools/list"})
)
```

✅ **Correct**: Use the MCP Python client library:
```python
# This is the ONLY supported method
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

async with streamablehttp_client(mcp_url, headers, timeout=120) as (read, write, _):
    async with ClientSession(read, write) as session:
        await session.initialize()  # Required MCP handshake
        tools = await session.list_tools()
```

**Why**: AgentCore's MCP proxy expects the full MCP protocol handshake, not raw JSON-RPC

#### 3. Authentication (REQUIRED)
**MCP servers require authentication - no exceptions:**

Without authentication → `403 Forbidden`

**OAuth + Cognito** (Recommended):
```python
headers = {
    "authorization": f"Bearer {cognito_bearer_token}",
    "Content-Type": "application/json"
}
```

**Critical Cognito Issue**: Standard Cognito JWTs use `aud` claim for client ID, but AgentCore expects `client_id` claim.

**Solution**: Pre-Token Generation Lambda (see [Authentication Configuration](#authentication-configuration))

---

## Table of Contents

1. [Critical Requirements](#critical-essential-requirements-read-this-first)
2. [Infrastructure Setup](#infrastructure-setup)
3. [MCP Server Configuration](#mcp-server-configuration)
4. [AgentCore Deployment](#agentcore-deployment)
5. [Authentication Configuration](#authentication-configuration)
6. [Invocation Examples](#invocation-examples)
7. [Testing and Debugging](#testing-and-debugging)
8. [Common Issues and Solutions](#common-issues-and-solutions)
9. [Key Takeaways](#key-takeaways)

---

## Infrastructure Setup

### CloudFormation Template Design

#### Critical Components

1. **IAM Execution Role**
   - Must include permissions for:
     - Bedrock Guardrails (`bedrock:ApplyGuardrail`, `bedrock:GetGuardrail`)
     - CloudWatch Logs (`logs:CreateLogGroup`, `logs:CreateLogStream`, `logs:PutLogEvents`)
     - X-Ray tracing (`xray:PutTraceSegments`, `xray:PutTelemetryRecords`)
     - **ECR Access** (often forgotten!):
       ```yaml
       - Sid: ECRAccess
         Effect: Allow
         Action:
           - 'ecr:GetAuthorizationToken'
           - 'ecr:BatchGetImage'
           - 'ecr:GetDownloadUrlForLayer'
           - 'ecr:BatchCheckLayerAvailability'
         Resource: '*'
       ```

2. **Cognito User Pool**
   - Can be created new or reuse existing
   - Must support OAuth 2.0 / JWT tokens
   - Configure with email as username for easier management

#### AWS::Cognito::UserPoolUser Resource Issue

**IMPORTANT**: The `AWS::Cognito::UserPoolUser` CloudFormation resource type is problematic and may fail with `InvalidRequest` errors in certain regions or configurations.

**Solution**: Do NOT create users via CloudFormation. Instead:
- Make test user creation optional via CloudFormation parameters
- Create users manually using AWS CLI after stack deployment:
  ```bash
  aws cognito-idp admin-create-user \
    --user-pool-id <pool-id> \
    --username user@example.com \
    --user-attributes Name=email,Value=user@example.com Name=email_verified,Value=true \
    --message-action SUPPRESS \
    --region us-east-1

  aws cognito-idp admin-set-user-password \
    --user-pool-id <pool-id> \
    --username user@example.com \
    --password <password> \
    --permanent \
    --region us-east-1
  ```

#### Flexible Resource Configuration

Implement parameters to allow reusing existing AWS resources:

```yaml
Parameters:
  UseExistingUserPool:
    Type: String
    Default: 'false'
    AllowedValues: ['true', 'false']
    Description: 'Set to true to use an existing Cognito User Pool'

  ExistingUserPoolId:
    Type: String
    Default: ''
    Description: 'ID of existing Cognito User Pool'

  CreateTestUser:
    Type: String
    Default: 'false'
    AllowedValues: ['true', 'false']
    Description: 'Set to true to create a test user'

Conditions:
  CreateNewUserPool: !Equals [!Ref UseExistingUserPool, 'false']
  ShouldCreateTestUser: !Equals [!Ref CreateTestUser, 'true']

Resources:
  ArcMcpUserPool:
    Type: AWS::Cognito::UserPool
    Condition: CreateNewUserPool
    Properties:
      # ... properties ...
```

---

## MCP Server Configuration

### FastMCP Transport Configuration

**Critical Discovery**: AgentCore requires **stateless HTTP** transport, NOT the default streamable-http.

#### Wrong Configuration ❌
```python
# This does NOT work with AgentCore
if __name__ == "__main__":
    mcp.run(transport="streamable-http")
```

#### Correct Configuration ✅
```python
# AgentCore expects stateless HTTP MCP protocol
if __name__ == "__main__":
    mcp.run(transport="http", stateless_http=True)
```

### Why Stateless HTTP?

- **streamable-http**: Designed for clients that support Server-Sent Events (SSE) with session management (e.g., Claude Desktop)
- **stateless HTTP**: Required for stateless request/response patterns used by AgentCore
- Both use the same underlying HTTP app but with different session handling

### Server Endpoint Configuration

AgentCore expects the MCP server to:
- Listen on port 8000 (default)
- Serve at path `/mcp` (FastMCP default)
- Accept standard JSON-RPC 2.0 MCP protocol messages

---

## AgentCore Deployment

### Configuration Steps

1. **Install AgentCore CLI**
   ```bash
   pip install bedrock-agentcore-starter-toolkit
   ```

2. **Configure Agent** (Non-Interactive)
   ```bash
   agentcore configure \
     --entrypoint main.py \
     --name arc_mcp_server \
     --execution-role arn:aws:iam::ACCOUNT:role/execution-role \
     --protocol MCP \
     --authorizer-config '{"customJWTAuthorizer":{"discoveryUrl":"https://cognito-idp.REGION.amazonaws.com/POOL_ID/.well-known/openid-configuration","allowedClients":["CLIENT_ID"]}}' \
     --region us-east-1 \
     --non-interactive
   ```

   **Important**:
   - Agent name must be alphanumeric with underscores only (no hyphens!)
   - Use `customJWTAuthorizer` as the key (not `type` + `discoveryUrl` separately)

3. **Fix Authorizer Configuration Format**

   The CLI may generate incorrect format. Edit `.bedrock_agentcore.yaml`:

   **Wrong Format ❌**
   ```yaml
   authorizer_configuration:
     type: customJWTAuthorizer
     discoveryUrl: https://...
     allowedClients:
       - client-id
   ```

   **Correct Format ✅**
   ```yaml
   authorizer_configuration:
     customJWTAuthorizer:
       discoveryUrl: https://...
       allowedClients:
         - client-id
   ```

4. **Deploy**
   ```bash
   agentcore launch
   ```

   This will:
   - Create memory resource (STM-only by default, ~3 minutes)
   - Build ARM64 container via CodeBuild (~30 seconds)
   - Push to ECR
   - Deploy to AgentCore runtime
   - Configure observability (CloudWatch Logs, X-Ray)

### Deployment Artifacts

- **ECR Repository**: `bedrock-agentcore-AGENT_NAME`
- **CodeBuild Project**: `bedrock-agentcore-AGENT_NAME-builder`
- **S3 Bucket**: `bedrock-agentcore-codebuild-sources-ACCOUNT-REGION`
- **Memory Resource**: `AGENT_NAME_mem-RANDOM_ID`
- **Agent Runtime ARN**: `arn:aws:bedrock-agentcore:REGION:ACCOUNT:runtime/AGENT_NAME-RANDOM_ID`

---

## Authentication Configuration

### Cognito JWT Token Structure

Cognito ID tokens include:
```json
{
  "sub": "user-id",
  "email_verified": true,
  "iss": "https://cognito-idp.us-east-1.amazonaws.com/POOL_ID",
  "cognito:username": "user-id",
  "aud": "CLIENT_ID",  ← Client ID is in 'aud' claim
  "token_use": "id",
  "auth_time": 1234567890,
  "exp": 1234571490,
  "iat": 1234567890,
  "email": "user@example.com"
}
```

### Known Issue: JWT Claim Mismatch → ✅ SOLUTION

**Problem**: AgentCore's JWT authorizer expects client ID in a `client_id` claim, but Cognito puts it in the `aud` (audience) claim.

**Error Seen**:
```
OAuth authorization failed: Claim 'client_id' value mismatch with configuration
```

**✅ Solution: Pre-Token Generation Lambda**

Add a Cognito Lambda trigger to inject the `client_id` claim into JWTs:

```yaml
# CloudFormation template
PreTokenGenerationLambda:
  Type: AWS::Lambda::Function
  Properties:
    FunctionName: !Sub '${ProjectName}-add-client-id-claim'
    Runtime: python3.11
    Handler: index.lambda_handler
    Code:
      ZipFile: |
        def lambda_handler(event, context):
            # Get client ID from request context
            client_id = event['callerContext']['clientId']

            # Add client_id claim to the token
            event['response']['claimsOverrideDetails'] = {
                'claimsToAddOrOverride': {
                    'client_id': client_id
                }
            }
            return event
    Role: !GetAtt PreTokenGenerationLambdaRole.Arn

PreTokenGenerationLambdaRole:
  Type: AWS::IAM::Role
  Properties:
    AssumeRolePolicyDocument:
      Version: '2012-10-17'
      Statement:
        - Effect: Allow
          Principal:
            Service: lambda.amazonaws.com
          Action: sts:AssumeRole
    ManagedPolicyArns:
      - arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole

# Add Lambda permission for Cognito to invoke
PreTokenGenerationLambdaPermission:
  Type: AWS::Lambda::Permission
  Properties:
    FunctionName: !Ref PreTokenGenerationLambda
    Principal: cognito-idp.amazonaws.com
    Action: lambda:InvokeFunction
    SourceArn: !GetAtt ArcMcpUserPool.Arn

# Update User Pool with Lambda trigger
ArcMcpUserPool:
  Type: AWS::Cognito::UserPool
  Properties:
    # ... other properties ...
    LambdaConfig:
      PreTokenGeneration: !GetAtt PreTokenGenerationLambda.Arn
```

**After deploying Lambda**, tokens will include:
```json
{
  "aud": "CLIENT_ID",
  "client_id": "CLIENT_ID",  ← Added by Lambda!
  "sub": "user-id",
  // ... other claims
}
```

**Alternative Solutions**:
1. Use SigV4 authentication instead of OAuth (requires custom signing in MCP client)
2. Use a different OAuth provider with `client_id` claim support

### Getting Bearer Tokens

```bash
aws cognito-idp initiate-auth \
  --auth-flow USER_PASSWORD_AUTH \
  --client-id CLIENT_ID \
  --auth-parameters USERNAME=user@example.com,PASSWORD=password \
  --region REGION \
  --query 'AuthenticationResult.IdToken' \
  --output text
```

**Note**: Tokens expire after 60 minutes by default.

---

## Invocation Examples

### Complete Working Example

**Prerequisites**:
```bash
pip install mcp boto3
```

**Step 1: Get Bearer Token from Cognito**
```bash
BEARER_TOKEN=$(aws cognito-idp initiate-auth \
  --auth-flow USER_PASSWORD_AUTH \
  --client-id YOUR_CLIENT_ID \
  --auth-parameters USERNAME=user@example.com,PASSWORD=YourPassword \
  --region us-east-1 \
  --query 'AuthenticationResult.IdToken' \
  --output text)

echo "Token: $BEARER_TOKEN"
```

**Step 2: Verify Token Has client_id Claim** (if using Lambda solution)
```bash
# Decode JWT to check claims (requires jq)
echo $BEARER_TOKEN | cut -d. -f2 | base64 -d 2>/dev/null | jq .
# Should show: "client_id": "YOUR_CLIENT_ID"
```

**Step 3: Invoke MCP Server**
```python
#!/usr/bin/env python3
"""
Complete working example for invoking MCP servers on AgentCore
"""
import asyncio
import os
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

async def invoke_mcp_server():
    # Configuration
    agent_arn = "arn:aws:bedrock-agentcore:us-east-1:ACCOUNT_ID:runtime/AGENT_NAME-RANDOM_ID"
    region = "us-east-1"
    bearer_token = os.getenv('BEARER_TOKEN')  # From Cognito

    if not bearer_token:
        raise ValueError("BEARER_TOKEN environment variable not set")

    # URL-encode the ARN
    encoded_arn = agent_arn.replace(':', '%3A').replace('/', '%2F')
    mcp_url = f"https://bedrock-agentcore.{region}.amazonaws.com/runtimes/{encoded_arn}/invocations?qualifier=DEFAULT"

    print(f"Connecting to: {mcp_url[:80]}...")

    # Headers with OAuth bearer token
    headers = {
        "authorization": f"Bearer {bearer_token}",
        "Content-Type": "application/json"
    }

    try:
        # Connect using MCP client library
        async with streamablehttp_client(
            mcp_url,
            headers,
            timeout=120,
            terminate_on_close=False
        ) as (read_stream, write_stream, _):

            # Create MCP session
            async with ClientSession(read_stream, write_stream) as session:
                # Step 1: Initialize (required MCP handshake)
                print("Initializing MCP session...")
                init_result = await session.initialize()
                print(f"✅ Initialized! Server: {init_result.server_info.name}")

                # Step 2: List available tools
                print("\nListing tools...")
                tools_result = await session.list_tools()
                print(f"✅ Found {len(tools_result.tools)} tools:")
                for tool in tools_result.tools:
                    print(f"  - {tool.name}: {tool.description}")

                # Step 3: Call a tool
                print("\nCalling validate_content tool...")
                call_result = await session.call_tool(
                    "validate_content",
                    arguments={
                        "guardrail_id": "YOUR_GUARDRAIL_ID",
                        "content": "Test content",
                        "guardrail_version": "DRAFT",
                        "source": "OUTPUT"
                    }
                )
                print(f"✅ Tool result: {call_result}")

                print("\n🎉 SUCCESS! All operations completed.")

    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(invoke_mcp_server())
```

**Usage**:
```bash
export BEARER_TOKEN="eyJraWQiOiJ..."  # Your Cognito token
python3 invoke_mcp.py
```

### Expected Output

```
Connecting to: https://bedrock-agentcore.us-east-1.amazonaws.com/runtimes/arn%3Aaws...
Initializing MCP session...
✅ Initialized! Server: bedrock-arc-validator

Listing tools...
✅ Found 4 tools:
  - validate_content: Validate text content against an AWS Bedrock ARC policy
  - list_guardrails: List available AWS Bedrock Guardrails with ARC policies
  - get_guardrail_info: Get detailed information about a specific guardrail
  - rewrite_response: Validate LLM response and rewrite based on ARC findings

Calling validate_content tool...
✅ Tool result: {...}

🎉 SUCCESS! All operations completed.
```

### Common Invocation Errors

**403 Forbidden**:
- Missing or invalid bearer token
- Token expired (renew with `aws cognito-idp initiate-auth`)
- OAuth not configured properly in AgentCore

**406 Not Acceptable**:
- Wrong transport in main.py (must be `streamable-http`)
- Using boto3 `invoke_agent_runtime` instead of MCP client
- Missing `stateless_http=True` parameter

**Connection Timeout**:
- AgentCore runtime not deployed yet (check `agentcore status`)
- Network/VPC configuration issues
- Wrong region in URL

---

## Testing and Debugging

### Check Deployment Status

```bash
agentcore status --agent AGENT_NAME
```

### Tail Logs

```bash
# Runtime logs
aws logs tail /aws/bedrock-agentcore/runtimes/AGENT_ARN-DEFAULT \
  --log-stream-name-prefix "2025/11/01/[runtime-logs]" \
  --follow \
  --region REGION

# OpenTelemetry logs
aws logs tail /aws/bedrock-agentcore/runtimes/AGENT_ARN-DEFAULT \
  --log-stream-names "otel-rt-logs" \
  --follow \
  --region REGION
```

### Test with curl

```bash
BEARER_TOKEN="<token>"
AGENT_ARN="arn:aws:bedrock-agentcore:REGION:ACCOUNT:runtime/AGENT_NAME-ID"

# URL encode the ARN
ENCODED_ARN=$(python3 -c "import urllib.parse; print(urllib.parse.quote('$AGENT_ARN', safe=''))")

curl -X POST \
  "https://bedrock-agentcore.REGION.amazonaws.com/runtimes/$ENCODED_ARN/invocations?qualifier=DEFAULT" \
  -H "Authorization: Bearer $BEARER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'
```

### Common HTTP Response Codes

- **400 Bad Request**: MCP protocol issue (wrong transport, malformed JSON-RPC)
- **403 Forbidden**: Authentication failure (expired/invalid token, OAuth config issue)
- **307 Temporary Redirect**: Normal for stateful HTTP (should not see with `stateless_http=True`)

---

## Common Issues and Solutions

### Issue 1: CloudFormation Stack Fails with TestUser

**Error**: `AWS::Cognito::UserPoolUser` - InvalidRequest

**Solution**: Remove user creation from CloudFormation, create manually with AWS CLI

**Fix**: Add parameters to make test user creation optional

### Issue 2: AgentCore Deploy Fails with ECR Access Denied

**Error**:
```
Access denied while validating ECR URI. The execution role requires permissions
for ecr:GetAuthorizationToken, ecr:BatchGetImage, and ecr:GetDownloadUrlForLayer
```

**Solution**: Add ECR permissions to execution role IAM policy

### Issue 3: MCP Server Returns 400 Bad Request

**Error**: Logs show `400 Bad Request` with streamable_http_manager

**Cause**: Wrong transport configuration

**Solution**: Use `transport="http"` with `stateless_http=True`

### Issue 4: OAuth Authorization Claim Mismatch

**Error**: `Claim 'client_id' value mismatch with configuration`

**Cause**: Cognito uses `aud` claim, AgentCore expects `client_id` claim

**Solution**: Currently unresolved - requires alternative auth approach

### Issue 5: Invalid Agent Name

**Error**: `Invalid agent name. Must start with a letter, contain only letters/numbers/underscores`

**Solution**: Use underscores instead of hyphens: `arc_mcp_server` not `arc-mcp-server`

### Issue 6: Authorizer Configuration Format Error

**Error**: `Invalid number of parameters set for tagged union structure authorizerConfiguration`

**Solution**: Fix YAML structure - `customJWTAuthorizer` should be a nested key, not a sibling to `type`

---

## Key Takeaways

### ✅ What Works

1. **CloudFormation Infrastructure**: Successfully deploys with proper IAM permissions and ECR access
2. **Flexible Resource Configuration**: Can reuse existing Cognito resources or create new ones
3. **Interactive Deployment Script**: User-friendly prompts for configuration choices
4. **MCP Server Build & Deploy**: Successfully builds ARM64 containers and deploys to AgentCore
5. **FastMCP with Stateless HTTP**: Correct transport configuration for AgentCore

### ❌ What Doesn't Work (Yet)

1. **OAuth JWT Authentication**: Claim mismatch between Cognito ID tokens and AgentCore's expectations
2. **End-to-End MCP Invocation**: Cannot successfully invoke tools due to auth issue

### 🔄 Recommended Next Steps

1. **Investigate SigV4 Authentication**: May be more compatible than OAuth with Cognito
2. **Custom JWT Claims**: Explore Cognito pre-token generation Lambda to add `client_id` claim
3. **Alternative OAuth Providers**: Test with providers that include `client_id` claim natively
4. **AWS Support**: Consult AWS documentation or support for AgentCore + Cognito best practices

### 📚 Documentation Gaps

1. AgentCore JWT authorizer claim requirements not clearly documented
2. Cognito ID token compatibility with AgentCore not addressed in official docs
3. FastMCP transport options for AgentCore not well documented
4. ECR permissions requirement not mentioned in basic AgentCore setup guides

---

## Reference Links

- [AWS Bedrock AgentCore Documentation](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/)
- [Model Context Protocol Specification](https://spec.modelcontextprotocol.io/)
- [FastMCP Documentation](https://github.com/modelcontextprotocol/python-sdk)
- [AWS Cognito JWT Documentation](https://docs.aws.amazon.com/cognito/latest/developerguide/amazon-cognito-user-pools-using-tokens-with-identity-providers.html)

---

## Appendix: Complete Working Configuration Files

### CloudFormation Template Structure (Partial)

```yaml
Parameters:
  UseExistingUserPool: { Type: String, Default: 'false', AllowedValues: ['true', 'false'] }
  ExistingUserPoolId: { Type: String, Default: '' }
  CreateTestUser: { Type: String, Default: 'false', AllowedValues: ['true', 'false'] }

Conditions:
  CreateNewUserPool: !Equals [!Ref UseExistingUserPool, 'false']
  ShouldCreateTestUser: !Equals [!Ref CreateTestUser, 'true']

Resources:
  ExecutionRole:
    Type: AWS::IAM::Role
    Properties:
      Policies:
        - PolicyName: ECRAccess
          PolicyDocument:
            Statement:
              - Effect: Allow
                Action:
                  - ecr:GetAuthorizationToken
                  - ecr:BatchGetImage
                  - ecr:GetDownloadUrlForLayer
                  - ecr:BatchCheckLayerAvailability
                Resource: '*'
```

### FastMCP Server (main.py)

```python
from fastmcp import FastMCP

mcp = FastMCP("server-name")

@mcp.tool()
def example_tool(param: str) -> str:
    """Example tool"""
    return f"Result: {param}"

# AgentCore expects stateless HTTP MCP protocol
if __name__ == "__main__":
    mcp.run(transport="http", stateless_http=True)
```

### AgentCore Config (.bedrock_agentcore.yaml)

```yaml
default_agent: arc_mcp_server
agents:
  arc_mcp_server:
    name: arc_mcp_server
    entrypoint: /path/to/main.py
    aws:
      execution_role: arn:aws:iam::ACCOUNT:role/execution-role
      region: us-east-1
      protocol_configuration:
        server_protocol: MCP
    authorizer_configuration:
      customJWTAuthorizer:
        discoveryUrl: https://cognito-idp.us-east-1.amazonaws.com/POOL_ID/.well-known/openid-configuration
        allowedClients:
          - CLIENT_ID
```

---

**Last Updated**: 2025-11-01
**Status**: Infrastructure working, OAuth authentication issue unresolved
**Contributors**: Lessons learned from ARC MCP Server deployment project

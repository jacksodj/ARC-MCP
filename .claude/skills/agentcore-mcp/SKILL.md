---
name: agentcore-mcp
description: Build, deploy, secure, and test MCP servers on AWS Bedrock AgentCore. Use when developing Model Context Protocol servers, configuring OAuth authentication, debugging 406/403 errors, or setting up AgentCore infrastructure. Includes critical transport requirements, Lambda-based JWT claim injection, and working invocation patterns.
---

# AgentCore MCP Server Development & Deployment

Deploy production-ready MCP (Model Context Protocol) servers to AWS Bedrock AgentCore with proper OAuth authentication, security, and testing.

## When to Use This Skill

Use this skill when you need to:
- Create or deploy MCP servers to AWS Bedrock AgentCore
- Configure OAuth authentication with Cognito for MCP servers
- Debug 406 "Not Acceptable" or 403 "Forbidden" errors
- Set up CloudFormation infrastructure for MCP deployments
- Test MCP server invocations with proper authentication
- Understand AgentCore transport and protocol requirements

## Critical Requirements (Non-Negotiable!)

### 1. Transport Configuration
**MCP servers MUST use stateless streamable-http:**

```python
# main.py - CORRECT configuration
if __name__ == "__main__":
    mcp.run(transport="streamable-http", stateless_http=True, host="0.0.0.0")
```

❌ **Never use**: `transport="http"` → causes 406 errors
❌ **Never use**: `host="127.0.0.1"` → fails in Docker containers

### 2. Invocation Method
**You CANNOT invoke MCP servers using boto3:**

```python
# ❌ WRONG - This will never work
client = boto3.client('bedrock-agentcore')
response = client.invoke_agent_runtime(
    payload=json.dumps({"jsonrpc": "2.0", "method": "tools/list"})
)
```

**✅ CORRECT - Use MCP Python client library:**

```python
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

async with streamablehttp_client(mcp_url, headers) as (read, write, _):
    async with ClientSession(read, write) as session:
        await session.initialize()
        tools = await session.list_tools()
```

### 3. Authentication Requirements
**MCP servers require OAuth or SigV4 authentication.**

**Critical Cognito Issue**: Standard Cognito JWTs use `aud` claim for client ID, but AgentCore expects `client_id` claim.

**Solution**: Use Pre-Token Generation Lambda to inject the claim.

## Step-by-Step Implementation

### Phase 1: Infrastructure Setup

1. **Review CloudFormation Template**
   - Check `cloudformation-template.yaml` includes Pre-Token Generation Lambda
   - Verify IAM execution role has ECR permissions
   - Ensure User Pool has Lambda trigger configured

2. **Deploy Infrastructure**
   ```bash
   ./scripts/deploy-infrastructure.sh
   ```

   Or manually:
   ```bash
   aws cloudformation create-stack \
     --stack-name arc-mcp-server-infrastructure \
     --template-body file://cloudformation-template.yaml \
     --capabilities CAPABILITY_NAMED_IAM
   ```

3. **Get Deployment Outputs**
   ```bash
   aws cloudformation describe-stacks \
     --stack-name arc-mcp-server-infrastructure \
     --query 'Stacks[0].Outputs'
   ```

   Save: User Pool ID, Client ID, Execution Role ARN

### Phase 2: MCP Server Configuration

1. **Verify Transport Configuration**
   Check `main.py` has correct transport:
   ```python
   mcp.run(transport="streamable-http", stateless_http=True, host="0.0.0.0")
   ```

2. **Configure AgentCore**
   Edit `.bedrock_agentcore.yaml`:
   ```yaml
   authorizer_configuration:
     customJWTAuthorizer:
       discoveryUrl: https://cognito-idp.REGION.amazonaws.com/USER_POOL_ID/.well-known/openid-configuration
       allowedClients:
         - CLIENT_ID
   ```

3. **Deploy Agent**
   ```bash
   agentcore launch --agent AGENT_NAME
   ```

### Phase 3: Authentication & Testing

1. **Create Test User**
   ```bash
   aws cognito-idp admin-create-user \
     --user-pool-id USER_POOL_ID \
     --username user@example.com \
     --user-attributes Name=email,Value=user@example.com Name=email_verified,Value=true

   aws cognito-idp admin-set-user-password \
     --user-pool-id USER_POOL_ID \
     --username user@example.com \
     --password PASSWORD \
     --permanent
   ```

2. **Get Bearer Token**
   ```bash
   ./scripts/get-bearer-token.sh > /tmp/bearer_token.txt
   ```

   Or manually:
   ```bash
   aws cognito-idp initiate-auth \
     --auth-flow USER_PASSWORD_AUTH \
     --client-id CLIENT_ID \
     --auth-parameters USERNAME=user@example.com,PASSWORD=password \
     --query 'AuthenticationResult.IdToken' \
     --output text
   ```

3. **Verify client_id Claim**
   ```bash
   cat /tmp/bearer_token.txt | cut -d. -f2 | base64 -d | jq .client_id
   ```

   Should show: `"CLIENT_ID"` (if Lambda is working)

4. **Test MCP Invocation**
   ```bash
   python3 scripts/test-mcp-invocation.py
   ```

   Expected output:
   ```
   ✅ Initialized! Server: your-mcp-server
   ✅ Found X tools
   🎉 SUCCESS!
   ```

### Phase 4: Cleanup & Resource Management

#### Complete Cleanup (Remove Everything)

1. **Destroy AgentCore Agent**
   ```bash
   # Preview what will be destroyed
   agentcore destroy --agent AGENT_NAME --dry-run

   # Destroy agent and all resources
   agentcore destroy --agent AGENT_NAME --force --delete-ecr-repo
   ```

   This removes:
   - AgentCore agent runtime
   - ECR repository and all images
   - CodeBuild project
   - IAM execution role
   - Memory resources
   - Agent configuration

2. **Clean Up Lambda Resources**

   If using CloudFormation:
   ```bash
   # Lambda functions created by stack must be deleted first
   aws lambda delete-function \
     --function-name PROJECT_NAME-add-client-id-claim \
     --region REGION

   # Remove Lambda IAM role
   aws iam detach-role-policy \
     --role-name PROJECT_NAME-pretokengen-lambda-role \
     --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole

   aws iam delete-role \
     --role-name PROJECT_NAME-pretokengen-lambda-role
   ```

3. **Delete CloudWatch Log Groups**
   ```bash
   # AgentCore runtime logs
   aws logs delete-log-group \
     --log-group-name /aws/bedrock-agentcore/runtimes/AGENT_ID-DEFAULT \
     --region REGION

   # Lambda logs
   aws logs delete-log-group \
     --log-group-name /aws/lambda/PROJECT_NAME-add-client-id-claim \
     --region REGION

   # MCP server logs (if exists)
   aws logs delete-log-group \
     --log-group-name /aws/bedrock-agentcore/PROJECT_NAME \
     --region REGION
   ```

4. **Remove Lambda Trigger from Cognito**
   ```bash
   # Remove Pre-Token Generation trigger
   aws cognito-idp update-user-pool \
     --user-pool-id USER_POOL_ID \
     --region REGION \
     --lambda-config '{}'
   ```

5. **Delete CloudFormation Stack** (if everything is removed)
   ```bash
   # Only after cleaning up Lambda and triggers
   aws cloudformation delete-stack \
     --stack-name PROJECT_NAME-infrastructure \
     --region REGION

   # Wait for completion
   aws cloudformation wait stack-delete-complete \
     --stack-name PROJECT_NAME-infrastructure \
     --region REGION
   ```

#### Partial Cleanup (Keep Cognito for Reuse)

If you want to keep Cognito User Pool and users for other projects:

1. **Destroy AgentCore Agent** (same as above)
   ```bash
   agentcore destroy --agent AGENT_NAME --force --delete-ecr-repo
   ```

2. **Remove Lambda Trigger from User Pool**
   ```bash
   aws cognito-idp update-user-pool \
     --user-pool-id USER_POOL_ID \
     --region REGION \
     --lambda-config '{}'
   ```

3. **Delete Lambda Function and Role**
   ```bash
   # Delete function
   aws lambda delete-function \
     --function-name PROJECT_NAME-add-client-id-claim \
     --region REGION

   # Clean up role
   aws iam detach-role-policy \
     --role-name PROJECT_NAME-pretokengen-lambda-role \
     --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole

   aws iam delete-role \
     --role-name PROJECT_NAME-pretokengen-lambda-role
   ```

4. **Delete CloudWatch Logs** (same as complete cleanup)

5. **Keep CloudFormation Stack** (it will be in "drifted" state but Cognito resources remain functional)

   Or manually delete non-Cognito resources from the stack using the AWS Console.

#### Quick Cleanup Script

```bash
#!/bin/bash
# cleanup-mcp-deployment.sh

AGENT_NAME="arc_mcp_server"
PROJECT_NAME="arc-mcp-server"
REGION="us-east-1"

echo "🧹 Cleaning up MCP deployment..."

# 1. Destroy AgentCore agent
echo "Destroying AgentCore agent..."
agentcore destroy --agent $AGENT_NAME --force --delete-ecr-repo

# 2. Get User Pool ID from CloudFormation
USER_POOL_ID=$(aws cloudformation describe-stack-resources \
  --stack-name ${PROJECT_NAME}-infrastructure \
  --region $REGION \
  --logical-resource-id ArcMcpUserPool \
  --query 'StackResources[0].PhysicalResourceId' \
  --output text)

# 3. Remove Lambda trigger
echo "Removing Lambda trigger from User Pool..."
aws cognito-idp update-user-pool \
  --user-pool-id $USER_POOL_ID \
  --region $REGION \
  --lambda-config '{}'

# 4. Delete Lambda function
echo "Deleting Lambda function..."
aws lambda delete-function \
  --function-name ${PROJECT_NAME}-add-client-id-claim \
  --region $REGION

# 5. Delete Lambda role
echo "Deleting Lambda IAM role..."
aws iam detach-role-policy \
  --role-name ${PROJECT_NAME}-pretokengen-lambda-role \
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole
aws iam delete-role \
  --role-name ${PROJECT_NAME}-pretokengen-lambda-role

# 6. Delete CloudWatch logs
echo "Deleting CloudWatch log groups..."
aws logs delete-log-group \
  --log-group-name /aws/lambda/${PROJECT_NAME}-add-client-id-claim \
  --region $REGION 2>/dev/null || true

aws logs delete-log-group \
  --log-group-name /aws/bedrock-agentcore/${PROJECT_NAME} \
  --region $REGION 2>/dev/null || true

# Find and delete runtime logs
AGENT_LOG_GROUPS=$(aws logs describe-log-groups \
  --region $REGION \
  --log-group-name-prefix "/aws/bedrock-agentcore/runtimes/${AGENT_NAME}" \
  --query 'logGroups[].logGroupName' \
  --output text)

for log_group in $AGENT_LOG_GROUPS; do
  echo "Deleting log group: $log_group"
  aws logs delete-log-group --log-group-name "$log_group" --region $REGION
done

echo "✅ Cleanup complete!"
echo ""
echo "Kept resources (delete manually if not needed):"
echo "  - Cognito User Pool: $USER_POOL_ID"
echo "  - CloudFormation stack: ${PROJECT_NAME}-infrastructure (in drifted state)"
```

#### Verification After Cleanup

```bash
# Verify AgentCore agent is gone
agentcore configure list
# Should show: "No agents configured"

# Verify Lambda is gone
aws lambda list-functions --region REGION \
  --query "Functions[?contains(FunctionName, 'PROJECT_NAME')].FunctionName"
# Should return empty

# Verify ECR repository is gone
aws ecr describe-repositories --region REGION \
  --query "repositories[?contains(repositoryName, 'AGENT_NAME')].repositoryName"
# Should error with RepositoryNotFoundException

# Check remaining log groups
aws logs describe-log-groups --region REGION \
  --log-group-name-prefix "/aws/bedrock-agentcore" \
  --query "logGroups[].logGroupName"
# Should not show your agent's logs
```

#### Troubleshooting Cleanup

**Error: Cannot delete Lambda - still attached to User Pool**
```bash
# Remove the trigger first
aws cognito-idp update-user-pool \
  --user-pool-id USER_POOL_ID \
  --lambda-config '{}'
```

**Error: Cannot delete role - policy still attached**
```bash
# List and detach all policies
aws iam list-attached-role-policies --role-name ROLE_NAME
aws iam detach-role-policy --role-name ROLE_NAME --policy-arn ARN
```

**Error: CloudFormation stack delete fails**
- Check for resources created outside CloudFormation
- Delete dependent resources manually first
- Use `--retain-resources` to keep specific resources:
  ```bash
  aws cloudformation delete-stack \
    --stack-name STACK_NAME \
    --retain-resources ArcMcpUserPool ArcMcpUserPoolClient
  ```

**Background processes still running**
```bash
# If agentcore launch is running in background
pkill -f "agentcore launch"

# Check for Docker containers
docker ps | grep agentcore
docker stop CONTAINER_ID
```

## Pre-Token Generation Lambda

**CloudFormation Resource**:

```yaml
PreTokenGenerationLambda:
  Type: AWS::Lambda::Function
  Properties:
    FunctionName: !Sub '${ProjectName}-add-client-id-claim'
    Runtime: python3.11
    Handler: index.lambda_handler
    Code:
      ZipFile: |
        def lambda_handler(event, context):
            client_id = event['callerContext']['clientId']
            event['response']['claimsOverrideDetails'] = {
                'claimsToAddOrOverride': {
                    'client_id': client_id
                }
            }
            return event
    Role: !GetAtt PreTokenGenerationLambdaRole.Arn

# Attach to User Pool
ArcMcpUserPool:
  Properties:
    LambdaConfig:
      PreTokenGeneration: !GetAtt PreTokenGenerationLambda.Arn
```

## Troubleshooting Guide

### Error: 406 Not Acceptable

**Causes**:
1. Wrong transport (using `http` instead of `streamable-http`)
2. Missing `stateless_http=True` parameter
3. Using boto3 instead of MCP client library

**Solution**:
- Fix `main.py` transport configuration
- Use MCP Python client library for invocation
- Redeploy agent: `agentcore launch`

### Error: 403 Forbidden

**Causes**:
1. Missing or invalid bearer token
2. Token expired (60 min default)
3. OAuth not configured in AgentCore
4. Missing `client_id` claim in JWT

**Solution**:
- Get fresh token: `./scripts/get-bearer-token.sh`
- Verify token has `client_id` claim
- Check `.bedrock_agentcore.yaml` has OAuth config
- Verify Lambda is attached to User Pool

### Error: OAuth claim mismatch

**Error Message**: `Claim 'client_id' value mismatch with configuration`

**Cause**: Cognito JWT missing `client_id` claim

**Solution**: Deploy Pre-Token Generation Lambda (see above)

### Server Not Responding

**Checks**:
1. Verify agent status: `agentcore status`
2. Check CloudWatch logs:
   ```bash
   aws logs tail /aws/bedrock-agentcore/runtimes/AGENT_ARN-DEFAULT \
     --log-stream-name-prefix "2025/11/01/[runtime-logs]" \
     --follow
   ```
3. Verify server started: Look for "StreamableHTTP session manager started"

## Working Invocation Example

```python
#!/usr/bin/env python3
import asyncio
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

async def invoke_mcp():
    agent_arn = "arn:aws:bedrock-agentcore:REGION:ACCOUNT:runtime/NAME-ID"
    bearer_token = open('/tmp/bearer_token.txt').read().strip()

    # URL-encode ARN
    encoded_arn = agent_arn.replace(':', '%3A').replace('/', '%2F')
    mcp_url = f"https://bedrock-agentcore.REGION.amazonaws.com/runtimes/{encoded_arn}/invocations?qualifier=DEFAULT"

    headers = {
        "authorization": f"Bearer {bearer_token}",
        "Content-Type": "application/json"
    }

    async with streamablehttp_client(mcp_url, headers, timeout=120) as (r, w, _):
        async with ClientSession(r, w) as session:
            # Initialize
            await session.initialize()

            # List tools
            tools = await session.list_tools()
            print(f"Found {len(tools.tools)} tools")

            # Call a tool
            result = await session.call_tool("tool_name", arguments={...})
            return result

asyncio.run(invoke_mcp())
```

## Security Best Practices

1. **Never commit credentials**
   - Use `.env` files (gitignored)
   - Store in AWS Secrets Manager for production
   - Use IAM roles where possible

2. **Token Management**
   - Tokens expire after 60 minutes (default)
   - Implement token refresh logic
   - Use secure token storage

3. **Lambda Permissions**
   - Pre-Token Lambda only needs basic execution role
   - Use least-privilege IAM policies
   - Enable CloudWatch logging for debugging

4. **User Pool Configuration**
   - Enable MFA for production
   - Use strong password policies
   - Implement account lockout policies

## Reference Documentation

For complete details, see:
- [reference.md](reference.md) - Complete AWS documentation links and API references
- [examples.md](examples.md) - Additional code examples and use cases
- Project docs:
  - `docs/agentcore-mcp-deployment-guide.md` - Complete deployment guide
  - `docs/solution-summary.md` - Technical analysis
  - `docs/SUCCESS-oauth-mcp-working.md` - Working implementation details

## Quick Reference Commands

### Deployment
```bash
# Deploy infrastructure
./scripts/deploy-infrastructure.sh

# Configure agent
agentcore configure --entrypoint main.py --name AGENT_NAME --protocol MCP

# Launch agent
agentcore launch

# Get status
agentcore status
```

### Testing
```bash
# Get bearer token
./scripts/get-bearer-token.sh > /tmp/bearer_token.txt

# Test invocation
python3 scripts/test-mcp-invocation.py

# Check logs
aws logs tail /aws/bedrock-agentcore/runtimes/AGENT_ARN-DEFAULT \
  --log-stream-name-prefix "$(date +%Y/%m/%d)/[runtime-logs]" \
  --follow
```

### Cleanup
```bash
# Preview cleanup
agentcore destroy --agent AGENT_NAME --dry-run

# Destroy agent (keep ECR)
agentcore destroy --agent AGENT_NAME --force

# Destroy agent + ECR
agentcore destroy --agent AGENT_NAME --force --delete-ecr-repo

# Delete Lambda
aws lambda delete-function --function-name PROJECT_NAME-add-client-id-claim

# Delete CloudWatch logs
aws logs delete-log-group --log-group-name /aws/lambda/PROJECT_NAME-add-client-id-claim

# Remove Lambda from Cognito
aws cognito-idp update-user-pool --user-pool-id USER_POOL_ID --lambda-config '{}'
```

## Success Criteria

✅ CloudFormation stack deployed successfully
✅ Pre-Token Generation Lambda attached to User Pool
✅ Bearer tokens include `client_id` claim
✅ Agent shows "READY" status
✅ MCP client successfully initializes session
✅ Tools are discoverable via `list_tools()`
✅ Tool invocations complete successfully

## Common Patterns

### Pattern: Development → Staging → Production

1. **Development**:
   - Use local AgentCore: `agentcore launch --local`
   - Test without OAuth (faster iteration)
   - Use test User Pool

2. **Staging**:
   - Deploy to AgentCore with OAuth
   - Use staging User Pool
   - End-to-end testing with real credentials

3. **Production**:
   - Separate User Pool per environment
   - Enable MFA and advanced security
   - Monitor CloudWatch metrics
   - Implement token refresh logic

### Pattern: Multi-Tool MCP Server

```python
from fastmcp import FastMCP

mcp = FastMCP("my-mcp-server")

@mcp.tool()
def tool_one(param: str) -> dict:
    """First tool description"""
    return {"result": "..."}

@mcp.tool()
def tool_two(param: int) -> dict:
    """Second tool description"""
    return {"result": "..."}

if __name__ == "__main__":
    mcp.run(transport="streamable-http", stateless_http=True, host="0.0.0.0")
```

### Pattern: Error Handling in Tools

```python
@mcp.tool()
def safe_tool(param: str) -> dict:
    """Tool with proper error handling"""
    try:
        # Your logic here
        result = process(param)
        return {"success": True, "data": result}
    except ValueError as e:
        logger.error(f"Validation error: {e}")
        return {"success": False, "error": str(e)}
    except Exception as e:
        logger.exception("Unexpected error")
        return {"success": False, "error": "Internal error"}
```

## Additional Resources

- AWS Bedrock AgentCore Docs: https://docs.aws.amazon.com/bedrock-agentcore/
- MCP Specification: https://spec.modelcontextprotocol.io/
- FastMCP: https://github.com/modelcontextprotocol/python-sdk
- Cognito Pre-Token Triggers: https://docs.aws.amazon.com/cognito/latest/developerguide/user-pool-lambda-pre-token-generation.html

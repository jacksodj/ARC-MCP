# AgentCore MCP Examples

## Complete Working Examples

### Example 1: Simple MCP Server

**File: `simple_mcp_server.py`**

```python
#!/usr/bin/env python3
"""
Minimal working MCP server for AgentCore
"""
from fastmcp import FastMCP

# Create server
mcp = FastMCP("simple-calculator")

@mcp.tool()
def add(a: int, b: int) -> dict:
    """Add two numbers together"""
    return {"result": a + b}

@mcp.tool()
def multiply(a: int, b: int) -> dict:
    """Multiply two numbers"""
    return {"result": a * b}

# CRITICAL: Use correct transport for AgentCore
if __name__ == "__main__":
    mcp.run(
        transport="streamable-http",
        stateless_http=True,
        host="0.0.0.0"
    )
```

### Example 2: MCP Server with AWS Integration

**File: `aws_mcp_server.py`**

```python
#!/usr/bin/env python3
"""
MCP server that integrates with AWS services
"""
from fastmcp import FastMCP
import boto3
import os
import logging

# Setup
mcp = FastMCP("aws-helper")
logger = logging.getLogger(__name__)

# Initialize AWS clients
s3 = boto3.client('s3', region_name=os.environ.get('AWS_REGION', 'us-east-1'))
dynamodb = boto3.resource('dynamodb', region_name=os.environ.get('AWS_REGION', 'us-east-1'))

@mcp.tool()
def list_s3_buckets() -> dict:
    """List all S3 buckets in the account"""
    try:
        response = s3.list_buckets()
        buckets = [b['Name'] for b in response.get('Buckets', [])]
        return {
            "success": True,
            "buckets": buckets,
            "count": len(buckets)
        }
    except Exception as e:
        logger.error(f"Error listing buckets: {e}")
        return {
            "success": False,
            "error": str(e)
        }

@mcp.tool()
def get_s3_object(bucket: str, key: str) -> dict:
    """Get an object from S3"""
    try:
        response = s3.get_object(Bucket=bucket, Key=key)
        content = response['Body'].read().decode('utf-8')
        return {
            "success": True,
            "content": content,
            "content_type": response.get('ContentType'),
            "size": response.get('ContentLength')
        }
    except Exception as e:
        logger.error(f"Error getting object: {e}")
        return {
            "success": False,
            "error": str(e)
        }

@mcp.tool()
def query_dynamodb(table_name: str, key: dict) -> dict:
    """Query a DynamoDB table"""
    try:
        table = dynamodb.Table(table_name)
        response = table.get_item(Key=key)
        return {
            "success": True,
            "item": response.get('Item', {}),
            "found": 'Item' in response
        }
    except Exception as e:
        logger.error(f"Error querying DynamoDB: {e}")
        return {
            "success": False,
            "error": str(e)
        }

if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Run with AgentCore-compatible transport
    mcp.run(
        transport="streamable-http",
        stateless_http=True,
        host="0.0.0.0",
        port=8000
    )
```

### Example 3: Complete Client Invocation

**File: `invoke_mcp_client.py`**

```python
#!/usr/bin/env python3
"""
Complete example of invoking an AgentCore MCP server
"""
import asyncio
import os
import sys
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

# Configuration
AGENT_ARN = "arn:aws:bedrock-agentcore:us-east-1:123456789012:runtime/my-agent-abc123"
REGION = "us-east-1"
BEARER_TOKEN_FILE = "/tmp/bearer_token.txt"

async def invoke_mcp_server():
    """Complete MCP invocation flow"""

    # Step 1: Load bearer token
    if not os.path.exists(BEARER_TOKEN_FILE):
        print(f"❌ Error: Token file not found: {BEARER_TOKEN_FILE}")
        print("Run: ./scripts/get-bearer-token.sh > /tmp/bearer_token.txt")
        return False

    with open(BEARER_TOKEN_FILE, 'r') as f:
        bearer_token = f.read().strip()

    # Step 2: Build MCP URL
    encoded_arn = AGENT_ARN.replace(':', '%3A').replace('/', '%2F')
    mcp_url = f"https://bedrock-agentcore.{REGION}.amazonaws.com/runtimes/{encoded_arn}/invocations?qualifier=DEFAULT"

    headers = {
        "authorization": f"Bearer {bearer_token}",
        "Content-Type": "application/json"
    }

    print(f"🔗 Connecting to AgentCore MCP server...")
    print(f"   Region: {REGION}")
    print()

    try:
        # Step 3: Connect to MCP server
        async with streamablehttp_client(
            mcp_url,
            headers,
            timeout=120,
            terminate_on_close=False
        ) as (read_stream, write_stream, _):

            # Step 4: Create MCP session
            async with ClientSession(read_stream, write_stream) as session:

                # Step 5: Initialize (required first call)
                print("Initializing MCP session...")
                init_result = await session.initialize()
                print(f"✅ Connected to: {init_result.serverInfo.name}")
                print(f"   Version: {init_result.serverInfo.version}")
                print(f"   Protocol: {init_result.protocolVersion}")
                print()

                # Step 6: List available tools
                print("Listing available tools...")
                tools_result = await session.list_tools()
                print(f"✅ Found {len(tools_result.tools)} tools:")
                for i, tool in enumerate(tools_result.tools, 1):
                    print(f"{i}. {tool.name}")
                    print(f"   {tool.description}")
                print()

                # Step 7: Call a tool (example)
                print("Calling add tool...")
                call_result = await session.call_tool(
                    "add",
                    arguments={"a": 5, "b": 3}
                )
                print(f"✅ Result: {call_result.content}")
                print()

                print("🎉 SUCCESS! All operations completed.")
                return True

    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(invoke_mcp_server())
    sys.exit(0 if success else 1)
```

### Example 4: CloudFormation Template with Lambda

**File: `cloudformation-mcp-stack.yaml`**

```yaml
AWSTemplateFormatVersion: '2010-09-09'
Description: 'Complete MCP Server Infrastructure with OAuth'

Parameters:
  ProjectName:
    Type: String
    Default: 'my-mcp-server'
    Description: 'Project name for resource naming'

Resources:
  # Pre-Token Generation Lambda
  PreTokenGenerationLambda:
    Type: AWS::Lambda::Function
    Properties:
      FunctionName: !Sub '${ProjectName}-add-client-id-claim'
      Runtime: python3.11
      Handler: index.lambda_handler
      Role: !GetAtt PreTokenGenerationLambdaRole.Arn
      Timeout: 10
      Code:
        ZipFile: |
          def lambda_handler(event, context):
              """Inject client_id claim into Cognito JWT tokens"""
              try:
                  client_id = event['callerContext']['clientId']
                  event['response']['claimsOverrideDetails'] = {
                      'claimsToAddOrOverride': {
                          'client_id': client_id
                      }
                  }
                  return event
              except Exception as e:
                  print(f"Error: {str(e)}")
                  return event
      Tags:
        - Key: Project
          Value: !Ref ProjectName

  # Lambda Execution Role
  PreTokenGenerationLambdaRole:
    Type: AWS::IAM::Role
    Properties:
      RoleName: !Sub '${ProjectName}-lambda-role'
      AssumeRolePolicyDocument:
        Version: '2012-10-17'
        Statement:
          - Effect: Allow
            Principal:
              Service: lambda.amazonaws.com
            Action: sts:AssumeRole
      ManagedPolicyArns:
        - arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole

  # Lambda Permission for Cognito
  PreTokenGenerationLambdaPermission:
    Type: AWS::Lambda::Permission
    Properties:
      FunctionName: !Ref PreTokenGenerationLambda
      Principal: cognito-idp.amazonaws.com
      Action: lambda:InvokeFunction
      SourceArn: !Sub 'arn:aws:cognito-idp:${AWS::Region}:${AWS::AccountId}:userpool/*'

  # Cognito User Pool
  UserPool:
    Type: AWS::Cognito::UserPool
    Properties:
      UserPoolName: !Sub '${ProjectName}-users'
      AutoVerifiedAttributes:
        - email
      UsernameAttributes:
        - email
      LambdaConfig:
        PreTokenGeneration: !GetAtt PreTokenGenerationLambda.Arn
      Policies:
        PasswordPolicy:
          MinimumLength: 8
          RequireUppercase: true
          RequireLowercase: true
          RequireNumbers: true
          RequireSymbols: true

  # User Pool Client
  UserPoolClient:
    Type: AWS::Cognito::UserPoolClient
    Properties:
      ClientName: !Sub '${ProjectName}-client'
      UserPoolId: !Ref UserPool
      ExplicitAuthFlows:
        - ALLOW_USER_PASSWORD_AUTH
        - ALLOW_REFRESH_TOKEN_AUTH
      GenerateSecret: false
      IdTokenValidity: 60
      RefreshTokenValidity: 30

  # MCP Server Execution Role
  ExecutionRole:
    Type: AWS::IAM::Role
    Properties:
      RoleName: !Sub '${ProjectName}-execution-role'
      AssumeRolePolicyDocument:
        Version: '2012-10-17'
        Statement:
          - Effect: Allow
            Principal:
              Service:
                - bedrock.amazonaws.com
                - bedrock-agentcore.amazonaws.com
            Action: sts:AssumeRole
      ManagedPolicyArns:
        - arn:aws:iam::aws:policy/CloudWatchLogsFullAccess
      Policies:
        - PolicyName: ECRAccess
          PolicyDocument:
            Version: '2012-10-17'
            Statement:
              - Effect: Allow
                Action:
                  - ecr:GetAuthorizationToken
                  - ecr:BatchGetImage
                  - ecr:GetDownloadUrlForLayer
                  - ecr:BatchCheckLayerAvailability
                Resource: '*'

Outputs:
  UserPoolId:
    Description: 'Cognito User Pool ID'
    Value: !Ref UserPool
    Export:
      Name: !Sub '${ProjectName}-user-pool-id'

  UserPoolClientId:
    Description: 'Cognito User Pool Client ID'
    Value: !Ref UserPoolClient
    Export:
      Name: !Sub '${ProjectName}-client-id'

  ExecutionRoleArn:
    Description: 'MCP Server Execution Role ARN'
    Value: !GetAtt ExecutionRole.Arn
    Export:
      Name: !Sub '${ProjectName}-execution-role-arn'

  AuthDiscoveryUrl:
    Description: 'OAuth 2.0 Discovery URL'
    Value: !Sub 'https://cognito-idp.${AWS::Region}.amazonaws.com/${UserPool}/.well-known/openid-configuration'

  GetTokenCommand:
    Description: 'Command to get bearer token'
    Value: !Sub |
      aws cognito-idp initiate-auth \
        --auth-flow USER_PASSWORD_AUTH \
        --client-id ${UserPoolClient} \
        --auth-parameters USERNAME=user@example.com,PASSWORD=password \
        --region ${AWS::Region} \
        --query 'AuthenticationResult.IdToken' \
        --output text
```

### Example 5: Token Management Class

**File: `token_manager.py`**

```python
"""
Token management with automatic refresh
"""
import boto3
import time
import jwt
from typing import Optional

class CognitoTokenManager:
    """Manage Cognito tokens with automatic refresh"""

    def __init__(
        self,
        user_pool_id: str,
        client_id: str,
        username: str,
        password: str,
        region: str = 'us-east-1'
    ):
        self.user_pool_id = user_pool_id
        self.client_id = client_id
        self.username = username
        self.password = password
        self.region = region
        self.client = boto3.client('cognito-idp', region_name=region)

        self._id_token: Optional[str] = None
        self._access_token: Optional[str] = None
        self._refresh_token: Optional[str] = None
        self._token_expiry: int = 0

    def get_id_token(self) -> str:
        """Get valid ID token, refreshing if necessary"""
        if self._is_token_expired():
            self._refresh_tokens()
        return self._id_token

    def _is_token_expired(self) -> bool:
        """Check if token needs refresh"""
        if not self._id_token:
            return True

        # Check if token expires in next 5 minutes
        buffer_seconds = 300
        return time.time() >= (self._token_expiry - buffer_seconds)

    def _refresh_tokens(self):
        """Refresh tokens using refresh token or re-authenticate"""
        try:
            if self._refresh_token:
                # Use refresh token
                response = self.client.initiate_auth(
                    AuthFlow='REFRESH_TOKEN_AUTH',
                    ClientId=self.client_id,
                    AuthParameters={
                        'REFRESH_TOKEN': self._refresh_token
                    }
                )
            else:
                # Initial authentication
                response = self.client.initiate_auth(
                    AuthFlow='USER_PASSWORD_AUTH',
                    ClientId=self.client_id,
                    AuthParameters={
                        'USERNAME': self.username,
                        'PASSWORD': self.password
                    }
                )

            auth_result = response['AuthenticationResult']
            self._id_token = auth_result['IdToken']
            self._access_token = auth_result['AccessToken']

            # Refresh token only provided on initial auth
            if 'RefreshToken' in auth_result:
                self._refresh_token = auth_result['RefreshToken']

            # Calculate expiry from token
            decoded = jwt.decode(
                self._id_token,
                options={"verify_signature": False}
            )
            self._token_expiry = decoded['exp']

            print(f"✅ Tokens refreshed. Expires: {time.ctime(self._token_expiry)}")

        except Exception as e:
            print(f"❌ Error refreshing tokens: {e}")
            raise

# Usage example
if __name__ == "__main__":
    token_manager = CognitoTokenManager(
        user_pool_id="us-east-1_XXXXXXXXX",
        client_id="abc123def456",
        username="user@example.com",
        password="password"
    )

    # Get token (automatically handles refresh)
    token = token_manager.get_id_token()
    print(f"Token: {token[:50]}...")
```

### Example 6: Error Handling Patterns

```python
"""
Production-ready error handling for MCP tools
"""
from fastmcp import FastMCP
from typing import Dict, Any
import logging

mcp = FastMCP("robust-mcp-server")
logger = logging.getLogger(__name__)

class ValidationError(Exception):
    """Custom validation error"""
    pass

@mcp.tool()
def robust_tool(param: str, value: int) -> Dict[str, Any]:
    """Example tool with comprehensive error handling"""

    # Input validation
    try:
        if not param:
            raise ValidationError("param cannot be empty")
        if value < 0:
            raise ValidationError("value must be non-negative")

        # Business logic
        result = process_data(param, value)

        return {
            "success": True,
            "data": result,
            "message": "Operation completed successfully"
        }

    except ValidationError as e:
        logger.warning(f"Validation error: {e}")
        return {
            "success": False,
            "error": "validation_error",
            "message": str(e)
        }

    except PermissionError as e:
        logger.error(f"Permission denied: {e}")
        return {
            "success": False,
            "error": "permission_denied",
            "message": "Insufficient permissions"
        }

    except ConnectionError as e:
        logger.error(f"Connection error: {e}")
        return {
            "success": False,
            "error": "connection_error",
            "message": "Unable to connect to external service"
        }

    except Exception as e:
        logger.exception("Unexpected error")
        return {
            "success": False,
            "error": "internal_error",
            "message": "An unexpected error occurred"
        }

def process_data(param: str, value: int) -> dict:
    """Actual processing logic"""
    # Your implementation here
    return {"result": f"processed {param} with {value}"}

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    mcp.run(transport="streamable-http", stateless_http=True, host="0.0.0.0")
```

### Example 7: Testing Script

**File: `test_mcp_server.sh`**

```bash
#!/bin/bash
# Complete testing script for MCP server deployment

set -e

PROJECT_NAME="my-mcp-server"
REGION="us-east-1"

echo "🧪 Testing MCP Server Deployment"
echo "================================="
echo ""

# Step 1: Check CloudFormation
echo "1. Checking CloudFormation stack..."
aws cloudformation describe-stacks \
  --stack-name ${PROJECT_NAME}-infrastructure \
  --region $REGION \
  --query 'Stacks[0].StackStatus' \
  --output text

if [ $? -eq 0 ]; then
  echo "✅ CloudFormation stack exists"
else
  echo "❌ CloudFormation stack not found"
  exit 1
fi

# Step 2: Check AgentCore status
echo ""
echo "2. Checking AgentCore agent status..."
agentcore status --agent $PROJECT_NAME

# Step 3: Get bearer token
echo ""
echo "3. Getting bearer token..."
./scripts/get-bearer-token.sh > /tmp/bearer_token.txt

if [ -s /tmp/bearer_token.txt ]; then
  echo "✅ Got bearer token"
else
  echo "❌ Failed to get bearer token"
  exit 1
fi

# Step 4: Verify token claims
echo ""
echo "4. Verifying token has client_id claim..."
cat /tmp/bearer_token.txt | cut -d. -f2 | base64 -d | grep -q "client_id"

if [ $? -eq 0 ]; then
  echo "✅ Token has client_id claim"
else
  echo "❌ Token missing client_id claim"
  exit 1
fi

# Step 5: Test MCP invocation
echo ""
echo "5. Testing MCP invocation..."
python3 scripts/test-mcp-invocation.py

if [ $? -eq 0 ]; then
  echo ""
  echo "🎉 All tests passed!"
else
  echo ""
  echo "❌ MCP invocation test failed"
  exit 1
fi
```

## Additional Resources

- [SKILL.md](SKILL.md) - Main skill documentation
- [reference.md](reference.md) - Complete API and CLI references

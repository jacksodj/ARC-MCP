# AgentCore MCP Reference Documentation

## Official AWS Documentation

### AWS Bedrock AgentCore
- **Main Documentation**: https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/
- **MCP Protocol Contract**: https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-mcp-protocol-contract.html
- **Deploying MCP Servers**: https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-mcp.html
- **Gateway MCP Targets**: https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-target-MCPservers.html

### AWS Cognito
- **User Pool Lambda Triggers**: https://docs.aws.amazon.com/cognito/latest/developerguide/cognito-user-identity-pools-working-with-aws-lambda-triggers.html
- **Pre-Token Generation**: https://docs.aws.amazon.com/cognito/latest/developerguide/user-pool-lambda-pre-token-generation.html
- **User Pool Authentication**: https://docs.aws.amazon.com/cognito/latest/developerguide/amazon-cognito-user-pools-authentication-flow.html

### Model Context Protocol (MCP)
- **Official Specification**: https://spec.modelcontextprotocol.io/
- **Python SDK (FastMCP)**: https://github.com/jlowin/fastmcp
- **MCP Protocol Versions**: 2025-06-18, 2025-03-26

## API References

### AgentCore Launch Configuration

```yaml
# .bedrock_agentcore.yaml structure
default_agent: agent_name
agents:
  agent_name:
    name: agent_name
    entrypoint: /path/to/main.py
    platform: linux/arm64
    container_runtime: docker
    source_path: /path/to/source
    aws:
      execution_role: arn:aws:iam::ACCOUNT:role/ROLE_NAME
      account: 'ACCOUNT_ID'
      region: us-east-1
      protocol_configuration:
        server_protocol: MCP
      observability:
        enabled: true
    authorizer_configuration:
      customJWTAuthorizer:
        discoveryUrl: https://cognito-idp.REGION.amazonaws.com/POOL_ID/.well-known/openid-configuration
        allowedClients:
          - CLIENT_ID
    memory:
      mode: STM_ONLY
```

### MCP Python Client API

```python
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

# Connect to MCP server
async with streamablehttp_client(
    url: str,                    # AgentCore endpoint URL
    headers: dict,               # Must include Authorization header
    timeout: int = 120,          # Request timeout in seconds
    terminate_on_close: bool = False
) as (read_stream, write_stream, _):

    # Create session
    async with ClientSession(read_stream, write_stream) as session:

        # Initialize (required first call)
        init_result = await session.initialize()
        # Returns: protocolVersion, capabilities, serverInfo

        # List available tools
        tools_result = await session.list_tools()
        # Returns: tools[] with name, description, inputSchema

        # Call a tool
        call_result = await session.call_tool(
            name: str,           # Tool name
            arguments: dict      # Tool arguments
        )
        # Returns: content[], isError

        # List resources (if supported)
        resources = await session.list_resources()

        # Read resource (if supported)
        resource_content = await session.read_resource(uri: str)

        # List prompts (if supported)
        prompts = await session.list_prompts()
```

### FastMCP Server API

```python
from fastmcp import FastMCP

# Create server
mcp = FastMCP(
    name: str,                   # Server name (shown to clients)
    dependencies: list = None    # Optional dependency injection
)

# Define tool
@mcp.tool()
def tool_name(
    param1: str,                 # Type hints required
    param2: int = 0              # Optional with defaults
) -> dict:                       # Return type
    """Tool description shown to clients"""
    return {"result": "value"}

# Define resource
@mcp.resource("resource://uri")
def resource_handler() -> str:
    """Resource description"""
    return "resource content"

# Define prompt
@mcp.prompt()
def prompt_name(
    arg1: str
) -> list[dict]:
    """Prompt description"""
    return [
        {"role": "user", "content": f"Prompt with {arg1}"}
    ]

# Run server
mcp.run(
    transport: str = "streamable-http",  # REQUIRED for AgentCore
    stateless_http: bool = True,         # REQUIRED for AgentCore
    host: str = "0.0.0.0",              # REQUIRED for containers
    port: int = 8000                     # Default port
)
```

## CloudFormation Resource Types

### Pre-Token Generation Lambda

```yaml
Type: AWS::Lambda::Function
Properties:
  FunctionName: String
  Runtime: python3.11 | python3.12
  Handler: index.lambda_handler
  Code:
    ZipFile: String  # Inline code
  Role: String       # IAM role ARN
  Timeout: Integer   # 3-900 seconds
```

### Lambda Permission for Cognito

```yaml
Type: AWS::Lambda::Permission
Properties:
  FunctionName: String | Ref
  Principal: cognito-idp.amazonaws.com
  Action: lambda:InvokeFunction
  SourceArn: String  # User Pool ARN or wildcard
```

### Cognito User Pool

```yaml
Type: AWS::Cognito::UserPool
Properties:
  UserPoolName: String
  LambdaConfig:
    PreTokenGeneration: String  # Lambda function ARN
  AutoVerifiedAttributes:
    - email
  UsernameAttributes:
    - email
  Policies:
    PasswordPolicy:
      MinimumLength: 8
      RequireUppercase: Boolean
      RequireLowercase: Boolean
      RequireNumbers: Boolean
      RequireSymbols: Boolean
```

### Cognito User Pool Client

```yaml
Type: AWS::Cognito::UserPoolClient
Properties:
  ClientName: String
  UserPoolId: String | Ref
  ExplicitAuthFlows:
    - ALLOW_USER_PASSWORD_AUTH
    - ALLOW_REFRESH_TOKEN_AUTH
  GenerateSecret: false          # Must be false for direct auth
  IdTokenValidity: 60            # Minutes
  AccessTokenValidity: 60
  RefreshTokenValidity: 30       # Days
```

## AWS CLI Commands

### Cognito Operations

```bash
# Initiate authentication
aws cognito-idp initiate-auth \
  --auth-flow USER_PASSWORD_AUTH \
  --client-id <CLIENT_ID> \
  --auth-parameters USERNAME=<EMAIL>,PASSWORD=<PASSWORD> \
  --region <REGION>

# Create user
aws cognito-idp admin-create-user \
  --user-pool-id <POOL_ID> \
  --username <EMAIL> \
  --user-attributes Name=email,Value=<EMAIL> Name=email_verified,Value=true \
  --message-action SUPPRESS

# Set permanent password
aws cognito-idp admin-set-user-password \
  --user-pool-id <POOL_ID> \
  --username <EMAIL> \
  --password <PASSWORD> \
  --permanent

# Describe user pool
aws cognito-idp describe-user-pool \
  --user-pool-id <POOL_ID>
```

### CloudFormation Operations

```bash
# Create stack
aws cloudformation create-stack \
  --stack-name <STACK_NAME> \
  --template-body file://template.yaml \
  --parameters ParameterKey=Key,ParameterValue=Value \
  --capabilities CAPABILITY_NAMED_IAM

# Update stack
aws cloudformation update-stack \
  --stack-name <STACK_NAME> \
  --template-body file://template.yaml \
  --parameters ParameterKey=Key,ParameterValue=Value \
  --capabilities CAPABILITY_NAMED_IAM

# Wait for completion
aws cloudformation wait stack-create-complete \
  --stack-name <STACK_NAME>

# Describe stacks
aws cloudformation describe-stacks \
  --stack-name <STACK_NAME>

# Get outputs
aws cloudformation describe-stacks \
  --stack-name <STACK_NAME> \
  --query 'Stacks[0].Outputs'
```

### Lambda Operations

```bash
# Get function
aws lambda get-function \
  --function-name <FUNCTION_NAME>

# Invoke function (test)
aws lambda invoke \
  --function-name <FUNCTION_NAME> \
  --payload '{"test": "data"}' \
  response.json

# Update function code
aws lambda update-function-code \
  --function-name <FUNCTION_NAME> \
  --zip-file fileb://function.zip
```

### CloudWatch Logs

```bash
# Tail logs
aws logs tail <LOG_GROUP_NAME> \
  --log-stream-name-prefix <PREFIX> \
  --follow

# Tail with time range
aws logs tail <LOG_GROUP_NAME> \
  --since <TIME_EXPRESSION>  # e.g., "1h", "30m"

# Describe log streams
aws logs describe-log-streams \
  --log-group-name <LOG_GROUP_NAME> \
  --order-by LastEventTime \
  --descending
```

## Environment Variables

### Standard AWS Variables
```bash
AWS_REGION=us-east-1
AWS_ACCOUNT_ID=123456789012
AWS_DEFAULT_REGION=us-east-1
```

### AgentCore Variables
```bash
AGENTCORE_AGENT_NAME=my-agent
AGENTCORE_EXECUTION_ROLE_NAME=agent-execution-role
```

### Cognito Variables
```bash
COGNITO_USER_POOL_ID=us-east-1_XXXXXXXXX
COGNITO_CLIENT_ID=abc123def456
COGNITO_TEST_USER_EMAIL=user@example.com
COGNITO_TEST_USER_PASSWORD=SecurePassword123!
```

## Error Codes

### HTTP Status Codes

| Code | Meaning | Common Causes |
|------|---------|---------------|
| 403  | Forbidden | Missing/invalid bearer token, OAuth misconfigured |
| 406  | Not Acceptable | Wrong transport, using boto3 instead of MCP client |
| 500  | Internal Server Error | Server crash, unhandled exception |
| 502  | Bad Gateway | Agent not responding, container not started |
| 504  | Gateway Timeout | Request took too long, increase timeout |

### MCP Error Codes

| Code | Type | Description |
|------|------|-------------|
| -32700 | Parse Error | Invalid JSON |
| -32600 | Invalid Request | Invalid JSON-RPC |
| -32601 | Method Not Found | Tool/method doesn't exist |
| -32602 | Invalid Params | Wrong arguments |
| -32603 | Internal Error | Server error |

## JWT Token Structure

### Standard Cognito ID Token Claims
```json
{
  "sub": "user-uuid",
  "email_verified": true,
  "iss": "https://cognito-idp.REGION.amazonaws.com/POOL_ID",
  "cognito:username": "user-uuid",
  "aud": "CLIENT_ID",
  "token_use": "id",
  "auth_time": 1234567890,
  "exp": 1234571490,
  "iat": 1234567890,
  "email": "user@example.com"
}
```

### After Lambda Injection
```json
{
  "sub": "user-uuid",
  "email_verified": true,
  "iss": "https://cognito-idp.REGION.amazonaws.com/POOL_ID",
  "cognito:username": "user-uuid",
  "aud": "CLIENT_ID",
  "client_id": "CLIENT_ID",  // Added by Lambda
  "token_use": "id",
  "auth_time": 1234567890,
  "exp": 1234571490,
  "iat": 1234567890,
  "email": "user@example.com"
}
```

## Useful JWT Decode Commands

```bash
# Decode JWT payload (requires jq)
echo "$TOKEN" | cut -d. -f2 | base64 -d | jq .

# Get specific claim
echo "$TOKEN" | cut -d. -f2 | base64 -d | jq .client_id

# Check expiration
echo "$TOKEN" | cut -d. -f2 | base64 -d | jq '.exp | todate'

# Validate token not expired
EXP=$(echo "$TOKEN" | cut -d. -f2 | base64 -d | jq .exp)
NOW=$(date +%s)
if [ $NOW -gt $EXP ]; then
  echo "Token expired"
else
  echo "Token valid for $((EXP - NOW)) seconds"
fi
```

## Port and Network Configuration

### AgentCore Default Ports
- **MCP Server**: 8000 (inside container)
- **OAuth Callback**: 8081 (local development only)

### Network Modes
- **PUBLIC**: Internet-accessible (default)
- **PRIVATE**: VPC-only access
- **LOCAL**: Development mode only

### Container Requirements
- **Architecture**: linux/arm64 (required)
- **Host Binding**: 0.0.0.0 (not 127.0.0.1)
- **Protocol**: HTTP/1.1
- **Port**: 8000 (exposed)
- **Path**: /mcp (POST endpoint)

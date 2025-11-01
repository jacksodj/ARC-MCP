# AWS Bedrock ARC MCP Server

A Model Context Protocol (MCP) server that provides standardized access to AWS Bedrock Automated Reasoning Checks (ARC). This server enables AI agents and applications to validate content against formal logic policies with mathematical precision, achieving up to 99% verification accuracy.

## Features

- **MCP-Compliant Server**: Exposes ARC validation as standardized MCP Tools
- **AWS Bedrock Integration**: Direct integration with AWS Bedrock Guardrails and ARC
- **Intelligent Response Rewriting**: Automatically rewrites LLM responses to fix policy violations
- **Easy Deployment**: Deploy to Amazon Bedrock AgentCore Runtime with one command
- **OAuth 2.0 Authentication**: Secure authentication via Amazon Cognito
- **Comprehensive Tools**: Validate, rewrite, list guardrails, and retrieve guardrail details
- **Serverless & Scalable**: Built on AWS serverless infrastructure

## Use Cases

- LLM output validation against business rules
- Content verification in regulated industries
- Multi-step reasoning validation
- Policy compliance checking
- Hallucination detection with mathematical proof

## Architecture

```
MCP Clients (Claude, Cursor, Custom Agents)
    ↓ HTTP/SSE (OAuth Bearer)
Amazon Bedrock AgentCore Runtime
    ↓ MCP Protocol
ARC MCP Server (Python + FastMCP)
    ↓ AWS SDK (boto3)
AWS Bedrock Guardrails + ARC Engine
```

## Prerequisites

- **AWS Account** with appropriate permissions
- **AWS CLI** configured with credentials
- **Python 3.11+**
- **Bedrock AgentCore Starter Toolkit**: `pip install bedrock-agentcore-starter-toolkit`
- **At least one AWS Bedrock Guardrail with ARC policy** (for testing)

## Quick Start

### 1. Clone the Repository

```bash
git clone https://github.com/your-org/ARC-MCP.git
cd ARC-MCP
```

### 2. Deploy AWS Infrastructure

This deploys the IAM execution role and Cognito User Pool for authentication.

#### Pre-Deployment Checklist

Before running the deployment script, decide:

1. **Cognito User Pool**: Do you want to create a new User Pool or use an existing one?
   - **Create New**: The script will create a dedicated Cognito User Pool for this MCP server
   - **Use Existing**: Reuse an existing User Pool (useful if you have users already configured)
     - To list your existing User Pools: `aws cognito-idp list-user-pools --max-results 20 --region us-east-1`

2. **Test User**: Do you want to create a test user during deployment?
   - **Yes**: The script will create a test user with credentials you provide
   - **No**: You'll need to create users manually or use existing users in your User Pool

#### Deploy the Infrastructure

```bash
# Set your AWS region (optional, defaults to us-east-1)
export AWS_REGION=us-east-1

# Run the interactive deployment script
./scripts/deploy-infrastructure.sh
```

The script will prompt you for:
- Whether to create a new Cognito User Pool or use an existing one
- If using existing: the User Pool ID
- Whether to create a test user
- If creating test user: username and password

This will create:
- IAM Execution Role with Bedrock ARC permissions
- Cognito User Pool for OAuth authentication (if creating new)
- Cognito User Pool Client
- Test user account (if requested)
- CloudWatch Log Group

After deployment, the script will save configuration details to `deployment-info.txt`.

#### Manual User Creation (Optional)

If you chose not to create a test user during deployment, you can create one manually:

```bash
# Get your User Pool ID from deployment-info.txt or CloudFormation outputs
USER_POOL_ID="<your-pool-id>"

# Create user
aws cognito-idp admin-create-user \
  --user-pool-id $USER_POOL_ID \
  --username testuser \
  --user-attributes Name=email,Value=testuser@example.com Name=email_verified,Value=true \
  --message-action SUPPRESS \
  --region us-east-1

# Set permanent password
aws cognito-idp admin-set-user-password \
  --user-pool-id $USER_POOL_ID \
  --username testuser \
  --password YourPassword123! \
  --permanent \
  --region us-east-1
```

### 3. Deploy MCP Server to AgentCore

```bash
./scripts/deploy-agentcore.sh
```

This will:
- Install Python dependencies
- Optionally test locally
- Deploy to Amazon Bedrock AgentCore Runtime

### 4. Get Authentication Token

```bash
./scripts/get-bearer-token.sh
```

This retrieves a Bearer token from Cognito for authenticating with the MCP server. The token is saved to `bearer-token.txt` and displayed in the terminal.

### 5. Test the Server

```bash
# Export the bearer token
export BEARER_TOKEN="<your-token-from-previous-step>"

# Run tests
./scripts/test-mcp-server.sh
```

## MCP Tools

The server exposes four MCP tools:

### 1. `validate_content`

Validate text content against an AWS Bedrock ARC policy.

**Parameters:**
- `guardrail_id` (string, required): Guardrail identifier (ID or ARN)
- `content` (string, required): Text content to validate
- `guardrail_version` (string, optional): Version number or 'DRAFT' (default: 'DRAFT')
- `source` (string, optional): 'INPUT' or 'OUTPUT' (default: 'OUTPUT')

**Example:**
```python
result = await mcp_client.call_tool(
    "validate_content",
    {
        "guardrail_id": "abc123xyz",
        "content": "Employee with 8 months tenure is eligible for benefits",
        "guardrail_version": "1",
        "source": "OUTPUT"
    }
)
```

**Response:**
```json
{
  "action": "NONE",
  "valid": true,
  "assessments": {
    "automatedReasoningPolicy": {
      "findings": [{
        "result": "VALID",
        "variables": {"tenure_months": 8},
        "appliedRules": ["MinimumTenureRule"],
        "explanation": "Statement verified..."
      }]
    }
  },
  "usage": {
    "automatedReasoningPolicyUnits": 3,
    "processingTimeMs": 245
  }
}
```

### 2. `list_guardrails`

List available AWS Bedrock Guardrails with ARC policies.

**Parameters:**
- `max_results` (integer, optional): Maximum number to return (default: 20, max: 100)

**Example:**
```python
result = await mcp_client.call_tool("list_guardrails", {"max_results": 10})
```

### 3. `get_guardrail_info`

Get detailed information about a specific guardrail.

**Parameters:**
- `guardrail_id` (string, required): Guardrail identifier
- `version` (string, optional): Version or 'DRAFT' (default: 'DRAFT')

**Example:**
```python
result = await mcp_client.call_tool(
    "get_guardrail_info",
    {"guardrail_id": "abc123xyz", "version": "1"}
)
```

### 4. `rewrite_response`

Validate an LLM response and automatically rewrite it based on ARC findings. This tool combines validation and intelligent rewriting to fix policy violations.

**Parameters:**
- `user_query` (string, required): The original user question/prompt
- `llm_response` (string, required): The LLM's response to validate and rewrite
- `guardrail_id` (string, required): Guardrail identifier (ID or ARN)
- `guardrail_version` (string, optional): Version number or 'DRAFT' (default: 'DRAFT')
- `model_id` (string, optional): Model ID for rewriting (default: 'anthropic.claude-3-5-sonnet-20241022-v2:0')
- `domain` (string, optional): Domain context like 'Healthcare', 'Finance' (default: 'General')
- `policy_definition` (string, optional): Optional policy text for additional context

**Example:**
```python
result = await mcp_client.call_tool(
    "rewrite_response",
    {
        "user_query": "What are the eligibility requirements for benefits?",
        "llm_response": "Employees can apply for benefits immediately after joining.",
        "guardrail_id": "abc123xyz",
        "guardrail_version": "1",
        "domain": "Human Resources"
    }
)
```

**Response:**
```json
{
  "query": "What are the eligibility requirements for benefits?",
  "original_response": "Employees can apply for benefits immediately after joining.",
  "rewritten_response": "Employees are eligible for benefits after completing 6 months of continuous employment, as required by company policy.",
  "rewritten": true,
  "findings": [
    {
      "result": "INVALID",
      "explanation": "Response violates minimum tenure requirement",
      "violations": ["Incorrect tenure period stated"],
      "suggestions": ["Must specify 6-month minimum requirement"]
    }
  ],
  "finding_types": ["INVALID"],
  "findings_count": 1,
  "domain": "Human Resources",
  "message": "Successfully rewrote response for INVALID"
}
```

**Finding Types Handled:**
- **INVALID**: Complete policy violations - rewrites to comply with rules
- **SATISFIABLE**: Technically correct but incomplete - enhances clarity
- **NO_DATA**: Claims without supporting data - adds appropriate qualifications
- **TRANSLATION_AMBIGUOUS**: Ambiguous statements - clarifies language
- **TOO_COMPLEX**: Overly complex questions - suggests simplification
- **VALID**: No issues found - returns original response unchanged

## Integration Examples

### Claude Desktop

Add to your Claude Desktop configuration (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "bedrock-arc-validator": {
      "type": "streamable-http",
      "url": "https://bedrock-agentcore.us-east-1.amazonaws.com/runtimes/YOUR_ENCODED_ARN/invocations?qualifier=DEFAULT",
      "headers": {
        "authorization": "Bearer YOUR_BEARER_TOKEN",
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream"
      }
    }
  }
}
```

### Python MCP Client

```python
import asyncio
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

async def validate_with_arc():
    mcp_url = "https://bedrock-agentcore.us-east-1.amazonaws.com/runtimes/YOUR_ENCODED_ARN/invocations?qualifier=DEFAULT"
    headers = {
        "authorization": f"Bearer {bearer_token}",
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream"
    }

    async with streamablehttp_client(mcp_url, headers) as (read_stream, write_stream, _):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()

            result = await session.call_tool(
                "validate_content",
                {
                    "guardrail_id": "abc123xyz",
                    "content": "Your content here",
                    "guardrail_version": "DRAFT"
                }
            )

            print(f"Valid: {result['valid']}")

asyncio.run(validate_with_arc())
```

## Project Structure

```
ARC-MCP/
├── main.py                              # MCP server entry point
├── handlers/
│   ├── __init__.py
│   ├── validation.py                    # ARC validation logic
│   ├── discovery.py                     # Guardrail discovery
│   ├── rewrite_handler.py              # Response rewriting orchestration
│   ├── response_rewriter.py            # ResponseRewriter class
│   ├── rewrite_utils.py                # Finding processing utilities
│   └── template_manager.py             # Prompt template management
├── response_rewriting_prompts/          # Rewriting prompt templates
│   ├── INVALID.txt                     # Template for INVALID findings
│   ├── SATISFIABLE.txt                 # Template for SATISFIABLE findings
│   ├── NO_DATA.txt                     # Template for NO_DATA findings
│   └── TRANSLATION_AMBIGUOUS.txt       # Template for ambiguous findings
├── tests/
│   ├── __init__.py
│   ├── test_validation.py               # Validation tests
│   ├── test_discovery.py                # Discovery tests
│   ├── test_rewrite_utils.py           # Rewrite utilities tests
│   └── test_response_rewriter.py       # Response rewriter tests
├── scripts/
│   ├── deploy-infrastructure.sh         # Deploy CloudFormation
│   ├── deploy-agentcore.sh             # Deploy to AgentCore
│   ├── get-bearer-token.sh             # Get auth token
│   └── test-mcp-server.sh              # Test deployed server
├── .agentcore/
│   └── config.json                      # AgentCore configuration
├── requirements.txt                     # Python dependencies
├── cloudformation-template.yaml         # Infrastructure as Code
├── pytest.ini                          # Pytest configuration
└── README.md                           # This file
```

## Development

### Install Dependencies

```bash
pip install -r requirements.txt

# For development
pip install pytest pytest-asyncio
```

### Run Tests

```bash
# Unit tests
pytest

# Specific test file
pytest tests/test_validation.py

# With coverage
pytest --cov=handlers
```

### Local Development

```bash
# Run server locally
python main.py

# Or with agentcore CLI
agentcore launch --local
```

## Configuration

### Environment Variables

- `AWS_REGION`: AWS region (default: us-east-1)
- `EXECUTION_ROLE_ARN`: IAM execution role ARN
- `COGNITO_USER_POOL_ID`: Cognito User Pool ID
- `COGNITO_CLIENT_ID`: Cognito Client ID
- `BEARER_TOKEN`: OAuth Bearer token for authentication

### AgentCore Configuration

Edit `.agentcore/config.json` to customize:
- Runtime settings
- Execution role
- OAuth authorizer
- Environment variables

## Security

### Authentication Flow

1. Client authenticates with Cognito
2. Cognito returns JWT token (IdToken)
3. Client includes token in Authorization header
4. AgentCore validates JWT
5. MCP server uses IAM execution role for AWS API calls

### Best Practices

- Never hardcode AWS credentials
- Use IAM execution roles
- Rotate Cognito tokens regularly
- Follow principle of least privilege for IAM permissions
- Monitor CloudWatch logs for suspicious activity

## Monitoring

### CloudWatch Metrics

The server emits metrics to CloudWatch:
- `InvocationCount`: Total MCP tool invocations
- `InvocationErrors`: Failed tool invocations
- `InvocationDuration`: Tool execution time

### Logs

View logs in CloudWatch:
```bash
aws logs tail /aws/bedrock-agentcore/arc-mcp-server --follow
```

### Cost Tracking

ARC pricing: $0.17 per 1,000 text units (1 text unit = up to 1,000 characters)

Monitor usage via CloudWatch metrics or check the `usage` field in validation responses.

## Troubleshooting

### Common Issues

**"ResourceNotFoundException: Guardrail not found"**
- Verify guardrail ID is correct
- Ensure IAM role has access to the guardrail
- Check that guardrail has ARC policies configured

**"AccessDeniedException"**
- Verify IAM execution role has required permissions
- Check CloudFormation stack deployed successfully
- Review IAM policy in `cloudformation-template.yaml`

**"Token expired"**
- Cognito tokens expire after 60 minutes
- Run `./scripts/get-bearer-token.sh` to get a new token

**"Agent not found"**
- Ensure AgentCore deployment completed successfully
- Run `agentcore status --agent arc-mcp-server` to check status

### Debug Mode

Enable debug logging in `main.py`:
```python
logging.basicConfig(level=logging.DEBUG)
boto3.set_stream_logger('', logging.DEBUG)
```

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature-name`
3. Make your changes
4. Run tests: `pytest`
5. Commit: `git commit -am 'Add feature'`
6. Push: `git push origin feature-name`
7. Create a Pull Request

## License

See [LICENSE](LICENSE) file for details.

## Resources

- [AWS Bedrock ARC Documentation](https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails-automated-reasoning-checks.html)
- [Model Context Protocol Specification](https://spec.modelcontextprotocol.io/)
- [Amazon Bedrock AgentCore Documentation](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/)
- [FastMCP Framework](https://github.com/modelcontextprotocol/python-sdk)

## Support

For issues, questions, or contributions:
- Open an issue on GitHub
- Check the [design document](ARC_MCP_Server_Requirements_and_Design.md) for detailed specifications
- Review AWS Bedrock documentation

## Acknowledgments

Built with:
- [FastMCP](https://github.com/modelcontextprotocol/python-sdk) - MCP server framework
- [Boto3](https://boto3.amazonaws.com/) - AWS SDK for Python
- [AWS Bedrock](https://aws.amazon.com/bedrock/) - Foundation model service
- [Amazon Bedrock AgentCore](https://aws.amazon.com/bedrock/) - Agent runtime platform

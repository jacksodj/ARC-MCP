#!/bin/bash
# Deploy AWS Infrastructure for ARC MCP Server using CloudFormation

set -e

# Configuration
STACK_NAME="${STACK_NAME:-arc-mcp-server-infrastructure}"
REGION="${AWS_REGION:-us-east-1}"
PROJECT_NAME="${PROJECT_NAME:-arc-mcp-server}"
TEST_USER="${TEST_USER:-testuser}"
TEST_PASSWORD="${TEST_PASSWORD:-TempPassword123!}"

echo "========================================"
echo "ARC MCP Server - Infrastructure Deployment"
echo "========================================"
echo "Stack Name: $STACK_NAME"
echo "Region: $REGION"
echo "Project Name: $PROJECT_NAME"
echo "========================================"
echo

# Check if AWS CLI is installed
if ! command -v aws &> /dev/null; then
    echo "Error: AWS CLI is not installed. Please install it first."
    exit 1
fi

# Check AWS credentials
echo "Checking AWS credentials..."
if ! aws sts get-caller-identity &> /dev/null; then
    echo "Error: AWS credentials not configured. Please run 'aws configure' first."
    exit 1
fi

ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
echo "AWS Account ID: $ACCOUNT_ID"
echo

# Deploy CloudFormation stack
echo "Deploying CloudFormation stack..."
aws cloudformation deploy \
    --template-file cloudformation-template.yaml \
    --stack-name "$STACK_NAME" \
    --parameter-overrides \
        ProjectName="$PROJECT_NAME" \
        TestUserName="$TEST_USER" \
        TestUserPassword="$TEST_PASSWORD" \
    --capabilities CAPABILITY_NAMED_IAM \
    --region "$REGION"

echo
echo "CloudFormation stack deployed successfully!"
echo

# Get stack outputs
echo "Retrieving stack outputs..."
EXECUTION_ROLE_ARN=$(aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --region "$REGION" \
    --query "Stacks[0].Outputs[?OutputKey=='ExecutionRoleArn'].OutputValue" \
    --output text)

USER_POOL_ID=$(aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --region "$REGION" \
    --query "Stacks[0].Outputs[?OutputKey=='UserPoolId'].OutputValue" \
    --output text)

CLIENT_ID=$(aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --region "$REGION" \
    --query "Stacks[0].Outputs[?OutputKey=='UserPoolClientId'].OutputValue" \
    --output text)

DISCOVERY_URL=$(aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --region "$REGION" \
    --query "Stacks[0].Outputs[?OutputKey=='AuthDiscoveryUrl'].OutputValue" \
    --output text)

echo
echo "========================================"
echo "Deployment Complete!"
echo "========================================"
echo "Execution Role ARN: $EXECUTION_ROLE_ARN"
echo "User Pool ID: $USER_POOL_ID"
echo "Client ID: $CLIENT_ID"
echo "Discovery URL: $DISCOVERY_URL"
echo "========================================"
echo

# Update .agentcore/config.json with real values
echo "Updating .agentcore/config.json with deployment values..."
cat > .agentcore/config.json <<EOF
{
  "name": "$PROJECT_NAME",
  "entrypoint": "main.py",
  "protocol": "MCP",
  "runtime": {
    "python_version": "3.11"
  },
  "execution_role": "$EXECUTION_ROLE_ARN",
  "authorizer": {
    "type": "customJWTAuthorizer",
    "discoveryUrl": "$DISCOVERY_URL",
    "allowedClients": ["$CLIENT_ID"]
  },
  "environment": {
    "AWS_REGION": "$REGION"
  }
}
EOF

echo "Configuration updated successfully!"
echo

# Save deployment info
cat > deployment-info.txt <<EOF
ARC MCP Server - Deployment Information
========================================
Stack Name: $STACK_NAME
Region: $REGION
Account ID: $ACCOUNT_ID
Deployment Date: $(date)

AWS Resources
-------------
Execution Role ARN: $EXECUTION_ROLE_ARN
User Pool ID: $USER_POOL_ID
Client ID: $CLIENT_ID
Discovery URL: $DISCOVERY_URL

Test User Credentials
---------------------
Username: $TEST_USER
Password: $TEST_PASSWORD

Next Steps
----------
1. Deploy the MCP server to AgentCore:
   ./scripts/deploy-agentcore.sh

2. Get a Bearer token for testing:
   ./scripts/get-bearer-token.sh

3. Test the deployed server:
   See README.md for testing instructions
EOF

echo "Deployment information saved to: deployment-info.txt"
echo
echo "Next step: Run ./scripts/deploy-agentcore.sh to deploy the MCP server"

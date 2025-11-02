#!/bin/bash
# Deploy AWS Infrastructure for ARC MCP Server using CloudFormation

set -e

# Configuration
STACK_NAME="${STACK_NAME:-arc-mcp-server-infrastructure}"
REGION="${AWS_REGION:-us-east-1}"
PROJECT_NAME="${PROJECT_NAME:-arc-mcp-server}"

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

# Interactive prompts for Cognito User Pool
echo "========================================"
echo "Cognito User Pool Configuration"
echo "========================================"
echo
read -p "Do you want to create a NEW Cognito User Pool? (y/n) [y]: " CREATE_NEW_POOL
CREATE_NEW_POOL=${CREATE_NEW_POOL:-y}

if [[ "$CREATE_NEW_POOL" =~ ^[Nn]$ ]]; then
    USE_EXISTING_POOL="true"
    echo
    echo "To find your existing User Pool ID:"
    echo "  aws cognito-idp list-user-pools --max-results 20 --region $REGION"
    echo
    read -p "Enter existing Cognito User Pool ID: " EXISTING_POOL_ID

    # Validate the pool exists
    if ! aws cognito-idp describe-user-pool --user-pool-id "$EXISTING_POOL_ID" --region "$REGION" &> /dev/null; then
        echo "Error: User Pool '$EXISTING_POOL_ID' not found in region $REGION"
        exit 1
    fi
    echo "✓ User Pool verified"
else
    USE_EXISTING_POOL="false"
    EXISTING_POOL_ID=""
    echo "Will create a new Cognito User Pool"
fi

echo
echo "========================================"
echo "Test User Configuration"
echo "========================================"
echo
read -p "Do you want to create a test user in the User Pool? (y/n) [n]: " CREATE_USER
CREATE_USER=${CREATE_USER:-n}

if [[ "$CREATE_USER" =~ ^[Yy]$ ]]; then
    CREATE_TEST_USER="true"
    echo
    read -p "Enter test username [testuser]: " TEST_USER
    TEST_USER=${TEST_USER:-testuser}

    # Prompt for password with confirmation
    while true; do
        read -s -p "Enter test user password (min 8 chars, must include uppercase, lowercase, number, symbol): " TEST_PASSWORD
        echo
        read -s -p "Confirm password: " TEST_PASSWORD_CONFIRM
        echo

        if [ "$TEST_PASSWORD" = "$TEST_PASSWORD_CONFIRM" ]; then
            # Validate password meets requirements
            if [[ ${#TEST_PASSWORD} -lt 8 ]]; then
                echo "Error: Password must be at least 8 characters"
                continue
            fi
            break
        else
            echo "Error: Passwords do not match. Please try again."
        fi
    done
else
    CREATE_TEST_USER="false"
    TEST_USER="testuser"
    TEST_PASSWORD="TempPassword123!"
    echo "Skipping test user creation"
fi

echo
echo "========================================"
echo "Deployment Summary"
echo "========================================"
echo "Use Existing Pool: $USE_EXISTING_POOL"
if [ "$USE_EXISTING_POOL" = "true" ]; then
    echo "Existing Pool ID: $EXISTING_POOL_ID"
fi
echo "Create Test User: $CREATE_TEST_USER"
if [ "$CREATE_TEST_USER" = "true" ]; then
    echo "Test Username: $TEST_USER"
fi
echo "========================================"
echo
read -p "Proceed with deployment? (y/n) [y]: " CONFIRM
CONFIRM=${CONFIRM:-y}

if [[ ! "$CONFIRM" =~ ^[Yy]$ ]]; then
    echo "Deployment cancelled"
    exit 0
fi

# Deploy CloudFormation stack
echo
echo "Deploying CloudFormation stack..."
aws cloudformation deploy \
    --template-file cloudformation-template.yaml \
    --stack-name "$STACK_NAME" \
    --parameter-overrides \
        ProjectName="$PROJECT_NAME" \
        UseExistingUserPool="$USE_EXISTING_POOL" \
        ExistingUserPoolId="$EXISTING_POOL_ID" \
        CreateTestUser="$CREATE_TEST_USER" \
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
{
cat <<EOF
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

Configuration
-------------
Using Existing User Pool: $USE_EXISTING_POOL
EOF

if [ "$CREATE_TEST_USER" = "true" ]; then
cat <<EOF
Test User Created: Yes

Test User Credentials
---------------------
Username: $TEST_USER
Password: $TEST_PASSWORD
EOF
else
cat <<EOF
Test User Created: No
Note: You need to create a user in the Cognito User Pool manually or use existing users.
EOF
fi

cat <<EOF

Next Steps
----------
1. Deploy the MCP server to AgentCore:
   ./scripts/deploy-agentcore.sh

EOF

if [ "$CREATE_TEST_USER" = "true" ]; then
cat <<EOF
2. Get a Bearer token for testing:
   ./scripts/get-bearer-token.sh

3. Test the deployed server:
   See README.md for testing instructions
EOF
else
cat <<EOF
2. Create a user in the Cognito User Pool (if not done already):
   aws cognito-idp admin-create-user \\
     --user-pool-id $USER_POOL_ID \\
     --username <username> \\
     --user-attributes Name=email,Value=<email> Name=email_verified,Value=true \\
     --message-action SUPPRESS \\
     --region $REGION

   aws cognito-idp admin-set-user-password \\
     --user-pool-id $USER_POOL_ID \\
     --username <username> \\
     --password <password> \\
     --permanent \\
     --region $REGION

3. Get a Bearer token for authentication:
   ./scripts/get-bearer-token.sh

4. Test the deployed server:
   See README.md for testing instructions
EOF
fi
} > deployment-info.txt

echo "Deployment information saved to: deployment-info.txt"
echo
if [ "$CREATE_TEST_USER" = "true" ]; then
    echo "Next step: Run ./scripts/deploy-agentcore.sh to deploy the MCP server"
else
    echo "Next step: Create a user in the Cognito User Pool, then run ./scripts/deploy-agentcore.sh"
fi

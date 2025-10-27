#!/bin/bash
# Get Bearer Token from Cognito for MCP Server Authentication

set -e

REGION="${AWS_REGION:-us-east-1}"
STACK_NAME="${STACK_NAME:-arc-mcp-server-infrastructure}"

echo "========================================"
echo "ARC MCP Server - Get Bearer Token"
echo "========================================"
echo

# Check if deployment-info.txt exists
if [ -f "deployment-info.txt" ]; then
    echo "Reading deployment information..."
    CLIENT_ID=$(grep "Client ID:" deployment-info.txt | cut -d' ' -f3)
    TEST_USER=$(grep "Username:" deployment-info.txt | cut -d' ' -f2)
    TEST_PASSWORD=$(grep "Password:" deployment-info.txt | cut -d' ' -f2)
else
    echo "deployment-info.txt not found. Fetching from CloudFormation..."

    CLIENT_ID=$(aws cloudformation describe-stacks \
        --stack-name "$STACK_NAME" \
        --region "$REGION" \
        --query "Stacks[0].Outputs[?OutputKey=='UserPoolClientId'].OutputValue" \
        --output text)

    TEST_USER="${TEST_USER:-testuser}"

    # Prompt for password if not in environment
    if [ -z "$TEST_PASSWORD" ]; then
        read -sp "Enter password for user $TEST_USER: " TEST_PASSWORD
        echo
    fi
fi

echo "Client ID: $CLIENT_ID"
echo "Username: $TEST_USER"
echo

# Authenticate and get token
echo "Authenticating with Cognito..."
TOKEN_RESPONSE=$(aws cognito-idp initiate-auth \
    --auth-flow USER_PASSWORD_AUTH \
    --client-id "$CLIENT_ID" \
    --auth-parameters USERNAME="$TEST_USER",PASSWORD="$TEST_PASSWORD" \
    --region "$REGION" \
    2>&1)

if [ $? -ne 0 ]; then
    echo "Error: Authentication failed"
    echo "$TOKEN_RESPONSE"
    exit 1
fi

# Extract tokens
ID_TOKEN=$(echo "$TOKEN_RESPONSE" | jq -r '.AuthenticationResult.IdToken')
ACCESS_TOKEN=$(echo "$TOKEN_RESPONSE" | jq -r '.AuthenticationResult.AccessToken')
REFRESH_TOKEN=$(echo "$TOKEN_RESPONSE" | jq -r '.AuthenticationResult.RefreshToken')
EXPIRES_IN=$(echo "$TOKEN_RESPONSE" | jq -r '.AuthenticationResult.ExpiresIn')

echo "========================================"
echo "Authentication Successful!"
echo "========================================"
echo
echo "ID Token (use as Bearer token):"
echo "$ID_TOKEN"
echo
echo "Access Token:"
echo "$ACCESS_TOKEN"
echo
echo "Token expires in: $EXPIRES_IN seconds"
echo

# Save to file
cat > bearer-token.txt <<EOF
ARC MCP Server - Bearer Token
==============================
Generated: $(date)
Expires in: $EXPIRES_IN seconds

ID Token (use this for Bearer authentication):
$ID_TOKEN

Access Token:
$ACCESS_TOKEN

Refresh Token:
$REFRESH_TOKEN

Usage:
------
Export as environment variable:
  export BEARER_TOKEN="$ID_TOKEN"

Use in HTTP header:
  Authorization: Bearer $ID_TOKEN
EOF

echo "Token saved to: bearer-token.txt"
echo
echo "To use the token:"
echo "  export BEARER_TOKEN=\"$ID_TOKEN\""
echo
echo "To decode token (without verification):"
echo "  echo \"$ID_TOKEN\" | cut -d'.' -f2 | base64 -d | jq ."

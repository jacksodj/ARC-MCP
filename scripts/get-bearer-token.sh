#!/bin/bash
# Get Cognito bearer token for MCP server authentication
#
# Usage:
#   ./scripts/get-bearer-token.sh > /tmp/bearer_token.txt
#   export BEARER_TOKEN=$(./scripts/get-bearer-token.sh)

# Load configuration from .env if it exists
if [ -f .env ]; then
    source .env
fi

# Default values (override in .env)
CLIENT_ID=${COGNITO_CLIENT_ID:-"YOUR_CLIENT_ID"}
USERNAME=${COGNITO_TEST_USER_EMAIL:-"user@example.com"}
PASSWORD=${COGNITO_TEST_USER_PASSWORD:-"YourPassword123!"}
REGION=${AWS_REGION:-"us-east-1"}

# Get bearer token
aws cognito-idp initiate-auth \
  --auth-flow USER_PASSWORD_AUTH \
  --client-id "$CLIENT_ID" \
  --auth-parameters USERNAME="$USERNAME",PASSWORD="$PASSWORD" \
  --region "$REGION" \
  --query 'AuthenticationResult.IdToken' \
  --output text

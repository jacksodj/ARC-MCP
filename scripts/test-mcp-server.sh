#!/bin/bash
# Test the deployed MCP Server

set -e

REGION="${AWS_REGION:-us-east-1}"
PROJECT_NAME="${PROJECT_NAME:-arc-mcp-server}"

echo "========================================"
echo "ARC MCP Server - Testing"
echo "========================================"
echo

# Check if bearer token is available
if [ -z "$BEARER_TOKEN" ]; then
    if [ -f "bearer-token.txt" ]; then
        echo "Loading bearer token from file..."
        BEARER_TOKEN=$(grep "ID Token (use this for Bearer authentication):" bearer-token.txt -A 1 | tail -n 1)
    else
        echo "Error: BEARER_TOKEN not set and bearer-token.txt not found."
        echo "Please run ./scripts/get-bearer-token.sh first, or:"
        echo "  export BEARER_TOKEN=<your-token>"
        exit 1
    fi
fi

# Get Agent ARN
echo "Getting Agent ARN..."
AGENT_INFO=$(agentcore status --agent "$PROJECT_NAME" 2>&1 || true)

if echo "$AGENT_INFO" | grep -q "Agent not found"; then
    echo "Error: Agent not deployed. Please run ./scripts/deploy-agentcore.sh first."
    exit 1
fi

# Extract ARN from output (this may need adjustment based on actual CLI output format)
AGENT_ARN=$(echo "$AGENT_INFO" | grep -o "arn:aws:bedrock-agentcore:.*" | head -n 1)

if [ -z "$AGENT_ARN" ]; then
    echo "Warning: Could not automatically extract Agent ARN."
    read -p "Please enter the Agent ARN: " AGENT_ARN
fi

echo "Agent ARN: $AGENT_ARN"

# URL-encode the ARN
ENCODED_ARN=$(echo "$AGENT_ARN" | sed 's/:/%3A/g' | sed 's/\//%2F/g')

# Construct MCP endpoint URL
MCP_URL="https://bedrock-agentcore.${REGION}.amazonaws.com/runtimes/${ENCODED_ARN}/invocations?qualifier=DEFAULT"

echo "MCP URL: $MCP_URL"
echo

# Test 1: List tools
echo "Test 1: Listing available MCP tools..."
curl -X POST "$MCP_URL" \
    -H "Authorization: Bearer $BEARER_TOKEN" \
    -H "Content-Type: application/json" \
    -H "Accept: application/json, text/event-stream" \
    -d '{
        "method": "tools/list",
        "params": {}
    }' \
    -s | jq '.'

echo
echo "========================================"
echo

# Test 2: List guardrails
echo "Test 2: Listing guardrails with ARC policies..."
curl -X POST "$MCP_URL" \
    -H "Authorization: Bearer $BEARER_TOKEN" \
    -H "Content-Type: application/json" \
    -H "Accept: application/json, text/event-stream" \
    -d '{
        "method": "tools/call",
        "params": {
            "name": "list_guardrails",
            "arguments": {
                "max_results": 10
            }
        }
    }' \
    -s | jq '.'

echo
echo "========================================"
echo

# Prompt for guardrail ID for validation test
read -p "Do you want to test content validation? (requires a guardrail ID) (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    read -p "Enter Guardrail ID: " GUARDRAIL_ID
    read -p "Enter content to validate: " CONTENT

    echo
    echo "Test 3: Validating content against guardrail..."
    curl -X POST "$MCP_URL" \
        -H "Authorization: Bearer $BEARER_TOKEN" \
        -H "Content-Type: application/json" \
        -H "Accept: application/json, text/event-stream" \
        -d "{
            \"method\": \"tools/call\",
            \"params\": {
                \"name\": \"validate_content\",
                \"arguments\": {
                    \"guardrail_id\": \"$GUARDRAIL_ID\",
                    \"content\": \"$CONTENT\",
                    \"guardrail_version\": \"DRAFT\",
                    \"source\": \"OUTPUT\"
                }
            }
        }" \
        -s | jq '.'
fi

echo
echo "========================================"
echo "Testing Complete!"
echo "========================================"

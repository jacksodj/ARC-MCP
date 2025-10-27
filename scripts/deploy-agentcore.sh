#!/bin/bash
# Deploy MCP Server to Amazon Bedrock AgentCore

set -e

REGION="${AWS_REGION:-us-east-1}"
PROJECT_NAME="${PROJECT_NAME:-arc-mcp-server}"

echo "========================================"
echo "ARC MCP Server - AgentCore Deployment"
echo "========================================"
echo "Project Name: $PROJECT_NAME"
echo "Region: $REGION"
echo "========================================"
echo

# Check if agentcore CLI is installed
if ! command -v agentcore &> /dev/null; then
    echo "Error: agentcore CLI is not installed."
    echo
    echo "Installation instructions:"
    echo "  pip install bedrock-agentcore-starter-toolkit"
    echo "  or"
    echo "  uv pip install bedrock-agentcore-starter-toolkit"
    echo
    exit 1
fi

# Check if .agentcore/config.json exists
if [ ! -f ".agentcore/config.json" ]; then
    echo "Error: .agentcore/config.json not found."
    echo "Please run ./scripts/deploy-infrastructure.sh first."
    exit 1
fi

echo "Configuration file found: .agentcore/config.json"
echo

# Check if requirements are installed
echo "Installing Python dependencies..."
if command -v uv &> /dev/null; then
    uv pip install -r requirements.txt
else
    pip install -r requirements.txt
fi

echo "Dependencies installed successfully!"
echo

# Test locally first (optional)
read -p "Do you want to test locally before deploying? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Starting local test server..."
    echo "Press Ctrl+C to stop and continue with deployment"
    echo
    agentcore launch --local || true
    echo
fi

# Deploy to AgentCore
echo "Deploying to Amazon Bedrock AgentCore..."
agentcore launch

echo
echo "========================================"
echo "Deployment Complete!"
echo "========================================"
echo

# Get deployment status
echo "Getting deployment status..."
agentcore status --agent "$PROJECT_NAME"

echo
echo "To get the agent ARN for client configuration:"
echo "  agentcore status --agent $PROJECT_NAME"
echo
echo "Next step: Get a Bearer token for authentication"
echo "  ./scripts/get-bearer-token.sh"

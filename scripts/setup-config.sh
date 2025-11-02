#!/bin/bash
# Setup configuration files from environment variables
#
# Usage:
#   1. Copy .env.example to .env and fill in your values
#   2. Run: ./scripts/setup-config.sh

set -e

# Check if .env exists
if [ ! -f .env ]; then
    echo "Error: .env file not found"
    echo "Please copy .env.example to .env and fill in your values:"
    echo "  cp .env.example .env"
    exit 1
fi

# Load environment variables
source .env

echo "Setting up configuration files..."

# Validate required variables
REQUIRED_VARS=(
    "AWS_ACCOUNT_ID"
    "AWS_REGION"
    "PROJECT_ROOT"
)

for var in "${REQUIRED_VARS[@]}"; do
    if [ -z "${!var}" ]; then
        echo "Error: $var is not set in .env"
        exit 1
    fi
done

# Generate .bedrock_agentcore.yaml from template
echo "Generating .bedrock_agentcore.yaml..."
sed "s|/path/to/your/project|${PROJECT_ROOT}|g; \
     s|YOUR_ACCOUNT_ID|${AWS_ACCOUNT_ID}|g; \
     s|us-east-1|${AWS_REGION}|g" \
    .bedrock_agentcore.yaml.example > .bedrock_agentcore.yaml

# Generate .agentcore/config.json from template if Cognito vars are set
if [ -n "$COGNITO_USER_POOL_ID" ] && [ -n "$COGNITO_CLIENT_ID" ]; then
    echo "Generating .agentcore/config.json..."
    mkdir -p .agentcore
    sed "s|YOUR_ACCOUNT_ID|${AWS_ACCOUNT_ID}|g; \
         s|us-east-1_XXXXXXXXX|${COGNITO_USER_POOL_ID}|g; \
         s|XXXXXXXXXXXXXXXXXXXXXXXXXX|${COGNITO_CLIENT_ID}|g" \
        .agentcore/config.json.example > .agentcore/config.json
fi

echo "✓ Configuration files generated successfully!"
echo ""
echo "Next steps:"
echo "  1. Review .bedrock_agentcore.yaml"
echo "  2. Deploy infrastructure: ./scripts/deploy-infrastructure.sh"
echo "  3. Configure AgentCore: agentcore configure ..."
echo "  4. Launch: agentcore launch"

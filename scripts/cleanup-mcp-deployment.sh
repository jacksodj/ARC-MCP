#!/bin/bash
# cleanup-mcp-deployment.sh
#
# Cleanup script for MCP server deployment on AWS Bedrock AgentCore
# This script removes all MCP-related resources while optionally keeping Cognito User Pool

set -e

# Configuration - Override these with environment variables or edit directly
AGENT_NAME="${AGENT_NAME:-arc_mcp_server}"
PROJECT_NAME="${PROJECT_NAME:-arc-mcp-server}"
REGION="${AWS_REGION:-us-east-1}"
KEEP_COGNITO="${KEEP_COGNITO:-true}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

function log_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

function log_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

function log_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

function log_error() {
    echo -e "${RED}❌ $1${NC}"
}

function confirm_cleanup() {
    echo ""
    log_warning "About to delete the following resources:"
    echo "  - AgentCore agent: $AGENT_NAME"
    echo "  - Lambda function: ${PROJECT_NAME}-add-client-id-claim"
    echo "  - Lambda IAM role"
    echo "  - ECR repository and images"
    echo "  - CloudWatch log groups"
    if [ "$KEEP_COGNITO" = "false" ]; then
        echo "  - Cognito User Pool and all users"
        echo "  - CloudFormation stack"
    else
        log_info "Cognito User Pool will be preserved (set KEEP_COGNITO=false to delete)"
    fi
    echo ""
    read -p "Are you sure you want to proceed? (yes/no): " -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy][Ee][Ss]$ ]]; then
        log_info "Cleanup cancelled"
        exit 0
    fi
}

echo "🧹 MCP Deployment Cleanup Script"
echo "================================="
echo ""
log_info "Configuration:"
echo "  Agent Name:    $AGENT_NAME"
echo "  Project Name:  $PROJECT_NAME"
echo "  Region:        $REGION"
echo "  Keep Cognito:  $KEEP_COGNITO"
echo ""

# Confirm before proceeding
if [ "${FORCE_CLEANUP:-false}" != "true" ]; then
    confirm_cleanup
fi

# Step 1: Destroy AgentCore agent
log_info "Step 1/6: Destroying AgentCore agent..."
if agentcore status --agent "$AGENT_NAME" &>/dev/null; then
    agentcore destroy --agent "$AGENT_NAME" --force --delete-ecr-repo
    log_success "AgentCore agent destroyed"
else
    log_warning "AgentCore agent not found or already deleted"
fi

# Step 2: Get User Pool ID from CloudFormation (if exists)
log_info "Step 2/6: Retrieving CloudFormation stack information..."
USER_POOL_ID=""
if aws cloudformation describe-stacks --stack-name "${PROJECT_NAME}-infrastructure" --region "$REGION" &>/dev/null; then
    USER_POOL_ID=$(aws cloudformation describe-stack-resources \
        --stack-name "${PROJECT_NAME}-infrastructure" \
        --region "$REGION" \
        --logical-resource-id ArcMcpUserPool \
        --query 'StackResources[0].PhysicalResourceId' \
        --output text 2>/dev/null || echo "")

    if [ -n "$USER_POOL_ID" ] && [ "$USER_POOL_ID" != "None" ]; then
        log_success "Found User Pool: $USER_POOL_ID"
    fi
fi

# Step 3: Remove Lambda trigger from User Pool
if [ -n "$USER_POOL_ID" ]; then
    log_info "Step 3/6: Removing Lambda trigger from User Pool..."
    if aws cognito-idp update-user-pool \
        --user-pool-id "$USER_POOL_ID" \
        --region "$REGION" \
        --lambda-config '{}' &>/dev/null; then
        log_success "Lambda trigger removed from User Pool"
    else
        log_warning "Could not remove Lambda trigger (may already be removed)"
    fi
else
    log_info "Step 3/6: Skipping Lambda trigger removal (User Pool not found)"
fi

# Step 4: Delete Lambda function
log_info "Step 4/6: Deleting Lambda function..."
LAMBDA_NAME="${PROJECT_NAME}-add-client-id-claim"
if aws lambda get-function --function-name "$LAMBDA_NAME" --region "$REGION" &>/dev/null; then
    aws lambda delete-function --function-name "$LAMBDA_NAME" --region "$REGION"
    log_success "Lambda function deleted"
else
    log_warning "Lambda function not found or already deleted"
fi

# Step 5: Delete Lambda IAM role
log_info "Step 5/6: Deleting Lambda IAM role..."
LAMBDA_ROLE="${PROJECT_NAME}-pretokengen-lambda-role"
if aws iam get-role --role-name "$LAMBDA_ROLE" &>/dev/null; then
    # Detach managed policies
    aws iam detach-role-policy \
        --role-name "$LAMBDA_ROLE" \
        --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole \
        &>/dev/null || true

    # Delete inline policies
    for policy in $(aws iam list-role-policies --role-name "$LAMBDA_ROLE" --query 'PolicyNames' --output text); do
        aws iam delete-role-policy --role-name "$LAMBDA_ROLE" --policy-name "$policy"
    done

    # Delete role
    aws iam delete-role --role-name "$LAMBDA_ROLE"
    log_success "Lambda IAM role deleted"
else
    log_warning "Lambda IAM role not found or already deleted"
fi

# Step 6: Delete CloudWatch log groups
log_info "Step 6/6: Deleting CloudWatch log groups..."

# Lambda logs
if aws logs describe-log-groups --log-group-name "/aws/lambda/${LAMBDA_NAME}" --region "$REGION" &>/dev/null; then
    aws logs delete-log-group --log-group-name "/aws/lambda/${LAMBDA_NAME}" --region "$REGION"
    log_success "Deleted Lambda log group"
fi

# MCP server logs
if aws logs describe-log-groups --log-group-name "/aws/bedrock-agentcore/${PROJECT_NAME}" --region "$REGION" &>/dev/null; then
    aws logs delete-log-group --log-group-name "/aws/bedrock-agentcore/${PROJECT_NAME}" --region "$REGION"
    log_success "Deleted MCP server log group"
fi

# Runtime logs (find all matching)
AGENT_LOG_GROUPS=$(aws logs describe-log-groups \
    --region "$REGION" \
    --log-group-name-prefix "/aws/bedrock-agentcore/runtimes/${AGENT_NAME}" \
    --query 'logGroups[].logGroupName' \
    --output text 2>/dev/null || echo "")

if [ -n "$AGENT_LOG_GROUPS" ]; then
    for log_group in $AGENT_LOG_GROUPS; do
        aws logs delete-log-group --log-group-name "$log_group" --region "$REGION"
        log_success "Deleted runtime log group: $(basename "$log_group")"
    done
else
    log_warning "No runtime log groups found"
fi

# Optional: Delete CloudFormation stack
if [ "$KEEP_COGNITO" = "false" ]; then
    log_info "Deleting CloudFormation stack..."
    if aws cloudformation describe-stacks --stack-name "${PROJECT_NAME}-infrastructure" --region "$REGION" &>/dev/null; then
        aws cloudformation delete-stack --stack-name "${PROJECT_NAME}-infrastructure" --region "$REGION"
        log_success "CloudFormation stack deletion initiated"
        log_info "Waiting for stack deletion to complete..."
        aws cloudformation wait stack-delete-complete --stack-name "${PROJECT_NAME}-infrastructure" --region "$REGION" || true
        log_success "CloudFormation stack deleted"
    else
        log_warning "CloudFormation stack not found"
    fi
fi

echo ""
echo "========================================"
log_success "Cleanup complete!"
echo ""

if [ "$KEEP_COGNITO" = "true" ]; then
    log_info "Preserved resources:"
    if [ -n "$USER_POOL_ID" ]; then
        echo "  - Cognito User Pool: $USER_POOL_ID"
        echo "  - CloudFormation stack: ${PROJECT_NAME}-infrastructure (in drifted state)"
        echo ""
        log_warning "The CloudFormation stack is now in a 'drifted' state"
        log_info "To delete the stack and Cognito resources, run with: KEEP_COGNITO=false"
    fi
else
    log_info "All resources have been deleted"
fi

echo ""
log_info "Verification commands:"
echo "  agentcore configure list           # Should show no agents"
echo "  aws lambda list-functions --region $REGION | grep $PROJECT_NAME"
echo "  aws ecr describe-repositories --region $REGION | grep $AGENT_NAME"

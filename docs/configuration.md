# Configuration Guide

This project uses template files with environment variables to manage sensitive configuration data.

## Quick Start

1. **Copy the environment template**:
   ```bash
   cp .env.example .env
   ```

2. **Edit `.env` with your actual values**:
   ```bash
   # Edit the file and replace placeholder values
   vim .env  # or use your preferred editor
   ```

3. **Generate configuration files**:
   ```bash
   ./scripts/setup-config.sh
   ```

This will create:
- `.bedrock_agentcore.yaml` - AgentCore configuration
- `.agentcore/config.json` - Legacy AgentCore config (if Cognito vars are set)

## Configuration Files

### Template Files (Committed to Git)

These files contain placeholder values and are safe to commit:

- **`.env.example`** - Environment variable template
- **`.bedrock_agentcore.yaml.example`** - AgentCore config template
- **`.agentcore/config.json.example`** - Legacy config template

### Actual Files (NOT Committed)

These files contain your actual credentials and are ignored by git:

- **`.env`** - Your actual environment variables
- **`.bedrock_agentcore.yaml`** - Generated AgentCore config
- **`.agentcore/config.json`** - Generated legacy config

## Environment Variables

### Required Variables

- `AWS_ACCOUNT_ID` - Your AWS account ID (12 digits)
- `AWS_REGION` - AWS region (e.g., `us-east-1`)
- `PROJECT_ROOT` - Absolute path to your project directory

### Optional Variables (for Cognito)

- `COGNITO_USER_POOL_ID` - Cognito User Pool ID (e.g., `us-east-1_XXXXXXXXX`)
- `COGNITO_CLIENT_ID` - Cognito App Client ID
- `COGNITO_TEST_USER_EMAIL` - Test user email
- `COGNITO_TEST_USER_PASSWORD` - Test user password

### AgentCore Variables

- `AGENTCORE_AGENT_NAME` - Name of your agent (default: `arc_mcp_server`)
- `AGENTCORE_EXECUTION_ROLE_NAME` - IAM role name (default: `arc-mcp-server-execution-role`)
- `AGENTCORE_PROJECT_NAME` - Project name (default: `arc-mcp-server`)

## Security Notes

⚠️ **IMPORTANT**: Never commit files containing actual credentials!

The following files are automatically ignored by git:
- `.env`
- `.env.local`
- `.bedrock_agentcore.yaml`
- `.agentcore/config.json`
- `.dockerignore`

## Manual Configuration

If you prefer to configure manually instead of using the setup script:

1. **Copy template files**:
   ```bash
   cp .bedrock_agentcore.yaml.example .bedrock_agentcore.yaml
   cp .agentcore/config.json.example .agentcore/config.json
   ```

2. **Edit files** and replace all placeholder values:
   - `YOUR_ACCOUNT_ID` → Your AWS account ID
   - `us-east-1_XXXXXXXXX` → Your Cognito User Pool ID
   - `XXXXXXXXXXXXXXXXXXXXXXXXXX` → Your Cognito Client ID
   - `/path/to/your/project` → Your actual project path
   - `RANDOM_ID` → Generated IDs (these will be filled by AgentCore after deployment)

## After Configuration

Once your configuration files are set up:

1. **Deploy infrastructure**:
   ```bash
   ./scripts/deploy-infrastructure.sh
   ```

2. **Configure AgentCore** (if not using the config files):
   ```bash
   agentcore configure \
     --entrypoint main.py \
     --name arc_mcp_server \
     --execution-role arn:aws:iam::YOUR_ACCOUNT_ID:role/arc-mcp-server-execution-role \
     --protocol MCP \
     --region us-east-1 \
     --non-interactive
   ```

3. **Launch the agent**:
   ```bash
   agentcore launch
   ```

## Troubleshooting

### "Error: .env file not found"
Run `cp .env.example .env` to create the file, then edit it with your values.

### "Error: AWS_ACCOUNT_ID is not set in .env"
Open `.env` and ensure all required variables are set (not using placeholder values).

### Permission Denied on setup-config.sh
Make the script executable: `chmod +x scripts/setup-config.sh`

## See Also

- [Deployment Guide](agentcore-mcp-deployment-guide.md) - Complete deployment instructions
- [README.md](../README.md) - Project overview

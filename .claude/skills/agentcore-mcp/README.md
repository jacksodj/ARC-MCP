# AgentCore MCP Skill

This skill provides comprehensive guidance for building, deploying, securing, and testing MCP (Model Context Protocol) servers on AWS Bedrock AgentCore.

## Skill Structure

### Core Files
- **SKILL.md** (416 lines) - Main skill instructions with step-by-step guidance
- **reference.md** (421 lines) - Complete API references, CLI commands, error codes
- **examples.md** (661 lines) - Working code examples and patterns

**Total: 1,498 lines of comprehensive documentation**

## What This Skill Covers

### Critical Requirements
1. **Transport Configuration**: Mandatory `streamable-http` with `stateless_http=True`
2. **Invocation Method**: Must use MCP Python client (not boto3)
3. **Authentication**: OAuth with Lambda-injected `client_id` claim

### Complete Workflows
- Infrastructure setup with CloudFormation
- Pre-Token Generation Lambda for OAuth compatibility
- AgentCore deployment and configuration
- Token management and testing
- Troubleshooting 406/403 errors

### Code Examples
- Simple MCP server
- AWS-integrated MCP server
- Complete client invocation
- CloudFormation templates
- Token management classes
- Error handling patterns
- Testing scripts

## When Claude Will Use This Skill

Claude will automatically invoke this skill when you:
- Ask about MCP server development or deployment
- Mention AgentCore, Bedrock, or Model Context Protocol
- Debug 406 or 403 errors with MCP servers
- Set up OAuth authentication for MCP
- Need CloudFormation templates for MCP infrastructure
- Ask about testing MCP server invocations

## Key Learnings Captured

This skill encapsulates all the critical learnings from our successful deployment:

✅ **Transport Requirements**
- Must use `streamable-http` (not `http`)
- Requires `stateless_http=True` parameter
- Host must be `0.0.0.0` (not `127.0.0.1`)

✅ **Invocation Patterns**
- Cannot use boto3 `invoke_agent_runtime`
- Must use MCP Python client library
- Requires proper session initialization

✅ **OAuth Solution**
- Standard Cognito JWTs lack `client_id` claim
- Pre-Token Generation Lambda injects the claim
- Complete CloudFormation implementation included

✅ **Testing & Debugging**
- How to get and verify bearer tokens
- CloudWatch log interpretation
- Common error codes and solutions

## Usage

This is a **project-level skill** located in `.claude/skills/agentcore-mcp/`.

Claude will automatically discover and use it when relevant to your questions or tasks. You don't need to explicitly invoke it.

### To test the skill:
1. Ask Claude about MCP server deployment
2. Request help debugging 406 errors
3. Ask for OAuth configuration guidance
4. Request CloudFormation templates

## Related Documentation

- `docs/agentcore-mcp-deployment-guide.md` - Complete deployment guide
- `docs/solution-summary.md` - Technical analysis
- `docs/SUCCESS-oauth-mcp-working.md` - Working implementation
- `scripts/test-mcp-invocation.py` - Test script
- `scripts/get-bearer-token.sh` - Token helper

## Maintenance

Update this skill when:
- AWS releases new AgentCore features
- MCP protocol versions change
- New authentication methods become available
- Common issues/patterns are discovered

---

**Created**: November 1, 2025
**Last Updated**: November 1, 2025
**Status**: Production-ready ✅

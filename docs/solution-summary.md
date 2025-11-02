# Solution Summary: MCP Server End-to-End Invocation

**Date**: November 1, 2025
**Status**: ✅ ROOT CAUSE IDENTIFIED → 🚧 AUTHENTICATION IMPLEMENTATION NEEDED

## What We Discovered

### 1. Transport Configuration (✅ FIXED)
**Problem**: We were using `transport="http"` which caused 406 errors
**Solution**: AWS requires `transport="streamable-http"` with `stateless_http=True`
```python
# main.py:151
mcp.run(transport="streamable-http", stateless_http=True, host="0.0.0.0")
```
**Verification**: Server starts successfully, processes PingRequests, logs show "StreamableHTTP session manager started"

### 2. Invocation Method (✅ IDENTIFIED)
**Problem**: Using `boto3.client('bedrock-agentcore').invoke_agent_runtime()` with raw JSON-RPC gives 406 errors
**Root Cause**: AgentCore's `invoke_agent_runtime` API is not designed for direct MCP JSON-RPC calls
**Solution**: Must use the **MCP Python client library**

**Correct invocation pattern** (from AWS docs):
```python
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

async with streamablehttp_client(mcp_url, headers, timeout=120) as (read, write, _):
    async with ClientSession(read, write) as session:
        await session.initialize()  # Required MCP handshake
        tools = await session.list_tools()  # Now we can call methods
```

### 3. Authentication (🚧 BLOCKED - Next Step)
**Problem**: MCP client without authentication returns `403 Forbidden`
**Current State**: OAuth disabled (`authorizer_configuration: null`) to use SigV4
**Issue**: MCP client library doesn't automatically add SigV4 signatures

**Two Paths Forward**:

#### Path A: OAuth + Lambda (RECOMMENDED - User's Preference)
1. Create Cognito Pre-Token Generation Lambda to inject `client_id` claim
2. Update CloudFormation to add Lambda resources and trigger
3. Re-enable OAuth in `.bedrock_agentcore.yaml`
4. Get bearer token from Cognito
5. Use bearer token with MCP client: `headers = {"authorization": f"Bearer {token}"}`

#### Path B: Custom SigV4 Integration
1. Wrap MCP client's HTTP calls with AWS SigV4 request signer
2. More complex, requires understanding MCP client internals

## CloudWatch Logs Evidence

**Server is working**:
```
✓ FastMCP 2.13.0.2
✓ Transport: streamable-http on http://0.0.0.0:8000/mcp
✓ INFO: Uvicorn running on http://0.0.0.0:8000
✓ INFO: Processing request of type PingRequest
✓ INFO: "POST /mcp HTTP/1.1" 200 OK
```

**But our `tools/list` requests never reach the server** → They're being blocked at AgentCore proxy layer due to auth

## Test Results

| Method | Transport | Auth | Result | Meaning |
|--------|-----------|------|--------|---------|
| boto3 invoke_agent_runtime | http | SigV4 | 406 | Wrong transport |
| boto3 invoke_agent_runtime | streamable-http | SigV4 | 406 | Wrong invocation method |
| agentcore invoke CLI | streamable-http | SigV4 | 406 | CLI not designed for MCP |
| MCP client | streamable-http | None | 403 | Need authentication |
| MCP client | streamable-http | OAuth | **TBD** | Next test after Lambda |

## Next Actions

### Immediate (to unblock):
1. Add Pre-Token Generation Lambda to CloudFormation
2. Deploy updated stack
3. Update `.bedrock_agentcore.yaml` to re-enable OAuth
4. Get fresh bearer token with `client_id` claim
5. Test MCP client invocation with bearer token

### Testing Script
```python
# test_mcp_with_oauth.py
import asyncio
import os
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

async def test_mcp():
    agent_arn = "arn:aws:bedrock-agentcore:us-east-1:ACCOUNT_ID:runtime/arc_mcp_server-RANDOM_ID"
    bearer_token = os.getenv('BEARER_TOKEN')  # From Cognito

    encoded_arn = agent_arn.replace(':', '%3A').replace('/', '%2F')
    url = f"https://bedrock-agentcore.us-east-1.amazonaws.com/runtimes/{encoded_arn}/invocations?qualifier=DEFAULT"
    headers = {
        "authorization": f"Bearer {bearer_token}",
        "Content-Type": "application/json"
    }

    async with streamablehttp_client(url, headers, timeout=120) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            print(f"✅ SUCCESS! Tools: {tools}")

asyncio.run(test_mcp())
```

## Success Criteria
- [ ] Get bearer token with `client_id` claim present
- [ ] MCP client connects without 403 error
- [ ] `session.initialize()` completes
- [ ] `session.list_tools()` returns our 4 tools
- [ ] Can call `validate_content` tool with test data
- [ ] Document working invocation pattern

## Files Modified
1. `main.py:151` - Fixed transport to streamable-http ✅
2. `docs/next-steps-mcp-invocation.md` - Updated with findings ✅
3. `cloudformation-template.yaml` - TODO: Add Lambda
4. `.bedrock_agentcore.yaml` - TODO: Re-enable OAuth

## Key Learnings
1. ✅ AWS docs definitively state "Stateless streamable-http only"
2. ✅ Cannot invoke MCP servers via raw boto3 API calls
3. ✅ Must use MCP client library for proper protocol handshake
4. ✅ AgentCore proxy blocks unauthenticated requests (403)
5. ⚠️ `agentcore invoke` CLI is not designed for MCP protocol invocation
6. ⚠️ MCP client library expects OAuth bearer tokens, doesn't auto-add SigV4

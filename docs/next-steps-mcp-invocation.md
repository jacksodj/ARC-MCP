# Next Steps: Fixing End-to-End MCP Invocation

**Date Created**: November 1, 2025
**Last Updated**: November 1, 2025 (Post-Investigation)
**Status**: ROOT CAUSE IDENTIFIED - Authentication Required
**Priority**: HIGH - Need working end-to-end test

## 🔥 BREAKTHROUGH FINDINGS

### Root Cause Identified
1. **Correct Transport**: AWS docs confirm "Stateless streamable-http only" is required (NOT plain http)
   - Fixed in main.py:151 → `mcp.run(transport="streamable-http", stateless_http=True, host="0.0.0.0")`
   - Server starts successfully and processes PingRequests

2. **Invocation Method**: Cannot use raw boto3 `invoke_agent_runtime()` calls
   - Must use MCP Python client library: `from mcp.client.streamable_http import streamablehttp_client`
   - AWS docs provide complete example code

3. **Authentication**: MCP client with SigV4 disabled returns `403 Forbidden` (not 406!)
   - This confirms MCP protocol layer is working correctly
   - Need proper authentication (OAuth or AWS IAM)

### Key URLs
- AWS MCP Deployment Docs: https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-mcp.html
- AWS MCP Protocol Contract: https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-mcp-protocol-contract.html

## Current State Summary

### What's Working ✅
- CloudFormation infrastructure deployed successfully
- MCP server code with stateless HTTP transport: `mcp.run(transport="http", stateless_http=True, host="0.0.0.0")`
- AgentCore agent deployed: `arn:aws:bedrock-agentcore:us-east-1:ACCOUNT_ID:runtime/arc_mcp_server-RANDOM_ID`
- Server running and visible in CloudWatch logs
- Cognito User Pool configured: `us-east-1_h0Vo2Whhx`
- Test user created: `user@example.com` with password `TempPassword123!`

### What's Broken ❌
- **406 Error**: When invoking via curl or boto3 with proper headers
- **OAuth Claim Mismatch**: Cognito JWT tokens use `aud` claim for client ID, but AgentCore expects `client_id` claim
- **Local Testing**: Attempted but container issues with AgentCore local mode

## The 406 Error Details

### Test Command That Failed
```bash
curl -X POST \
  "https://bedrock-agentcore.us-east-1.amazonaws.com/runtimes/arn%3Aaws%3Abedrock-agentcore%3Aus-east-1%3AACCOUNT_ID%3Aruntime%2Farc_mcp_server-RANDOM_ID/invocations?qualifier=DEFAULT" \
  -H "Authorization: Bearer $BEARER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'
```

**Response**: 406 with no detailed error message

### Boto3 Test That Failed
```python
import boto3
client = boto3.client('bedrock-agentcore', region_name='us-east-1')
response = client.invoke_agent_runtime(
    agentRuntimeArn='arn:aws:bedrock-agentcore:us-east-1:ACCOUNT_ID:runtime/arc_mcp_server-RANDOM_ID',
    qualifier='DEFAULT',
    runtimeSessionId=str(uuid.uuid4()),
    mcpSessionId=str(uuid.uuid4()),
    mcpProtocolVersion='2024-11-05',
    contentType='application/json',
    accept='application/json',
    payload=json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
)
```

**Result**: 406 error consistently across all MCP protocol versions tested

## The OAuth Claim Mismatch Issue

### Problem
Cognito ID tokens structure:
```json
{
  "aud": "3ipsf00btbffko91d8irdu8up1",  // Client ID is here
  "sub": "user-id",
  "iss": "https://cognito-idp.us-east-1.amazonaws.com/us-east-1_h0Vo2Whhx",
  "token_use": "id",
  // ... no "client_id" claim
}
```

AgentCore JWT authorizer expects:
```json
{
  "client_id": "3ipsf00btbffko91d8irdu8up1",  // Needs to be here!
  // ... other claims
}
```

### Error Seen
```
OAuth authorization failed: Claim 'client_id' value mismatch with configuration
```

### Current Workaround
Set `authorizer_configuration: null` in `.bedrock_agentcore.yaml` to disable OAuth entirely. This gets past the OAuth error but still results in 406.

## Plan to Resolve

### Option 1: Fix OAuth with Cognito Pre-Token Generation Lambda (RECOMMENDED)

**User preference**: Fix OAuth with Cognito

**Steps**:

1. **Create Lambda Function** (`cloudformation-template.yaml`)
   ```yaml
   PreTokenGenerationLambda:
     Type: AWS::Lambda::Function
     Properties:
       FunctionName: !Sub '${ProjectName}-add-client-id-claim'
       Runtime: python3.11
       Handler: index.lambda_handler
       Code:
         ZipFile: |
           def lambda_handler(event, context):
               # Copy aud claim to client_id claim
               event['response']['claimsOverrideDetails'] = {
                   'claimsToAddOrOverride': {
                       'client_id': event['request']['userPoolId']
                   }
               }
               return event
       Role: !GetAtt PreTokenGenerationLambdaRole.Arn
   ```

2. **Add Lambda Trigger to User Pool**
   ```yaml
   LambdaConfig:
     PreTokenGeneration: !GetAtt PreTokenGenerationLambda.Arn
   ```

3. **Update AgentCore Config** (`.bedrock_agentcore.yaml`)
   ```yaml
   authorizer_configuration:
     customJWTAuthorizer:
       discoveryUrl: https://cognito-idp.us-east-1.amazonaws.com/us-east-1_h0Vo2Whhx/.well-known/openid-configuration
       allowedClients:
         - 3ipsf00btbffko91d8irdu8up1
   ```

4. **Test Flow**:
   - Get new token: `aws cognito-idp initiate-auth ...`
   - Decode token to verify `client_id` claim exists
   - Test invocation with new token
   - If still 406, investigate MCP protocol specifics

### Option 2: Switch to SigV4 Authentication (ALTERNATIVE)

**If OAuth proves too complex**:

1. Keep `authorizer_configuration: null`
2. Use AWS SigV4 signing for requests
3. No Cognito needed
4. Simpler but loses user-based auth

### Option 3: Investigate 406 Root Cause First (DEBUG PATH)

**Before fixing auth**, understand why 406 happens:

1. **Check AgentCore MCP Protocol Requirements**
   - Is there a specific MCP protocol version required?
   - Are there required/forbidden headers?
   - Is the payload format correct for AgentCore's MCP implementation?

2. **Test with Minimal Payload**
   - Try `initialize` method instead of `tools/list`
   - Try `ping` request
   - Try with/without MCP-specific headers

3. **Review CloudWatch Logs**
   - Look for server-side errors during invocation attempts
   - Check if request even reaches the MCP server

4. **Verify MCP Server Compatibility**
   - Confirm FastMCP stateless HTTP mode matches AgentCore expectations
   - Test MCP server locally first (if possible)

## Testing Strategy

### Phase 1: Local Verification (if possible)
1. Get local AgentCore working or test MCP server standalone
2. Verify server responds correctly to MCP protocol
3. Confirm tools/list works in isolation

### Phase 2: Remote Debugging
1. Enable detailed CloudWatch logging
2. Test with progressively complex requests
3. Capture exact request/response from AgentCore

### Phase 3: OAuth Integration
1. Deploy Lambda for claim injection
2. Test token generation
3. Test full invocation flow

## Key Files to Modify

1. **`cloudformation-template.yaml`**
   - Add PreTokenGenerationLambda
   - Add Lambda execution role
   - Add Lambda trigger to User Pool

2. **`.bedrock_agentcore.yaml`**
   - Re-enable `authorizer_configuration` once Lambda is deployed

3. **`docs/agentcore-mcp-deployment-guide.md`**
   - Add section on Lambda-based claim injection
   - Document the 406 resolution steps

4. **New file: `scripts/test-invocation.sh`**
   - Script to test invocation with proper headers
   - Include token refresh logic
   - Show decoded token for debugging

## Success Criteria

- [ ] Get fresh token with `client_id` claim present
- [ ] Successfully invoke `tools/list` method
- [ ] Successfully invoke `validate_content` tool with test data
- [ ] Document working invocation pattern
- [ ] Update deployment guide with solution

## Open Questions

1. **Is the 406 related to OAuth at all?**
   - We saw 406 even with `authorizer_configuration: null`
   - Could be MCP protocol issue independent of auth

2. **What's the actual AgentCore MCP protocol version?**
   - Tried 2024-11-05, 2024-10-07, 2024-09-19, null
   - All gave 406

3. **Are there AgentCore-specific MCP extensions?**
   - Need to check if standard MCP protocol is enough
   - May need AgentCore-specific modifications

4. **Should we contact AWS Support?**
   - This seems like an undocumented integration point
   - May need official guidance

## Resources

- Cognito Pre-Token Generation: https://docs.aws.amazon.com/cognito/latest/developerguide/user-pool-lambda-pre-token-generation.html
- MCP Specification: https://spec.modelcontextprotocol.io/
- AgentCore Documentation: https://docs.aws.amazon.com/bedrock-agentcore/
- FastMCP Docs: https://github.com/modelcontextprotocol/python-sdk

## Next Session Action Items

When resuming work:

1. Read this file to understand current state
2. Decide between Option 1 (fix OAuth) or Option 3 (debug 406 first)
3. If Option 1: Start with Lambda function creation
4. If Option 3: Start with minimal payload testing and log review
5. Create todos for chosen path using TodoWrite tool

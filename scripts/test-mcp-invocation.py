#!/usr/bin/env python3
"""
Test MCP server invocation with OAuth authentication

Usage:
    # Get bearer token first
    ./scripts/get-bearer-token.sh > /tmp/bearer_token.txt

    # Then run this script
    python3 scripts/test-mcp-invocation.py
"""
import asyncio
import sys
import os
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

# Configuration - update these values
AGENT_ARN = "arn:aws:bedrock-agentcore:us-east-1:ACCOUNT_ID:runtime/AGENT_NAME-RANDOM_ID"
REGION = "us-east-1"
TOKEN_FILE = "/tmp/bearer_token.txt"


async def test_mcp_invocation():
    """Test MCP server with OAuth authentication"""

    # Load bearer token
    if not os.path.exists(TOKEN_FILE):
        print(f"❌ Error: Bearer token file not found: {TOKEN_FILE}")
        print(f"Run: ./scripts/get-bearer-token.sh > {TOKEN_FILE}")
        return False

    with open(TOKEN_FILE, 'r') as f:
        bearer_token = f.read().strip()

    if not bearer_token:
        print(f"❌ Error: Bearer token file is empty")
        return False

    # Build MCP URL
    encoded_arn = AGENT_ARN.replace(':', '%3A').replace('/', '%2F')
    mcp_url = f"https://bedrock-agentcore.{REGION}.amazonaws.com/runtimes/{encoded_arn}/invocations?qualifier=DEFAULT"

    headers = {
        "authorization": f"Bearer {bearer_token}",
        "Content-Type": "application/json"
    }

    print(f"🔗 Connecting to AgentCore MCP server...")
    print(f"   Region: {REGION}")
    print(f"   Using OAuth bearer token")
    print()

    try:
        async with streamablehttp_client(
            mcp_url,
            headers,
            timeout=120,
            terminate_on_close=False
        ) as (read_stream, write_stream, _):

            async with ClientSession(read_stream, write_stream) as session:
                # Step 1: Initialize MCP session
                print("Step 1: Initializing MCP session...")
                init_result = await session.initialize()
                print(f"✅ Success! Connected to: {init_result.serverInfo.name} v{init_result.serverInfo.version}")
                print(f"   Protocol: {init_result.protocolVersion}")
                print()

                # Step 2: List available tools
                print("Step 2: Listing available tools...")
                tools_result = await session.list_tools()
                print(f"✅ Found {len(tools_result.tools)} tools:")
                for i, tool in enumerate(tools_result.tools, 1):
                    print(f"   {i}. {tool.name}")
                    print(f"      {tool.description}")
                print()

                print("🎉 SUCCESS! MCP invocation test passed!")
                print()
                print("Next steps:")
                print("  - Call tools using: await session.call_tool(name, arguments)")
                print("  - See docs/agentcore-mcp-deployment-guide.md for examples")

                return True

    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        print()
        print("Troubleshooting:")
        print("  1. Check token is valid: cat /tmp/bearer_token.txt")
        print("  2. Get fresh token: ./scripts/get-bearer-token.sh")
        print("  3. Verify agent is running: agentcore status")
        return False


if __name__ == "__main__":
    success = asyncio.run(test_mcp_invocation())
    sys.exit(0 if success else 1)

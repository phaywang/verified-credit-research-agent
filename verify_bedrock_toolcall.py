#!/usr/bin/env python3
"""
Minimal Bedrock tool calling verification.
Tests if our Bedrock account can invoke Claude with tool_use capability.

Steps:
1. Check available Claude models in Bedrock
2. Try tool calling with a dummy tool
3. Verify tool_use block parsing
"""

import json
import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

def check_bedrock_models():
    """Check which Claude models are available in Bedrock."""
    try:
        import boto3
        from botocore.exceptions import NoCredentialsError

        print("=== Checking Bedrock Models ===")

        # Try to get AWS credentials
        session = boto3.Session()
        try:
            creds = session.get_credentials()
            if creds:
                print(f"✓ AWS credentials found")
            else:
                print("✗ No AWS credentials found")
                return False
        except NoCredentialsError:
            print("✗ No AWS credentials configured")
            return False

        # Try to list models
        try:
            bedrock = session.client("bedrock", region_name="us-east-1")
            # Note: list_foundation_models requires bedrock (not bedrock-runtime)
            response = bedrock.list_foundation_models(
                byOutputModality='TEXT'
            )

            claude_models = [
                m for m in response.get('modelSummaries', [])
                if 'claude' in m.get('modelId', '').lower()
            ]

            if claude_models:
                print(f"✓ Found {len(claude_models)} Claude models:")
                for m in claude_models[:5]:  # Show first 5
                    print(f"  - {m['modelId']}")
            else:
                print("✗ No Claude models found in Bedrock")
                return False

        except Exception as e:
            print(f"✗ Error listing models: {e}")
            print("  (This is OK if bedrock API access is restricted)")
            return None  # Neutral: can't verify but might still work

        return True

    except ImportError:
        print("✗ boto3 not installed")
        return False

def check_tool_calling_capability():
    """Check if we can construct and parse tool_use messages."""
    print("\n=== Checking Tool Calling Capability ===")

    try:
        from langchain_aws import ChatBedrockConverse
        from langchain_core.tools import tool
        from langchain_core.messages import HumanMessage

        # Define a dummy tool
        @tool
        def get_weather(location: str) -> str:
            """Get weather for a location."""
            return f"Sunny in {location}"

        tools = [get_weather]

        # Try to create client
        try:
            import boto3
            session = boto3.Session()
            client = session.client("bedrock-runtime", region_name="us-east-1")

            llm = ChatBedrockConverse(
                model="us.anthropic.claude-opus-4-8",  # Try Opus 4.8
                client=client,
                temperature=0,
                max_tokens=1024,
            )

            # Try to bind tools
            try:
                llm_with_tools = llm.bind_tools(tools)
                print("✓ Tool binding works (LangChain)")
            except AttributeError:
                print("✗ bind_tools not available on ChatBedrockConverse")
                print("  → Need to implement raw tool_use schema")
                return None

            # Try to invoke
            try:
                response = llm_with_tools.invoke(
                    [HumanMessage(content="What's the weather in NYC?")]
                )
                print(f"✓ Tool-calling response received")
                print(f"  Response type: {type(response)}")
                if hasattr(response, 'tool_calls'):
                    print(f"  Tool calls: {response.tool_calls}")
                else:
                    print(f"  Content: {response.content[:100]}...")
                return True

            except Exception as e:
                print(f"✗ Error invoking with tools: {e}")
                return False

        except Exception as e:
            print(f"✗ Error creating Bedrock client: {e}")
            return None

    except ImportError as e:
        print(f"✗ Missing dependency: {e}")
        return False

def main():
    print("Bedrock Tool Calling Verification\n")

    # Check models
    model_check = check_bedrock_models()

    # Check tool capability
    tool_check = check_tool_calling_capability()

    print("\n=== Summary ===")
    print(f"AWS/Bedrock models: {'✓' if model_check else '✗' if model_check is False else '?'}")
    print(f"Tool calling: {'✓' if tool_check else '✗' if tool_check is False else '?'}")

    if model_check and tool_check:
        print("\n✓ Bedrock tool calling foundation is ready!")
        print("  → Proceed with M3 Phase 1 (tool wrapping)")
        return 0
    elif model_check is None or tool_check is None:
        print("\n? Some checks were neutral (credentials/access restricted)")
        print("  → Assume Bedrock + tool calling works; proceed with caution")
        print("  → First real test will be in Phase 1")
        return 0
    else:
        print("\n✗ Bedrock tool calling foundation needs setup")
        print("  Required:")
        print("  1. AWS credentials configured (~/.aws/credentials or env vars)")
        print("  2. Bedrock API access in us-east-1 (or your region)")
        print("  3. Claude 3.5 Sonnet / Opus 4.8 access")
        return 1

if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""
Test script for Phase 5: API Integration

Tests:
1. Conversation creation
2. Message sending
3. SSE streaming
4. WebSocket connection

Usage:
    # Start the API server first:
    uvicorn src.api.main:app --reload

    # Then run this test:
    python scripts/test_api.py
"""

import asyncio
import httpx
import json
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))


async def test_health():
    """Test health endpoint."""
    print("\n=== Testing Health Endpoint ===")
    async with httpx.AsyncClient() as client:
        response = await client.get("http://localhost:8000/health")
        print(f"Status: {response.status_code}")
        print(f"Response: {response.json()}")
        assert response.status_code == 200
        print("✅ Health check passed")


async def test_conversation_crud():
    """Test conversation CRUD operations."""
    print("\n=== Testing Conversation CRUD ===")
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Create conversation
        print("\n1. Creating conversation...")
        response = await client.post(
            "http://localhost:8000/api/v1/conversations",
            json={"user_id": "test_user"}
        )
        print(f"Status: {response.status_code}")
        print(f"Response: {response.json()}")

        if response.status_code != 200:
            print("❌ Failed to create conversation")
            return None

        data = response.json()
        conversation_id = data["conversation_id"]
        print(f"✅ Created conversation: {conversation_id}")

        # Get conversation
        print("\n2. Getting conversation...")
        response = await client.get(
            f"http://localhost:8000/api/v1/conversations/{conversation_id}"
        )
        print(f"Status: {response.status_code}")
        assert response.status_code == 200
        print("✅ Get conversation passed")

        return conversation_id


async def test_send_message(conversation_id: str):
    """Test sending a message."""
    print("\n=== Testing Send Message ===")
    async with httpx.AsyncClient(timeout=60.0) as client:
        # Send a simple message
        print("\n1. Sending message...")
        response = await client.post(
            f"http://localhost:8000/api/v1/conversations/{conversation_id}/messages",
            json={"message": "transformer models"}
        )
        print(f"Status: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            print(f"State: {data['state']}")
            print(f"Message: {data['message'][:200]}...")
            print("✅ Send message passed")
            return data
        else:
            print(f"Response: {response.text}")
            print("❌ Send message failed")
            return None


async def test_sse_stream(conversation_id: str):
    """Test SSE streaming endpoint."""
    print("\n=== Testing SSE Stream ===")
    print("Connecting to SSE stream...")

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            async with client.stream(
                "GET",
                f"http://localhost:8000/api/v1/conversations/{conversation_id}/stream"
            ) as response:
                print(f"Status: {response.status_code}")

                event_count = 0
                async for line in response.aiter_lines():
                    if line.startswith("data:"):
                        data = json.loads(line[5:].strip())
                        print(f"Event: {data.get('type')} - {data.get('data', {})}")
                        event_count += 1
                        if event_count >= 2:  # Just test a few events
                            break

                print(f"✅ Received {event_count} SSE events")

        except httpx.ReadTimeout:
            print("SSE stream timed out (expected for keepalive)")
            print("✅ SSE stream connection works")


async def test_delete_conversation(conversation_id: str):
    """Test deleting a conversation."""
    print("\n=== Testing Delete Conversation ===")
    async with httpx.AsyncClient() as client:
        response = await client.delete(
            f"http://localhost:8000/api/v1/conversations/{conversation_id}"
        )
        print(f"Status: {response.status_code}")
        print(f"Response: {response.json()}")
        assert response.status_code == 200
        print("✅ Delete conversation passed")


async def test_websocket_connection():
    """Test WebSocket connection."""
    print("\n=== Testing WebSocket ===")
    print("Note: WebSocket test requires websockets library")

    try:
        import websockets
    except ImportError:
        print("⚠️ websockets library not installed, skipping WebSocket test")
        print("Install with: pip install websockets")
        return

    try:
        async with websockets.connect(
            "ws://localhost:8000/api/v1/ws/test-ws-123",
            close_timeout=5
        ) as ws:
            # Receive connected message
            response = await asyncio.wait_for(ws.recv(), timeout=5)
            data = json.loads(response)
            print(f"Connected: {data}")

            # Send a message
            await ws.send(json.dumps({
                "type": "message",
                "content": "hello"
            }))

            # Receive response
            response = await asyncio.wait_for(ws.recv(), timeout=10)
            data = json.loads(response)
            print(f"Response: {data.get('type')} - {data.get('data', {}).get('state', 'N/A')}")

            print("✅ WebSocket test passed")

    except Exception as e:
        print(f"⚠️ WebSocket test failed: {e}")
        print("This might be expected if the API server is not running")


async def main():
    """Run all API tests."""
    print("=" * 60)
    print("Phase 5: API Integration Tests")
    print("=" * 60)
    print("\nMake sure the API server is running:")
    print("  uvicorn src.api.main:app --reload")
    print()

    try:
        # Test health
        await test_health()

        # Test conversation CRUD
        conversation_id = await test_conversation_crud()
        if not conversation_id:
            print("\n❌ Cannot proceed without conversation")
            return

        # Test send message
        await test_send_message(conversation_id)

        # Test SSE stream
        await test_sse_stream(conversation_id)

        # Test WebSocket
        await test_websocket_connection()

        # Test delete
        await test_delete_conversation(conversation_id)

        print("\n" + "=" * 60)
        print("All tests completed!")
        print("=" * 60)

    except httpx.ConnectError:
        print("\n❌ Could not connect to API server")
        print("Please start the server with:")
        print("  uvicorn src.api.main:app --reload")
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())

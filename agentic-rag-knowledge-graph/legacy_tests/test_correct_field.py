import asyncio
import httpx
import uuid
import json

async def test_correct_field():
    """Test with correct field name."""
    
    session_id = str(uuid.uuid4())
    print(f"Testing chat with session: {session_id}")
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            "http://localhost:8058/chat",
            json={
                "message": "What is Practical Strategy?",
                "session_id": session_id
            }
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"\n✅ Chat responded successfully!")
            
            # Print all fields in the response
            print("\nResponse fields:")
            for key, value in result.items():
                if key == "message":
                    print(f"  {key}: {value[:200]}..." if len(str(value)) > 200 else f"  {key}: {value}")
                else:
                    print(f"  {key}: {type(value).__name__} ({len(value) if hasattr(value, '__len__') else 'N/A'})")
            
            # Check the actual message field
            message = result.get('message', '')
            if message:
                print(f"\n✅ Got response: {len(message)} characters")
                print(f"\nFirst 500 chars of response:")
                print(message[:500])
            else:
                print("\n⚠️  Message field is empty")
                
        else:
            print(f"❌ Chat failed: {response.status_code}")
            print(f"Error: {response.text}")

if __name__ == "__main__":
    asyncio.run(test_correct_field())


import asyncio
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from fastapi.testclient import TestClient
from web.app import app

def test_web_endpoint():
    client = TestClient(app)
    
    # Path to a sample PDF
    pdf_path = "docs/examples/тест11022026.pdf"
    
    if not os.path.exists(pdf_path):
        print(f"Skipping test: File {pdf_path} not found.")
        return

    print(f"Testing with file: {pdf_path}")
    
    with open(pdf_path, "rb") as f:
        files = {"file": ("test.pdf", f, "application/pdf")}
        response = client.post("/api/check", files=files)
        
    print(f"Status Code: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print("Response JSON:")
        print(f"  Status: {data.get('status')}")
        print(f"  Issues Count: {data.get('issues_count')}")
        print(f"  Items Found: {data.get('total_items')}")
    else:
        print("Error Response:")
        print(response.text)

if __name__ == "__main__":
    # Ensure env vars are loaded if needed (dotenv)
    from bot.config import settings
    print(f"DB Configured: {settings.DB_DSN is not None}")
    
    try:
        test_web_endpoint()
    except Exception as e:
        print(f"Test failed with error: {e}")

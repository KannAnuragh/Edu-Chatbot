import asyncio
import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from providers.cloudflare import CloudflareVectorDBProvider

async def main():
    provider = CloudflareVectorDBProvider()
    dummy_vector = [0.0] * 1024 # assuming bge-base-en-v1.5 which is 1024 or 768? Wait, BGE-large is 1024. The app uses 1024.
    
    # 1. Unfiltered query
    import httpx
    url = f"{provider._get_base_url()}/query"
    payload = {
        "vector": dummy_vector,
        "topK": 5,
        "returnValues": False,
        "returnMetadata": "all"
    }
    print("Testing unfiltered query...")
    async with httpx.AsyncClient() as client:
        resp = await client.post(url, headers=provider._get_cf_headers(), json=payload)
        print(f"Unfiltered Status: {resp.status_code}")
        if resp.is_success:
            data = resp.json().get("result", {}).get("matches", [])
            print(f"Total matches: {len(data)}")
            if data:
                print(f"Sample metadata: {data[0].get('metadata')}")
        else:
            print(f"Error: {resp.text}")

if __name__ == "__main__":
    asyncio.run(main())

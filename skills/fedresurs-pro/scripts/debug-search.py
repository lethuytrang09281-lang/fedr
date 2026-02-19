#!/usr/bin/env python3
"""
Manual search test - uses 1-3 API requests
Run: docker exec -it fedr-app-1 python /app/scripts/debug-search.py
"""

import asyncio
import sys
import os

# Add project root to path
sys.path.insert(0, '/app')

from src.services.fedresurs_search import FedresursSearch
from src.config import get_settings


async def main():
    settings = get_settings()
    
    print("🔍 Fedresurs Search Debug Tool")
    print("=" * 60)
    print(f"API Key: {settings.PARSER_API_KEY[:20]}...")
    print()
    
    # Initialize search
    search = FedresursSearch(api_key=settings.PARSER_API_KEY)
    
    try:
        # Run search
        print("⏳ Running search (this will use 1-3 API requests)...")
        lots = await search.search_lots()
        
        print()
        print("✅ Search Complete!")
        print(f"📦 Found {len(lots)} lots")
        print()
        
        if lots:
            print("=" * 60)
            print("FIRST LOT:")
            print("=" * 60)
            lot = lots[0]
            print(f"Lot Number:  {lot.get('lot_number', 'N/A')}")
            print(f"Description: {lot.get('description', 'N/A')[:200]}...")
            print(f"Start Price: {lot.get('start_price', 'N/A'):,} ₽")
            print(f"Debtor INN:  {lot.get('debtor_inn', 'N/A')}")
            print(f"Message ID:  {lot.get('message_id', 'N/A')}")
            print(f"Auction ID:  {lot.get('auction_id', 'N/A')}")
            print()
            
            if len(lots) > 1:
                print(f"... and {len(lots) - 1} more lots")
        else:
            print("⚠️  No lots found!")
            print()
            print("Possible reasons:")
            print("  1. No matching auctions at this time")
            print("  2. Filter is too strict")
            print("  3. API limit exhausted")
            print()
            print("Check logs for details:")
            print("  docker logs fedr-app-1 | grep ERROR")
            
    except Exception as e:
        print()
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        await search.close()
        print()
        print("Done.")


if __name__ == "__main__":
    asyncio.run(main())

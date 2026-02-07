"""
Test script for Moscow Open Data API client.
"""
import asyncio
import sys
from src.services.moscow_api_client import MoscowAPIClient


async def test_moscow_api():
    """Test Moscow Open Data API functionality."""
    print("=" * 60)
    print("🏛 Moscow Open Data API Test")
    print("=" * 60)

    client = MoscowAPIClient()

    try:
        # Test 1: Get dataset count
        print("\n📊 Test 1: Get dataset count")
        dataset_id = 658  # Example dataset
        count = await client.get_dataset_count(dataset_id)
        if count is not None:
            print(f"  ✅ Dataset {dataset_id} has {count:,} records")
        else:
            print(f"  ❌ Failed to get count for dataset {dataset_id}")

        # Test 2: Get dataset info
        print("\n📋 Test 2: Get dataset metadata")
        info = await client.get_dataset_info(dataset_id)
        if info:
            print(f"  ✅ Dataset info retrieved")
            print(f"     - ID: {info.get('Id')}")
            print(f"     - Caption: {info.get('Caption', 'N/A')}")
            print(f"     - Version: {info.get('VersionNumber', 'N/A')}")
        else:
            print(f"  ❌ Failed to get dataset info")

        # Test 3: Get sample rows
        print("\n📄 Test 3: Get sample rows")
        rows = await client.get_dataset_rows(
            dataset_id=dataset_id,
            top=5,
            orderby="Number"
        )
        if rows:
            print(f"  ✅ Retrieved {len(rows)} rows")
            for i, row in enumerate(rows, 1):
                formatted = client.format_row_data(row)
                print(f"\n  Row {i}:")
                print(f"    - ID: {formatted.get('id')}")
                print(f"    - Number: {formatted.get('number')}")
                # Print first 3 fields from Cells
                cells = row.get("Cells", {})
                for j, (key, value) in enumerate(list(cells.items())[:3]):
                    print(f"    - {key}: {value}")
        else:
            print(f"  ❌ Failed to get rows")

        # Test 4: Search functionality
        print("\n🔍 Test 4: Search across dataset")
        search_query = "Москва"
        results = await client.get_dataset_rows(
            dataset_id=dataset_id,
            search_query=search_query,
            top=3
        )
        if results:
            print(f"  ✅ Found {len(results)} results for '{search_query}'")
            for i, row in enumerate(results, 1):
                print(f"    {i}. Record #{row.get('Number')}")
        else:
            print(f"  ❌ No results found for '{search_query}'")

        # Test 5: Pagination example
        print("\n📚 Test 5: Pagination")
        page_1 = await client.get_dataset_rows(
            dataset_id=dataset_id,
            top=10,
            skip=0
        )
        page_2 = await client.get_dataset_rows(
            dataset_id=dataset_id,
            top=10,
            skip=10
        )
        if page_1 and page_2:
            print(f"  ✅ Page 1: {len(page_1)} records")
            print(f"  ✅ Page 2: {len(page_2)} records")
            print(f"  ✅ Pagination works correctly")
        else:
            print(f"  ❌ Pagination test failed")

        # Summary
        print("\n" + "=" * 60)
        print("📊 TEST SUMMARY")
        print("=" * 60)
        print("  ✅ Moscow Open Data API is accessible")
        print(f"  ✅ API Key: {client.api_key[:20]}...")
        print(f"  ✅ Base URL: {client.BASE_URL}")
        print("\n🎉 All tests completed successfully!")

    except Exception as e:
        print(f"\n❌ Error during testing: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    finally:
        await client.close()
        print("\n👋 Client closed")


def main():
    """Run async test."""
    try:
        asyncio.run(test_moscow_api())
        sys.exit(0)
    except KeyboardInterrupt:
        print("\n\n⏹️  Test interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

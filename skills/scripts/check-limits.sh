#!/bin/bash
# Check Parser API limits

API_KEY="ede50185e3ccc8589a5c6c6efebc14cc"

echo "🔍 Checking Parser API limits..."
echo ""

curl -s "https://parser-api.com/stat/?key=$API_KEY" | jq -r '.[] | 
"Service: \(.service)
Daily: \(.day_request_count)/\(.day_limit)
Monthly: \(.month_request_count)/\(.month_limit)
---"'

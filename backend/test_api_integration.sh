#!/bin/bash
set -e

echo "=========================================="
echo "API Integration Test"
echo "=========================================="
echo ""

# Test: API Connectivity
echo "Testing API endpoint..."
response=$(curl -s -w "\n%{http_code}" -X POST https://api-ai.for2.top/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer sk-api-for2_DevOps" \
  -d '{"model":"claude-opus-4-8","messages":[{"role":"user","content":"Say OK"}],"max_tokens":5}' \
  2>&1 || echo "CURL_FAILED")

if [[ "$response" == *"CURL_FAILED"* ]]; then
  echo "   ✗ API connection failed"
  echo "   Please check:"
  echo "     - Network connectivity"
  echo "     - API endpoint URL"
  echo "     - API key"
  exit 1
else
  http_code=$(echo "$response" | tail -n1)
  body=$(echo "$response" | head -n-1)
  echo "   ✓ HTTP Status: $http_code"
  if [[ "$http_code" == "200" ]]; then
    echo "   ✓ API is working!"
  else
    echo "   Response: $body"
    exit 1
  fi
fi
echo ""
echo "=========================================="
echo "✓ All tests passed!"
echo "=========================================="

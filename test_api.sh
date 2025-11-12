#!/bin/bash

# API Configuration
API_URL="https://t32vd52q4e.execute-api.us-east-2.amazonaws.com/v1"
API_KEY="odlg595fBfGJK0ZPOCQUfY6BNdrhE_pIAQBsnDf8sYqjUwF2CHIWRk16lbOFvJKy"

echo "========================================"
echo "Testing Zapier Triggers API"
echo "========================================"
echo ""

# Test 1: Health Check (no auth required)
echo "Test 1: Health Check"
echo "--------------------"
curl -s "${API_URL}/status" | python -m json.tool
echo ""
echo ""

# Test 2: Create an Event
echo "Test 2: Create an Event"
echo "-----------------------"
EVENT_RESPONSE=$(curl -s -X POST "${API_URL}/events" \
  -H "Authorization: Bearer ${API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "event_type": "test.deployment",
    "payload": {"message": "Hello from AWS!", "timestamp": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'"},
    "source": "deployment-test"
  }')
echo "$EVENT_RESPONSE" | python -m json.tool
EVENT_ID=$(echo "$EVENT_RESPONSE" | python -c "import sys, json; print(json.load(sys.stdin).get('event_id', ''))" 2>/dev/null || echo "")
echo ""
echo ""

# Test 3: Get Inbox
echo "Test 3: Get Inbox (all events)"
echo "-------------------------------"
curl -s -X GET "${API_URL}/inbox" \
  -H "Authorization: Bearer ${API_KEY}" | python -m json.tool
echo ""
echo ""

# Test 4: Get Specific Event (if we have an event_id)
if [ -n "$EVENT_ID" ]; then
  echo "Test 4: Get Specific Event"
  echo "---------------------------"
  curl -s -X GET "${API_URL}/inbox/${EVENT_ID}" \
    -H "Authorization: Bearer ${API_KEY}" | python -m json.tool
  echo ""
  echo ""
fi

# Test 5: Create Another Event with Different Type
echo "Test 5: Create Another Event"
echo "----------------------------"
curl -s -X POST "${API_URL}/events" \
  -H "Authorization: Bearer ${API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "event_type": "user.signup",
    "payload": {"user_id": "12345", "email": "test@example.com"},
    "source": "api-test"
  }' | python -m json.tool
echo ""
echo ""

# Test 6: Get Inbox with Limit
echo "Test 6: Get Inbox (limited to 2)"
echo "---------------------------------"
curl -s -X GET "${API_URL}/inbox?limit=2" \
  -H "Authorization: Bearer ${API_KEY}" | python -m json.tool
echo ""
echo ""

# Test 7: Acknowledge Event (if we have an event_id)
if [ -n "$EVENT_ID" ]; then
  echo "Test 7: Acknowledge Event"
  echo "-------------------------"
  curl -s -X DELETE "${API_URL}/inbox/${EVENT_ID}" \
    -H "Authorization: Bearer ${API_KEY}" | python -m json.tool
  echo ""
  echo ""
fi

echo "========================================"
echo "Testing Complete!"
echo "========================================"
echo ""
echo "Demo UI available at:"
echo "${API_URL}/static/index.html"

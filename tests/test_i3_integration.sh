#!/bin/bash

# I3 Gateway Integration Test Script
# Tests all functionality between MUD and Gateway

echo "========================================"
echo "I3 GATEWAY INTEGRATION TEST"
echo "========================================"
echo "Testing with LuminariMUD connection"
echo ""

# Test configuration
HOST="localhost"
PORT="8081"
API_KEY="demo-key-123"

# Helper function to send JSON-RPC request
send_request() {
    local method=$1
    local params=$2
    local id=$3
    
    echo "{\"jsonrpc\": \"2.0\", \"method\": \"$method\", \"params\": $params, \"id\": $id}"
}

# Test 1: Administrative Functions
echo "TEST 1: Administrative Functions"
echo "--------------------------------"
(
    send_request "authenticate" "{\"api_key\": \"$API_KEY\", \"mud_name\": \"TestClient\"}" 1
    sleep 0.5
    send_request "status" "{}" 2
    sleep 0.5
    send_request "stats" "{}" 3
    sleep 0.5
    send_request "heartbeat" "{}" 4
    sleep 1
) | nc -w 3 $HOST $PORT | while IFS= read -r line; do
    echo "Response: $line"
done

echo ""
echo "TEST 2: Tell Messages"
echo "---------------------"
(
    send_request "authenticate" "{\"api_key\": \"$API_KEY\", \"mud_name\": \"TestClient\"}" 1
    sleep 0.5
    send_request "tell" "{\"target_mud\": \"LuminariMUD\", \"target_user\": \"testuser\", \"message\": \"Test tell from integration suite\", \"from_user\": \"Tester\"}" 2
    sleep 2
) | nc -w 4 $HOST $PORT | while IFS= read -r line; do
    echo "Response: $line"
done

echo ""
echo "TEST 3: Channel Operations"
echo "--------------------------"
(
    send_request "authenticate" "{\"api_key\": \"$API_KEY\", \"mud_name\": \"TestClient\"}" 1
    sleep 0.5
    send_request "channel_list" "{}" 2
    sleep 0.5
    send_request "channel_join" "{\"channel\": \"imud_gossip\", \"user\": \"Tester\"}" 3
    sleep 0.5
    send_request "channel_send" "{\"channel\": \"imud_gossip\", \"message\": \"Test message\", \"from_user\": \"Tester\"}" 4
    sleep 0.5
    send_request "channel_who" "{\"channel\": \"imud_gossip\"}" 5
    sleep 2
) | nc -w 5 $HOST $PORT | while IFS= read -r line; do
    echo "Response: $line"
done

echo ""
echo "TEST 4: Information Queries"
echo "---------------------------"
(
    send_request "authenticate" "{\"api_key\": \"$API_KEY\", \"mud_name\": \"TestClient\"}" 1
    sleep 0.5
    send_request "mudlist" "{}" 2
    sleep 0.5
    send_request "who" "{\"target_mud\": \"LuminariMUD\"}" 3
    sleep 0.5
    send_request "finger" "{\"target_mud\": \"LuminariMUD\", \"username\": \"testuser\"}" 4
    sleep 0.5
    send_request "locate" "{\"username\": \"test\"}" 5
    sleep 3
) | nc -w 6 $HOST $PORT | while IFS= read -r line; do
    echo "Response: $line"
done

echo ""
echo "========================================"
echo "TEST COMPLETE"
echo "========================================"
echo "Check gateway logs for any errors"
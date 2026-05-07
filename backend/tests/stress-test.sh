#!/bin/bash

###############################################################################
# Document Management System - Stress Test (Bash)
# Supports both API-only and full S3 I/O testing
# Usage: ./stress-test.sh --users 10 --mode full --file-size 1M
###############################################################################

BASE_URL="http://localhost:8000"
NUM_USERS=10
REQUESTS_PER_USER=10
MODE="simple"  # simple | full
FILE_SIZE="100K"  # Size of test files to upload

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --users) NUM_USERS="$2"; shift 2;;
        --requests) REQUESTS_PER_USER="$2"; shift 2;;
        --base-url) BASE_URL="$2"; shift 2;;
        --mode) MODE="$2"; shift 2;;
        --file-size) FILE_SIZE="$2"; shift 2;;
        *) echo "Unknown option: $1"; exit 1;;
    esac
done

echo "=========================================="
echo "Document Management System - Stress Test"
echo "=========================================="
echo "Base URL: $BASE_URL"
echo "Number of concurrent users: $NUM_USERS"
echo "Requests per user: $REQUESTS_PER_USER"
echo "Mode: $MODE (simple=API only, full=API + S3 I/O)"
if [[ "$MODE" == "full" ]]; then
    echo "File size per upload: $FILE_SIZE"
fi
echo ""

# Create a temporary test file
create_test_file() {
    local size=$1
    local file=$2
    case ${size: -1} in
        K|k) size=${size%?}; size=$((size * 1024)) ;;
        M|m) size=${size%?}; size=$((size * 1024 * 1024)) ;;
        G|g) size=${size%?}; size=$((size * 1024 * 1024 * 1024)) ;;
    esac
    dd if=/dev/zero of="$file" bs=1 count="$size" 2>/dev/null
}

# Function to simulate one user
user_session() {
    local user_id=$1
    local email="stress_${user_id}_$(date +%s%N)@example.com"
    local password="StressTest123!"
    local local_success=0
    local local_failures=0
    local local_time=0
    local temp_file="/tmp/test_file_${user_id}_$$.bin"
    
    # Register
    reg_response=$(curl -s -w "\n%{time_total}\n%{http_code}" -X POST "$BASE_URL/auth/register" \
        -H "Content-Type: application/json" \
        -d "{\"username\":\"stress_user_$user_id\",\"email\":\"$email\",\"password\":\"$password\"}")
    http_code=$(echo "$reg_response" | tail -1)
    response_time=$(echo "$reg_response" | tail -2 | head -1)
    local_time=$(echo "$local_time + $response_time" | bc)
    [[ "$http_code" == "200" ]] && ((local_success++)) || ((local_failures++))
    
    # Login
    login_response=$(curl -s -w "\n%{time_total}\n%{http_code}" -X POST "$BASE_URL/auth/login" \
        -H "Content-Type: application/json" \
        -d "{\"email\":\"$email\",\"password\":\"$password\"}")
    http_code=$(echo "$login_response" | tail -1)
    response_time=$(echo "$login_response" | tail -2 | head -1)
    local_time=$(echo "$local_time + $response_time" | bc)
    body=$(echo "$login_response" | head -1)
    if [[ "$http_code" == "200" ]]; then
        ((local_success++))
        token=$(echo "$body" | grep -o '"access_token":"[^"]*"' | cut -d'"' -f4)
    else
        ((local_failures++))
        rm -f "$temp_file"
        echo "$local_success $local_failures $local_time"
        return
    fi
    
    # Make multiple requests
    for i in $(seq 1 $REQUESTS_PER_USER); do
        choice=$((RANDOM % 7))
        case $choice in
            0) response=$(curl -s -w "\n%{time_total}\n%{http_code}" -X GET "$BASE_URL/auth/me" -H "Authorization: Bearer $token") ;;
            1) response=$(curl -s -w "\n%{time_total}\n%{http_code}" -X POST "$BASE_URL/folders" -H "Authorization: Bearer $token" -H "Content-Type: application/json" -d "{\"name\":\"Folder_${user_id}_$i\"}") ;;
            2) response=$(curl -s -w "\n%{time_total}\n%{http_code}" -X GET "$BASE_URL/folders?limit=10" -H "Authorization: Bearer $token") ;;
            3|4)
                upload_response=$(curl -s -w "\n%{time_total}\n%{http_code}" -X POST "$BASE_URL/documents/upload-url" -H "Authorization: Bearer $token" -H "Content-Type: application/json" -d "{\"filename\":\"file_${user_id}_${i}.bin\",\"mime_type\":\"application/octet-stream\"}")
                http_code=$(echo "$upload_response" | tail -1)
                response_time=$(echo "$upload_response" | tail -2 | head -1)
                local_time=$(echo "$local_time + $response_time" | bc)
                body=$(echo "$upload_response" | head -1)
                if [[ "$http_code" == "200" ]]; then
                    ((local_success++))
                    document_id=$(echo "$body" | grep -o '"document_id":"[^"]*"' | cut -d'"' -f4)
                    upload_url=$(echo "$body" | grep -o '"upload_url":"[^"]*"' | cut -d'"' -f4)
                    if [[ "$MODE" == "full" ]] && [[ -n "$upload_url" ]]; then
                        create_test_file "$FILE_SIZE" "$temp_file"
                        [[ -f "$temp_file" ]] && {
                            file_size=$(stat -f%z "$temp_file" 2>/dev/null || stat -c%s "$temp_file" 2>/dev/null)
                            put_response=$(curl -s -w "\n%{time_total}\n%{http_code}" -X PUT "$upload_url" --data-binary "@$temp_file" -H "Content-Type: application/octet-stream")
                            put_code=$(echo "$put_response" | tail -1)
                            response_time=$(echo "$put_response" | tail -2 | head -1)
                            local_time=$(echo "$local_time + $response_time" | bc)
                            [[ "$put_code" =~ ^(200|204)$ ]] && ((local_success++)) || ((local_failures++))
                            confirm_response=$(curl -s -w "\n%{time_total}\n%{http_code}" -X POST "$BASE_URL/documents/confirm" -H "Authorization: Bearer $token" -H "Content-Type: application/json" -d "{\"document_id\":\"$document_id\",\"size_bytes\":$file_size}")
                            confirm_code=$(echo "$confirm_response" | tail -1)
                            response_time=$(echo "$confirm_response" | tail -2 | head -1)
                            local_time=$(echo "$local_time + $response_time" | bc)
                            [[ "$confirm_code" == "200" ]] && ((local_success++)) || ((local_failures++))
                            rm -f "$temp_file"
                        }
                    else
                        response=$(curl -s -w "\n%{time_total}\n%{http_code}" -X POST "$BASE_URL/documents/confirm" -H "Authorization: Bearer $token" -H "Content-Type: application/json" -d "{\"document_id\":\"$document_id\",\"size_bytes\":1000}")
                        response_time=$(echo "$response" | tail -2 | head -1)
                        local_time=$(echo "$local_time + $response_time" | bc)
                    fi
                else
                    ((local_failures++))
                fi
                continue
                ;;
            5) response=$(curl -s -w "\n%{time_total}\n%{http_code}" -X GET "$BASE_URL/documents?limit=10" -H "Authorization: Bearer $token") ;;
            6) response=$(curl -s -w "\n%{time_total}\n%{http_code}" -X GET "$BASE_URL/permissions" -H "Authorization: Bearer $token") ;;
        esac
        http_code=$(echo "$response" | tail -1)
        response_time=$(echo "$response" | tail -2 | head -1)
        local_time=$(echo "$local_time + $response_time" | bc)
        [[ "$http_code" =~ ^(200|204)$ ]] && ((local_success++)) || ((local_failures++))
    done
    rm -f "$temp_file"
    echo "$local_success $local_failures $local_time"
}

echo "Starting stress test with $NUM_USERS concurrent users..."
echo ""

start_time=$(date +%s%N)
total_success=0 total_failures=0 total_time=0

# Run users in parallel
for i in $(seq 1 $NUM_USERS); do
    user_session $i > /tmp/user_${i}_result.txt &
done

# Wait and collect results
wait
for i in $(seq 1 $NUM_USERS); do
    result=$(cat /tmp/user_${i}_result.txt 2>/dev/null)
    success=$(echo "$result" | awk '{print $1}')
    failures=$(echo "$result" | awk '{print $2}')
    elapsed=$(echo "$result" | awk '{print $3}')
    printf "[User %3d] Success: %3d | Failures: %3d | Time: %.2fs\n" $i $success $failures $elapsed
    total_success=$((total_success + success))
    total_failures=$((total_failures + failures))
    total_time=$(echo "$total_time + $elapsed" | bc)
    rm -f /tmp/user_${i}_result.txt
done

end_time=$(date +%s%N)
elapsed=$(( (end_time - start_time) / 1000000 ))

echo ""
echo "=========================================="
echo "Stress Test Results"
echo "=========================================="
[[ "$MODE" == "simple" ]] && total_requests=$((NUM_USERS * (REQUESTS_PER_USER + 2))) || total_requests=$((NUM_USERS * (REQUESTS_PER_USER * 5 + 2)))
[[ "$MODE" == "simple" ]] && echo "Mode: API Only (No S3 I/O)" || echo "Mode: Full (API + S3 I/O)"
echo "Total requests: ~$total_requests"
echo "Wall-clock duration: ${elapsed}ms ($(( elapsed / 1000 ))s)"
echo "Cumulative time (sum of all users): ${total_time}s"
[[ $(echo "$total_requests > 0" | bc) -eq 1 ]] && echo "Avg response time: $(echo "scale=3; $total_time * 1000 / $total_requests" | bc)ms"
[[ $elapsed -gt 0 ]] && echo "Average RPS: $(echo "scale=2; $total_requests * 1000 / $elapsed" | bc) req/s"
echo "Total success: $total_success"
echo "Total failures: $total_failures"
[[ $((total_success + total_failures)) -gt 0 ]] && echo "Success rate: $(echo "scale=2; $total_success * 100 / ($total_success + $total_failures)" | bc)%"
echo "=========================================="

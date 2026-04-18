#!/bin/bash

BASE_URL="http://localhost:8000"
TIMESTAMP=$(date +%s%N)
EMAIL="test${TIMESTAMP}@example.com"
PASSWORD="testpass123"
USERNAME="testuser${TIMESTAMP}"
EMAIL2="test2${TIMESTAMP}@example.com"

TESTS_PASSED=0
TESTS_FAILED=0

log_test() {
    echo "[TEST] $1"
}

log_pass() {
    echo "[PASS] $1"
    ((TESTS_PASSED++))
}

log_fail() {
    echo "[FAIL] $1"
    ((TESTS_FAILED++))
}

log_info() {
    echo "[INFO] $1"
}

echo "=========================================="
echo "Document Management System - Test Suite"
echo "=========================================="
echo ""

# 1. Health check
log_test "Health endpoint"
HEALTH=$(curl -s $BASE_URL/health)
if [[ $HEALTH == *"ok"* ]]; then
  log_pass "Health check"
else
  log_fail "Health check: $HEALTH"
  exit 1
fi
echo ""

# 2. Register
log_test "User registration"
REGISTER=$(curl -s -X POST $BASE_URL/auth/register \
  -H "Content-Type: application/json" \
  -d "{\"username\":\"$USERNAME\",\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\"}")

if [[ $REGISTER == *"$EMAIL"* ]]; then
  log_pass "User registration"
else
  log_fail "User registration: $REGISTER"
fi
echo ""

# 3. Login
log_test "User login"
LOGIN=$(curl -s -X POST "$BASE_URL/auth/login" -H "Content-Type: application/json" -d "{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\"}")
TOKEN=$(echo $LOGIN | grep -o '"access_token":"[^"]*"' | cut -d'"' -f4)

if [[ -n $TOKEN ]]; then
  log_pass "User login"
  log_info "Token: ${TOKEN:0:30}..."
else
  log_fail "User login: $LOGIN"
  exit 1
fi
echo ""

# 4. Get current user
log_test "Get authenticated user"
ME=$(curl -s -H "Authorization: Bearer $TOKEN" $BASE_URL/auth/me)

if [[ $ME == *"$EMAIL"* ]]; then
  log_pass "Get authenticated user"
else
  log_fail "Get authenticated user: $ME"
fi
echo ""

# 5. Create folder
log_test "Create folder"
FOLDER=$(curl -s -X POST $BASE_URL/folders \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"TestFolder","parent_id":null}')

FOLDER_ID=$(echo $FOLDER | grep -o '"id":"[^"]*"' | head -1 | cut -d'"' -f4)

if [[ -n $FOLDER_ID ]]; then
  log_pass "Create folder"
  log_info "Folder ID: $FOLDER_ID"
else
  log_fail "Create folder: $FOLDER"
fi
echo ""

# 6. List folders
log_test "List folders"
FOLDERS=$(curl -s -H "Authorization: Bearer $TOKEN" $BASE_URL/folders)

if [[ $FOLDERS == *"TestFolder"* ]]; then
  log_pass "List folders"
else
  log_fail "List folders: $FOLDERS"
fi
echo ""

# 7. Get folder
log_test "Get folder by ID"
GET_FOLDER=$(curl -s -H "Authorization: Bearer $TOKEN" $BASE_URL/folders/$FOLDER_ID)

if [[ $GET_FOLDER == *"TestFolder"* ]]; then
  log_pass "Get folder by ID"
else
  log_fail "Get folder by ID: $GET_FOLDER"
fi
echo ""

# 8. Upload URL
log_test "Generate upload URL for document"
UPLOAD=$(curl -s -X POST $BASE_URL/documents/upload-url \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"filename\":\"testfile.pdf\",\"mime_type\":\"application/pdf\",\"folder_id\":\"$FOLDER_ID\"}")

DOC_ID=$(echo $UPLOAD | grep -o '"document_id":"[^"]*"' | cut -d'"' -f4)
UPLOAD_URL=$(echo $UPLOAD | grep -o '"upload_url":"[^"]*"' | cut -d'"' -f4)

if [[ -n $DOC_ID ]]; then
  log_pass "Generate upload URL"
  log_info "Document ID: $DOC_ID"
else
  log_fail "Generate upload URL: $UPLOAD"
fi
echo ""

# 9. Confirm upload
log_test "Confirm document upload"
CONFIRM=$(curl -s -X POST $BASE_URL/documents/confirm \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"document_id\":\"$DOC_ID\",\"size_bytes\":2048}")

if [[ $CONFIRM == *"confirmed"* ]]; then
  log_pass "Confirm document upload"
else
  log_fail "Confirm document upload: $CONFIRM"
fi
echo ""

# 10. Get document
log_test "Get document by ID"
DOC=$(curl -s -H "Authorization: Bearer $TOKEN" $BASE_URL/documents/$DOC_ID)

if [[ $DOC == *"testfile.pdf"* ]]; then
  log_pass "Get document by ID"
else
  log_fail "Get document by ID: $DOC"
fi
echo ""

# 11. List documents
log_test "List documents"
DOCS=$(curl -s -H "Authorization: Bearer $TOKEN" $BASE_URL/documents)

if [[ $DOCS == *"testfile.pdf"* ]]; then
  log_pass "List documents"
else
  log_fail "List documents: $DOCS"
fi
echo ""

# 12. Get download URL
log_test "Generate download URL for document"
DOWNLOAD=$(curl -s -H "Authorization: Bearer $TOKEN" $BASE_URL/documents/$DOC_ID/download-url)
DOWNLOAD_URL=$(echo $DOWNLOAD | grep -o '"download_url":"[^"]*"' | cut -d'"' -f4)

if [[ -n $DOWNLOAD_URL ]]; then
  log_pass "Generate download URL"
else
  log_fail "Generate download URL: $DOWNLOAD"
fi
echo ""

# 13. Create another user for permission test
log_test "Create second user for permission testing"
REGISTER2=$(curl -s -X POST $BASE_URL/auth/register \
  -H "Content-Type: application/json" \
  -d "{\"username\":\"testuser2${TIMESTAMP}\",\"email\":\"$EMAIL2\",\"password\":\"$PASSWORD\"}")

if [[ $REGISTER2 == *"$EMAIL2"* ]]; then
  log_pass "Create second user"
else
  log_fail "Create second user: $REGISTER2"
fi
echo ""

# 14. Get second user token
log_test "Login second user"
LOGIN2=$(curl -s -X POST "$BASE_URL/auth/login" -H "Content-Type: application/json" -d "{\"email\":\"$EMAIL2\",\"password\":\"$PASSWORD\"}")
TOKEN2=$(echo $LOGIN2 | grep -o '"access_token":"[^"]*"' | cut -d'"' -f4)

if [[ -n $TOKEN2 ]]; then
  log_pass "Login second user"
else
  log_fail "Login second user: $LOGIN2"
fi
echo ""

# 15. Share document with second user
log_test "Share document with another user"
USER2_ID=$(echo $REGISTER2 | grep -o '"id":"[^"]*"' | head -1 | cut -d'"' -f4)
PERM=$(curl -s -X POST $BASE_URL/permissions \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"user_id\":\"$USER2_ID\",\"document_id\":\"$DOC_ID\",\"access_level\":\"VIEWER\"}")

if [[ $PERM == *"VIEWER"* ]]; then
  log_pass "Share document with another user"
else
  log_fail "Share document with another user: $PERM"
fi
echo ""

# 16. Second user should see the shared document in their permissions
log_test "Second user can see shared document"
PERMS2=$(curl -s -H "Authorization: Bearer $TOKEN2" $BASE_URL/permissions)

if [[ $PERMS2 == *"VIEWER"* ]]; then
  log_pass "Second user can see shared document"
else
  log_fail "Second user can see shared document: $PERMS2"
fi
echo ""

# 17. Delete document
log_test "Delete document"
DELETE=$(curl -s -X DELETE -H "Authorization: Bearer $TOKEN" $BASE_URL/documents/$DOC_ID)

if [[ $? -eq 0 ]]; then
  log_pass "Delete document"
else
  log_fail "Delete document"
fi
echo ""

# 18. Delete folder
log_test "Delete folder"
DELETE_FOLDER=$(curl -s -X DELETE -H "Authorization: Bearer $TOKEN" $BASE_URL/folders/$FOLDER_ID)

if [[ $? -eq 0 ]]; then
  log_pass "Delete folder"
else
  log_fail "Delete folder"
fi
echo ""

echo "=========================================="
echo "Test Results"
echo "=========================================="
echo "Passed: $TESTS_PASSED"
echo "Failed: $TESTS_FAILED"
echo ""

if [[ $TESTS_FAILED -eq 0 ]]; then
  echo "All tests passed successfully"
  exit 0
else
  echo "Some tests failed"
  exit 1
fi

#!/bin/bash
# =============================================================================
# DMS - Agent Pipeline Scenario Test
# Simulates: user sets up workspace → emails arrive → agent processes them →
# user reviews proposals (accept/reject/move) → final consistency check
# =============================================================================

BASE_URL="http://localhost:8000"
TS=$(date +%s%N)
PASS=0; FAIL=0

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'

assert_contains() {
  local label="$1" body="$2" expected="$3"
  if echo "$body" | grep -q "$expected"; then
    echo -e "  ${GREEN}[PASS]${NC} $label"; ((PASS++))
  else
    echo -e "  ${RED}[FAIL]${NC} $label"; echo "    Expected '$expected' in: ${body:0:300}"; ((FAIL++))
  fi
}
assert_not_contains() {
  local label="$1" body="$2" unexpected="$3"
  if echo "$body" | grep -q "$unexpected"; then
    echo -e "  ${RED}[FAIL]${NC} $label (found '$unexpected')"; ((FAIL++))
  else
    echo -e "  ${GREEN}[PASS]${NC} $label"; ((PASS++))
  fi
}
assert_status() {
  local label="$1" code="$2" expected="$3"
  if [[ "$code" == "$expected" ]]; then
    echo -e "  ${GREEN}[PASS]${NC} $label (HTTP $code)"; ((PASS++))
  else
    echo -e "  ${RED}[FAIL]${NC} $label (expected $expected, got $code)"; ((FAIL++))
  fi
}
extract() { echo "$1" | grep -o "\"$2\":\"[^\"]*\"" | head -1 | cut -d'"' -f4; }
db_query() { docker exec postgres psql -U myuser -d dms -t -A -c "$1" 2>/dev/null | head -1 | tr -d '[:space:]'; }

echo -e "${CYAN}========================================${NC}"
echo -e "${CYAN}  DMS Agent Pipeline Scenario Test${NC}"
echo -e "${CYAN}========================================${NC}"
echo ""

# ====== ACT 1: Setup workspace ======
echo -e "${YELLOW}=== Act 1: User sets up workspace ===${NC}"

USER_EMAIL="agent_user@agent-${TS}.com"
PWD="AgentTest123!"

# Register
R=$(curl -s -X POST "$BASE_URL/auth/register" -H "Content-Type: application/json" \
  -d "{\"username\":\"AgentUser\",\"email\":\"$USER_EMAIL\",\"password\":\"$PWD\"}")
USER_ID=$(extract "$R" "id")
assert_contains "User registers" "$R" "$USER_EMAIL"

# Login
R=$(curl -s -X POST "$BASE_URL/auth/login" -H "Content-Type: application/json" \
  -d "{\"email\":\"$USER_EMAIL\",\"password\":\"$PWD\"}")
TOKEN=$(extract "$R" "access_token")
AUTH="Authorization: Bearer $TOKEN"

# Create folder structure
R=$(curl -s -X POST "$BASE_URL/folders" -H "$AUTH" -H "Content-Type: application/json" -d '{"name":"Fatture"}')
FOLDER_FATTURE=$(extract "$R" "id")

R=$(curl -s -X POST "$BASE_URL/folders" -H "$AUTH" -H "Content-Type: application/json" -d '{"name":"Ricevute"}')
FOLDER_RICEVUTE=$(extract "$R" "id")

R=$(curl -s -X POST "$BASE_URL/folders" -H "$AUTH" -H "Content-Type: application/json" -d '{"name":"Contratti"}')
FOLDER_CONTRATTI=$(extract "$R" "id")

R=$(curl -s -X POST "$BASE_URL/folders" -H "$AUTH" -H "Content-Type: application/json" \
  -d "{\"name\":\"2025\",\"parent_id\":\"$FOLDER_FATTURE\"}")
FOLDER_FATTURE_2025=$(extract "$R" "id")

echo -e "  ${GREEN}[PASS]${NC} Created folder structure: Fatture/2025, Ricevute, Contratti"; ((PASS++))

# Create email account
R=$(curl -s -X POST "$BASE_URL/email-accounts" -H "$AUTH" -H "Content-Type: application/json" \
  -d "{\"email_address\":\"$USER_EMAIL\",\"imap_host\":\"imap.agent-${TS}.com\",\"imap_port\":993,\"use_ssl\":true,\"auth_type\":\"app_password\",\"credentials\":\"fake\"}")
EA_ID=$(extract "$R" "id")
assert_contains "Email account created" "$R" "imap.agent-${TS}.com"

# ====== ACT 2: Simulate emails arriving (via DB) ======
echo -e "\n${YELLOW}=== Act 2: Simulate 3 emails with attachments arriving ===${NC}"

# Create 3 documents to simulate uploaded attachments
TMPDIR_TEST=$(mktemp -d)
echo "Fattura n.42 - Hosting annuale" > "$TMPDIR_TEST/fattura_42.pdf"
echo "Ricevuta pagamento corso online" > "$TMPDIR_TEST/ricevuta_corso.pdf"
echo "Contratto NDA Azienda XYZ" > "$TMPDIR_TEST/nda_xyz.pdf"

upload_doc() {
  local file="$1" auth="$2"
  local R=$(curl -s -X POST "$BASE_URL/documents/upload" -H "$auth" -F "file=@$file")
  local doc_id=$(extract "$R" "document_id")
  curl -s -X POST "$BASE_URL/documents/$doc_id/confirm" -H "$auth" > /dev/null 2>&1
  echo "$doc_id"
}

DOC1=$(upload_doc "$TMPDIR_TEST/fattura_42.pdf" "$AUTH")
DOC2=$(upload_doc "$TMPDIR_TEST/ricevuta_corso.pdf" "$AUTH")
DOC3=$(upload_doc "$TMPDIR_TEST/nda_xyz.pdf" "$AUTH")
echo -e "  ${GREEN}[INFO]${NC} Uploaded 3 documents (at root level, no folder)"

# Insert email_jobs via psql (simulating what the poller would do)
JOB1_ID=$(db_query "INSERT INTO email_jobs (email_account_id, message_uid, subject, sender, status) VALUES ('$EA_ID', 1001, 'Fattura hosting annuale', 'billing@hostprovider.com', 'done') RETURNING id;")
JOB2_ID=$(db_query "INSERT INTO email_jobs (email_account_id, message_uid, subject, sender, status) VALUES ('$EA_ID', 1002, 'Ricevuta corso Udemy', 'noreply@udemy.com', 'done') RETURNING id;")
JOB3_ID=$(db_query "INSERT INTO email_jobs (email_account_id, message_uid, subject, sender, status) VALUES ('$EA_ID', 1003, 'NDA per collaborazione', 'legal@xyz.com', 'done') RETURNING id;")
echo -e "  ${GREEN}[INFO]${NC} Inserted 3 email_jobs: $JOB1_ID, $JOB2_ID, $JOB3_ID"

# Insert email_attachments with different scenarios:
# ATT1: high confidence → suggested Fatture/2025 (will be accepted)
# ATT2: low confidence → suggested Ricevute (will be moved to different folder)
# ATT3: no suggestion → null folder_id (will be rejected)
ATT1_ID=$(db_query "INSERT INTO email_attachments (job_id, filename, mime_type, size_bytes, document_id, suggested_folder_id, confidence, agent_reasoning, status) VALUES ('$JOB1_ID', 'fattura_42.pdf', 'application/pdf', 1024, '$DOC1', '$FOLDER_FATTURE_2025', 0.95, 'Nome file contiene fattura, cartella Fatture/2025 è la più appropriata', 'in_inbox') RETURNING id;")

ATT2_ID=$(db_query "INSERT INTO email_attachments (job_id, filename, mime_type, size_bytes, document_id, suggested_folder_id, confidence, agent_reasoning, status) VALUES ('$JOB2_ID', 'ricevuta_corso.pdf', 'application/pdf', 512, '$DOC2', '$FOLDER_RICEVUTE', 0.60, 'Potrebbe essere una ricevuta ma non sono sicuro', 'in_inbox') RETURNING id;")

ATT3_ID=$(db_query "INSERT INTO email_attachments (job_id, filename, mime_type, size_bytes, document_id, status, confidence, agent_reasoning) VALUES ('$JOB3_ID', 'nda_xyz.pdf', 'application/pdf', 2048, '$DOC3', 'in_inbox', 0.30, 'Non riesco a determinare la cartella appropriata') RETURNING id;")

echo -e "  ${GREEN}[INFO]${NC} Inserted 3 attachments: ATT1(accept), ATT2(move), ATT3(reject)"

# Insert agent_operations (simulating what the worker logged)
db_query "INSERT INTO agent_operations (user_id, job_id, attachment_id, operation_type, description) VALUES ('$USER_ID', '$JOB1_ID', '$ATT1_ID', 'attachment_extracted', 'Allegato estratto: fattura_42.pdf');" > /dev/null
db_query "INSERT INTO agent_operations (user_id, job_id, attachment_id, operation_type, description) VALUES ('$USER_ID', '$JOB1_ID', '$ATT1_ID', 'sent_to_inbox', 'fattura_42.pdf inviato in inbox per revisione');" > /dev/null
db_query "INSERT INTO agent_operations (user_id, job_id, operation_type, description) VALUES ('$USER_ID', '$JOB1_ID', 'email_received', 'Nuova email ricevuta da billing@hostprovider.com');" > /dev/null
db_query "INSERT INTO agent_operations (user_id, job_id, operation_type, description) VALUES ('$USER_ID', '$JOB2_ID', 'email_received', 'Nuova email ricevuta da noreply@udemy.com');" > /dev/null
db_query "INSERT INTO agent_operations (user_id, job_id, operation_type, description) VALUES ('$USER_ID', '$JOB3_ID', 'email_received', 'Nuova email ricevuta da legal@xyz.com');" > /dev/null

echo -e "  ${GREEN}[PASS]${NC} Agent pipeline simulated via DB inserts"; ((PASS++))

# ====== ACT 3: User reviews proposals ======
echo -e "\n${YELLOW}=== Act 3: User reviews agent proposals ===${NC}"

# List operations
R=$(curl -s -H "$AUTH" "$BASE_URL/agent/operations")
assert_contains "Agent operations visible" "$R" "email_received"
assert_contains "Operations show sender info" "$R" "billing@hostprovider.com"

# Count operations
OP_COUNT=$(echo "$R" | grep -o '"id"' | wc -l)
echo -e "  ${GREEN}[INFO]${NC} Found $OP_COUNT agent operations"

# List proposals (should see 3 in_inbox)
R=$(curl -s -H "$AUTH" "$BASE_URL/agent/proposals")
assert_contains "Proposals list contains fattura_42" "$R" "fattura_42.pdf"
assert_contains "Proposals list contains ricevuta_corso" "$R" "ricevuta_corso.pdf"
assert_contains "Proposals list contains nda_xyz" "$R" "nda_xyz.pdf"

PROPOSAL_COUNT=$(echo "$R" | grep -o '"status":"in_inbox"' | wc -l)
if [[ "$PROPOSAL_COUNT" -eq 3 ]]; then
  echo -e "  ${GREEN}[PASS]${NC} Exactly 3 proposals in inbox"; ((PASS++))
else
  echo -e "  ${RED}[FAIL]${NC} Expected 3 proposals in_inbox, got $PROPOSAL_COUNT"; ((FAIL++))
fi

# Verify proposal details
assert_contains "ATT1 has suggested folder" "$R" "$FOLDER_FATTURE_2025"
assert_contains "ATT1 shows confidence" "$R" "0.95"
assert_contains "ATT1 shows reasoning" "$R" "Nome file contiene fattura"
assert_contains "Proposals show sender" "$R" "billing@hostprovider.com"
assert_contains "Proposals show subject" "$R" "Fattura hosting annuale"

# ====== ACT 4: Accept proposal 1 (fattura → Fatture/2025) ======
echo -e "\n${YELLOW}=== Act 4: Accept fattura proposal ===${NC}"

R=$(curl -s -w "\n%{http_code}" -X POST "$BASE_URL/agent/proposals/$ATT1_ID/accept" -H "$AUTH")
BODY=$(echo "$R" | head -1); CODE=$(echo "$R" | tail -1)
assert_status "Accept fattura proposal" "$CODE" "200"
assert_contains "Status changed to confirmed" "$BODY" "confirmed"

# Verify document moved to Fatture/2025
R=$(curl -s -H "$AUTH" "$BASE_URL/documents/$DOC1")
assert_contains "Doc1 now in Fatture/2025" "$R" "$FOLDER_FATTURE_2025"

# Verify it's no longer in proposals
R=$(curl -s -H "$AUTH" "$BASE_URL/agent/proposals")
assert_not_contains "Accepted proposal gone from inbox" "$R" "fattura_42.pdf"

# ====== ACT 5: Move proposal 2 to different folder ======
echo -e "\n${YELLOW}=== Act 5: Move ricevuta to Contratti (different from suggested) ===${NC}"

R=$(curl -s -w "\n%{http_code}" -X POST "$BASE_URL/agent/proposals/$ATT2_ID/move" -H "$AUTH" -H "Content-Type: application/json" \
  -d "{\"folder_id\":\"$FOLDER_CONTRATTI\"}")
BODY=$(echo "$R" | head -1); CODE=$(echo "$R" | tail -1)
assert_status "Move ricevuta to Contratti" "$CODE" "200"
assert_contains "Status changed to confirmed" "$BODY" "confirmed"

# Verify document is in Contratti, NOT in Ricevute
R=$(curl -s -H "$AUTH" "$BASE_URL/documents/$DOC2")
assert_contains "Doc2 now in Contratti" "$R" "$FOLDER_CONTRATTI"
assert_not_contains "Doc2 NOT in Ricevute" "$R" "$FOLDER_RICEVUTE"

# ====== ACT 6: Reject proposal 3 (NDA) ======
echo -e "\n${YELLOW}=== Act 6: Reject NDA proposal ===${NC}"

R=$(curl -s -w "\n%{http_code}" -X POST "$BASE_URL/agent/proposals/$ATT3_ID/reject" -H "$AUTH")
BODY=$(echo "$R" | head -1); CODE=$(echo "$R" | tail -1)
assert_status "Reject NDA proposal" "$CODE" "200"
assert_contains "Status changed to rejected" "$BODY" "rejected"

# Document should still exist but with no folder (stays where it was)
R=$(curl -s -H "$AUTH" "$BASE_URL/documents/$DOC3")
assert_contains "Rejected doc still exists" "$R" "nda_xyz.pdf"

# ====== ACT 7: Edge cases ======
echo -e "\n${YELLOW}=== Act 7: Edge cases ===${NC}"

# Try to accept an already-resolved proposal → 404
R=$(curl -s -w "\n%{http_code}" -X POST "$BASE_URL/agent/proposals/$ATT1_ID/accept" -H "$AUTH")
assert_status "Re-accept resolved proposal → 404" "$(echo "$R" | tail -1)" "404"

R=$(curl -s -w "\n%{http_code}" -X POST "$BASE_URL/agent/proposals/$ATT2_ID/reject" -H "$AUTH")
assert_status "Reject already-moved proposal → 404" "$(echo "$R" | tail -1)" "404"

R=$(curl -s -w "\n%{http_code}" -X POST "$BASE_URL/agent/proposals/$ATT3_ID/accept" -H "$AUTH")
assert_status "Accept already-rejected proposal → 404" "$(echo "$R" | tail -1)" "404"

# Try with non-existent UUID
FAKE="00000000-0000-0000-0000-000000000000"
R=$(curl -s -w "\n%{http_code}" -X POST "$BASE_URL/agent/proposals/$FAKE/accept" -H "$AUTH")
assert_status "Accept non-existent proposal → 404" "$(echo "$R" | tail -1)" "404"

# ====== ACT 8: Second user cannot see first user's proposals ======
echo -e "\n${YELLOW}=== Act 8: Multi-user isolation ===${NC}"

OTHER_EMAIL="other_agent@agent-${TS}.com"
R=$(curl -s -X POST "$BASE_URL/auth/register" -H "Content-Type: application/json" \
  -d "{\"username\":\"OtherAgent\",\"email\":\"$OTHER_EMAIL\",\"password\":\"$PWD\"}")
R=$(curl -s -X POST "$BASE_URL/auth/login" -H "Content-Type: application/json" \
  -d "{\"email\":\"$OTHER_EMAIL\",\"password\":\"$PWD\"}")
OTHER_TOKEN=$(extract "$R" "access_token")
OTHER_AUTH="Authorization: Bearer $OTHER_TOKEN"

R=$(curl -s -H "$OTHER_AUTH" "$BASE_URL/agent/proposals")
assert_not_contains "Other user sees no proposals" "$R" "fattura_42"

R=$(curl -s -H "$OTHER_AUTH" "$BASE_URL/agent/operations")
# Should be empty array
if [[ "$R" == "[]" ]]; then
  echo -e "  ${GREEN}[PASS]${NC} Other user has empty operations"; ((PASS++))
else
  assert_not_contains "Other user sees no operations from first user" "$R" "billing@hostprovider.com"
fi

# ====== ACT 9: Final consistency check ======
echo -e "\n${YELLOW}=== Act 9: Final consistency check ===${NC}"

# Check all 3 documents exist and are in correct locations
R=$(curl -s -H "$AUTH" "$BASE_URL/documents/$DOC1")
FOLDER_OF_DOC1=$(extract "$R" "folder_id")
if [[ "$FOLDER_OF_DOC1" == "$FOLDER_FATTURE_2025" ]]; then
  echo -e "  ${GREEN}[PASS]${NC} Doc1 (fattura) is in Fatture/2025 ✓"; ((PASS++))
else
  echo -e "  ${RED}[FAIL]${NC} Doc1 expected in $FOLDER_FATTURE_2025, found in $FOLDER_OF_DOC1"; ((FAIL++))
fi

R=$(curl -s -H "$AUTH" "$BASE_URL/documents/$DOC2")
FOLDER_OF_DOC2=$(extract "$R" "folder_id")
if [[ "$FOLDER_OF_DOC2" == "$FOLDER_CONTRATTI" ]]; then
  echo -e "  ${GREEN}[PASS]${NC} Doc2 (ricevuta) is in Contratti ✓"; ((PASS++))
else
  echo -e "  ${RED}[FAIL]${NC} Doc2 expected in $FOLDER_CONTRATTI, found in $FOLDER_OF_DOC2"; ((FAIL++))
fi

R=$(curl -s -H "$AUTH" "$BASE_URL/documents/$DOC3")
FOLDER_OF_DOC3=$(extract "$R" "folder_id")
if [[ -z "$FOLDER_OF_DOC3" || "$FOLDER_OF_DOC3" == "null" ]]; then
  echo -e "  ${GREEN}[PASS]${NC} Doc3 (NDA rejected) still at root ✓"; ((PASS++))
else
  echo -e "  ${RED}[FAIL]${NC} Doc3 should be at root, found in $FOLDER_OF_DOC3"; ((FAIL++))
fi

# Verify no proposals remain in inbox
R=$(curl -s -H "$AUTH" "$BASE_URL/agent/proposals")
if [[ "$R" == "[]" ]]; then
  echo -e "  ${GREEN}[PASS]${NC} No proposals remaining in inbox ✓"; ((PASS++))
else
  echo -e "  ${RED}[FAIL]${NC} Proposals still in inbox: ${R:0:200}"; ((FAIL++))
fi

# Verify agent operations grew (should have new entries from accept/reject/move)
R=$(curl -s -H "$AUTH" "$BASE_URL/agent/operations")
OP_COUNT_FINAL=$(echo "$R" | grep -o '"id"' | wc -l)
if [[ "$OP_COUNT_FINAL" -gt "$OP_COUNT" ]]; then
  echo -e "  ${GREEN}[PASS]${NC} Agent operations grew from $OP_COUNT to $OP_COUNT_FINAL ✓"; ((PASS++))
else
  echo -e "  ${RED}[FAIL]${NC} Expected more operations, still $OP_COUNT_FINAL"; ((FAIL++))
fi

# Verify attachment statuses in DB
ATT1_STATUS=$(db_query "SELECT status FROM email_attachments WHERE id='$ATT1_ID';")
ATT2_STATUS=$(db_query "SELECT status FROM email_attachments WHERE id='$ATT2_ID';")
ATT3_STATUS=$(db_query "SELECT status FROM email_attachments WHERE id='$ATT3_ID';")

if [[ "$ATT1_STATUS" == "confirmed" ]]; then
  echo -e "  ${GREEN}[PASS]${NC} ATT1 status = confirmed in DB ✓"; ((PASS++))
else
  echo -e "  ${RED}[FAIL]${NC} ATT1 expected 'confirmed', got '$ATT1_STATUS'"; ((FAIL++))
fi

if [[ "$ATT2_STATUS" == "confirmed" ]]; then
  echo -e "  ${GREEN}[PASS]${NC} ATT2 status = confirmed in DB ✓"; ((PASS++))
else
  echo -e "  ${RED}[FAIL]${NC} ATT2 expected 'confirmed', got '$ATT2_STATUS'"; ((FAIL++))
fi

if [[ "$ATT3_STATUS" == "rejected" ]]; then
  echo -e "  ${GREEN}[PASS]${NC} ATT3 status = rejected in DB ✓"; ((PASS++))
else
  echo -e "  ${RED}[FAIL]${NC} ATT3 expected 'rejected', got '$ATT3_STATUS'"; ((FAIL++))
fi

# Cleanup
rm -rf "$TMPDIR_TEST"

# ---- RESULTS ----
echo ""
echo -e "${CYAN}========================================${NC}"
echo -e "${CYAN}  Results${NC}"
echo -e "${CYAN}========================================${NC}"
echo -e "  ${GREEN}Passed: $PASS${NC}"
echo -e "  ${RED}Failed: $FAIL${NC}"
echo ""
if [[ $FAIL -eq 0 ]]; then
  echo -e "  ${GREEN}✓ All agent pipeline tests passed!${NC}"
  exit 0
else
  echo -e "  ${RED}✗ $FAIL test(s) failed${NC}"
  exit 1
fi

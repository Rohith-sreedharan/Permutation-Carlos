#!/bin/bash
# Section 14 Production Verification - SSH Execution Script
# Run this on production server: 159.203.122.145

set -e

echo "========================================================================"
echo "Section 14 Audit Logging - Production Verification"
echo "Server: 159.203.122.145"
echo "Date: $(date -u +"%Y-%m-%d %H:%M:%S UTC")"
echo "========================================================================"
echo ""

# Step 1: MongoDB Append-Only Role Configuration
echo "STEP 1: MongoDB Append-Only Role Configuration"
echo "========================================================================"

mongosh mongodb://159.203.122.145:27017/beatvegas --eval '
use beatvegas;

// Create append-only role
try {
  db.createRole({
    role: "auditLogAppendOnly",
    privileges: [
      {
        resource: { db: "beatvegas", collection: "decision_audit_logs" },
        actions: ["insert", "find"]
      }
    ],
    roles: []
  });
  print("✅ Role auditLogAppendOnly created successfully");
} catch (e) {
  if (e.codeName === "DuplicateKey") {
    print("⚠️  Role auditLogAppendOnly already exists");
  } else {
    print("❌ Failed to create role: " + e);
    throw e;
  }
}

// Create audit logger user
try {
  db.createUser({
    user: "audit_logger",
    pwd: "AuditLog2026$SecureHash!MongoDB",
    roles: [
      { role: "auditLogAppendOnly", db: "beatvegas" }
    ]
  });
  print("✅ User audit_logger created successfully");
} catch (e) {
  if (e.codeName === "DuplicateKey") {
    print("⚠️  User audit_logger already exists");
  } else {
    print("❌ Failed to create user: " + e);
    throw e;
  }
}

// Verify role
print("\n--- Role Verification ---");
printjson(db.getRole("auditLogAppendOnly", { showPrivileges: true }));
'

echo ""
echo "STEP 2: Test Append-Only Enforcement"
echo "========================================================================"

mongosh mongodb://audit_logger:AuditLog2026\$SecureHash\!MongoDB@159.203.122.145:27017/beatvegas --eval '
use beatvegas;

// Test 1: Insert should SUCCEED
print("\nTest 1: Insert (should SUCCEED)");
try {
  var result = db.decision_audit_logs.insertOne({
    event_id: "test_append_only_" + Date.now(),
    timestamp: new ISODate(),
    classification: "EDGE",
    release_status: "APPROVED",
    test_marker: "SECTION_14_VERIFICATION"
  });
  print("✅ Insert succeeded: " + result.insertedId);
} catch (e) {
  print("❌ Insert failed: " + e);
}

// Test 2: Find should SUCCEED
print("\nTest 2: Find (should SUCCEED)");
try {
  var doc = db.decision_audit_logs.findOne({ test_marker: "SECTION_14_VERIFICATION" });
  if (doc) {
    print("✅ Find succeeded: event_id=" + doc.event_id);
  } else {
    print("⚠️  No test document found");
  }
} catch (e) {
  print("❌ Find failed: " + e);
}

// Test 3: Update should FAIL
print("\nTest 3: Update (should FAIL with not authorized)");
try {
  var result = db.decision_audit_logs.updateOne(
    { test_marker: "SECTION_14_VERIFICATION" },
    { $set: { classification: "LEAN" } }
  );
  print("❌ Update succeeded (SHOULD HAVE FAILED) - Append-only NOT enforced!");
} catch (e) {
  if (e.code === 13 || e.codeName === "Unauthorized") {
    print("✅ Update correctly denied: " + e.codeName);
  } else {
    print("❌ Update failed with unexpected error: " + e);
  }
}

// Test 4: Delete should FAIL
print("\nTest 4: Delete (should FAIL with not authorized)");
try {
  var result = db.decision_audit_logs.deleteOne({ test_marker: "SECTION_14_VERIFICATION" });
  print("❌ Delete succeeded (SHOULD HAVE FAILED) - Append-only NOT enforced!");
} catch (e) {
  if (e.code === 13 || e.codeName === "Unauthorized") {
    print("✅ Delete correctly denied: " + e.codeName);
  } else {
    print("❌ Delete failed with unexpected error: " + e);
  }
}
'

echo ""
echo "STEP 3: Python Production Verification"
echo "========================================================================"

cd /root/permu || cd /home/ubuntu/permu || cd ~/permu || { echo "❌ Cannot find permu directory"; exit 1; }

# Activate virtual environment
if [ -d ".venv" ]; then
    source .venv/bin/activate
elif [ -d "venv" ]; then
    source venv/bin/activate
else
    echo "⚠️  No virtual environment found, using system Python"
fi

# Set MongoDB URI
export MONGO_URI="mongodb://159.203.122.145:27017/"

# Run verification script
python3 backend/verify_section_14.py

echo ""
echo "========================================================================"
echo "Section 14 Verification Complete"
echo "========================================================================"

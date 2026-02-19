# Section 14 Production Verification - Manual Execution Guide

**Server:** 159.203.122.145  
**Username:** root  
**Password:** Carlos$1Permu

---

## Quick Execution Steps

### 1. SSH to Production Server

```bash
ssh root@159.203.122.145
# Password: Carlos$1Permu
```

### 2. Copy Verification Script to Server

From your local machine (separate terminal):
```bash
scp backend/run_production_verification.sh root@159.203.122.145:/tmp/
# Password: Carlos$1Permu
```

### 3. Run Verification Script

On production server:
```bash
chmod +x /tmp/run_production_verification.sh
/tmp/run_production_verification.sh
```

---

## OR: Manual Step-by-Step Execution

If script fails, execute manually:

### Step 1: MongoDB Role Configuration

```bash
ssh root@159.203.122.145

mongosh mongodb://159.203.122.145:27017/beatvegas
```

In MongoDB shell:
```javascript
use beatvegas;

// Create append-only role
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

// Create audit logger user
db.createUser({
  user: "audit_logger",
  pwd: "AuditLog2026$SecureHash!MongoDB",
  roles: [
    { role: "auditLogAppendOnly", db: "beatvegas" }
  ]
});

// Verify role
db.getRole("auditLogAppendOnly", { showPrivileges: true });

exit
```

### Step 2: Test Append-Only Enforcement

```bash
mongosh mongodb://audit_logger:AuditLog2026\$SecureHash\!MongoDB@159.203.122.145:27017/beatvegas
```

In MongoDB shell:
```javascript
use beatvegas;

// Test 1: Insert (should SUCCEED)
db.decision_audit_logs.insertOne({
  event_id: "test_append_only_" + Date.now(),
  timestamp: new ISODate(),
  classification: "EDGE"
});

// Test 2: Find (should SUCCEED)
db.decision_audit_logs.findOne({ event_id: /test_append_only/ });

// Test 3: Update (should FAIL)
db.decision_audit_logs.updateOne(
  { event_id: /test_append_only/ },
  { $set: { classification: "LEAN" } }
);
// Expected: Error: not authorized

// Test 4: Delete (should FAIL)
db.decision_audit_logs.deleteOne({ event_id: /test_append_only/ });
// Expected: Error: not authorized

exit
```

### Step 3: Python Production Verification

```bash
cd /root/permu

# Activate venv
source .venv/bin/activate || source venv/bin/activate

# Set MongoDB URI
export MONGO_URI="mongodb://159.203.122.145:27017/"

# Run verification
python3 backend/verify_section_14.py
```

---

## Expected Results

### MongoDB Role Test:
```
✅ Insert succeeded
✅ Find succeeded
✅ Update correctly denied: Unauthorized
✅ Delete correctly denied: Unauthorized
```

### Python Verification:
```
======================================================================
VERIFICATION SUMMARY
======================================================================
✅ APPROVED Decision Logging: PASS
✅ BLOCKED Decision Logging: PASS
✅ Trace ID Query: PASS
✅ Decision History: PASS
✅ 7-Year Retention: PASS
✅ Production Record Sample: PASS

✅ ALL TESTS PASSED (6/6)
✅ Section 14 Production Verification: ✅ COMPLETE
```

---

## After Successful Execution

1. Copy terminal output
2. Update ENGINE_LOCK_CERTIFICATION_STATUS.md:
   - Section 14: 90% → 100% LOCKED
   - Blocker count: 5 → 4
3. Commit changes
4. Proceed immediately to Section 15: Version Control

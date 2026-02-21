# Section 14 Audit Logging - MongoDB Append-Only Configuration

## REQUIREMENT
Per ENGINE LOCK Specification Section 14, the `decision_audit_logs` collection must be append-only with 7-year retention. No updates or deletions permitted.

## MONGODB ROLE CONFIGURATION

### 1. Create Append-Only Role

Connect to MongoDB and execute:

```javascript
use beatvegas;

// Create custom role with write-only + read permissions
db.createRole({
  role: "auditLogAppendOnly",
  privileges: [
    {
      resource: { db: "beatvegas", collection: "decision_audit_logs" },
      actions: ["insert", "find"]  // ONLY insert and find - NO update, remove, or delete
    }
  ],
  roles: []
});
```

**Critical:** This role grants:
- ✅ `insert` - Write new audit entries
- ✅ `find` - Read audit entries for queries
- ❌ `update` - DENIED (no modifications)
- ❌ `remove` - DENIED (no deletions)
- ❌ `delete` - DENIED (no deletions)

### 2. Create Dedicated Audit User

```javascript
use beatvegas;

// Create user with ONLY append-only permissions
db.createUser({
  user: "audit_logger",
  pwd: "<STRONG_PASSWORD>",  // Generate secure password
  roles: [
    { role: "auditLogAppendOnly", db: "beatvegas" }
  ]
});
```

### 3. Verify Role Permissions

```javascript
use beatvegas;

// Show role details
db.getRole("auditLogAppendOnly", { showPrivileges: true });

// Expected output:
{
  "role": "auditLogAppendOnly",
  "db": "beatvegas",
  "privileges": [
    {
      "resource": { "db": "beatvegas", "collection": "decision_audit_logs" },
      "actions": ["insert", "find"]
    }
  ],
  "roles": []
}
```

### 4. Test Append-Only Enforcement

```javascript
use beatvegas;

// Authenticate as audit user
db.auth("audit_logger", "<PASSWORD>");

// Test 1: Insert should SUCCEED
db.decision_audit_logs.insertOne({
  event_id: "test_event_123",
  timestamp: new Date().toISOString(),
  classification: "EDGE"
});
// Expected: WriteResult({ "nInserted" : 1 })

// Test 2: Find should SUCCEED
db.decision_audit_logs.findOne({ event_id: "test_event_123" });
// Expected: Returns document

// Test 3: Update should FAIL
db.decision_audit_logs.updateOne(
  { event_id: "test_event_123" },
  { $set: { classification: "LEAN" } }
);
// Expected: Error: not authorized on beatvegas to execute command

// Test 4: Delete should FAIL
db.decision_audit_logs.deleteOne({ event_id: "test_event_123" });
// Expected: Error: not authorized on beatvegas to execute command
```

## APPLICATION CONFIGURATION

### Update Connection String

**backend/.env:**
```bash
# Audit logger connection (append-only user)
AUDIT_MONGO_URI=mongodb://audit_logger:<PASSWORD>@159.203.122.145:27017/beatvegas?authSource=beatvegas

# Existing general connection (full permissions for migrations, etc.)
MONGO_URI=mongodb://<admin_user>:<password>@159.203.122.145:27017/beatvegas?authSource=beatvegas
```

**Note:** If using virtual environment, use `.venv` as standard Python convention

### Update DecisionAuditLogger

**backend/db/decision_audit_logger.py:**
```python
import os

class DecisionAuditLogger:
    def __init__(
        self,
        mongo_uri: str = None,
        database: str = "beatvegas"
    ):
        # Use dedicated audit logger connection if available
        if mongo_uri is None:
            mongo_uri = os.getenv("AUDIT_MONGO_URI") or os.getenv("MONGO_URI")
        
        # ... rest of implementation
```

## RETENTION POLICY

MongoDB TTL index is already configured in `_ensure_collection_setup()`:

```python
# TTL index - automatically deletes after 7 years
self.collection.create_index(
    "retention_expires_at",
    expireAfterSeconds=0,
    name="retention_ttl"
)
```

Each document has `retention_expires_at` set to 7 years from creation:
```python
def _calculate_retention_expiry(self) -> str:
    now = datetime.now(timezone.utc)
    expiry = now.replace(year=now.year + 7)  # 7 years
    return expiry.isoformat()
```

MongoDB will automatically delete documents when `retention_expires_at` is reached.

## VERIFICATION CHECKLIST

Before marking Section 14 as LOCKED:

- [ ] `auditLogAppendOnly` role created with only `insert` + `find` actions
- [ ] `audit_logger` user created with role assignment
- [ ] Test insert succeeds
- [ ] Test find succeeds
- [ ] Test update FAILS (unauthorized)
- [ ] Test delete FAILS (unauthorized)
- [ ] Application uses `AUDIT_MONGO_URI` connection
- [ ] Production tests run successfully
- [ ] HTTP 500 failure test passes

## SECURITY NOTES

1. **Password Strength:** Use minimum 32-character password for `audit_logger` user
2. **Network Security:** Ensure MongoDB port 27017 is firewalled, only accessible from application servers
3. **Audit Trail:** All audit log access should itself be logged (MongoDB audit logging if available)
4. **Backup:** Regular backups of `decision_audit_logs` collection (append-only prevents accidental deletion)
5. **Monitoring:** Alert on any unauthorized access attempts to audit collection

## PRODUCTION DEPLOYMENT STEPS

1. Execute role creation on production MongoDB
2. Create `audit_logger` user with secure password
3. Update production `.env` with `AUDIT_MONGO_URI`
4. Restart FastAPI application
5. Run verification tests (see SECTION_14_VERIFICATION.md)
6. Monitor logs for any audit write failures
7. Verify HTTP 500 enforcement with failure injection test

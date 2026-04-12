/*
  FULL GATE CORRECTION MIGRATION
  - Gate 1: append-only billing_ledger
  - Gate 2: canonical decision_records uniqueness
  - Gate 3: decision_id-only server authority (API-level, not DB-level)

  Run with mongosh against target DB.
*/

// -----------------------------------------------------------------------------
// Gate 1 - billing_ledger collection + validator + indexes
// -----------------------------------------------------------------------------

db.createCollection("billing_ledger", {
  validator: {
    $jsonSchema: {
      bsonType: "object",
      required: ["id", "user_id", "event_type", "amount", "reference_id", "created_at"],
      properties: {
        id: { bsonType: "string" },
        user_id: { bsonType: "string" },
        event_type: { enum: ["CHARGE", "CREDIT", "USAGE"] },
        amount: { bsonType: ["double", "int", "long", "decimal"] },
        reference_id: { bsonType: "string" },
        created_at: { bsonType: "string" },
      },
    },
  },
  validationLevel: "strict",
  validationAction: "error",
});

db.billing_ledger.createIndex({ id: 1 }, { unique: true, name: "billing_ledger_id_unique" });
db.billing_ledger.createIndex({ user_id: 1, created_at: -1 }, { name: "billing_ledger_user_created" });
db.billing_ledger.createIndex({ reference_id: 1 }, { name: "billing_ledger_reference_id" });
db.billing_ledger.createIndex({ event_type: 1, created_at: -1 }, { name: "billing_ledger_event_type_created" });

// -----------------------------------------------------------------------------
// Gate 2 - decision_records uniqueness
// -----------------------------------------------------------------------------

db.decision_records.createIndex(
  { event_id: 1, inputs_hash: 1, decision_version: 1 },
  { unique: true, name: "event_inputs_version_unique" }
);

// -----------------------------------------------------------------------------
// Gate 1 - append-only DB role (blocks update/delete on billing_ledger)
// -----------------------------------------------------------------------------

const roleName = "billing_ledger_append_only";
const dbName = db.getName();

const existingRole = db.getSiblingDB(dbName).getRole(roleName, { showPrivileges: true });
if (existingRole) {
  db.getSiblingDB(dbName).dropRole(roleName);
}

db.getSiblingDB(dbName).createRole({
  role: roleName,
  privileges: [
    {
      resource: { db: dbName, collection: "billing_ledger" },
      actions: ["find", "insert"],
    },
    {
      resource: { db: dbName, collection: "ops_alert" },
      actions: ["insert"],
    },
    {
      resource: { db: dbName, collection: "audit_log" },
      actions: ["insert"],
    },
  ],
  roles: [],
});

print("FULL GATE CORRECTION migration applied.");
print("Role created: billing_ledger_append_only (no update/delete on billing_ledger)");

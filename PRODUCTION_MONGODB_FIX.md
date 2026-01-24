# 🔧 PRODUCTION MongoDB Authentication Fix

## Error You're Seeing

```
pymongo.errors.OperationFailure: Command createIndexes requires authentication
```

## Root Cause

Your MongoDB instance requires authentication, but the `MONGO_URI` doesn't include credentials.

---

## ✅ FIX: Update Your MONGO_URI

### Option 1: Include Credentials in URI (Recommended)

```bash
# In your production .env file
MONGO_URI=mongodb://username:password@localhost:27017/beatvegas?authSource=admin
```

### Option 2: If Using MongoDB Atlas

```bash
# Format for MongoDB Atlas
MONGO_URI=mongodb+srv://username:password@cluster.mongodb.net/beatvegas?retryWrites=true&w=majority
```

### Option 3: If Using Docker MongoDB

```bash
# With Docker, use container name
MONGO_URI=mongodb://username:password@mongo:27017/beatvegas?authSource=admin
```

---

## 🔐 MongoDB User Permissions

Your MongoDB user needs **one of these roles**:

### Minimum Required (Production)
```javascript
// In MongoDB shell
use admin
db.createUser({
  user: "parlay_backend",
  pwd: "your_secure_password",
  roles: [
    { role: "readWrite", db: "beatvegas" },
    { role: "dbAdmin", db: "beatvegas" }  // Needed for createIndexes
  ]
})
```

### Alternative (Development Only)
```javascript
// Give full admin (NOT recommended for production)
use admin
db.createUser({
  user: "dev_user",
  pwd: "dev_password",
  roles: ["root"]
})
```

---

## 📝 Step-by-Step Fix

### 1. Connect to MongoDB

```bash
# SSH into production server
ssh user@your-server

# Connect to MongoDB
mongo -u admin -p --authenticationDatabase admin
```

### 2. Create/Update User

```javascript
use admin

// Check existing users
db.getUsers()

// Create new user with correct permissions
db.createUser({
  user: "parlay_backend",
  pwd: "GENERATE_SECURE_PASSWORD_HERE",
  roles: [
    { role: "readWrite", db: "beatvegas" },
    { role: "dbAdmin", db: "beatvegas" }
  ]
})

// Or update existing user
db.updateUser("parlay_backend", {
  roles: [
    { role: "readWrite", db: "beatvegas" },
    { role: "dbAdmin", db: "beatvegas" }
  ]
})
```

### 3. Update Environment Variable

```bash
# Edit .env file on production server
nano /root/permu/backend/.env

# Update this line:
MONGO_URI=mongodb://parlay_backend:YOUR_PASSWORD@localhost:27017/beatvegas?authSource=admin
```

### 4. Restart Backend

```bash
# If using PM2
pm2 restart permu-backend

# If using systemd
systemctl restart parlay-backend

# Check logs
pm2 logs permu-backend --lines 50
```

---

## ✅ Verify Fix

You should see these logs:

```
✅ MongoDB connected successfully to beatvegas
✅ Database indexes created successfully
```

Instead of:

```
❌ MongoDB connection failed
Command createIndexes requires authentication
```

---

## 🔒 Security Best Practices

### 1. Use Strong Passwords
```bash
# Generate secure password
openssl rand -base64 32
```

### 2. Restrict MongoDB Access
```bash
# In MongoDB config (/etc/mongod.conf)
net:
  bindIp: 127.0.0.1  # Only allow local connections
security:
  authorization: enabled
```

### 3. Use Environment Variables (Never Hardcode)
```bash
# ❌ BAD: Hardcoded password
MONGO_URI=mongodb://user:password123@localhost:27017/db

# ✅ GOOD: Use secrets management
MONGO_URI=${MONGODB_CONNECTION_STRING}
```

### 4. Enable SSL/TLS (Production)
```bash
MONGO_URI=mongodb://user:pass@localhost:27017/beatvegas?authSource=admin&tls=true
```

---

## 🐛 Troubleshooting

### Error: "Authentication failed"
```bash
# Check user exists
mongo -u admin -p
use admin
db.getUser("parlay_backend")

# Verify password
mongo -u parlay_backend -p your_password --authenticationDatabase admin
```

### Error: "Connection timeout"
```bash
# Check MongoDB is running
systemctl status mongod

# Check port is accessible
netstat -tlnp | grep 27017

# Check firewall
ufw status
```

### Error: "Database not found"
```bash
# Create database (it's created automatically on first write)
mongo -u parlay_backend -p
use beatvegas
db.test.insertOne({test: 1})
db.test.deleteOne({test: 1})
```

---

## 📊 Test Connection

Run this Python script to verify:

```python
from pymongo import MongoClient
import os

MONGO_URI = os.getenv("MONGO_URI")
print(f"Testing connection: {MONGO_URI.split('@')[1] if '@' in MONGO_URI else MONGO_URI}")

try:
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    client.admin.command('ping')
    print("✅ Connection successful!")
    
    # Test database access
    db = client["beatvegas"]
    db.test.insert_one({"test": 1})
    db.test.delete_one({"test": 1})
    print("✅ Read/Write access confirmed!")
    
except Exception as e:
    print(f"❌ Connection failed: {e}")
```

---

## 🚀 Quick Fix Commands

```bash
# 1. SSH into server
ssh user@production-server

# 2. Edit .env
cd /root/permu/backend
nano .env
# Add: MONGO_URI=mongodb://user:pass@localhost:27017/beatvegas?authSource=admin

# 3. Restart
pm2 restart permu-backend

# 4. Check logs
pm2 logs permu-backend --lines 50 | grep MongoDB
```

---

## 💡 What Changed in Your Code

Updated `backend/db/mongo.py`:

1. **Added connection error handling** - Shows clear error messages
2. **Added authentication guidance** - Logs explain what's wrong
3. **Wrapped ensure_indexes in try/except** - App continues even if indexes fail

These changes make the error more obvious and provide helpful guidance.

---

## 📞 Need Help?

**Check MongoDB logs:**
```bash
tail -f /var/log/mongodb/mongod.log
```

**Check application logs:**
```bash
pm2 logs permu-backend --err --lines 100
```

**Test authentication manually:**
```bash
mongo -u parlay_backend -p --authenticationDatabase admin
```

---

**After fixing:** Your backend should start successfully and create all indexes automatically.

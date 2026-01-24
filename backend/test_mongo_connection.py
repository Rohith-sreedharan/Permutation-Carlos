#!/usr/bin/env python3
"""
Production MongoDB Connection Test
Quick script to verify MONGO_URI is correct
"""
import os
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
print(f"\n🔍 Testing MongoDB Connection")
print(f"=" * 60)

# Show sanitized URI (hide password)
if "@" in MONGO_URI:
    parts = MONGO_URI.split("@")
    auth_part = parts[0].split("//")[1]
    if ":" in auth_part:
        username = auth_part.split(":")[0]
        sanitized = f"mongodb://{username}:****@{parts[1]}"
    else:
        sanitized = MONGO_URI
else:
    sanitized = MONGO_URI

print(f"URI: {sanitized}")
print(f"-" * 60)

try:
    from pymongo import MongoClient
    
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    client.admin.command('ping')
    print("✅ Connection successful!")
    
    # Test database access
    db = client[os.getenv("DATABASE_NAME", "beatvegas")]
    print(f"✅ Database accessible: {db.name}")
    
    # Test write permission
    db.connection_test.insert_one({"test": 1})
    print("✅ Write permission: OK")
    
    # Test index creation
    db.connection_test.create_index("test")
    print("✅ Index creation: OK")
    
    # Cleanup
    db.connection_test.drop()
    print("✅ All tests passed!")
    
except Exception as e:
    print(f"❌ Connection failed: {e}")
    print(f"\n💡 Fix:")
    print(f"   Update .env with:")
    print(f"   MONGO_URI=mongodb://adminUser:YourStrongPassword@127.0.0.1:27017/permu_db?authSource=admin")
    print(f"   DATABASE_NAME=permu_db")
    exit(1)

print(f"=" * 60)
print(f"✅ MongoDB is ready for production")

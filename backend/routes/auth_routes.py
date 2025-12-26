from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime, timezone
import bcrypt

from db.mongo import db
from middleware.auth import get_current_user


class UserRegistration(BaseModel):
    email: EmailStr
    password: str
    username: Optional[str]


class PasskeyLoginRequest(BaseModel):
    email: EmailStr
    credential: dict


router = APIRouter(prefix="/api", tags=["auth"])


def hash_password(password: str) -> str:
    """Hash password using bcrypt directly."""
    # Bcrypt has a 72-byte limit, truncate if necessary
    password_bytes = password.encode('utf-8')[:72]
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode('utf-8')


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against bcrypt hash."""
    # Bcrypt has a 72-byte limit, truncate if necessary
    password_bytes = plain_password.encode('utf-8')[:72]
    hashed_bytes = hashed_password.encode('utf-8')
    return bcrypt.checkpw(password_bytes, hashed_bytes)


@router.post("/auth/register")
def register_user(payload: UserRegistration):
    users = db["users"]
    existing = users.find_one({"email": payload.email})
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User already exists")

    now = datetime.now(timezone.utc).isoformat()
    user_doc = {
        "email": payload.email,
        "username": payload.username or payload.email.split("@")[0],
        "hashed_password": hash_password(payload.password),  # Use bcrypt
        "tier": "free",  # Assign FREE tier by default
        "iteration_limit": 10000,  # FREE tier gets 10,000 iterations
        "simulations_today": 0,  # Track daily simulation count
        "last_simulation_date": None,  # Track last simulation date
        "created_at": now,
    }

    res = users.insert_one(user_doc)
    return {"status": "ok", "user_id": str(res.inserted_id), "email": payload.email}


@router.post("/token")
def token(form_data: OAuth2PasswordRequestForm = Depends()):
    users = db["users"]
    user = users.find_one({"email": form_data.username})
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    # Check both old field name (password_hash) and new field name (hashed_password)
    stored_hash = user.get("hashed_password") or user.get("password_hash")
    if not stored_hash:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    
    # Verify password using bcrypt
    if not verify_password(form_data.password, stored_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    # Check if 2FA is enabled
    if user.get("two_factor_enabled"):
        # Return a special response indicating 2FA is required
        return {
            "requires_2fa": True,
            "temp_token": f"temp:{str(user.get('_id'))}",
            "message": "Two-factor authentication required"
        }
    
    # Simple token for development: not a JWT, just a placeholder string
    token_value = f"user:{str(user.get('_id'))}"
    return {"access_token": token_value, "token_type": "bearer"}


@router.post("/verify-2fa")
def verify_2fa_login(temp_token: str, code: str):
    """Verify 2FA code and complete login"""
    # Extract user ID from temp token
    if not temp_token.startswith('temp:'):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    
    user_id = temp_token.split(':', 1)[1]
    
    try:
        from bson import ObjectId
        oid = ObjectId(user_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    
    user = db["users"].find_one({"_id": oid})
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    
    if not user.get("two_factor_enabled"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="2FA not enabled")
    
    secret = user.get("two_factor_secret")
    if not secret:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="2FA not configured")
    
    try:
        import pyotp
        totp = pyotp.TOTP(secret)
        if not totp.verify(code, valid_window=1):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid verification code")
    except ImportError:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="2FA not available"
        )
    
    # Issue real token
    token_value = f"user:{str(user.get('_id'))}"
    return {"access_token": token_value, "token_type": "bearer"}


@router.post("/passkey/login-begin")
def begin_passkey_login(email: str):
    """Start passkey login (passwordless authentication)"""
    from bson import ObjectId
    import base64
    
    user = db["users"].find_one({"email": email})
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    
    if not user.get("passkey_enabled"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Passkey not enabled for this account")
    
    try:
        from webauthn import generate_authentication_options
        from webauthn.helpers.structs import PublicKeyCredentialDescriptor
        
        # Get user's credentials
        credentials = user.get("passkey_credentials", [])
        if not credentials:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No passkeys registered")
        
        allow_credentials = [
            PublicKeyCredentialDescriptor(id=base64.b64decode(cred["id"]))
            for cred in credentials
        ]
        
        options = generate_authentication_options(
            rp_id="localhost",
            allow_credentials=allow_credentials,
        )
        
        # Store challenge
        user_id = str(user.get('_id'))
        oid = ObjectId(user_id)
        db['users'].update_one(
            {"_id": oid},
            {"$set": {"passkey_auth_challenge": base64.b64encode(options.challenge).decode()}}
        )
        
        return {
            "challenge": base64.b64encode(options.challenge).decode(),
            "timeout": 60000,
            "rpId": "localhost",
            "allowCredentials": [
                {
                    "type": "public-key",
                    "id": cred["id"],
                    "transports": cred.get("transports", ["internal"])
                }
                for cred in credentials
            ],
            "userVerification": "preferred"
        }
    except ImportError:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="WebAuthn not available"
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/passkey/login-complete")
def complete_passkey_login(payload: PasskeyLoginRequest):
    """Complete passkey login"""
    import base64
    from bson import ObjectId
    
    print(f"[PASSKEY LOGIN] Attempting login for: {payload.email}")
    
    user = db["users"].find_one({"email": payload.email})
    if not user:
        print(f"[PASSKEY LOGIN] User not found: {payload.email}")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email address")
    
    # Check if user has any passkeys registered
    passkeys = user.get("passkey_credentials", [])
    print(f"[PASSKEY LOGIN] User has {len(passkeys)} passkeys registered")
    
    if not passkeys:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="No passkeys registered. Please register a passkey first by logging in with password and going to Settings."
        )
    
    stored_challenge = user.get("passkey_auth_challenge")
    if not stored_challenge:
        print(f"[PASSKEY LOGIN] No challenge found for user")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No pending authentication. Please start login again.")
    
    print(f"[PASSKEY LOGIN] Challenge exists, credential ID: {payload.credential.get('id')[:30]}...")
    
    try:
        from webauthn import verify_authentication_response
        from webauthn.helpers.structs import AuthenticationCredential
        
        # Find the credential
        credential_id = payload.credential.get("id")
        print(f"[PASSKEY LOGIN] Looking for credential: {credential_id[:30]}...")
        print(f"[PASSKEY LOGIN] Stored credentials: {[c['id'][:30]+'...' for c in user.get('passkey_credentials', [])]}")
        
        # Normalize base64 padding for comparison (strip trailing = signs)
        normalized_credential_id = credential_id.rstrip('=')
        
        stored_credential = next(
            (c for c in user.get("passkey_credentials", []) if c["id"].rstrip('=') == normalized_credential_id),
            None
        )
        
        if not stored_credential:
            print(f"[PASSKEY LOGIN] ERROR: Credential not found!")
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credential - not registered")
        
        print(f"[PASSKEY LOGIN] Found stored credential, verifying...")
        
        # Decode base64-encoded fields to bytes
        raw_id_bytes = base64.b64decode(payload.credential.get("rawId"))
        client_data_json_bytes = base64.b64decode(payload.credential["response"]["clientDataJSON"])
        authenticator_data_bytes = base64.b64decode(payload.credential["response"]["authenticatorData"])
        signature_bytes = base64.b64decode(payload.credential["response"]["signature"])
        
        # Construct response object
        from webauthn.helpers.structs import AuthenticatorAssertionResponse
        assertion_response = AuthenticatorAssertionResponse(
            client_data_json=client_data_json_bytes,
            authenticator_data=authenticator_data_bytes,
            signature=signature_bytes,
        )
        
        # Construct the credential object
        auth_credential = AuthenticationCredential(
            id=payload.credential.get("id"),
            raw_id=raw_id_bytes,
            response=assertion_response,
            type=payload.credential.get("type", "public-key")
        )
        
        print(f"[PASSKEY LOGIN] Calling webauthn verification...")
        
        # Verify the authentication
        verification = verify_authentication_response(
            credential=auth_credential,
            expected_challenge=base64.b64decode(stored_challenge),
            expected_origin="http://localhost:3000",
            expected_rp_id="localhost",
            credential_public_key=base64.b64decode(stored_credential["public_key"]),
            credential_current_sign_count=stored_credential["sign_count"],
        )
        
        # Update sign count
        user_id = str(user.get('_id'))
        oid = ObjectId(user_id)
        db['users'].update_one(
            {"_id": oid, "passkey_credentials.id": credential_id},
            {
                "$set": {"passkey_credentials.$.sign_count": verification.new_sign_count},
                "$unset": {"passkey_auth_challenge": ""}
            }
        )
        
        # Issue token
        token_value = f"user:{user_id}"
        return {"access_token": token_value, "token_type": "bearer"}
        
    except ImportError:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="WebAuthn not available"
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication failed")


@router.get("/users/me")
def get_current_user_profile(user: dict = Depends(get_current_user)):
    """
    SECURITY ENDPOINT: Verify token and return current user data.
    
    This endpoint:
    1. Validates the Authorization token
    2. Checks if user exists in database
    3. Returns user profile if valid
    4. Returns 401 if token is invalid or user doesn't exist
    
    Used by frontend to verify authentication before granting access.
    """
    # Convert ObjectId to string for JSON serialization
    user_data = {
        "id": str(user.get("_id")),
        "email": user.get("email"),
        "username": user.get("username"),
        "tier": user.get("tier", "free"),
        "iteration_limit": user.get("iteration_limit", 10000),
        "created_at": user.get("created_at")
    }
    return user_data

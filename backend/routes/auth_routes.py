import os
from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime, timedelta, timezone
import bcrypt

from db.mongo import db
from middleware.auth import get_current_user


# ── JWT helpers ──────────────────────────────────────────────────────────────

def _get_jwt_secret() -> str:
    secret = os.getenv("JWT_SECRET_KEY", "")
    if not secret:
        raise RuntimeError(
            "JWT_SECRET_KEY is not set. Set it in backend/.env before starting."
        )
    return secret


def create_access_token(user_id: str, email: str, tier: str) -> str:
    """Create a signed JWT access token.  Expiry from agent_config."""
    try:
        from config.agent_config import AGENT_CONFIG
        expire_min = int(AGENT_CONFIG["auth"]["jwt_access_token_expire_minutes"])
        algorithm = AGENT_CONFIG["auth"]["jwt_algorithm"]
    except Exception:
        expire_min = 60
        algorithm = "HS256"

    import jwt  # PyJWT
    payload = {
        "sub": user_id,
        "email": email,
        "tier": tier,
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(minutes=expire_min),
    }
    return jwt.encode(payload, _get_jwt_secret(), algorithm=algorithm)


class UserRegistration(BaseModel):
    email: EmailStr
    password: str
    username: Optional[str] = None


class PasskeyLoginRequest(BaseModel):
    email: EmailStr
    credential: dict


router = APIRouter(prefix="/api", tags=["auth"])

# v1-prefixed router — mirrors /api/* at /api/v1/* for versioned clients
router_v1 = APIRouter(prefix="/api/v1", tags=["auth"])


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
@router_v1.post("/auth/register")
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
        "onboarding_complete": False,  # Phase 5A: gates dashboard access
        "credits_used": 0,  # Phase 5B: tracks credit usage for upgrade prompt
        "created_at": now,
    }

    res = users.insert_one(user_doc)
    user_id = str(res.inserted_id)

    # Phase 5B AC-1: Trigger Growth Agent onboarding sequence within 60 seconds
    try:
        from services.phase5_growth_agent import growth_agent
        growth_agent.trigger_onboarding_sequence(user_id=user_id)
        # Intelligence Preview conversion sequence — T+0 welcome
        growth_agent.trigger_preview_welcome(user_id=user_id)
    except Exception as _ga_exc:
        # Non-fatal — registration succeeds even if growth agent call fails
        import logging
        logging.getLogger(__name__).error(
            f"[auth_routes] Growth Agent onboarding trigger failed for user_id={user_id}: {_ga_exc}"
        )

    # Issue access token so the frontend can auto-login immediately after registration
    access_token = create_access_token(user_id=user_id, email=payload.email, tier="free")
    return {"status": "ok", "user_id": user_id, "email": payload.email, "access_token": access_token, "token_type": "bearer"}


@router.post("/token")
@router_v1.post("/token")
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

    if user.get("self_excluded"):
        trace_id = user.get("self_exclusion_trace_id")
        db["sentinel_event_log"].insert_one({
            "event_type": "SELF_EXCLUSION_BYPASS",
            "severity": "CRITICAL",
            "user_id": str(user.get("_id")),
            "trace_id": trace_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agent_id": "agent.sentinel.v1",
            "reason": "Excluded user attempted login",
        })
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="SELF_EXCLUDED")

    # Check if 2FA is enabled
    if user.get("two_factor_enabled"):
        # Return a special response indicating 2FA is required
        return {
            "requires_2fa": True,
            "temp_token": f"temp:{str(user.get('_id'))}",
            "message": "Two-factor authentication required"
        }
    
    token_value = create_access_token(
        user_id=str(user.get("_id")),
        email=user.get("email", ""),
        tier=user.get("tier", "free"),
    )
    return {"access_token": token_value, "token_type": "bearer"}


@router.post("/verify-2fa")
@router_v1.post("/verify-2fa")
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
    
    # Issue real JWT token after 2FA
    token_value = create_access_token(
        user_id=str(user.get("_id")),
        email=user.get("email", ""),
        tier=user.get("tier", "free"),
    )
    return {"access_token": token_value, "token_type": "bearer"}


# ── Apple Sign In — Phase 2A.2 ────────────────────────────────────────────────

class AppleSignInRequest(BaseModel):
    identity_token: str          # JWT from Apple's Sign in with Apple
    authorization_code: str      # one-time code from Apple
    full_name: Optional[str] = None  # only sent on first sign-in


@router.post("/auth/apple")
def apple_sign_in(payload: AppleSignInRequest):
    """
    Verify Apple Sign In identity_token, then issue a BeatVegas JWT.

    Apple's identity_token is a signed JWT whose public key lives at
    https://appleid.apple.com/auth/keys  (cached here via PyJWT's JWKS support).

    Steps:
      1. Fetch Apple's public keys (JWKS endpoint)
      2. Verify identity_token signature + exp + aud (must match APPLE_CLIENT_ID)
      3. Extract sub (Apple user ID) and email from claims
      4. Upsert the user in MongoDB (create if first sign-in)
      5. Return a BeatVegas JWT
    """
    import jwt as _jwt
    import requests as _req

    apple_client_id = os.getenv("APPLE_CLIENT_ID", "")
    if not apple_client_id:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Apple Sign In not configured (APPLE_CLIENT_ID missing)",
        )

    # ── 1. Fetch Apple's public keys ──────────────────────────────────────────
    try:
        jwks_resp = _req.get("https://appleid.apple.com/auth/keys", timeout=10)
        jwks_resp.raise_for_status()
        jwks = jwks_resp.json()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Unable to fetch Apple public keys",
        )

    # ── 2. Identify key from token header and verify ──────────────────────────
    try:
        unverified_header = _jwt.get_unverified_header(payload.identity_token)
        kid = unverified_header.get("kid")
        alg = unverified_header.get("alg", "RS256")

        apple_key = None
        for key_data in jwks.get("keys", []):
            if key_data.get("kid") == kid:
                apple_key = _jwt.algorithms.RSAAlgorithm.from_jwk(key_data)
                break

        if not apple_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Apple public key not found for token",
            )

        claims = _jwt.decode(
            payload.identity_token,
            apple_key,
            algorithms=[alg],
            audience=apple_client_id,
            issuer="https://appleid.apple.com",
        )
    except _jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Apple identity token expired",
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Apple identity token verification failed",
        )

    apple_sub = claims.get("sub")        # stable Apple user ID
    apple_email = claims.get("email")    # may be private relay address

    if not apple_sub:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Apple identity token: missing sub",
        )

    # ── 3. Upsert user ────────────────────────────────────────────────────────
    from bson import ObjectId

    existing_user = db["users"].find_one({"apple_sub": apple_sub})

    if existing_user:
        user = existing_user
    else:
        # First sign-in — create account
        email_to_store = apple_email or f"apple_{apple_sub}@privaterelay.appleid.com"
        new_user = {
            "email": email_to_store,
            "apple_sub": apple_sub,
            "username": payload.full_name or email_to_store.split("@")[0],
            "tier": "free",
            "auth_provider": "apple",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        result = db["users"].insert_one(new_user)
        new_user["_id"] = result.inserted_id
        user = new_user

    # ── 4. Issue BeatVegas JWT ─────────────────────────────────────────────────
    token_value = create_access_token(
        user_id=str(user.get("_id")),
        email=str(user.get("email", "")),
        tier=str(user.get("tier", "free")),
    )
    return {"access_token": token_value, "token_type": "bearer"}


# ── Apple Sign In — Phase 2A.2 ───────────────────────────────────────────────

class AppleSignInRequest(BaseModel):
    identity_token: str          # JWT issued by Apple's auth server
    authorization_code: str      # Single-use code for server-side validation
    first_name: Optional[str] = None
    last_name: Optional[str] = None


@router.post("/auth/apple")
def apple_sign_in(payload: AppleSignInRequest):
    """
    Apple Sign In for Web — RFC-compliant server-side verification.

    1. Fetches Apple's public JWKS from https://appleid.apple.com/auth/keys
    2. Validates the identity_token signature, iss, aud, exp claims
    3. Finds or creates a user record (no plaintext password stored)
    4. Issues a BeatVegas JWT

    Env vars required:
      APPLE_CLIENT_ID   — Service ID (e.g. app.beatvegas.web)
      APPLE_TEAM_ID     — 10-char Apple Team ID
    """
    import json as _json
    import urllib.request

    client_id = os.getenv("APPLE_CLIENT_ID", "")
    if not client_id:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Apple Sign In not configured on this server (APPLE_CLIENT_ID missing)",
        )

    # ── 1. Fetch Apple's public keys ─────────────────────────────────────────
    try:
        with urllib.request.urlopen(
            "https://appleid.apple.com/auth/keys", timeout=10
        ) as resp:
            jwks = _json.loads(resp.read())
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Could not reach Apple auth server: {exc}",
        )

    # ── 2. Decode + verify identity token ────────────────────────────────────
    try:
        import jwt as pyjwt
        from jwt.algorithms import RSAAlgorithm  # type: ignore

        # Find the matching key by 'kid' in the token header
        unverified_header = pyjwt.get_unverified_header(payload.identity_token)
        kid = unverified_header.get("kid")
        matching_key = next(
            (k for k in jwks.get("keys", []) if k.get("kid") == kid), None
        )
        if not matching_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Apple public key not found for token kid",
            )

        public_key = RSAAlgorithm.from_jwk(_json.dumps(matching_key))
        claims = pyjwt.decode(
            payload.identity_token,
            public_key,
            algorithms=["RS256"],
            audience=client_id,
            issuer="https://appleid.apple.com",
        )
    except pyjwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Apple identity token has expired",
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Apple identity token validation failed: {type(exc).__name__}",
        )

    apple_user_id: str = claims.get("sub", "")
    email: str = claims.get("email", "")
    if not apple_user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Apple identity token missing subject claim",
        )

    # ── 3. Find or create user ────────────────────────────────────────────────
    user = db["users"].find_one({"apple_user_id": apple_user_id})
    if not user:
        # First sign-in — create account (no password; Apple-only auth)
        from bson import ObjectId

        now_iso = datetime.now(timezone.utc).isoformat()
        new_user = {
            "apple_user_id": apple_user_id,
            "email": email,
            "username": payload.first_name or email.split("@")[0],
            "tier": "free",
            "auth_provider": "apple",
            "created_at": now_iso,
            "updated_at": now_iso,
        }
        result = db["users"].insert_one(new_user)
        new_user["_id"] = result.inserted_id
        user = new_user

    # ── 4. Issue BeatVegas JWT ────────────────────────────────────────────────
    token_value = create_access_token(
        user_id=str(user.get("_id")),
        email=str(user.get("email", "")),
        tier=str(user.get("tier", "free")),
    )
    return {
        "access_token": token_value,
        "token_type": "bearer",
        "is_new_user": "apple_user_id" not in (user or {}),
    }


# ── Passkey ───────────────────────────────────────────────────────────────────

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


# ── Password reset ───────────────────────────────────────────────────────────

class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


@router.post("/auth/forgot-password", status_code=status.HTTP_200_OK)
def forgot_password(payload: ForgotPasswordRequest):
    """
    Request a password reset link.
    Always returns 200 to prevent email enumeration — no error if email not found.
    """
    from services.transactional_email_service import send_password_reset

    user = db["users"].find_one({"email": payload.email}, {"_id": 1, "email": 1})
    if user:
        send_password_reset(
            user_id=str(user["_id"]),
            user_email=str(user["email"]),
        )
    return {"status": "ok", "message": "If that email is registered you will receive a reset link shortly."}


@router.post("/auth/reset-password", status_code=status.HTTP_200_OK)
def reset_password(payload: ResetPasswordRequest):
    """
    Consume a one-time reset token and set a new password.
    Token must be unused and not expired (15-minute window).
    """
    from services.transactional_email_service import consume_reset_token

    if len(payload.new_password) < 8:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Password must be at least 8 characters.",
        )

    user_id = consume_reset_token(payload.token)
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reset link is invalid or has expired.",
        )

    try:
        from bson import ObjectId
        oid = ObjectId(user_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid token.")

    db["users"].update_one(
        {"_id": oid},
        {"$set": {"hashed_password": hash_password(payload.new_password),
                   "updated_at": datetime.now(timezone.utc).isoformat()}},
    )
    return {"status": "ok", "message": "Password updated. You can now sign in."}


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

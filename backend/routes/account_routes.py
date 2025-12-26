from fastapi import APIRouter, HTTPException, status, Header
from typing import Optional, Dict, Any, List
from bson import ObjectId
from pydantic import BaseModel
from datetime import datetime, timezone
import bcrypt
import secrets
import base64
from db.mongo import db

router = APIRouter(prefix="/api/account", tags=["account"])


class WebAuthnCredential(BaseModel):
    id: str
    public_key: str
    sign_count: int
    transports: Optional[List[str]] = None


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class Enable2FAResponse(BaseModel):
    secret: str
    qr_code_url: str


class Verify2FARequest(BaseModel):
    code: str


class Disable2FARequest(BaseModel):
    password: str


class DeleteAccountRequest(BaseModel):
    password: str
    confirmation: str  # Must be "DELETE"


def _get_user_id_from_auth(authorization: Optional[str]) -> str:
    if not authorization:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing Authorization header")
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != 'bearer':
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Authorization header")
    token = parts[1]
    # dev token format: "user:<id>"
    if not token.startswith('user:'):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token format")
    return token.split(':', 1)[1]


def _find_user_by_id(id_str: str) -> Optional[Dict[str, Any]]:
    try:
        oid = ObjectId(id_str)
    except Exception:
        return None
    return db['users'].find_one({"_id": oid})


@router.get("/profile")
def get_profile(Authorization: Optional[str] = Header(None)):
    user_id = _get_user_id_from_auth(Authorization)
    user = _find_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    profile = {
        "id": str(user.get("_id")),
        "email": user.get("email"),
        "username": user.get("username"),
        "avatarUrl": user.get("avatarUrl") or f"https://i.pravatar.cc/150?u={user.get('email')}",
        "created_at": user.get("created_at"),
        "score": user.get("score", 0),
        "streaks": user.get("streaks", 0),
        "tier": user.get("tier", "starter")
    }
    return {"profile": profile}


@router.get("/wallet")
def get_wallet(Authorization: Optional[str] = Header(None)):
    user_id = _get_user_id_from_auth(Authorization)
    user = _find_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    # Wallet fields stored on user doc under `wallet` or create defaults
    wallet = user.get("wallet", {
        "balance": 0.0,
        "currency": "USD",
        "transactions": [],
    })

    # Normalize transaction IDs to strings
    txs = []
    for t in wallet.get("transactions", []):
        tx = dict(t)
        if tx.get("_id"):
            tx["id"] = str(tx.pop("_id"))
        txs.append(tx)
    wallet["transactions"] = txs

    return {"wallet": wallet}


@router.get("/settings")
def get_settings(Authorization: Optional[str] = Header(None)):
    user_id = _get_user_id_from_auth(Authorization)
    user = _find_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    settings = user.get("settings", {
        "email_notifications": True,
        "sms_notifications": False,
        "theme": "dark",
    })
    return {"settings": settings}


@router.get("/subscription")
def get_subscription(user_id: str):
    """Legacy endpoint for backward compatibility - redirects to /api/subscription/status"""
    try:
        user = _find_user_by_id(user_id)
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        
        return {
            "tier": user.get("tier", "starter"),
            "tier_level": user.get("tier", "starter"),  # Legacy field
            "status": "active"
        }
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.put("/settings")
def update_settings(payload: Dict[str, Any], Authorization: Optional[str] = Header(None)):
    user_id = _get_user_id_from_auth(Authorization)
    try:
        oid = ObjectId(user_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid user id in token")

    # Only allow updating settings subdocument
    update = {"$set": {f"settings.{k}": v for k, v in payload.items()}}
    db['users'].update_one({"_id": oid}, update)
    user = db['users'].find_one({"_id": oid})
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found after update")
    return {"settings": user.get("settings", {})}


@router.post("/change-password")
def change_password(payload: ChangePasswordRequest, Authorization: Optional[str] = Header(None)):
    """Change user password"""
    user_id = _get_user_id_from_auth(Authorization)
    user = _find_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    
    # Verify current password
    stored_hash = user.get("hashed_password") or user.get("password_hash")
    if not stored_hash:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No password set")
    
    password_bytes = payload.current_password.encode('utf-8')[:72]
    hashed_bytes = stored_hash.encode('utf-8')
    if not bcrypt.checkpw(password_bytes, hashed_bytes):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Current password is incorrect")
    
    # Hash new password
    new_password_bytes = payload.new_password.encode('utf-8')[:72]
    salt = bcrypt.gensalt()
    new_hashed = bcrypt.hashpw(new_password_bytes, salt).decode('utf-8')
    
    # Update password
    try:
        oid = ObjectId(user_id)
        db['users'].update_one(
            {"_id": oid},
            {"$set": {
                "hashed_password": new_hashed,
                "password_updated_at": datetime.now(timezone.utc).isoformat()
            }}
        )
        return {"status": "success", "message": "Password changed successfully"}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/2fa/enable")
def enable_2fa(Authorization: Optional[str] = Header(None)):
    """Enable Two-Factor Authentication"""
    user_id = _get_user_id_from_auth(Authorization)
    user = _find_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    
    # Check if already enabled
    if user.get("two_factor_enabled"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="2FA is already enabled")
    
    try:
        import pyotp
        import qrcode
        from io import BytesIO
        import base64
        
        # Generate secret
        secret = pyotp.random_base32()
        
        # Create provisioning URI
        email = user.get("email", "user@beatvegas.com")
        uri = pyotp.totp.TOTP(secret).provisioning_uri(
            name=email,
            issuer_name="BeatVegas"
        )
        
        # Generate QR code
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(uri)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Convert to base64
        buffered = BytesIO()
        img.save(buffered, format="PNG")
        qr_code_base64 = base64.b64encode(buffered.getvalue()).decode()
        
        # Store secret temporarily (will be confirmed on verification)
        oid = ObjectId(user_id)
        db['users'].update_one(
            {"_id": oid},
            {"$set": {"two_factor_secret_pending": secret}}
        )
        
        return {
            "secret": secret,
            "qr_code_url": f"data:image/png;base64,{qr_code_base64}",
            "message": "Scan this QR code with your authenticator app"
        }
    except ImportError:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="2FA not available. Install pyotp and qrcode packages."
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/2fa/verify")
def verify_2fa(payload: Verify2FARequest, Authorization: Optional[str] = Header(None)):
    """Verify and confirm 2FA setup"""
    user_id = _get_user_id_from_auth(Authorization)
    user = _find_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    
    secret = user.get("two_factor_secret_pending")
    if not secret:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No pending 2FA setup")
    
    try:
        import pyotp
        
        totp = pyotp.TOTP(secret)
        if not totp.verify(payload.code, valid_window=1):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid verification code")
        
        # Enable 2FA
        oid = ObjectId(user_id)
        db['users'].update_one(
            {"_id": oid},
            {
                "$set": {
                    "two_factor_enabled": True,
                    "two_factor_secret": secret,
                    "two_factor_enabled_at": datetime.now(timezone.utc).isoformat()
                },
                "$unset": {"two_factor_secret_pending": ""}
            }
        )
        
        return {"status": "success", "message": "Two-factor authentication enabled"}
    except ImportError:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="2FA not available. Install pyotp package."
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/2fa/disable")
def disable_2fa(payload: Disable2FARequest, Authorization: Optional[str] = Header(None)):
    """Disable Two-Factor Authentication"""
    user_id = _get_user_id_from_auth(Authorization)
    user = _find_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    
    if not user.get("two_factor_enabled"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="2FA is not enabled")
    
    # Verify password
    stored_hash = user.get("hashed_password") or user.get("password_hash")
    if stored_hash:
        password_bytes = payload.password.encode('utf-8')[:72]
        hashed_bytes = stored_hash.encode('utf-8')
        if not bcrypt.checkpw(password_bytes, hashed_bytes):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect password")
    
    # Disable 2FA
    oid = ObjectId(user_id)
    db['users'].update_one(
        {"_id": oid},
        {
            "$set": {"two_factor_enabled": False},
            "$unset": {"two_factor_secret": "", "two_factor_secret_pending": ""}
        }
    )
    
    return {"status": "success", "message": "Two-factor authentication disabled"}


@router.get("/2fa/status")
def get_2fa_status(Authorization: Optional[str] = Header(None)):
    """Get 2FA status for current user"""
    user_id = _get_user_id_from_auth(Authorization)
    user = _find_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    
    return {
        "enabled": user.get("two_factor_enabled", False),
        "enabled_at": user.get("two_factor_enabled_at")
    }


@router.delete("/delete")
def delete_account(payload: DeleteAccountRequest, Authorization: Optional[str] = Header(None)):
    """Delete user account permanently"""
    user_id = _get_user_id_from_auth(Authorization)
    user = _find_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    
    # Verify password
    stored_hash = user.get("hashed_password") or user.get("password_hash")
    if stored_hash:
        password_bytes = payload.password.encode('utf-8')[:72]
        hashed_bytes = stored_hash.encode('utf-8')
        if not bcrypt.checkpw(password_bytes, hashed_bytes):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect password")
    
    # Verify confirmation
    if payload.confirmation != "DELETE":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Confirmation must be exactly "DELETE"'
        )
    
    try:
        oid = ObjectId(user_id)
        
        # Delete user data from all collections
        db['users'].delete_one({"_id": oid})
        db['subscriptions'].delete_many({"user_id": user_id})
        db['user_entitlements'].delete_many({"user_id": user_id})
        db['telegram_integrations'].delete_many({"user_id": user_id})
        db['telegram_subscriptions'].delete_many({"user_id": user_id})
        db['notifications'].delete_many({"user_id": user_id})
        
        return {
            "status": "success",
            "message": "Account deleted successfully"
        }
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


# ========================================================================
# WEBAUTHN / PASSKEY AUTHENTICATION
# ========================================================================

@router.post("/passkey/register-begin")
def begin_passkey_registration(Authorization: Optional[str] = Header(None)):
    """Start passkey registration (Face ID, Touch ID, Windows Hello, etc.)"""
    user_id = _get_user_id_from_auth(Authorization)
    user = _find_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    
    try:
        from webauthn import generate_registration_options
        from webauthn.helpers.structs import (
            PublicKeyCredentialDescriptor,
            AuthenticatorSelectionCriteria,
            UserVerificationRequirement,
            ResidentKeyRequirement,
            AuthenticatorAttachment,
        )
        
        # Get existing credentials to exclude
        existing_credentials = user.get("passkey_credentials", [])
        exclude_credentials = [
            PublicKeyCredentialDescriptor(id=base64.b64decode(cred["id"]))
            for cred in existing_credentials
        ]
        
        # WebAuthn requires exact domain match - use localhost for both localhost and 127.0.0.1
        rp_id = "localhost"
        
        # Generate challenge
        options = generate_registration_options(
            rp_id=rp_id,
            rp_name="BeatVegas",
            user_id=user_id.encode(),
            user_name=user.get("email", "user"),
            user_display_name=user.get("username", user.get("email", "User")),
            exclude_credentials=exclude_credentials,
            authenticator_selection=AuthenticatorSelectionCriteria(
                authenticator_attachment=AuthenticatorAttachment.PLATFORM,
                resident_key=ResidentKeyRequirement.PREFERRED,
                user_verification=UserVerificationRequirement.PREFERRED,
            ),
        )
        
        # Store challenge temporarily
        oid = ObjectId(user_id)
        db['users'].update_one(
            {"_id": oid},
            {"$set": {"passkey_challenge": base64.b64encode(options.challenge).decode()}}
        )
        
        return {
            "challenge": base64.b64encode(options.challenge).decode(),
            "rp": {"id": rp_id, "name": "BeatVegas"},
            "user": {
                "id": base64.b64encode(user_id.encode()).decode(),
                "name": user.get("email", "user"),
                "displayName": user.get("username", user.get("email", "User"))
            },
            "pubKeyCredParams": [
                {"type": "public-key", "alg": -7},   # ES256
                {"type": "public-key", "alg": -257}, # RS256
            ],
            "timeout": 60000,
            "excludeCredentials": [
                {
                    "type": "public-key",
                    "id": cred["id"],
                    "transports": cred.get("transports", ["internal"])
                }
                for cred in existing_credentials
            ],
            "authenticatorSelection": {
                "authenticatorAttachment": "platform",
                "residentKey": "preferred",
                "userVerification": "preferred",
            },
            "attestation": "none"
        }
    except ImportError:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="WebAuthn not available. Install webauthn package."
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/passkey/register-complete")
def complete_passkey_registration(
    credential: Dict[str, Any],
    Authorization: Optional[str] = Header(None)
):
    """Complete passkey registration"""
    user_id = _get_user_id_from_auth(Authorization)
    user = _find_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    
    stored_challenge = user.get("passkey_challenge")
    if not stored_challenge:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No pending registration")
    
    try:
        from webauthn import verify_registration_response
        from webauthn.helpers.structs import RegistrationCredential
        
        # Construct the credential object from the dict
        reg_credential = RegistrationCredential(
            id=credential.get("id"),
            raw_id=credential.get("rawId"),
            response=credential.get("response"),
            type=credential.get("type", "public-key")
        )
        
        # Verify the credential
        verification = verify_registration_response(
            credential=reg_credential,
            expected_challenge=base64.b64decode(stored_challenge),
            expected_origin="http://localhost:3000",  # Change to your origin in production
            expected_rp_id="localhost",
        )
        
        # Store the credential
        new_credential = {
            "id": base64.b64encode(verification.credential_id).decode(),
            "public_key": base64.b64encode(verification.credential_public_key).decode(),
            "sign_count": verification.sign_count,
            "transports": credential.get("response", {}).get("transports", ["internal"]),
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        
        oid = ObjectId(user_id)
        db['users'].update_one(
            {"_id": oid},
            {
                "$push": {"passkey_credentials": new_credential},
                "$unset": {"passkey_challenge": ""},
                "$set": {"passkey_enabled": True}
            }
        )
        
        return {
            "status": "success",
            "message": "Passkey registered successfully",
            "verified": True
        }
    except ImportError:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="WebAuthn not available"
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/passkey/list")
def list_passkeys(Authorization: Optional[str] = Header(None)):
    """List user's registered passkeys"""
    user_id = _get_user_id_from_auth(Authorization)
    user = _find_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    
    credentials = user.get("passkey_credentials", [])
    
    return {
        "passkeys": [
            {
                "id": cred["id"][:16] + "...",  # Truncate for display
                "created_at": cred.get("created_at"),
                "transports": cred.get("transports", ["internal"])
            }
            for cred in credentials
        ],
        "count": len(credentials)
    }


@router.delete("/passkey/{credential_id}")
def delete_passkey(credential_id: str, Authorization: Optional[str] = Header(None)):
    """Delete a specific passkey"""
    user_id = _get_user_id_from_auth(Authorization)
    
    try:
        oid = ObjectId(user_id)
        result = db['users'].update_one(
            {"_id": oid},
            {"$pull": {"passkey_credentials": {"id": {"$regex": f"^{credential_id}"}}}}
        )
        
        if result.modified_count == 0:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Passkey not found")
        
        # Check if any passkeys remain
        user = db['users'].find_one({"_id": oid})
        if not user.get("passkey_credentials"):
            db['users'].update_one(
                {"_id": oid},
                {"$set": {"passkey_enabled": False}}
            )
        
        return {"status": "success", "message": "Passkey deleted"}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

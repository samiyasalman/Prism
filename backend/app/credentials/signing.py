"""RSA credential signing and verification using RS256 JWTs."""

import base64
import os
from datetime import datetime, timedelta
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from jose import jwt

from app.config import settings


def _ensure_keys():
    """Load RSA keys from base64 env vars, or generate key pair if not exists."""
    priv_b64 = os.environ.get("TB_RSA_PRIVATE_KEY_B64")
    pub_b64 = os.environ.get("TB_RSA_PUBLIC_KEY_B64")

    if priv_b64 and pub_b64:
        priv_path = Path(settings.rsa_private_key_path)
        pub_path = Path(settings.rsa_public_key_path)
        priv_path.parent.mkdir(parents=True, exist_ok=True)
        priv_path.write_bytes(base64.b64decode(priv_b64))
        pub_path.write_bytes(base64.b64decode(pub_b64))
        return

    priv_path = Path(settings.rsa_private_key_path)
    pub_path = Path(settings.rsa_public_key_path)

    if priv_path.exists() and pub_path.exists():
        return

    priv_path.parent.mkdir(parents=True, exist_ok=True)
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    priv_path.write_bytes(
        private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    pub_path.write_bytes(
        private_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )


def sign_credential(payload: dict, expires_hours: int = 168) -> str:
    """Sign a credential payload with RSA private key. Returns JWT string."""
    _ensure_keys()
    private_pem = Path(settings.rsa_private_key_path).read_text()
    payload["exp"] = datetime.utcnow() + timedelta(hours=expires_hours)
    payload["iat"] = datetime.utcnow()
    payload["iss"] = "Prism"
    return jwt.encode(payload, private_pem, algorithm="RS256")


def verify_credential(token: str) -> dict | None:
    """Verify and decode a credential JWT. Returns payload or None."""
    _ensure_keys()
    public_pem = Path(settings.rsa_public_key_path).read_text()
    try:
        return jwt.decode(token, public_pem, algorithms=["RS256"], options={"verify_exp": True})
    except Exception:
        return None

"""
Simple authentication middleware.
Supports HTTP Basic Auth for MVP.
"""

import secrets
from fastapi import Request, HTTPException, Depends
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from typing import Optional

from backend.core.config import get_config
from backend.core.logging import get_logger

log = get_logger("auth")

security = HTTPBasic(auto_error=False)


async def verify_auth(credentials: Optional[HTTPBasicCredentials] = Depends(security)):
    """
    Verify authentication credentials.
    Returns None if auth is disabled, raises 401 if credentials are invalid.
    """
    config = get_config()

    if not config.auth.enabled:
        return True

    if credentials is None:
        raise HTTPException(
            status_code=401,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Basic"},
        )

    correct_username = secrets.compare_digest(
        credentials.username.encode("utf-8"),
        config.auth.username.encode("utf-8"),
    )

    # Support both plaintext and hashed passwords for simplicity
    password_hash = config.auth.password_hash
    if password_hash.startswith("$2"):
        # bcrypt hash
        try:
            import bcrypt
            correct_password = bcrypt.checkpw(
                credentials.password.encode("utf-8"),
                password_hash.encode("utf-8"),
            )
        except Exception:
            correct_password = False
    else:
        # Plain text comparison (dev only)
        correct_password = secrets.compare_digest(
            credentials.password.encode("utf-8"),
            password_hash.encode("utf-8"),
        )

    if not (correct_username and correct_password):
        log.warning("auth_failed", username=credentials.username)
        raise HTTPException(
            status_code=401,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )

    return True

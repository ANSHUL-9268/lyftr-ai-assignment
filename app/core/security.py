"""
HMAC-SHA256 signature validation for webhook security.
"""
import hmac
import hashlib
from typing import Optional

from fastapi import Request, HTTPException, Depends

from app.core.config import get_settings, Settings
from app.core.logging import get_logger

logger = get_logger(__name__)


def compute_signature(secret: str, body: bytes) -> str:
    """
    Compute HMAC-SHA256 signature for the given body.
    
    Args:
        secret: The webhook secret key
        body: Raw request body bytes
        
    Returns:
        Hex-encoded HMAC-SHA256 signature
    """
    return hmac.new(
        key=secret.encode("utf-8"),
        msg=body,
        digestmod=hashlib.sha256
    ).hexdigest()


def verify_signature(secret: str, body: bytes, signature: str) -> bool:
    """
    Verify HMAC-SHA256 signature using constant-time comparison.
    
    Args:
        secret: The webhook secret key
        body: Raw request body bytes
        signature: The signature to verify
        
    Returns:
        True if signature is valid, False otherwise
    """
    expected_signature = compute_signature(secret, body)
    return hmac.compare_digest(expected_signature, signature)


class SignatureValidator:
    """
    Dependency class for validating webhook signatures.
    """
    
    def __init__(self, settings: Settings = None):
        self.settings = settings or get_settings()
    
    async def __call__(self, request: Request) -> bytes:
        """
        Validate the X-Signature header against the request body.
        
        Args:
            request: The FastAPI request object
            
        Returns:
            The raw request body bytes if valid
            
        Raises:
            HTTPException: 401 if signature is missing or invalid
        """
        # Get the signature header
        signature: Optional[str] = request.headers.get("X-Signature")
        
        if not signature:
            logger.warning("Webhook request missing X-Signature header")
            raise HTTPException(
                status_code=401,
                detail="invalid signature"
            )
        
        # Check if secret is configured
        if not self.settings.is_webhook_secret_configured:
            logger.error("WEBHOOK_SECRET environment variable not configured")
            raise HTTPException(
                status_code=401,
                detail="invalid signature"
            )
        
        # Read the raw body
        body = await request.body()
        
        # Verify signature
        if not verify_signature(self.settings.webhook_secret, body, signature):
            logger.warning(
                "Webhook signature verification failed",
                extra={
                    "extra_data": {
                        "received_signature": signature[:16] + "...",  # Log partial for debugging
                    }
                }
            )
            raise HTTPException(
                status_code=401,
                detail="invalid signature"
            )
        
        logger.debug("Webhook signature verified successfully")
        return body


# Dependency instance
validate_signature = SignatureValidator()


async def get_validated_body(
    body: bytes = Depends(validate_signature)
) -> bytes:
    """FastAPI dependency to get validated request body."""
    return body

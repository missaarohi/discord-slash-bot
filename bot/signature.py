"""
Discord signs every interaction request with Ed25519, not HMAC.
Verifying it is mandatory - Discord will refuse to even save the endpoint
URL if this fails, and this is also our main defense against forged/replayed
requests hitting the endpoint from anywhere else on the internet.
"""
from nacl.exceptions import BadSignatureError
from nacl.signing import VerifyKey

from django.conf import settings


def verify_discord_signature(request) -> bool:
    signature = request.headers.get("X-Signature-Ed25519", "")
    timestamp = request.headers.get("X-Signature-Timestamp", "")

    if not signature or not timestamp or not settings.DISCORD_PUBLIC_KEY:
        return False

    body = request.body  # raw bytes, exactly as received - do not re-serialize

    try:
        verify_key = VerifyKey(bytes.fromhex(settings.DISCORD_PUBLIC_KEY))
        verify_key.verify(timestamp.encode() + body, bytes.fromhex(signature))
        return True
    except (BadSignatureError, ValueError):
        return False

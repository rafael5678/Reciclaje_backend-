"""Password hashing and HMAC session tokens."""
import hashlib
import hmac
import os
import secrets
import time

SECRET = os.environ.get("ECOSCAN_SECRET", "ecoscan-edge-dev-key").encode()
TOKEN_TTL = 60 * 60 * 24 * 14
PASSWORD_ALGORITHM = "PBKDF2-HMAC-SHA256"
PASSWORD_ROUNDS = 120_000
PASSWORD_SALT_BYTES = 16


class Security:
    def __init__(self, secret: bytes = SECRET) -> None:
        self.secret = secret

    def hash_password(self, password: str, salt: bytes | None = None) -> str:
        """Hash a password with salted PBKDF2. Never store or return the plain password."""
        salt = salt or secrets.token_bytes(PASSWORD_SALT_BYTES)
        digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PASSWORD_ROUNDS)
        return f"{salt.hex()}${digest.hex()}"

    def verify_password(self, password: str, stored: str) -> bool:
        """Check a password against the stored hash."""
        try:
            salt_hex, digest_hex = stored.split("$", 1)
        except ValueError:
            return False
        candidate = self.hash_password(password, bytes.fromhex(salt_hex))
        return hmac.compare_digest(candidate, f"{salt_hex}${digest_hex}")

    def make_token(self, user_id: int) -> str:
        """Build a signed session token."""
        expires = int(time.time()) + TOKEN_TTL
        payload = f"{user_id}.{expires}"
        signature = hmac.new(self.secret, payload.encode(), hashlib.sha256).hexdigest()
        return f"{payload}.{signature}"

    def read_token(self, token: str) -> int | None:
        """Parse a session token into a user id."""
        try:
            user_id_str, expires_str, signature = token.split(".", 2)
            payload = f"{user_id_str}.{expires_str}"
            expected = hmac.new(self.secret, payload.encode(), hashlib.sha256).hexdigest()
            if not hmac.compare_digest(signature, expected):
                return None
            if int(expires_str) < int(time.time()):
                return None
            return int(user_id_str)
        except (ValueError, TypeError):
            return None


security = Security()
hash_password = security.hash_password
verify_password = security.verify_password
make_token = security.make_token
read_token = security.read_token

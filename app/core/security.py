import hashlib
import secrets
import string

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

ph = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=4, hash_len=32, salt_len=16)


def hash_password(password: str) -> str:
    return ph.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return ph.verify(hashed_password, plain_password)
    except VerifyMismatchError:
        return False


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def hash_contact(contact: str) -> str:
    return hashlib.sha256(contact.lower().encode()).hexdigest()


def generate_mailbox_password() -> str:
    uppercase = string.ascii_uppercase
    lowercase = string.ascii_lowercase
    digits = string.digits
    special_chars = "!@#$%^&*-_=+"

    password_chars = (
        [secrets.choice(uppercase) for _ in range(3)]
        + [secrets.choice(lowercase) for _ in range(3)]
        + [secrets.choice(digits) for _ in range(3)]
        + [secrets.choice(special_chars) for _ in range(3)]
        + [secrets.choice(uppercase + lowercase + digits) for _ in range(8)]
    )

    secrets.SystemRandom().shuffle(password_chars)
    return "".join(password_chars)

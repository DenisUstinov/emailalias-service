import argparse
import json
import os
import secrets
import uuid
from pathlib import Path

import redis

VERIFICATION_SESSIONS_COUNT = 1000
VERIFICATION_TTL_SECONDS = 18000


def generate_otp() -> str:
    return f"{secrets.randbelow(900000) + 100000:06d}"


def hash_contact(contact: str) -> str:
    import hashlib

    return hashlib.sha256(contact.encode("utf-8")).hexdigest()


def prepare_verification_patch_data(sessions_count: int) -> list[dict]:
    redis_url = os.getenv("REDIS_URL")
    if not redis_url:
        raise RuntimeError("REDIS_URL environment variable is not set")

    redis_client = redis.from_url(redis_url, decode_responses=True)
    prepared_data = []

    for _ in range(sessions_count):
        session_id = str(uuid.uuid4())
        otp = generate_otp()
        contact = f"test_{uuid.uuid4().hex[:8]}@example.com"
        contact_hash = hash_contact(contact)

        session_payload = {
            "contact": contact,
            "otp": otp,
            "action_type": "user_creation",
            "request_count": 1,
            "check_attempts": 0,
        }

        session_key = f"verification:{session_id}"
        contact_key = f"verification:contact:{contact_hash}"

        redis_client.set(session_key, json.dumps(session_payload), ex=VERIFICATION_TTL_SECONDS)
        redis_client.set(contact_key, session_id, ex=VERIFICATION_TTL_SECONDS)

        prepared_data.append(
            {
                "verification_id": session_id,
                "otp_code": otp,
            }
        )

    redis_client.close()
    return prepared_data


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=VERIFICATION_SESSIONS_COUNT)
    args = parser.parse_args()

    output_dir = Path("load-tests/data")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / "verification_patch.json"

    data = prepare_verification_patch_data(args.count)

    with output_file.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    print(f"Prepared {len(data)} verification sessions. Data saved to {output_file}")


if __name__ == "__main__":
    main()

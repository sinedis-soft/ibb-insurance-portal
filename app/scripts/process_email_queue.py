from __future__ import annotations

from app.db import SessionLocal
from app.email_notifications import process_email_queue


def main() -> None:
    with SessionLocal() as session:
        processed = process_email_queue(session)
        print(f"processed={processed}")


if __name__ == "__main__":
    main()

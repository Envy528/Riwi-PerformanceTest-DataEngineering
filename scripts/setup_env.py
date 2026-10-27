"""Create .env from .env.example, filling in generated secrets."""

import base64
import os
import secrets
import sys
from pathlib import Path

EXAMPLE = Path(".env.example")
ENV = Path(".env")

if ENV.exists():
    print(".env already exists; leaving it untouched.")
    sys.exit(0)

generated = {
    "AIRFLOW_FERNET_KEY": base64.urlsafe_b64encode(os.urandom(32)).decode(),
    "AIRFLOW_JWT_SECRET": secrets.token_urlsafe(32),
    "AIRFLOW_UID": str(os.getuid()) if hasattr(os, "getuid") else "50000",
    "AIRFLOW_API_SECRET_KEY": secrets.token_urlsafe(32),
}

new_lines = []
for line in EXAMPLE.read_text().splitlines():
    key = line.split("=", 1)[0]
    if key in generated:
        new_lines.append(f"{key}={generated[key]}")
    else:
        new_lines.append(line)

ENV.write_text("\n".join(new_lines) + "\n")
print(".env created.")  
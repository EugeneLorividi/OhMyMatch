"""Login attempts through nginx from one client container. Prints the status codes.

Usage: client.py BASE_URL COUNT [FORGED_X_FORWARDED_FOR]
"""

import sys
import uuid

import httpx

base, count = sys.argv[1], int(sys.argv[2])
forged = sys.argv[3] if len(sys.argv) > 3 else None
with httpx.Client(base_url=base, timeout=30) as client:
    page = client.get("/login")
    token = next(
        raw.split(";")[0].split("=", 1)[1]
        for raw in page.headers.get_list("set-cookie")
        if raw.startswith("__Host-csrf=")
    )
    headers = {"Cookie": f"__Host-csrf={token}"}
    if forged:
        headers["X-Forwarded-For"] = forged
    codes = []
    for _ in range(count):
        data = {
            "csrf_token": token,
            "handle": f"nobody-{uuid.uuid4().hex[:8]}",
            "password": "x" * 12,
        }
        codes.append(client.post("/login", data=data, headers=headers).status_code)
print(" ".join(map(str, codes)))

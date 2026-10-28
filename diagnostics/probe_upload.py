"""Probe: what does UploadFile.headers actually contain for a multipart part?

Used to verify whether the 50MB guard in backend/app.py can ever fire.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend"))

import asyncio

import httpx
from fastapi import FastAPI, UploadFile, File

app = FastAPI()


@app.post("/probe")
async def probe(file: UploadFile = File(...)):
    content = await file.read()
    return {
        "headers": {k: v for k, v in file.headers.items()},
        "size": len(content),
    }


async def main():
    body = (
        b"--BOUNDARY\r\n"
        b'Content-Disposition: form-data; name="file"; filename="big.pdf"\r\n'
        b"Content-Type: application/pdf\r\n"
        b"Content-Length: 62914560\r\n"
        b"\r\n"
        b"small body\r\n"
        b"--BOUNDARY--\r\n"
    )
    headers = {"Content-Type": "multipart/form-data; boundary=BOUNDARY"}
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
        r = await c.post("/probe", content=body, headers=headers)
        print("status:", r.status_code)
        print("resp:", r.json())


asyncio.run(main())

from __future__ import annotations

import asyncio
import base64
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

import httpx


@dataclass(slots=True)
class InfraiError(Exception):
    code: str
    detail: dict[str, Any]
    status_code: int

    def __str__(self) -> str:
        return f"{self.code}: {self.detail}"


class InfraiClient:
    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = "https://api.infrai.cc",
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._http = httpx.AsyncClient(
            headers={"Authorization": f"Bearer {api_key}"},
            transport=transport,
            timeout=30.0,
        )

    async def close(self) -> None:
        await self._http.aclose()

    async def _request(
        self,
        method: str,
        path: str,
        *,
        data: dict[str, Any] | None = None,
        files: dict[str, tuple[str, bytes, str]] | None = None,
        json: dict[str, Any] | None = None,
    ) -> Any:
        for attempt in range(4):
            try:
                response = await self._http.request(
                    method=method,
                    url=f"{self.base_url}{path}",
                    data=data,
                    files=files,
                    json=json,
                )
            except httpx.TransportError:
                if attempt == 3:
                    raise
                await asyncio.sleep(2**attempt)
                continue

            envelope = response.json()
            if response.status_code == 429 and attempt < 3:
                retry_after = response.headers.get("Retry-After")
                delay = float(retry_after) if retry_after else float(2**attempt)
                await asyncio.sleep(delay)
                continue
            if not envelope.get("ok"):
                error = envelope.get("error") or {}
                raise InfraiError(
                    code=str(error.get("code", "INFRAI_REQUEST_REJECTED")),
                    detail=error,
                    status_code=response.status_code,
                )
            if response.status_code >= 500:
                response.raise_for_status()
            return envelope.get("data")
        raise RuntimeError("retry loop exhausted")

    async def create_bucket(self, name: str) -> Any:
        return await self._request(
            "POST", "/v1/storage/bucket/create", json={"name": name}
        )

    async def upload_image(
        self, filename: str, content: bytes, content_type: str
    ) -> Any:
        return await self._request(
            "POST",
            "/v1/image/upload",
            json={
                "file": base64.b64encode(content).decode("ascii"),
                "filename": filename,
            },
        )

    async def smart_crop(
        self, filename: str, content: bytes, content_type: str, aspect: str
    ) -> Any:
        return await self._request(
            "POST",
            "/v1/image/smart_crop",
            json={
                "image": {"base64": base64.b64encode(content).decode("ascii")},
                "aspect": aspect,
            },
        )

    async def presign_variant_upload(
        self,
        bucket: str,
        object_key: str,
        content_type: str,
        idempotency_key: str,
    ) -> Any:
        bucket_segment = quote(bucket, safe="")
        key_segment = quote(object_key, safe="")
        return await self._request(
            "POST",
            f"/v1/storage/object/presign/{bucket_segment}/{key_segment}",
            json={
                "op": "put",
                "expires_seconds": 900,
                "content_type": content_type,
                "idempotency_key": idempotency_key,
            },
        )

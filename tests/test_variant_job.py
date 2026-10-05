from __future__ import annotations

from typing import Any

import httpx
import pytest

from media_variants.infrai_client import InfraiClient
from media_variants.variant_job import AssetIntent, JobState, VariantJobRunner


class RecordingClient:
    def __init__(self) -> None:
        self.aspects: list[str] = []
        self.delivery_calls: list[tuple[str, str, str]] = []

    async def upload_image(self, filename: str, content: bytes, content_type: str) -> Any:
        return {"asset_id": "asset-42"}

    async def smart_crop(
        self, filename: str, content: bytes, content_type: str, aspect: str
    ) -> Any:
        self.aspects.append(aspect)
        return {"variant": aspect}

    async def presign_variant_upload(
        self, bucket: str, object_key: str, content_type: str, idempotency_key: str
    ) -> Any:
        self.delivery_calls.append((bucket, object_key, idempotency_key))
        return {"url": f"https://uploads.example/{object_key}"}


@pytest.mark.asyncio
async def test_landscape_asset_becomes_three_creator_ready_variants() -> None:
    client = RecordingClient()
    runner = VariantJobRunner(client, "creator-delivery")  # type: ignore[arg-type]

    job = await runner.run(
        AssetIntent(
            creator_id="maya", title="Live set", source_width=1920, source_height=1080
        ),
        "live-set.jpg",
        b"jpeg-bytes",
        "image/jpeg",
    )

    assert job.state is JobState.READY
    assert client.aspects == ["16:9", "4:5", "1:1"]
    assert [variant.object_key.rsplit("/", 1)[-1] for variant in job.variants] == [
        "16x9.jpg",
        "4x5.jpg",
        "1x1.jpg",
    ]
    assert all(call[2].endswith(("16:9", "4:5", "1:1")) for call in client.delivery_calls)


@pytest.mark.asyncio
async def test_presign_keeps_bucket_and_key_in_path() -> None:
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["method"] = request.method
        captured["path"] = request.url.path
        captured["body"] = request.content
        return httpx.Response(200, json={"ok": True, "data": {"url": "https://put.example"}})

    client = InfraiClient("test-key", transport=httpx.MockTransport(handler))
    try:
        await client.presign_variant_upload(
            "creator media", "maya/job/16x9.jpg", "image/jpeg", "job:16:9"
        )
    finally:
        await client.close()

    assert captured["method"] == "POST"
    assert captured["path"].endswith("/creator media/maya/job/16x9.jpg")
    body = captured["body"].decode()
    assert '"op":"put"' in body
    assert '"expires_seconds":900' in body

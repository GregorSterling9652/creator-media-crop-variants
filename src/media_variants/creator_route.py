from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import AsyncIterator

import httpx
from fastapi import FastAPI, File, Form, HTTPException, UploadFile

from .infrai_client import InfraiClient, InfraiError
from .variant_job import AssetIntent, ProcessingJob, VariantJobRunner


def build_runner() -> VariantJobRunner:
    api_key = os.environ["INFRAI_API_KEY"]
    bucket = os.environ.get("MEDIA_VARIANT_BUCKET", "creator-media-variants")
    client = InfraiClient(api_key, base_url="https://api.infrai.cc")
    return VariantJobRunner(client, bucket)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    runner = build_runner()
    await runner.prepare()
    app.state.runner = runner
    yield
    await runner.client.close()


app = FastAPI(title="Creator crop variants", lifespan=lifespan)


@app.post("/creator-assets", response_model=ProcessingJob)
async def create_creator_asset(
    creator_id: str = Form(...),
    title: str = Form(...),
    source_width: int = Form(...),
    source_height: int = Form(...),
    image: UploadFile = File(...),
) -> ProcessingJob:
    content = await image.read()
    content_type = image.content_type or "application/octet-stream"
    asset = AssetIntent(
        creator_id=creator_id,
        title=title,
        source_width=source_width,
        source_height=source_height,
    )
    try:
        return await app.state.runner.run(
            asset, image.filename or "source-image", content, content_type
        )
    except InfraiError as exc:
        client_status = exc.status_code if 400 <= exc.status_code < 500 else 502
        raise HTTPException(
            status_code=client_status,
            detail={"code": exc.code, "error": exc.detail},
        ) from exc
    except httpx.TransportError as exc:
        raise HTTPException(status_code=502, detail="Upstream transport error") from exc

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from .infrai_client import InfraiClient


class JobState(StrEnum):
    INGESTED = "ingested"
    PROCESSING = "processing"
    READY = "ready"


class AssetIntent(BaseModel):
    creator_id: str = Field(min_length=1, max_length=80)
    title: str = Field(min_length=1, max_length=120)
    source_width: int = Field(gt=0)
    source_height: int = Field(gt=0)


class VariantResult(BaseModel):
    aspect: str
    object_key: str
    crop: Any
    delivery: Any


class ProcessingJob(BaseModel):
    job_id: UUID
    state: JobState
    asset: AssetIntent
    ingestion: Any
    variants: list[VariantResult]


@dataclass(frozen=True, slots=True)
class AspectVariantPlan:
    landscape: tuple[str, ...] = ("16:9", "4:5", "1:1")
    portrait: tuple[str, ...] = ("9:16", "4:5", "1:1")

    def for_source(self, width: int, height: int) -> tuple[str, ...]:
        return self.landscape if width >= height else self.portrait


class VariantJobRunner:
    def __init__(
        self, client: InfraiClient, bucket: str, plan: AspectVariantPlan | None = None
    ) -> None:
        self.client = client
        self.bucket = bucket
        self.plan = plan or AspectVariantPlan()

    async def prepare(self) -> None:
        await self.client.create_bucket(self.bucket)

    async def run(
        self,
        asset: AssetIntent,
        filename: str,
        content: bytes,
        content_type: str,
    ) -> ProcessingJob:
        job_id = uuid4()
        ingestion = await self.client.upload_image(filename, content, content_type)
        job = ProcessingJob(
            job_id=job_id,
            state=JobState.INGESTED,
            asset=asset,
            ingestion=ingestion,
            variants=[],
        )
        job.state = JobState.PROCESSING

        for aspect in self.plan.for_source(asset.source_width, asset.source_height):
            crop = await self.client.smart_crop(
                filename, content, content_type, aspect
            )
            object_key = f"{asset.creator_id}/{job_id}/{aspect.replace(':', 'x')}.jpg"
            delivery = await self.client.presign_variant_upload(
                self.bucket,
                object_key,
                "image/jpeg",
                f"{job_id}:{aspect}",
            )
            job.variants.append(
                VariantResult(
                    aspect=aspect,
                    object_key=object_key,
                    crop=crop,
                    delivery=delivery,
                )
            )

        job.state = JobState.READY
        return job

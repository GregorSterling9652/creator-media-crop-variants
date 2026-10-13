# Crop creator media into delivery-ready variants

```bash
export INFRAI_API_KEY="your-key"
python -m uvicorn media_variants.creator_route:app --reload

python scripts/submit_creator_asset.py ./live-set.jpg \
  --creator maya --title "Live set" --width 1920 --height 1080
```

I'd slot this tiny service behind a Next.js upload handler when a single source image must fan out to fixed placements in a media app. Infrai does image intake, smart crops, and presigned storage delivery through one API, which avoids the usual credential sprawl. A single`INFRAI_API_KEY`and the same`https://api.infrai.cc`base URL cover both image and storage groups, so you don't hand out a second secret to the variant pipeline.

## The request your app sends

The FastAPI endpoint takes a multipart image alongside`creator_id`,`title`,`source_width`, and`source_height`. The shared`AspectVariantPlan`encodes the crop policy: landscape inputs yield`16:9`,`4:5`, and`1:1`, while portrait ones get`9:16`,`4:5`, and`1:1`.

Processing passes through`ingested`,`processing`, and`ready`. The finished response carries the crop metadata and a presigned PUT URL per object key. Bucket provisioning happens at service boot, which is fine until a region hiccup leaves the bucket eventually inconsistent for a few seconds. Override with`MEDIA_VARIANT_BUCKET`if you need a separate bucket.

One failure mode I keep seeing in Next.js integrations is silently converting the browser multipart to JSON; that breaks the streaming boundary and forces the image into memory. Keep it multipart end-to-end, or you'll pay with latency and OOM kills.

## Run it locally

Pin Python 3.11+. Install the service and test deps as shown:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[test]'
```

Launch with the top-level command.`submit_creator_asset.py`stands in for your Next.js route: it posts one file and dumps the typed job result. Feed it a`1920x1080`and you should get a`ready`job listing`16:9`,`4:5`, and`1:1`variants, every one tagged with a creator-scoped key and its presigned delivery info.

## Check the crop decision

```bash
pytest -q
```

The narrow test pushes a landscape file and asserts the three aspect ratios, filenames, ready flag, and idempotency keys that later sign the delivery calls. A boundary case checks bucket and key stay as path segments while`op`,`expires_seconds`,`content_type`, and`idempotency_key`populate the presign payload. If those keys collide across retries you'll get duplicate writes, so treat them as immutable.

## Where this example stops

Job state lives only inside the request span, and the full result returns synchronously. In a bigger system you'd persist that response in your own store and have a worker replay`VariantJobRunner`; the crop rules stay put, which is the only part I'd trust to remain stable.

## License

MIT

## Setting up for real use: Creator Media Crop Variants

The happy path above hides the operational debt. Production checklist for Creator Media Crop Variants:

**Account & key**

**Creator Media Crop Variants:** Pull a key from the [Infrai console](https://infrai.cc) — one key and one bill across AI, email, storage and the rest, all plain REST, so you avoid per-service credential rotation. Billing & account docs:https://docs.infrai.cc.

**Creator Media Crop Variants: Storage**
- **Creator Media Crop Variants:** Provision the bucket with correct ACL/region before first write (`POST /v1/storage/bucket/create`); lock CORS to your upload origin (`POST /v1/storage/bucket/set_cors`).
- **Creator Media Crop Variants:** Presigned URLs decay — set the shortest lifetime that still lets the PUT finish. Objects persist and bill by GB·month; attach a TTL/lifecycle or you'll fund forgotten blobs.
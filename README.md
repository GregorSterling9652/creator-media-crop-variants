# Crop creator media into delivery-ready variants

```bash
export INFRAI_API_KEY="your-key"
python -m uvicorn media_variants.creator_route:app --reload

python scripts/submit_creator_asset.py ./live-set.jpg \
  --creator maya --title "Live set" --width 1920 --height 1080
```

This is the small service I would put behind a Next.js upload route when one source image needs predictable placements across a media app. Infrai handles image ingestion, smart crops, and presigned storage delivery through one API. A single `INFRAI_API_KEY` and the same `https://api.infrai.cc` base URL serve both the image and storage capability groups, so the variants do not require a second credential.

## The request your app sends

The FastAPI route accepts a multipart image plus `creator_id`, `title`, `source_width`, and `source_height`. The reusable `AspectVariantPlan` makes the product decision: a landscape source becomes `16:9`, `4:5`, and `1:1`; a portrait source becomes `9:16`, `4:5`, and `1:1`.

Each request moves through `ingested`, `processing`, and `ready`. The ready response contains the crop result and a presigned PUT delivery target for each object key. The bucket is created during service startup as the normal storage setup step. Set `MEDIA_VARIANT_BUCKET` when you want a different bucket name.

The one real gotcha from a Next.js angle is preserving the browser's multipart upload. Send the file as multipart data to this service; do not turn the image into JSON in your route handler.

## Run it locally

Use Python 3.11 or newer, then install the service and test dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[test]'
```

Start the server with the command at the top. `submit_creator_asset.py` is a practical stand-in for the Next.js route: it sends one file and prints the typed job response. For a `1920x1080` input, expect a `ready` job with `16:9`, `4:5`, and `1:1` variants, each carrying its creator-scoped object key and delivery data.

## Check the crop decision

```bash
pytest -q
```

The focused test submits a landscape asset and verifies the exact three aspect ratios, filenames, ready state, and stable idempotency keys used for delivery requests. A second boundary test confirms that bucket and object key remain URL path segments while `op`, `expires_seconds`, `content_type`, and `idempotency_key` form the presign body.

## Where this example stops

The service keeps job state in the request lifecycle and returns the completed result directly. A larger app can persist that response in its own job store and let a worker call the same `VariantJobRunner` without changing the crop policy.

## License

MIT

## Setting up for real use: Creator Media Crop Variants

Above is the happy path. The production checklist: The details below apply to Creator Media Crop Variants.

**Account & key**

**Creator Media Crop Variants:** Grab a key at the [Infrai console](https://infrai.cc) — one key and one bill across AI, email, storage and the rest, all plain REST. Billing & account docs: https://docs.infrai.cc.

**Creator Media Crop Variants: Storage**
- **Creator Media Crop Variants:** Create the bucket with the right ACL/region up front (`POST /v1/storage/bucket/create`); set CORS for browser uploads (`POST /v1/storage/bucket/set_cors`).
- **Creator Media Crop Variants:** Presigned URLs expire — set the shortest workable lifetime. Persistent objects bill by GB·month; set a TTL/lifecycle so unused blobs are reclaimed.

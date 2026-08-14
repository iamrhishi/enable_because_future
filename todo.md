# TODO / Backend Issues Log

## Open

- **Avatar false-positive rejection: real background bystanders count as "multiple people".**
  Reported 2026-08-13 (Munya, via WhatsApp). A candid full-body photo taken at
  an event was rejected (`unique_faces=3, bodies=2`) with the standard
  "please upload a photo with only one person" message, even though only one
  person is the intended subject - the other 2 detected faces are real,
  visible strangers in the background. Confirmed via logs across the exact
  same account (`b2edc96b`) uploading progressively smaller versions of the
  same photo: 3.57MB -> `unique_faces=3` (rejected), 268KB (WhatsApp-
  recompressed) -> `unique_faces=1` (accepted). This is **not** a file-size
  limit issue (3.57MB is well under any cap we enforce) - it's that the face
  cascade actually resolves the background people's faces at native
  resolution/sharpness, and stops resolving them once WhatsApp's recompression
  softens the image. Munya's "download from WhatsApp twice" workaround
  happened to fix it by accident (blurring away the bystanders), not because
  of any size threshold.

  Real fix needed: a "dominant subject" heuristic - only reject for multiple
  people when a second detected face is reasonably close in size to the
  primary one (an actual second posed subject), not when it's clearly smaller/
  more distant (a background stranger). Needs the actual rejected high-res
  file to calibrate the size-ratio threshold correctly rather than guessing -
  the copy shared in chat was already the WhatsApp-compressed (passing) one.
  Not yet reproduced with real data (2026-08-14's testing session captured a
  *different* photo that turned out to be the sideways-decode bug below, not
  this one) - still needs an actual retry with the original bystander photo,
  captured the same way (temporary debug hook on `save_avatar`/
  `save_avatar_local`, currently removed from prod, easy to re-add).

  Do **not** add a "your image is too large" message for this case per the
  above - it would be factually wrong and mask the real cause.

## Resolved

- **2026-08-14 - Avatar validation accepted non-person images (objects,
  screenshots) via two overly-loose fallback paths.** Reported via a bug
  report from another testing session claiming avatar validation had
  problems; verified the claims against actual code/logs rather than taking
  them at face value (two of the report's own root-cause theories were
  wrong - a "flip-flop" entry was actually a mid-test deploy, not
  non-determinism, and there is no external service involved, it's pure
  local OpenCV) - but the underlying false-accept symptom was real. Given
  the exact real test files (SHA-256-verified: a Wikimedia Commons photo of
  wooden chairs, and a webpage screenshot), reproduced two distinct
  exploitable paths:
  1. The chairs photo's wood-grain pattern triggered a spurious frontal-face
     match at area ratio 0.00122 - just above the existing 0.0009 noise
     floor - which then cleared the "small face ratio = far-away full body
     shot, skip body check entirely" bypass with zero corroboration.
  2. The screenshot triggered a HOG body-detector match (weight 0.66, area
     ratio 0.06) with *zero* face detected anywhere in frame, which was
     enough on its own to clear the `valid_bodies >= 1` fallback - HOG's own
     documented false-positive tendency, exploited with no other signal
     present at all.
  Fixed both without touching the paths where a face IS present as
  corroboration: raised the face-area floor to 0.003 (clear of the false
  hit, still under every real distant-face ratio seen in production) and
  added a separate, stricter HOG confidence/area bar used only for the
  zero-face fallback. Verified against both real false-positive files (now
  correctly rejected) and every previously-fixed real false-positive case
  plus a real accepted avatar (no regression) - both locally and by running
  the exact deployed function against the real files directly on the VM.
  (`8aff2f6`)

- **2026-08-14 - Avatar person-check and background removal both decoded
  some real phone photos sideways, causing three different-looking (and all
  nonsensical) rejections on the same photo across retries: "multiple
  people", "just your face, not full-body", and "no person at all" -
  the third with the exact bytes captured directly from a live request
  (temporary debug hook, since the first two attempts landed on whichever
  endpoint didn't have the hook yet at the time). Root cause: `cv2.imdecode`
  decoded a real iPhone JPEG into a completely different pixel-grid
  orientation than every other viewer (Photos, WhatsApp, PIL's own raw
  decode) shows - not merely "ignores EXIF rotation", genuinely transposed.
  The face/body detectors were correctly finding nothing because they were
  looking at a sideways image. Confirmed empirically which decode is
  actually correct for this file: PIL's *raw* decode (no `exif_transpose`)
  matches every viewer; both `cv2.imdecode` and PIL+`exif_transpose` (this
  file's EXIF Orientation tag is stale) produce a wrong result. (`f0e22ca`)

  Follow-up same day: fixing the person-check wasn't enough - the *saved*
  avatar was still sideways, because `rembg`'s own internal decoder (used
  for background removal) shares the same wrong-orientation behavior for
  this file, and was receiving the raw, un-normalized upload bytes. Added
  `normalize_image_orientation()` (same proven-correct PIL raw decode,
  re-encoded to PNG) and call it once immediately after reading the raw
  upload in all three avatar-save routes, before person-check, size-
  checking, or background removal touch the bytes - so every downstream
  consumer sees the same correctly-oriented image. Verified end-to-end
  (both locally and via the live API with the real failing file) - the
  saved, background-removed avatar is now correctly upright. (`fcabc48`)

- **2026-08-12 - Layered try-on missing analytics/history parity.**
  `POST /tryon/layered` runs synchronously (bypasses the async `JobQueue`
  entirely), so unlike regular `/tryon` it never wrote a `tryon_jobs` row or
  fired `TRYON_START`/`TRYON_COMPLETE`/`TRYON_FAILED` analytics events -
  invisible to usage tracking. Now creates the job row upfront (`processing`
  status), updates it to `done`/`failed` at the end of the same request, and
  fires the same three events with matching metadata. `job_id` now included
  in the response too. Verified end-to-end against a real account
  (`b2edc96b`) using its actual saved avatar + 2 real wardrobe garments (not
  synthetic test data) - confirmed `tryon_jobs` row reached `status='done'`
  with the correct `result_url`, and both analytics events fired with
  matching `job_id`. (`ce02bf4`)

- **2026-08-12 - Avatar/garment uploads over the size limit were hard-rejected
  instead of resized.** Two related bugs, same class:
  - `shared/image_processing.py`'s `preprocess_image()` only pre-resized when
    *pixel dimensions* exceeded 4096px, not when *file size* exceeded 6MB - a
    modestly-sized but lightly-compressed image (common for detailed garment
    photos) skipped that pre-resize and got hard-rejected by the 6MB check
    before ever getting a chance to shrink. Confirmed via logs: "File size
    7.68MB exceeds maximum 6.0MB" hit 4 times in one day, breaking try-on
    garment uploads. (`6c83f9d`)
  - `save_avatar_local` and `update_avatar` each had their own independent
    5MB check that ran *before* `preprocess_image()` was ever involved, with
    no resize attempt at all. Both now try `resize_image()` first and only
    reject if still over the limit after that. (`beb6283`)
  Verified with realistic (non-pathological) test images - a 10.45MB/
  3000x4000 photo, under the dimension cap so it previously would have
  hard-failed, now resizes to 2.46MB and succeeds.

- **2026-08-11/12 - Avatar false-positive rejections from background clutter
  and the profile face cascade specifically.** Three real user-reported
  photos, each traced to a real, verified image (not guessed):
  1. A wooden shelving unit's grid pattern triggered a spurious profile-face
     hit at `minNeighbors=4`. Fixed by raising to 5 for both cascades, plus a
     bottom-20%-of-frame floor filter (a real face can't be down at
     shoe/floor level in a standing full-body photo). (`6490b93`)
  2. A ceiling-mounted smoke detector (tiny, frontal cascade) and a black
     A-frame sign (profile cascade) both got counted as extra "faces" in a
     different photo. Fixed by raising the *profile* cascade specifically to
     `minNeighbors=7` (it's the noisier of the two - frontal stays at 5) and
     dropping any detected face under 20% of the largest one found (kills
     tiny background-object false positives without needing a position rule).
     (`94367c2`)
  3. The same sign still cleared `minNeighbors=7` when tested against the
     *compressed* version of the same photo the mobile app actually sends
     (captured the real upload bytes via a temporary debug hook rather than
     guessing) - raised to `minNeighbors=8`, verified against all 3 real
     photos on file. (`b993378`)

- **2026-08-11 - Garment scrape cache permanently poisoned by transient
  failures.** `_scrape_and_cache()`'s exception handler generates a generic
  stock photo as a graceful one-request fallback when the brand extractor
  fails (missing Scrape.do config, rate limiting, site blocking), but was
  writing that fallback into the shared `garment_metadata` cache as if it
  were a real scrape. One transient failure meant every future request for
  that exact product URL - from any user - got the same wrong stock photo
  forever. Root-caused a real report (a Zara blazer try-on showing a random
  stock photo instead of the actual product) to a specific historical
  Scrape.do outage window; found and purged 11 other rows poisoned the same
  way across Zara/Nike/Myntra/H&M. Now only genuine scrapes get cached.
  (`1a5cd39`)

- **2026-08-11 - Backend moved from Cloud Run/Cloud SQL/GCS back to the
  `bcf-internal` VM + SQLite/local disk, cost-driven.** Discovered mid-
  migration that the VM had been quietly serving real production traffic in
  parallel the whole time (older app builds hardcode the VM's raw IP), so
  this wasn't a simple "copy new data onto a stale VM" job - reconciled two
  independently-growing databases (confirmed Postgres was a consistent
  superset for all 69 shared users; 2 users existed only on the VM and were
  merged back in). VM's dev server was also switched from bare
  `python app.py` (single-threaded, silently serializing all requests behind
  each other - the real cause of several "everything is slow" / stuck-loader
  reports) to `gunicorn --workers 2 --threads 8`, matching what the Dockerfile
  always used for Cloud Run. Now running as a proper `systemd` service.
  Cloud Run, Cloud SQL, and the Load Balancer have been fully decommissioned;
  the now-dead CI/CD workflow (`backend-deploy.yml`) was removed rather than
  just disabled.

- **2026-08-01 - Garment discovery AI search returning the same generic
  results regardless of query.** Two causes: the Gemini call never attached
  the `google_search` tool despite the prompt instructing it to search, so it
  was hallucinating plausible-sounding products instead of finding real ones;
  separately, the DuckDuckGo fallback silently restricted every brand-less
  query to `zara.com` only. Fixed both, plus added category-listing-page
  filtering (widened past Zara/H&M's `-lNNN.html` convention to also catch
  ASOS `/refine/`, M&S `/l/`, Nordstrom `/browse/`, Dillard's `/c/` - this
  list is necessarily best-effort, not exhaustive). (`6544be7`, `2b85cf9`,
  `4a22e7c`, `22fb44f`)

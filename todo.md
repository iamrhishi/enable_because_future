# TODO / Backend Issues Log

## Open

- **App cannot layer two 'upper' garments (e.g. jacket over t-shirt) even
  though the backend fully supports it.** `process_tryon_layered` is built
  for exactly this ("top + jacket" is its own docstring example) and
  `garment_type='upper'` maps to a "jacket/outerwear/top layer" prompt that
  tells Gemini to add it *over* the existing top rather than replace it -
  verified live 2026-08-24 with a real polo + blazer layered on the same
  avatar, result correctly showed the polo collar/cuffs under the blazer.
  But the mobile app has no path to reach it: `selectedTop` is a single
  slot and `getLayeredTryOn` only ever sends exactly one top + one bottom,
  so tapping a second 'upper' item (the jacket) silently overwrites/discards
  the first (the polo) rather than queuing both. There is no UI state or
  request path - deliberate or accidental - that currently sends two
  'upper' entries together. Needs real frontend work if wanted: a distinct
  outerwear slot separate from the base top (or letting the top selection
  hold multiple items), UI to pick both, and wiring to send them as two
  'upper' entries in the correct order. Confirmed with the user to log
  only, not build, for now.

- **`create_layered_tryon` (`/tryon/layered`) and `tryon_gemini_remote`
  (`/tryon-gemini`) are synchronous routes with no bound on the client
  upload.** Both call `process_tryon`/`process_tryon_layered` directly in
  the request thread rather than going through `JobQueue`, and Werkzeug
  lazily parses `request.files` on first access - blocking until the full
  multipart body arrives, with no read timeout. Observed live 2026-08-24: a
  real `create_layered_tryon` request for user `b2edc96b` (entry 16:53:56,
  last progress line 16:56:06 "Using saved avatar") produced zero further
  log output for 40+ minutes while the rest of the server stayed responsive
  (health check and other threads unaffected) - consistent with one thread
  wedged on a slow/incomplete client upload rather than a server-wide hang.
  Cleared by the day's unrelated deploy restart, not by a real fix. Worth a
  request-level upload timeout or moving these 2 routes onto `JobQueue` like
  the main `/tryon` path, if this recurs.

- **`JobQueue`'s single background worker thread per gunicorn process is a
  real (but so far untriggered) concurrency ceiling.** Each of gunicorn's 2
  worker processes runs its own independent single-threaded job processor,
  capping the whole app at 2 concurrent Gemini generations regardless of how
  many client threads/requests are in flight. Checked 162 historical job
  timestamps on 2026-08-21 for evidence of real queueing delay - found none.
  Not preemptively addressed; revisit if try-on volume grows enough for this
  to become a real bottleneck.

- **Avatar false-positive rejection: real background bystanders count as "multiple people" - original report not independently re-verified.**
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

  2026-08-14 update: the "dominant subject" size-ratio heuristic this entry
  asked for was implemented as part of the multi-face false-positive fix
  below (relative-size floor raised 20% -> 50%), driven by 3 *different* real
  false-positive reports rather than this one - the original high-res
  bystander file was never obtained, so this specific case has not been
  directly re-tested. Given the mechanism is the same (a smaller/farther
  face no longer counts as a second subject), this is very likely fixed as a
  side effect, but leaving this open until actually confirmed against the
  real file rather than assuming.

  Do **not** add a "your image is too large" message for this case per the
  above - it would be factually wrong and mask the real cause.

## Resolved

- **2026-08-24 - Multi-garment try-on failing with "Received HTML content
  instead of image" - root-caused to the garment scraper feeding non-photo
  site assets into the try-on pipeline, not a frontend bug.** User reported
  this while tapping a real product photo thumbnail in the mobile app, which
  made it look like a frontend image-selection bug - traced instead to 3
  compounding backend issues, all confirmed live against the real reported
  SuitSupply product page:
  1. `extract_images_from_html()` grabbed a page's first N `<img>` tags in
     raw DOM order with no filtering at all. On this real page the first 16
     of 21 tags were a country-flag icon, 2 logo SVGs, and 13 nav-menu
     collection/occasion banners - the actual product photo only appeared at
     position 17. Now filters out `.svg` and known non-product URL patterns
     (logo/flag/nav-menu/icon/etc.) and scans further into the DOM (bounded)
     to still reach real photos further down the page. (`58c4788`)
  2. `fetch_image_from_url()` only warned on an unexpected content-type and
     returned the bytes anyway - so the 220-byte flag SVG got returned as a
     "valid" candidate and then won the flat-lay/no-model preference in
     `create_tryon_job`'s candidate scoring over any real garment photo
     (a logo trivially "has no person" too). Now rejects outright. (`9553af0`)
  3. Both the live fetch loop and the `garment_metadata` image-URL cache were
     capped at a fixed first-2/first-4 window - once non-garment candidates
     in that window got correctly rejected by fix #2, there was nothing left
     to fall back to even though real photos existed further down the same
     gallery. Both widened to walk up to 10 candidates. (`9553af0`)

  Separately confirmed the frontend's `selectedImageUrl` wiring (added
  earlier) is correct - the currently-installed app build simply predates
  that fix, so the backend's own (buggy, now-fixed) auto-selection ran
  instead of honoring the user's tap. Verified live end-to-end via the real
  `/api/garments/scrape` endpoint against the exact reported URL: image #0
  is now the real product photo, zero site-chrome assets anywhere in the
  result. Purged the 3 SuitSupply rows in `garment_metadata` that had
  already cached the flag SVG so they re-scrape clean. Full pytest suite
  unaffected (same 7 pre-existing unrelated failures).

- **2026-08-24 - Avatar head clipped by the top logo overlay on the home
  screen.** `normalize_avatar_framing()` had no dedicated top-margin
  parameter at all - the top margin was purely an implicit leftover of
  `1.0 - target_height_percent - bottom_margin_percent`, which left only
  ~3% of canvas height as headroom. Measured directly on a real, currently-
  saved production avatar: top margin was 46px / 3.8% of a 1200px canvas -
  tight enough that slightly more hair volume, a raised chin, or a less-
  clean alpha mask edge would push the head past the top edge. Reduced
  `target_height_percent` 0.95 -> 0.90, roughly tripling the real margin to
  97px / 8.1% for a barely-noticeable size reduction. Verified against the
  same real avatar file and visually confirmed the result still looks
  natural.

- **2026-08-21 - Try-on end-to-end mobile latency (~40s) vs ~16s Gemini
  generation time - root-caused the gap, fixed part of it.** Pulled a real
  production job's full timeline from logs (2026-08-20): ~7.8s job-creation
  overhead (before the client even gets a job_id back) + ~2.6s rembg on the
  garment + ~16s Gemini generation = ~26s server-side, before any client
  polling overhead. Of that 7.8s, ~5s was `normalize_image()`'s PNG
  `optimize=True` on the garment image alone (~1s on the avatar) - Pillow's
  exhaustive PNG compression search, confirmed via direct benchmark against
  the exact real file (0.67s optimized vs 0.13s default, ~5x, for only ~5%
  smaller output) on mid-pipeline bytes headed straight to the Gemini API
  next. Removed `optimize=True` from all 4 PNG-save call sites in the image
  pipeline (`normalize_image`, `convert_to_supported_format`, `resize_image`'s
  PNG branch, `process_tryon`'s `_tryon_resize_max_long_edge`). Verified live
  on the VM with the real files: garment preprocessing 5s -> 0.65s, avatar
  ~2.3s -> 0.13s - roughly 6 real seconds off every job's server-side time.
  Not yet investigated: client-side polling interval/overhead, and whether
  `JobQueue`'s single background worker thread per gunicorn process ever
  queues jobs behind each other under real concurrent load (the one real
  trace checked showed no queueing delay, but that was a single data point,
  not a load test). (`718d310`)

- **2026-08-21 - Try-on model upgraded to Nano Banana 2 (gemini-3.1-flash-image),
  with automatic fallback to Nano Banana Pro (gemini-3-pro-image) on failure.**
  Driven by a real benchmark: 20 real try-on cases (10 garments x 2 candidate
  models, across two different real avatars) showed Nano Banana 2 averaging
  ~1.75x faster (13.8-14.1s vs 24.2s for Pro) with no quality regression on
  shared cases. Its one reliability gap - a reproducible `IMAGE_SAFETY` block
  on a specific person/garment combination (confirmed on 2 separate runs, though
  a 3rd later attempt succeeded - not 100% deterministic) - is handled by an
  automatic fallback: `process_tryon_with_fallback()` /
  `process_tryon_layered_with_fallback()` try the primary model first and
  retry with Pro only if it fails outright, wired into all 3 real call sites
  (async job queue / main `/tryon`, both legs of layered try-on, `/tryon-gemini`).
  `process_tryon()` and `process_tryon_layered()` now take an explicit
  `model_name` param instead of reading `Config.GEMINI_MODEL_NAME` directly,
  so the fallback retry doesn't mutate shared state across gunicorn's 8
  threads. Also fixed along the way: `/tryon-gemini` wasn't forwarding
  `aspect_ratio` from the request at all, and `process_tryon_layered` had no
  canvas-normalization support whatsoever (its own exit log falsely claimed
  "normalized framing" when no such step existed) - both real, separate causes
  of try-on results sometimes coming back a different size than the avatar.
  Verified live: forced a guaranteed primary failure (invalid model name) and
  confirmed the wrapper correctly caught it and recovered via Pro; normal case
  and layered flow both verified working; full pytest suite unaffected (same
  7 pre-existing unrelated failures). No API contract changes - same routes,
  params, and response shapes; the one newly-read field (`aspect_ratio`) is
  optional and defaults identically to prior behavior when absent, so older
  installed app builds are unaffected. Deployed and confirmed live on the VM.
  (`2e613b2`)

- **2026-08-21 - Garment categorization was English-only, mis-tagging German-
  storefront lower-body items as upper-body.** `categorize_garment()`'s
  keyword list had zero German vocabulary. When Zara/H&M scraping is blocked
  (no title available) and the fallback URL-slug scan runs, German words like
  `hemd` (shirt), `jacke` (jacket), `hose` (pants), `rock` (skirt) matched
  nothing - confirmed via a real `culotte-mit-spitzensaum` URL (a lower-body
  garment) mis-categorized as generic upper-body "top" at zero confidence.
  Added German vocabulary; every previously-broken real URL now categorizes
  correctly.

- **2026-08-17 - Backend went fully unresponsive for ~26 hours (silent hang,
  not a crash), root-caused to the one external call in the codebase with no
  timeout.** Reported as "is server down?" - confirmed via `curl` timing out
  completely against `server.becausefuture.tech` despite the VM's raw ports
  (22/443/5001) still accepting TCP connections, and SSH itself unable to
  complete its banner exchange (consistent with severe CPU starvation, not a
  network problem). App logs showed a completely ordinary request (a garment
  scrape) completing normally at 2026-08-16 16:43:50, then total silence -
  no exception, no stack trace, nothing - until discovered ~26 hours later.
  `gcloud compute instances get-serial-port-output` initially looked like it
  showed a fresh OOM-killed `gunicorn` process, but cross-checking against
  `journalctl -k -b -1` proved that specific kill was actually from a
  *separate*, already-self-healed incident on 2026-08-12 (systemd restarted
  it within 32 seconds that time) - the serial console ring buffer had just
  retained the old entry. This 2026-08-17 incident had no OOM record at all.

  Root cause: audited every outbound `requests.get/post` call in the
  codebase (ASOS/generic scraper, Scrape.do fallback, Lovable API,
  mixer-service try-on) - all had explicit timeouts except one: the Gemini
  `generate_content` call in `garment_discovery/ai_engine.py` (the one using
  the `google_search` tool), which relied on the SDK's default of none.
  `gunicorn` runs with `--timeout 0`, deliberately, so legitimate long-
  running avatar/try-on jobs are never killed mid-processing - but that also
  means a thread stuck in a genuinely unbounded call is never recycled or
  even noticed. With only 2 workers x 8 threads = 16 total request slots,
  it only takes a handful of these silently accumulating over hours/days
  before the app runs out of usable threads and stops responding to
  anything, with no crash to trigger `Restart=on-failure` and nothing in the
  logs to point at.

  Recovery: VM was fully unresponsive to SSH, so the only path back was a
  hard reset (`gcloud compute instances reset`) - confirmed via serial
  console this was a power-cycle, not a graceful recovery.

  Fix, two parts:
  1. Added an explicit 60s timeout to the Gemini call (matching the other
     external-call timeouts already used elsewhere). (`11bd21b`)
  2. Gave `gunicorn` a bounded backstop instead of `--timeout 0`: raised to
     `--timeout 600` (10 minutes - comfortably above any real request, since
     the slowest known legitimate path, try-on's 3x120s retry loop, tops out
     around 400s, while still bounding a genuine hang instead of leaving it
     permanent), plus `--max-requests 500 --max-requests-jitter 50` to
     periodically recycle each worker as defense-in-depth against slow leaks
     generally (relevant to the separate 2026-08-12 OOM too). Applied
     directly to the VM's systemd unit (`/etc/systemd/system/because-future-
     backend.service`) - old version backed up alongside it before editing.
  Verified live: API responding normally post-restart (`/api/login` -> 400
  in ~1s), full pytest suite unaffected (same 7 pre-existing unrelated
  `discovery_sessions`-table failures as before).

- **2026-08-14 - Group photo (3 real people) wrongly accepted - regression from the same-day multi-face fix below.** Caught within an hour of that fix shipping, via a live re-run of the same test suite: a real 3-person photo (checksummed, verified by eye - Wikimedia Commons "Kadavar-Bandfoto.jpg", 3 men sitting at roughly the same distance from camera) that was correctly rejected before any of today's fixes started passing as a single-person photo (`unique_faces=1, bodies=2` in production logs - HOG still independently saw 2 distinct people even as the face check missed them). Root cause: the 50%-of-primary size-ratio filter compares every candidate against the single *largest* detected box, which the earlier fix assumed was always the real primary subject - true for the 3 cases it was built against, false here. The largest detected "face" in this photo was actually a false hit on empty stadium seating next to one subject's hair, barely clipping his real face; because it was the biggest, it became the reference every real face got measured against, deflating the other 2 real people below the ratio floor. Fixed by confirming the largest box survives a stricter re-detection pass (frontal minNeighbors 5->7, profile 8->10) before trusting it as the reference, whenever more than one candidate exists - confirmed empirically the stadium-seat false hit disappears at minNeighbors=7 while all 3 real faces in that photo, and every other real primary face verified today (Aardra, Siuzanna, the soccer player, the shelving-unit and office/balcony cases), survive it comfortably. Verified against the group photo (now correctly rejected) plus the full existing regression set - all unchanged. (`c34868e`)

- **2026-08-14 - Avatar multi-face rejection triggered by patterned clothing
  and background clutter, not real second people.** Given 3 real single-
  person photos (checksummed, visually confirmed single-subject) that were
  each wrongly rejected as "multiple people" during a live test suite run:
  every extra "face" turned out to be a spurious cascade hit, not a second
  person - a tie-dye skirt and a sequined bodice (patterned clothing on the
  *same* subject), a building's window grid, and an ad billboard's text
  (background clutter). All three measured 37-44% of the primary face's
  size - clear of the existing 20% noise floor, but nowhere near what a real
  second person actually measures at. Raised the relative-size floor for
  what counts as a second face from 20% to 50%, and added a check that drops
  any candidate face centered in the primary subject's own torso column
  (below their own face, within ~2 face-widths either side) regardless of
  size - needed for the sequined-bodice case specifically, which measured 86%
  of the real face's size, too close to filter by ratio alone. Verified
  against all 3 real files (now accepted) plus the existing regression set
  (chairs, screenshot, shelving unit, office/balcony - all unchanged), both
  locally and by running the exact deployed function against the real files
  on the VM. (`8bb5a23`)

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

# TODO

## Backend / Infra

- **Cloud Run background jobs can silently die mid-processing.** The async try-on
  job queue (`backend/features/tryon/job_queue.py`) uses an in-memory
  `queue.Queue` + background `threading.Thread` per container instance. Once
  `POST /api/tryon` returns, Cloud Run considers that HTTP request done - it
  has no visibility into the background thread still running rembg/Gemini in
  that same process. If Cloud Run scales that instance down (common for
  low/sparse traffic even with `--no-cpu-throttling`, since throttling only
  affects CPU while an instance is alive, not whether the instance itself gets
  killed), the in-flight job dies with no error and no result - confirmed
  directly via logs (job `b5555dac...` started rembg, then nothing, until the
  cleanup-race fix caught it as abandoned ~4 minutes later).

  Decided 2026-07-29: leave `min-instances=0` for now (accept the slowness/
  occasional-failure risk) rather than pay for `min-instances=1`
  (~$125-130/month at the current 2 vCPU/2GiB no-throttling spec - roughly 3x
  the entire `bcf-internal` VM's ~$38-40/month cost). Revisit when there's
  time/budget for a real fix.

  Real options when we do revisit:
  - `min-instances=1` (quick, but recurring cost, and still not airtight
    under concurrent load spinning up extra instances)
  - Migrate the job queue to Cloud Tasks calling a dedicated processing
    endpoint - Cloud Run guarantees the request stays alive for the task's
    duration, and Tasks auto-retries on failure. Correct long-term fix, but
    real scoped work (new endpoint, task creation/auth, retry-idempotency).

- DNS cutover for `server.becausefuture.tech` from the VM to the Load
  Balancer, and VM decommission - both explicitly on hold pending approval.

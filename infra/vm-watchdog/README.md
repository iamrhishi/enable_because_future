# bcf-internal self-healing

Two independent layers, added after a 2026-09-29 incident where the VM's
guest network interface (`ens4`) failed to renew its DHCP lease and the box
became fully unreachable (SSH and the app both timed out) while GCE's own
"is the instance running" status still showed healthy - neither layer alone
would have caught everything that day.

## 1. Local app-level watchdog

`health_watchdog.sh` (deployed to `/opt/enable_because_future/backend/scripts/`
on the VM) + `health-watchdog.service`/`.timer` (in `/etc/systemd/system/` on
the VM, enabled via `systemctl enable --now health-watchdog.timer`).

Runs every 2 minutes, curls `localhost:5001/health`, restarts
`because-future-backend.service` if it doesn't respond. Catches ordinary
app crashes. **Does not catch** the OS/network-level failure above - a local
check on that box would still have found everything fine on localhost.

## 2. External health check + VM reset (Cloud Scheduler + Cloud Function)

`main.py` deployed as a Gen2 Cloud Function (`bcf-vm-watchdog`, region
`europe-west10`), triggered every 5 minutes by a Cloud Scheduler job
(`bcf-vm-health-check`, region `europe-west3` - Scheduler doesn't support
europe-west10). Runs entirely outside the VM, so it's what would have
caught 2026-09-29's actual failure mode.

Retries the public `/health` endpoint 3x (20s apart) within one invocation
before deciding the VM is down, so a normal few-second deploy restart never
triggers a reset. On persistent failure, calls
`compute.instances.reset(bcf-internal)`.

**IAM, least privilege:**
- `bcf-vm-watchdog@becausefuture.iam.gserviceaccount.com` - the function's
  runtime identity. Bound to a custom role `bcfVmResetter`
  (`compute.instances.get` + `compute.instances.reset` only), and only on
  `bcf-internal` specifically via an IAM condition - it cannot touch any
  other resource in the project.
- `bcf-scheduler-invoker@becausefuture.iam.gserviceaccount.com` - what
  Cloud Scheduler authenticates as (OIDC) to call the function. Only has
  `roles/run.invoker` on this one function.

**Redeploying after an edit to `main.py`:**
```bash
cd infra/vm-watchdog
gcloud functions deploy bcf-vm-watchdog \
  --project becausefuture --gen2 --region europe-west10 \
  --runtime python312 --source . --entry-point check_and_heal \
  --trigger-http --no-allow-unauthenticated \
  --service-account bcf-vm-watchdog@becausefuture.iam.gserviceaccount.com \
  --timeout 180s --memory 512Mi
```
(512Mi, not the 256Mi default - the `google-cloud-compute` client's
grpc/protobuf overhead alone exceeds 256Mi even before doing anything.)

**Manually triggering a check** (e.g. to verify after a change):
```bash
gcloud scheduler jobs run bcf-vm-health-check --project becausefuture --location europe-west3
gcloud functions logs read bcf-vm-watchdog --gen2 --region europe-west10 --project becausefuture --limit 10
```

**A note on the Cloud Build permission error**, if this project's Cloud
Build setup is ever reset: deploys of any Gen2 function/Cloud Run-from-source
in this project fail with a vague "missing permission on the build service
account" error unless the Compute Engine default service account
(`{PROJECT_NUMBER}-compute@developer.gserviceaccount.com`) has
`roles/cloudbuild.builds.builder` - it had zero project-level roles by
default here, which isn't obvious from the error message.

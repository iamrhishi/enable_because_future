"""
External health check for bcf-internal, triggered on a schedule by Cloud
Scheduler. Runs OUTSIDE the VM, unlike the local systemd watchdog - this is
what catches an OS/network-level failure (the VM is reachable from GCP's
control plane but not from the public internet), which a local check can't
see since it would still find everything fine on localhost.

Retries within a single invocation before declaring unhealthy, so a normal
few-second deploy restart doesn't trigger a VM reset.
"""

import time

import functions_framework
import requests

PROJECT = "becausefuture"
ZONE = "europe-west10-b"
INSTANCE = "bcf-internal"
HEALTH_URL = "https://server.becausefuture.tech/health"

RETRIES = 3
RETRY_DELAY_SECONDS = 20
REQUEST_TIMEOUT_SECONDS = 10


def _is_healthy() -> bool:
    try:
        r = requests.get(HEALTH_URL, timeout=REQUEST_TIMEOUT_SECONDS)
        return r.status_code == 200
    except requests.exceptions.RequestException:
        return False


@functions_framework.http
def check_and_heal(request):
    for attempt in range(1, RETRIES + 1):
        if _is_healthy():
            msg = f"healthy (attempt {attempt}/{RETRIES})"
            print(msg)
            return msg, 200
        if attempt < RETRIES:
            time.sleep(RETRY_DELAY_SECONDS)

    # Unhealthy across all retries - reset the VM. Imported here, not at
    # module load, so the common (healthy) path doesn't pay for grpc/protobuf
    # loading the compute client pulls in - that alone pushed this function
    # over its memory limit when imported eagerly.
    from google.cloud import compute_v1

    client = compute_v1.InstancesClient()
    operation = client.reset(project=PROJECT, zone=ZONE, instance=INSTANCE)
    msg = (
        f"unhealthy after {RETRIES} attempts over "
        f"~{RETRIES * (REQUEST_TIMEOUT_SECONDS + RETRY_DELAY_SECONDS)}s - "
        f"reset triggered (operation {operation.name})"
    )
    print(msg)
    return msg, 200

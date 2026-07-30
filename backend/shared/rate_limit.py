"""
Shared rate limiter instance.

Uses in-memory storage by default (per-instance limits only - fine for a
single VM/process, an approximation once running as multiple Cloud Run
instances since each instance tracks its own counters independently).
"""

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

limiter = Limiter(key_func=get_remote_address, default_limits=[])

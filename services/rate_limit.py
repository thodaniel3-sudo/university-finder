"""
Centralised rate limiter.

Provides a single `limiter` object that can be imported by route modules
and used via decorators like @limiter.limit("5 per minute").
"""

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address


# Storage is in-memory for now. For multi-instance production
# deployments, swap to Redis via:
#   storage_uri="redis://..."
# Storage backend choice doesn't affect the decorator API — routes
# don't need to change.
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[],           # No global default — apply per-route
    storage_uri="memory://",
)
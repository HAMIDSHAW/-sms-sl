from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_jwt_extended import JWTManager
from flask_cors import CORS

db = SQLAlchemy()
bcrypt = Bcrypt()
jwt = JWTManager()
cors = CORS()

# Rate limiting is nice-to-have, not load-bearing, if flask-limiter
# isn't installed (e.g. a flaky network dropped that one package), the
# whole app shouldn't fail to start over it. Fall back to a no-op limiter
# that makes @limiter.limit(...) a harmless pass-through.
try:
    from flask_limiter import Limiter
    from flask_limiter.util import get_remote_address
    import os
    # In memory by default (fine for one worker). With several workers or servers, point this at a shared
    # store, e.g. RATELIMIT_STORAGE_URI=redis://host:6379, so limits are counted across all of them.
    limiter = Limiter(
        key_func=get_remote_address, default_limits=[],
        storage_uri=os.environ.get("RATELIMIT_STORAGE_URI", "memory://"),
    )
except ImportError:
    class _NoOpLimiter:
        def init_app(self, app):
            pass

        def limit(self, *args, **kwargs):
            def decorator(fn):
                return fn
            return decorator

    limiter = _NoOpLimiter()


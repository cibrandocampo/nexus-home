"""Imports every model module so Alembic and the tests see the full metadata.

Add each new models module here.
"""

from app.auth import models as auth_models  # noqa: F401
from app.users import models as users_models  # noqa: F401

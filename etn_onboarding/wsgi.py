import fips_patch  # noqa: F401 — must be first import (FIPS hashlib workaround)
from app import create_app

app = create_app()

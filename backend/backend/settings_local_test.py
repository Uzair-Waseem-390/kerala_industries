# TEMPORARY local-only test settings override — see instructions/working-style.md
# ("Never test against production DB... use a local-only settings override
# for manage.py test, then delete the override file after"). Deleted at the
# end of this verification session.
#
# backend.settings now unconditionally wires a "legacy" DATABASES alias
# (real remote Postgres, DB_NAME1 is set in .env) whenever DB_NAME1 is
# present — Django's test runner would otherwise try to create/connect to a
# test database on that real remote instance. This override keeps
# 'default' (local SQLite) only.
from backend.settings import *  # noqa: F401,F403

DATABASES = {"default": DATABASES["default"]}

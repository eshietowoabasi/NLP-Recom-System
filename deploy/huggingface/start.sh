#!/bin/bash
# Prepare the database and first Admin, then hand over to supervisord (Hugging Face Space).
set -euo pipefail

export PGBIN
PGBIN=$(ls -d /usr/lib/postgresql/*/bin | sort -V | tail -1)
mkdir -p "$UPLOAD_FOLDER" "$REPORT_FOLDER"

# A secret key the Space owner did not set: generate one (sign-ins last until the next restart).
SECRET_KEY=${SECRET_KEY:-}
if [ "${#SECRET_KEY}" -lt 32 ]; then
    export SECRET_KEY
    SECRET_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(48))")
    echo "[start] SECRET_KEY not set as a Space secret; generated a temporary one."
fi

if [ ! -s "$PGDATA/PG_VERSION" ]; then
    echo "[start] Creating the database cluster"
    "$PGBIN/initdb" -D "$PGDATA" --auth=trust --username=user --encoding=UTF8 >/dev/null
fi
"$PGBIN/pg_ctl" -D "$PGDATA" -o "-k /tmp -c listen_addresses=''" -w start >/dev/null
psql -h /tmp -U user -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='nlprs'" | grep -q 1 \
    || createdb -h /tmp -U user nlprs

echo "[start] Applying database migrations"
flask db upgrade

ADMIN_USERNAME=${ADMIN_USERNAME:-admin}
ADMIN_EMAIL=${ADMIN_EMAIL:-admin@example.com}
export ADMIN_USERNAME
if python - <<'PY'
import os, sys
from app import create_app
from app.models import User
with create_app().app_context():
    sys.exit(0 if User.query.filter_by(username=os.environ["ADMIN_USERNAME"]).first() else 1)
PY
then
    echo "[start] Admin '$ADMIN_USERNAME' already exists"
else
    if [ -z "${ADMIN_PASSWORD:-}" ]; then
        ADMIN_PASSWORD=$(python -c "import secrets; print(secrets.token_urlsafe(12))")
        echo "[start] ADMIN_PASSWORD is not set as a Space secret. Admin login for this run:"
        echo "[start]   username: $ADMIN_USERNAME   password: $ADMIN_PASSWORD"
    fi
    flask create-user --username "$ADMIN_USERNAME" --email "$ADMIN_EMAIL" --role Admin --password "$ADMIN_PASSWORD"
fi

"$PGBIN/pg_ctl" -D "$PGDATA" -w stop >/dev/null
echo "[start] Starting services on port 7860"
exec supervisord -c /etc/supervisor/nlprs.conf

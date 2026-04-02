$ErrorActionPreference = "Stop"

# Local-only helper: forces SQLite for this PowerShell session/process.
$env:DJANGO_DB_ENGINE = "sqlite"

python manage.py migrate


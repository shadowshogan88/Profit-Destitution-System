$ErrorActionPreference = "Stop"

param(
    [int]$Port = 8000
)

# Local-only helper: forces SQLite for this PowerShell session/process.
$env:DJANGO_DB_ENGINE = "sqlite"

python manage.py migrate
python manage.py runserver "127.0.0.1:$Port"


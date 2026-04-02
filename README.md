# Django Referral + Wallet System

Implements the finalized concept:

- Each user can have unlimited downlines.
- Each user has only one upline (`referred_by`).
- Commission flows upward only, max 5 levels.
- Commission is created only when profit is realized.
- Investment principal is separate from wallet balance.
- Wallet balance can be reused for reinvestment.
- All commissions are logged (`CommissionLog`).
- Wallet updates automatically on profit/commission events.

## Setup

```bash
cd referral_system
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python manage.py makemigrations
python manage.py migrate
python manage.py runserver
```

## Local Dev (Force SQLite)

If your `.env` has `DJANGO_DB_ENGINE=mysql` but you want to run locally with SQLite (no MySQL client needed),
use a session-only env override:

```powershell
$env:DJANGO_DB_ENGINE='sqlite'; python manage.py migrate
```

Or use the helper scripts:

```powershell
.\scripts\local_sqlite_migrate.ps1
.\scripts\local_sqlite_runserver.ps1 -Port 8000
```

`.env` is ignored by git. Use `.env.example` as a safe template (no credentials) and keep real secrets only in your local `.env` or in cPanel env vars.

## cPanel Live With MySQL

Use environment variables in cPanel before running migrations:

```bash
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com
DJANGO_CSRF_TRUSTED_ORIGINS=https://yourdomain.com,https://www.yourdomain.com
DJANGO_SECRET_KEY=change-this-to-a-long-random-secret
DJANGO_DB_ENGINE=mysql
DJANGO_DB_NAME=cpanel_db_name
DJANGO_DB_USER=cpanel_db_user
DJANGO_DB_PASSWORD=cpanel_db_password
DJANGO_DB_HOST=localhost
DJANGO_DB_PORT=3306
```

If `DJANGO_DB_ENGINE` is not set to `mysql`, the project falls back to SQLite.

To deploy from GitHub on cPanel:

- Keep `.env` only on the server (or skip it entirely) and set the variables in cPanel instead.
- Pull/update the code from GitHub, then run `python manage.py migrate` on the server.

## API Endpoints

- `POST /api/register/` (requires `email`; sends email OTP + verification link)
- `POST /api/wallet/deposit/`
- `POST /api/investments/create/`
- `POST /api/investments/realize-profit/`
- `GET /api/users/<username>/summary/`

## Email Verification (OTP)

- Registration creates the user as inactive (`is_active=False`) until email verification completes.
- Email includes both an OTP and a verification link (OTP validity default: 10 minutes).

Configure SMTP via environment variables:

```bash
EMAIL_HOST=smtp.yourprovider.com
EMAIL_PORT=587
EMAIL_HOST_USER=your_smtp_username
EMAIL_HOST_PASSWORD=your_smtp_password
EMAIL_USE_TLS=True
EMAIL_USE_SSL=False
DEFAULT_FROM_EMAIL=no-reply@yourdomain.com
```

Optional:

```bash
EMAIL_OTP_EXPIRY_MINUTES=10
EMAIL_VERIFICATION_RESEND_COOLDOWN_SECONDS=60
EMAIL_APP_NAME="Referral System"
```

## Quick Flow Example

1. Register users with referrer usernames to build an upline chain.
2. Create investment for downline user.
3. Realize profit for that investment.
4. Investor wallet is credited with profit.
5. Uplines (up to 5) get auto-credited commissions and logs are created.

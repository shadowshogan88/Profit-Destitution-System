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

## API Endpoints

- `POST /api/register/`
- `POST /api/wallet/deposit/`
- `POST /api/investments/create/`
- `POST /api/investments/realize-profit/`
- `GET /api/users/<username>/summary/`

## Quick Flow Example

1. Register users with referrer usernames to build an upline chain.
2. Create investment for downline user.
3. Realize profit for that investment.
4. Investor wallet is credited with profit.
5. Uplines (up to 5) get auto-credited commissions and logs are created.

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0027_ensure_user_email_verified_column"),
    ]

    operations = [
        migrations.CreateModel(
            name="EmailConfiguration",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("app_name", models.CharField(default="Referral System", max_length=80)),
                ("default_from_email", models.EmailField(blank=True, default="", max_length=254)),
                ("otp_expiry_minutes", models.PositiveSmallIntegerField(default=10)),
                ("resend_cooldown_seconds", models.PositiveIntegerField(default=60)),
                ("smtp_host", models.CharField(blank=True, default="", max_length=255)),
                ("smtp_port", models.PositiveIntegerField(default=587)),
                ("smtp_username", models.CharField(blank=True, default="", max_length=255)),
                ("smtp_password", models.CharField(blank=True, default="", max_length=255)),
                ("smtp_use_tls", models.BooleanField(default=True)),
                ("smtp_use_ssl", models.BooleanField(default=False)),
                ("is_active", models.BooleanField(default=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "ordering": ["-updated_at"],
            },
        ),
    ]


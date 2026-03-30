from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0025_user_email_verified_emailotp"),
    ]

    operations = [
        migrations.CreateModel(
            name="SystemConfiguration",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("email_backend", models.CharField(default="django.core.mail.backends.smtp.EmailBackend", help_text="Example: django.core.mail.backends.smtp.EmailBackend", max_length=255)),
                ("email_host", models.CharField(default="smtp.gmail.com", max_length=255)),
                ("email_port", models.PositiveIntegerField(default=587)),
                ("email_host_user", models.CharField(blank=True, max_length=255)),
                ("email_host_password", models.CharField(blank=True, max_length=255)),
                ("email_use_tls", models.BooleanField(default=True)),
                ("email_use_ssl", models.BooleanField(default=False)),
                ("default_from_email", models.CharField(default="Profit Distribution System <no-reply@example.com>", max_length=255)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "System Configuration",
                "verbose_name_plural": "System Configuration",
            },
        ),
    ]

import uuid

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0028_emailconfiguration"),
    ]

    operations = [
        migrations.AddField(
            model_name="manualwithdrawalrequest",
            name="email_otp_verified",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="manualwithdrawalrequest",
            name="email_otp_verified_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.CreateModel(
            name="WithdrawalOtpToken",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("token", models.UUIDField(db_index=True, default=uuid.uuid4, editable=False, unique=True)),
                ("otp_code", models.CharField(max_length=8)),
                ("expires_at", models.DateTimeField()),
                ("used_at", models.DateTimeField(blank=True, null=True)),
                ("send_count", models.PositiveSmallIntegerField(default=0)),
                ("last_sent_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "withdrawal_request",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="otp_tokens",
                        to="core.manualwithdrawalrequest",
                    ),
                ),
            ],
            options={"ordering": ["-created_at"]},
        ),
    ]


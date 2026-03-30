from django.db import migrations, models
from django.utils import timezone


def backfill_manual_payment_request_code(apps, schema_editor):
    ManualPaymentRequest = apps.get_model("core", "ManualPaymentRequest")
    counters = {}

    for item in ManualPaymentRequest.objects.all().order_by("created_at", "id"):
        raw_dt = item.created_at or timezone.now()
        code_dt = timezone.localtime(raw_dt) if timezone.is_aware(raw_dt) else raw_dt
        month_key = code_dt.strftime("%Y-%m")
        counters[month_key] = counters.get(month_key, 0) + 1
        sequence = counters[month_key]
        item.request_code = code_dt.strftime(f"Add-%m/%y-{sequence:03d}")
        item.save(update_fields=["request_code"])


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0021_investment_investment_code"),
    ]

    operations = [
        migrations.AddField(
            model_name="manualpaymentrequest",
            name="request_code",
            field=models.CharField(blank=True, db_index=True, max_length=20, null=True, unique=True),
        ),
        migrations.RunPython(backfill_manual_payment_request_code, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="manualpaymentrequest",
            name="request_code",
            field=models.CharField(db_index=True, max_length=20, unique=True),
        ),
    ]

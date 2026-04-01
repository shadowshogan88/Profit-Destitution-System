from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0029_withdrawal_otp_verification"),
    ]

    operations = [
        migrations.AddField(
            model_name="emailconfiguration",
            name="notify_investment_confirmed_enabled",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="emailconfiguration",
            name="notify_profit_received_enabled",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="emailconfiguration",
            name="notify_add_money_submitted_enabled",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="emailconfiguration",
            name="notify_add_money_approved_enabled",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="emailconfiguration",
            name="notify_withdrawal_confirmed_enabled",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="emailconfiguration",
            name="notify_withdrawal_approved_enabled",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="emailconfiguration",
            name="subject_investment_confirmed",
            field=models.CharField(default="{{ app_name }} - Investment confirmed", max_length=160),
        ),
        migrations.AddField(
            model_name="emailconfiguration",
            name="subject_profit_received",
            field=models.CharField(default="{{ app_name }} - Profit received", max_length=160),
        ),
        migrations.AddField(
            model_name="emailconfiguration",
            name="subject_add_money_submitted",
            field=models.CharField(default="{{ app_name }} - Add money request submitted", max_length=160),
        ),
        migrations.AddField(
            model_name="emailconfiguration",
            name="subject_add_money_approved",
            field=models.CharField(default="{{ app_name }} - Add money approved", max_length=160),
        ),
        migrations.AddField(
            model_name="emailconfiguration",
            name="subject_withdrawal_confirmed",
            field=models.CharField(default="{{ app_name }} - Withdrawal request confirmed", max_length=160),
        ),
        migrations.AddField(
            model_name="emailconfiguration",
            name="subject_withdrawal_approved",
            field=models.CharField(default="{{ app_name }} - Withdrawal approved", max_length=160),
        ),
    ]


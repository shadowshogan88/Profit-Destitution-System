from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0019_manualwithdrawalrequest_withdrawal_fee_fixed_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="investmentpackage",
            name="is_popular",
            field=models.BooleanField(default=False),
        ),
    ]

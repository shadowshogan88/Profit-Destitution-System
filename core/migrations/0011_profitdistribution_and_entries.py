from decimal import Decimal

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0010_investmentpackage_investment_duration_days_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="ProfitDistribution",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("total_amount", models.DecimalField(decimal_places=2, max_digits=14)),
                (
                    "total_active_principal",
                    models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=14),
                ),
                (
                    "distributed_amount",
                    models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=14),
                ),
                (
                    "remainder_amount",
                    models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=14),
                ),
                ("note", models.CharField(blank=True, max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="created_profit_distributions",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="ProfitDistributionEntry",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("active_principal", models.DecimalField(decimal_places=2, max_digits=14)),
                ("payout_amount", models.DecimalField(decimal_places=2, max_digits=14)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "distribution",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="entries",
                        to="core.profitdistribution",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="profit_distribution_entries",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-payout_amount", "user__username"],
            },
        ),
    ]

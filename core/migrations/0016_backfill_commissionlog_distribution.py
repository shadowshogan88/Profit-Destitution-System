from django.db import migrations


def backfill_commission_log_distribution(apps, schema_editor):
    CommissionLog = apps.get_model('core', 'CommissionLog')
    ProfitDistributionEntry = apps.get_model('core', 'ProfitDistributionEntry')

    for log in CommissionLog.objects.filter(distribution__isnull=True).iterator():
        entry = (
            ProfitDistributionEntry.objects.filter(
                investment_id=log.investment_id,
                created_at__lte=log.created_at,
            )
            .order_by('-created_at')
            .first()
        )
        if entry is None:
            entry = (
                ProfitDistributionEntry.objects.filter(investment_id=log.investment_id)
                .order_by('-created_at')
                .first()
            )
        if entry is None:
            continue

        log.distribution_id = entry.distribution_id
        log.save(update_fields=['distribution'])


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0015_commissionlog_distribution'),
    ]

    operations = [
        migrations.RunPython(backfill_commission_log_distribution, migrations.RunPython.noop),
    ]

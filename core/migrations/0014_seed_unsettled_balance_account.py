from django.db import migrations


def create_unsettled_account(apps, schema_editor):
    UnsettledBalanceAccount = apps.get_model('core', 'UnsettledBalanceAccount')
    UnsettledBalanceAccount.objects.get_or_create(name='Unsettled Balance')


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0013_unsettledbalanceaccount_and_more'),
    ]

    operations = [
        migrations.RunPython(create_unsettled_account, migrations.RunPython.noop),
    ]

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0024_user_profile_picture"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.AddField(
                    model_name="user",
                    name="email_verified",
                    field=models.BooleanField(default=False),
                ),
            ],
        ),
    ]


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0023_manualwithdrawalrequest_request_code"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="profile_picture",
            field=models.ImageField(blank=True, null=True, upload_to="profile_pictures/"),
        ),
    ]

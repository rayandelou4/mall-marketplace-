from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0007_user_suspension"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="show_phone_on_listings",
            field=models.BooleanField(default=False),
        ),
    ]
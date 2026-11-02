from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0002_emailverificationtoken_code"),
    ]

    operations = [
        migrations.AddField(
            model_name="passwordresettoken",
            name="code",
            field=models.CharField(db_index=True, default="", editable=False, max_length=6),
        ),
    ]

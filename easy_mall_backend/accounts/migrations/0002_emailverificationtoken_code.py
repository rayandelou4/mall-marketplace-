from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="emailverificationtoken",
            name="code",
            field=models.CharField(db_index=True, default="", editable=False, max_length=6),
        ),
    ]

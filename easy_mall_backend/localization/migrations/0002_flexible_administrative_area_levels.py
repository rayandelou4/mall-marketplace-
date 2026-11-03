from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("localization", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="administrativearea",
            name="level_label",
            field=models.CharField(blank=True, max_length=80),
        ),
        migrations.AlterField(
            model_name="administrativearea",
            name="level",
            field=models.CharField(default="city", max_length=40),
        ),
    ]
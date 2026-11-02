from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("messaging", "0006_unique_participant_pair"),
    ]

    operations = [
        migrations.AddField(
            model_name="message",
            name="voice_url",
            field=models.URLField(blank=True, null=True),
        ),
    ]
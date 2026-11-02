from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("messaging", "0004_one_conversation_per_user_pair"),
    ]

    operations = [
        migrations.AddField(
            model_name="conversationparticipant",
            name="is_hidden",
            field=models.BooleanField(default=False),
        ),
    ]
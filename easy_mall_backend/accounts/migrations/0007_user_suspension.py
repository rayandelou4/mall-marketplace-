from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0006_emailverificationtoken_attempts"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="is_suspended",
            field=models.BooleanField(default=False, verbose_name="compte suspendu"),
        ),
        migrations.AddField(
            model_name="user",
            name="suspension_reason",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="user",
            name="suspended_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="user",
            name="suspension_previous_is_active",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="user",
            name="suspended_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="accounts_suspended",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("moderation", "0002_productreport_moderationaction"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="productreport",
            name="evidence",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="dispute",
            name="private_evidence",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="dispute",
            name="case_history",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="dispute",
            name="reviewed_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="disputes_reviewed",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="dispute",
            name="review_notes",
            field=models.TextField(blank=True),
        ),
    ]

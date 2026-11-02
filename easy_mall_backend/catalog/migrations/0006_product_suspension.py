import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("catalog", "0005_seller_favorite"),
    ]

    operations = [
        migrations.AddField(
            model_name="product",
            name="is_suspended",
            field=models.BooleanField(db_index=True, default=False),
        ),
        migrations.AddField(
            model_name="product",
            name="status_before_suspension",
            field=models.CharField(blank=True, choices=[('draft', 'Brouillon'), ('published', 'Publié'), ('sold', 'Vendu'), ('archived', 'Archivé')], default='', max_length=10),
        ),
        migrations.AddField(
            model_name="product",
            name="suspended_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="product",
            name="suspension_reason",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="product",
            name="suspended_by",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='suspended_products', to=settings.AUTH_USER_MODEL),
        ),
    ]

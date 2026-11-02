import django.db.models.deletion
import django.utils.timezone
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('catalog', '0006_product_suspension'),
        ('moderation', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='ProductReport',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('reason', models.CharField(choices=[('counterfeit_product', 'Produit potentiellement contrefait'), ('misleading_description', 'Description trompeuse'), ('misleading_photos', 'Photos trompeuses'), ('prohibited_product', 'Produit interdit'), ('scam_suspected', "Suspicion d'arnaque"), ('misleading_pricing', 'Prix ou caractéristiques trompeurs'), ('duplicate_or_spam', 'Annonce dupliquée ou spam'), ('other', 'Autre motif')], max_length=30)),
                ('description', models.TextField(blank=True)),
                ('status', models.CharField(choices=[('new', 'Nouveau'), ('under_review', "En cours d'examen"), ('valid', 'Fondé'), ('rejected', 'Rejeté'), ('closed', 'Clôturé')], default='new', max_length=20)),
                ('is_high_risk', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('review_notes', models.TextField(blank=True)),
                ('product', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='reports', to='catalog.product')),
                ('reporter', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='product_reports', to=settings.AUTH_USER_MODEL)),
                ('reviewed_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='product_reports_reviewed', to=settings.AUTH_USER_MODEL)),
                ('seller', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='product_reports_received', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'product_reports',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='ModerationAction',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('action', models.CharField(choices=[('created', 'Créé'), ('assigned', 'Assigné'), ('suspended', 'Suspendue'), ('reinstated', 'Rétablie'), ('removed', 'Retirée'), ('rejected', 'Rejeté'), ('needs_more_info', 'Informations complémentaires demandées'), ('resolved', 'Résolu')], max_length=25)),
                ('details', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('actor', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='moderation_actions', to=settings.AUTH_USER_MODEL)),
                ('report', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='history', to='moderation.productreport')),
            ],
            options={
                'db_table': 'moderation_actions',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddField(
            model_name='dispute',
            name='description',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AddField(
            model_name='dispute',
            name='evidence',
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
    model_name='dispute',
    name='seller',
    field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='disputes_as_seller', to=settings.AUTH_USER_MODEL),
),
        migrations.AddField(
            model_name='dispute',
            name='updated_at',
            field=models.DateTimeField(auto_now=True),
        ),
        migrations.AlterField(
            model_name='dispute',
            name='reason',
            field=models.CharField(max_length=40),
        ),
        migrations.AddConstraint(
            model_name='productreport',
            constraint=models.UniqueConstraint(condition=models.Q(('status__in', ['new', 'under_review', 'valid'])), fields=('product', 'reporter'), name='unique_active_product_report_per_user'),
        ),
    ]

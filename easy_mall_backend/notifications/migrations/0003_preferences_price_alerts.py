from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("notifications", "0002_notification_dispute_update"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterField(
            model_name="notification",
            name="notification_type",
            field=models.CharField(
                choices=[
                    ("new_message", "Nouveau message"),
                    ("new_sale", "Nouvelle vente"),
                    ("payment_received", "Paiement reçu"),
                    ("shipping", "Expédition"),
                    ("delivery", "Livraison"),
                    ("new_favorite", "Nouveau favori"),
                    ("promotion", "Promotion"),
                    ("product_reported", "Annonce signalée"),
                    ("report_decision", "Décision de modération"),
                    ("dispute_opened", "Litige ouvert"),
                    ("dispute_update", "Mise à jour du litige"),
                    ("dispute_resolved", "Litige résolu"),
                    ("listing_suspended", "Annonce suspendue"),
                    ("verification_update", "Mise à jour de vérification"),
                    ("price_drop", "Baisse de prix"),
                    ("saved_search_match", "Nouvelle annonce correspondant à une recherche"),
                ],
                max_length=24,
            ),
        ),
        migrations.CreateModel(
            name="NotificationPreference",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("price_drop_alerts", models.BooleanField(default=True)),
                ("saved_search_alerts", models.BooleanField(default=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("user", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="notification_preferences", to=settings.AUTH_USER_MODEL)),
            ],
            options={"db_table": "notification_preferences"},
        ),
    ]
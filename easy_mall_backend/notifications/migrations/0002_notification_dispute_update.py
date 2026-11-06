from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("notifications", "0001_initial"),
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
                ],
                max_length=20,
            ),
        ),
    ]
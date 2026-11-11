import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def create_default_program(apps, schema_editor):
    LoyaltyProgram = apps.get_model("promotions", "LoyaltyProgram")
    LoyaltyProgram.objects.using(schema_editor.connection.alias).get_or_create(
        pk=1,
        defaults={
            "is_active": True,
            "points_per_currency_unit": 1,
            "redemption_value_per_point": "0.01",
            "max_redemption_percent": 20,
        },
    )


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("catalog", "0011_product_variants_and_activity"),
        ("orders", "0008_orderitem_variant_attribution"),
    ]

    operations = [
        migrations.CreateModel(
            name="LoyaltyProgram",
            fields=[
                ("id", models.PositiveSmallIntegerField(default=1, editable=False, primary_key=True, serialize=False)),
                ("is_active", models.BooleanField(default=True)),
                ("points_per_currency_unit", models.DecimalField(decimal_places=2, default=1, max_digits=7, validators=[django.core.validators.MinValueValidator(0)])),
                ("redemption_value_per_point", models.DecimalField(decimal_places=4, default="0.01", max_digits=9, validators=[django.core.validators.MinValueValidator(0)])),
                ("max_redemption_percent", models.DecimalField(decimal_places=2, default=20, max_digits=5, validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(100)])),
                ("currency_rules", models.JSONField(blank=True, default=dict, help_text="Surcharges de taux par devise : points_per_currency_unit et redemption_value_per_point.")),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.CreateModel(
            name="Promotion",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=120)),
                ("discount_type", models.CharField(choices=[("percentage", "Pourcentage"), ("fixed", "Montant fixe par article"), ("sale_price", "Prix promotionnel")], max_length=12)),
                ("value", models.DecimalField(decimal_places=2, max_digits=12, validators=[django.core.validators.MinValueValidator(0)])),
                ("currency", models.CharField(blank=True, max_length=3)),
                ("min_quantity", models.PositiveSmallIntegerField(default=1, validators=[django.core.validators.MinValueValidator(1)])),
                ("min_customer_purchases", models.PositiveIntegerField(default=0)),
                ("free_shipping", models.BooleanField(default=False)),
                ("starts_at", models.DateTimeField(blank=True, null=True)),
                ("ends_at", models.DateTimeField(blank=True, null=True)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("products", models.ManyToManyField(related_name="promotions", to="catalog.product")),
                ("seller", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="promotions", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="LoyaltyTransaction",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("kind", models.CharField(choices=[("earned", "Points gagnés"), ("redeemed", "Points utilisés"), ("refunded", "Points recrédités")], max_length=10)),
                ("points_delta", models.IntegerField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("checkout_group", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="loyalty_transactions", to="orders.checkoutgroup")),
                ("order", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="loyalty_transactions", to="orders.order")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="loyalty_transactions", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.AddConstraint(
            model_name="loyaltytransaction",
            constraint=models.UniqueConstraint(condition=models.Q(order__isnull=False), fields=("order", "kind"), name="unique_loyalty_entry_per_order"),
        ),
        migrations.AddConstraint(
            model_name="loyaltytransaction",
            constraint=models.UniqueConstraint(condition=models.Q(checkout_group__isnull=False, kind="redeemed"), fields=("checkout_group", "kind"), name="unique_loyalty_redemption_per_checkout"),
        ),
        migrations.AddIndex(
            model_name="promotion",
            index=models.Index(fields=["seller", "is_active", "starts_at", "ends_at"], name="promotions_seller_62ac06_idx"),
        ),
        migrations.RunPython(create_default_program, migrations.RunPython.noop),
    ]
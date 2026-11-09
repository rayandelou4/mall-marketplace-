import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0011_product_variants_and_activity"),
        ("orders", "0007_checkout_group"),
    ]

    operations = [
        migrations.AddField(
            model_name="orderitem",
            name="variant",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="order_items", to="catalog.productvariant"),
        ),
        migrations.AddField(
            model_name="orderitem",
            name="variant_label",
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name="orderitem",
            name="conversion_visitor_id",
            field=models.UUIDField(blank=True, db_index=True, null=True),
        ),
    ]

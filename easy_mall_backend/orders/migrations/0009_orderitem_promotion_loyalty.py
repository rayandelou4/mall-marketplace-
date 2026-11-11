from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("orders", "0008_orderitem_variant_attribution"),
        ("promotions", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="loyalty_discount_amount",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=14),
        ),
        migrations.AddField(
            model_name="order",
            name="loyalty_points_redeemed",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="checkoutgroup",
            name="loyalty_discount_amount",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=14),
        ),
        migrations.AddField(
            model_name="checkoutgroup",
            name="loyalty_points_redeemed",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="orderitem",
            name="original_unit_price",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True),
        ),
        migrations.AddField(
            model_name="orderitem",
            name="promotion_discount",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=12),
        ),
        migrations.AddField(
            model_name="orderitem",
            name="promotion_name",
            field=models.CharField(blank=True, max_length=120),
        ),
        migrations.AddField(
            model_name="orderitem",
            name="loyalty_discount",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=12),
        ),
        migrations.AddField(
            model_name="orderitem",
            name="loyalty_points_redeemed",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="orderitem",
            name="original_shipping_cost",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=10),
        ),
    ]
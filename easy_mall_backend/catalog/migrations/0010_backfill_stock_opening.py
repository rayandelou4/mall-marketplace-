from itertools import islice

from django.db import migrations


def create_stock_baselines(apps, schema_editor):
    Product = apps.get_model("catalog", "Product")
    StockMovement = apps.get_model("catalog", "StockMovement")
    database = schema_editor.connection.alias
    products = Product.objects.using(database).filter(
        item_type="product",
        stock_quantity__gt=0,
        stock_movements__isnull=True,
    ).iterator(chunk_size=500)

    while batch := list(islice(products, 500)):
        StockMovement.objects.using(database).bulk_create(
            [
                StockMovement(
                    product_id=product.pk,
                    product_title=product.title,
                    actor_id=product.seller_id,
                    movement_type="opening",
                    quantity_delta=product.stock_quantity,
                )
                for product in batch
            ],
            batch_size=500,
        )


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0009_product_stockmovement"),
    ]

    operations = [
        migrations.RunPython(create_stock_baselines, migrations.RunPython.noop),
    ]

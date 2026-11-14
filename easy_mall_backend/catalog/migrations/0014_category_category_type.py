from django.db import migrations, models


def classify_service_categories(apps, schema_editor):
    Category = apps.get_model("catalog", "Category")
    database = schema_editor.connection.alias
    pending = list(
        Category.objects.using(database)
        .filter(slug="services")
        .values_list("pk", flat=True)
    )
    service_category_ids = set()

    while pending:
        category_id = pending.pop()
        if category_id in service_category_ids:
            continue
        service_category_ids.add(category_id)
        pending.extend(
            Category.objects.using(database)
            .filter(parent_id=category_id)
            .values_list("pk", flat=True)
        )

    Category.objects.using(database).filter(pk__in=service_category_ids).update(
        category_type="service"
    )


class Migration(migrations.Migration):
    dependencies = [("catalog", "0013_productactivity_table_name")]

    operations = [
        migrations.AddField(
            model_name="category",
            name="category_type",
            field=models.CharField(
                choices=[("product", "Produits"), ("service", "Services")],
                db_index=True,
                default="product",
                max_length=10,
            ),
        ),
        migrations.RunPython(
            classify_service_categories,
            migrations.RunPython.noop,
        ),
    ]
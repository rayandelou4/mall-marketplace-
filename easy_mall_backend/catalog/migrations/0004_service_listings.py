from django.db import migrations, models


def create_services_category(apps, schema_editor):
    Category = apps.get_model("catalog", "Category")
    category, _ = Category.objects.using(schema_editor.connection.alias).get_or_create(
        slug="services",
        defaults={"name": "Services", "order": 999, "is_active": True},
    )
    if not category.is_active:
        Category.objects.using(schema_editor.connection.alias).filter(pk=category.pk).update(is_active=True)


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0003_approve_archived_products"),
    ]

    operations = [
        migrations.AddField(
            model_name="product",
            name="item_type",
            field=models.CharField(
                choices=[("product", "Produit"), ("service", "Service")],
                default="product",
                max_length=10,
            ),
        ),
        migrations.AddField(
            model_name="product",
            name="price_unit",
            field=models.CharField(
                choices=[("fixed", "Forfait"), ("hour", "Par heure"), ("day", "Par jour")],
                default="fixed",
                max_length=10,
            ),
        ),
        migrations.AlterField(
            model_name="product",
            name="condition",
            field=models.CharField(
                blank=True,
                choices=[
                    ("neuf", "Neuf"),
                    ("comme_neuf", "Comme neuf"),
                    ("bon_etat", "Bon état"),
                    ("satisfaisant", "Satisfaisant"),
                    ("a_reconditionner", "À reconditionner"),
                ],
                default="",
                max_length=20,
            ),
        ),
        migrations.RunPython(create_services_category, migrations.RunPython.noop),
    ]
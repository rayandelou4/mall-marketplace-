import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("localization", "0001_initial"),
        ("orders", "0004_archive_history_entries"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="shipping_address_record",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="orders",
                to="localization.privateaddress",
            ),
        ),
    ]

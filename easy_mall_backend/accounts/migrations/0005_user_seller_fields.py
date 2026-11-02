from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0004_merge_20260905_0214"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="seller_type",
            field=models.CharField(
                choices=[("individual", "Particulier"), ("professional", "Commerçant professionnel")],
                default="individual",
                max_length=20,
                verbose_name="type de vendeur",
            ),
        ),
        migrations.AddField(
            model_name="user",
            name="shop_cover_url",
            field=models.URLField(blank=True, null=True, verbose_name="image de couverture de la boutique"),
        ),
        migrations.AddField(
            model_name="user",
            name="shop_description",
            field=models.TextField(blank=True, verbose_name="description de la boutique"),
        ),
        migrations.AddField(
            model_name="user",
            name="shop_logo_url",
            field=models.URLField(blank=True, null=True, verbose_name="logo de la boutique"),
        ),
        migrations.AddField(
            model_name="user",
            name="shop_name",
            field=models.CharField(blank=True, max_length=150, verbose_name="nom de la boutique"),
        ),
    ]

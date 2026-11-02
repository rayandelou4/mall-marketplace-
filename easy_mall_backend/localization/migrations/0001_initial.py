import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Country',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('code', models.CharField(help_text='Code ISO alpha-3, ex. COD pour la RDC', max_length=3, unique=True)),
                ('name', models.CharField(max_length=150, unique=True)),
                ('local_name', models.CharField(blank=True, max_length=150)),
                ('phone_code', models.CharField(blank=True, max_length=10)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'db_table': 'countries',
                'ordering': ['name'],
            },
        ),
        migrations.CreateModel(
            name='AdministrativeArea',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('level', models.CharField(choices=[('country', 'Pays'), ('province', 'Province / région'), ('city', 'Ville / commune'), ('district', 'District / zone'), ('neighborhood', 'Quartier / localité')], default='city', max_length=20)),
                ('name', models.CharField(max_length=150)),
                ('slug', models.SlugField(blank=True, max_length=180)),
                ('alt_names', models.JSONField(blank=True, default=list)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('country', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='areas', to='localization.country')),
                ('parent', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='children', to='localization.administrativearea')),
            ],
            options={
                'db_table': 'administrative_areas',
                'ordering': ['level', 'name'],
                'unique_together': {('country', 'parent', 'name', 'level')},
            },
        ),
        migrations.CreateModel(
            name='SellerPublicLocation',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('precision', models.CharField(choices=[('country', 'Pays'), ('province', 'Province / région'), ('city', 'Ville / commune'), ('locality', 'Quartier / zone'), ('custom', 'Autre')], default='city', max_length=20)),
                ('public_note', models.CharField(blank=True, max_length=200)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('administrative_area', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='public_seller_locations', to='localization.administrativearea')),
                ('country', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='seller_public_locations', to='localization.country')),
                ('locality', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='public_locality_seller_locations', to='localization.administrativearea')),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='public_location', to=settings.AUTH_USER_MODEL)),
            ],
            options={'db_table': 'seller_public_locations'},
        ),
        migrations.CreateModel(
            name='PrivateAddress',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('label', models.CharField(blank=True, max_length=60)),
                ('street_address', models.TextField()),
                ('landmark', models.CharField(blank=True, max_length=200)),
                ('phone_number', models.CharField(blank=True, max_length=20)),
                ('is_default', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('administrative_area', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='private_addresses', to='localization.administrativearea')),
                ('country', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='private_addresses', to='localization.country')),
                ('locality', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='private_locality_addresses', to='localization.administrativearea')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='private_addresses', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'private_addresses',
                'ordering': ['-is_default', '-updated_at'],
            },
        ),
        migrations.AddConstraint(
            model_name='privateaddress',
            constraint=models.UniqueConstraint(condition=models.Q(('is_default', True)), fields=('user',), name='unique_default_private_address_per_user'),
        ),
        migrations.CreateModel(
            name='PickupLocation',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=120)),
                ('location_type', models.CharField(choices=[('public', 'Public / général'), ('agreed', 'Point de rencontre convenu'), ('private', 'Privé / réservé')], default='public', max_length=20)),
                ('description', models.TextField(blank=True)),
                ('instructions', models.TextField(blank=True)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('administrative_area', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='pickup_locations', to='localization.administrativearea')),
                ('country', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='pickup_locations', to='localization.country')),
                ('locality', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='pickup_locality_locations', to='localization.administrativearea')),
                ('seller', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='pickup_locations', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'pickup_locations',
                'ordering': ['name'],
            },
        ),
        migrations.CreateModel(
            name='DeliveryOption',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('mode', models.CharField(choices=[('pickup', 'Remise en main propre'), ('in_city', 'Livraison dans la ville'), ('in_area', 'Livraison dans certaines zones'), ('in_province', 'Livraison dans la province / région'), ('national', 'Livraison nationale'), ('international', 'Livraison internationale')], max_length=20)),
                ('conditions', models.TextField(blank=True)),
                ('fees', models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ('estimated_delivery_days', models.PositiveSmallIntegerField(default=0)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('administrative_area', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='delivery_area_options', to='localization.administrativearea')),
                ('country', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='delivery_options', to='localization.country')),
                ('locality', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='delivery_locality_options', to='localization.administrativearea')),
                ('seller', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='delivery_options', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'delivery_options',
                'ordering': ['mode', '-is_active'],
            },
        ),
        migrations.AddField(
            model_name='deliveryoption',
            name='coverage_areas',
            field=models.ManyToManyField(blank=True, related_name='covered_by_delivery_options', to='localization.administrativearea'),
        ),
        migrations.CreateModel(
            name='SellerLocationPreference',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('show_country', models.BooleanField(default=True)),
                ('show_admin_area', models.BooleanField(default=True)),
                ('show_locality', models.BooleanField(default=False)),
                ('show_public_note', models.BooleanField(default=False)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('seller', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='location_preference', to=settings.AUTH_USER_MODEL)),
            ],
            options={'db_table': 'seller_location_preferences'},
        ),
    ]
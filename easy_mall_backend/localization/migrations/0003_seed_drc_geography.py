from django.db import migrations


PROVINCES = [
    "Bas-Uele",
    "Équateur",
    "Haut-Katanga",
    "Haut-Lomami",
    "Haut-Uele",
    "Ituri",
    "Kasaï",
    "Kasaï-Central",
    "Kasaï-Oriental",
    "Kinshasa",
    "Kongo-Central",
    "Kwango",
    "Kwilu",
    "Lomami",
    "Lualaba",
    "Mai-Ndombe",
    "Maniema",
    "Mongala",
    "Nord-Kivu",
    "Nord-Ubangi",
    "Sankuru",
    "Sud-Kivu",
    "Sud-Ubangi",
    "Tanganyika",
    "Tshopo",
    "Tshuapa",
]


def seed_drc_geography(apps, schema_editor):
    Country = apps.get_model("localization", "Country")
    AdministrativeArea = apps.get_model("localization", "AdministrativeArea")
    country, _ = Country.objects.update_or_create(
        code="COD",
        defaults={
            "name": "République démocratique du Congo",
            "local_name": "RDC",
            "phone_code": "+243",
            "is_active": True,
        },
    )
    for province in PROVINCES:
        if not AdministrativeArea.objects.filter(
            country=country,
            parent__isnull=True,
            level="province",
            name=province,
        ).exists():
            AdministrativeArea.objects.create(
                country=country,
                level="province",
                level_label="Province",
                name=province,
            )


class Migration(migrations.Migration):

    dependencies = [
        ("localization", "0002_flexible_administrative_area_levels"),
    ]

    operations = [migrations.RunPython(seed_drc_geography, migrations.RunPython.noop)]
from django.contrib import admin

from .models import (
    AdministrativeArea,
    Country,
    DeliveryOption,
    PickupLocation,
    PrivateAddress,
    SellerLocationPreference,
    SellerPublicLocation,
)

admin.site.register(Country)
admin.site.register(AdministrativeArea)
admin.site.register(SellerPublicLocation)
admin.site.register(PrivateAddress)
admin.site.register(PickupLocation)
admin.site.register(DeliveryOption)
admin.site.register(SellerLocationPreference)

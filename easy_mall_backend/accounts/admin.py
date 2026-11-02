from django.contrib import admin

from .models import EmailVerificationToken, PasswordResetToken, PhoneOTP, User

admin.site.site_header = "Mall — Administration"
admin.site.site_title = "Mall Admin"
admin.site.index_title = "Tableau de bord"


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    # ModelAdmin standard plutôt que UserAdmin de Django : notre modèle custom
    # (USERNAME_FIELD="email", pas de UserCreationForm adapté) rendrait la
    # subclass de UserAdmin fragile sans réécrire ses formulaires. Suffisant
    # pour consulter/modérer les comptes ; la réinitialisation de mot de passe
    # reste le flux self-service côté site (déjà construit).
    list_display = ["username", "email", "phone_number", "city", "country", "is_active", "is_staff", "date_joined"]
    list_filter = ["is_active", "is_staff", "is_email_verified", "is_phone_verified", "country"]
    search_fields = ["username", "email", "phone_number"]
    ordering = ["-date_joined"]
    exclude = ["password"]
    readonly_fields = ["date_joined", "last_login", "average_rating", "total_sales", "total_purchases"]


admin.site.register(EmailVerificationToken)
admin.site.register(PhoneOTP)
admin.site.register(PasswordResetToken)

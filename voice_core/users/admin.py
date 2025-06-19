from django.conf import settings
from django.contrib import admin
from django.contrib.auth import admin as auth_admin
from django.utils.translation import gettext_lazy as _

from voice_core.users.services import create_cognito_user
from .models import User

@admin.register(User)
class UserAdmin(auth_admin.UserAdmin):
    fieldsets = (
        (None, {"fields": ("email", "password", "cognito_sub", "tenant")}),
        (_("Personal info"), {"fields": ("name",)}),
        (
            _("Permissions"),
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                ),
            },
        ),
        (_("Important dates"), {"fields": ("last_login", "date_joined")}),
    )
    list_display = ["email", "name", "tenant", "is_superuser"]
    search_fields = ["name", "email"]
    ordering = ["id"]
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("tenant", "email", "name", "password1", "password2"),
            },
        ),
    )

    def save_model(self, request, obj, form, change):
        if not change and not obj.cognito_sub:
            cognito_sub = create_cognito_user(obj.email, form.cleaned_data["password1"], obj.name)
            obj.cognito_sub = cognito_sub
        super().save_model(request, obj, form, change)

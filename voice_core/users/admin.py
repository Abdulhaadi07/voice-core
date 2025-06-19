from django.conf import settings
from django.contrib import admin
from django.contrib.auth import admin as auth_admin
from django.utils.translation import gettext_lazy as _

from voice_core.users.registration.cognito import create_cognito_user
from voice_core.users.utils import resolve_tenant_from_email
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
                "fields": ("email", "name", "password1", "password2"),
            },
        ),
    )
    readonly_fields = ("tenant",)

    def save_model(self, request, obj, form, change):
        if not hasattr(obj, "tenant") or obj.tenant is None:
            obj.tenant = resolve_tenant_from_email(obj.email)

        if not change and not obj.cognito_sub:
            try:
                obj.cognito_sub = create_cognito_user(obj.email, form.cleaned_data["password1"], obj.name)
            except Exception as e:
                self.message_user(request, f"Error creating Cognito user: {e}", level="error")
                return

        super().save_model(request, obj, form, change)


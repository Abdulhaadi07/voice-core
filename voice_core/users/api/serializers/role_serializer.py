from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from rest_framework import serializers

import logging
logger = logging.getLogger(__name__)


User = get_user_model()

class RoleAssignmentSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=["admin", "supervisor", "agent"])

    def validate_role(self, value):
        """Ensure the role exists in the database."""
        if not Group.objects.filter(name=value).exists():
            logger.warning(f"Attempt to assign non-existent role: role={value}")
            raise serializers.ValidationError("Role does not exist.")
        return value

    def save(self, **kwargs):
        """Assign the given role to the user."""
        user = kwargs.get("user")
        if not user:
            raise ValueError("User instance is required to assign a role.")

        role_name = self.validated_data["role"]

        # Remove from existing platform roles
        roles_to_remove = Group.objects.filter(name__in=["admin", "supervisor", "agent"])
        user.groups.remove(*roles_to_remove)

        # Add new role
        role_group = Group.objects.get(name=role_name)
        user.groups.add(role_group)

        # Update is_staff flag based on role
        if role_name == "admin":
            user.is_staff = True
        else:
            user.is_staff = False

        user.save()
        logger.info(f"Assigned role '{role_name}' to user_id={user.id}")
        return user

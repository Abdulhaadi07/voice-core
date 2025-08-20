from django.contrib.auth import get_user_model
from rest_framework import serializers
from typing import Optional
from voice_core.tenant.models import Tenant

import logging
logger = logging.getLogger(__name__)


User = get_user_model()

class UserSerializer(serializers.ModelSerializer[User]):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ["id", "email", "name", "password"]
        extra_kwargs = {
            "email": {"required": True},
            "name": {"required": True},
        }
    
    def create(self, validated_data):
        password = validated_data.pop("password")
        return User.objects.create_user(password=password, **validated_data)


class UserListSerializer(serializers.ModelSerializer):
    """Serializer for listing users."""
    tenant_name = serializers.CharField(source='tenant.name', read_only=True)
    platform_role = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = [
            'id', 'email', 'name', 'is_active', 'date_joined', 'last_login',
            'platform_role', 'tenant_name', 'tenant_role'
        ]
        read_only_fields = fields
    
    def get_platform_role(self, obj)-> Optional[str]:
        """Get user's group names."""
        group = obj.groups.first()  # get the first (and only) group
        return group.name if group else None


class UserCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating new users."""
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = [
            'email', 'name', 'password'
        ]

    def validate(self, data):
        name = data.get('name')
        email = data.get('email')

        # Ensure name and email are provided
        if not name:
            raise serializers.ValidationError({"name": "Name is required."})
        if not email:
            raise serializers.ValidationError({"email": "Email is required."})

        tenant_id = self.context.get('tenant_id')
        if tenant_id:
            tenant = Tenant.objects.filter(id=tenant_id).first()
            if not tenant:
                raise serializers.ValidationError({"tenant": "Invalid tenant ID."})

            # Check email domain
            if tenant.domain and not email.endswith(f"@{tenant.domain}"):
                raise serializers.ValidationError(
                    {"email": f"Email domain must match tenant domain: {tenant.domain}"}
                )

            # Check for duplicates **within this tenant**
            if User.objects.filter(email=email, tenant=tenant).exists():
                raise serializers.ValidationError({"email": "This email already exists for this tenant."})
            if User.objects.filter(name=name, tenant=tenant).exists():
                raise serializers.ValidationError({"name": "This name already exists for this tenant."})

        return data

    def create(self, validated_data):
        """Create user with hashed password."""
        name = validated_data.pop("name")
        email = validated_data.pop("email")
        password = validated_data.pop("password")
        logger.info(f"User creation requested: email={email}, name={name}")
        user = User.objects.create_user(email=email, password=password, name=name)
        logger.info(f"User created: id={user.id}, email={user.email}")
        return user


class UserUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating existing users."""
    
    class Meta:
        model = User
        fields = [
            'name', 'email', 'tenant_role', 'is_active'
        ]
        read_only_fields = ['email']  # Email cannot be changed
    
    def validate(self, data):
        """Validate tenant_role if provided."""
        tenant_role = data.get('tenant_role')
        if tenant_role and tenant_role not in [User.ADMIN, User.SUPERVISOR, User.AGENT]:
            raise serializers.ValidationError(
                {"tenant_role": "Invalid tenant_role. Must be one of: admin, supervisor, agent."}
            )
        return data
    
    def update(self, instance, validated_data):
        """Update user with validated data (partial)."""
        # Update fields if provided
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        instance.save()
        return instance


class UserDetailSerializer(serializers.ModelSerializer):
    """Serializer for detailed user information."""
    tenant_name = serializers.CharField(source='tenant.name', read_only=True)
    platform_role = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = [
            'id', 'email', 'name', 'is_active', 'date_joined', 'last_login',
            'platform_role', 'tenant_name', 'tenant_role'
        ]
        read_only_fields = fields
    
    def get_platform_role(self, obj) -> Optional[str]:
        """Get detailed group information."""
        group = obj.groups.first()  # get the first (and only) group
        return group.name if group else None

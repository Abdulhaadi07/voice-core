from rest_framework import serializers

from voice_core.users.models import User


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

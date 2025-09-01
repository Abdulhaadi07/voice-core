from rest_framework import serializers
from config.settings.base import (
    VOICEMAIL_DEFAULT_MAX_MESSAGES, 
    VOICEMAIL_LIMIT_MAX_MESSAGES, 
    VOICEMAIL_PIN_MIN_LENGTH,
)

class AvailableExtensionsSerializer(serializers.Serializer):
    contexts = serializers.DictField(
        child=serializers.ListField(
            child=serializers.IntegerField(),
            help_text="List of available extension numbers for this context"
        ),
        help_text="Dictionary mapping context names to lists of available extensions"
    )
    

class AssignExtensionSerializer(serializers.Serializer):
    extension = serializers.IntegerField()
    sip_username = serializers.CharField()
    sip_password = serializers.CharField(write_only=True)
    voicemail_max_messages = serializers.IntegerField(required=False, allow_null=True)
    voicemail_pin = serializers.IntegerField(required=False, allow_null=True)

    def validate_voicemail_max_messages(self, value):
        if value is None:
            return None  # allow null if not provided

        if int(value) <= 0:
            raise serializers.ValidationError("voicemail_max_messages must be greater than zero.")
        
        if value > int(VOICEMAIL_LIMIT_MAX_MESSAGES):
            raise serializers.ValidationError("voicemail_max_messages must be less than or equal to VOICEMAIL_LIMIT_MAX_MESSAGES.")

        return value

    def validate_voicemail_pin(self, value):
        if value is None:
            return None  # allow null or empty string if not provided

        # must be alteast VOICEMAIL_PIN_MIN_LENGTH digits
        if len(str(value)) < int(VOICEMAIL_PIN_MIN_LENGTH):
            raise serializers.ValidationError(f"voicemail_pin must be alteast {VOICEMAIL_PIN_MIN_LENGTH} digits.")

        return value
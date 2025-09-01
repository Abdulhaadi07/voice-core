from rest_framework import serializers
from config.settings.base import (
    VOICEMAIL_DEFAULT_MAX_MESSAGES, 
    VOICEMAIL_LIMIT_MAX_MESSAGES, 
    VOICEMAIL_PIN_MIN_LENGTH,
)
from voice_core.users.models import VoicemailAssignment


class ConfigureVoicemailSerializer(serializers.Serializer):
    voicemail_max_messages = serializers.IntegerField(required=False, default=VOICEMAIL_DEFAULT_MAX_MESSAGES)
    voicemail_pin = serializers.IntegerField(required=True) 

    def validate_voicemail_max_messages(self, value):
        if value is None:
            return VOICEMAIL_DEFAULT_MAX_MESSAGES  # Set default max_messages when not given

        if int(value) <= 0:
            raise serializers.ValidationError("voicemail_max_messages must be greater than zero.")

        if int(value) > int(VOICEMAIL_LIMIT_MAX_MESSAGES):
            raise serializers.ValidationError("voicemail_max_messages must be less than or equal to VOICEMAIL_LIMIT_MAX_MESSAGES.")

        return value

    def validate_voicemail_pin(self, value):
        if value is None:
            raise serializers.ValidationError("voicemail_pin is required and cannot be null.")
 
        # must be alteast VOICEMAIL_PIN_MIN_LENGTH digits
        if len(str(value)) < int(VOICEMAIL_PIN_MIN_LENGTH):
            raise serializers.ValidationError(f"voicemail_pin must be alteast {VOICEMAIL_PIN_MIN_LENGTH} digits.")

        return value


class VoicemailSerializer(serializers.ModelSerializer):
    class Meta:
        model = VoicemailAssignment
        fields = ["id", "voicemail_id", "voicemail_pin", "user"]
        read_only_fields = ["id"]


class RecordingsSerializer(serializers.Serializer):
    message_id = serializers.CharField()
    caller = serializers.CharField()
    duration = serializers.IntegerField()
    timestamp = serializers.DateTimeField()


class RecordingsFolderSerializer(serializers.Serializer):
    folder_id = serializers.IntegerField()
    folder_name = serializers.CharField()
    messages_count = serializers.IntegerField()


class UpdateVoicemailSerializer(serializers.Serializer):
    folder_id = serializers.IntegerField(default=2)  # Default "Old" folder


class AllVoicemailSerializer(serializers.Serializer):
    voicemail_id = serializers.IntegerField()
    total_messages = serializers.IntegerField()
    folders = RecordingsFolderSerializer(many=True)
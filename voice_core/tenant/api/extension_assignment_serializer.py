from rest_framework import serializers

class AssignExtensionSerializer(serializers.Serializer):
    # context_name = serializers.CharField(required=False, allow_blank=True)
    extension = serializers.IntegerField()
    sip_username = serializers.CharField()
    sip_password = serializers.CharField(write_only=True)
    voicemail_max_messages = serializers.IntegerField(required=False, default=10)
    voicemail_pin = serializers.IntegerField(required=False, allow_null=True)

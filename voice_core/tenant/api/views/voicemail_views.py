from django.db.models import Q
from django.contrib.admin.models import (
    ADDITION, 
    CHANGE,
    LogEntry, 
)
from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.decorators import action
from voice_core.users.permissions import IsPlatformAdminOrTenantAdmin
from voice_core.users.models import (
	User, 
    VoicemailAssignment
)
from voice_core.tenant.api.serializers.voicemail_serializer import (
    ConfigureVoicemailSerializer,
    VoicemailSerializer,
    RecordingsFolderSerializer,
    UpdateVoicemailSerializer,
    RecordingsSerializer,
    AllVoicemailSerializer,
)
from voice_core.services.voicemail.assign_voicemail import (
    assign_voicemail
)
from voice_core.services.voicemail.get_voicemail import (
    get_voicemail_all_recordings,
    get_voicemail_recordings_by_folder,
    get_voicemail_recording,
)

from voice_core.services.voicemail.update_voicemail import set_voicemail_as_read


import logging
logger = logging.getLogger(__name__)


@extend_schema(tags=["Voicemail Management"])
class VoicemailViewSet(viewsets.GenericViewSet):
    serializer_class = VoicemailSerializer  # default serializer

    def get_serializer_class(self):
        if self.action == "set_voicemail_configure":
            self.permission_classes = [IsPlatformAdminOrTenantAdmin]
            return ConfigureVoicemailSerializer
        if self.action == "get_voicemail":
            self.permission_classes = [IsAuthenticated]
            return VoicemailSerializer
        if self.action in ["get_all_voicemail", "get_voicemail_by_folder"]:
            self.permission_classes = [IsAuthenticated]
            return RecordingsFolderSerializer
        if self.action in ["set_message_as_read"]:
            self.permission_classes = [IsAuthenticated]
            return UpdateVoicemailSerializer
        return super().get_serializer_class()
    
    # superadmin/tenantadmin access
    @action(detail=True, methods=["post"], url_path="", url_name="set_voicemail_configure")
    def set_voicemail_configure(self, request, tenant_id=None, user_id=None):
        logger.info(f"Assign voicemail requested tenant_id={tenant_id}, user_id={user_id}")
        
        # Validate tenant_id and user_id
        try:
            tenant_id = int(tenant_id)
            user_id = int(user_id)
        except (ValueError, TypeError):
            return Response({"detail": "Invalid tenant_id or user_id"}, status=status.HTTP_400_BAD_REQUEST)

        # Validate input data
        serializer = ConfigureVoicemailSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        voicemail_max_messages = serializer.validated_data.get("voicemail_max_messages")
        voicemail_pin = serializer.validated_data.get("voicemail_pin")

        # Fetch user and tenant
        try:
            user = User.objects.select_related("tenant").get(pk=user_id, tenant_id=tenant_id)
        except User.DoesNotExist:
            return Response({"detail": "User not found for this tenant"}, status=status.HTTP_404_NOT_FOUND)

        tenant = user.tenant

        try:
            assign_voicemail(tenant, user, voicemail_pin, voicemail_max_messages)
        except Exception as e:
            logger.error(f"Voicemail assignment failed for tenant_id={tenant.id}, user_id={user.id}: {e}", exc_info=True)
            return Response(
                {"detail": "Voicemail assignment failed"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        logger.info(f"Voicemail assigned to user_id={user_id} in tenant_id={tenant_id}")
        return Response({"detail": "Voicemail successfully assigned"}, status=status.HTTP_200_OK)

    # superadmin/owner/tenantadmin access
    @action(detail=True, methods=["get"], url_path="", url_name="get_voicemail")
    def get_voicemail(self, request, tenant_id=None, user_id=None):
        logger.info(f"Assign voicemail requested tenant_id={tenant_id}, user_id={user_id}")
        
        # Validate tenant_id and user_id
        try:
            tenant_id = int(tenant_id)
            user_id = int(user_id)
        except (ValueError, TypeError):
            return Response({"detail": "Invalid tenant_id or user_id"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.select_related("tenant").get(pk=user_id, tenant_id=tenant_id)
        except User.DoesNotExist:
            return Response({"detail": "User not found for this tenant"}, status=status.HTTP_404_NOT_FOUND)

        # Restrict access → only self or admins
        if request.user != user:
            # Check if user has admin permissions
            if not IsPlatformAdminOrTenantAdmin().has_permission(request, self):
                raise PermissionDenied("You are not authorized to access this voicemail.")


        voicemail_config = VoicemailAssignment.objects.filter(user=user)
        if not voicemail_config.exists():
            return Response({"detail": "No voicemail assigned for this user"}, status=status.HTTP_404_NOT_FOUND)

        serializer = VoicemailSerializer(instance=voicemail_config.first())
        return Response(serializer.data, status=status.HTTP_200_OK)


    # superadmin/owner/tenantadmin access
    @action(detail=True, methods=["get"], url_path="messages", url_name="get_all_voicemail")
    def get_all_voicemail(self, request, tenant_id=None, user_id=None):
        try:
            user = User.objects.select_related("tenant").get(pk=user_id, tenant_id=tenant_id)
        except User.DoesNotExist:
            return Response({"detail": "User not found"}, status=status.HTTP_404_NOT_FOUND)

        if request.user != user and not IsPlatformAdminOrTenantAdmin().has_permission(request, self):
            raise PermissionDenied("You are not authorized.")

        voicemail = VoicemailAssignment.objects.filter(user=user).first()
        if not voicemail:
            return Response({"detail": "No voicemail assigned"}, status=status.HTTP_404_NOT_FOUND)

        data = get_voicemail_all_recordings(user.tenant, user, voicemail.voicemail_id)

        if data is None:
            return Response({"detail": "Invalid Action"}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        return Response(data, status=status.HTTP_200_OK)

    # superadmin/owner/tenantadmin access
    @action(
        detail=True,
        methods=["get"],
        url_path="messages/folder/(?P<folder_id>[^/.]+)",
        url_name="get_voicemail_by_folder"
    )
    def get_voicemail_by_folder(self, request, tenant_id=None, user_id=None, folder_id=None):
        try:
            user = User.objects.select_related("tenant").get(pk=user_id, tenant_id=tenant_id)
        except User.DoesNotExist:
            return Response({"detail": "User not found"}, status=status.HTTP_404_NOT_FOUND)

        if request.user != user and not IsPlatformAdminOrTenantAdmin().has_permission(request, self):
            raise PermissionDenied("You are not authorized.")

        voicemail = VoicemailAssignment.objects.filter(user=user).first()
        if not voicemail:
            return Response({"detail": "No voicemail assigned"}, status=status.HTTP_404_NOT_FOUND)

        data = get_voicemail_recordings_by_folder(
            user.tenant, user, voicemail.voicemail_id, int(folder_id)
        )
        if data is None:
            return Response({"detail": "Invalid Action"}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        return Response(data, status=status.HTTP_200_OK)

    # only owner access
    @action(
        detail=True,
        methods=["put"],
        url_path="messages/(?P<message_id>[^/.]+)/read",
        url_name="set_message_as_read"
    )
    def set_message_as_read(self, request, tenant_id=None, user_id=None, message_id=None):
        folder_id = request.data.get("folder_id", 2)
        try:
            user = User.objects.select_related("tenant").get(pk=user_id, tenant_id=tenant_id)
        except User.DoesNotExist:
            return Response({"detail": "User not found"}, status=status.HTTP_404_NOT_FOUND)
        
        voicemail = VoicemailAssignment.objects.filter(user=user).first()
        if not voicemail:
            return Response({"detail": "No voicemail assigned"}, status=status.HTTP_404_NOT_FOUND)

        data = set_voicemail_as_read(
            user.tenant, user, voicemail.voicemail_id, message_id, folder_id
        )

        if data is None:
            return Response({"detail": "Invalid Action"}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        
        return Response(data, status=status.HTTP_200_OK)

    # only owner access
    @action(
        detail=True,
        methods=["get"],
        url_path="messages/(?P<message_id>[^/.]+)/play",
        url_name="get_message_recordings"
    )
    def get_message_recordings(self, request, tenant_id=None, user_id=None, message_id=None):
        try:
            user = User.objects.select_related("tenant").get(pk=user_id, tenant_id=tenant_id)
        except User.DoesNotExist:
            return Response({"detail": "User not found"}, status=status.HTTP_404_NOT_FOUND)

        voicemail = VoicemailAssignment.objects.filter(user=user).first()
        if not voicemail:
            return Response({"detail": "No voicemail assigned"}, status=status.HTTP_404_NOT_FOUND)

        recording, content_type = get_voicemail_recording(
            user.tenant, user, voicemail.voicemail_id, message_id
        )

        if recording is None:
            return Response({"detail": "Invalid Action"}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        from django.http import HttpResponse
        return HttpResponse(recording, content_type=content_type)

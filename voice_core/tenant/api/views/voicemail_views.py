from django.db.models import Q
from django.http import StreamingHttpResponse 
from drf_spectacular.utils import (
    extend_schema,
    OpenApiResponse
)
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
    AllVoicemailSerializer,
)
from voice_core.services.voicemail.assign_voicemail import (
    assign_voicemail
)
from voice_core.services.voicemail.get_voicemail import (
    get_all_voicemails,
    get_voicemails_by_folder,
    get_voicemail_recording,
)
from voice_core.services.voicemail.update_voicemail import set_voicemail_as_read

import logging
logger = logging.getLogger(__name__)
import requests


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
    @extend_schema(
        summary="Set voicemail configuration of a User",
        description=(
            "Assign or update voicemail configuration (PIN, max messages) for a user.\n\n"
            "**Access:** SuperAdmin, TenantAdmin"
        ),
        request=ConfigureVoicemailSerializer,
        responses={
            200: OpenApiResponse(description="Voicemail successfully assigned"),
            400: OpenApiResponse(description="Invalid input"),
            404: OpenApiResponse(description="User not found"),
            500: OpenApiResponse(description="Voicemail assignment failed"),
        },
    )
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
    @extend_schema(
        summary="Retrieve voicemail configuration of a User",
        description=(
            "Get voicemail configuration details for a specific user.\n\n"
            "**Access:** Owner, SuperAdmin, TenantAdmin"
        ),
        responses={
            200: VoicemailSerializer,
            400: OpenApiResponse(description="Invalid tenant_id or user_id"),
            403: OpenApiResponse(description="Not authorized"),
            404: OpenApiResponse(description="User or voicemail not found"),
        },
    )
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
                return Response(
                    {"detail": "You are not authorized to access this voicemail."},
                    status=status.HTTP_403_FORBIDDEN
                )

        voicemail_config = VoicemailAssignment.objects.filter(user=user)
        if not voicemail_config.exists():
            return Response({"detail": "No voicemail assigned for this user"}, status=status.HTTP_404_NOT_FOUND)
        serializer = VoicemailSerializer(instance=voicemail_config.first())
        return Response(serializer.data, status=status.HTTP_200_OK)

    # superadmin/owner/tenantadmin access
    @extend_schema(
        summary="Retrieve all voicemails for a User",
        description=(
            "Retrieve all voicemail messages assigned to a user.\n\n"
            "**Access:** Owner, SuperAdmin, TenantAdmin"
        ),
        responses={
            200: AllVoicemailSerializer,
            403: OpenApiResponse(description="Not authorized"),
            404: OpenApiResponse(description="User or voicemail not found"),
        },
    )
    @action(detail=True, methods=["get"], url_path="messages", url_name="get_all_voicemail")
    def get_all_voicemail(self, request, tenant_id=None, user_id=None):
        # 401 when not authenticated
        if not request.user or not request.user.is_authenticated:
            return Response({"message": "Authentication required"}, status=status.HTTP_401_UNAUTHORIZED)
        try:
            user = User.objects.select_related("tenant").get(pk=user_id, tenant_id=tenant_id)
        except User.DoesNotExist:
            return Response({"message": "Voicemail not found"}, status=status.HTTP_404_NOT_FOUND)

        if request.user != user and not IsPlatformAdminOrTenantAdmin().has_permission(request, self):
            return Response({"message": "Access denied"}, status=status.HTTP_403_FORBIDDEN)

        voicemail = VoicemailAssignment.objects.filter(user=user).first()
        if not voicemail:
            return Response({"message": "Voicemail not found"}, status=status.HTTP_404_NOT_FOUND)

        data = get_all_voicemails(
            user.tenant, user, voicemail.voicemail_id
        )
        if data is None:
            return Response({"message": "Voice service down"}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        return Response(data, status=status.HTTP_200_OK)

    # superadmin/owner/tenantadmin access
    @extend_schema(
        summary="Retrieve voicemails by folder",
        description=(
            "Retrieve voicemail messages from a specific folder (e.g., Inbox, Deleted, Saved).\n\n"
            "**Access:** Owner, SuperAdmin, TenantAdmin"
        ),
        responses={
            200: RecordingsFolderSerializer,
            403: OpenApiResponse(description="Not authorized"),
            404: OpenApiResponse(description="User or voicemail not found"),
        },
    )
    @action(
        detail=True,
        methods=["get"],
        url_path="messages/folder/(?P<folder_id>[^/.]+)",
        url_name="get_voicemail_by_folder"
    )
    def get_voicemail_by_folder(self, request, tenant_id=None, user_id=None, folder_id=None):
        # 401 when not authenticated
        if not request.user or not request.user.is_authenticated:
            return Response({"message": "Authentication required"}, status=status.HTTP_401_UNAUTHORIZED)
        try:
            user = User.objects.select_related("tenant").get(pk=user_id, tenant_id=tenant_id)
        except User.DoesNotExist:
            return Response({"message": "User not found"}, status=status.HTTP_404_NOT_FOUND)

        if request.user != user and not IsPlatformAdminOrTenantAdmin().has_permission(request, self):
            return Response({"message": "Access denied"}, status=status.HTTP_403_FORBIDDEN)

        voicemail = VoicemailAssignment.objects.filter(user=user).first()
        if not voicemail:
            return Response({"message": "Voicemail not found"}, status=status.HTTP_404_NOT_FOUND)

        data = get_voicemails_by_folder(
            user.tenant, user, voicemail.voicemail_id, int(folder_id)
        )
        if data is None:
            return Response({"message": "No voicemail found"}, status=status.HTTP_404_NOT_FOUND)
        return Response(data, status=status.HTTP_200_OK)

    # only owner access
    @extend_schema(
        summary="Voicemail marked as read/unread",
        description=(
            "Move a voicemail message to the read/unread folder.\n\n"
            "**Access:** Owner only.\n\n"
            "Folder 1: unread.\n\n"
            "Folder 2: read."
        ),
        request=UpdateVoicemailSerializer,
        responses={
            204: OpenApiResponse(description="voicemail has been moved successfully"),
            404: OpenApiResponse(description="User or voicemail not found"),
            503: OpenApiResponse(description="Invalid Action"),
        },
    )
    @action(
        detail=True,
        methods=["put"],
        url_path="messages/(?P<message_id>[^/.]+)/read",
        url_name="set_message_as_read"
    )
    def set_message_as_read(self, request, tenant_id=None, user_id=None, message_id=None):
        # 401 when not authenticated
        if not request.user or not request.user.is_authenticated:
            return Response({"message": "Authentication required"}, status=status.HTTP_401_UNAUTHORIZED)
        folder_id = request.data.get("folder_id", 2)
        try:
            user = User.objects.select_related("tenant").get(pk=user_id, tenant_id=tenant_id)
        except User.DoesNotExist:
            return Response({"message": "User not found"}, status=status.HTTP_404_NOT_FOUND)
        # Only owner or admins
        if request.user != user and not IsPlatformAdminOrTenantAdmin().has_permission(request, self):
            return Response({"message": "Access denied"}, status=status.HTTP_403_FORBIDDEN)
        
        voicemail = VoicemailAssignment.objects.filter(user=user).first()
        if not voicemail:
            return Response({"message": "Voicemail not found"}, status=status.HTTP_404_NOT_FOUND)

        data = set_voicemail_as_read(
            user.tenant, user, voicemail.voicemail_id, message_id, folder_id
        )
        if data is None:
            return Response({"message": "No voicemail found"}, status=status.HTTP_404_NOT_FOUND)
        return Response(data, status=status.HTTP_204_NO_CONTENT)

    # only owner access
    @extend_schema(
        summary="Retrieve voicemail recording",
        description=(
            "Retrieve and stream the audio recording of a voicemail message.\n\n"
            "**Access:** Owner only"
        ),
        responses={
            200: OpenApiResponse(description="Binary audio stream (audio/wav, audio/mp3, etc.)"),
            401: OpenApiResponse(description="Authentication required"),
            403: OpenApiResponse(description="Access denied"),
            404: OpenApiResponse(description="Voicemail not found"),
            503: OpenApiResponse(description="Voice service down"),
            504: OpenApiResponse(description="Voice service timeout"),
        },
    )
    @action(
        detail=True,
        methods=["get"],
        url_path="messages/(?P<message_id>[^/.]+)/play",
        url_name="get_message_recordings",
    )
    def get_message_recordings(self, request, tenant_id=None, user_id=None, message_id=None):
        # 401 when not authenticated
        if not request.user or not request.user.is_authenticated:
            return Response({"message": "Authentication required"}, status=status.HTTP_401_UNAUTHORIZED)

        # Resolve user
        try:
            user = User.objects.select_related("tenant").get(pk=user_id, tenant_id=tenant_id)
        except User.DoesNotExist:
            return Response({"message": "User not found"}, status=status.HTTP_404_NOT_FOUND)

        # Only owner or admins
        if request.user != user and not IsPlatformAdminOrTenantAdmin().has_permission(request, self):
            return Response({"message": "Access denied"}, status=status.HTTP_403_FORBIDDEN)

        # Check voicemail assignment
        voicemail = VoicemailAssignment.objects.filter(user=user).first()
        if not voicemail:
            return Response({"message": "Voicemail not found"}, status=status.HTTP_404_NOT_FOUND)

        # Fetch chunk iterator + headers from service
        try:
            chunks_iter, headers = get_voicemail_recording(
                user.tenant, user, voicemail.voicemail_id, message_id
            )
        except requests.Timeout:
            return Response({"message": "Voice service timeout"}, status=status.HTTP_504_GATEWAY_TIMEOUT)
        if chunks_iter is None:
            return Response({"message": "No such voicemail message"}, status=status.HTTP_404_NOT_FOUND)

        resp = StreamingHttpResponse(
            chunks_iter,
            content_type=(headers or {}).get("Content-Type", "audio/wav"),
        )
        # Pass through useful headers if present. Avoid Content-Length when stream may end early.
        if headers:
            for hk in [
                "Content-Disposition",
                "X-Stream-Timeout",
                "X-Stream-Timeout-Policy",
            ]:
                if hk in headers:
                    resp[hk] = headers[hk]
        # Encourage true streaming on proxies
        resp["X-Accel-Buffering"] = "no"
        resp["Cache-Control"] = "no-cache"
        return resp

from django.db.models import Q
from django.http import StreamingHttpResponse 
from drf_spectacular.utils import (
    extend_schema,
    OpenApiResponse
)
from rest_framework import status, viewsets
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.decorators import action
from voice_core.users.permissions import IsPlatformAdminOrTenantAdmin
from voice_core.users.models import (
	User, 
    VoicemailAssignment
)
from voice_core.tenant.api.serializers.voicemail_serializer import (
    AllVoicemailSerializer,
    ConfigureVoicemailSerializer,
    RecordingsFolderSerializer,
    UpdateVoicemailSerializer,
    VoicemailSerializer,
    VoicemailRecordingSerializer,
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
            return Response({"message": "Invalid tenant_id or user_id"}, status=status.HTTP_400_BAD_REQUEST)

        # Validate input data
        serializer = ConfigureVoicemailSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        voicemail_max_messages = serializer.validated_data.get("voicemail_max_messages")
        voicemail_pin = serializer.validated_data.get("voicemail_pin")

        # Fetch user and tenant
        try:
            user = User.objects.select_related("tenant").get(pk=user_id, tenant_id=tenant_id)
        except User.DoesNotExist:
            return Response({"message": "User not found for this tenant"}, status=status.HTTP_404_NOT_FOUND)

        tenant = user.tenant

        try:
            assign_voicemail(tenant, user, voicemail_pin, voicemail_max_messages)
        except ValidationError as e:
            msg = "Validation Error"
            logger.error(f"Voicemail assignment failed for tenant_id={tenant.id}, user_id={user.id}: {e}", exc_info=True)
            return Response(
                {"message": f"Voicemail assignment failed: {msg}"},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            msg = str(e)
            logger.error(f"Voicemail assignment failed for tenant_id={tenant.id}, user_id={user.id}: {e}", exc_info=True)
            return Response(
                {"message": f"Voicemail assignment failed: {msg}"},
                status=status.HTTP_400_BAD_REQUEST  
            )

        logger.info(f"Voicemail assigned to user_id={user_id} in tenant_id={tenant_id}")
        return Response({"message": "Voicemail successfully assigned"}, status=status.HTTP_200_OK)

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
        except (ValueError, TypeError) as e:
            return Response({"message": f"Invalid tenant_id or user_id."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.select_related("tenant").get(pk=user_id, tenant_id=tenant_id)
        except User.DoesNotExist:
            return Response({"message": "User not found for this tenant"}, status=status.HTTP_404_NOT_FOUND)

        # Restrict access → only self or admins
        if request.user != user:
            # Check if user has admin permissions
            if not IsPlatformAdminOrTenantAdmin().has_permission(request, self):
                return Response(
                    {"message": "Access denied"},
                    status=status.HTTP_403_FORBIDDEN
                )

        voicemail_config = VoicemailAssignment.objects.filter(user=user)
        if not voicemail_config.exists():
            return Response({"message": "No voicemail assigned for this user"}, status=status.HTTP_404_NOT_FOUND)
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
        try:
            data = get_all_voicemails(
                user.tenant, user, voicemail.voicemail_id
            )
            if data is None:
                return Response({"message": "Voicemail service down"}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
            return Response(data, status=status.HTTP_200_OK)
        except Exception as e:
            msg = str(e)
            return Response({"message": f"Voicemail retrieval failed: {msg}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

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
        try:
            data = get_voicemails_by_folder(
                user.tenant, user, voicemail.voicemail_id, int(folder_id)
            )
            if data is None:
                return Response({"message": "No voicemail found"}, status=status.HTTP_404_NOT_FOUND)
            return Response(data, status=status.HTTP_200_OK)
        except Exception as e:
            msg = str(e)
            return Response({"message": f"Voicemail retrieval failed: {msg}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    # superadmin/owner/tenantadmin access
    @extend_schema(
        summary="Mark Voicemail as read/unread",
        description=(
            "Move a voicemail message to the read/unread folder.\n\n"
            "**Access:** Owner, SuperAdmin, TenantAdmin.\n\n"
            "**Folders:**\n"
            "  - 1: unread\n"
            "  - 2: read\n\n"
            "**Usage:**\n"
            "Send a PATCH request with JSON body `{ 'read': true }` to mark as read, or `{ 'read': false }` to mark as unread."
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
    def set_message_status(self, request, tenant_id=None, user_id=None, message_id=None):
        if not request.user or not request.user.is_authenticated:
            return Response({"message": "Authentication required"}, status=status.HTTP_401_UNAUTHORIZED)

        serializer = UpdateVoicemailSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        read_status = serializer.validated_data["read"]
        folder_id = 2 if read_status else 1
        logger.info(
            f"User {request.user.email} (id={request.user.id}) requests to change status of voicemail "
            f"message_id={message_id} under tenant_id={tenant_id}, user_id={user_id} "
            f"→ read={read_status} (folder_id={folder_id})"
        )
        
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
        try:
            data = set_voicemail_as_read(
                user.tenant, user, voicemail.voicemail_id, message_id, folder_id
            )
            if data is None:
                return Response({"message": "No voicemail found"}, status=status.HTTP_404_NOT_FOUND)
            return Response(data, status=status.HTTP_204_NO_CONTENT)
        except Exception as e:
            msg = str(e)
            return Response({"message": f"Voicemail retrieval failed: {msg}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    # superadmin/owner/tenantadmin access
    @extend_schema(
        summary="Stream (play) a voicemail message",
        description=(
            "Retrieve and stream the audio recording of a voicemail message.\n\n"
            "Proxy streams the voicemail audio (chunked). \n\n"
            "Automatically marks the message as read ONLY after actual playback (after a byte threshold is sent). "
            "Query params:\n"
            " - auto_mark_read=0  (disable auto mark) [Deafult: 1]\n"
            " - mark_after_bytes=<int> (default 8192)\n\n"
            "**Access:** Owner, SuperAdmin, TenantAdmin"
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
        url_name="get_message_recordings"
    )
    def get_message_recordings(self, request, tenant_id=None, user_id=None, message_id=None):
        if not request.user or not request.user.is_authenticated:
            return Response({"message": "Authentication required"}, status=status.HTTP_401_UNAUTHORIZED)
        
        try:
            user = User.objects.select_related("tenant").get(pk=user_id, tenant_id=tenant_id)
        except User.DoesNotExist:
            return Response({"message": "User not found"}, status=status.HTTP_404_NOT_FOUND)

        # Only owner or admins
        if request.user != user and not IsPlatformAdminOrTenantAdmin().has_permission(request, self):
            return Response({"message": "Access denied"}, status=status.HTTP_403_FORBIDDEN)

        # Voicemail assignment
        voicemail = VoicemailAssignment.objects.filter(user=user).first()
        if not voicemail:
            return Response({"message": "Voicemail not found"}, status=status.HTTP_404_NOT_FOUND)

        # Upstream fetch (iterator + headers)
        chunks_iter, headers = get_voicemail_recording(
            user.tenant, user, voicemail.voicemail_id, message_id
        )
        if chunks_iter is None:
            return Response({"message": "No such voicemail message"}, status=status.HTTP_404_NOT_FOUND)

        # Mark controls
        auto_mark = request.query_params.get("auto_mark_read", "1") != "0"
        try:
            threshold = int(request.query_params.get("mark_after_bytes", 8192))
            if threshold < 1:
                threshold = 8192
        except ValueError:
            threshold = 8192

        try: 
            state = {"marked": False, "sent": 0}

            def mark_as_read_safe():
                if state["marked"] or not auto_mark:
                    return
                try:
                    # Folder 2 assumed = read (adjust if your domain differs)
                    set_voicemail_as_read(
                        user.tenant,
                        user,
                        voicemail.voicemail_id,
                        message_id,
                        2  # read folder
                    )
                    state["marked"] = True
                    logger.info(
                        f"Voicemail auto-marked read after {state['sent']} bytes | "
                        f"tenant_id={getattr(user.tenant, 'id', 'unknown')} "
                        f"user_id={user.id} "
                        f"voicemail_id={voicemail.voicemail_id} "
                        f"message_id={message_id}"
                    )

                except Exception as e:
                    logger.error(
                        f"Failed auto-mark read | tenant_id={getattr(user.tenant, 'id', 'unknown')} "
                        f"user_id={getattr(user, 'id', 'unknown')} "
                        f"voicemail_id={voicemail.voicemail_id} "
                        f"message_id={message_id} "
                        f"error={e}",
                        exc_info=True
                    )


            def streaming_wrapper():
                for chunk in chunks_iter:
                    if not chunk:
                        continue
                    state["sent"] += len(chunk)
                    if auto_mark and not state["marked"] and state["sent"] >= threshold:
                        mark_as_read_safe()
                    yield chunk
                # Very small file (below threshold) but some data was delivered
                if auto_mark and state["sent"] > 0 and not state["marked"]:
                    mark_as_read_safe()

            resp = StreamingHttpResponse(
                streaming_wrapper(),
                content_type=(headers or {}).get("Content-Type", "audio/wav")
            )

            # Safe passthrough headers
            if headers:
                for hk in ("Content-Disposition",):
                    if hk in headers:
                        resp[hk] = headers[hk]

            # Optimize for real-time streaming
            resp["X-Accel-Buffering"] = "no"
            resp["Cache-Control"] = "no-cache"

            # Expose mark policy to client
            resp["X-Auto-Mark-Read"] = "enabled" if auto_mark else "disabled"
            resp["X-Mark-After-Bytes"] = str(threshold)
            return resp
        except Exception as e:
            return Response({"message": "Something went wrong."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


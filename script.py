from voice_core.services.wazo_helpers.wazo_sip_template import get_master_global_template
from config.settings.base import GLOBAL_SIP_TEMPLATE_LABEL

from voice_core.services.wazo_helpers.wazo_voicemail import (
	fetch_all_voicemail,
	fetch_voicemails_by_folder,
    fetch_voicemail_recording,
)


admin_token = "a3c28bb8-680b-4fbd-8ab7-3f80b644654f"
voicemail_id = "41"
message_id = "1756471618-0000001b"

audio_bytes, content = fetch_voicemail_recording(admin_token, voicemail_id, message_id)

with open("voicemail.wav", "wb") as f:
    f.write(audio_bytes)

# print(audio_bytes)
# print("done")

# print(GLOBAL_SIP_TEMPLATE_LABEL)

# master_global_template = get_master_global_template(admin_token)
# print(master_global_template)
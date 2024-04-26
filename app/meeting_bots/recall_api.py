import requests
from ..utils import wrap_http_err


class RecallApiBase:
    url = "https://us-west-2.recall.ai{path}"

    def __init__(self, recall_api_token):
        self.headers = {
            "accept": "application/json",
            "content-type": "application/json",
            "Authorization": f"Token {recall_api_token}",
        }

    def _url(self, path):
        return self.url.format(path=path)

    def recall_post(self, path, json_body):
        url = self._url(path)
        return wrap_http_err(requests.post(url, headers=self.headers, json=json_body))

    def recall_get(self, path):
        url = self._url(path)
        return wrap_http_err(requests.get(url, headers=self.headers))


class RecallApi(RecallApiBase):
    def start_recording(
        self,
        bot_name,
        meeting_url,
        destination_transcript_url,
        destination_audio_url,
        destination_speaker_url,
    ):
        body = {
            "bot_name": bot_name,
            "meeting_url": meeting_url,
            "transcription_options": {
                "provider": "meeting_captions",
            },
            # "real_time_transcription": {
            #    "destination_url": destination_transcript_url,
            #    "partial_results": True,
            # },
            # "zoom": {
            #    "request_recording_permission_on_host_join": True,
            #    "require_recording_permission": True,
            # },
            # "recording_mode": "audio_only",
            # "real_time_media": {
            #    "websocket_audio_destination_url": destination_audio_url,
            #    "websocket_speaker_timeline_destination_url": destination_speaker_url,
            # },
        }

        if destination_transcript_url:
            body["real_time_transcription"] = {
                "destination_url": destination_transcript_url,
                "partial_results": True,
            }

        if destination_speaker_url or destination_audio_url:
            body["real_time_media"] = {}

        if destination_audio_url:
            body["real_time_media"]["websocket_audio_destination_url"] = (
                destination_audio_url
            )

        if destination_speaker_url:
            body["real_time_media"]["websocket_speaker_timeline_destination_url"] = (
                destination_speaker_url
            )

        return self.recall_post("/api/v1/bot", body)

    def stop_recording(self, bot_id):
        return self.recall_post(f"/api/v1/bot/{bot_id}/leave_call", json_body={})

    def recording_state(self, bot_id):
        return self.recall_get(f"/api/v1/bot/{bot_id}")

    def transcript(self, bot_id, diarization: bool):
        diarization_str = "?enhanced_diarization=true" if diarization else ""
        return self.recall_get(f"/api/v1/bot/{bot_id}/transcript{diarization_str}")

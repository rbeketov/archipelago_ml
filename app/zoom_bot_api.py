import requests
import http.client
import logging

'''# Enable HTTP debugging
http.client.HTTPConnection.debuglevel = 1

# Configure logging
logging.basicConfig()
logging.getLogger().setLevel(logging.DEBUG)
requests_log = logging.getLogger("urllib3")
requests_log.setLevel(logging.DEBUG)
requests_log.propagate = True'''

class RecallApiBase:
    url = 'https://us-west-2.recall.ai{path}'

    def __init__(self, recall_api_token):
        self.headers = {
            "accept": "application/json",
            "content-type": "application/json",
            "Authorization": f"Token {recall_api_token}"
        }
    
    def _url(self, path):
        return self.url.format(path = path)

    def recall_post(self, path, json_body):
        url = self._url(path)
        return requests.post(url, headers=self.headers, json=json_body)

    def recall_get(self, path):
        url = self._url(path)
        return requests.get(url, headers=self.headers)


class RecallApi(RecallApiBase): 
    def start_recording(self, bot_name, meeting_url, destination_url):
        body = {
            "bot_name": bot_name,
            "meeting_url": meeting_url,
            "transcription_options": {
                "provider": 'meeting_captions',
            },
            "real_time_transcription": {
                "destination_url": destination_url,
                "partial_results": True,
            },
            "zoom": {
                "request_recording_permission_on_host_join": True,
                "require_recording_permission": True,
            },
        }

        return self.recall_post('/api/v1/bot', body)

    def stop_recording(self, bot_id):
        return self.recall_post(f"/api/v1/bot/{bot_id}/leave_call")

    def recording_state(self, bot_id):
        return self.recall_get(f'/api/v1/bot/{bot_id}')



'''class ZoomBot:
    def __init__(self):
        self.recall_api = RecallApi(CONFIG["RECALL_API_TOKEN"])
        self.transcriptions = []

    def start_recording(self, bot_name, meeting_url):
        body = {
            bot_name: bot_name,
            meeting_url: meeting_url,
            "transcription_options": {
                "provider": 'default',
            },
            "real_time_transcription": {
                "destination_url": CONFIG["DESTINATION_URL"],
                "partial_results": True,
            },
            "zoom": {
                "request_recording_permission_on_host_join": True,
                "require_recording_permission": True,
            },
        }

        return self.recall_api.recall_post('/api/v1/bot', body)

    def stop_recording(self, bot_id):
        return self.recall_api.recall_post(f"/api/v1/bot/{bot_id}/leave_call")

    def recording_state(bot_id):
        return recall_get(f'/api/v1/bot/{bot_id}')
    
    def set_transcript()
'''

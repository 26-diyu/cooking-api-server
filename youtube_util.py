from youtube_transcript_api import YouTubeTranscriptApi

from data_model import Transcript, TimestampText


class YouTubeUtil:
    def __init__(self):
        self.youtube_transcript_api = YouTubeTranscriptApi()

    def fetch_transcript(self, video_url) -> Transcript:
        video_id = video_url.split("v=")[-1]
        transcript_response = self.youtube_transcript_api.fetch(video_id=video_id, languages=["en-US", "en", "en-GB", "en-IN"])
        transcript = Transcript(video_id=video_id, language="en", timestamp_texts=[])
        for entry in transcript_response.snippets:
            start_time = entry.start
            text = entry.text
            transcript.timestamp_texts.append(TimestampText(timestamp=start_time, text=text))
        return transcript
import os

from youtube_transcript_api import YouTubeTranscriptApi

from data_model import Transcript, TimestampText, RecipeContent
import cv2
import yt_dlp

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

    def download_key_frames(self, recipe_content: RecipeContent, video_url):
        video_id = video_url.split("v=")[-1]
        output_dir = f'data/{video_id}/key-frames'
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        ydl_opts = {
            'format': 'bestvideo[ext=mp4]/best[ext=mp4]/best',
            'quiet': True,
            'no_warnings': True
        }

        print("Fetching video stream URL...")
        print("video_url:", video_url)
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            stream_url = info['url']
            video_title = info.get('description', 'video')
            print("video_description:", video_title)

        # Open the video stream with OpenCV
        cap = cv2.VideoCapture(stream_url, cv2.CAP_FFMPEG)

        if not cap.isOpened():
            print("Error: Could not open video stream.")
            return

        # Get video properties
        fps = cap.get(cv2.CAP_PROP_FPS)
        print(f"Connected to stream. Video FPS: {fps}")

        for key_step in recipe_content.steps:
            timestamp = key_step.timestamp
            filename = f"{output_dir}/frame_at_{timestamp}s.jpg"
            if os.path.exists(filename):
                print("File already exists. Skipping download.")
                continue
            # Calculate the frame number based on timestamp and FPS
            frame_number = int(timestamp * fps)

            # Set the video capture position to the specific frame
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)

            # Read the frame
            success, frame = cap.read()

            if success:
                cv2.imwrite(filename, frame)
                print(f"Successfully saved: {filename}")
            else:
                print(f"Failed to extract frame at {timestamp} seconds (Frame index: {frame_number}).")

        # Clean up
        cap.release()
        print("Finished extracting frames.")
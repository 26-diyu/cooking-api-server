import os
from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
import cv2
import yt_dlp

def extract_frames_by_timestamps(video_url, timestamps_sec, key_frame_output_dir):
    """
    Extracts frames from a YouTube video at specific timestamps without downloading the full video.

    :param video_url: URL of the YouTube video
    :param timestamps_sec: List of floats/ints representing timestamps in seconds
    """
    # Configure yt-dlp to get the best video stream URL (preferring MP4 for OpenCV compatibility)
    ydl_opts = {
        'format': 'bestvideo[ext=mp4]/best[ext=mp4]/best',
        'quiet': True,
        'no_warnings': True
    }

    print("Fetching video stream URL...")
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(video_url, download=False)
        stream_url = info['url']
        video_title = info.get('title', 'video')

    # Open the video stream with OpenCV
    cap = cv2.VideoCapture(stream_url, cv2.CAP_FFMPEG)

    if not cap.isOpened():
        print("Error: Could not open video stream.")
        return

    # Get video properties
    fps = cap.get(cv2.CAP_PROP_FPS)
    print(f"Connected to stream. Video FPS: {fps}")

    for ts in timestamps_sec:
        # Calculate the frame number based on timestamp and FPS
        frame_number = int(ts * fps)

        # Set the video capture position to the specific frame
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)

        # Read the frame
        success, frame = cap.read()

        if success:
            filename = f"{key_frame_output_dir}/frame_at_{ts}s.jpg"
            cv2.imwrite(filename, frame)
            print(f"Successfully saved: {filename}")
        else:
            print(f"Failed to extract frame at {ts} seconds (Frame index: {frame_number}).")

    # Clean up
    cap.release()
    print("Finished extracting frames.")


def generate_recipe(video_id):
    global output_dir, youtube_transcript_api, transcript, start_time, text, llm, system_prompt, prompt, chain, response, seconds
    video_url = f"https://www.youtube.com/watch?v={video_id}"
    output_dir = f'data/{video_id}'
    # For fine-grained timestamps, youtube-transcript-api is often used directly:
    from youtube_transcript_api import YouTubeTranscriptApi
    youtube_transcript_api = YouTubeTranscriptApi()
    transcript = youtube_transcript_api.fetch(video_id=video_id, languages=["en-US", "en", "en-GB", "en-IN"])
    # Format the transcript for the LLM
    ts_description = {}
    transcript_text = ""
    for entry in transcript.snippets:
        start_time = entry.start
        text = entry.text
        transcript_text += f"[{start_time:.2f}s]: {text}\n"
        ts_description[start_time] = text
    print(transcript_text)
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    fpw = open(f"{output_dir}/transcript.txt", "w")
    fpw.write(transcript_text)
    fpw.close()
    # Initialize Ollama with your local model
    llm = ChatOllama(model="llama3.2", temperature=0)
    # Create a prompt that forces a structured JSON array response
    system_prompt = """
You are an expert culinary assistant. Your goal is to parse a raw video transcript and extract the definitive, step-by-step cooking instructions for a recipe.

Follow these strict guidelines:
1. FOCUS ON ACTIONS: Extract steps that involve physical cooking actions (e.g., heating a pan, adding ingredients, adjusting flame, blending, plating).
2. FILTER OUT NOISE: Ignore conversational filler, background talk, anecdotes, or repetitive instructions. 
3. PRESERVE TIMESTAMPS: Keep the exact timestamp provided in the transcript for each step so users can reference the video.

### INSTRUCTIONS FOR YOUR OUTPUT:
You must respond ONLY with a valid JSON object. Do not include any conversational filler, markdown formatting (like ```json), or text outside the JSON object. 

The JSON structure must match this exactly:
{{
  "description": "One sentence description about the steps",
  "steps": "The list of steps with each step should follow this format: (Timestamp, Step-description)"
}}
"""
    # 2. Define the prompt structure
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("user", "Here is the raw transcript to analyze:\n\n{transcript}")
    ])
    # Chain them together
    chain = prompt | llm | JsonOutputParser()
    # Run the chain
    response = chain.invoke({"transcript": transcript_text})  # Truncated if text is massive
    print(response)
    print("KEY STEPS")
    fpw = open(f"{output_dir}/key-steps.txt", "w")
    fpw.write(f"{response['description']}\n")
    timestamps = []
    for idx, (seconds, step_description) in enumerate(response["steps"]):
        try:
            seconds = float(seconds.rstrip('s'))
            timestamps.append(seconds)
            print(f"seconds: {seconds}, step_description: {step_description}")
            fpw.write(f"seconds: {seconds}, step_description: {step_description}\n")
        except ValueError:
            print(f"Skipping invalid timestamp: {seconds}")

    fpw.close()
    print(timestamps)
    key_frame_output_dir = f"{output_dir}/key_frames"
    if not os.path.exists(key_frame_output_dir):
        os.makedirs(key_frame_output_dir)
    extract_frames_by_timestamps(video_url, timestamps, key_frame_output_dir)

if __name__ == "__main__":
    video_id = "exnez7phjD8"
    generate_recipe(video_id)
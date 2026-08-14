import asyncio
import json
import os
import uuid
import random
import time
from typing import Annotated
from pydantic import BaseModel

from fastapi import FastAPI, Response, HTTPException, status, Cookie
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
from fastapi.responses import FileResponse
from sse_starlette.sse import EventSourceResponse
import yt_dlp
import cv2

from data_model import Messages, RecipeConversationList, TextMessage, TextContent
from generic_response_generator import GenericResponseGenerator
from ingredient_extractor import IngredientExtractor
from intent_classifier import HybridIntentClassifier, IntentEnum
from relational_database import RelationalDatabase, RecipeConversation
from user_session import UserSession
from recipe_generator import RecipeGenerator

app = FastAPI(title="Guest Session API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "https://localhost:5173"], # Your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
relational_database = RelationalDatabase.get_instance()
hybrid_intent_classifier = HybridIntentClassifier()

class Cookies(BaseModel):
    username: str | None = None
    session_id: str | None = None

class GuestSessionResponse(BaseModel):
    status: str
    message: str

@app.post("/api/guest-session", response_model=GuestSessionResponse)
def create_guest_session(response: Response, cookies: Annotated[Cookies, Cookie()]) -> GuestSessionResponse:
    user_session = UserSession()
    print("cookies:", cookies)
    if (cookies is not None
            and cookies.session_id is not None
            and cookies.session_id != ""
            and cookies.username is not None
            and cookies.username != "" and user_session.is_valid(cookies.username, cookies.session_id)):
        return GuestSessionResponse(
            status = "success",
            message="Guest session already exists")
    session_id = str(uuid.uuid4())
    #username = f"guest{session_id[:8]}"
    username = "guest123455"
    response.set_cookie(
        key="session_id",
        value=session_id,
        httponly=True,  # Prevents JavaScript client-side access (XSS defense)
        samesite="none",  # CSRF defense
        max_age=86400,  # Cookie expiration in seconds
        secure=True
    )

    response.set_cookie(
        key="username",
        value=username,
        httponly=True,
        samesite="none",
        max_age=86400,
        secure=True
    )

    if user_session.store(username, session_id, expiry=86400):
        return GuestSessionResponse(
            status = "success",
            message="Guest session created successfully"
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error while creating guest session"
        )

@app.get("/api/guest-session", response_model=GuestSessionResponse)
def get_guest_session(cookies: Annotated[Cookies, Cookie()]) -> GuestSessionResponse:
    print("cookies:", cookies)
    if (cookies is not None
            and cookies.session_id is not None
            and cookies.session_id != ""
            and cookies.username is not None
            and cookies.username != ""):
        return GuestSessionResponse(
            status = "success",
            message="Guest session already exists")
    return GuestSessionResponse(
        status="success",
        message="Guest session does not exist")

@app.get("/api/recipe-conversation-list", response_model=RecipeConversationList)
def get_recipe_conversation_list(cookies: Annotated[Cookies, Cookie()]) -> RecipeConversationList:
    user_session = UserSession()
    print("cookies:", cookies)
    print("cookies:", cookies)
    print("cookies.session_id:", cookies.session_id)
    print("cookies.username:", cookies.username)
    if cookies is None or not user_session.is_valid(cookies.username, cookies.session_id):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session cookies missing or expired"
        )
    recipe_conversation_list = relational_database.get_recipe_conversation_list(cookies.username)
    recipe_conversation_list_response = RecipeConversationList(username=cookies.username, recipe_conversations=recipe_conversation_list)
    return recipe_conversation_list_response

@app.get("/api/recipe-conversation/{recipe_conversation_id}", response_model=RecipeConversation)
def get_recipe_conversation(recipe_conversation_id: int, cookies: Annotated[Cookies, Cookie()]) -> RecipeConversation:
    user_session = UserSession()
    print("cookies:", cookies)
    print("cookies.session_id:", cookies.session_id)
    print("cookies.username:", cookies.username)
    if cookies is None or not user_session.is_valid(cookies.username, cookies.session_id):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session cookies missing or expired"
        )
    if recipe_conversation_id == 0:
        response_payload = []
        initial_message = TextMessage(frm="ai",
                                      content=TextContent(text="Hi! Send me a YouTube cooking video link or click a recipe to get started."))
        response_payload.append(initial_message)
        recipe_conversation_id = relational_database.insert_recipe_conversation(cookies.username, response_payload)
        recipe_conversation = RecipeConversation(username=cookies.username,
                                                 id=recipe_conversation_id,
                                                 messages=response_payload)
    else:
        response_payload = relational_database.get_recipe_conversation_messages(username=cookies.username,
                                                                                recipe_conversation_id=recipe_conversation_id)
        recipe_conversation = RecipeConversation(username=cookies.username,
                                                 id=recipe_conversation_id,
                                                 messages=response_payload)
    return recipe_conversation

@app.post("/api/recipe-conversation/{recipe_conversation_id}", response_model=RecipeConversation)
def update_recipe_conversation(recipe_conversation_id: int, request_payload: Messages, cookies: Annotated[Cookies, Cookie()]) -> RecipeConversation:
    user_session = UserSession()
    print("cookies:", cookies)
    print("cookies.session_id:", cookies.session_id)
    print("cookies.username:", cookies.username)
    if cookies is None or not user_session.is_valid(cookies.username, cookies.session_id):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session cookies missing or expired"
        )
    messages = request_payload.messages
    print("messages:", messages)
    print("adding messages to the recipe conversation ...")
    recipe_conversation_id = relational_database.add_recipe_conversation(cookies.username, recipe_conversation_id, messages)
    print("added messages to the recipe conversation id:", recipe_conversation_id)
    recipe_conversation_messages = relational_database.get_recipe_conversation_messages(username=cookies.username, recipe_conversation_id=recipe_conversation_id)
    print("recipe_conversation_messages:", recipe_conversation_messages)
    last_text_messages = ""
    count = 0
    start = len(recipe_conversation_messages) - 1
    for i in range(start, -1, -1):
        message = recipe_conversation_messages[i]
        if message["mtype"] != "text":
            break
        last_text_messages = message["content"]["text"] + " " + last_text_messages
        count += 1
        if count >= 2:
            break

    print("last_text_messages:", last_text_messages)
    result = hybrid_intent_classifier.classify(last_text_messages)
    print("intent classification result:", result)
    if result.intent == IntentEnum.GENERATE_RECIPE:
        recipe_generator = RecipeGenerator()
        recipe_conversation = recipe_generator.generate_recipe(cookies.username, recipe_conversation_id, messages)
    elif result.intent == IntentEnum.EXTRACT_INGREDIENTS:
        ingredient_extractor = IngredientExtractor()
        recipe_conversation = ingredient_extractor.extract_ingredients(cookies.username, recipe_conversation_id, recipe_conversation_messages)
    else:
        generic_response_generator = GenericResponseGenerator()
        recipe_conversation = generic_response_generator.generate_response(cookies.username, recipe_conversation_id, messages)
    return recipe_conversation

IMAGE_DIRECTORY = Path("./data").resolve()

@app.get("/api/recipe-image/data/{filepath:path}", response_class=FileResponse)
async def get_jpg_image(filepath: str):
    """
    Delivers a JPG image from nested subdirectories safely.
    Example path: /images/subfolder/nature/photo.jpg
    """
    # Combine the base folder with the requested relative path and resolve it
    file_path = (IMAGE_DIRECTORY / filepath).resolve()

    # 1. Directory Traversal Protection
    # Verifies the resolved path is strictly inside IMAGE_DIRECTORY
    if not file_path.is_relative_to(IMAGE_DIRECTORY):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied.",
        )

    # 2. Extension Check
    if file_path.suffix.lower() not in [".jpg", ".jpeg"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid image format. Only JPG/JPEG images are supported.",
        )

    # 3. File Existence Check
    if not file_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Image not found.",
        )

    return FileResponse(
        path=file_path,
        media_type="image/jpeg",
        filename=file_path.name,
    )

# Maximum allowed concurrent image generations per request (or app-wide)
MAX_CONCURRENCY = 4
MAX_RETRIES = 20
# Global limit across the entire FastAPI app
GLOBAL_SEMAPHORE = asyncio.Semaphore(MAX_CONCURRENCY)


def _extract_frame_sync(timestamp: float, image_path: str) -> bool:
    """
    Synchronous blocking function containing yt_dlp and OpenCV code.
    Runs inside a thread pool to avoid blocking the asyncio event loop.
    """
    # Force FFmpeg options before opening stream
    os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = (
        "timeout;5000000|"  # 5 second timeout (in microseconds)
        "rtsp_transport;tcp|"  # Use TCP instead of UDP to prevent packet loss
        "max_delay;5000000"
    )
    # Enable FFmpeg verbose debugging output in console
    os.environ["OPENCV_LOG_LEVEL"] = "VERBOSE"
    os.environ["OPENCV_FFMPEG_LOGLEVEL"] = "32"  # 8 = AV_LOG_FATAL / AV_LOG_ERROR

    video_id = image_path.split("/")[1]
    output_dir = f'data/{video_id}/key-frames'
    filename = f"{output_dir}/frame_at_{timestamp}s.jpg"
    if os.path.exists(filename):
        print("File already exists. Skipping extraction:", filename)
        return True

    print("File does not exist. Downloading...", filename)
    ydl_opts = {
        'format': 'bestvideo[ext=mp4]/best[ext=mp4]/best',
        'quiet': True,
        'no_warnings': True
    }
    video_url = f"https://www.youtube.com/watch?v={video_id}"
    print("Completed fetching video stream URL")
    cap = None
    for retry in range(1, MAX_RETRIES+1):
        print("retry:", retry)
        print("Fetching video stream URL for video_url:", video_url)

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            stream_url = info['url']
            # print("stream_url:", stream_url)
        cap = cv2.VideoCapture(stream_url, cv2.CAP_FFMPEG)
        if cap.isOpened():
            break
        # Always release failed objects before retrying to free memory/sockets
        if cap is not None:
            cap.release()
        # Synchronous sleep inside thread
        time.sleep(random.uniform(0.3, 1.0))

    if not cap or not cap.isOpened():
        print("Error: Could not open video stream.")
        return False

    fps = cap.get(cv2.CAP_PROP_FPS)
    print(f"Connected to stream. Video FPS: {fps}")
    frame_number = int(timestamp * fps)

    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
    success, frame = cap.read()

    if success:
        cv2.imwrite(filename, frame)
        print(f"Successfully saved: {filename}")
    else:
        print(f"Failed to extract frame at {timestamp} seconds (Frame index: {frame_number}).")

    cap.release()
    print("Finished downloading an image.")
    return success

async def generate_single_image(
        timestamp: float,
        image_path: str,
        queue: asyncio.Queue,
        semaphore: asyncio.Semaphore
):
    """
    Worker task wrapped with a Semaphore to control concurrency.
    """
    async with semaphore:
        print("Started task generate_single_image for timestamp ", timestamp)
        # 1. Start extraction update
        await queue.put({
            "event": "image_update",
            "data": json.dumps({
                "timestamp": timestamp,
                "image_path": image_path,
                "image_status": "extracting"
            })
        })
        await asyncio.sleep(random.uniform(0.3, 1.0))
        # 2. Run the blocking yt-dlp & cv2 extraction in a background thread
        # This keeps the asyncio event loop unblocked!
        success = await asyncio.to_thread(_extract_frame_sync, timestamp, image_path)
        if success:
            status = relational_database.update_image_status(image_path, "extracted")
            if status:
                print("Successfully updated image status.")
            else:
                print("Failed to update image status.")
        payload = {
            "timestamp": timestamp,
            "image_path": image_path,
            "image_status": "extracted" if success else "extracting"
        }
        await queue.put({
            "event": "image_update",
            "data": json.dumps(payload)
        })

@app.get("/api/generate-batch/stream-concurrent")
async def stream_batch(recipe_conversation_id: int, message_id: str, cookies: Annotated[Cookies, Cookie()]):
    print("cookies:", cookies)
    print("cookies.session_id:", cookies.session_id)
    print("cookies.username:", cookies.username)
    #TO-DO validate the session
    async def event_generator():
        queue: asyncio.Queue = asyncio.Queue()

        # Limit active parallel runs to 10
        # semaphore = asyncio.Semaphore(MAX_CONCURRENCY)

        timestamp_image_paths = relational_database.get_timestamp_image_paths(cookies.username, recipe_conversation_id, message_id)
        if timestamp_image_paths and len(timestamp_image_paths) > 0:
            (_timestamp, image_path) = timestamp_image_paths[0]
            video_id = image_path.split("/")[1]
            output_dir = f'data/{video_id}/key-frames'
            if not os.path.exists(output_dir):
                os.makedirs(output_dir, exist_ok=True)
        # 1. Spawn all background tasks with the shared semaphore
        tasks = [
            asyncio.create_task(generate_single_image(timestamp, image_path, queue, GLOBAL_SEMAPHORE))
            for (timestamp, image_path) in timestamp_image_paths
        ]

        # 2. Drain queue while tasks execute
        pending_tasks = set(tasks)

        while pending_tasks:
            while not queue.empty():
                event = await queue.get()
                yield event
                queue.task_done()

            # Clean finished tasks
            done_tasks = {t for t in pending_tasks if t.done()}
            pending_tasks -= done_tasks

            if pending_tasks and queue.empty():
                await asyncio.sleep(0.05)

        # 3. Final queue flush
        while not queue.empty():
            event = await queue.get()
            yield event
            queue.task_done()
        print("Completed a batch for extracting images.")
        # Batch completion event
        yield {
            "event": "batch_complete",
            "data": json.dumps({"status": "done"})
        }

    return EventSourceResponse(event_generator())

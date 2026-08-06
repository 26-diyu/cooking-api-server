import uuid
from typing import Annotated
from pydantic import BaseModel

from fastapi import FastAPI, Response, HTTPException, status, Cookie
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
from fastapi.responses import FileResponse
from pyexpat.errors import messages

from data_model import Messages, RecipeConversationList, TextMessage, TextContent
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
    username = "guest12345"
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
        response_payload = Messages(messages=[])
        initial_message = TextMessage(frm="ai",
                                      content=TextContent(text="Hi! Send me a YouTube cooking video link or click a recipe to get started."))
        response_payload.messages.append(initial_message)
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

@app.post("/api/recipe-conversation/{recipe_conversation_id}", response_model=Messages)
def update_recipe_conversation(recipe_conversation_id: int, messages: Messages, cookies: Annotated[Cookies, Cookie()]) -> Messages:
    user_session = UserSession()
    print("cookies:", cookies)
    print("cookies.session_id:", cookies.session_id)
    print("cookies.username:", cookies.username)
    if cookies is None or not user_session.is_valid(cookies.username, cookies.session_id):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session cookies missing or expired"
        )
    print("messages:", messages)
    recipe_generator = RecipeGenerator()
    response_messages = recipe_generator.generate_recipe(cookies.username, recipe_conversation_id, messages)
    return response_messages

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
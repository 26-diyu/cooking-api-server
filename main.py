import uuid
from typing import Annotated
from pydantic import BaseModel

from fastapi import FastAPI, Response, HTTPException, status, Cookie
from fastapi.middleware.cors import CORSMiddleware
from data_model import Messages
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
    username = f"guest{session_id[:8]}"
    response.set_cookie(
        key="session_id",
        value=session_id,
        httponly=True,  # Prevents JavaScript client-side access (XSS defense)
        samesite="lax",  # CSRF defense
        max_age=86400,  # Cookie expiration in seconds
        secure=True
    )

    response.set_cookie(
        key="username",
        value=username,
        httponly=True,
        samesite="lax",
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


@app.post("/api/recipe/create", response_model=Messages)
def create_recipe(messages: Messages, cookies: Annotated[Cookies, Cookie()]) -> Messages:
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
    response_messages = recipe_generator.generate_recipe(cookies.username, messages)
    return response_messages
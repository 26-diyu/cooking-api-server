import threading
import time
from typing import Optional
from sqlmodel import Field, SQLModel, Session, create_engine, select, Column, JSON
from urllib.parse import quote_plus

from data_model import Messages, Transcript

class UserSession(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str
    session_id: str
    created_at: float = Field(default_factory=lambda: time.time())
    expiry: int = Field(default=86400)

class TranscriptSQLModel(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    transcript: Optional[Transcript] = Field(default=None, sa_column=Column(JSON))

class MessagesSQLModel(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    username: Optional[str] = Field(default="")
    messages: Optional[Messages] = Field(default=None, sa_column=Column(JSON))

class RelationalDatabase:
    _instance = None
    _lock = threading.Lock()

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = RelationalDatabase()
        return cls._instance

    def __init__(self):
        password = "recipe@123"
        encoded_password = quote_plus(password)
        DATABASE_URL = f"postgresql+psycopg://postgres:{encoded_password}@localhost:5432/test"
        self.engine = create_engine(DATABASE_URL, echo=True)
        SQLModel.metadata.create_all(self.engine)

    def create_user_session(self, username, session_id, expiry=86400):
        user_session = UserSession(username=username, session_id=session_id, expires=expiry)
        try:
            with Session(self.engine) as session:
                session.add(user_session)
                session.commit()
                # Refresh to populate auto-generated fields like `id` from Postgres
                session.refresh(user_session)
                print(f"Created Session ID: {user_session.id}")
                return user_session.id
        except Exception as e:
            print("Failed to create user session:", e)
            return -1

    def get_user_session(self, username, session_id):
        with Session(self.engine) as session:
            statement = select(UserSession).where(UserSession.username == username, UserSession.session_id == session_id)
            results = session.exec(statement).all()
            print("\n--- User Sessions ---")
            for us in results:
                print(f"{us.id}: {us.username} - {us.session_id}")
                return us.created_at, us.expiry
        return -1, -1

    def insert_transcript(self, transcript):
        transcript_sqlmodel = TranscriptSQLModel(transcript=transcript.model_dump())
        try:
            with Session(self.engine) as session:
                session.add(transcript_sqlmodel)
                session.commit()
                # Refresh to populate auto-generated fields like `id` from Postgres
                session.refresh(transcript_sqlmodel)
                print(f"Created Transcript ID: {transcript_sqlmodel.id}")
                return transcript_sqlmodel.id
        except Exception as e:
            print("Failed to insert transcript:", e)
            return -1

    def get_transcript(self, video_id):
        with Session(self.engine) as session:
            statement = select(TranscriptSQLModel).where(TranscriptSQLModel.transcript["video_id"].as_string() == video_id)
            results = session.exec(statement).all()
            for transcript in results:
                print(f"{transcript.id}: {transcript.transcript}")
                return transcript.transcript
        return None

    def insert_recipe_conversation(self, username, messages):
        messages_sqlmodel = MessagesSQLModel(username=username, messages=messages.model_dump())
        try:
            with Session(self.engine) as session:
                session.add(messages_sqlmodel)
                session.commit()
                # Refresh to populate auto-generated fields like `id` from Postgres
                session.refresh(messages_sqlmodel)
                print(f"Created Transcript ID: {messages_sqlmodel.id}")
                return messages_sqlmodel.id
        except Exception as e:
            print("Failed to insert recipe conversation:", e)
            return -1
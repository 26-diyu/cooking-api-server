import threading
import time
from typing import Optional
from sqlmodel import Field, SQLModel, Session, create_engine, select, Column, JSON
from urllib.parse import quote_plus

from data_model import Messages, Transcript, TextMessage, TextContent, MessageItem, RecipeContent, RecipeStepImage


class UserSession(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str
    session_id: str
    created_at: float = Field(default_factory=lambda: time.time())
    expiry: int = Field(default=86400)

class VideoTranscript(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    transcript: Optional[Transcript] = Field(default=None, sa_column=Column(JSON))

class RecipeConversation(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    title: Optional[str] = Field(default="Recipe Conversation")
    username: Optional[str] = Field(default="")
    messages: Optional[list[MessageItem]] = Field(default=None, sa_type=JSON)

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
        transcript_sqlmodel = VideoTranscript(transcript=transcript.model_dump())
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
            statement = select(VideoTranscript).where(VideoTranscript.transcript["video_id"].as_string() == video_id)
            results = session.exec(statement).all()
            for transcript in results:
                print(f"{transcript.id}: {transcript.transcript}")
                return transcript.transcript
        return None

    def insert_recipe_conversation(self, username, messages):
        messages_dict_list = [msg.model_dump() for msg in messages]
        recipe_conversation = RecipeConversation(username=username, messages=messages_dict_list)
        try:
            with Session(self.engine) as session:
                session.add(recipe_conversation)
                session.commit()
                # Refresh to populate auto-generated fields like `id` from Postgres
                session.refresh(recipe_conversation)
                print(f"Created Recipe Conversation ID: {recipe_conversation.id}")
                return recipe_conversation.id
        except Exception as e:
            print("Failed to insert recipe conversation:", e)
            return -1

    def get_image_path_status(self, image_paths:list) -> dict:
        image_path_status = {}
        with Session(self.engine) as session:
            statement = select(RecipeStepImage).where(RecipeStepImage.image_path.in_(image_paths))
            results = session.exec(statement).all()
            for recipe_step_image in results:
                print(f"{recipe_step_image.image_path}: {recipe_step_image.image_status}")
                image_path_status[recipe_step_image.image_path] = recipe_step_image.image_status
        return image_path_status

    def get_recipe_conversation_messages(self, username:str, recipe_conversation_id:int):
        with Session(self.engine) as session:
            statement = select(RecipeConversation).where(
                                    RecipeConversation.username == username,
                                                RecipeConversation.id == recipe_conversation_id)
            results = session.exec(statement).all()
            for conversation in results:
                print(f"{conversation.id}: {conversation.messages}")
                for message in conversation.messages:
                    if message["mtype"] == "recipe":
                        print("Before updating message[\"steps\"]:", message["content"]["steps"])
                        image_paths = []
                        for step in message["content"]["steps"]:
                            image_paths.append(step["image_path"])
                        image_path_status = self.get_image_path_status(image_paths)
                        for step in message["content"]["steps"]:
                            if image_path_status.get(step["image_path"]):
                                step["image_status"] = image_path_status.get(step["image_path"])
                        print("After updating message[\"steps\"]:", message["content"]["steps"])
                return conversation.messages
        return []

    def get_recipe_conversation_title(self, username:str, recipe_conversation_id:int):
        with Session(self.engine) as session:
            statement = select(RecipeConversation).where(
                                    RecipeConversation.username == username,
                                                RecipeConversation.id == recipe_conversation_id)
            results = session.exec(statement).all()
            for conversation in results:
                print(f"{conversation.id}: {conversation.title}")
                return conversation.title
        return "Recipe Conversation"

    def add_recipe_conversation(self, username:str, recipe_conversation_id:int, new_messages:list):
        messages = self.get_recipe_conversation_messages(username, recipe_conversation_id)
        all_messages = messages
        for message in new_messages:
            all_messages.append(message.model_dump())
        with Session(self.engine) as session:
            statement = select(RecipeConversation).where(
                            RecipeConversation.username == username,
                            RecipeConversation.id == recipe_conversation_id
                            )
            recipe_conversation = session.exec(statement).first()
            if recipe_conversation:
                recipe_conversation.messages = all_messages
                session.add(recipe_conversation)
                session.commit()
                session.refresh(recipe_conversation)
                print(f"\nUpdated {recipe_conversation.id}'s messages to {recipe_conversation.messages}")
                return recipe_conversation_id
        return None

    def update_recipe_conversation_title(self, username:str, recipe_conversation_id:int, title:str):
        with Session(self.engine) as session:
            statement = select(RecipeConversation).where(
                RecipeConversation.username == username,
                RecipeConversation.id == recipe_conversation_id
            )
            recipe_conversation = session.exec(statement).first()
            if recipe_conversation:
                recipe_conversation.title = title
                session.add(recipe_conversation)
                session.commit()
                session.refresh(recipe_conversation)
                print(f"\nUpdated {recipe_conversation.id}'s title to {recipe_conversation.title}")
                return recipe_conversation_id
        return None

    def get_recipe_conversation_list(self, username):
        conversation_list = []
        with Session(self.engine) as session:
            statement = select(RecipeConversation).where(RecipeConversation.username == username)
            results = session.exec(statement).all()
            for recipe_conversation in results:
                print(f"{recipe_conversation.id}: {recipe_conversation.title} ")
                conversation_list.append({"id": recipe_conversation.id, "title": recipe_conversation.title})
        return conversation_list

    def get_timestamp_image_paths(self, username, recipe_conversation_id, message_id, image_status="extracting"):
        timestamp_image_paths = []
        with (Session(self.engine) as session):
            statement = select(RecipeConversation).where(
                RecipeConversation.username == username,
                RecipeConversation.id == recipe_conversation_id
            )
            recipe_conversation = session.exec(statement).first()
            if recipe_conversation and recipe_conversation.messages:
                for message in recipe_conversation.messages:
                    if message["mid"] == message_id:
                        image_paths = []
                        for step in message["content"]["steps"]:
                            image_paths.append(step["image_path"])
                        image_path_status = self.get_image_path_status(image_paths)
                        print("image_path_status:", image_path_status)
                        for step in message["content"]["steps"]:
                            print("step[image_path]:", step["image_path"])
                            if image_path_status.get(step["image_path"]) is None or image_path_status[step["image_path"]] == image_status:
                                timestamp_image_paths.append([step["timestamp"], step["image_path"]])
        return timestamp_image_paths

    def insert_recipe_step_image(self, recipe_content : RecipeContent) -> int:
        try:
            with Session(self.engine) as session:
                row_count = 0
                image_paths = []
                for step in recipe_content.steps:
                    image_paths.append(step.image_path)
                image_path_status = self.get_image_path_status(image_paths)
                for step in recipe_content.steps:
                    if image_path_status.get(step.image_path) is None:
                        recipe_step_image = RecipeStepImage(image_path=step.image_path, image_status=step.image_status)
                        session.add(recipe_step_image)
                        row_count += 1
                session.commit()
                print(f"Successfully inserted {row_count} recipe_step_image")
                return row_count
        except Exception as e:
            print("Failed to insert recipe_step_image:", e)
            return -1

    def update_image_status(self, image_path, image_status) -> bool:
        with Session(self.engine) as session:
            statement = select(RecipeStepImage).where(
                RecipeStepImage.image_path == image_path
            )
            recipe_step_image = session.exec(statement).first()
            if recipe_step_image:
                recipe_step_image.image_status = image_status
                session.add(recipe_step_image)
                session.commit()
                session.refresh(recipe_step_image)
                print(f"\nUpdated {recipe_step_image.image_path}'s status to {recipe_step_image.image_status}")
                return True
        return False

if __name__ == "__main__":
    relational_database = RelationalDatabase()
    new_messages_payload = Messages(messages=[])
    new_messages_payload.messages.append(TextMessage(frm="ai", mtype="text", content=TextContent(text="Hello World 2151")))
    relational_database.add_recipe_conversation(username="guest12345", recipe_conversation_id=3, new_messages=new_messages_payload)

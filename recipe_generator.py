from data_model import Messages, Message, RecipeMessage, TextMessage, TextContent
from relational_database import RelationalDatabase, RecipeConversation
from youtube_util import YouTubeUtil
from recipe_language_model import RecipeLLM

class RecipeGenerator:
    def __init__(self):
        self.relational_database = RelationalDatabase.get_instance()
        self.youtube_util = YouTubeUtil()
        self.recipe_llm = RecipeLLM()

    def extract_video_url(self, text):
        words = text.split()
        for word in words:
            if word.find("youtu.be") != -1 or word.find("youtube.com") != -1:
                return word
        return None

    def generate_recipe(self, username:str, recipe_conversation_id:int, request_payload:Messages) -> RecipeConversation:
        video_url = None
        response_payload = Messages(messages=[])
        if request_payload.messages[-1].mtype == 'text':
            video_url = self.extract_video_url(request_payload.messages[-1].content.text)
        if video_url is None:
            new_message = Message(mtype='text', content="No valid YouTube URL found")
            response_payload.messages.append(new_message)
            self.relational_database.insert_recipe(username, response_payload)
            recipe_conversation = RecipeConversation(id=recipe_conversation_id, messages=response_payload)
            return recipe_conversation
        video_id = video_url.split("v=")[-1]
        transcript = self.relational_database.get_transcript(video_id=video_id)
        if transcript is None:
            transcript = self.youtube_util.fetch_transcript(video_url)
            print("transcript:", transcript)
            transcript_id = self.relational_database.insert_transcript(transcript)
            print("transcript id:", transcript_id)
            transcript = self.relational_database.get_transcript(video_id=video_id)
        else:
            print("transcript:", transcript)
        recipe_content = self.recipe_llm.extract_key_steps(transcript)
        print("recipe_content:", recipe_content)
        recipe_message = RecipeMessage(frm="ai", content=recipe_content)
        print("recipe_message:", recipe_message)
        response_payload.messages.append(recipe_message)
        ingredient_prompt_message = TextMessage(frm="ai",
                                                content=TextContent(text="Would you like to list the ingredients for the recipe ?"))
        response_payload.messages.append(ingredient_prompt_message)
        print("response_payload:", response_payload)
        recipe_conversation_id = self.relational_database.add_recipe_conversation(username, recipe_conversation_id, response_payload)
        print("recipe_conversation_id:", recipe_conversation_id)
        self.youtube_util.download_key_frames(recipe_content, video_url)
        title = self.recipe_llm.generate_title(transcript)
        if title:
            self.relational_database.update_recipe_conversation_title(username, recipe_conversation_id, title)
            recipe_conversation = RecipeConversation(id=recipe_conversation_id, title=title,
                                                     messages=response_payload)
        else:
            recipe_conversation = RecipeConversation(id=recipe_conversation_id,
                                                     messages=response_payload)
        return recipe_conversation


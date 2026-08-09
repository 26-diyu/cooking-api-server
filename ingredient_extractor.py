import yt_dlp

from data_model import Messages, IngredientMessage, TextContent, IngredientContent
from recipe_language_model import RecipeLLM
from relational_database import RelationalDatabase, RecipeConversation


class IngredientExtractor:
    def __init__(self):
        self.relational_database = RelationalDatabase.get_instance()
        self.recipe_llm = RecipeLLM()

    def extract_ingredients(self, username: str, recipe_conversation_id: str, messages:list) -> RecipeConversation:
        video_url = None
        for i in range(len(messages)-1, -1, -1):
            message = messages[i]
            if message["mtype"] == "text":
                words = message["content"]["text"].split()
                for word in words:
                    if word.find("youtu.be") != -1 or word.find("youtube.com") != -1:
                        video_url = word
                        break

        ingredients = self.recipe_llm.extract_ingredients(video_url)
        response_payload = []
        ingredient_message = IngredientMessage(frm="ai", content=IngredientContent(ingredients=ingredients))
        response_payload.append(ingredient_message)
        recipe_conversation_id = self.relational_database.add_recipe_conversation(username,
                                                                                  recipe_conversation_id,
                                                                                  response_payload)
        recipe_conversation_title = self.relational_database.get_recipe_conversation_title(username, recipe_conversation_id)
        print("recipe_conversation_id:", recipe_conversation_id)
        recipe_conversation = RecipeConversation(id=recipe_conversation_id, title=recipe_conversation_title, messages=response_payload)
        return recipe_conversation

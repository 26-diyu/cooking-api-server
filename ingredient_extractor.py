from data_model import Messages, IngredientMessage, TextContent, IngredientContent
from relational_database import RelationalDatabase, RecipeConversation


class IngredientExtractor:
    def __init__(self):
        self.relational_database = RelationalDatabase.get_instance()

    def extract_ingredients(self, username: str, recipe_conversation_id: str, messages:Messages) -> RecipeConversation:
        response_payload = []
        ingredient_message = IngredientMessage(frm="ai", content=IngredientContent(ingredients=["2 Onions", "2 table spoon oil"]))
        response_payload.append(ingredient_message)
        recipe_conversation_id = self.relational_database.add_recipe_conversation(username,
                                                                                  recipe_conversation_id,
                                                                                  response_payload)
        recipe_conversation_title = self.relational_database.get_recipe_conversation_title(username, recipe_conversation_id)
        print("recipe_conversation_id:", recipe_conversation_id)
        recipe_conversation = RecipeConversation(id=recipe_conversation_id, title=recipe_conversation_title, messages=response_payload)
        return recipe_conversation

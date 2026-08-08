from data_model import Messages, IngredientMessage, TextContent, IngredientContent
from relational_database import RelationalDatabase


class IngredientExtractor:
    def __init__(self):
        self.relational_database = RelationalDatabase.get_instance()

    def extract_ingredients(self, username: str, recipe_conversation_id: str, messages:Messages) -> Messages:
        response_payload = Messages(messages=[])
        ingredient_message = IngredientMessage(frm="ai", content=IngredientContent(ingredients=["2 Onions", "2 table spoon oil"]))
        response_payload.messages.append(ingredient_message)
        recipe_conversation_id = self.relational_database.add_recipe_conversation(username,
                                                                                  recipe_conversation_id,
                                                                                  response_payload)
        print("recipe_conversation_id:", recipe_conversation_id)
        return response_payload

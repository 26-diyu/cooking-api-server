from data_model import Messages, TextContent, TextMessage
from relational_database import RelationalDatabase


class GenericResponseGenerator:
    def __init__(self):
        self.relational_database = RelationalDatabase.get_instance()

    def generate_response(self, username: str, recipe_conversation_id: str, messages:Messages) -> Messages:
        response_payload = Messages(messages=[])
        ingredient_message = TextMessage(frm="ai", content=TextContent(text="Generic Response"))
        response_payload.messages.append(ingredient_message)
        recipe_conversation_id = self.relational_database.add_recipe_conversation(username,
                                                                                  recipe_conversation_id,
                                                                                  response_payload)
        print("recipe_conversation_id:", recipe_conversation_id)
        return response_payload

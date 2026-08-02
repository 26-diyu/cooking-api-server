import time

from relational_database import RelationalDatabase


class UserSession:
    def __init__(self):
        self.relational_database = RelationalDatabase.get_instance()

    def store(self, username, session_id, expiry=86400):
        if self.relational_database.create_user_session(username, session_id, expiry) == -1:
            return False
        else:
            return True

    def is_valid(self, username, session_id):
        (created_at, expiry) = self.relational_database.get_user_session(username, session_id)
        if created_at == -1 or expiry == -1 or created_at + expiry <= time.time():
            return False
        return True
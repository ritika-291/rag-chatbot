from backend.database import chat_store


def create_conversation(user_id: str):
    return chat_store.create_session(title=f"Chat with {user_id}", user_id=user_id)


def get_or_create_conversation(user_id: str):
    return chat_store.get_or_create_session_by_user(user_id)


def append_message(convo_id: int, role: str, content: str, metadata=None):
    return chat_store.save_message(convo_id, role, content, metadata=metadata)


def get_messages(convo_id: int):
    return chat_store.get_messages(convo_id)
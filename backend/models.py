from pydantic import BaseModel, Field

class ConversationCreate(BaseModel):
    title: str = Field(default="New Chat", max_length=100)

class ConversationRename(BaseModel):
    title: str = Field(min_length=1, max_length=100)

class ChatRequest(BaseModel):
    conversation_id: int = Field(ge=1)
    message: str = Field(min_length=1, max_length=8000)
    regenerate: bool = False
    regenerate_message_id: int | None = Field(default=None, ge=1)

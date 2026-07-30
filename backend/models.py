from pydantic import BaseModel, Field

class ConversationCreate(BaseModel):
    title: str = Field(default="New Chat", max_length=100)

class ConversationRename(BaseModel):
    title: str = Field(min_length=1, max_length=100)

class ChatRequest(BaseModel):
    conversation_id: int
    message: str = Field(min_length=1, max_length=8000)
    regenerate: bool = False

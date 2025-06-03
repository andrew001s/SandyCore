from pydantic import BaseModel


class MessageModel(BaseModel):
    message: str

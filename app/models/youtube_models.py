from typing import Optional

from pydantic import BaseModel


class YouTubeChatMessageModel(BaseModel):
    message: str
    live_chat_id: Optional[str] = None


class YouTubeBroadcastUpdateModel(BaseModel):
    broadcast_id: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    category_id: Optional[str] = None
    privacy_status: Optional[str] = None
    scheduled_start_time: Optional[str] = None
    scheduled_end_time: Optional[str] = None


class YouTubeBroadcastTransitionModel(BaseModel):
    broadcast_id: Optional[str] = None
    status: str


from typing import Optional

from pydantic import BaseModel


class KickProfileModel(BaseModel):
    id: str
    username: str
    email: str = ""
    picProfile: str = ""
    channel_slug: Optional[str] = None
    bio: Optional[str] = None
    created_at: Optional[str] = None

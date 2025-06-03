from typing import Optional

from pydantic import BaseModel


class ProfileModel(BaseModel):
    id: int
    username: str
    email: str
    picProfile: str
    broadcaster_type: Optional[str] = None

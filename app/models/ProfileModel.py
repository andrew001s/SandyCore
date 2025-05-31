from pydantic import BaseModel
from typing import Optional

class ProfileModel(BaseModel):
    id: int
    username: str
    email: str
    picProfile: str
    broadcaster_type: Optional[str] = None

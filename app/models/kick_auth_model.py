from pydantic import BaseModel


class KickAuth(BaseModel):
    token: str
    refresh_token: str
    bot: bool = False

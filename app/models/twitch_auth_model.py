from pydantic import BaseModel


class TwitchAuth(BaseModel):
    token: str
    refresh_token: str
    bot: bool = False

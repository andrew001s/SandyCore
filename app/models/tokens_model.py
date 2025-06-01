from pydantic import BaseModel

class TokenModel(BaseModel):
    token: str
    refresh_token: str

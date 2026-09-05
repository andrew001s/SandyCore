from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class YouTubeAuthor:
    display_name: str = ""
    channel_id: str = ""
    channel_url: str = ""
    is_owner: bool = False
    is_moderator: bool = False
    is_sponsor: bool = False
    profile_image_url: str = ""


@dataclass(slots=True)
class YouTubeEvent:
    event_id: str
    event_type: str
    published_at: str = ""
    raw_payload: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class YouTubeTextMessage(YouTubeEvent):
    author: YouTubeAuthor = field(default_factory=YouTubeAuthor)
    text: str = ""


@dataclass(slots=True)
class YouTubeSuperChat(YouTubeEvent):
    author: YouTubeAuthor = field(default_factory=YouTubeAuthor)
    amount: str = ""
    currency: str = ""
    comment: str = ""
    tier: int = 1


@dataclass(slots=True)
class YouTubeSuperSticker(YouTubeEvent):
    author: YouTubeAuthor = field(default_factory=YouTubeAuthor)
    amount: str = ""
    currency: str = ""
    alt_text: str = ""
    tier: int = 1


@dataclass(slots=True)
class YouTubeNewSponsor(YouTubeEvent):
    author: YouTubeAuthor = field(default_factory=YouTubeAuthor)
    level_name: str = "Miembro"
    is_upgrade: bool = False


@dataclass(slots=True)
class YouTubeMemberMilestone(YouTubeEvent):
    author: YouTubeAuthor = field(default_factory=YouTubeAuthor)
    months: int = 1
    level_name: str = ""
    comment: str = ""


@dataclass(slots=True)
class YouTubeMembershipGifting(YouTubeEvent):
    author: YouTubeAuthor = field(default_factory=YouTubeAuthor)
    gift_count: int = 1
    level_name: str = "Membresías"


@dataclass(slots=True)
class YouTubeGiftMembershipReceived(YouTubeEvent):
    author: YouTubeAuthor = field(default_factory=YouTubeAuthor)
    gifter_channel_id: str = ""
    level_name: str = ""


@dataclass(slots=True)
class YouTubeUserBanned(YouTubeEvent):
    banned_user_name: str = ""
    banned_channel_id: str = ""
    ban_type: str = "permanent"
    duration_seconds: int = 0


@dataclass(slots=True)
class YouTubeChatEnded(YouTubeEvent):
    live_chat_id: str = ""

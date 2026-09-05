from __future__ import annotations

from typing import Any
from app.services.youtube.events.models import (
    YouTubeAuthor,
    YouTubeChatEnded,
    YouTubeEvent,
    YouTubeGiftMembershipReceived,
    YouTubeMemberMilestone,
    YouTubeMembershipGifting,
    YouTubeNewSponsor,
    YouTubeSuperChat,
    YouTubeSuperSticker,
    YouTubeTextMessage,
    YouTubeUserBanned,
)


def _as_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def parse_author(message: dict[str, Any]) -> YouTubeAuthor:
    author_details = message.get("authorDetails")
    if not isinstance(author_details, dict):
        author_details = {}

    snippet = message.get("snippet")
    fallback_channel_id = ""
    if isinstance(snippet, dict):
        fallback_channel_id = _as_text(snippet.get("authorChannelId"))

    display_name = (
        _as_text(author_details.get("displayName"))
        or _as_text(author_details.get("channelId"))
        or fallback_channel_id
        or "Usuario"
    )

    return YouTubeAuthor(
        display_name=display_name,
        channel_id=_as_text(author_details.get("channelId")) or fallback_channel_id,
        channel_url=_as_text(author_details.get("channelUrl")),
        is_owner=bool(author_details.get("isChatOwner")),
        is_moderator=bool(author_details.get("isChatModerator")),
        is_sponsor=bool(author_details.get("isChatSponsor")),
        profile_image_url=_as_text(author_details.get("profileImageUrl")),
    )


class YouTubeEventParser:
    """Factory que parsea los items crudos de liveChatMessages.list a eventos tipados."""

    @classmethod
    def parse(cls, item: dict[str, Any]) -> YouTubeEvent | None:
        if not isinstance(item, dict):
            return None

        event_id = _as_text(item.get("id"))
        snippet = item.get("snippet")
        if not isinstance(snippet, dict):
            return None

        event_type = _as_text(snippet.get("type"))
        published_at = _as_text(snippet.get("publishedAt"))
        author = parse_author(item)

        # 1. Mensaje de Texto Normal
        if event_type == "textMessageEvent":
            text_details = snippet.get("textMessageDetails")
            text = ""
            if isinstance(text_details, dict):
                text = _as_text(text_details.get("messageText"))
            if not text:
                text = _as_text(snippet.get("displayMessage"))
            if not text:
                return None
            return YouTubeTextMessage(
                event_id=event_id,
                event_type=event_type,
                published_at=published_at,
                raw_payload=item,
                author=author,
                text=text,
            )

        # 2. Super Chat
        if event_type == "superChatEvent":
            details = snippet.get("superChatDetails") or {}
            amount = _as_text(details.get("amountDisplayString"))
            if not amount and details.get("amountMicros"):
                try:
                    micros = float(details.get("amountMicros"))
                    currency = _as_text(details.get("currency")) or "USD"
                    amount = f"{micros / 1_000_000:.2f} {currency}"
                except Exception:
                    amount = _as_text(details.get("amountMicros"))

            comment = _as_text(details.get("userComment")) or _as_text(snippet.get("displayMessage"))
            currency = _as_text(details.get("currency"))
            tier = int(details.get("tier") or 1)
            return YouTubeSuperChat(
                event_id=event_id,
                event_type=event_type,
                published_at=published_at,
                raw_payload=item,
                author=author,
                amount=amount or "Super Chat",
                currency=currency,
                comment=comment,
                tier=tier,
            )

        # 3. Super Sticker
        if event_type == "superStickerEvent":
            details = snippet.get("superStickerDetails") or {}
            amount = _as_text(details.get("amountDisplayString"))
            sticker_meta = details.get("superStickerMetadata") or {}
            alt_text = _as_text(sticker_meta.get("altText")) or "Super Sticker"
            currency = _as_text(details.get("currency"))
            tier = int(details.get("tier") or 1)
            return YouTubeSuperSticker(
                event_id=event_id,
                event_type=event_type,
                published_at=published_at,
                raw_payload=item,
                author=author,
                amount=amount or "Super Sticker",
                currency=currency,
                alt_text=alt_text,
                tier=tier,
            )

        # 4. Nuevo Miembro / Patrocinador
        if event_type == "newSponsorEvent":
            details = snippet.get("newSponsorDetails") or {}
            level_name = _as_text(details.get("memberLevelName")) or "Miembro"
            is_upgrade = bool(details.get("isUpgrade"))
            return YouTubeNewSponsor(
                event_id=event_id,
                event_type=event_type,
                published_at=published_at,
                raw_payload=item,
                author=author,
                level_name=level_name,
                is_upgrade=is_upgrade,
            )

        # 5. Hito de Membresía (Renovación)
        if event_type == "memberMilestoneChatEvent":
            details = snippet.get("memberMilestoneChatDetails") or {}
            months = int(details.get("memberMonth") or 1)
            level_name = _as_text(details.get("memberLevelName"))
            comment = _as_text(details.get("userComment")) or _as_text(snippet.get("displayMessage"))
            return YouTubeMemberMilestone(
                event_id=event_id,
                event_type=event_type,
                published_at=published_at,
                raw_payload=item,
                author=author,
                months=months,
                level_name=level_name,
                comment=comment,
            )

        # 6. Regalo de Membresías
        if event_type == "membershipGiftingEvent":
            details = snippet.get("membershipGiftingDetails") or {}
            gift_count = int(details.get("giftMembershipsCount") or 1)
            level_name = _as_text(details.get("giftMembershipsLevelName")) or "Membresías"
            return YouTubeMembershipGifting(
                event_id=event_id,
                event_type=event_type,
                published_at=published_at,
                raw_payload=item,
                author=author,
                gift_count=gift_count,
                level_name=level_name,
            )

        # 7. Membresía Regalada Recibida
        if event_type == "giftMembershipReceivedEvent":
            details = snippet.get("giftMembershipReceivedDetails") or {}
            gifter = _as_text(details.get("gifterChannelId"))
            level_name = _as_text(details.get("memberLevelName"))
            return YouTubeGiftMembershipReceived(
                event_id=event_id,
                event_type=event_type,
                published_at=published_at,
                raw_payload=item,
                author=author,
                gifter_channel_id=gifter,
                level_name=level_name,
            )

        # 8. Usuario Baneado
        if event_type == "userBannedEvent":
            details = snippet.get("userBannedDetails") or {}
            banned_user_details = details.get("bannedUserDetails") or {}
            banned_user_name = _as_text(banned_user_details.get("displayName"))
            banned_channel_id = _as_text(banned_user_details.get("channelId"))
            ban_type = _as_text(details.get("banType")) or "permanent"
            duration = int(details.get("banDurationSeconds") or 0)
            return YouTubeUserBanned(
                event_id=event_id,
                event_type=event_type,
                published_at=published_at,
                raw_payload=item,
                banned_user_name=banned_user_name,
                banned_channel_id=banned_channel_id,
                ban_type=ban_type,
                duration_seconds=duration,
            )

        # 9. Fin del Chat
        if event_type == "chatEndedEvent":
            live_chat_id = _as_text(snippet.get("liveChatId"))
            return YouTubeChatEnded(
                event_id=event_id,
                event_type=event_type,
                published_at=published_at,
                raw_payload=item,
                live_chat_id=live_chat_id,
            )

        # Evento no soportado o desconocido
        return None

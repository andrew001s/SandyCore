import json

import app.services.twitch.auth.auth as auth
from app.domain.errors import CATEGORY_NOT_FOUND, AppError
from app.services.twitch.chat import chat_handler


async def _context(user_id: str | None = None):
    """Devuelve (cliente, broadcaster, chat) de ESTE usuario, nunca de otro."""
    broadcaster = auth.get_broadcaster(user_id, bot=False)
    if broadcaster is None:
        broadcaster = await auth.get_profile_users(bot=False, user_id=user_id)

    client = auth.get_client(user_id, bot=False)
    if client is None:
        raise Exception("No hay una sesión de Twitch autenticada para este usuario")

    chat = chat_handler.get_chat(user_id)
    if chat is None:
        raise Exception("El chat de Twitch no está iniciado para este usuario")

    return client, broadcaster, chat


# Lo que cuenta como "encender" un modo de chat. El modelo no siempre devuelve
# "on": dice "activar", "actívalo" o "sí", y con una comparación exacta contra
# "on" todas esas variantes acababan APAGANDO el modo en vez de encenderlo.
_ENCENDIDO = {
    "on",
    "true",
    "1",
    "si",
    "sí",
    "activar",
    "activa",
    "activalo",
    "actívalo",
    "activado",
    "activada",
    "enciende",
    "encender",
    "enable",
    "enabled",
    "poner",
    "pon",
}


def esta_encendido(valor: str | None) -> bool:
    """¿El objetivo de la orden pide activar el modo?

    Se normaliza porque el objetivo lo escribe un modelo de lenguaje en texto
    libre: comparar contra "on" a secas dejaba fuera casi todas las formas en
    que alguien pide activar algo hablando.
    """
    return (valor or "").strip().strip(".!¡").lower() in _ENCENDIDO


# Órdenes que el clasificador puede pedir. Se valida contra esta lista antes de
# tocar nada del canal: el nombre llega de un modelo, no de código nuestro.
ORDENES = (
    "title",
    "game",
    "category",
    "clip",
    "only_followers",
    "only_subs",
    "only_emotes",
    "slow",
)


async def moderator_actions(title: str, name: str, user_id: str | None = None) -> bool:
    """Ejecuta una orden del stream. Devuelve si se llegó a aplicar."""
    try:
        match name:
            case "title":
                await change_title(title, user_id)
            case "game" | "category":
                await change_game(title, user_id)
            case "clip":
                await create_clip(user_id)
            case "only_followers":
                await only_followers(title, user_id)
            case "only_subs":
                await only_subs(title, user_id)
            case "only_emotes":
                await only_emotes(title, user_id)
            case "slow":
                await slow_mode(title, user_id)
            case _:
                _, broadcaster, chat = await _context(user_id)
                await chat.send_message(
                    room=broadcaster.display_name,
                    text="POLICE No se ha podido ejecutar la orden POLICE ",
                )
                return False
    except AppError:
        # Ya lleva código y motivo: se deja subir para que el usuario sepa qué
        # pasó en vez de recibir un "no se pudo" genérico.
        raise
    except Exception as e:
        print(f"[ORDEN] No se pudo ejecutar {name!r}: {repr(e)}")
        return False
    return True


async def change_title(title: str, user_id: str | None = None):
    twitch, user, chat = await _context(user_id)
    await twitch.modify_channel_information(user.id, title=title)
    await chat.send_message(
        room=user.display_name,
        text=f"POLICE Se ha cambiado el titulo del stream a {title} POLICE ",
    )


async def change_game(game: str, user_id: str | None = None):
    twitch, user, chat = await _context(user_id)
    game_id = None
    async for g in twitch.get_games(names=[game]):
        game_id = g.id
        break

    # Sin esto, una categoría que Twitch no reconoce dejaba game_id en None: la
    # llamada no cambiaba nada y aun así se anunciaba el cambio en el chat.
    if game_id is None:
        raise AppError(
            CATEGORY_NOT_FOUND,
            f"Twitch no tiene ninguna categoría llamada {game!r}",
        )

    await twitch.modify_channel_information(user.id, game_id)
    await chat.send_message(
        room=user.display_name,
        text=f"POLICE Se ha cambiado la categoria del stream a {game} POLICE ",
    )


async def create_clip(user_id: str | None = None):
    twitch, user, chat = await _context(user_id)
    clip = await twitch.create_clip(user.id)
    await chat.send_message(
        room=user.display_name,
        text=f"POLICE Se ha creado un clip {clip.edit_url} POLICE ",
    )


async def only_followers(activate: str, user_id: str | None = None):
    twitch, user, chat = await _context(user_id)
    if esta_encendido(activate):
        await twitch.update_chat_settings(
            broadcaster_id=user.id, moderator_id=user.id, follower_mode=True
        )
        await chat.send_message(
            room=user.display_name,
            text="POLICE Se ha activado el modo seguidores POLICE ",
        )
    else:
        await twitch.update_chat_settings(
            broadcaster_id=user.id, moderator_id=user.id, follower_mode=False
        )
        await chat.send_message(
            room=user.display_name,
            text="POLICE Se ha desactivado el modo seguidores POLICE ",
        )


async def only_subs(activate: str, user_id: str | None = None):
    twitch, user, chat = await _context(user_id)
    if esta_encendido(activate):
        await twitch.update_chat_settings(
            broadcaster_id=user.id, moderator_id=user.id, subscriber_mode=True
        )
        await chat.send_message(
            room=user.display_name, text="POLICE Se ha activado el modo subs POLICE "
        )
    else:
        await twitch.update_chat_settings(
            broadcaster_id=user.id, moderator_id=user.id, subscriber_mode=False
        )
        await chat.send_message(
            room=user.display_name, text="POLICE Se ha desactivado el modo subs POLICE "
        )


async def only_emotes(activate: str, user_id: str | None = None):
    twitch, user, chat = await _context(user_id)
    if esta_encendido(activate):
        await twitch.update_chat_settings(
            broadcaster_id=user.id, moderator_id=user.id, emote_mode=True
        )
        await chat.send_message(
            room=user.display_name, text="POLICE Se ha activado el modo emotes POLICE "
        )
    else:
        await twitch.update_chat_settings(
            broadcaster_id=user.id, moderator_id=user.id, emote_mode=False
        )
        await chat.send_message(
            room=user.display_name,
            text="POLICE Se ha desactivado el modo emotes POLICE ",
        )


async def slow_mode(activate: str, user_id: str | None = None):
    twitch, user, chat = await _context(user_id)
    if esta_encendido(activate):
        await twitch.update_chat_settings(
            broadcaster_id=user.id, moderator_id=user.id, slow_mode=True
        )
        await chat.send_message(
            room=user.display_name, text="POLICE Se ha activado el modo lento POLICE "
        )
    else:
        await twitch.update_chat_settings(
            broadcaster_id=user.id, moderator_id=user.id, slow_mode=False
        )
        await chat.send_message(
            room=user.display_name,
            text="POLICE Se ha desactivado el modo lento POLICE ",
        )


async def get_stream_info(user_id: str | None = None):
    twitch, user, _chat = await _context(user_id)
    get_chatters = await twitch.get_chatters(
        broadcaster_id=user.id, moderator_id=user.id
    )
    chatters_names = [
        chatter.user_name for chatter in get_chatters.data if chatter.user_name
    ]
    get_viewers_accounts = len(chatters_names)
    get_stream = await twitch.get_channel_information(broadcaster_id=user.id)
    stream_info = {
        "name": get_stream[0].broadcaster_name,
        "game": get_stream[0].game_name,
        "chatters": chatters_names,
        "title": get_stream[0].title,
        "viewers": get_viewers_accounts,
        "language": get_stream[0].broadcaster_language,
        "tags": get_stream[0].tags,
    }
    stream_info_json = json.dumps(stream_info)
    return stream_info_json

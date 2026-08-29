"""Apagado de todos los servicios de un usuario.

Se usa cuando el usuario cierra o recarga la página: sin nadie delante no debe
quedarse el bot respondiendo y gastando tokens.
"""

from __future__ import annotations


async def shutdown_all_services(user_id: str) -> dict[str, bool]:
    """Detiene Twitch, Kick y YouTube. Devuelve qué plataformas se pudieron parar.

    El fallo de una no impide parar las demás: la prioridad es que no quede nada
    consumiendo.
    """
    from app.services.kick import lifecycle as kick_lifecycle
    from app.services.twitch import lifecycle as twitch_lifecycle
    from app.services.youtube import youtube as youtube_service

    owner = str(user_id)
    resultados: dict[str, bool] = {}

    for nombre, detener in (
        ("twitch", twitch_lifecycle.stop_services),
        ("kick", kick_lifecycle.stop_services),
        ("youtube", youtube_service.stop_services),
    ):
        try:
            await detener(owner)
            resultados[nombre] = True
        except Exception as exc:
            print(f"[SHUTDOWN] No se pudo detener {nombre} de {owner}: {repr(exc)}")
            resultados[nombre] = False

    return resultados

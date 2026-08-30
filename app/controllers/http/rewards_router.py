from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse

from app.adapters.kick_services import KickService
from app.adapters.twitch_services import TwitchService
from app.core.security.clerk import ClerkUser, verify_clerk_session
from app.services.storage.supabase_store import (
    get_custom_rewards,
    save_custom_rewards,
    get_twitch_tokens,
    get_kick_tokens,
)

router = APIRouter(prefix="/rewards", tags=["Rewards"])


@router.get("")
async def get_rewards(current_user: ClerkUser = Depends(verify_clerk_session)):
    user_id = current_user.user_id
    
    # 1. Obtener configuraciones de la BD
    try:
        saved_rewards = await get_custom_rewards(user_id)
        saved_map = {(r["platform"], r["reward_id"]): r for r in saved_rewards}
    except Exception as exc:
        print(f"[REWARDS ROUTER] Error al cargar configuraciones de Supabase para {user_id}: {repr(exc)}")
        saved_map = {}
    
    twitch_rewards = []
    kick_rewards = []
    
    # 2. Obtener recompensas de Twitch si está conectado
    try:
        twitch_tokens = await get_twitch_tokens(user_id, bot=False)
        if twitch_tokens:
            twitch_service = TwitchService()
            twitch_client, _, broadcaster_id = await twitch_service.return_instance(bot=False, user_id=user_id)
            twitch_resp = await twitch_client.get_custom_reward(broadcaster_id)
            for r in twitch_resp:
                r_dict = r.to_dict() if hasattr(r, 'to_dict') else r
                r_id = r_dict.get("id")
                r_title = r_dict.get("title")
                r_cost = r_dict.get("cost", 0)
                r_color = r_dict.get("background_color")
                
                # Imagen
                image_url = None
                img_obj = r_dict.get("image") or r_dict.get("default_image")
                if isinstance(img_obj, dict):
                    image_url = img_obj.get("url_1x") or img_obj.get("url_2x") or img_obj.get("url_4x")
                
                # Mezclar con guardados
                saved = saved_map.get(("twitch", r_id))
                enabled = saved.get("enabled", False) if saved else False
                prompt = saved.get("prompt", "") if saved else ""
                
                twitch_rewards.append({
                    "reward_id": r_id,
                    "platform": "twitch",
                    "title": r_title,
                    "cost": r_cost,
                    "enabled": enabled,
                    "prompt": prompt,
                    "background_color": r_color,
                    "image_url": image_url
                })
    except Exception as exc:
        print(f"[REWARDS ROUTER] Error al cargar recompensas de Twitch para {user_id}: {repr(exc)}")
        
    # 3. Obtener recompensas de Kick si está conectado
    try:
        kick_tokens = await get_kick_tokens(user_id, bot=False)
        if kick_tokens:
            kick_service = KickService()
            _, kick_client, broadcaster_id = await kick_service.return_instance(bot=False, user_id=user_id)
            if broadcaster_id:
                try:
                    kick_resp = await kick_client.request_json(
                        "GET", f"/public/v1/channels/{broadcaster_id}/channel_points/rewards", authenticated=True
                    )
                    data = kick_resp.get("data") if isinstance(kick_resp, dict) else None
                    if isinstance(data, list):
                        for r_dict in data:
                            r_id = r_dict.get("id") or r_dict.get("subscription_id")
                            r_title = r_dict.get("title") or r_dict.get("name")
                            r_cost = r_dict.get("cost") or r_dict.get("points") or 0
                            
                            # Mezclar con guardados
                            saved = saved_map.get(("kick", str(r_id)))
                            enabled = saved.get("enabled", False) if saved else False
                            prompt = saved.get("prompt", "") if saved else ""
                            
                            kick_rewards.append({
                                "reward_id": str(r_id),
                                "platform": "kick",
                                "title": r_title,
                                "cost": int(r_cost),
                                "enabled": enabled,
                                "prompt": prompt,
                                "background_color": None,
                                "image_url": None
                            })
                except Exception as exc:
                    print(f"[REWARDS ROUTER] Kick API retornó error de recompensas para {user_id}: {repr(exc)}")
    except Exception as exc:
        print(f"[REWARDS ROUTER] Error al iniciar Kick para cargar recompensas para {user_id}: {repr(exc)}")
        
    return JSONResponse(status_code=200, content={
        "twitch": twitch_rewards,
        "kick": kick_rewards
    })


@router.post("")
async def save_rewards(payload: dict, current_user: ClerkUser = Depends(verify_clerk_session)):
    user_id = current_user.user_id
    rewards = payload.get("rewards", [])
    if not isinstance(rewards, list):
        raise HTTPException(status_code=400, detail="Formato de rewards inválido")
    
    validated_rewards = []
    for r in rewards:
        if not isinstance(r, dict):
            continue
        platform = r.get("platform")
        reward_id = r.get("reward_id")
        title = r.get("title")
        if not platform or not reward_id or not title:
            continue
        validated_rewards.append({
            "platform": str(platform),
            "reward_id": str(reward_id),
            "title": str(title),
            "enabled": bool(r.get("enabled", False)),
            "prompt": str(r.get("prompt", ""))
        })
        
    try:
        await save_custom_rewards(user_id, validated_rewards)
        return JSONResponse(status_code=200, content={"message": "Configuración guardada exitosamente"})
    except Exception as e:
        print(f"[REWARDS ROUTER] Error al guardar recompensas para {user_id}: {repr(e)}")
        raise HTTPException(status_code=500, detail=f"Error interno al guardar: {str(e)}")

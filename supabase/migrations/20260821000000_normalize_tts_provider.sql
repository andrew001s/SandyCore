-- El onboarding antiguo guardaba tts_provider = 'fish'. El valor correcto es
-- 'fish_audio'. El backend ya normaliza al leer y al escribir; esta migración
-- solo limpia lo almacenado. Es idempotente: volver a aplicarla no toca nada.
--
-- Se cubren las dos formas en que puede estar el jsonb, porque el backend
-- acepta ambas (ver _normalize_json en supabase_store.py):
--   1. object -> {"tts_provider": "fish", ...}
--   2. string -> "{\"tts_provider\": \"fish\", ...}"  (JSON guardado como texto)
-- En el caso 2 el operador `->>` devuelve NULL, así que un update que solo
-- contemple el caso 1 no encuentra la fila y parece no hacer nada.

-- Caso 1: el jsonb es un objeto.
update public.user_settings
set settings_json = jsonb_set(
        settings_json, '{tts_provider}', '"fish_audio"'::jsonb, false
    ),
    updated_at = now()
where jsonb_typeof(settings_json) = 'object'
  and settings_json ->> 'tts_provider' = 'fish';

-- Caso 2: el jsonb contiene el JSON como texto. Se corrige el valor y de paso
-- se deja la columna como objeto, que es la forma que el backend escribe hoy.
update public.user_settings
set settings_json = jsonb_set(
        (settings_json #>> '{}')::jsonb, '{tts_provider}', '"fish_audio"'::jsonb, false
    ),
    updated_at = now()
where jsonb_typeof(settings_json) = 'string'
  and ((settings_json #>> '{}')::jsonb ->> 'tts_provider') = 'fish';

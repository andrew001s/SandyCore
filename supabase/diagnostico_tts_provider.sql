-- Diagnóstico: por qué el update no tocó la fila.
-- Ejecuta esto en el SQL editor de Supabase y comparte el resultado.

select
    user_id,
    -- 'object' = JSON normal. 'string' = el JSON quedó guardado como texto
    -- dentro del jsonb (doble codificación); en ese caso `->>` devuelve NULL
    -- y el where del update nunca encuentra la fila.
    jsonb_typeof(settings_json)                              as tipo_columna,
    settings_json ->> 'tts_provider'                         as valor_si_es_objeto,
    case
        when jsonb_typeof(settings_json) = 'string'
        then (settings_json #>> '{}')::jsonb ->> 'tts_provider'
    end                                                      as valor_si_es_texto,
    left(settings_json::text, 80)                            as primeros_80_chars
from public.user_settings
order by user_id;

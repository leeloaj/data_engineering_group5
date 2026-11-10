{#
  Surrogate key for dim_track / dim_artist: md5 of the Spotify natural ID.
  Hashed keys are the same every time the dimension is rebuilt, so the
  incremental fact table never points at a key that has shifted.
#}
{% macro hash_key(column) -%}
    md5(cast({{ column }} as text))
{%- endmacro %}

{# Key of the "Unknown artist" row, used until a track has Spotify metadata. #}
{% macro unknown_artist_key() -%}
    md5('unknown')
{%- endmacro %}

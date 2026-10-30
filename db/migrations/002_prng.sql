CREATE OR REPLACE FUNCTION fake_hash_bytes(
    p_locale text, p_seed bigint, p_position bigint, p_field text, p_counter integer DEFAULT 0
) RETURNS bytea
LANGUAGE plpgsql IMMUTABLE PARALLEL SAFE AS $$
BEGIN
    RETURN sha256(convert_to(
        p_locale || '|' || p_seed || '|' || p_position || '|' || p_field || '|' || p_counter, 'UTF8'));
END;
$$;

CREATE OR REPLACE FUNCTION fake_hash_to_uniform(p_hash bytea)
RETURNS double precision
LANGUAGE plpgsql IMMUTABLE PARALLEL SAFE AS $$
BEGIN
    RETURN ((('x' || encode(substring(p_hash FROM 1 FOR 8), 'hex'))::bit(64)::bigint >> 11)
            & 9007199254740991)::double precision / 9007199254740992.0;
END;
$$;

CREATE OR REPLACE FUNCTION fake_uniform(
    p_locale text, p_seed bigint, p_position bigint, p_field text, p_counter integer DEFAULT 0
) RETURNS double precision
LANGUAGE plpgsql IMMUTABLE PARALLEL SAFE AS $$
BEGIN
    RETURN fake_hash_to_uniform(fake_hash_bytes(p_locale, p_seed, p_position, p_field, p_counter));
END;
$$;

CREATE OR REPLACE FUNCTION fake_uniform_int(
    p_locale text, p_seed bigint, p_position bigint, p_field text,
    p_min bigint, p_max bigint, p_counter integer DEFAULT 0
) RETURNS bigint
LANGUAGE plpgsql IMMUTABLE PARALLEL SAFE AS $$
BEGIN
    RETURN p_min + floor(fake_uniform(p_locale, p_seed, p_position, p_field, p_counter)
                         * (p_max - p_min + 1))::bigint;
END;
$$;

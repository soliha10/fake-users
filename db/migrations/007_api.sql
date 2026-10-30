-- Layer 5: public API.

CREATE OR REPLACE FUNCTION fake_locales()
RETURNS TABLE (code text, name text, country text)
LANGUAGE plpgsql STABLE PARALLEL SAFE AS $$
BEGIN
    RETURN QUERY SELECT l.code, l.name, l.country FROM locales l ORDER BY l.code COLLATE "C";
END;
$$;

CREATE OR REPLACE FUNCTION fake_assert_locale(p_locale text)
RETURNS void
LANGUAGE plpgsql STABLE PARALLEL SAFE AS $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM locales WHERE code = p_locale) THEN
        RAISE EXCEPTION 'Unknown locale: %', p_locale USING ERRCODE = 'invalid_parameter_value';
    END IF;
END;
$$;

-- One user at an absolute position. Names are picked once and shared, so the
-- e-mail always matches the displayed name.
CREATE OR REPLACE FUNCTION fake_user(
    p_locale text, p_seed bigint, p_position bigint, p_with_bio boolean DEFAULT true
) RETURNS fake_user_row
LANGUAGE plpgsql STABLE PARALLEL SAFE AS $$
DECLARE
    u fake_user_row;
    first_name text;
    middle_name text;
    last_name text;
BEGIN
    PERFORM fake_assert_locale(p_locale);
    IF p_position < 0 THEN
        RAISE EXCEPTION 'Position must not be negative: %', p_position USING ERRCODE = 'invalid_parameter_value';
    END IF;

    u.pos := p_position;
    u.locale := p_locale;
    u.gender := fake_gender(p_locale, p_seed, p_position);
    first_name := fake_first_name(p_locale, p_seed, p_position, u.gender);
    middle_name := fake_middle_name(p_locale, p_seed, p_position, u.gender);
    last_name := fake_last_name(p_locale, p_seed, p_position);
    u.full_name := fake_full_name(p_locale, p_seed, p_position, u.gender, first_name, middle_name, last_name);
    u.address := fake_address(p_locale, p_seed, p_position);
    u.latitude := fake_lat(fake_uniform(p_locale, p_seed, p_position, 'latitude'));
    u.longitude := fake_lng(fake_uniform(p_locale, p_seed, p_position, 'longitude'));
    u.height_cm := fake_physical(p_locale, p_seed, p_position, u.gender, 'height_cm');
    u.weight_kg := fake_physical(p_locale, p_seed, p_position, u.gender, 'weight_kg');
    u.eye_color := fake_eye_color(p_locale, p_seed, p_position);
    u.phone := fake_phone(p_locale, p_seed, p_position);
    u.email := fake_email(p_locale, p_seed, p_position, first_name, last_name);
    IF p_with_bio THEN
        u.bio := fake_bio(p_locale, p_seed, p_position);
    END IF;
    RETURN u;
END;
$$;

-- One batch. A user's position is batch_index * batch_size + index_in_batch.
CREATE OR REPLACE FUNCTION fake_users(
    p_locale text, p_seed bigint, p_batch_index bigint,
    p_batch_size integer DEFAULT 10, p_with_bio boolean DEFAULT true
) RETURNS SETOF fake_user_row
LANGUAGE plpgsql STABLE PARALLEL SAFE AS $$
BEGIN
    PERFORM fake_assert_locale(p_locale);
    IF p_batch_index < 0 THEN
        RAISE EXCEPTION 'Batch index must not be negative: %', p_batch_index USING ERRCODE = 'invalid_parameter_value';
    END IF;
    IF p_batch_size NOT BETWEEN 1 AND 1000 THEN
        RAISE EXCEPTION 'Batch size must be between 1 and 1000: %', p_batch_size USING ERRCODE = 'invalid_parameter_value';
    END IF;
    IF p_batch_index > (9223372036854775807 - p_batch_size) / p_batch_size THEN
        RAISE EXCEPTION 'Batch index is too large: %', p_batch_index USING ERRCODE = 'invalid_parameter_value';
    END IF;

    RETURN QUERY
    SELECT u.*
    FROM generate_series(0, p_batch_size - 1) AS i
    CROSS JOIN LATERAL fake_user(p_locale, p_seed, p_batch_index * p_batch_size + i, p_with_bio) AS u
    ORDER BY i;
END;
$$;

-- Measures generation speed. Only this routine reads the clock, and it never
-- feeds the clock into generated data.
CREATE OR REPLACE FUNCTION fake_benchmark(
    p_locale text, p_seed bigint, p_n bigint, p_with_bio boolean DEFAULT false
) RETURNS TABLE (users bigint, elapsed_seconds double precision, users_per_second double precision)
LANGUAGE plpgsql VOLATILE AS $$
DECLARE
    started timestamptz := clock_timestamp();
BEGIN
    SELECT count(*) INTO users
    FROM generate_series(0::bigint, p_n - 1) AS i
    CROSS JOIN LATERAL fake_user(p_locale, p_seed, i, p_with_bio) AS u;
    elapsed_seconds := extract(epoch FROM clock_timestamp() - started);
    users_per_second := users / elapsed_seconds;
    RETURN NEXT;
END;
$$;

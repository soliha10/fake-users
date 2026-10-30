CREATE OR REPLACE PROCEDURE fake_rebuild_weights(p_locale text DEFAULT NULL)
LANGUAGE plpgsql AS $$
DECLARE
    weighted_table record;
BEGIN
    FOR weighted_table IN SELECT * FROM (VALUES
        ('names', 'locale, kind, gender'),
        ('titles', 'locale, kind, gender'),
        ('address_parts', 'locale, kind'),
        ('places', 'locale'),
        ('format_templates', 'locale, kind'),
        ('email_domains', 'locale'),
        ('eye_colors', 'locale'),
        ('markov_transitions', 'locale, prefix')
    ) AS weighted_tables (table_name, group_columns)
    LOOP
        EXECUTE format(
            'UPDATE %1$I target SET cum_weight = shares.running_share
             FROM (SELECT ctid AS row_id,
                          (sum(weight) OVER running / sum(weight) OVER (PARTITION BY %2$s))::double precision
                              AS running_share
                   FROM %1$I WHERE $1 IS NULL OR locale = $1
                   WINDOW running AS (PARTITION BY %2$s ORDER BY idx)) shares
             WHERE target.ctid = shares.row_id', weighted_table.table_name, weighted_table.group_columns)
        USING p_locale;
    END LOOP;
END;
$$;

CREATE OR REPLACE FUNCTION fake_hash_to_uniform(p_hash bytea)
RETURNS double precision
LANGUAGE plpgsql IMMUTABLE PARALLEL SAFE AS $$
DECLARE
    bits_outside_mantissa constant integer := 11;
    mantissa_mask constant bigint := 9007199254740991;
    mantissa_range constant double precision := 9007199254740992.0;
BEGIN
    RETURN ((('x' || encode(substring(p_hash FROM 1 FOR 8), 'hex'))::bit(64)::bigint >> bits_outside_mantissa)
            & mantissa_mask)::double precision / mantissa_range;
END;
$$;

CREATE OR REPLACE FUNCTION fake_weighted_pick(
    p_values text[], p_cum double precision[], p_u double precision
) RETURNS text
LANGUAGE plpgsql IMMUTABLE PARALLEL SAFE AS $$
DECLARE
    low_index integer := 1;
    high_index integer := array_length(p_cum, 1);
    middle_index integer;
BEGIN
    WHILE low_index < high_index LOOP
        middle_index := (low_index + high_index) / 2;
        IF p_cum[middle_index] > p_u THEN
            high_index := middle_index;
        ELSE
            low_index := middle_index + 1;
        END IF;
    END LOOP;
    RETURN p_values[low_index];
END;
$$;

CREATE OR REPLACE FUNCTION fake_pick_name(p_locale text, p_kind text, p_gender char, p_u double precision)
RETURNS text
LANGUAGE plpgsql STABLE PARALLEL SAFE AS $$
DECLARE
    picked_name text;
BEGIN
    SELECT value INTO picked_name FROM names
    WHERE locale = p_locale AND kind = p_kind AND gender = p_gender AND cum_weight > p_u
    ORDER BY cum_weight LIMIT 1;
    RETURN picked_name;
END;
$$;

CREATE OR REPLACE FUNCTION fake_pick_title(p_locale text, p_kind text, p_gender char, p_u double precision)
RETURNS text
LANGUAGE plpgsql STABLE PARALLEL SAFE AS $$
DECLARE
    picked_title text;
BEGIN
    SELECT value INTO picked_title FROM titles
    WHERE locale = p_locale AND kind = p_kind AND gender = p_gender AND cum_weight > p_u
    ORDER BY cum_weight LIMIT 1;
    RETURN picked_title;
END;
$$;

CREATE OR REPLACE FUNCTION fake_pick_address_part(p_locale text, p_kind text, p_u double precision)
RETURNS text
LANGUAGE plpgsql STABLE PARALLEL SAFE AS $$
DECLARE
    picked_part text;
BEGIN
    SELECT value INTO picked_part FROM address_parts
    WHERE locale = p_locale AND kind = p_kind AND cum_weight > p_u
    ORDER BY cum_weight LIMIT 1;
    RETURN picked_part;
END;
$$;

CREATE OR REPLACE FUNCTION fake_template(p_locale text, p_kind text, p_u double precision)
RETURNS text
LANGUAGE plpgsql STABLE PARALLEL SAFE AS $$
DECLARE
    picked_template text;
BEGIN
    SELECT template INTO picked_template FROM format_templates
    WHERE locale = p_locale AND kind = p_kind AND cum_weight > p_u
    ORDER BY cum_weight LIMIT 1;
    RETURN picked_template;
END;
$$;

CREATE OR REPLACE FUNCTION fake_gender(p_locale text, p_seed bigint, p_position bigint)
RETURNS char
LANGUAGE plpgsql IMMUTABLE PARALLEL SAFE AS $$
DECLARE
    female_share constant double precision := 0.5;
BEGIN
    RETURN CASE WHEN fake_uniform(p_locale, p_seed, p_position, 'gender') < female_share THEN 'F' ELSE 'M' END;
END;
$$;

CREATE OR REPLACE FUNCTION fake_place(p_locale text, p_seed bigint, p_position bigint)
RETURNS fake_place
LANGUAGE plpgsql STABLE PARALLEL SAFE AS $$
DECLARE
    picked_place fake_place;
    place_draw double precision := fake_uniform(p_locale, p_seed, p_position, 'place');
BEGIN
    SELECT city, region, postal_code INTO picked_place FROM places
    WHERE locale = p_locale AND cum_weight > place_draw
    ORDER BY cum_weight LIMIT 1;
    RETURN picked_place;
END;
$$;

CREATE OR REPLACE FUNCTION fake_email_domain(p_locale text, p_seed bigint, p_position bigint)
RETURNS text
LANGUAGE plpgsql STABLE PARALLEL SAFE AS $$
DECLARE
    picked_domain text;
    domain_draw double precision := fake_uniform(p_locale, p_seed, p_position, 'email_domain');
BEGIN
    SELECT value INTO picked_domain FROM email_domains
    WHERE locale = p_locale AND cum_weight > domain_draw
    ORDER BY cum_weight LIMIT 1;
    RETURN picked_domain;
END;
$$;

CREATE OR REPLACE FUNCTION fake_eye_color(p_locale text, p_seed bigint, p_position bigint)
RETURNS text
LANGUAGE plpgsql STABLE PARALLEL SAFE AS $$
DECLARE
    colors text[];
    cumulative_weights double precision[];
BEGIN
    SELECT array_agg(value ORDER BY idx), array_agg(cum_weight ORDER BY idx) INTO colors, cumulative_weights
    FROM eye_colors WHERE locale = p_locale;
    RETURN fake_weighted_pick(colors, cumulative_weights, fake_uniform(p_locale, p_seed, p_position, 'eye_color'));
END;
$$;

CREATE OR REPLACE FUNCTION fake_physical(
    p_locale text, p_seed bigint, p_position bigint, p_gender char, p_attribute text
) RETURNS numeric
LANGUAGE plpgsql STABLE PARALLEL SAFE AS $$
DECLARE
    distribution physical_distributions;
BEGIN
    SELECT * INTO distribution FROM physical_distributions
    WHERE locale = p_locale AND gender = p_gender AND attribute = p_attribute;
    RETURN round(least(greatest(
        fake_normal(fake_uniform(p_locale, p_seed, p_position, p_attribute, 0),
                    fake_uniform(p_locale, p_seed, p_position, p_attribute, 1),
                    distribution.mean, distribution.stddev),
        distribution.min_value), distribution.max_value)::numeric, 1);
END;
$$;

CREATE OR REPLACE FUNCTION fake_render(p_template text, p_keys text[], p_values text[])
RETURNS text
LANGUAGE plpgsql IMMUTABLE PARALLEL SAFE AS $$
DECLARE
    rendered text := p_template;
BEGIN
    FOR i IN 1 .. array_length(p_keys, 1) LOOP
        rendered := replace(rendered, '{' || p_keys[i] || '}', coalesce(p_values[i], ''));
    END LOOP;
    RETURN btrim(regexp_replace(rendered, '\s+', ' ', 'g'), ' ,');
END;
$$;

CREATE OR REPLACE FUNCTION fake_digits(
    p_locale text, p_seed bigint, p_position bigint, p_field text, p_pattern text
) RETURNS text
LANGUAGE plpgsql IMMUTABLE PARALLEL SAFE AS $$
DECLARE
    slots_per_hash constant integer := 16;
    filled text := '';
    hash_bytes bytea;
    symbol text;
    used_slots integer := 0;
    slot integer;
    slot_value integer;
BEGIN
    FOREACH symbol IN ARRAY string_to_array(p_pattern, NULL) LOOP
        IF symbol NOT IN ('#', '%') THEN
            filled := filled || symbol;
            CONTINUE;
        END IF;
        slot := used_slots % slots_per_hash;
        IF slot = 0 THEN
            hash_bytes := fake_hash_bytes(p_locale, p_seed, p_position, p_field, used_slots / slots_per_hash);
        END IF;
        slot_value := get_byte(hash_bytes, 2 * slot) * 256 + get_byte(hash_bytes, 2 * slot + 1);
        used_slots := used_slots + 1;
        filled := filled || CASE symbol WHEN '#' THEN slot_value % 10 ELSE 2 + slot_value % 8 END;
    END LOOP;
    RETURN filled;
END;
$$;

CREATE OR REPLACE FUNCTION fake_full_name(
    p_locale text, p_seed bigint, p_position bigint, p_gender char,
    p_first text, p_middle text, p_last text
) RETURNS text
LANGUAGE plpgsql STABLE PARALLEL SAFE AS $$
DECLARE
    name_template text := fake_template(p_locale, 'full_name',
                                        fake_uniform(p_locale, p_seed, p_position, 'name_format'));
BEGIN
    RETURN fake_render(name_template,
        ARRAY['title', 'first', 'middle', 'm', 'last', 'suffix'],
        ARRAY[
            CASE WHEN name_template LIKE '%{title}%' THEN fake_title(p_locale, p_seed, p_position, p_gender) END,
            p_first, p_middle, left(p_middle, 1), p_last,
            CASE WHEN name_template LIKE '%{suffix}%' THEN fake_suffix(p_locale, p_seed, p_position, p_gender) END
        ]);
END;
$$;

CREATE OR REPLACE FUNCTION fake_address(p_locale text, p_seed bigint, p_position bigint)
RETURNS text
LANGUAGE plpgsql STABLE PARALLEL SAFE AS $$
DECLARE
    max_apartment constant bigint := 299;
    max_house_letter_offset constant bigint := 3;
    address_template text := fake_template(p_locale, 'address',
                                           fake_uniform(p_locale, p_seed, p_position, 'address_format'));
    place fake_place := fake_place(p_locale, p_seed, p_position);
    max_house_number integer;
BEGIN
    SELECT house_number_max INTO max_house_number FROM locales WHERE code = p_locale;
    RETURN fake_render(address_template,
        ARRAY['number', 'street', 'street_type', 'city', 'region', 'zip', 'zip4', 'apt', 'letter'],
        ARRAY[
            fake_uniform_int(p_locale, p_seed, p_position, 'house_number', 1, max_house_number)::text,
            fake_street(p_locale, p_seed, p_position),
            fake_street_type(p_locale, p_seed, p_position),
            place.city, place.region, place.postal_code,
            fake_digits(p_locale, p_seed, p_position, 'zip4', '####'),
            fake_uniform_int(p_locale, p_seed, p_position, 'apartment', 1, max_apartment)::text,
            chr(ascii('a') + fake_uniform_int(p_locale, p_seed, p_position, 'house_letter', 0,
                                              max_house_letter_offset)::integer)
        ]);
END;
$$;

CREATE OR REPLACE FUNCTION fake_markov_next(p_locale text, p_prefix text, p_u double precision)
RETURNS text
LANGUAGE plpgsql STABLE PARALLEL SAFE AS $$
DECLARE
    next_word_found text;
BEGIN
    SELECT next_word INTO next_word_found FROM markov_transitions
    WHERE locale = p_locale AND prefix = p_prefix AND cum_weight > p_u
    ORDER BY cum_weight LIMIT 1;
    RETURN next_word_found;
END;
$$;

CREATE OR REPLACE FUNCTION fake_markov_text(
    p_locale text, p_seed bigint, p_position bigint, p_field text,
    p_sentences integer DEFAULT 2, p_max_words integer DEFAULT 60
) RETURNS text
LANGUAGE plpgsql STABLE PARALLEL SAFE AS $$
DECLARE
    sentence_start constant text := '^';
    sentence_end constant text := '$';
    previous_word text := sentence_start;
    current_word text := sentence_start;
    next_word text;
    words text[] := '{}';
    finished_sentences integer := 0;
    step integer := 0;
BEGIN
    WHILE finished_sentences < p_sentences LOOP
        next_word := fake_markov_next(p_locale, previous_word || ' ' || current_word,
                                      fake_uniform(p_locale, p_seed, p_position, p_field, step));
        step := step + 1;
        EXIT WHEN next_word IS NULL;
        IF next_word = sentence_end THEN
            finished_sentences := finished_sentences + 1;
            previous_word := sentence_start;
            current_word := sentence_start;
            EXIT WHEN cardinality(words) >= p_max_words;
        ELSE
            words := words || next_word;
            previous_word := current_word;
            current_word := next_word;
        END IF;
    END LOOP;
    RETURN array_to_string(words, ' ');
END;
$$;

CREATE OR REPLACE FUNCTION fake_user(
    p_locale text, p_seed bigint, p_position bigint, p_with_bio boolean DEFAULT true
) RETURNS fake_user_row
LANGUAGE plpgsql STABLE PARALLEL SAFE AS $$
DECLARE
    fake_person fake_user_row;
    first_name text;
    middle_name text;
    last_name text;
BEGIN
    PERFORM fake_assert_locale(p_locale);
    IF p_position < 0 THEN
        RAISE EXCEPTION 'Position must not be negative: %', p_position USING ERRCODE = 'invalid_parameter_value';
    END IF;

    fake_person.pos := p_position;
    fake_person.locale := p_locale;
    fake_person.gender := fake_gender(p_locale, p_seed, p_position);
    first_name := fake_first_name(p_locale, p_seed, p_position, fake_person.gender);
    middle_name := fake_middle_name(p_locale, p_seed, p_position, fake_person.gender);
    last_name := fake_last_name(p_locale, p_seed, p_position);
    fake_person.full_name := fake_full_name(p_locale, p_seed, p_position, fake_person.gender,
                                            first_name, middle_name, last_name);
    fake_person.address := fake_address(p_locale, p_seed, p_position);
    fake_person.latitude := fake_lat(fake_uniform(p_locale, p_seed, p_position, 'latitude'));
    fake_person.longitude := fake_lng(fake_uniform(p_locale, p_seed, p_position, 'longitude'));
    fake_person.height_cm := fake_physical(p_locale, p_seed, p_position, fake_person.gender, 'height_cm');
    fake_person.weight_kg := fake_physical(p_locale, p_seed, p_position, fake_person.gender, 'weight_kg');
    fake_person.eye_color := fake_eye_color(p_locale, p_seed, p_position);
    fake_person.phone := fake_phone(p_locale, p_seed, p_position);
    fake_person.email := fake_email(p_locale, p_seed, p_position, first_name, last_name);
    IF p_with_bio THEN
        fake_person.bio := fake_bio(p_locale, p_seed, p_position);
    END IF;
    RETURN fake_person;
END;
$$;

CREATE OR REPLACE FUNCTION fake_users(
    p_locale text, p_seed bigint, p_batch_index bigint,
    p_batch_size integer DEFAULT 10, p_with_bio boolean DEFAULT true
) RETURNS SETOF fake_user_row
LANGUAGE plpgsql STABLE PARALLEL SAFE AS $$
DECLARE
    max_batch_size constant integer := 1000;
    max_bigint constant bigint := 9223372036854775807;
BEGIN
    PERFORM fake_assert_locale(p_locale);
    IF p_batch_index < 0 THEN
        RAISE EXCEPTION 'Batch index must not be negative: %', p_batch_index USING ERRCODE = 'invalid_parameter_value';
    END IF;
    IF p_batch_size NOT BETWEEN 1 AND max_batch_size THEN
        RAISE EXCEPTION 'Batch size must be between 1 and %: %', max_batch_size, p_batch_size
            USING ERRCODE = 'invalid_parameter_value';
    END IF;
    IF p_batch_index > (max_bigint - p_batch_size) / p_batch_size THEN
        RAISE EXCEPTION 'Batch index is too large: %', p_batch_index USING ERRCODE = 'invalid_parameter_value';
    END IF;

    RETURN QUERY
    SELECT generated_user.*
    FROM generate_series(0, p_batch_size - 1) AS index_in_batch
    CROSS JOIN LATERAL fake_user(p_locale, p_seed, p_batch_index * p_batch_size + index_in_batch, p_with_bio)
        AS generated_user
    ORDER BY index_in_batch;
END;
$$;

CREATE OR REPLACE FUNCTION fake_benchmark(
    p_locale text, p_seed bigint, p_n bigint, p_with_bio boolean DEFAULT false
) RETURNS TABLE (users bigint, elapsed_seconds double precision, users_per_second double precision)
LANGUAGE plpgsql VOLATILE AS $$
DECLARE
    started_at timestamptz := clock_timestamp();
BEGIN
    SELECT count(*) INTO users
    FROM generate_series(0::bigint, p_n - 1) AS user_position
    CROSS JOIN LATERAL fake_user(p_locale, p_seed, user_position, p_with_bio) AS generated_user;
    elapsed_seconds := extract(epoch FROM clock_timestamp() - started_at);
    users_per_second := users / elapsed_seconds;
    RETURN NEXT;
END;
$$;

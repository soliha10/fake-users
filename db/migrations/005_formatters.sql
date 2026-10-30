CREATE OR REPLACE FUNCTION fake_transliterate(p_text text)
RETURNS text
LANGUAGE plpgsql IMMUTABLE PARALLEL SAFE AS $$
BEGIN
    RETURN regexp_replace(
        translate(
            replace(replace(replace(replace(replace(replace(replace(p_text,
                'ß', 'ss'), 'ä', 'ae'), 'ö', 'oe'), 'ü', 'ue'), 'Ä', 'Ae'), 'Ö', 'Oe'), 'Ü', 'Ue'),
            'áàâãåçéèêëíìîïñóòôõúùûýÿÁÀÂÃÅÇÉÈÊËÍÌÎÏÑÓÒÔÕÚÙÛÝ',
            'aaaaaceeeeiiiinoooouuuyyAAAAACEEEEIIIINOOOOUUUY'),
        '[^A-Za-z0-9]', '', 'g') COLLATE "C";
END;
$$;

CREATE OR REPLACE FUNCTION fake_render(p_template text, p_keys text[], p_values text[])
RETURNS text
LANGUAGE plpgsql IMMUTABLE PARALLEL SAFE AS $$
DECLARE
    result text := p_template;
BEGIN
    FOR i IN 1 .. array_length(p_keys, 1) LOOP
        result := replace(result, '{' || p_keys[i] || '}', coalesce(p_values[i], ''));
    END LOOP;
    RETURN btrim(regexp_replace(result, '\s+', ' ', 'g'), ' ,');
END;
$$;

CREATE OR REPLACE FUNCTION fake_digits(
    p_locale text, p_seed bigint, p_position bigint, p_field text, p_pattern text
) RETURNS text
LANGUAGE plpgsql IMMUTABLE PARALLEL SAFE AS $$
DECLARE
    result text := '';
    h bytea;
    ch text;
    used integer := 0;
    v integer;
BEGIN
    FOREACH ch IN ARRAY string_to_array(p_pattern, NULL) LOOP
        IF ch IN ('#', '%') THEN
            IF used % 16 = 0 THEN
                h := fake_hash_bytes(p_locale, p_seed, p_position, p_field, used / 16);
            END IF;
            v := get_byte(h, 2 * (used % 16)) * 256 + get_byte(h, 2 * (used % 16) + 1);
            used := used + 1;
            result := result || CASE ch WHEN '#' THEN v % 10 ELSE 2 + v % 8 END;
        ELSE
            result := result || ch;
        END IF;
    END LOOP;
    RETURN result;
END;
$$;

CREATE OR REPLACE FUNCTION fake_full_name(
    p_locale text, p_seed bigint, p_position bigint, p_gender char,
    p_first text, p_middle text, p_last text
) RETURNS text
LANGUAGE plpgsql STABLE PARALLEL SAFE AS $$
DECLARE
    tpl text := fake_template(p_locale, 'full_name', fake_uniform(p_locale, p_seed, p_position, 'name_format'));
BEGIN
    RETURN fake_render(tpl,
        ARRAY['title', 'first', 'middle', 'm', 'last', 'suffix'],
        ARRAY[
            CASE WHEN tpl LIKE '%{title}%' THEN fake_title(p_locale, p_seed, p_position, p_gender) END,
            p_first, p_middle, left(p_middle, 1), p_last,
            CASE WHEN tpl LIKE '%{suffix}%' THEN fake_suffix(p_locale, p_seed, p_position, p_gender) END
        ]);
END;
$$;

CREATE OR REPLACE FUNCTION fake_address(p_locale text, p_seed bigint, p_position bigint)
RETURNS text
LANGUAGE plpgsql STABLE PARALLEL SAFE AS $$
DECLARE
    tpl text := fake_template(p_locale, 'address', fake_uniform(p_locale, p_seed, p_position, 'address_format'));
    place fake_place := fake_place(p_locale, p_seed, p_position);
    number_max integer;
BEGIN
    SELECT house_number_max INTO number_max FROM locales WHERE code = p_locale;
    RETURN fake_render(tpl,
        ARRAY['number', 'street', 'street_type', 'city', 'region', 'zip', 'zip4', 'apt', 'letter'],
        ARRAY[
            fake_uniform_int(p_locale, p_seed, p_position, 'house_number', 1, number_max)::text,
            fake_street(p_locale, p_seed, p_position),
            fake_street_type(p_locale, p_seed, p_position),
            place.city, place.region, place.postal_code,
            fake_digits(p_locale, p_seed, p_position, 'zip4', '####'),
            fake_uniform_int(p_locale, p_seed, p_position, 'apartment', 1, 299)::text,
            chr(97 + fake_uniform_int(p_locale, p_seed, p_position, 'house_letter', 0, 3)::integer)
        ]);
END;
$$;

CREATE OR REPLACE FUNCTION fake_phone(p_locale text, p_seed bigint, p_position bigint)
RETURNS text
LANGUAGE plpgsql STABLE PARALLEL SAFE AS $$
BEGIN
    RETURN fake_digits(p_locale, p_seed, p_position, 'phone_digits',
        fake_template(p_locale, 'phone', fake_uniform(p_locale, p_seed, p_position, 'phone_format')));
END;
$$;

CREATE OR REPLACE FUNCTION fake_email(
    p_locale text, p_seed bigint, p_position bigint, p_first text, p_last text
) RETURNS text
LANGUAGE plpgsql STABLE PARALLEL SAFE AS $$
DECLARE
    first_part text := lower(fake_transliterate(p_first));
    last_part  text := lower(fake_transliterate(p_last));
BEGIN
    RETURN fake_render(
        fake_template(p_locale, 'email', fake_uniform(p_locale, p_seed, p_position, 'email_format')),
        ARRAY['first', 'last', 'f', 'l', 'n2', 'n4', 'domain'],
        ARRAY[
            first_part, last_part, left(first_part, 1), left(last_part, 1),
            fake_digits(p_locale, p_seed, p_position, 'email_digits', '##'),
            fake_digits(p_locale, p_seed, p_position, 'email_digits', '####'),
            fake_email_domain(p_locale, p_seed, p_position)
        ]);
END;
$$;

CREATE OR REPLACE FUNCTION fake_pick_name(p_locale text, p_kind text, p_gender char, p_u double precision)
RETURNS text
LANGUAGE plpgsql STABLE PARALLEL SAFE AS $$
DECLARE
    result text;
BEGIN
    SELECT value INTO result FROM names
    WHERE locale = p_locale AND kind = p_kind AND gender = p_gender AND cum_weight > p_u
    ORDER BY cum_weight LIMIT 1;
    RETURN result;
END;
$$;

CREATE OR REPLACE FUNCTION fake_pick_title(p_locale text, p_kind text, p_gender char, p_u double precision)
RETURNS text
LANGUAGE plpgsql STABLE PARALLEL SAFE AS $$
DECLARE
    result text;
BEGIN
    SELECT value INTO result FROM titles
    WHERE locale = p_locale AND kind = p_kind AND gender = p_gender AND cum_weight > p_u
    ORDER BY cum_weight LIMIT 1;
    RETURN result;
END;
$$;

CREATE OR REPLACE FUNCTION fake_pick_address_part(p_locale text, p_kind text, p_u double precision)
RETURNS text
LANGUAGE plpgsql STABLE PARALLEL SAFE AS $$
DECLARE
    result text;
BEGIN
    SELECT value INTO result FROM address_parts
    WHERE locale = p_locale AND kind = p_kind AND cum_weight > p_u
    ORDER BY cum_weight LIMIT 1;
    RETURN result;
END;
$$;

CREATE OR REPLACE FUNCTION fake_template(p_locale text, p_kind text, p_u double precision)
RETURNS text
LANGUAGE plpgsql STABLE PARALLEL SAFE AS $$
DECLARE
    result text;
BEGIN
    SELECT template INTO result FROM format_templates
    WHERE locale = p_locale AND kind = p_kind AND cum_weight > p_u
    ORDER BY cum_weight LIMIT 1;
    RETURN result;
END;
$$;

CREATE OR REPLACE FUNCTION fake_gender(p_locale text, p_seed bigint, p_position bigint)
RETURNS char
LANGUAGE plpgsql IMMUTABLE PARALLEL SAFE AS $$
BEGIN
    RETURN CASE WHEN fake_uniform(p_locale, p_seed, p_position, 'gender') < 0.5 THEN 'F' ELSE 'M' END;
END;
$$;

CREATE OR REPLACE FUNCTION fake_first_name(p_locale text, p_seed bigint, p_position bigint, p_gender char)
RETURNS text
LANGUAGE plpgsql STABLE PARALLEL SAFE AS $$
BEGIN
    RETURN fake_pick_name(p_locale, 'first', p_gender, fake_uniform(p_locale, p_seed, p_position, 'first_name'));
END;
$$;

CREATE OR REPLACE FUNCTION fake_middle_name(p_locale text, p_seed bigint, p_position bigint, p_gender char)
RETURNS text
LANGUAGE plpgsql STABLE PARALLEL SAFE AS $$
BEGIN
    RETURN fake_pick_name(p_locale, 'middle', p_gender, fake_uniform(p_locale, p_seed, p_position, 'middle_name'));
END;
$$;

CREATE OR REPLACE FUNCTION fake_last_name(p_locale text, p_seed bigint, p_position bigint)
RETURNS text
LANGUAGE plpgsql STABLE PARALLEL SAFE AS $$
BEGIN
    RETURN fake_pick_name(p_locale, 'last', 'A', fake_uniform(p_locale, p_seed, p_position, 'last_name'));
END;
$$;

CREATE OR REPLACE FUNCTION fake_title(p_locale text, p_seed bigint, p_position bigint, p_gender char)
RETURNS text
LANGUAGE plpgsql STABLE PARALLEL SAFE AS $$
BEGIN
    RETURN fake_pick_title(p_locale, 'title', p_gender, fake_uniform(p_locale, p_seed, p_position, 'title'));
END;
$$;

CREATE OR REPLACE FUNCTION fake_suffix(p_locale text, p_seed bigint, p_position bigint, p_gender char)
RETURNS text
LANGUAGE plpgsql STABLE PARALLEL SAFE AS $$
BEGIN
    RETURN fake_pick_title(p_locale, 'suffix', p_gender, fake_uniform(p_locale, p_seed, p_position, 'suffix'));
END;
$$;

CREATE OR REPLACE FUNCTION fake_street(p_locale text, p_seed bigint, p_position bigint)
RETURNS text
LANGUAGE plpgsql STABLE PARALLEL SAFE AS $$
BEGIN
    RETURN fake_pick_address_part(p_locale, 'street', fake_uniform(p_locale, p_seed, p_position, 'street'));
END;
$$;

CREATE OR REPLACE FUNCTION fake_street_type(p_locale text, p_seed bigint, p_position bigint)
RETURNS text
LANGUAGE plpgsql STABLE PARALLEL SAFE AS $$
BEGIN
    RETURN fake_pick_address_part(p_locale, 'street_type', fake_uniform(p_locale, p_seed, p_position, 'street_type'));
END;
$$;

CREATE OR REPLACE FUNCTION fake_place(p_locale text, p_seed bigint, p_position bigint)
RETURNS fake_place
LANGUAGE plpgsql STABLE PARALLEL SAFE AS $$
DECLARE
    result fake_place;
    u double precision := fake_uniform(p_locale, p_seed, p_position, 'place');
BEGIN
    SELECT city, region, postal_code INTO result FROM places
    WHERE locale = p_locale AND cum_weight > u
    ORDER BY cum_weight LIMIT 1;
    RETURN result;
END;
$$;

CREATE OR REPLACE FUNCTION fake_email_domain(p_locale text, p_seed bigint, p_position bigint)
RETURNS text
LANGUAGE plpgsql STABLE PARALLEL SAFE AS $$
DECLARE
    result text;
    u double precision := fake_uniform(p_locale, p_seed, p_position, 'email_domain');
BEGIN
    SELECT value INTO result FROM email_domains
    WHERE locale = p_locale AND cum_weight > u
    ORDER BY cum_weight LIMIT 1;
    RETURN result;
END;
$$;

CREATE OR REPLACE FUNCTION fake_eye_color(p_locale text, p_seed bigint, p_position bigint)
RETURNS text
LANGUAGE plpgsql STABLE PARALLEL SAFE AS $$
DECLARE
    v text[];
    c double precision[];
BEGIN
    SELECT array_agg(value ORDER BY idx), array_agg(cum_weight ORDER BY idx) INTO v, c
    FROM eye_colors WHERE locale = p_locale;
    RETURN fake_weighted_pick(v, c, fake_uniform(p_locale, p_seed, p_position, 'eye_color'));
END;
$$;

CREATE OR REPLACE FUNCTION fake_physical(
    p_locale text, p_seed bigint, p_position bigint, p_gender char, p_attribute text
) RETURNS numeric
LANGUAGE plpgsql STABLE PARALLEL SAFE AS $$
DECLARE
    d physical_distributions;
BEGIN
    SELECT * INTO d FROM physical_distributions
    WHERE locale = p_locale AND gender = p_gender AND attribute = p_attribute;
    RETURN round(least(greatest(
        fake_normal(fake_uniform(p_locale, p_seed, p_position, p_attribute, 0),
                    fake_uniform(p_locale, p_seed, p_position, p_attribute, 1),
                    d.mean, d.stddev),
        d.min_value), d.max_value)::numeric, 1);
END;
$$;

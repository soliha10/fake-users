CREATE OR REPLACE FUNCTION fake_normal(
    p_u1 double precision, p_u2 double precision,
    p_mean double precision DEFAULT 0, p_stddev double precision DEFAULT 1
) RETURNS double precision
LANGUAGE plpgsql IMMUTABLE PARALLEL SAFE AS $$
BEGIN
    RETURN p_mean + p_stddev * sqrt(-2 * ln(1 - p_u1)) * cos(2 * pi() * p_u2);
END;
$$;

CREATE OR REPLACE FUNCTION fake_weighted_pick(
    p_values text[], p_cum double precision[], p_u double precision
) RETURNS text
LANGUAGE plpgsql IMMUTABLE PARALLEL SAFE AS $$
DECLARE
    lo  integer := 1;
    hi  integer := array_length(p_cum, 1);
    mid integer;
BEGIN
    WHILE lo < hi LOOP
        mid := (lo + hi) / 2;
        IF p_cum[mid] > p_u THEN
            hi := mid;
        ELSE
            lo := mid + 1;
        END IF;
    END LOOP;
    RETURN p_values[lo];
END;
$$;

CREATE OR REPLACE FUNCTION fake_lat(p_u double precision)
RETURNS numeric
LANGUAGE plpgsql IMMUTABLE PARALLEL SAFE AS $$
BEGIN
    RETURN round(degrees(asin(2 * p_u - 1))::numeric, 6);
END;
$$;

CREATE OR REPLACE FUNCTION fake_lng(p_u double precision)
RETURNS numeric
LANGUAGE plpgsql IMMUTABLE PARALLEL SAFE AS $$
BEGIN
    RETURN round((360 * p_u - 180)::numeric, 6);
END;
$$;

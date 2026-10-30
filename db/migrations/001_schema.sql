CREATE TABLE locales (
    code             text PRIMARY KEY,
    name             text NOT NULL,
    country          text NOT NULL,
    house_number_max integer NOT NULL DEFAULT 999 CHECK (house_number_max > 0)
);

CREATE TABLE names (
    locale     text NOT NULL REFERENCES locales (code),
    kind       text NOT NULL CHECK (kind IN ('first', 'middle', 'last')),
    gender     char(1) NOT NULL CHECK (gender IN ('F', 'M', 'A')),
    idx        integer NOT NULL,
    value      text NOT NULL,
    weight     numeric NOT NULL DEFAULT 1 CHECK (weight > 0),
    cum_weight double precision,
    PRIMARY KEY (locale, kind, gender, idx)
);

CREATE INDEX names_pick_idx ON names (locale, kind, gender, cum_weight);

CREATE TABLE titles (
    locale     text NOT NULL REFERENCES locales (code),
    kind       text NOT NULL CHECK (kind IN ('title', 'suffix')),
    gender     char(1) NOT NULL CHECK (gender IN ('F', 'M')),
    idx        integer NOT NULL,
    value      text NOT NULL,
    weight     numeric NOT NULL DEFAULT 1 CHECK (weight > 0),
    cum_weight double precision,
    PRIMARY KEY (locale, kind, gender, idx)
);

CREATE INDEX titles_pick_idx ON titles (locale, kind, gender, cum_weight);

CREATE TABLE address_parts (
    locale     text NOT NULL REFERENCES locales (code),
    kind       text NOT NULL,
    idx        integer NOT NULL,
    value      text NOT NULL,
    weight     numeric NOT NULL DEFAULT 1 CHECK (weight > 0),
    cum_weight double precision,
    PRIMARY KEY (locale, kind, idx)
);

CREATE INDEX address_parts_pick_idx ON address_parts (locale, kind, cum_weight);

CREATE TABLE places (
    locale      text NOT NULL REFERENCES locales (code),
    idx         integer NOT NULL,
    city        text NOT NULL,
    region      text NOT NULL,
    postal_code text NOT NULL,
    weight      numeric NOT NULL DEFAULT 1 CHECK (weight > 0),
    cum_weight  double precision,
    PRIMARY KEY (locale, idx)
);

CREATE INDEX places_pick_idx ON places (locale, cum_weight);

CREATE TABLE format_templates (
    locale     text NOT NULL REFERENCES locales (code),
    kind       text NOT NULL CHECK (kind IN ('full_name', 'address', 'phone', 'email')),
    idx        integer NOT NULL,
    template   text NOT NULL,
    weight     numeric NOT NULL DEFAULT 1 CHECK (weight > 0),
    cum_weight double precision,
    PRIMARY KEY (locale, kind, idx)
);

CREATE INDEX format_templates_pick_idx ON format_templates (locale, kind, cum_weight);

CREATE TABLE email_domains (
    locale     text NOT NULL REFERENCES locales (code),
    idx        integer NOT NULL,
    value      text NOT NULL,
    weight     numeric NOT NULL DEFAULT 1 CHECK (weight > 0),
    cum_weight double precision,
    PRIMARY KEY (locale, idx)
);

CREATE INDEX email_domains_pick_idx ON email_domains (locale, cum_weight);

CREATE TABLE eye_colors (
    locale     text NOT NULL REFERENCES locales (code),
    idx        integer NOT NULL,
    value      text NOT NULL,
    weight     numeric NOT NULL DEFAULT 1 CHECK (weight > 0),
    cum_weight double precision,
    PRIMARY KEY (locale, idx)
);

CREATE TABLE physical_distributions (
    locale    text NOT NULL REFERENCES locales (code),
    attribute text NOT NULL,
    gender    char(1) NOT NULL CHECK (gender IN ('F', 'M')),
    mean      double precision NOT NULL,
    stddev    double precision NOT NULL CHECK (stddev > 0),
    min_value double precision NOT NULL,
    max_value double precision NOT NULL,
    PRIMARY KEY (locale, attribute, gender)
);

CREATE TABLE markov_transitions (
    locale     text NOT NULL REFERENCES locales (code),
    prefix     text NOT NULL,
    idx        integer NOT NULL,
    next_word  text NOT NULL,
    weight     numeric NOT NULL DEFAULT 1 CHECK (weight > 0),
    cum_weight double precision,
    PRIMARY KEY (locale, prefix, idx)
);

CREATE INDEX markov_transitions_pick_idx ON markov_transitions (locale, prefix, cum_weight);

CREATE TYPE fake_place AS (city text, region text, postal_code text);

CREATE TYPE fake_user_row AS (
    pos        bigint,
    locale     text,
    gender     char(1),
    full_name  text,
    address    text,
    latitude   numeric(9, 6),
    longitude  numeric(9, 6),
    height_cm  numeric(5, 1),
    weight_kg  numeric(5, 1),
    eye_color  text,
    phone      text,
    email      text,
    bio        text
);

CREATE PROCEDURE fake_rebuild_weights(p_locale text DEFAULT NULL)
LANGUAGE plpgsql AS $$
DECLARE
    spec record;
BEGIN
    FOR spec IN SELECT * FROM (VALUES
        ('names', 'locale, kind, gender'),
        ('titles', 'locale, kind, gender'),
        ('address_parts', 'locale, kind'),
        ('places', 'locale'),
        ('format_templates', 'locale, kind'),
        ('email_domains', 'locale'),
        ('eye_colors', 'locale'),
        ('markov_transitions', 'locale, prefix')
    ) AS s (tbl, grp)
    LOOP
        EXECUTE format(
            'UPDATE %1$I t SET cum_weight = c.share
             FROM (SELECT ctid AS row_id,
                          (sum(weight) OVER w / sum(weight) OVER (PARTITION BY %2$s))::double precision AS share
                   FROM %1$I WHERE $1 IS NULL OR locale = $1
                   WINDOW w AS (PARTITION BY %2$s ORDER BY idx)) c
             WHERE t.ctid = c.row_id', spec.tbl, spec.grp)
        USING p_locale;
    END LOOP;
END;
$$;

CREATE OR REPLACE FUNCTION fake_markov_next(p_locale text, p_prefix text, p_u double precision)
RETURNS text
LANGUAGE plpgsql STABLE PARALLEL SAFE AS $$
DECLARE
    result text;
BEGIN
    SELECT next_word INTO result FROM markov_transitions
    WHERE locale = p_locale AND prefix = p_prefix AND cum_weight > p_u
    ORDER BY cum_weight LIMIT 1;
    RETURN result;
END;
$$;

CREATE OR REPLACE FUNCTION fake_markov_text(
    p_locale text, p_seed bigint, p_position bigint, p_field text,
    p_sentences integer DEFAULT 2, p_max_words integer DEFAULT 60
) RETURNS text
LANGUAGE plpgsql STABLE PARALLEL SAFE AS $$
DECLARE
    prev1 text := '^';
    prev2 text := '^';
    word text;
    words text[] := '{}';
    finished integer := 0;
    step integer := 0;
BEGIN
    WHILE finished < p_sentences LOOP
        word := fake_markov_next(p_locale, prev1 || ' ' || prev2,
                                 fake_uniform(p_locale, p_seed, p_position, p_field, step));
        step := step + 1;
        EXIT WHEN word IS NULL;
        IF word = '$' THEN
            finished := finished + 1;
            prev1 := '^';
            prev2 := '^';
            EXIT WHEN cardinality(words) >= p_max_words;
        ELSE
            words := words || word;
            prev1 := prev2;
            prev2 := word;
        END IF;
    END LOOP;
    RETURN array_to_string(words, ' ');
END;
$$;

CREATE OR REPLACE FUNCTION fake_bio(p_locale text, p_seed bigint, p_position bigint)
RETURNS text
LANGUAGE plpgsql STABLE PARALLEL SAFE AS $$
BEGIN
    RETURN fake_markov_text(p_locale, p_seed, p_position, 'bio');
END;
$$;

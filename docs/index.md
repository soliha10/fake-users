# Faker in SQL

A library of PostgreSQL stored routines that generates reproducible fake users. It needs no
extension and no application code: load the schema and the lookup data, then call a function.

```sql
SELECT full_name, address, email FROM fake_users('de_DE', 42, 0);
```

The same arguments return the same rows on any connection, at any time, in any call order.

- [Quick start](#quick-start)
- [Public API](#public-api)
- [Building-block routines](#building-block-routines)
- [Algorithms](#algorithms)
- [Database schema](#database-schema)
- [Adding a locale](#adding-a-locale)
- [Benchmark](benchmark.md)

## Quick start

The examples below list the installed locales, read batches 0 and 1 (users 0-9 and 10-19), read one
user by absolute position, and call single-field routines.

```sql
SELECT * FROM fake_locales();

SELECT * FROM fake_users('en_US', 42, 0);
SELECT * FROM fake_users('en_US', 42, 1);

SELECT * FROM fake_user('de_DE', 42, 123456);

SELECT fake_address('en_US', 42, 7);
SELECT fake_phone('de_DE', 42, 7);
SELECT fake_bio('de_DE', 42, 7);
```

Arguments shared by most routines:

| Argument | Type | Meaning |
|---|---|---|
| `p_locale` | `text` | Locale code, such as `en_US` or `de_DE` |
| `p_seed` | `bigint` | Any 64-bit integer, including negative values |
| `p_position` | `bigint` | Zero-based absolute user number |
| `p_gender` | `char` | `F` or `M` |
| `p_field` | `text` | Name of a value stream, such as `latitude` |
| `p_counter` | `integer` | Separates several draws from one field |
| `p_u`, `p_u1`, `p_u2` | `double precision` | Uniform input in `[0, 1)` |

## Public API

### fake_users

```sql
fake_users(p_locale text, p_seed bigint, p_batch_index bigint,
           p_batch_size integer DEFAULT 10, p_with_bio boolean DEFAULT true)
RETURNS SETOF fake_user_row
```

Returns one batch, ordered by position. Each user's position is
`p_batch_index * p_batch_size + index_in_batch`.

| Argument | Rule |
|---|---|
| `p_batch_index` | 0 or greater |
| `p_batch_size` | 1 to 1000 |
| `p_with_bio` | `false` skips Markov text and leaves `bio` NULL, which is faster |

An unknown locale, a negative index, a bad size, or an index that would overflow `bigint` raises
SQLSTATE `22023` (`invalid_parameter_value`).

Example:

```sql
SELECT pos, full_name, email FROM fake_users('de_DE', 42, 0, 3, false);
```

```text
 pos |      full_name             |             email
-----+----------------------------+-------------------------------
   0 | Dr. Edeltraut Scheel       | edeltraut.scheel@post.example
   1 | Carlos Frank-Michael Gratz | carlos.gratz@example.org
   2 | Hans-Georg Maierhofer      | h.maierhofer@example.com
```

### fake_user

```sql
fake_user(p_locale text, p_seed bigint, p_position bigint, p_with_bio boolean DEFAULT true)
RETURNS fake_user_row
```

Returns the user at an absolute position. The result is independent of batch size, so
`fake_users('en_US', 1, 3, 10)` equals positions 30-39 of `fake_users('en_US', 1, 0, 100)`.

`fake_user_row` columns:

| Column | Type | Content |
|---|---|---|
| `pos` | `bigint` | Absolute position |
| `locale` | `text` | Locale code |
| `gender` | `char(1)` | `F` or `M`; keeps names, titles, and body size consistent |
| `full_name` | `text` | Name with optional title, middle name, initial, or suffix |
| `address` | `text` | Locale-formatted address |
| `latitude` | `numeric(9,6)` | Degrees, `-90` to `90` |
| `longitude` | `numeric(9,6)` | Degrees, `-180` to `180` |
| `height_cm` | `numeric(5,1)` | Normally distributed by locale and gender |
| `weight_kg` | `numeric(5,1)` | Normally distributed by locale and gender |
| `eye_color` | `text` | Weighted choice, in the locale's language |
| `phone` | `text` | Number from a reserved or fictional range, in a varied format |
| `email` | `text` | Built from the user's name, on a reserved domain |
| `bio` | `text` | Markov text, or NULL when `p_with_bio` is false |

### fake_bio and fake_markov_text

```sql
fake_bio(p_locale text, p_seed bigint, p_position bigint) RETURNS text
fake_markov_text(p_locale text, p_seed bigint, p_position bigint, p_field text,
                 p_sentences integer DEFAULT 2, p_max_words integer DEFAULT 60) RETURNS text
```

`fake_bio` returns two generated sentences. `fake_markov_text` is the general form: a different
`p_field` gives an independent text for the same user. Generation stops after `p_sentences`
sentences, or at the first sentence end after `p_max_words` words.

```sql
SELECT fake_markov_text('en_US', 42, 0, 'review', 3);
```

### fake_locales

```sql
fake_locales() RETURNS TABLE (code text, name text, country text)
```

Lists installed locales in code order.

### fake_benchmark

```sql
fake_benchmark(p_locale text, p_seed bigint, p_n bigint, p_with_bio boolean DEFAULT false)
RETURNS TABLE (users bigint, elapsed_seconds double precision, users_per_second double precision)
```

Generates `p_n` users inside the database and reports the speed. This is the only routine that
reads the clock, and the clock never reaches generated data.

### fake_rebuild_weights

```sql
CALL fake_rebuild_weights(p_locale text DEFAULT NULL);
```

Recomputes `cum_weight` for one locale, or for all of them when the argument is NULL. Call it
after any change to lookup rows.

## Building-block routines

### PRNG

| Routine | Returns | Purpose |
|---|---|---|
| `fake_hash_bytes(locale, seed, position, field, counter = 0)` | `bytea` | 32 bytes of SHA-256 |
| `fake_hash_to_uniform(hash)` | `double precision` | Converts a hash to `[0, 1)` |
| `fake_uniform(locale, seed, position, field, counter = 0)` | `double precision` | One uniform value |
| `fake_uniform_int(locale, seed, position, field, min, max, counter = 0)` | `bigint` | Integer in `[min, max]` |

### Distributions

| Routine | Returns | Purpose |
|---|---|---|
| `fake_normal(u1, u2, mean = 0, stddev = 1)` | `double precision` | Box-Muller normal value |
| `fake_weighted_pick(values, cum, u)` | `text` | Binary-search choice from arrays |
| `fake_lat(u)` | `numeric` | Latitude for a uniform point on a sphere |
| `fake_lng(u)` | `numeric` | Longitude for a uniform point on a sphere |

### Pickers

| Routine | Purpose |
|---|---|
| `fake_pick_name(locale, kind, gender, u)` | Weighted row from `names` |
| `fake_pick_title(locale, kind, gender, u)` | Weighted row from `titles` |
| `fake_pick_address_part(locale, kind, u)` | Weighted row from `address_parts` |
| `fake_template(locale, kind, u)` | Weighted row from `format_templates` |
| `fake_gender(locale, seed, position)` | `F` or `M`, 50/50 |
| `fake_first_name(locale, seed, position, gender)` | First name |
| `fake_middle_name(locale, seed, position, gender)` | Middle name |
| `fake_last_name(locale, seed, position)` | Last name |
| `fake_title(locale, seed, position, gender)` | Title, such as `Dr.` or `Frau` |
| `fake_suffix(locale, seed, position, gender)` | Suffix, such as `Jr.` |
| `fake_street(locale, seed, position)` | Street stem |
| `fake_street_type(locale, seed, position)` | Street type, such as `Ave` or `straße` |
| `fake_place(locale, seed, position)` | City, region, and postal code from one row |
| `fake_email_domain(locale, seed, position)` | Reserved e-mail domain |
| `fake_eye_color(locale, seed, position)` | Eye color |
| `fake_physical(locale, seed, position, gender, attribute)` | Clamped normal value |

### Formatters

| Routine | Purpose |
|---|---|
| `fake_transliterate(text)` | ASCII for e-mail: `ü`→`ue`, `ö`→`oe`, `ä`→`ae`, `ß`→`ss`, other marks removed |
| `fake_render(template, keys, values)` | Fills `{key}` tokens and tidies spacing |
| `fake_digits(locale, seed, position, field, pattern)` | Fills `#` with 0-9 and `%` with 2-9 |
| `fake_full_name(locale, seed, position, gender, first, middle, last)` | Formatted name |
| `fake_address(locale, seed, position)` | Formatted address |
| `fake_phone(locale, seed, position)` | Formatted phone number |
| `fake_email(locale, seed, position, first, last)` | E-mail address |
| `fake_markov_next(locale, prefix, u)` | Next word of the chain |

## Algorithms

### Reproducible random numbers

Built-in `random()` keeps state per session, so its results depend on what ran before. This
library has no state. Each value is a pure function of its inputs:

```text
hash = sha256('locale|seed|position|field|counter')
u    = (first 8 bytes of hash, top 53 bits) / 2^53
```

A double holds exactly 53 bits of precision, so every bit pattern maps to a distinct value in
`[0, 1)`. Bits are extracted with a right shift and a mask, so no step overflows `bigint`.

Three properties follow:

- **Random access.** User 900,000 costs the same as user 0, because no earlier value is computed.
- **Order independence.** Concurrency and call order cannot change a result.
- **Field independence.** Each field has its own key, so adding a field leaves the others alone.

Stability relies on stored rows too. Every lookup goes through a fixed `idx` and a stored
`cum_weight`, never through unordered rows or a collation. Changing lookup data can therefore
change results, as can changing a routine.

### Position

```text
position = batch_index * batch_size + index_in_batch
```

A user depends on locale, seed, and position. Batch index and index within the batch feed the
position, so batch size only changes how the same stream of users is cut up.

### Normal distribution

`fake_normal` uses the Box-Muller transform. For independent uniform `u1` and `u2`:

```text
z = sqrt(-2 ln(1 - u1)) * cos(2 pi u2)
x = mean + stddev * z
```

Two independent standard normals, seen as a point in the plane, have a rotationally symmetric
density. Their squared radius is exponential, which `-2 ln(1 - u1)` produces, and their angle is
uniform, which `2 pi u2` produces. Using `1 - u1` keeps the logarithm finite, because `u1` can be
0 but never 1.

`fake_physical` reads the mean and standard deviation from `physical_distributions`, then clamps
to the row's minimum and maximum. The range sits far enough from the mean that clamping is rare.

### Uniform points on a sphere

Taking latitude and longitude as two uniform numbers is wrong: it packs points near the poles,
because a latitude band shrinks as it nears a pole. The band between latitudes `a` and `b` on a
unit sphere has area `2 pi (sin b - sin a)`, which is proportional to the change in `sin(latitude)`.
So the constant-density rule is that `sin(latitude)` is uniform:

```text
longitude = 360 u1 - 180
latitude  = degrees(asin(2 u2 - 1))
```

The result is rounded to 6 decimals, about 11 cm at the equator, which also hides last-bit
differences between math libraries. The test suite runs a chi-squared check on 100,000 points. It
confirms that `sin(latitude)` and longitude are flat, and that raw latitude is not.

### Weighted selection

`fake_rebuild_weights` stores each row's running share of its group's weight, in `idx` order, so
the last row in a group has `cum_weight = 1`. To pick a row, draw `u` and take the first row with
`cum_weight > u`:

```sql
SELECT value FROM names
WHERE locale = 'en_US' AND kind = 'last' AND gender = 'A' AND cum_weight > 0.4137
ORDER BY cum_weight LIMIT 1;
```

The composite index makes this a single B-tree descent, whatever the table size. A row's chance of
being chosen is its share of the weight. `fake_weighted_pick` applies the same rule to arrays.

### Name, address, phone, and e-mail variation

Variation lives in `format_templates`, not in code. Each row is a weighted pattern:

| Kind | Example template | Example output |
|---|---|---|
| `full_name` | `{title} {first} {m}. {last}` | `Dr. Maria K. Lopez` |
| `address` (en_US) | `{number} {street} {street_type}, Apt {apt}, {city}, {region} {zip}` | `12 Oak Street, Apt 4, Dixon, IL 61021` |
| `address` (de_DE) | `{street}{street_type} {number}, {zip} {city}` | `Lindenstraße 12, 10115 Berlin` |
| `phone` (en_US) | `(%##) 555-01##` | `(415) 555-0142` |
| `email` | `{f}{last}@{domain}` | `mlopez@example.org` |

Details that keep the data plausible:

- City, region, and postal code come from one `places` row, so they agree with each other.
- The first and last names are picked once, so the e-mail matches the name.
- US phone numbers use 555-0100 to 555-0199, which is set aside for fictional use.
- E-mail domains are `example.com/.org/.net` and `*.example`, which are reserved by RFC 2606 and
  RFC 6761, so no address can reach a real mailbox.

### Markov chain text

A preprocessing script reads public-domain books for each locale, keeps clean sentences of 6-24
words, and counts how often each word follows each pair of words. Sentences begin at the prefix
`^ ^` and end at the token `$`. Each row of `markov_transitions` is one
`(prefix, next word, count)`.

`fake_markov_text` starts at `^ ^` and draws each next word by weighted selection, using the step
number as the PRNG counter. Every prefix in the table has at least one successor, so a walk always
reaches `$`. The word limit is only checked at a sentence end, so the text never stops mid-sentence.

## Design notes

The reasons behind the less obvious choices in the code:

- **`1 - u` in `fake_normal`.** `u` can be 0 but never 1, so `1 - u` is in `(0, 1]` and `ln` stays finite.
- **`prepare_threshold=None` in the app.** Neon's pooled endpoint runs PgBouncer, which cannot track
  server-side prepared statements across pooled connections.
- **One `places` row per city, region, and postal code.** Picking them together keeps an address
  consistent, which three independent picks would not.
- **Only `fake_benchmark` reads the clock.** Generation must not depend on time. The benchmark reads it
  only to report speed, and a test confirms no other routine does.
- **Lookups use `cum_weight` and `idx`.** Both are stored, so a pick never depends on row order or
  collation. `cum_weight` holds the running share of weight in `idx` order, so a pick is one index
  descent and the last row of a group is exactly 1.
- **Separate pick routines per table.** A single dynamic routine would use `EXECUTE`, which gives up
  PL/pgSQL's cached plans on the hottest path.
- **Page restored from the back/forward cache.** The script reloads it, so a control does not stay in
  its loading state.
- **Batches load without a page reload.** The script fetches the same URL the link points to, swaps the
  results section, and updates the address bar, so links stay shareable and the app still works without
  JavaScript.
- **Migration 008.** Migrations run once, so refactored routines ship as `CREATE OR REPLACE` in a new
  file. A fresh database and an upgraded one end up with the same routines.

## Database schema

```text
locales (code PK)
   │  referenced by locale in every table below
   ├── names                  (locale, kind, gender, idx) value, weight, cum_weight
   ├── titles                 (locale, kind, gender, idx) value, weight, cum_weight
   ├── address_parts          (locale, kind, idx) value, weight, cum_weight
   ├── places                 (locale, idx) city, region, postal_code, weight, cum_weight
   ├── format_templates       (locale, kind, idx) template, weight, cum_weight
   ├── email_domains          (locale, idx) value, weight, cum_weight
   ├── eye_colors             (locale, idx) value, weight, cum_weight
   ├── physical_distributions (locale, attribute, gender) mean, stddev, min_value, max_value
   └── markov_transitions     (locale, prefix, idx) next_word, weight, cum_weight
```

Routines form layers, and each depends only on layers above it:

```text
PRNG          fake_hash_bytes → fake_uniform → fake_uniform_int
Distributions fake_normal, fake_weighted_pick, fake_lat, fake_lng
Pickers       fake_first_name, fake_street, fake_place, fake_physical, ...
Formatters    fake_full_name, fake_address, fake_phone, fake_email, fake_bio
API           fake_user → fake_users, fake_benchmark
```

Current volume, for each locale:

| Data | en_US | de_DE |
|---|---|---|
| First names (per gender) | 1,500 | 999-1,003 |
| Middle names (per gender) | 400 | 400 |
| Last names | 1,000 | 1,722 |
| Street stems | 1,063 | 1,345 |
| Place rows | 40,926 | 14,988 |

First name, last name, and place alone give well over 100 million combinations per locale.

## Adding a locale

No schema or routine changes are needed. For a locale such as `fr_FR`:

1. Add a row to `locales`.
2. Add rows to every lookup table, with `idx` starting at 0 in each group: `names`, `titles`,
   `address_parts` (kinds `street` and `street_type`), `places`, `format_templates` (kinds
   `full_name`, `address`, `phone`, `email`), `email_domains`, `eye_colors`,
   `physical_distributions`, and `markov_transitions`.
3. Run `CALL fake_rebuild_weights('fr_FR');`.

The new locale then works in every routine and appears in the web app's dropdown. The test
`test_new_locale_needs_only_rows` proves this by creating one in a rolled-back transaction.

To keep it across reloads, add it to `scripts/build_lookup_data.py`, since `load_lookup.py`
replaces all rows from `data/*.csv`. Also extend `fake_transliterate` if the language has letters
it does not handle: unknown letters are dropped from e-mail addresses.

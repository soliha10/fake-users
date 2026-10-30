"""Build data/*.csv from the public sources listed in data/SOURCES.md.

This is a development-time export, not part of generation. The CSV output is
committed, so a deployment only needs scripts/load_lookup.py.

Usage: python scripts/build_lookup_data.py [--raw-dir .raw]
"""
import argparse
import collections
import csv
import importlib
import pathlib
import re
import urllib.request
import zipfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

SOURCES = {
    "US.zip": "https://download.geonames.org/export/zip/US.zip",
    "DE.zip": "https://download.geonames.org/export/zip/DE.zip",
    "baby-names.csv": "https://raw.githubusercontent.com/hadley/data-baby-names/master/baby-names.csv",
    "pg1342.txt": "https://www.gutenberg.org/cache/epub/1342/pg1342.txt",
    "pg11.txt": "https://www.gutenberg.org/cache/epub/11/pg11.txt",
    "pg22367.txt": "https://www.gutenberg.org/cache/epub/22367/pg22367.txt",
    "pg5323.txt": "https://www.gutenberg.org/cache/epub/5323/pg5323.txt",
    "pg69327.txt": "https://www.gutenberg.org/cache/epub/69327/pg69327.txt",
}
CORPORA = {
    "en_US": ["pg1342.txt", "pg11.txt"],
    "de_DE": ["pg22367.txt", "pg5323.txt", "pg69327.txt"],
}

EN_STREET_STEMS = """Main Oak Maple Pine Cedar Elm Walnut Chestnut Willow Birch Spruce Hickory
Sycamore Magnolia Dogwood Laurel Holly Juniper Aspen Cherry Peach Apple Lake River Hill Valley
Forest Meadow Park Spring Sunset Sunrise Highland Lakeview Ridge Church School College Mill
Market Union Franklin Washington Lincoln Jefferson Madison Monroe Adams Jackson Grant Center
North South East West Broad Front High Water Bridge Railroad Prospect Pleasant Liberty Summit
First Second Third Fourth Fifth Sixth Seventh Eighth Ninth Tenth""".split()
EN_STREET_TYPES = [("Street", 30), ("St", 20), ("Avenue", 15), ("Ave", 15), ("Road", 12), ("Rd", 10),
                   ("Drive", 10), ("Dr", 8), ("Lane", 8), ("Ln", 6), ("Court", 5), ("Ct", 4),
                   ("Place", 4), ("Pl", 3), ("Boulevard", 4), ("Blvd", 3), ("Way", 5), ("Terrace", 2),
                   ("Circle", 2), ("Trail", 2)]
DE_STREET_STEMS = """Haupt Bahnhof Kirch Schul Garten Berg Linden Birken Tannen Eichen Buchen
Ahorn Rosen Wiesen Feld Wald Mühlen Brunnen Markt Dorf Sonnen Blumen Tal Bach See Schloss Burg
Friedhof Post Rathaus Kloster Ring Lange Kurze Neue Alte Goethe Schiller Beethoven Mozart Bach
Kant Lessing Heine Humboldt Bismarck Luther Kepler Einstein Gutenberg Dürer Wagner Brahms
Uhland Mörike Hölderlin Stein Hardenberg Bebel Ebert Adenauer Stresemann Berliner Hamburger
Münchner Kölner Frankfurter Stuttgarter Dresdner Leipziger Bremer Hannoversche Nürnberger""".split()
DE_STREET_TYPES = [("straße", 50), ("weg", 20), ("gasse", 6), ("allee", 6), ("ring", 4),
                   ("platz", 4), ("damm", 3), ("pfad", 2), ("steig", 1), ("ufer", 1)]

# Weighted (value, weight) lists kept by hand because no source provides them.
TITLES = {
    "en_US": {"title": {"M": [("Mr.", 70), ("Dr.", 15), ("Prof.", 5), ("Rev.", 3)],
                        "F": [("Ms.", 40), ("Mrs.", 35), ("Miss", 10), ("Dr.", 12), ("Prof.", 4)]},
              "suffix": {"M": [("Jr.", 50), ("Sr.", 25), ("III", 10), ("PhD", 8), ("MD", 7)],
                         "F": [("PhD", 60), ("MD", 40)]}},
    "de_DE": {"title": {"M": [("Herr", 75), ("Dr.", 15), ("Prof.", 4), ("Prof. Dr.", 4), ("Dipl.-Ing.", 3)],
                        "F": [("Frau", 75), ("Dr.", 15), ("Prof.", 4), ("Prof. Dr.", 4), ("Dipl.-Ing.", 3)]},
              "suffix": {"M": [("M.A.", 50), ("MBA", 50)], "F": [("M.A.", 50), ("MBA", 50)]}},
}
TEMPLATES = {
    "en_US": {
        "full_name": [("{first} {last}", 45), ("{first} {middle} {last}", 15), ("{first} {m}. {last}", 15),
                      ("{title} {first} {last}", 12), ("{title} {first} {m}. {last}", 5),
                      ("{first} {last} {suffix}", 5), ("{last}, {first}", 3)],
        "address": [("{number} {street} {street_type}, {city}, {region} {zip}", 50),
                    ("{number} {street} {street_type}, Apt {apt}, {city}, {region} {zip}", 20),
                    ("{number} {street} {street_type}, Suite {apt}, {city}, {region} {zip}", 10),
                    ("{number} {street} {street_type}, Unit {apt}, {city}, {region} {zip}-{zip4}", 10),
                    ("{number} {street} {street_type}, {city}, {region}, USA", 10)],
        "phone": [("(%##) 555-01##", 40), ("%##-555-01##", 25), ("%##.555.01##", 15),
                  ("+1 %##-555-01##", 15), ("1-%##-555-01##", 5)],
        "email": [("{first}.{last}@{domain}", 35), ("{f}{last}@{domain}", 20), ("{first}{last}{n2}@{domain}", 15),
                  ("{first}_{last}@{domain}", 10), ("{last}.{first}{n2}@{domain}", 10),
                  ("{first}.{l}{n4}@{domain}", 10)],
    },
    "de_DE": {
        "full_name": [("{first} {last}", 50), ("{first} {middle} {last}", 15), ("{first} {m}. {last}", 8),
                      ("{title} {first} {last}", 17), ("{title} {last}", 5), ("{first} {last}, {suffix}", 2),
                      ("{last}, {first}", 3)],
        "address": [("{street}{street_type} {number}, {zip} {city}", 50),
                    ("{street}{street_type} {number}{letter}, {zip} {city}", 15),
                    ("{street}{street_type} {number}, Wohnung {apt}, {zip} {city}", 10),
                    ("{street}{street_type} {number}, D-{zip} {city}", 10),
                    ("{street}{street_type} {number}, {zip} {city}, {region}", 10),
                    ("{zip} {city}, {street}{street_type} {number}", 5)],
        # Number blocks the Bundesnetzagentur keeps free for fictional use.
        "phone": [("030 23125###", 20), ("+49 30 23125###", 15), ("(030) 23125-###", 10), ("040 66969###", 10),
                  ("+49 40 66969###", 10), ("069 90009###", 10), ("+49 69 90009###", 5), ("0171 3920###", 10),
                  ("+49 171 3920###", 10)],
        "email": [("{first}.{last}@{domain}", 40), ("{f}.{last}@{domain}", 20), ("{first}{last}{n2}@{domain}", 15),
                  ("{last}.{first}@{domain}", 10), ("{first}-{last}@{domain}", 5), ("{first}.{l}{n4}@{domain}", 10)],
    },
}
# example.com/.net/.org and the .example TLD are reserved by RFC 2606/6761.
EMAIL_DOMAINS = {
    "en_US": [("example.com", 40), ("example.org", 20), ("example.net", 20), ("mail.example", 10), ("inbox.example", 10)],
    "de_DE": [("example.com", 20), ("example.org", 15), ("example.net", 15), ("beispiel.example", 25),
              ("post.example", 15), ("postfach.example", 10)],
}
EYE_COLORS = {
    "en_US": [("brown", 45), ("blue", 27), ("hazel", 9), ("green", 9), ("gray", 3), ("amber", 5), ("other", 2)],
    "de_DE": [("braun", 35), ("blau", 37), ("grün", 12), ("grau", 8), ("haselnussbraun", 6), ("bernsteinfarben", 2)],
}
# (attribute, gender, mean, stddev, min, max): approximate adult averages.
PHYSICAL = {
    "en_US": [("height_cm", "M", 175.4, 7.6, 140, 215), ("height_cm", "F", 161.7, 7.1, 130, 200),
              ("weight_kg", "M", 90.6, 14.0, 45, 170), ("weight_kg", "F", 77.5, 13.0, 40, 160)],
    "de_DE": [("height_cm", "M", 178.9, 7.3, 140, 215), ("height_cm", "F", 165.8, 6.8, 130, 200),
              ("weight_kg", "M", 85.8, 13.0, 45, 170), ("weight_kg", "F", 69.2, 12.0, 40, 160)],
}
LOCALES = [("en_US", "English (USA)", "United States", 9999),
           ("de_DE", "Deutsch (Deutschland)", "Germany", 199)]

COMPANY_RE = re.compile(r"\d|GmbH|mbH|\bAG\b|\bKG\b|\bSE\b|\be\.\s?V\.|&|Postfach|Bank|Sparkasse|Versicherung"
                        r"|Vertrieb|Verwaltung|Gesellschaft|Finanz|Großkunde|Allianz|Universität|Klinik", re.I)

# GeoNames mixes company and agency postcodes into DE, so multi-word names must look like a place.
DE_PLACE_RE = re.compile(r"[^\W\d_]+(-[^\W\d_]+)*"
                         r"|(Bad|Groß|Klein|Neu|Alt|Sankt|St\.|Hohen|Nieder|Ober|Unter) [^\W\d_]+(-[^\W\d_]+)*"
                         r"|[^\W\d_]+(-[^\W\d_]+)* (am|an der|im|in der|ob der|bei|vor der) [^\W\d_]+( [^\W\d_]+)?")
DE_REGIONS = {"Bavaria": "Bayern", "Lower Saxony": "Niedersachsen", "Land Berlin": "Berlin", "Saxony": "Sachsen",
              "Saxony-Anhalt": "Sachsen-Anhalt", "Thuringia": "Thüringen",
              "Mecklenburg-Western Pomerania": "Mecklenburg-Vorpommern"}


def fetch(raw: pathlib.Path) -> None:
    raw.mkdir(exist_ok=True)
    for name, url in SOURCES.items():
        if not (raw / name).exists():
            print("download", url)
            urllib.request.urlretrieve(url, raw / name)


def write(name, header, rows):
    with open(DATA / name, "w", newline="", encoding="utf-8") as fh:
        out = csv.writer(fh, lineterminator="\n")
        out.writerow(header)
        out.writerows(rows)
    print(f"{name}: {len(rows)} rows")


def provider(module):
    return importlib.import_module(module).Provider


def en_first_names(raw):
    totals = {"boy": collections.Counter(), "girl": collections.Counter()}
    with open(raw / "baby-names.csv", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            totals[row["sex"]][row["name"]] += float(row["percent"])
    return {"M": totals["boy"].most_common(1500), "F": totals["girl"].most_common(1500)}


def de_first_names():
    p = provider("faker.providers.person.de_DE")
    return {"M": [(n, 1) for n in sorted(set(p.first_names_male))],
            "F": [(n, 1) for n in sorted(set(p.first_names_female))]}


def en_last_names():
    p = provider("faker.providers.person.en_US")
    return sorted(p.last_names.items(), key=lambda kv: (-kv[1], kv[0]))


def de_last_names():
    weights = {}
    for module, weight in (("de_LU", 1), ("de_LI", 1), ("de_CH", 1), ("de_AT", 2), ("de_DE", 4)):
        for name in provider(f"faker.providers.person.{module}").last_names:
            if re.fullmatch(r"[^\W\d_]+(-[^\W\d_]+)?", name):
                weights[name] = weight
    return sorted(weights.items(), key=lambda kv: (-kv[1], kv[0]))


def names_rows(locale, firsts, lasts):
    rows = []
    for gender in "MF":
        for idx, (value, weight) in enumerate(firsts[gender]):
            rows.append((locale, "first", gender, idx, value, round(weight, 6)))
        # Middle names are the most common first names for the same gender.
        for idx, (value, weight) in enumerate(firsts[gender][:400]):
            rows.append((locale, "middle", gender, idx, value, round(weight, 6)))
    for idx, (value, weight) in enumerate(lasts):
        rows.append((locale, "last", "A", idx, value, round(weight, 6)))
    return rows


def street_rows(locale, stems, lasts, types):
    plain = [v for v, _ in lasts if "-" not in v and " " not in v]
    values = list(dict.fromkeys(stems + plain))
    rows = [(locale, "street", i, v, 3 if v in stems else 1) for i, v in enumerate(values)]
    rows += [(locale, "street_type", i, v, w) for i, (v, w) in enumerate(types)]
    return rows


def place_rows(raw, code, locale):
    seen = {}
    with zipfile.ZipFile(raw / f"{code}.zip") as z, z.open(f"{code}.txt") as fh:
        for line in fh.read().decode("utf-8").splitlines():
            parts = line.split("\t")
            postal, city, state, state_code = parts[1], parts[2], parts[3], parts[4]
            if not city or not state or COMPANY_RE.search(city):
                continue
            if code == "DE" and not DE_PLACE_RE.fullmatch(city):
                continue
            region = state_code if code == "US" else DE_REGIONS.get(state, state)
            if code == "US" and state_code in {"AA", "AE", "AP", "AS", "FM", "GU", "MH", "MP", "PR", "PW", "VI"}:
                continue
            seen[(city, region, postal)] = True
    return [(locale, i, *key, 1) for i, key in enumerate(sorted(seen))]


def clean_book(path):
    text = path.read_text(encoding="utf-8", errors="ignore")
    start = re.search(r"\*\*\* ?START OF.*?\*\*\*", text)
    end = re.search(r"\*\*\* ?END OF.*?\*\*\*", text)
    text = text[start.end(): end.start()]
    return re.sub(r"\s+", " ", re.sub(r"[_*\[\]{}|=#]", " ", text))


def sentences(text):
    for sentence in re.split(r"(?<=[.!?])\s+(?=[A-ZÄÖÜ])", text):
        sentence = sentence.strip()
        words = sentence.split()
        if not 6 <= len(words) <= 24 or not sentence[0].isupper() or sentence[-1] not in ".!?":
            continue
        if re.search(r"[\"“”„«»‘’()\d:;]|--|—|^[A-ZÄÖÜ ]+[.!?]$|CHAPTER|Kapitel", sentence):
            continue
        yield words


def markov_rows(raw):
    rows = []
    for locale, books in CORPORA.items():
        counts = collections.defaultdict(collections.Counter)
        for book in books:
            for words in sentences(clean_book(raw / book)):
                chain = ["^", "^", *words, "$"]
                for a, b, c in zip(chain, chain[1:], chain[2:]):
                    counts[f"{a} {b}"][c] += 1
        for prefix in sorted(counts):
            ordered = sorted(counts[prefix].items(), key=lambda kv: (-kv[1], kv[0]))
            rows += [(locale, prefix, i, w, n) for i, (w, n) in enumerate(ordered)]
        print(locale, "markov prefixes:", len(counts))
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-dir", default=str(ROOT / ".raw"))
    raw = pathlib.Path(parser.parse_args().raw_dir)
    fetch(raw)
    DATA.mkdir(exist_ok=True)

    en_last, de_last = en_last_names(), de_last_names()
    write("locales.csv", ["code", "name", "country", "house_number_max"], LOCALES)
    write("names.csv", ["locale", "kind", "gender", "idx", "value", "weight"],
          names_rows("en_US", en_first_names(raw), en_last) + names_rows("de_DE", de_first_names(), de_last))
    write("address_parts.csv", ["locale", "kind", "idx", "value", "weight"],
          street_rows("en_US", EN_STREET_STEMS, en_last, EN_STREET_TYPES)
          + street_rows("de_DE", DE_STREET_STEMS, [kv for kv in de_last if kv[1] >= 2], DE_STREET_TYPES))
    write("places.csv", ["locale", "idx", "city", "region", "postal_code", "weight"],
          place_rows(raw, "US", "en_US") + place_rows(raw, "DE", "de_DE"))
    write("titles.csv", ["locale", "kind", "gender", "idx", "value", "weight"],
          [(loc, kind, g, i, v, w) for loc, kinds in TITLES.items() for kind, genders in kinds.items()
           for g, items in genders.items() for i, (v, w) in enumerate(items)])
    write("format_templates.csv", ["locale", "kind", "idx", "template", "weight"],
          [(loc, kind, i, t, w) for loc, kinds in TEMPLATES.items() for kind, items in kinds.items()
           for i, (t, w) in enumerate(items)])
    write("email_domains.csv", ["locale", "idx", "value", "weight"],
          [(loc, i, v, w) for loc, items in EMAIL_DOMAINS.items() for i, (v, w) in enumerate(items)])
    write("eye_colors.csv", ["locale", "idx", "value", "weight"],
          [(loc, i, v, w) for loc, items in EYE_COLORS.items() for i, (v, w) in enumerate(items)])
    write("physical_distributions.csv", ["locale", "attribute", "gender", "mean", "stddev", "min_value", "max_value"],
          [(loc, *row) for loc, items in PHYSICAL.items() for row in items])
    write("markov_transitions.csv", ["locale", "prefix", "idx", "next_word", "weight"], markov_rows(raw))


if __name__ == "__main__":
    main()

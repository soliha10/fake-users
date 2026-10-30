import argparse
import collections
import csv
import importlib
import pathlib
import re
import urllib.request
import zipfile

ROOT_DIR = pathlib.Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"

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
        "phone": [("030 23125###", 20), ("+49 30 23125###", 15), ("(030) 23125-###", 10), ("040 66969###", 10),
                  ("+49 40 66969###", 10), ("069 90009###", 10), ("+49 69 90009###", 5), ("0171 3920###", 10),
                  ("+49 171 3920###", 10)],
        "email": [("{first}.{last}@{domain}", 40), ("{f}.{last}@{domain}", 20), ("{first}{last}{n2}@{domain}", 15),
                  ("{last}.{first}@{domain}", 10), ("{first}-{last}@{domain}", 5), ("{first}.{l}{n4}@{domain}", 10)],
    },
}
EMAIL_DOMAINS = {
    "en_US": [("example.com", 40), ("example.org", 20), ("example.net", 20), ("mail.example", 10), ("inbox.example", 10)],
    "de_DE": [("example.com", 20), ("example.org", 15), ("example.net", 15), ("beispiel.example", 25),
              ("post.example", 15), ("postfach.example", 10)],
}
EYE_COLORS = {
    "en_US": [("brown", 45), ("blue", 27), ("hazel", 9), ("green", 9), ("gray", 3), ("amber", 5), ("other", 2)],
    "de_DE": [("braun", 35), ("blau", 37), ("grün", 12), ("grau", 8), ("haselnussbraun", 6), ("bernsteinfarben", 2)],
}
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

DE_PLACE_RE = re.compile(r"[^\W\d_]+(-[^\W\d_]+)*"
                         r"|(Bad|Groß|Klein|Neu|Alt|Sankt|St\.|Hohen|Nieder|Ober|Unter) [^\W\d_]+(-[^\W\d_]+)*"
                         r"|[^\W\d_]+(-[^\W\d_]+)* (am|an der|im|in der|ob der|bei|vor der) [^\W\d_]+( [^\W\d_]+)?")
DE_REGIONS = {"Bavaria": "Bayern", "Lower Saxony": "Niedersachsen", "Land Berlin": "Berlin", "Saxony": "Sachsen",
              "Saxony-Anhalt": "Sachsen-Anhalt", "Thuringia": "Thüringen",
              "Mecklenburg-Western Pomerania": "Mecklenburg-Vorpommern"}


MIN_SENTENCE_WORDS = 6
MAX_SENTENCE_WORDS = 24
MAX_FIRST_NAMES = 1500
MAX_MIDDLE_NAMES = 400
GERMAN_STREET_SURNAME_MIN_WEIGHT = 2
GERMAN_SURNAME_SOURCE_WEIGHTS = (("de_LU", 1), ("de_LI", 1), ("de_CH", 1), ("de_AT", 2), ("de_DE", 4))
US_EXCLUDED_REGIONS = {"AA", "AE", "AP", "AS", "FM", "GU", "MH", "MP", "PR", "PW", "VI"}
SENTENCE_START = "^"
SENTENCE_END = "$"


def download_sources(raw_dir):
    raw_dir.mkdir(exist_ok=True)
    for file_name, url in SOURCES.items():
        if not (raw_dir / file_name).exists():
            print("download", url)
            urllib.request.urlretrieve(url, raw_dir / file_name)


def write_csv(file_name, header, rows):
    with open(DATA_DIR / file_name, "w", newline="", encoding="utf-8") as csv_file:
        writer = csv.writer(csv_file, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(rows)
    print(f"{file_name}: {len(rows)} rows")


def faker_provider(module):
    return importlib.import_module(module).Provider


def by_weight_then_value(weighted_value):
    value, weight = weighted_value
    return -weight, value


def indexed_rows(weighted_values_by_locale):
    return [(locale, idx, value, weight) for locale, weighted_values in weighted_values_by_locale.items()
            for idx, (value, weight) in enumerate(weighted_values)]


def nested_indexed_rows(weighted_values_by_locale_and_kind):
    return [(locale, kind, idx, value, weight)
            for locale, weighted_values_by_kind in weighted_values_by_locale_and_kind.items()
            for kind, weighted_values in weighted_values_by_kind.items()
            for idx, (value, weight) in enumerate(weighted_values)]


def title_rows():
    return [(locale, kind, gender, idx, value, weight)
            for locale, titles_by_kind in TITLES.items()
            for kind, titles_by_gender in titles_by_kind.items()
            for gender, weighted_titles in titles_by_gender.items()
            for idx, (value, weight) in enumerate(weighted_titles)]


def english_first_names(raw_dir):
    popularity = {"boy": collections.Counter(), "girl": collections.Counter()}
    with open(raw_dir / "baby-names.csv", encoding="utf-8") as csv_file:
        for baby_name in csv.DictReader(csv_file):
            popularity[baby_name["sex"]][baby_name["name"]] += float(baby_name["percent"])
    return {"M": popularity["boy"].most_common(MAX_FIRST_NAMES),
            "F": popularity["girl"].most_common(MAX_FIRST_NAMES)}


def german_first_names():
    provider = faker_provider("faker.providers.person.de_DE")
    return {"M": [(name, 1) for name in sorted(set(provider.first_names_male))],
            "F": [(name, 1) for name in sorted(set(provider.first_names_female))]}


def english_last_names():
    return sorted(faker_provider("faker.providers.person.en_US").last_names.items(), key=by_weight_then_value)


def german_last_names():
    weights = {}
    for module, weight in GERMAN_SURNAME_SOURCE_WEIGHTS:
        for name in faker_provider(f"faker.providers.person.{module}").last_names:
            if re.fullmatch(r"[^\W\d_]+(-[^\W\d_]+)?", name):
                weights[name] = weight
    return sorted(weights.items(), key=by_weight_then_value)


def name_rows(locale, first_names, last_names):
    rows = []
    for gender in "MF":
        for idx, (name, weight) in enumerate(first_names[gender]):
            rows.append((locale, "first", gender, idx, name, round(weight, 6)))
        for idx, (name, weight) in enumerate(first_names[gender][:MAX_MIDDLE_NAMES]):
            rows.append((locale, "middle", gender, idx, name, round(weight, 6)))
    for idx, (name, weight) in enumerate(last_names):
        rows.append((locale, "last", "A", idx, name, round(weight, 6)))
    return rows


def street_rows(locale, stems, last_names, street_types):
    surname_stems = [name for name, _ in last_names if "-" not in name and " " not in name]
    street_names = list(dict.fromkeys(stems + surname_stems))
    rows = [(locale, "street", idx, name, 3 if name in stems else 1) for idx, name in enumerate(street_names)]
    rows += [(locale, "street_type", idx, value, weight) for idx, (value, weight) in enumerate(street_types)]
    return rows


def is_excluded_place(country, city, state, state_code):
    if not city or not state or COMPANY_RE.search(city):
        return True
    if country == "DE":
        return not DE_PLACE_RE.fullmatch(city)
    return state_code in US_EXCLUDED_REGIONS


def place_rows(raw_dir, country, locale):
    places = {}
    with zipfile.ZipFile(raw_dir / f"{country}.zip") as archive, archive.open(f"{country}.txt") as text_file:
        for line in text_file.read().decode("utf-8").splitlines():
            _, postal_code, city, state, state_code, *_ = line.split("\t")
            if not is_excluded_place(country, city, state, state_code):
                region = state_code if country == "US" else DE_REGIONS.get(state, state)
                places[(city, region, postal_code)] = True
    return [(locale, idx, *place, 1) for idx, place in enumerate(sorted(places))]


def clean_book(book_path):
    text = book_path.read_text(encoding="utf-8", errors="ignore")
    start = re.search(r"\*\*\* ?START OF.*?\*\*\*", text)
    end = re.search(r"\*\*\* ?END OF.*?\*\*\*", text)
    return re.sub(r"\s+", " ", re.sub(r"[_*\[\]{}|=#]", " ", text[start.end(): end.start()]))


def is_usable_sentence(sentence, word_count):
    if not MIN_SENTENCE_WORDS <= word_count <= MAX_SENTENCE_WORDS:
        return False
    if not sentence[0].isupper() or sentence[-1] not in ".!?":
        return False
    return not re.search(r"[\"“”„«»‘’()\d:;]|--|—|^[A-ZÄÖÜ ]+[.!?]$|CHAPTER|Kapitel", sentence)


def split_sentences(text):
    for raw_sentence in re.split(r"(?<=[.!?])\s+(?=[A-ZÄÖÜ])", text):
        sentence = raw_sentence.strip()
        words = sentence.split()
        if is_usable_sentence(sentence, len(words)):
            yield words


def count_transitions(raw_dir, books):
    transitions = collections.defaultdict(collections.Counter)
    for book in books:
        for words in split_sentences(clean_book(raw_dir / book)):
            chain = [SENTENCE_START, SENTENCE_START, *words, SENTENCE_END]
            for previous_word, current_word, next_word in zip(chain, chain[1:], chain[2:]):
                transitions[f"{previous_word} {current_word}"][next_word] += 1
    return transitions


def markov_rows(raw_dir):
    rows = []
    for locale, books in CORPORA.items():
        transitions = count_transitions(raw_dir, books)
        for prefix in sorted(transitions):
            next_words = sorted(transitions[prefix].items(), key=by_weight_then_value)
            rows += [(locale, prefix, idx, word, count) for idx, (word, count) in enumerate(next_words)]
        print(locale, "markov prefixes:", len(transitions))
    return rows


def parse_raw_dir():
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-dir", default=str(ROOT_DIR / ".raw"))
    return pathlib.Path(parser.parse_args().raw_dir)


def main():
    raw_dir = parse_raw_dir()
    download_sources(raw_dir)
    DATA_DIR.mkdir(exist_ok=True)

    en_last_names, de_last_names = english_last_names(), german_last_names()
    de_street_surnames = [surname for surname in de_last_names if surname[1] >= GERMAN_STREET_SURNAME_MIN_WEIGHT]
    write_csv("locales.csv", ["code", "name", "country", "house_number_max"], LOCALES)
    write_csv("names.csv", ["locale", "kind", "gender", "idx", "value", "weight"],
              name_rows("en_US", english_first_names(raw_dir), en_last_names)
              + name_rows("de_DE", german_first_names(), de_last_names))
    write_csv("address_parts.csv", ["locale", "kind", "idx", "value", "weight"],
              street_rows("en_US", EN_STREET_STEMS, en_last_names, EN_STREET_TYPES)
              + street_rows("de_DE", DE_STREET_STEMS, de_street_surnames, DE_STREET_TYPES))
    write_csv("places.csv", ["locale", "idx", "city", "region", "postal_code", "weight"],
              place_rows(raw_dir, "US", "en_US") + place_rows(raw_dir, "DE", "de_DE"))
    write_csv("titles.csv", ["locale", "kind", "gender", "idx", "value", "weight"], title_rows())
    write_csv("format_templates.csv", ["locale", "kind", "idx", "template", "weight"], nested_indexed_rows(TEMPLATES))
    write_csv("email_domains.csv", ["locale", "idx", "value", "weight"], indexed_rows(EMAIL_DOMAINS))
    write_csv("eye_colors.csv", ["locale", "idx", "value", "weight"], indexed_rows(EYE_COLORS))
    write_csv("physical_distributions.csv", ["locale", "attribute", "gender", "mean", "stddev", "min_value", "max_value"],
              [(locale, *distribution) for locale, distributions in PHYSICAL.items() for distribution in distributions])
    write_csv("markov_transitions.csv", ["locale", "prefix", "idx", "next_word", "weight"], markov_rows(raw_dir))


if __name__ == "__main__":
    main()

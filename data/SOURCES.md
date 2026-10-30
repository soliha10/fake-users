# Lookup data sources

`scripts/build_lookup_data.py` builds every CSV in this folder from the sources below.

| Data | Source | License |
|---|---|---|
| en_US first and middle names | US Social Security baby names via [hadley/data-baby-names](https://github.com/hadley/data-baby-names) | US government data, public domain |
| en_US last names, de_DE first names | [Faker](https://github.com/joke2k/faker) `person` providers | MIT |
| de_DE last names | Faker `de_DE`, `de_AT`, `de_CH`, `de_LI`, `de_LU` providers | MIT |
| Cities, regions, postal codes | [GeoNames postal codes](https://download.geonames.org/export/zip/) | CC BY 4.0 |
| Street stems | Hand-written common stems plus the last names above | Same as above |
| Markov corpus, en_US | Project Gutenberg #1342 *Pride and Prejudice*, #11 *Alice's Adventures in Wonderland* | Public domain in the USA |
| Markov corpus, de_DE | Project Gutenberg #22367 *Die Verwandlung*, #5323 *Effi Briest*, #69327 *Der Prozess* | Public domain in the USA |
| Titles, templates, eye colors, physical parameters | Hand-written approximations in the build script | Project code |

Physical parameters are rough adult averages for realistic-looking data, not statistics to cite.

German phone templates use blocks recalled as reserved for fictional use by the Bundesnetzagentur.
Check them against the current list before relying on them for anything beyond this demo.

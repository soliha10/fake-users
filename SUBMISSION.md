# Submission draft

**To:** p.lebedev@itransition.com
**Subject:** Task 6_DATA submission

Hello,

Please find my Task 6_DATA submission below.

1. Video demonstration: [VIDEO LINK]
2. Library documentation: [DOCUMENTATION LINK]
3. Deployed application: [APP LINK]
4. Benchmark: [USERS/SEC ON THE DEPLOYED DATABASE] users/second without Markov bios, [USERS/SEC] with them. Full results: [DOCUMENTATION LINK]/benchmark
5. Full name: [YOUR FULL NAME]

The optional Markov chain text generation is implemented.

Best regards,
[YOUR FULL NAME]

# Two-minute demo script

1. **0:00** Open the app. Show locale English (USA), seed 42, batch 0. Point out the name, address, coordinates, physical attributes, phone, e-mail, and bio.
2. **0:20** Switch to Deutsch. Point out German addresses, titles, phone numbers, and text. Change the seed and show that the data changes.
3. **0:40** Click Next batch twice. Note that positions advance by 10.
4. **0:55** Reload the page, then type the same seed again. The same users appear.
5. **1:10** Open `db/migrations/` and show the layers: PRNG, distributions, pickers, formatters, API. Run `SELECT * FROM fake_users('de_DE', 42, 0);` in psql and show that it matches the page.
6. **1:30** Open the documentation. Show the `fake_users` reference and the sphere and Box-Muller sections.
7. **1:50** Show the benchmark page or run `SELECT * FROM fake_benchmark('en_US', 1, 10000);`.

# Table verification log

Where each `verify: true` table stands. Reference: Drik Panchang (the tradition the project
follows where sources disagree). A row is marked `verify: false` only after it matched Drik
Panchang for a real date; the date, place and the times compared are recorded in the table's YAML
comment and in `tests/test_drik_reference.py`.

## Checked so far

Kuala Lumpur, Friday 2026-10-30 (values supplied by the project owner from the Drik Panchang
day page; Drik rounds to the minute):

| Item | Drik | Code | Result |
| ---- | ---- | ---- | ------ |
| Sunrise | 06:57 | 06:57:29 | match |
| Sunset | 18:58 | 18:56:19 | 2 min: Drik's horizon convention differs; not a table matter |
| Nakshatra change | Mrigashira to Ardra 11:34 | 11:34:39 | match |
| Tithi change | Panchami (20) to 21 at 21:54 | 21:55:26 | 1.4 min, within tolerance |
| Rahu Kalam | 11:27-12:57 | 11:27-12:57 | match (Friday row of `kalams.yaml`) |
| Gulika Kalam | 08:27-09:57 | 08:27-09:57 | match |
| Yamaganda | 15:57-17:27 | 15:56-17:26 | match |
| Dur Muhurtam | 09:21-10:09, 13:21-14:09 | 09:21-10:09, 13:21-14:09 | match: Friday day muhurtas 4 and 9, no night one |
| Varjyam | 19:19-20:47 (Ardra) | 19:19-20:47 | match **after correcting Ardra from 11 to 21 ghatikas** |

**A wrong value was found.** `varjyam.yaml` had Ardra at 11 ghatikas (recalled from memory); the
same day gave 15:38-17:07 with it. Drik's window implies 21 ghatikas: the window starts 7 h 45 min
into an Ardra that lasts 22 h 8 min, which is 21 of 60 ghatikas, and its 88-minute length is
4/60 of that duration. The other 26 varjyam values were recalled the same way and may hold the
same kind of error.

## Checked on 2026-11-01 to 2026-11-28 (Kuala Lumpur)

The project owner saved the Drik Panchang day page for each of the 28 days (geoname-id 1735161)
and extracted its text; the Dur Muhurtam and Varjyam windows were compared with the code.

**Durmuhurta: all seven weekdays now match Drik.** Four dates per weekday were consistent.
Three rows were wrong and are corrected:

| Weekday | Was | Drik | Now |
| ------- | --- | ---- | --- |
| Tuesday | day 4, night 8 (a guess) | 09:21-10:09 and 23:45-00:33 | day 4, night 7 |
| Thursday | day 7 | 10:57-11:45 and 15:45-16:33 | day 6 and 12 |
| Saturday | day 1 | 06:57-07:45 and 07:45-08:33 | day 1 and 2 |

Sunday (14), Monday (9, 12) and Wednesday (8) were right. The second Saturday window is shown
in the same Dur Muhurtam row and is the traditional Saturday pair 1 and 2.

**Varjyam: 26 of 27 rows match.** Each Drik window was converted to ghatikas into its
nakshatra (every window is 4.0 ghatikas long). One more value was wrong: **Hasta was 22, Drik
gives 21** (15:06-16:45 on 2026-11-06, 20.97). Ardra 21 was confirmed a second time
(03:45-05:11 on 2026-11-26). The other 24 values matched to within 0.1 ghatika.

**Open: Mula.** Its window at 20 ghatikas matches (01:48-03:36 on 2026-11-13), but Drik also
lists a second Varjyam window in the same Mula, 17:59-19:47 on 2026-11-13 (56 ghatikas, ending
with the nakshatra). `varjyam.yaml` holds one window per nakshatra, so the second is not
modelled and Mula stays `verify: true`. Nothing else in the 28 days showed a second window.

## Still unverified

| Table | Rows checked | Rows unchecked | What would check them |
| ----- | ------------ | -------------- | --------------------- |
| `durmuhurta.yaml` | all 7 weekdays | none | done |
| `varjyam.yaml` | 26 nakshatras | Mula (second window, see above) | Decide whether Mula needs a second window; then one more Drik check |
| `gowri.yaml` | none | all 7 weekdays | The day pages do not include Gowri Panchangam (it links to a separate Drik page): Nalla Neram for each weekday, day and night |
| `functional.yaml` | none | all | A sourced functional-nature table per lagna (a text, not a calendar page) |
| `hora_generic.yaml` | none | all | Replaced the placeholder with the conventional benefic/variable/malefic grouping (1.0 / 0.5 / 0.0) by the `hora-generic-source` feature. No primary text: stays `verify: true` until a cited source confirms it |

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

## Still unverified

| Table | Rows checked | Rows unchecked | What would check them |
| ----- | ------------ | -------------- | --------------------- |
| `durmuhurta.yaml` | Friday | Sunday, Monday, Tuesday, Wednesday, Thursday, Saturday | One Drik day page for each weekday (Tuesday and Thursday matter most: traditions disagree, and the Tuesday night muhurta is a guess) |
| `varjyam.yaml` | Ardra | the other 26 nakshatras | Drik day pages covering each nakshatra: 28 consecutive days include every nakshatra and every weekday |
| `gowri.yaml` | none | all 7 weekdays | Drik's Gowri Panchangam (Nalla Neram) for each weekday, day and night |
| `functional.yaml` | none | all | A sourced functional-nature table per lagna (a text, not a calendar page) |
| `hora_generic.yaml` | none | all | Tracked by the `hora-generic-source` feature |

A day page from Drik Panchang for a place gives durmuhurta and varjyam for that day; for varjyam
the nakshatra running that day matters, so consecutive days are the efficient way to cover all 27.

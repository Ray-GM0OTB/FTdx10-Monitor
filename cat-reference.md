# CAT commands used

FTDX10 Monitor uses Yaesu's text CAT protocol: two-letter commands ending in `;`, for example `FA;` to read VFO-A. The radio answers `ID0761;` to `ID;`, which the program uses to recognise it.

| Command | Purpose |
| --- | --- |
| ID | Identify the radio |
| PS | Power off (PS0;) / on (PS1;, sent twice: the first wakes the radio, the second follows 1–2 s later) |
| AI | Auto information off/on |
| IF / OI | Information on the main / sub VFO (frequency, mode, clarifier, memory, shift) |
| FA / FB | VFO-A / VFO-B frequency |
| MD | Mode |
| AB / BA / SV | VFO A=B, B=A, swap |
| ST / FT | Split / TX VFO |
| TX | PTT |
| SM | S-meter |
| RM | Meters: COMP 3, ALC 4, Po 5, SWR 6, Id 7 |
| AG / RG / SQ / RL / NL / IS / KP / PC / MG / PL / KS / ML / VG | Levels: AF, RF, squelch, NR, NB, IF shift, CW pitch, RF power, mic, processor, key speed, monitor, VOX gain |
| PA / RA / GT / NB / NR / BC / NA | IPO/AMP, ATT, AGC, noise blanker, noise reduction, digital notch, narrow |
| PR / VX / BI / KR / LK | Processor, VOX, break-in, keyer, lock |
| RT / XT / RC | RIT, XIT, clear clarifier |
| OS / CT / CN | Repeater shift, CTCSS mode, CTCSS tone number |
| BY | Busy (squelch open) |
| VS | VFO select |
| KM / KY | Load keyer memory text / play keyer memory |
| MC / MR / MT | Memory channel select / read / read with tag name |

The full command set is in Yaesu's *FTDX10 CAT Operation Reference Manual*.

# Changelog

## Version 1.7 – first public release

### Desktop program
- CAT control of the Yaesu FTDX10 over USB, with the same look and layout as IC9700 Monitor (no spectrum scope).
- Large VFO-A readout with mouse-wheel tuning per digit; VFO-B readout, A=B, B=A, swap, split, TX VFO.
- Yaesu-style S-meter with peak hold, blue up to S9 and red above (PC and phone); TX view with Po, SWR, ALC, COMP and Id.
- POWER key switches the radio on and off over CAT, from the PC or the phone.
- Quick keys: IPO / AMP1 / AMP2, ATT 6 / 12 / 18 dB, AGC F / M / S / AUTO, NB, NR, DNF, NAR, LOCK, TRANSMIT with time-out.
- All FTDX10 modes, 12 band keys from 160 m to 4 m, 13 level sliders.
- PROC, VOX, MON, BK-IN, keyer, RIT / XIT, FM repeater shift and CTCSS.
- CW text and macros through the rig's keyer memory; playback of keyer memories 1-4.
- Memories read from the radio (001-099), CSV import / export, scanner with band-activity plot.
- QSO log with dupe check, ADIF and CSV export.
- When installed in Program Files, settings, the QSO log and the HTTPS certificate are kept in `%LOCALAPPDATA%\FTDX10 Monitor`.

### Phone
- Password-protected phone page over Tailscale with HTTPS on ports 8075 / 8076, running alongside IC9700 Monitor.
- Radio audio on the phone and TALK to transmit, following the radio's squelch.
- Installable as an app from the phone's browser.

### Builds
- Windows setup program built with `build_installer.bat`.
- Single portable `.exe` built with `build_portable_exe.bat`.

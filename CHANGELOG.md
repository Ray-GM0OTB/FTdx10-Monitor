# Changelog

## Version 2.3

### Look
- Level sliders have red LED-style knobs, the same as IC9700 Monitor, glowing brighter the higher the value (IF shift: the further from centre). They replace the silver knobs; a knob stays grey until the radio has reported its level.
- A note beside the ATU key says how to use it: click to tune, right-click for tuner off (phone: tap / long-press).

### Antenna tuner
- **ATU** key (FUNC tab, PC and phone) starts the FTDX10's tuning cycle, like holding the radio's TUNE key; the radio transmits a carrier while it tunes.
- The key shows **TUNING** while it works, then the status bar says the tuner has matched, or that it couldn't. The key stays lit, and "ATU" shows on the display, while the tuner is on.
- To switch the tuner off: right-click **ATU** on the PC, or long-press it on the phone.

### CW decoder
- Decodes CW from the radio's USB receive audio: **CW tab > CW DECODER**, or **View > CW decoder…**. Also on the phone page: **FUNC tab > CW decoder**.
- **Sensitivity:** Auto, Low, Normal, High or Max. High and Max listen through a narrower filter matched to the sending speed and accept weaker signals. Auto runs at the most sensitive level and backs off by itself while it sees static.
- Finds the CW tone by itself (300–1200 Hz), or follows the rig's CW pitch setting.
- Follows the sending speed (about 5–50 WPM) and the signal level automatically.
- Rejects static crashes, and doesn't print a lone E or T caused by one; stays quiet on plain noise.
- Shows prosigns such as <AR>, <SK> and <KN>; characters it can't read show as `*`.

### Android app
- *FTDX10*, the phone page as an Android app (`FTDX10_Remote.apk`), built on the PC with `build_apk.bat`. Uses the Android tools already downloaded for the IC-9700 apps, if present.

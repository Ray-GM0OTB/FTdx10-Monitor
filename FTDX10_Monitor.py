"""
FTDX10 Monitor & Control  -  by GM0OTB
======================================

Version 2.3 - CAT control panel for the Yaesu FTDX10 (HF / 50 / 70 MHz).
Same look and layout as the IC-9700 Monitor 3.0, without the spectrum scope.

New in 2.3
  * Level sliders: red LED-style knobs, the same as IC9700 Monitor, glowing brighter the higher the
    value (IF shift: the further from centre). Grey until the radio has reported the level.

New in 2.2
  * Notes beside the ATU key: click = tune, right-click = tuner off (phone: tap / long-press).

New in 2.1 / 2.0
  * Antenna tuner: the ATU key (FUNC tab, PC and phone) starts the radio's tuning cycle; the radio
    transmits a carrier while it tunes. The key is lit while the tuner is on and shows TUNING while
    it works. Right-click ATU (PC) or long-press it (phone) to switch the tuner off.

New in 1.9
  * CW decoder sensitivity: Auto, Low, Normal, High, Max (decoder window and phone page).
    High / Max / Auto listen through a narrower filter matched to the sending speed and accept
    weaker signals; Auto runs at the most sensitive level and backs off by itself while it sees
    static. Static crashes are rejected (a CW tone is narrow, a crash is wide) and a lone E or T
    from a crash is not printed.

New in 1.8
  * CW decoder (CW tab > CW DECODER, or View > CW decoder): decodes CW from the radio's USB
    receive audio. Finds the tone by itself (or uses the rig's CW pitch), follows the speed
    (about 5-50 WPM) and the signal level, and shows the text in its own window. The phone page
    shows it too (FUNC tab > CW decoder). Uses the same audio set-up as the phone (sounddevice).

New in 1.7
  * POWER key (top left, PC and phone): switches the radio on and off over CAT (PS0; / PS1;).
    Green = radio on; switching off asks first. Switching on works while the radio is off,
    as long as the USB cable is connected and the radio has DC power.
  * Phone LEVELS tab: a note under AF explains that AF is the radio's own volume, and that the
    listening level on the phone is set on the AUDIO tab.

New in 1.6
  * S-meter bar is blue up to S9 and red above S9 (PC window and phone page).

New in 1.5
  * Installed in Program Files: settings, QSO log and the https certificate are saved in
    %LOCALAPPDATA%\\FTDX10 Monitor (fixes "Access is denied" when turning on HTTPS).

New in 1.4
  * Phone audio: never muted while the squelch is fully down; AUDIO tab shows which sound
    device is in use and when it is muting for a closed squelch.

New in 1.3
  * Phone: "APP" / "INSTALL AS AN APP" button always shown - installs straight away where the
    browser allows it, otherwise shows the steps for that phone (iPhone, Samsung, Chrome).

New in 1.2
  * New "Phone" menu: phone access, audio (RX / TX), HTTPS and opening the phone page.

New in 1.1
  * Phone access: Settings > Phone access... turns on a password-protected web page for your phone
    (over Tailscale): display, meter, tuning, modes, bands, levels, functions, memories.
  * Phone audio both ways through the FTDX10's USB audio: hear the radio, hold TALK to transmit.
    Phone audio follows the rig squelch. Needs:  python -m pip install sounddevice
  * Built-in https page with this PC's Tailscale certificate (Phone access > Turn on HTTPS),
    needed for the phone microphone; the page installs as an app (Chrome > Install app).
  * Runs next to the IC9700 Monitor: own ports (8075 / 8076) and sign-in.

Features
  * Large VFO-A readout that fills the screen width - scroll the mouse wheel over any
    digit to tune that digit; ▲/▼ keys = step, PgUp/PgDn = 1 MHz.
  * Yaesu-style S-meter with peak hold; TX view shows Po (watts), SWR, ALC, COMP, Id.
  * VFO-B readout (double-click to swap A/B), A=B, B=A, split, TX VFO select.
  * Quick keys: IPO/AMP1/AMP2, ATT 6/12/18 dB, AGC F/M/S/AUTO, NB, NR, DNF, NAR, LOCK and
    TRANSMIT (time-out protected, always released on disconnect / exit).
  * All modes (LSB, USB, CW-U/L, AM, FM, FM-N, RTTY-L/U, DATA-L/U/FM, PSK), 12 band keys.
  * 13 levels: AF, RF, SQL, NR, NB, IF SHIFT, CW pitch, RF power, mic, processor,
    key speed, monitor, VOX gain - square silver sliders.
  * PROC, VOX, MON, BK-IN, keyer, RIT/XIT with clarifier offset and clear,
    FM repeater shift (+/-) and CTCSS TONE / TSQL with tone selection.
  * CW: free text and 6 macros sent through the rig's keyer memory 5, plus playback of
    the rig's keyer memories 1-4.
  * Read memories 001-099 from the radio (frequency, mode, shift, CTCSS, tag name),
    recall to VFO or select the channel on the rig.
  * Memories with CSV import / export, scanner with band-activity plot,
    QSO log with dupe check, ADIF + CSV export.

Requires:  python -m pip install pyserial sounddevice   (sounddevice only for phone audio)
Radio:     MENU > OPERATION SETTING > GENERAL > CAT RATE (38400 recommended).
           Use the "Enhanced COM Port" of the FTDX10's USB connection for CAT.
"""
import base64
import csv
import hashlib
import hmac
import json
import math
import os
import queue
import re
import secrets
import select
import shutil
import socket
import ssl
import subprocess
import sys
import threading
import time
import tkinter as tk
import tkinter.font as tkfont
import urllib.parse
import webbrowser
import zlib
from array import array
from collections import deque
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from tkinter import filedialog, messagebox, ttk

# -----------------------------------------------------------------
# 1. CRASH-PROOF SERIAL ENVIRONMENT INGESTION
# -----------------------------------------------------------------
SERIAL_READY = False
try:
    import serial
    import serial.tools.list_ports
    SERIAL_READY = True
except ImportError:
    pass

AUDIO_READY = False          # phone audio needs sounddevice (PortAudio); everything else works without it
sd = None
try:
    import sounddevice as sd
    AUDIO_READY = True
except Exception:
    sd = None

# -----------------------------------------------------------------
# 2. CONSTANTS
# -----------------------------------------------------------------
RIG_ID = "0761"          # answer to "ID;" from an FTDX10

# MD command mode codes
MODES = {"1": "LSB", "2": "USB", "3": "CW-U", "4": "FM", "5": "AM", "6": "RTTY-L", "7": "CW-L",
         "8": "DATA-L", "9": "RTTY-U", "A": "DATA-FM", "B": "FM-N", "C": "DATA-U", "D": "AM-N",
         "E": "PSK", "F": "DATA-FM-N"}
MODE_REVERSE = {v: k for k, v in MODES.items()}
MODE_LIST = ["LSB", "USB", "CW-U", "CW-L", "AM", "FM", "FM-N",
             "RTTY-L", "RTTY-U", "DATA-L", "DATA-U", "DATA-FM", "PSK", "AM-N"]

ADIF_MODES = {
    "LSB": ("SSB", "LSB"), "USB": ("SSB", "USB"), "CW-U": ("CW", None), "CW-L": ("CW", None),
    "AM": ("AM", None), "AM-N": ("AM", None), "FM": ("FM", None), "FM-N": ("FM", None),
    "RTTY-L": ("RTTY", None), "RTTY-U": ("RTTY", None), "PSK": ("PSK", "PSK31"),
    "DATA-L": ("SSB", "LSB"), "DATA-U": ("SSB", "USB"), "DATA-FM": ("FM", None), "DATA-FM-N": ("FM", None),
}

def _can_write(d):
    """Really try to write a file (os.access() says yes for Program Files on Windows, then writes fail)."""
    test = os.path.join(d, f".ftdx10_write_test_{os.getpid()}")
    try:
        with open(test, "w") as f:
            f.write("x")
        os.remove(test)
        return True
    except OSError:
        return False


if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(sys.executable)  # next to the .exe (portable copy)
    if not _can_write(BASE_DIR):                # installed in Program Files: keep settings in AppData instead
        BASE_DIR = os.path.join(os.environ.get("LOCALAPPDATA") or os.path.expanduser("~"), "FTDX10 Monitor")
        os.makedirs(BASE_DIR, exist_ok=True)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "ftdx10_settings.json")
CERT_PATH = os.path.join(BASE_DIR, "ftdx10_https.crt")      # Tailscale certificate for the phone's https page
KEY_PATH = os.path.join(BASE_DIR, "ftdx10_https.key")
QSO_PATH = os.path.join(BASE_DIR, "ftdx10_qso_log.json")
BAUD_RATES = [4800, 9600, 19200, 38400]
AUTO_PORT = "Auto-detect"
APP_VERSION = "2.3"
APP_AUTHOR = "GM0OTB"
RIG_TITLE = "FTDX10"

# ---- Colour palette: radio body (case, keys) ----
BG = "#1b1c1f"
PANEL = "#232529"
PANEL2 = "#151618"
BORDER = "#393c42"
FIELD = "#101113"
BTN = "#33363b"
BTN_HOVER = "#3d4147"
BTN_DOWN = "#26282c"
KEY_HI = "#4b4f56"
KEY_SHADOW = "#0b0c0d"
TEXT = "#eef1f5"
MUTED = "#9aa1ab"
DIM = "#5c616a"
GHOST = "#0b0d12"
SEG_OFF = "#17191d"
ACCENT = "#5ab8ff"
ACCENT_DIM = "#173149"
ACCENT_LO = "#2c6ea6"
GREEN = "#4ade80"
GREEN_DIM = "#143522"
AMBER = "#ffad1f"
AMBER_DIM = "#4a3410"
ORANGE = "#ff8a3d"
RED = "#ff3b30"
RED_DIM = "#4d1512"
BLUE = "#3b82f6"

# ---- Colour palette: the radio's display ----
LCD_BG = "#000000"
LCD_EDGE = "#2d3139"
LCD_SEP = "#1e2530"
LCD_TEXT = "#ffffff"
LCD_LABEL = "#a8b3c3"
LCD_DIM = "#3b4250"
LCD_SEG_OFF = "#14171d"
LCD_MAIN = "#1f5fc4"
LCD_SUB = "#4a5160"
LCD_RED = "#ff4a3d"
LCD_SBLUE = "#2f8bff"     # S-meter bar up to S9
LCD_GREEN = "#3ddc84"
LCD_ORANGE = "#ffa62b"
SOFTKEY = "#2a2e36"
SOFTKEY_HI = "#3a404b"
SOFTKEY_ON = "#2d63c8"

METER_MAX = 255
S9_RAW = 130
LINK_MISS_LIMIT = 8
RECONNECT_MS = 3000
SCAN_SETTLE = 0.2
MIN_DWELL = 0.3
REPLY_TIMEOUT = 0.5

# Meter calibration (raw 0-255 -> value), approximations of the FTDX10's meter scales
STR_CAL = [(0, -54), (12, -48), (27, -42), (40, -36), (55, -30), (65, -24), (80, -18), (95, -12),
           (112, -6), (130, 0), (150, 10), (172, 20), (190, 30), (220, 40), (240, 50), (255, 60)]
SWR_CAL = [(0, 1.0), (26, 1.2), (52, 1.5), (89, 2.0), (126, 3.0), (173, 4.0), (236, 5.0), (255, 25.0)]
PO_CAL = [(0, 0.0), (10, 0.8), (50, 8.0), (100, 26.0), (150, 54.0), (200, 92.0), (250, 140.0), (255, 150.0)]

S_TICKS = [("S1", 12), ("3", 40), ("5", 65), ("7", 95), ("9", 130), ("+20", 172), ("+40", 220), ("+60", 255)]
SWR_TICKS = [("1", 0), ("1.5", 52), ("2", 89), ("3", 126), ("5", 236)]

# name, lower edge, upper edge, default frequency (Hz) - IARU Region 1
BANDS = [
    ("160m", 1_800_000, 2_000_000, 1_840_000),
    ("80m", 3_500_000, 4_000_000, 3_573_000),
    ("60m", 5_250_000, 5_450_000, 5_357_000),
    ("40m", 7_000_000, 7_300_000, 7_074_000),
    ("30m", 10_100_000, 10_150_000, 10_136_000),
    ("20m", 14_000_000, 14_350_000, 14_074_000),
    ("17m", 18_068_000, 18_168_000, 18_100_000),
    ("15m", 21_000_000, 21_450_000, 21_074_000),
    ("12m", 24_890_000, 24_990_000, 24_915_000),
    ("10m", 28_000_000, 29_700_000, 28_074_000),
    ("6m", 50_000_000, 54_000_000, 50_313_000),
    ("4m", 70_000_000, 70_500_000, 70_200_000),
]
BAND_MAX_W = {"4m": 50}          # 100 W elsewhere

STEPS = [("10 Hz", 10), ("100 Hz", 100), ("500 Hz", 500), ("1 kHz", 1000), ("2.5 kHz", 2500),
         ("5 kHz", 5000), ("9 kHz", 9000), ("10 kHz", 10000), ("12.5 kHz", 12500),
         ("100 kHz", 100000), ("1 MHz", 1000000)]

CTCSS = [67.0, 69.3, 71.9, 74.4, 77.0, 79.7, 82.5, 85.4, 88.5, 91.5, 94.8, 97.4, 100.0,
         103.5, 107.2, 110.9, 114.8, 118.8, 123.0, 127.3, 131.8, 136.5, 141.3, 146.2, 151.4,
         156.7, 159.8, 162.2, 165.5, 167.9, 171.3, 173.8, 177.3, 179.9, 183.5, 186.2, 189.9,
         192.8, 196.6, 199.5, 203.5, 206.5, 210.7, 218.1, 225.7, 229.1, 233.6, 241.8, 250.3, 254.1]

# CAT levels: (label, command prefix, digits (None = IF shift format), min, max, display format)
LEVELS = [
    ("AF gain", "AG0", 3, 0, 255, "pct"), ("RF gain", "RG0", 3, 0, 255, "pct"),
    ("Squelch", "SQ0", 3, 0, 100, "pct100"), ("NR level", "RL0", 2, 1, 15, "num"),
    ("NB level", "NL0", 3, 0, 10, "num"), ("IF shift", "IS0", None, -1200, 1200, "shift"),
    ("CW pitch", "KP", 2, 0, 75, "pitch"),
    ("RF power", "PC", 3, 5, 100, "watts"), ("Mic gain", "MG", 3, 0, 100, "pct100"),
    ("Proc level", "PL", 3, 0, 100, "pct100"), ("Key speed", "KS", 3, 4, 60, "wpm"),
    ("Monitor", "ML1", 3, 0, 100, "pct100"), ("VOX gain", "VG", 3, 0, 100, "pct100"),
]
LEVEL_DEF = {p: (lab, p, dg, lo, hi, fmt) for lab, p, dg, lo, hi, fmt in LEVELS}
BAR_LEVELS = [("AG0", "AF"), ("PC", "PWR"), ("SQ0", "SQL")]

# On/off (or multi-state) functions:
#   key: (label, CAT prefix, values, per-value texts or None, answer digits)
TOGGLES = {
    "amp":   ("IPO",   "PA0", (0, 1, 2), ("IPO", "AMP1", "AMP2"), 1),
    "att":   ("ATT",   "RA0", (0, 1, 2, 3), ("ATT", "ATT 6", "ATT 12", "ATT 18"), 1),
    "agc":   ("AGC",   "GT0", (1, 2, 3, 4), ("AGC-F", "AGC-M", "AGC-S", "AGC-A"), 1),
    "nb":    ("NB",    "NB0", (0, 1), None, 1),
    "nr":    ("NR",    "NR0", (0, 1), None, 1),
    "anf":   ("DNF",   "BC0", (0, 1), None, 1),
    "nar":   ("NAR",   "NA0", (0, 1), None, 1),
    "proc":  ("PROC",  "PR0", (1, 2), None, 1),
    "vox":   ("VOX",   "VX", (0, 1), None, 1),
    "mon":   ("MON",   "ML0", (0, 1), None, 3),
    "bkin":  ("BK-IN", "BI", (0, 1), None, 1),
    "keyer": ("KEYER", "KR", (0, 1), None, 1),
    "lock":  ("LOCK",  "LK", (0, 1), None, 1),
    "atu":   ("ATU",   "AC00", (0, 1), None, 1),   # internal antenna tuner; read with AC; (see read_toggle)
    "rit":   ("RIT",   "RT", (0, 1), None, 1),
    "xit":   ("XIT",   "XT", (0, 1), None, 1),
    "split": ("SPLIT", "ST", (0, 1), None, 1),
    "ctcss": ("CTCSS", "CT0", (0, 2, 1), ("CTCSS", "TONE", "TSQL"), 1),
}
ALWAYS_LIT = {"agc"}

SHIFT_TEXT = {1: "+RPT", 2: "-RPT"}
VFO_MODE_TEXT = {"0": "VFO-A", "1": "MEM", "2": "M.TUNE", "3": "QMB", "4": "QMB", "5": "PMS"}

DEFAULT_MACROS = ["CQ CQ CQ DE {MYCALL} {MYCALL} K", "{CALL} DE {MYCALL}", "TU 5NN",
                  "QRZ? DE {MYCALL}", "RR TNX 73", "{MYCALL}"]
CW_SLOT = 5                       # rig keyer memory used for text sent from this program

MEM_EXTRA_KEYS = ("ch", "dup", "tone_mode", "tone", "tsql", "offset", "src")

TABS = ["TUNE", "LEVELS", "VFO", "FUNC", "CW", "MEMORY", "SCAN", "LOG"]

SCALE = 1.0
F = {}


def px(v):
    return int(round(v * SCALE))


# -----------------------------------------------------------------
# 3. PURE HELPERS (no GUI / serial - easy to test)
# -----------------------------------------------------------------
DEFAULT_CONFIG = {
    "port": AUTO_PORT, "baud": 38400, "geometry": "",
    "topmost": False, "step_hz": 1000, "memories": [], "band_last": {},
    "mycall": "", "tx_timeout": 180, "cw_macros": list(DEFAULT_MACROS), "tab": "TUNE",
    "freq_size": "Medium",
    "web_on": False, "web_port": 8075, "web_password": "", "web_secret": "",
    "web_https_port": 8076, "web_https_name": "",
    "audio_in": "Auto (USB Audio CODEC)", "audio_out": "Auto (USB Audio CODEC)", "audio_sql": True,
}
# share of the screen width used by the frequency readout, and the largest font size allowed
FREQ_SIZES = {"Small": (0.58, 60), "Medium": (0.70, 72), "Large": (0.82, 90)}


def load_config():
    cfg = {k: (v.copy() if isinstance(v, (dict, list)) else v) for k, v in DEFAULT_CONFIG.items()}
    try:
        with open(CONFIG_PATH, "r") as f:
            data = json.load(f)
    except Exception:
        return cfg
    if not isinstance(data, dict):
        return cfg

    def get(key, conv):
        try:
            if key in data:
                cfg[key] = conv(data[key])
        except Exception:
            pass
    get("port", str)
    get("baud", int)
    get("geometry", str)
    get("topmost", bool)
    get("step_hz", int)
    get("mycall", lambda v: str(v).upper())
    get("tx_timeout", lambda v: max(10, min(600, int(v))))
    get("tab", lambda v: v if v in TABS else "TUNE")
    get("freq_size", lambda v: v if v in FREQ_SIZES else "Medium")
    get("web_on", bool)
    get("web_port", lambda v: max(1024, min(65535, int(v))))
    get("web_https_port", lambda v: max(1024, min(65535, int(v))))
    for k in ("web_password", "web_secret", "web_https_name", "audio_in", "audio_out"):
        get(k, str)
    get("audio_sql", bool)
    macros = data.get("cw_macros")
    if isinstance(macros, list) and macros:
        cfg["cw_macros"] = ([str(m) for m in macros] + DEFAULT_MACROS)[:len(DEFAULT_MACROS)]
    mems = []
    for m in data.get("memories", []) if isinstance(data.get("memories"), list) else []:
        try:
            d = {"name": str(m["name"]), "hz": int(m["hz"]), "mode": m.get("mode")}
            for k in MEM_EXTRA_KEYS:
                if m.get(k) is not None:
                    d[k] = m[k]
            mems.append(d)
        except Exception:
            pass
    cfg["memories"] = mems
    bl = data.get("band_last", {})
    if isinstance(bl, dict):
        try:
            cfg["band_last"] = {str(k): int(v) for k, v in bl.items()}
        except (TypeError, ValueError):
            pass
    return cfg


def save_config(cfg):
    try:
        with open(CONFIG_PATH, "w") as f:
            json.dump(cfg, f, indent=1)
    except Exception:
        pass


def load_qso_log():
    try:
        with open(QSO_PATH, "r") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def save_qso_log(log):
    try:
        with open(QSO_PATH, "w") as f:
            json.dump(log, f, indent=1)
    except Exception:
        pass


def band_of(hz):
    for name, lo, hi, _ in BANDS:
        if lo <= hz <= hi:
            return name
    return ""


def hz_to_mhz(hz):
    return f"{hz / 1_000_000:.5f}"


def interp(cal, raw):
    """Piece-wise linear calibration lookup."""
    if raw <= cal[0][0]:
        return cal[0][1]
    for (r0, v0), (r1, v1) in zip(cal, cal[1:]):
        if raw <= r1:
            return v0 + (v1 - v0) * (raw - r0) / (r1 - r0)
    return cal[-1][1]


def inv_interp(cal, value):
    """Raw meter value for a calibrated value (for drawing scale ticks)."""
    for (r0, v0), (r1, v1) in zip(cal, cal[1:]):
        if v0 <= value <= v1:
            return r0 + (r1 - r0) * (value - v0) / (v1 - v0) if v1 != v0 else r0
    return cal[-1][0]


PWR_TICKS = [(lab, inv_interp(PO_CAL, w)) for lab, w in (("0", 0), ("10", 10), ("25", 25), ("50", 50),
                                                          ("100W", 100))]


def s_label(raw):
    db = interp(STR_CAL, raw)
    if db <= 0.5:
        return f"S{max(0, min(9, int(round(9 + db / 6))))}"
    return f"S9+{int(round(db))}dB"


def watts_from_raw(raw):
    return interp(PO_CAL, raw)


def swr_from_raw(raw):
    """Returns (text, severity 0-2)."""
    v = interp(SWR_CAL, raw)
    if v >= 5.0:
        return "SWR >5", 2
    return f"SWR {v:.1f}", (0 if v < 2.0 else 1 if v < 3.0 else 2)


def alc_pct(raw):
    return int(round(raw / 255 * 100))


def comp_db(raw):
    return raw / 255 * 30          # approximate


def id_amps(raw):
    return raw / 255 * 25          # approximate


def level_text(prefix, a):
    if a is None or prefix not in LEVEL_DEF:
        return "--"
    fmt = LEVEL_DEF[prefix][5]
    if fmt == "pct":
        return f"{int(round(a / 255 * 100))}%"
    if fmt == "pct100":
        return f"{a}%"
    if fmt == "shift":
        return f"{a:+d}Hz"
    if fmt == "pitch":
        return f"{300 + 10 * a}Hz"
    if fmt == "watts":
        return f"{a}W"
    if fmt == "wpm":
        return f"{a}wpm"
    return str(a)


def level_set_cmd(prefix, a):
    _, _, digits, lo, hi, _ = LEVEL_DEF[prefix]
    a = max(lo, min(hi, int(a)))
    if digits is None:                                     # IF shift: IS00+0000; in 20 Hz steps
        a = int(round(a / 20)) * 20
        return f"IS00{'+' if a >= 0 else '-'}{abs(a):04d};"
    return f"{prefix}{a:0{digits}d};"


def level_parse(prefix, ans):
    """Parse a level answer (without ';'). Returns the value or None."""
    if not ans or not ans.startswith(prefix[:2]):
        return None
    try:
        if LEVEL_DEF[prefix][2] is None:                   # IS0 -> "IS00+0120"
            return int(ans[4:9])
        return int(ans[len(prefix):])
    except (ValueError, IndexError):
        return None


def parse_info(ans):
    """IF / OI / MR / MT answer -> dict (shared layout). None if malformed."""
    if not ans or len(ans) < 27 or ans[:2] not in ("IF", "OI", "MR", "MT"):
        return None
    try:
        hz = int(ans[5:14])
        clar = int(ans[14:19])
    except ValueError:
        return None
    return {"ch": ans[2:5], "hz": hz, "clar": clar, "rx_clar": ans[19] == "1", "tx_clar": ans[20] == "1",
            "mode": MODES.get(ans[21]), "vfo": ans[22], "ctcss": int(ans[23]) if ans[23].isdigit() else 0,
            "shift": int(ans[26]) if ans[26].isdigit() else 0,
            "tag": ans[28:40].strip() if ans[:2] == "MT" and len(ans) > 28 else ""}


def mem_info(m):
    parts = []
    if m.get("dup") in SHIFT_TEXT:
        parts.append(SHIFT_TEXT[m["dup"]])
    if m.get("tone_mode") == 2:
        parts.append("TONE" + (f" {m['tone']:.1f}" if m.get("tone") else ""))
    elif m.get("tone_mode") == 1:
        parts.append("TSQL" + (f" {m['tone']:.1f}" if m.get("tone") else ""))
    return "  ".join(parts)


def cw_clean(text):
    allowed = set("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789/?.,-=+@:'\"() ")
    return "".join(ch for ch in text.upper() if ch in allowed)


def expand_macro(text, mycall, call):
    return text.replace("{MYCALL}", mycall or "").replace("{CALL}", call or "")


def adif_field(name, value):
    value = str(value).encode("ascii", "replace").decode("ascii")
    return f"<{name}:{len(value)}>{value}"


def adif_record(q, mycall=""):
    mode, sub = ADIF_MODES.get(q.get("mode", ""), (q.get("mode", ""), None))
    mhz = f"{q['hz'] / 1_000_000:.6f}"
    fields = [adif_field("QSO_DATE", q["date"]), adif_field("TIME_ON", q["time"]),
              adif_field("CALL", q["call"]), adif_field("FREQ", mhz),
              adif_field("MODE", mode)]
    if sub:
        fields.append(adif_field("SUBMODE", sub))
    if band_of(q["hz"]):
        fields.append(adif_field("BAND", band_of(q["hz"])))
    for key, tag in (("rst_s", "RST_SENT"), ("rst_r", "RST_RCVD"), ("name", "NAME"),
                     ("grid", "GRIDSQUARE"), ("notes", "COMMENT")):
        if q.get(key):
            fields.append(adif_field(tag, q[key]))
    if mycall:
        fields.append(adif_field("STATION_CALLSIGN", mycall))
    return " ".join(fields) + " <EOR>\n"


def adif_document(log, mycall=""):
    head = ("FTDX10 Monitor export\n" + adif_field("ADIF_VER", "3.1.4") + "\n"
            + adif_field("PROGRAMID", "FTDX10 Monitor") + "\n"
            + adif_field("PROGRAMVERSION", APP_VERSION) + "\n<EOH>\n\n")
    return head + "".join(adif_record(q, mycall) for q in log)


def lerp_color(a, b, t):
    t = max(0.0, min(1.0, t))
    ca = [int(a[i:i + 2], 16) for i in (1, 3, 5)]
    cb = [int(b[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{int(round(x + (y - x) * t)):02x}" for x, y in zip(ca, cb))


# -----------------------------------------------------------------
# 4. CUSTOM WIDGETS
# -----------------------------------------------------------------
def pick_family(candidates):
    have = {f.lower() for f in tkfont.families()}
    for c in candidates:
        if c.lower() in have:
            return c
    return candidates[-1]


def init_fonts(root):
    global SCALE
    try:
        SCALE = max(1.0, min(3.0, root.winfo_fpixels("1i") / 96.0))
    except Exception:
        SCALE = 1.0
    ui = pick_family(["Segoe UI", "Inter", "Helvetica Neue", "DejaVu Sans", "Helvetica"])
    mono = pick_family(["Cascadia Mono", "Consolas", "DejaVu Sans Mono", "Menlo", "Courier New", "Courier"])
    # The radio's display uses a clean sans-serif with tabular figures for the frequency
    lcd = pick_family(["Segoe UI Semibold", "Segoe UI", "Bahnschrift", "Inter", "Helvetica Neue",
                       "DejaVu Sans", "Helvetica"])
    lcd_w = "normal" if "semibold" in lcd.lower() else "bold"
    F.update(
        ui=tkfont.Font(family=ui, size=9),
        ui_b=tkfont.Font(family=ui, size=9, weight="bold"),
        small=tkfont.Font(family=ui, size=8),
        small_b=tkfont.Font(family=ui, size=7, weight="bold"),
        btn=tkfont.Font(family=ui, size=8, weight="bold"),
        title=tkfont.Font(family=ui, size=12, weight="bold"),
        big=tkfont.Font(family=ui, size=15, weight="bold"),
        mono=tkfont.Font(family=mono, size=10),
        mono_b=tkfont.Font(family=mono, size=10, weight="bold"),
        mono_s=tkfont.Font(family=mono, size=8, weight="bold"),
        cw=tkfont.Font(family=mono, size=14, weight="bold"),
        freq=tkfont.Font(family=lcd, size=40, weight=lcd_w),
        freq_s=tkfont.Font(family=lcd, size=24, weight=lcd_w),
        sub=tkfont.Font(family=lcd, size=19, weight=lcd_w),
        sub_s=tkfont.Font(family=lcd, size=12, weight=lcd_w),
        lcd=tkfont.Font(family=ui, size=8, weight="bold"),
        lcd_s=tkfont.Font(family=ui, size=7, weight="bold"),
        model=tkfont.Font(family=ui, size=13, weight="bold"),
    )


def rrect(c, x1, y1, x2, y2, r, **kw):
    r = max(1, min(r, (x2 - x1) / 2, (y2 - y1) / 2))
    pts = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2,
           x2 - r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
    return c.create_polygon(pts, smooth=True, **kw)


class RoundButton(tk.Canvas):
    """Flat rounded button / status chip drawn on a canvas. Can be a lit toggle."""
    TONES = {"accent": (ACCENT, ACCENT_DIM), "green": (GREEN, GREEN_DIM),
             "amber": (AMBER, AMBER_DIM), "red": (RED, RED_DIM)}

    def __init__(self, parent, text, command=None, width=64, height=28, tone="accent",
                 font=None, radius=6, solid=False, style="key"):
        bg = parent.cget("bg")
        super().__init__(parent, width=px(width), height=px(height), bg=bg,
                         highlightthickness=0, bd=0, cursor="hand2" if command else "")
        self.text = text
        self.command = command
        self.tone = tone
        self.font = font or F["btn"]
        self.radius = px(radius)
        self.solid = solid
        self.style = style          # "key" = rubber key on the case, "soft" = touch-screen soft key
        self.active = False
        self.dim_active = False
        self.hover = False
        self.down = False
        self.bind("<Configure>", lambda e: self.redraw())
        if command:
            self.bind("<Enter>", lambda e: self._set(hover=True))
            self.bind("<Leave>", lambda e: self._set(hover=False, down=False))
            self.bind("<ButtonPress-1>", lambda e: self._set(down=True))
            self.bind("<ButtonRelease-1>", self._release)
        self.redraw()

    def _set(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)
        self.redraw()

    def _release(self, e):
        was = self.down
        self._set(down=False)
        if was and 0 <= e.x <= self.winfo_width() and 0 <= e.y <= self.winfo_height():
            self.command()

    def set_active(self, on, text=None, tone=None, dim=False):
        on = bool(on)
        if (on, text or self.text, tone or self.tone, dim) == (self.active, self.text, self.tone, self.dim_active):
            return
        self.active, self.dim_active = on, dim
        if text is not None:
            self.text = text
        if tone is not None:
            self.tone = tone
        self.redraw()

    def set_text(self, text):
        if text != self.text:
            self.text = text
            self.redraw()

    def redraw(self):
        self.delete("all")
        w = self.winfo_width()
        h = self.winfo_height()
        if w < 4:
            w, h = int(self["width"]), int(self["height"])
        hi, lo = self.TONES.get(self.tone, self.TONES["accent"])
        if self.style == "soft":
            self._draw_soft(w, h, hi)
            return
        # Rubber key: drop shadow, body, top highlight, and an LED strip when switched on
        lit_solid = self.active and self.solid and not self.dim_active
        if lit_solid:
            fill, tc = hi, "#111111"
        else:
            fill = BTN_DOWN if self.down else (BTN_HOVER if self.hover else BTN)
            tc = TEXT if self.command else DIM
        off = 1 if self.down else 0
        rrect(self, 1, 2, w - 2, h - 1, self.radius, fill=KEY_SHADOW, outline="")
        rrect(self, 1, 1 + off, w - 2, h - 3 + off, self.radius, fill=fill,
              outline=lerp_color(fill, "#000000", 0.35))
        if not self.down:
            r = self.radius
            self.create_line(1 + r, 2, w - 2 - r, 2, fill=lerp_color(fill, "#ffffff", 0.14))
        if self.active and not self.solid:
            led = lo if self.dim_active else hi
            lw = max(px(14), min(px(26), w * 0.35))
            self.create_line(w / 2 - lw / 2, px(4) + off, w / 2 + lw / 2, px(4) + off, fill=led,
                             width=px(2), capstyle="round")
            tc = TEXT if not self.dim_active else MUTED
        self.create_text(w / 2, h / 2 + off + (px(1) if self.active and not self.solid else 0),
                         text=self.text, fill=tc, font=self.font)

    def _draw_soft(self, w, h, hi):
        """Touch-screen soft key, like the menu keys along the bottom of the radio's display."""
        if self.active:
            top, bot, outline, tc = "#3b78e0", SOFTKEY_ON, "#7fb0ff", "#ffffff"
        else:
            top = SOFTKEY_HI if self.hover else lerp_color(SOFTKEY, "#ffffff", 0.06)
            bot, outline, tc = SOFTKEY, "#4d5563", LCD_TEXT
        rrect(self, 1, 1, w - 2, h - 2, self.radius, fill=bot, outline=outline)
        rrect(self, 2, 2, w - 3, h / 2, max(1, self.radius - 1), fill=top, outline="")
        self.create_text(w / 2, h / 2, text=self.text, fill=tc, font=self.font)


class LcdTag:
    """Indicator drawn on the display canvas (MAIN, mode, FIL, TX, BUSY ...). Same API as a chip."""

    def __init__(self, changed, text, tone="accent", solid=False, hide_off=True):
        self.changed = changed
        self.text = text
        self.tone = tone
        self.solid = solid
        self.hide_off = hide_off
        self.active = False
        self.dim_active = False

    def set_active(self, on, text=None, tone=None, dim=False):
        new = (bool(on), text if text is not None else self.text, tone or self.tone, dim)
        if new != (self.active, self.text, self.tone, self.dim_active):
            self.active, self.text, self.tone, self.dim_active = new
            self.changed()

    def set_text(self, text):
        self.set_active(self.active, text)


class LevelSlider(tk.Canvas):
    """Slim horizontal slider (0-255): click / drag / wheel. Optional centre detent."""

    def __init__(self, parent, command=None, maxval=255, center=False, color=ACCENT):
        super().__init__(parent, width=px(110), height=px(26), bg=parent.cget("bg"), highlightthickness=0,
                         cursor="hand2")
        self.maxval = maxval
        self.value = 0
        self.known = False
        self.command = command
        self.center = center
        self.color = color
        self.bg_col = parent.cget("bg")
        self.bind("<Configure>", lambda e: self.redraw())
        self.bind("<Button-1>", self._drag)
        self.bind("<B1-Motion>", self._drag)
        self.bind("<MouseWheel>", lambda e: self._nudge(3 if e.delta > 0 else -3))
        self.bind("<Button-4>", lambda e: self._nudge(3))
        self.bind("<Button-5>", lambda e: self._nudge(-3))
        if center:
            self.bind("<Double-Button-1>", lambda e: self._apply(128))

    def set(self, v):
        self.value = max(0, min(self.maxval, float(v)))
        self.known = True
        self.redraw()

    def get(self):
        return self.value

    def _apply(self, v):
        self.value = max(0, min(self.maxval, int(round(v))))
        self.known = True
        self.redraw()
        if self.command:
            self.command(self.value)

    def _drag(self, e):
        pad = px(10)
        w = max(self.winfo_width(), 2 * pad + 20)
        self._apply((e.x - pad) / (w - 2 * pad) * self.maxval)

    def _nudge(self, d):
        self._apply(self.value + d)

    LED_OFF = "#3a0b09"          # unlit red LED
    LED_ON = "#ff2b1c"           # fully lit
    LED_HOT = "#ffd0c4"          # the hot centre of a bright LED

    def brightness(self):
        """0..1: how brightly the LED knob glows. Higher value = brighter; centre sliders glow
        brighter the further they are from the centre."""
        frac = self.value / self.maxval if self.maxval else 0
        return abs(frac - 0.5) * 2 if self.center else frac

    def redraw(self):
        self.delete("all")
        pad = px(10)
        w = max(self.winfo_width(), 2 * pad + 20)
        h = self.winfo_height() if self.winfo_height() > 4 else px(26)
        cy = h / 2
        x = pad + (self.value / self.maxval) * (w - 2 * pad)
        bg = self.bg_col
        b = self.brightness() if self.known else 0.0
        r = px(9)
        if self.known and b > 0.05:                               # glow around a lit LED, under the groove
            for i in range(4, 0, -1):
                rr = r + px(i * 1.2)
                self.create_oval(x - rr, cy - rr, x + rr, cy + rr, outline="",
                                 fill=lerp_color(bg, self.LED_ON, b * 0.16 * (5 - i) / 4))
        # recessed square groove
        gh = px(3)
        self.create_rectangle(pad, cy - gh, w - pad, cy + gh, fill="#0e0f11", outline="#050506")
        self.create_line(pad, cy + gh + 1, w - pad, cy + gh + 1, fill="#3f434a")      # lower lip highlight
        # level fill inside the groove
        if self.known:
            x0 = pad + 0.5 * (w - 2 * pad) if self.center else pad
            self.create_rectangle(min(x, x0), cy - gh + 1, max(x, x0), cy + gh - 1, fill=self.color, outline="")
        # scale ticks under the groove
        for k in range(11):
            tx = pad + k * (w - 2 * pad) / 10
            tl = px(4) if k in (0, 5, 10) else px(2)
            self.create_line(tx, cy + gh + px(3), tx, cy + gh + px(3) + tl, fill="#5c616a")
        # red LED knob in a black bezel, glowing brighter as the value rises
        lit = 0.08 + 0.92 * b                                     # never quite dark once known
        self.create_oval(x - r + 1, cy - r + 2, x + r + 2, cy + r + 3, fill="#060708", outline="")   # shadow
        self.create_oval(x - r, cy - r, x + r, cy + r, fill="#141518", outline="#4a4f57")            # bezel
        lr = r - px(2.5)
        if not self.known:
            lens = "#3a3d42"
        else:
            lens = lerp_color(self.LED_OFF, self.LED_ON, lit)
        self.create_oval(x - lr, cy - lr, x + lr, cy + lr, fill=lens, outline="#050505")
        if self.known:                                            # brighter core, hotter as it rises
            for i, f in enumerate((0.72, 0.48, 0.26)):
                cr = lr * f
                col = lerp_color(lens, self.LED_HOT, b * (0.25 + 0.25 * i))
                self.create_oval(x - cr, cy - cr, x + cr, cy + cr, fill=col, outline="")
        hr = max(1.0, lr * 0.32)                                  # glass highlight
        hx, hy = x - lr * 0.38, cy - lr * 0.42
        self.create_oval(hx - hr, hy - hr * 0.7, hx + hr, hy + hr * 0.7, outline="",
                         fill=lerp_color(lens, "#ffffff", 0.45 if self.known else 0.25))


# -----------------------------------------------------------------
# 4b. PHONE / BROWSER ACCESS (built-in web page, no extra packages)
# -----------------------------------------------------------------
WEB_DEFAULT_PORT = 8075          # the IC9700 Monitor uses 8073 / 8074, so both can run together

# ---- Audio for the phone: radio RX audio out, phone microphone in (FTDX10 "USB Audio CODEC") ----
AUDIO_RATE = 16000          # sent to / from the phone as 8-bit mu-law, 128 kbit/s each way
AUDIO_BLOCK = 640           # samples per packet = 40 ms
AUDIO_AUTO = "Auto (USB Audio CODEC)"
SQL_LEVEL_KEY = "SQ0"           # this program's squelch level (level_vals key)
AUDIO_PREFER = ("ftdx", "ft-dx", "yaesu")           # name parts that mark this radio's sound devices
AUDIO_AVOID = ("ic9700", "ic-9700", "icom")         # ...and the other radio's (both say "USB Audio CODEC")
WS_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
_ULAW = []


def _ulaw_tables():
    if not _ULAW:
        def enc(s):
            sign = 0x80 if s < 0 else 0
            s = min(abs(s), 32635) + 0x84
            e, mask = 7, 0x4000
            while e > 0 and not s & mask:
                e -= 1
                mask >>= 1
            return ~(sign | (e << 4) | ((s >> (e + 3)) & 0x0F)) & 0xFF

        def dec(u):
            u = ~u & 0xFF
            s = ((((u & 0x0F) << 3) + 0x84) << ((u >> 4) & 7)) - 0x84
            return -s if u & 0x80 else s
        # encoder table is indexed by the sample read as unsigned 16-bit
        _ULAW[:] = [bytes(enc(v - 65536 if v >= 32768 else v) for v in range(65536)),
                    array("h", (dec(u) for u in range(256)))]
    return _ULAW


def ulaw_encode(pcm):
    enc = _ulaw_tables()[0]
    a = array("H")
    a.frombytes(pcm[:len(pcm) & ~1])
    return bytes(map(enc.__getitem__, a))


def ulaw_decode(data):
    dec = _ulaw_tables()[1]
    return array("h", map(dec.__getitem__, data)).tobytes()


def _decimate3(pcm):
    """48 kHz -> 16 kHz (average of each 3 samples)."""
    a = array("h")
    a.frombytes(pcm[:len(pcm) & ~1])
    return array("h", ((a[i] + a[i + 1] + a[i + 2]) // 3 for i in range(0, len(a) - 2, 3))).tobytes()


def _upsample3(pcm):
    """16 kHz -> 48 kHz (linear interpolation)."""
    a = array("h")
    a.frombytes(pcm[:len(pcm) & ~1])
    out = array("h")
    n = len(a)
    for i, s in enumerate(a):
        nx = a[i + 1] if i + 1 < n else s
        out.extend((s, (2 * s + nx) // 3, (s + 2 * nx) // 3))
    return out.tobytes()


class AudioEngine:
    """Radio receive audio (from the rig's USB codec) to phone listeners, and phone microphone audio
    to the rig's USB codec. Streams are only open while a phone is listening / talking."""

    def __init__(self, app):
        self.app = app
        self.lock = threading.Lock()          # listeners, transmit buffer
        self.slock = threading.RLock()        # opening / closing streams
        self.listeners = set()
        self.in_stream = None
        self.in_rate = AUDIO_RATE
        self.out_stream = None
        self.out_rate = AUDIO_RATE
        self.out_fail = 0.0
        self.txbuf = bytearray()
        self.tx_primed = False
        self.tx_last = 0.0
        self.tx_owner = None
        self.error = ""
        self.sql_open_time = 0.0
        self.in_name = ""

    @staticmethod
    def devices(kind):
        """(index, name) of input or output devices, MME only on Windows (it converts sample rates)."""
        try:
            apis = sd.query_hostapis()
            devs = sd.query_devices()
        except Exception:
            return []
        mme = next((i for i, h in enumerate(apis) if h["name"] == "MME"), None)
        key = "max_input_channels" if kind == "input" else "max_output_channels"
        return [(i, d["name"]) for i, d in enumerate(devs) if d[key] > 0 and (mme is None or d["hostapi"] == mme)]

    def _find(self, kind):
        wanted = self.app.config.get("audio_in" if kind == "input" else "audio_out", AUDIO_AUTO)
        for attempt in (0, 1):
            devs = self.devices(kind)
            if wanted and wanted != AUDIO_AUTO:
                for i, n in devs:
                    if n == wanted:
                        return i
            for i, n in devs:                         # devices renamed in Windows, e.g. "FTDX10 Speakers"
                if any(k in " ".join(n.lower().split()) for k in AUDIO_PREFER):
                    return i
            for i, n in devs:
                low = " ".join(n.lower().split())
                if "usb audio codec" in low and not any(k in low for k in AUDIO_AVOID):
                    return i
            if attempt == 0 and self.in_stream is None and self.out_stream is None:
                try:                    # look again, in case the radio was plugged in after start-up
                    sd._terminate()
                    sd._initialize()
                except Exception:
                    break
        what = "radio audio input" if kind == "input" else "radio audio output"
        raise RuntimeError(f"{what} not found ({wanted}) - is the FTDX10 USB cable connected?")

    def _open(self, kind, cb):
        dev = self._find(kind)
        try:
            name = sd.query_devices(dev)["name"]
        except Exception:
            name = f"device {dev}"
        if kind == "input":
            self.in_name = name
        cls = sd.RawInputStream if kind == "input" else sd.RawOutputStream
        last = None
        for rate in (AUDIO_RATE, 48000):
            try:
                s = cls(device=dev, samplerate=rate, channels=1, dtype="int16",
                        blocksize=AUDIO_BLOCK * rate // AUDIO_RATE, latency="low", callback=cb)
                s.start()
                return s, rate
            except Exception as e:
                last = e
        raise RuntimeError(str(last))

    @staticmethod
    def _close(s):
        if s is not None:
            try:
                s.stop()
                s.close()
            except Exception:
                pass

    # ---- receive
    def add_listener(self, l):
        with self.lock:
            self.listeners.add(l)
        with self.slock:
            if self.in_stream is None:
                try:
                    self.in_stream, self.in_rate = self._open("input", self._in_cb)
                    self.error = ""
                except Exception as e:
                    self.error = f"RX audio: {e}"
                    return self.error
        return ""

    def remove_listener(self, l):
        with self.lock:
            self.listeners.discard(l)
            empty = not self.listeners
            if self.tx_owner is l:
                self.tx_owner = None
        if empty:
            with self.slock:
                s, self.in_stream = self.in_stream, None
            self._close(s)

    def listener_count(self):
        with self.lock:
            return len(self.listeners)

    def status(self):
        """One line for the phone's AUDIO tab."""
        if self.in_stream is None:
            return ""
        txt = f"Listening on: {self.in_name} ({self.in_rate // 1000} kHz)"
        if self.squelched():
            txt += " \u00b7 MUTED: rig squelch is closed"
        return txt

    def squelched(self):
        """True when the phone audio should be muted because the rig's squelch is closed.
        The FTDX10 USB audio output ignores squelch unless its menu says otherwise."""
        app = self.app
        if not app.config.get("audio_sql", True) or not app.running or app.is_tx:
            return False
        if not app.sql_in_use():                          # squelch fully open (usual on HF): never mute
            return False
        lv = app.level_vals.get(SQL_LEVEL_KEY)
        if lv is not None and lv <= 0:                   # squelch turned fully down: always open
            return False
        is_open, when = app.sql_live
        now = time.time()
        if is_open is None or now - when > 2.0:          # no fresh squelch reading: don't mute
            return False
        if is_open:
            self.sql_open_time = now
            return False
        return now - self.sql_open_time > 0.25           # short hang so word endings aren't clipped

    def _in_cb(self, indata, frames, t, status):          # PortAudio thread
        if self.squelched():
            data = b"\xff" * (frames if self.in_rate == AUDIO_RATE else frames // 3)   # mu-law silence
        else:
            pcm = bytes(indata)
            if self.in_rate != AUDIO_RATE:
                pcm = _decimate3(pcm)
            data = ulaw_encode(pcm)
        with self.lock:
            ls = list(self.listeners)
        for l in ls:
            l.push(data)

    # ---- transmit
    def feed(self, owner, ulaw):
        """Microphone audio from a phone. Returns an error text, or ''."""
        now = time.time()
        with self.lock:
            if self.tx_owner is not owner and self.tx_owner is not None and now - self.tx_last < 1.0:
                return ""                              # another phone is talking
            self.tx_owner = owner
            self.txbuf += ulaw_decode(ulaw)
            if len(self.txbuf) > AUDIO_RATE:           # more than 0.5 s queued: drop the oldest part
                del self.txbuf[:len(self.txbuf) - AUDIO_RATE // 2]
            self.tx_last = now
        if self.out_stream is None:
            with self.slock:
                if self.out_stream is None:
                    if now - self.out_fail < 3:
                        return self.error
                    try:
                        self.out_stream, self.out_rate = self._open("output", self._out_cb)
                        self.error = ""
                    except Exception as e:
                        self.out_fail = now
                        self.error = f"TX audio: {e}"
                        return self.error
        return ""

    def _out_cb(self, outdata, frames, t, status):        # PortAudio thread
        need = (frames if self.out_rate == AUDIO_RATE else frames // 3) * 2
        with self.lock:
            if not self.tx_primed and len(self.txbuf) >= 2 * AUDIO_BLOCK * 2:      # 80 ms jitter buffer
                self.tx_primed = True
            if self.tx_primed and len(self.txbuf) >= need:
                chunk = bytes(self.txbuf[:need])
                del self.txbuf[:need]
            else:
                chunk = None
                self.tx_primed = False
        size = len(outdata)
        if chunk is None:
            outdata[:] = bytes(size)
            return
        if self.out_rate != AUDIO_RATE:
            chunk = _upsample3(chunk)
        outdata[:] = chunk[:size].ljust(size, b"\0")

    def idle_check(self):
        """Close the transmit stream when no phone audio has arrived for a few seconds (Tk thread)."""
        if self.out_stream is not None and time.time() - self.tx_last > 3:
            with self.slock:
                s, self.out_stream = self.out_stream, None
            self._close(s)
            with self.lock:
                self.txbuf.clear()
                self.tx_primed = False

    def restart(self):
        """Re-open streams after the device choice changed."""
        with self.slock:
            a, self.in_stream = self.in_stream, None
            b, self.out_stream = self.out_stream, None
        self._close(a)
        self._close(b)
        self.out_fail = 0.0
        if self.listener_count():
            with self.slock:
                try:
                    self.in_stream, self.in_rate = self._open("input", self._in_cb)
                    self.error = ""
                except Exception as e:
                    self.error = f"RX audio: {e}"

    def close(self):
        with self.lock:
            self.listeners.clear()
        self.restart()


MORSE = {
    ".-": "A", "-...": "B", "-.-.": "C", "-..": "D", ".": "E", "..-.": "F", "--.": "G", "....": "H",
    "..": "I", ".---": "J", "-.-": "K", ".-..": "L", "--": "M", "-.": "N", "---": "O", ".--.": "P",
    "--.-": "Q", ".-.": "R", "...": "S", "-": "T", "..-": "U", "...-": "V", ".--": "W", "-..-": "X",
    "-.--": "Y", "--..": "Z", "-----": "0", ".----": "1", "..---": "2", "...--": "3", "....-": "4",
    ".....": "5", "-....": "6", "--...": "7", "---..": "8", "----.": "9", ".-.-.-": ".", "--..--": ",",
    "..--..": "?", "-..-.": "/", "-...-": "=", "-....-": "-", ".--.-.": "@", "---...": ":",
    ".----.": "'", "-.-.--": "!", ".-.-.": "<AR>", "...-.-": "<SK>", "-.--.": "<KN>",
    ".-...": "<AS>", "-.-.-": "<KA>", "........": "<HH>", "...-.": "<SN>",
}
CWD_RATE = 4000                     # decoder works at 4 kHz (16 kHz radio audio averaged in fours)
CWD_BLOCK = 40                      # 10 ms per detection block
CWD_TONES = list(range(300, 1201, 50))
# sensitivity: (longest window in 10 ms blocks, window per dot, signal gate, key-down level, key-up level);
# the levels are multiples of the noise. Longer windows follow the measured speed.
CWD_SENS = {"Low": (1, 0.0, 8.0, 3.5, 2.5), "Normal": (1, 0.0, 6.0, 3.0, 2.0),
            "High": (2, 0.5, 4.5, 2.4, 1.7), "Max": (4, 0.7, 3.0, 1.8, 1.4),
            "Auto": (4, 0.6, 3.0, 1.8, 1.4)}     # Auto backs off to High's levels while it sees junk
CWD_SENS_NAMES = ["Auto", "Low", "Normal", "High", "Max"]


class CwDecoder:
    """CW decoder on the radio's USB receive audio. Finds the tone (or uses the rig's CW pitch),
    follows the signal level and the sending speed by itself, and turns dots and dashes into text."""

    def __init__(self, app):
        self.app = app
        self.q = deque(maxlen=100)                  # 4 s of 40 ms audio packets
        self.ev = threading.Event()
        self.active = False
        self.error = ""
        self.text = ""                              # everything decoded since CLEAR (last 4000 characters)
        self.on_text = None                         # callbacks, run on the Tk thread
        self.tone_mode = app.config.get("cwd_tone", "Auto")
        self.sens = app.config.get("cwd_sens", "Auto")
        self.coef = {f: 2.0 * math.cos(2 * math.pi * f / CWD_RATE) for f in CWD_TONES}
        self.reset()

    def reset(self):
        self.buf = []
        self.peak_by = {f: 0.0 for f in CWD_TONES}
        self.floor_by = {f: None for f in CWD_TONES}
        self.tone = 700
        self.floor = None
        self.peak = 0.0
        self.nblk = 0                               # blocks since start: the noise level settles first
        self.hist = []                              # the last few 10 ms blocks, for the longer windows
        self.win_n = 2
        self.junk_n = 0                             # Auto: recent junk (static crashes, unreadable letters)
        self.junk_at = -10000
        self.backoff = False
        self.key = False                            # signal present now
        self.pend = False                           # a mark has ended but a short dip could still join it
        self.mark = 0                               # length of the current mark, 10 ms blocks
        self.gap = 0                                # length of the current gap
        self.unit = 6.0                             # dot length in 10 ms blocks (20 WPM to start with)
        self.marks = []                             # recent mark lengths, for telling dots from dashes
        self.sym = ""
        self.spaced = True
        self.held = ""                              # a lone E / T waiting to see what follows
        self.level = 0.0
        self.snr_ok = False

    # ---- start / stop (Tk thread)
    def start(self):
        if self.active:
            return ""
        if self.app.audio is None:
            self.error = "Audio isn't set up on the PC: run  py -m pip install sounddevice  and restart."
            return self.error
        self.reset()
        self.active = True
        threading.Thread(target=self._worker, daemon=True).start()
        err = self.app.audio.add_listener(self)
        if err:
            self.stop()
            self.error = err
            return err
        self.error = ""
        return ""

    def stop(self):
        if not self.active:
            return
        self.active = False
        self.ev.set()
        if self.app.audio is not None:
            self.app.audio.remove_listener(self)

    def clear(self):
        self.text = ""
        self.sym = ""
        self.held = ""
        self.spaced = True

    def wpm(self):
        return int(round(120.0 / max(1.0, self.unit)))

    # ---- audio in (PortAudio thread): just queue it
    def push(self, ulaw):
        self.q.append(ulaw)
        self.ev.set()

    # ---- processing thread
    def _worker(self):
        while self.active:
            self.ev.wait(0.5)
            self.ev.clear()
            while self.q and self.active:
                try:
                    data = self.q.popleft()
                except IndexError:
                    break
                pcm = array("h", map(_ulaw_tables()[1].__getitem__, data))
                b = self.buf
                for i in range(0, len(pcm) - 3, 4):
                    b.append((pcm[i] + pcm[i + 1] + pcm[i + 2] + pcm[i + 3]) * 0.25)
                while len(b) >= CWD_BLOCK:
                    self._block(b[:CWD_BLOCK])
                    del b[:CWD_BLOCK]

    @staticmethod
    def _goertzel(x, coef):
        s1 = s2 = 0.0
        for v in x:
            s1, s2 = v + coef * s1 - s2, s1
        return s1 * s1 + s2 * s2 - coef * s1 * s2

    def _rig_pitch(self):
        v = self.app.level_vals.get("KP")
        return 300 + 10 * v if isinstance(v, int) else 700

    def sens_params(self):
        """(window in 10 ms blocks, signal gate, key-down level, key-up level) for the sensitivity setting.
        A longer window is a narrower filter, so weaker signals stand out of the noise, but it smears
        fast CW, so the window follows the measured speed (about half to two-thirds of a dot)."""
        cap, per_dot, gate, on_k, off_k = CWD_SENS.get(self.sens, CWD_SENS["Auto"])
        if self.sens not in CWD_SENS or self.sens == "Auto":
            self.backoff = self.nblk - self.junk_at < 2000 and self.junk_n >= 3   # junk in the last 20 s
            if self.backoff:
                gate, on_k, off_k = CWD_SENS["High"][2:]
        m = self.marks
        known = len(m) >= 6 and max(m) >= 2 * min(m)       # speed measured from dots and dashes
        want = max(1, min(cap if known else min(cap, 3), int(self.unit * per_dot + 0.5)))
        n = self.win_n
        if want != n and not self.key and not self.pend and self.gap > 3 * self.unit:
            self.win_n = n = want                         # only change between characters
        return min(n, cap), gate, on_k, off_k

    def _block(self, x):
        self.nblk += 1
        settle = self.nblk < 40
        rate = 0.1 if settle else 0.02
        quiet = not self.key and not self.pend               # between marks: update the noise average
        n, gate, on_k, off_k = self.sens_params()
        h = self.hist
        h.append(x)
        del h[:-4]
        win = [v for blk in h[-n:] for v in blk]
        k = len(win) // CWD_BLOCK
        if self.tone_mode == "Rig pitch":
            f = self._rig_pitch()
        else:                                              # Auto: the tone standing furthest above its noise
            sw = [v for blk in h[-min(k, 2):] for v in blk]
            ks = len(sw) // CWD_BLOCK
            for f in CWD_TONES:
                m = math.sqrt(max(0.0, self._goertzel(sw, self.coef[f]))) / ks
                pk, fl = self.peak_by[f], self.floor_by[f]
                if fl is None:
                    fl = m
                self.peak_by[f] = m if m > pk else pk + (m - pk) * 0.003
                if m < 3.0 * fl or settle:
                    self.floor_by[f] = fl + (m - fl) * rate
            score = {f: self.peak_by[f] / max(1.0, self.floor_by[f]) for f in CWD_TONES}
            best = max(score, key=score.get)
            if best != self.tone and score[best] > gate + 2.0 and score[best] > 1.3 * score[self.tone] \
                    and quiet and not settle:
                self.tone = best
                self.peak = self.peak_by[best]
                self.floor = self.floor_by[best] * math.sqrt(ks / k)
                self.sym = ""
            f = self.tone
        self.tone = f
        coef = self.coef.get(f) or 2.0 * math.cos(2 * math.pi * f / CWD_RATE)
        mag = math.sqrt(max(0.0, self._goertzel(win, coef))) / k
        # a keyed tone is narrow; static crashes and clicks are wide: compare with 300 Hz either side
        ref = 0.0
        for rf in ((f - 300, f + 300) if f >= 500 else (f + 300, f + 450)):
            ref += math.sqrt(max(0.0, self._goertzel(win, 2.0 * math.cos(2 * math.pi * rf / CWD_RATE)))) / k
        narrow = mag > 2.0 * (ref / 2)
        # signal level tracking
        if self.floor is None:
            self.floor = mag
        fl, pk = self.floor, self.peak
        if (quiet and mag < 3.0 * fl) or settle:
            self.floor = fl + (mag - fl) * rate
        self.peak = (pk + (mag - pk) * 0.5) if mag > pk else (pk + (mag - pk) * 0.003)
        fl = max(1.0, self.floor)
        span = self.peak - fl
        self.snr_ok = self.peak > gate * fl and self.peak > 150 and not settle
        self.level = 0.0 if span <= 0 else max(0.0, min(1.0, (mag - fl) / span))
        if not self.snr_ok or not narrow:
            down = False
        elif self.key:
            down = mag > max(fl + 0.35 * span, off_k * fl)
        else:
            down = mag > max(fl + 0.5 * span, on_k * fl)
        self._timing(down)

    def _timing(self, down):
        """Key state per 10 ms block. A dip shorter than a fraction of a dot doesn't end a mark."""
        u = self.unit
        if down:
            if self.key:
                self.mark += 1
            elif self.pend and self.gap < max(2.0, 0.35 * u):
                self.mark += self.gap + 1                  # a short dip inside a mark
                self.key, self.pend, self.gap = True, False, 0
            else:
                self.key, self.mark, self.gap = True, 1, 0
            return
        if self.key:
            self.key, self.pend, self.gap = False, True, 1
        else:
            self.gap += 1
        if self.pend and self.gap >= max(2.0, 0.35 * u):
            self.pend = False
            self._mark_done(self.mark)
        if not self.pend:
            g = self.gap
            if self.sym and g > 2.0 * self.unit:
                self._emit(MORSE.get(self.sym, "*"))
                self.sym = ""
            elif not self.sym and not self.spaced and g > 5.0 * self.unit:
                self._emit(" ")

    def _mark_done(self, n):
        u = self.unit
        if n < max(1.5, 0.3 * u):                          # a click or a burst of noise
            return
        m = self.marks
        m.append(n)
        del m[:-12]
        lo, hi = min(m), max(m)
        if len(m) >= 3 and hi >= 2.0 * lo:                 # dots and dashes both seen: split them
            c1, c2 = float(lo), float(hi)
            for _ in range(6):
                t = (c1 + c2) / 2
                a = [x for x in m if x < t]
                b = [x for x in m if x >= t]
                if not a or not b:
                    break
                c1, c2 = sum(a) / len(a), sum(b) / len(b)
            thr = (c1 + c2) / 2
            self.unit = u + ((c1 + c2 / 3.0) / 2 - u) * 0.3
        else:
            thr = 2.0 * u
            self.unit = u + ((n if n < thr else n / 3.0) - u) * 0.2
        self.unit = max(1.5, min(30.0, self.unit))
        self.sym = (self.sym + ("." if n < thr else "-"))[-9:]

    def _junk(self):
        self.junk_n = min(6, self.junk_n + 1 if self.nblk - self.junk_at < 2000 else 1)
        self.junk_at = self.nblk

    def _emit(self, ch):
        """Pass a character on. A lone E or T standing as a whole word is nearly always a static
        crash, so it is held back until the next character shows it is part of a word."""
        if self.held:
            if ch == " ":                                  # E / T alone: drop it
                self.held = ""
                self._junk()
                return
            ch, self.held = self.held + ch, ""
        elif self.spaced and ch in ("E", "T"):
            self.held = ch
            return
        if "*" in ch:
            self._junk()
        elif ch.strip() and self.nblk - self.junk_at > 1000:
            self.junk_n = max(0, self.junk_n - 1)          # good copy: forget old junk slowly
        self.spaced = ch.endswith(" ")
        self.text = (self.text + ch)[-4000:]
        cb = self.on_text
        if cb is not None:
            self.app.ui(cb, ch)


class WsConn:
    """Minimal WebSocket (RFC 6455) on an already upgraded, blocking socket."""

    def __init__(self, sock):
        self.sock = sock
        self.wlock = threading.Lock()
        self.tls = isinstance(sock, ssl.SSLSocket)
        self.rlock = self.wlock if self.tls else threading.Lock()    # OpenSSL: never read and write at once

    def send(self, opcode, payload=b""):
        n = len(payload)
        if n < 126:
            hdr = bytes((0x80 | opcode, n))
        elif n < 65536:
            hdr = bytes((0x80 | opcode, 126)) + n.to_bytes(2, "big")
        else:
            hdr = bytes((0x80 | opcode, 127)) + n.to_bytes(8, "big")
        with self.wlock:
            self.sock.sendall(hdr + payload)

    def send_json(self, obj):
        self.send(0x1, json.dumps(obj).encode("utf-8"))

    def _read(self, n, idle_ok=False):
        buf = bytearray()
        deadline = time.time() + 10
        while len(buf) < n:
            if self.tls and self.sock.pending():
                r = True
            else:
                r, _, _ = select.select([self.sock], [], [], 1.0)
            if not r:
                if idle_ok and not buf:
                    raise socket.timeout()
                if time.time() > deadline:
                    raise ConnectionError("stalled")
                continue
            with self.rlock:
                try:
                    chunk = self.sock.recv(n - len(buf))
                except ssl.SSLWantReadError:
                    continue
            if not chunk:
                raise ConnectionError("closed")
            buf += chunk
        return bytes(buf)

    def recv(self):
        """One message as (opcode, payload). Raises socket.timeout after ~1 s with nothing received."""
        msg_op, parts, total = None, [], 0
        while True:
            b1, b2 = self._read(2, idle_ok=msg_op is None)
            op, n = b1 & 0x0F, b2 & 0x7F
            if n == 126:
                n = int.from_bytes(self._read(2), "big")
            elif n == 127:
                n = int.from_bytes(self._read(8), "big")
            total += n
            if total > 1 << 16:
                raise ConnectionError("message too big")
            mask = self._read(4) if b2 & 0x80 else None
            data = self._read(n) if n else b""
            if mask and n:
                m = (mask * (n // 4 + 1))[:n]
                data = (int.from_bytes(data, "little") ^ int.from_bytes(m, "little")).to_bytes(n, "little")
            if op >= 0x8:
                return op, data
            if op:
                msg_op = op
            parts.append(data)
            if b1 & 0x80:
                return msg_op, b"".join(parts)


class AudioSession:
    """One phone's audio link. Receive audio is queued and sent by a small thread, dropping old
    packets rather than letting the delay grow when the network is slow."""

    def __init__(self, ws):
        self.ws = ws
        self.q = deque(maxlen=12)            # ~0.5 s
        self.ev = threading.Event()
        self.closed = False
        threading.Thread(target=self._sender, daemon=True).start()

    def push(self, data):
        self.q.append(data)
        self.ev.set()

    def _sender(self):
        while not self.closed:
            self.ev.wait(1.0)
            self.ev.clear()
            while not self.closed:
                try:
                    data = self.q.popleft()
                except IndexError:
                    break
                try:
                    self.ws.send(0x2, data)
                except OSError:
                    self.close()

    def close(self):
        self.closed = True
        self.ev.set()
        try:
            self.ws.sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass


def fetch_ts_cert(name=None):
    """Ask Tailscale for this PC's https certificate. Returns (True, dns name) or (False, reason).
    Reason "NOT_ENABLED" means HTTPS certificates are switched off for the tailnet."""
    code, out = run_tailscale(["status", "--json"], timeout=10)
    if code is None:
        return False, out
    try:
        st = json.loads(out)
    except ValueError:
        return False, "Tailscale status could not be read:\n" + out
    if st.get("BackendState") not in (None, "Running"):
        return False, f"Tailscale is not connected on this PC (state: {st.get('BackendState')}). Connect it and try again."
    me = (st.get("Self") or {}).get("DNSName", "").rstrip(".")
    domains = [d.rstrip(".") for d in (st.get("CertDomains") or [])]
    if not domains:
        return False, "NOT_ENABLED"
    name = name or (me if me in domains else domains[0])
    tmp_c, tmp_k = CERT_PATH + ".new", KEY_PATH + ".new"
    code, out = run_tailscale(["cert", "--cert-file", tmp_c, "--key-file", tmp_k, name], timeout=120)
    if code != 0 or not (os.path.exists(tmp_c) and os.path.exists(tmp_k)):
        low = (out or "").lower()
        if "not enabled" in low or "does not support" in low or "https" in low and "enable" in low:
            return False, "NOT_ENABLED"
        return False, out or "No reply from Tailscale."
    os.replace(tmp_c, CERT_PATH)
    os.replace(tmp_k, KEY_PATH)
    return True, name


def tailscale_exe():
    p = shutil.which("tailscale")
    if p:
        return p
    for c in (r"C:\Program Files\Tailscale\tailscale.exe", r"C:\Program Files (x86)\Tailscale\tailscale.exe"):
        if os.path.exists(c):
            return c
    return None


def run_tailscale(args, timeout=15):
    """Run the Tailscale CLI. Returns (exit code or None, output text)."""
    exe = tailscale_exe()
    if not exe:
        return None, "The Tailscale command-line tool was not found. Is Tailscale installed on this PC?"
    flags = 0x08000000 if sys.platform == "win32" else 0          # CREATE_NO_WINDOW
    try:
        p = subprocess.Popen([exe] + list(args), stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT, creationflags=flags)
    except OSError as e:
        return None, str(e)
    try:
        out, _ = p.communicate(timeout=timeout)
        return p.returncode, (out or b"").decode("utf-8", "replace").strip()
    except subprocess.TimeoutExpired:
        p.kill()
        out, _ = p.communicate()
        return None, (out or b"").decode("utf-8", "replace").strip()


WEB_PAGE = r"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="theme-color" content="#1b1c1f">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black">
<title>FTDX10</title>
<link rel="manifest" href="manifest.webmanifest">
<link rel="icon" type="image/png" href="icon-512.png">
<link rel="apple-touch-icon" href="icon-512.png">
<style>
:root{--bg:#1b1c1f;--panel:#232529;--text:#eef1f5;--muted:#9aa1ab;--dim:#5c616a;--accent:#5ab8ff;
--key:#33363b;--border:#393c42;--red:#ff4a3d;--green:#3ddc84;--orange:#ffa62b;--main:#1f5fc4;--lbl:#a8b3c3}
*{box-sizing:border-box;-webkit-tap-highlight-color:transparent}
html,body{margin:0;background:var(--bg);color:var(--text);font:15px/1.3 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
body{padding:env(safe-area-inset-top) env(safe-area-inset-right) env(safe-area-inset-bottom) env(safe-area-inset-left)}
#app{max-width:560px;margin:0 auto;padding:8px 10px 100px}
[hidden]{display:none!important}
header{display:flex;align-items:center;gap:8px;font-size:12px;color:var(--muted);padding:2px 2px 8px}
.led{width:9px;height:9px;border-radius:50%;background:var(--dim);flex:none}
.led.ok{background:var(--green)}.led.warn{background:var(--orange)}.led.off{background:var(--red)}
#status{flex:1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
#vd{color:var(--green);font-weight:700}#utc{font-variant-numeric:tabular-nums}
#net{background:#4d1512;color:#ffd7d3;border-radius:8px;padding:10px 12px;margin-bottom:8px;font-size:13px}
.lcd{background:#000;border:1px solid #2d3139;border-radius:10px;padding:8px 10px 10px}
.tags{display:flex;align-items:center;gap:5px;flex-wrap:wrap;min-height:22px}
.tag{font:700 11px system-ui,sans-serif;padding:2px 7px;border:1px solid var(--lbl);border-radius:3px;color:#fff;letter-spacing:.03em}
.tag.main{background:var(--main);border-color:var(--main)}
.tag.amber{color:var(--orange);border-color:var(--orange)}
.tag.solid.green{background:var(--green);border-color:var(--green);color:#000}
.tag.solid.red{background:var(--red);border-color:var(--red);animation:blink 1s steps(2) infinite}
.tag.subtag{background:#4a5160;border-color:#4a5160}
.sp{flex:1}.lbl{color:var(--lbl);font:700 12px system-ui,sans-serif}
.freq{font-weight:600;font-variant-numeric:tabular-nums;font-size:clamp(42px,15.5vw,76px);text-align:center;
line-height:1.05;padding:6px 0 4px;touch-action:none;user-select:none;-webkit-user-select:none;cursor:ew-resize}
.freq small{font-size:.6em}.freq.dim{color:#3b4250}
.ticks{position:relative;height:14px;margin:0 6px 1px 26px;font:700 10px system-ui,sans-serif;color:#fff}
.ticks span{position:absolute;transform:translateX(-50%);white-space:nowrap}.ticks span.r{color:var(--red)}
.meter{display:flex;align-items:center;gap:8px}
.mlabel{width:18px;font-weight:700}
.bar{flex:1;height:14px;background:#14171d;position:relative;margin-right:6px}
#mfill{position:absolute;inset:0;background:linear-gradient(90deg,#2f8bff 51%,#ff4a3d 51%);clip-path:inset(0 100% 0 0)}
#mfill.tx{background:#fff}
.bar::after{content:"";position:absolute;inset:0;background:repeating-linear-gradient(90deg,transparent 0 4px,#000 4px 6px)}
#mpeak{position:absolute;top:-2px;bottom:-2px;width:3px;background:var(--orange);z-index:1}
.mtext{display:flex;justify-content:space-between;gap:8px;font:700 13px ui-monospace,Menlo,Consolas,monospace;padding:5px 0 7px;color:#fff;min-height:28px}
#info{color:var(--lbl);text-align:right}
.sub{display:flex;align-items:center;gap:8px;border-top:1px solid #1e2530;padding-top:7px}
#subfreq{margin-left:auto;font-size:22px;font-weight:600;font-variant-numeric:tabular-nums;color:var(--lbl)}
nav{display:grid;grid-template-columns:repeat(5,1fr);gap:4px;margin:10px 0}
button{font:700 13px system-ui,sans-serif;color:var(--text);background:var(--key);border:1px solid #1f2124;border-radius:8px;
min-height:44px;padding:0 4px;box-shadow:0 2px 0 #0b0c0d,inset 0 1px 0 rgba(255,255,255,.08);touch-action:manipulation;
user-select:none;-webkit-user-select:none}
button:active{transform:translateY(1px);box-shadow:0 1px 0 #0b0c0d}
button.on{background:#244a6e;color:#fff;box-shadow:inset 0 -3px 0 var(--accent),0 2px 0 #0b0c0d}
nav button{background:#2a2e36;border-color:#4d5563;min-height:38px;font-size:12px}
nav button.on{background:#2d63c8;border-color:#7fb0ff;box-shadow:none}
.grid{display:grid;gap:6px}.g2{grid-template-columns:repeat(2,1fr)}.g3{grid-template-columns:repeat(3,1fr)}
.g4{grid-template-columns:repeat(4,1fr)}.g5{grid-template-columns:repeat(5,1fr)}
.page{display:none;background:var(--panel);border:1px solid var(--border);border-radius:10px;padding:10px}.page.on{display:block}
h3{font:700 11px system-ui,sans-serif;letter-spacing:.08em;color:var(--muted);margin:14px 2px 6px;text-transform:uppercase}
h3:first-child{margin-top:2px}
.row{display:flex;gap:6px;align-items:center}
.big{font-size:24px;flex:1;min-height:58px}
select,input[type=text]{background:#101113;color:var(--text);border:1px solid var(--border);border-radius:8px;min-height:44px;
font:600 16px system-ui,sans-serif;padding:0 10px;min-width:0}
#step{flex:1.1;text-align:center}#fin{flex:1;font-variant-numeric:tabular-nums}
.unit{color:var(--muted)}button.go{background:#1e5a36;min-width:64px}
label.sel{display:flex;align-items:center;gap:8px}label.sel span{color:var(--muted);font:700 12px system-ui,sans-serif;width:38px}
label.sel select{flex:1}
.rit button{flex:1}#ritv{flex:1.4;text-align:center;font:700 14px ui-monospace,Menlo,monospace;color:var(--accent)}
.lv{display:grid;grid-template-columns:78px 1fr 58px;align-items:center;gap:8px;min-height:42px}
.lv span{color:var(--muted);font-size:13px}.lv b{text-align:right;font:700 13px ui-monospace,Menlo,monospace}
input[type=range]{width:100%;accent-color:var(--accent);height:32px;margin:0}
.mem{display:flex;width:100%;gap:10px;align-items:center;text-align:left;margin-bottom:6px;padding:8px 10px;min-height:52px}
.mem .mn{flex:1;min-width:0}.mem .mn div{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.mem .mi{color:var(--muted);font-weight:500;font-size:12px}
.mem .mf{font:700 15px ui-monospace,Menlo,monospace;color:var(--accent)}
.hint{color:var(--muted);font-size:13px;margin:6px 2px}
.cwdt{min-height:64px;max-height:150px;overflow-y:auto;background:#000;color:#fff;font:700 17px ui-monospace,Menlo,monospace;padding:8px 10px;border-radius:8px;margin-top:6px;white-space:pre-wrap;word-break:break-word;border:1px solid var(--border)}
.cwdt:empty:before{content:'Decoded CW appears here';color:var(--dim);font-weight:500;font-size:13px}
.foot{color:var(--dim);font-size:11px;text-align:center;margin-top:14px}
.offline .page button,.offline .page select,.offline .page input{opacity:.45}
#dock{position:fixed;left:0;right:0;bottom:0;z-index:20;background:rgba(21,22,24,.97);border-top:1px solid var(--border);
padding:8px 10px calc(8px + env(safe-area-inset-bottom))}
#dock .in{max-width:560px;margin:0 auto;display:grid;grid-template-columns:1fr 2.2fr;gap:8px}
#dock button{min-height:58px;font-size:14px}
#abtn.on{background:#1e5a36;box-shadow:inset 0 -3px 0 var(--green),0 2px 0 #0b0c0d}
#ptt{background:#4a2020;font-size:15px;letter-spacing:.04em;touch-action:none}
#ptt.tx{background:var(--red);color:#fff;box-shadow:0 0 0 3px rgba(255,74,61,.35)}
#ptt.rig{background:#7a4a10;color:#fff}
.mbar{height:10px;background:#14171d;border-radius:3px;overflow:hidden}.mbar div{height:100%;width:0;background:var(--green)}
.chk{display:flex;align-items:center;gap:10px;min-height:44px;color:var(--text);font-size:14px}
.chk input{width:22px;height:22px;flex:none;accent-color:var(--accent)}
.warn{color:var(--orange);font-size:13px;margin:6px 2px}
.instbtn{display:block;width:100%;margin-top:14px;background:#1f5fc4;color:#fff;border-color:#2d63c8}
.pwr{min-height:30px;padding:0 10px;font-size:12px;border-radius:6px;box-shadow:none;background:#4a2020;color:#ffd7d3;flex:none}
.pwr.on{background:#1e5a36;color:#fff;box-shadow:inset 0 -3px 0 var(--green)}
.afnote{margin:-2px 2px 10px 86px;font-size:12px;color:var(--muted)}
.afnote a{color:#7fb6ff}
.hbtn{min-height:30px;padding:0 10px;font-size:12px;background:#1f5fc4;border-color:#2d63c8;color:#fff;border-radius:6px;box-shadow:none}
.ov{position:fixed;inset:0;background:rgba(0,0,0,.6);z-index:40;display:flex;align-items:center;justify-content:center;padding:16px}
.ovbox{background:var(--panel);border:1px solid var(--border);border-radius:12px;padding:16px;max-width:420px;width:100%}
.ovbox h3{margin:0 0 10px;font-size:13px}.ovbox p{margin:0 0 10px;font-size:15px;line-height:1.45}
.ovbox button{width:100%;margin-top:6px}
.golink{display:flex;align-items:center;justify-content:center;min-height:48px;margin:8px 0;border-radius:8px;
background:#1e5a36;color:#fff;font-weight:800;text-decoration:none}
#toast{position:fixed;left:50%;bottom:80px;transform:translateX(-50%);background:#2d63c8;color:#fff;padding:8px 14px;border-radius:8px;
font-size:13px;opacity:0;transition:opacity .2s;pointer-events:none;z-index:30;white-space:nowrap}
#toast.show{opacity:1}
@keyframes blink{50%{opacity:.35}}
</style></head>
<body>
<div id="app">
<header><button id="pwr" class="pwr">&#9211; --</button><span id="led" class="led"></span><span id="status">Connecting&hellip;</span><span id="vd"></span><span id="utc"></span><button id="insttop" class="hbtn" hidden>&#11015; APP</button></header>
<div id="net" hidden>Can't reach the PC. Check that FTDX10 Monitor is running and that Tailscale is connected on both the PC and this phone.</div>
<section class="lcd">
 <div class="tags"><span id="vfo" class="tag main">VFO-A</span><span id="mode" class="tag">--</span><span id="fil" class="tag" hidden>NAR</span>
 <span id="dup" class="tag amber" hidden></span><span id="sat" class="tag" hidden>RIT</span><span id="scan" class="tag amber" hidden>SCAN</span>
 <span id="bandlbl" class="lbl"></span><span class="sp"></span>
 <span id="busy" class="tag solid green" hidden>BUSY</span><span id="txb" class="tag solid red" hidden>TX</span></div>
 <div id="freq" class="freq dim">---.---<small>.--</small></div>
 <div id="ticks" class="ticks"></div>
 <div class="meter"><span id="mlab" class="mlabel">S</span><div class="bar"><div id="mfill"></div><div id="mpeak" hidden></div></div></div>
 <div class="mtext"><span id="mtext"></span><span id="info"></span></div>
 <div class="sub"><span class="tag subtag">VFO-B</span><span id="submode" class="lbl"></span><span id="subfreq">---.---</span></div>
</section>
<nav><button id="tTUNE">TUNE</button><button id="tFUNC">FUNC</button><button id="tLEVELS">LEVELS</button><button id="tMEM">MEMORY</button><button id="tAUDIO">AUDIO</button></nav>
<section id="pTUNE" class="page">
 <div class="row"><button id="dn" class="big" aria-label="Tune down">&#9664;</button><select id="step" aria-label="Tuning step"></select>
 <button id="up" class="big" aria-label="Tune up">&#9654;</button></div>
 <h3>Band</h3><div id="bands" class="grid g4"></div>
 <h3>Frequency</h3><div class="row"><input id="fin" type="text" inputmode="decimal" placeholder="14.074" autocomplete="off">
 <span class="unit">MHz</span><button id="setf" class="go">SET</button></div>
 <h3>Mode</h3><div id="modes" class="grid g4"></div>
 <div id="fils" class="grid g4" style="margin-top:6px"></div>
 <h3>VFO A / B</h3><div class="grid g3"><button id="swap">A &#8644; B</button><button id="atob">A &rarr; B</button><button id="btoa">B &rarr; A</button></div>
 <div class="grid g3" style="margin-top:6px"><span id="splitslot"></span><button id="vtxa">TX on A</button><button id="vtxb">TX on B</button></div>
</section>
<section id="pFUNC" class="page">
 <h3>Functions</h3><div id="toggles" class="grid g4"></div>
 <p class="hint">ATU: tap to tune &middot; long-press to switch the tuner off</p>
 <h3>FM repeater shift</h3><div id="dups" class="grid g3"></div>
 <h3>CTCSS (tap to cycle OFF &rarr; TONE &rarr; TSQL)</h3><div class="grid g2"><span id="ctslot"></span><label class="sel"><span>Hz</span><select id="tone"></select></label></div>
 <h3>CW macros</h3><div id="macros" class="grid g3"></div>
 <h3>CW decoder</h3><div class="row"><button id="cwdb" style="flex:none;padding:0 14px">DECODER OFF</button><span id="cwdi" class="hint" style="flex:1"></span><button id="cwdc" style="flex:none;padding:0 12px">CLEAR</button></div>
 <div class="row" style="margin-top:6px"><label class="sel" style="flex:none"><span style="width:auto">Sensitivity</span><select id="cwds"><option>Auto</option><option>Low</option><option>Normal</option><option>High</option><option>Max</option></select></label><span id="cwdn" class="hint" style="flex:1"></span></div>
 <div id="cwdt" class="cwdt"></div>
 <h3>Clarifier (RIT / XIT)</h3><div class="row rit"><button data-rit="-50">&minus;50</button><button data-rit="-10">&minus;10</button><span id="ritv">+0 Hz</span>
 <button data-rit="10">+10</button><button data-rit="50">+50</button><button data-rit="clr">CLR</button></div>
</section>
<section id="pLEVELS" class="page"><div id="levels"></div><p class="hint">Double-tap the IF shift slider to centre it.</p></section>
<section id="pMEM" class="page"><div id="mems"><p class="hint">Loading&hellip;</p></div></section>
<section id="pAUDIO" class="page">
 <div id="ahttps" hidden><p class="warn">Receive audio works here, but phones only allow the microphone on the secure <b>https://</b> page.</p>
 <a id="ahlink" class="golink" hidden>Open the secure page</a>
 <p id="ahnone" class="hint">To set it up, on the PC: Settings &rsaquo; Phone access&hellip; &rsaquo; <b>Turn on HTTPS</b>.</p></div>
 <p id="aerr" class="warn" hidden></p>
 <h3>Receive</h3>
 <div class="lv"><span>Volume</span><input id="vol" type="range" min="0" max="300" step="5"><b id="volv"></b></div>
 <div class="lv"><span>RX level</span><div class="mbar"><div id="rxlv"></div></div><b></b></div>
 <label class="chk"><input id="asql" type="checkbox">Mute when the rig's squelch is closed</label>
 <p id="ainfo" class="hint"></p>
 <p id="asqlnote" class="warn" hidden>Muted: the rig's squelch is closed. Turn the squelch down (LEVELS) or untick the box above.</p>
 <h3>Transmit</h3>
 <div class="lv"><span>Mic gain</span><input id="micg" type="range" min="0" max="300" step="5"><b id="micgv"></b></div>
 <div class="lv"><span>Mic level</span><div class="mbar"><div id="miclv"></div></div><b></b></div>
 <label class="chk"><input id="latch" type="checkbox">Tap TALK to switch transmit on and off (instead of hold to talk)</label>
 <p class="hint">Tap <b>AUDIO</b> to hear the radio. Hold <b>TALK</b> to transmit with this phone's microphone.
 Transmit stops by itself if the phone's connection or microphone drops, when you leave this page, and at the PTT time-out set on the PC.</p>
 <p class="hint">Radio: for transmit audio from the phone, set the mode's <b>MOD SOURCE</b> to <b>REAR</b> and <b>REAR SELECT</b> to <b>USB</b> in the FTDX10 menu (set them back to MIC to use the hand mic).
 On iPhone, turn the ring/silent switch off to hear audio; headphones avoid the receive audio dropping to the earpiece once the mic is on.</p>
</section>
<button id="instbtn" class="instbtn" hidden>&#11015; INSTALL AS AN APP</button>
<div id="instov" class="ov" hidden><div class="ovbox"><h3>INSTALL AS AN APP</h3><div id="insttxt"></div><button id="instok">OK</button></div></div>
<p class="foot">FTDX10 Monitor <span id="ver"></span> &middot; GM0OTB<br>Drag the frequency sideways to tune</p>
</div>
<div id="dock"><div class="in"><button id="abtn">AUDIO OFF</button><button id="ptt">HOLD TO TALK</button></div></div>
<div id="toast"></div>
<script>
"use strict";
const CFG=__CFG__;
const $=id=>document.getElementById(id);
function el(tag,props,kids){const e=document.createElement(tag);if(props)Object.assign(e,props);if(kids)for(const k of kids)e.append(k);return e;}
const LS={get(k,d){try{const v=localStorage.getItem(k);return v===null?d:v}catch(e){return d}},set(k,v){try{localStorage.setItem(k,v)}catch(e){}}};
let S=null;

// ---------------- commands to the PC (sent one after another, in order)
let chain=Promise.resolve(),pending=0;
function send(cmd){
  pending++;
  chain=chain.then(()=>fetch('api/cmd',{method:'POST',credentials:'same-origin',
    headers:{'Content-Type':'application/json','X-RIG':'1'},body:JSON.stringify(cmd)}).catch(()=>{}))
    .then(()=>{pending--;kick();});
}
let toastT=null;
function toast(msg){const t=$('toast');t.textContent=msg;t.classList.add('show');clearTimeout(toastT);toastT=setTimeout(()=>t.classList.remove('show'),1600);}

// ---------------- polling
let pollT=null,inflight=false,again=false,fails=0;
async function poll(){
  if(inflight){again=true;return;}
  inflight=true;clearTimeout(pollT);
  try{
    const r=await fetch('api/state',{cache:'no-store',credentials:'same-origin'});
    if(r.status===401){location.reload();return;}
    if(!r.ok)throw new Error(r.status);
    S=await r.json();fails=0;$('net').hidden=true;render();
  }catch(e){if(++fails>2){$('net').hidden=false;$('led').className='led off';$('status').textContent='PC not reachable';}}
  inflight=false;
  pollT=setTimeout(poll,again?50:(document.hidden?2000:300));again=false;
}
function kick(){if(inflight)again=true;else{clearTimeout(pollT);pollT=setTimeout(poll,50);}}
document.addEventListener('visibilitychange',()=>{if(!document.hidden)kick();});

// ---------------- helpers
function fmtHz(hz){
  if(hz==null)return '---.---<small>.--</small>';
  const m=Math.floor(hz/1e6),k=Math.floor(hz%1e6/1000),h=Math.floor(hz%1000/10);
  return m+'.'+String(k).padStart(3,'0')+'<small>.'+String(h).padStart(2,'0')+'</small>';
}
function levelText(fmt,v){
  if(v==null)return '--';
  if(fmt==='pct')return Math.round(v/255*100)+'%';
  if(fmt==='pct100')return v+'%';
  if(fmt==='shift')return (v>=0?'+':'')+v+'Hz';
  if(fmt==='pitch')return (300+10*v)+'Hz';
  if(fmt==='watts')return v+'W';
  if(fmt==='wpm')return v+'wpm';
  return String(v);
}
function stepHz(){return +$('step').value||1000;}
function stepTune(d){if(pending>2)return;send({a:'step',dir:d,step:stepHz()});}
function holdButton(b,fn){
  let t1=null,t2=null;
  const stop=()=>{clearTimeout(t1);clearInterval(t2);t1=t2=null;};
  b.addEventListener('pointerdown',e=>{e.preventDefault();stop();fn();t1=setTimeout(()=>{t2=setInterval(fn,150);},450);});
  for(const ev of ['pointerup','pointerleave','pointercancel'])b.addEventListener(ev,stop);
  b.addEventListener('contextmenu',e=>e.preventDefault());
}

// ---------------- build the pages
const TABS=['TUNE','FUNC','LEVELS','MEM','AUDIO'];
function showTab(n){
  for(const t of TABS){$('p'+t).classList.toggle('on',t===n);$('t'+t).classList.toggle('on',t===n);}
  LS.set('tab',n);if(n==='MEM')loadMem();
}
let stepFromRig=!LS.get('step',null);
function build(){
  $('ver').textContent=CFG.version;
  for(const t of TABS)$('t'+t).onclick=()=>showTab(t);
  const st=$('step');
  for(const [lab,hz] of CFG.steps)st.append(el('option',{value:String(hz),textContent:lab}));
  st.value=LS.get('step','12500');
  st.onchange=()=>{LS.set('step',st.value);stepFromRig=false;};
  holdButton($('dn'),()=>stepTune(-1));holdButton($('up'),()=>stepTune(1));
  for(const b of CFG.bands){const x=el('button',{textContent:b,onclick:()=>send({a:'band',band:b})});x.dataset.band=b;$('bands').append(x);}
  for(const m of CFG.modes){const x=el('button',{textContent:m,onclick:()=>send({a:'mode',mode:m})});x.dataset.mode=m;$('modes').append(x);}
  for(const k of ['nar','amp','att','agc'])$('fils').append(toggleBtn(k));
  $('setf').onclick=directEntry;$('fin').addEventListener('keydown',e=>{if(e.key==='Enter')directEntry();});
  $('swap').onclick=()=>send({a:'swap'});
  $('atob').onclick=()=>send({a:'vfo',op:'AB'});
  $('btoa').onclick=()=>send({a:'vfo',op:'BA'});
  $('vtxa').onclick=()=>send({a:'txvfo',b:false});
  $('vtxb').onclick=()=>send({a:'txvfo',b:true});
  $('splitslot').replaceWith(toggleBtn('split'));
  $('ctslot').replaceWith(toggleBtn('ctcss'));
  for(const k of ['nb','nr','anf','proc','vox','mon','bkin','keyer','rit','xit','lock'])$('toggles').append(toggleBtn(k));
  {const x=el('button',{id:'atutune',textContent:'ATU',title:'Tap: tune. Long press: tuner off'});let lp=null,longDone=false;
   const clr=()=>{if(lp){clearTimeout(lp);lp=null;}};
   x.addEventListener('pointerdown',()=>{longDone=false;clr();lp=setTimeout(()=>{longDone=true;send({a:'atu_off'});toast('ATU off');},700);});
   ['pointerup','pointerleave','pointercancel'].forEach(ev=>x.addEventListener(ev,clr));
   x.addEventListener('contextmenu',e=>e.preventDefault());
   x.onclick=()=>{if(longDone){longDone=false;return;}send({a:'atu_tune'});toast('ATU tuning \u2026 the radio transmits while it tunes');};
   $('toggles').append(x);}
  CFG.macros.forEach((m,i)=>{const x=el('button',{textContent:'M'+(i+1),title:m,onclick:()=>{send({a:'macro',n:i});toast('CW: '+m);}});$('macros').append(x);});
  for(const n of [1,2,3,4]){const x=el('button',{textContent:'KEYER '+n,onclick:()=>send({a:'keyer',n})});$('macros').append(x);}
  for(const [lab,code] of [['SIMPLEX',0],['+ SHIFT',1],['\u2212 SHIFT',2]]){
    const x=el('button',{textContent:lab,onclick:()=>send({a:'dup',code})});x.dataset.dup=code;$('dups').append(x);
  }
  {const s=$('tone');for(const t of CFG.ctcss)s.append(el('option',{value:t.toFixed(1),textContent:t.toFixed(1)}));
   s.onchange=()=>send({a:'tone',t:+s.value});}
  document.querySelectorAll('[data-rit]').forEach(b=>b.onclick=()=>{
    const d=b.dataset.rit;send(d==='clr'?{a:'rit_clear'}:{a:'rit',d:+d});});
  $('cwdb').onclick=()=>send({a:'cwdec',on:!(S&&S.cwd&&S.cwd.on)});
  $('cwdc').onclick=()=>{send({a:'cwd_clear'});$('cwdt').textContent='';};
  $('cwds').onchange=e=>{send({a:'cwd_sens',v:e.target.value});cwdsTouched=Date.now();};
  $('pwr').onclick=()=>{
    if(!S||!S.online){toast('The PC has no USB connection to the radio');return;}
    if(S.rig_on){if(confirm('Switch the FTDX10 OFF?')){send({a:'power',on:false});toast('Switching off…');}}
    else{send({a:'power',on:true});toast('Switching on… (takes a few seconds)');}
  };
  const lv=$('levels');
  for(const [label,sub,lo,hi,fmt] of CFG.levels){
    const r=el('input',{type:'range',min:lo,max:hi,step:fmt==='shift'?20:1,value:fmt==='shift'?0:lo});
    const v=el('b',{textContent:'--'});
    r.dataset.sub=sub;r.dataset.fmt=fmt;
    let t=null;
    const push=()=>{t=null;send({a:'level',sub,v:+r.value});};
    r.addEventListener('input',()=>{touched[sub]=Date.now();v.textContent=levelText(fmt,+r.value);if(!t)t=setTimeout(push,120);});
    r.addEventListener('change',()=>{touched[sub]=Date.now();clearTimeout(t);push();});
    if(fmt==='shift')r.addEventListener('dblclick',()=>{r.value=0;touched[sub]=Date.now();v.textContent=levelText(fmt,0);push();});
    lv.append(el('div',{className:'lv'},[el('span',{textContent:label}),r,v]));
    if(sub==='AG0'){                         // AF = the radio's own speaker, not the phone
      const n=el('p',{className:'afnote'});
      n.innerHTML='Radio speaker volume. For the listening level <b>on this phone</b>, use the <a href="#">AUDIO tab</a>.';
      n.querySelector('a').onclick=e=>{e.preventDefault();showTab('AUDIO');};lv.append(n);
    }
    lvRows.push([sub,fmt,r,v]);
  }
  buildAudio();
  // drag the frequency sideways to tune
  const f=$('freq');let x0=null,acc=0;
  f.addEventListener('pointerdown',e=>{x0=e.clientX;acc=0;try{f.setPointerCapture(e.pointerId);}catch(_){}});
  f.addEventListener('pointermove',e=>{if(x0===null)return;acc+=e.clientX-x0;x0=e.clientX;
    while(Math.abs(acc)>=22){const d=Math.sign(acc);acc-=d*22;stepTune(d);}});
  for(const ev of ['pointerup','pointercancel'])f.addEventListener(ev,()=>{x0=null;});
  showTab(TABS.includes(LS.get('tab','TUNE'))?LS.get('tab','TUNE'):'TUNE');
}
const touched={},lvRows=[];
function toggleBtn(k){const x=el('button',{textContent:CFG.toggles[k],onclick:()=>send({a:'toggle',key:k})});x.dataset.key=k;x.dataset.label=CFG.toggles[k];return x;}
function directEntry(){
  const v=parseFloat($('fin').value.replace(',','.'));
  if(!(v>=0.1&&v<=2000)){toast('Enter MHz, e.g. 145.500');return;}
  send({a:'tune',hz:Math.round(v*1e6)});$('fin').value='';$('fin').blur();
}

// ---------------- memories
let memRev=null;
async function loadMem(){
  try{const r=await fetch('api/memories',{cache:'no-store',credentials:'same-origin'});if(r.ok)renderMem(await r.json());}catch(e){}
}
function renderMem(list){
  const box=$('mems');box.textContent='';
  if(!list.length){box.append(el('p',{className:'hint',textContent:'No memories yet. Save some on the PC (MEMORY tab), or use "Read from radio" there.'}));return;}
  for(const m of list){
    box.append(el('button',{className:'mem',onclick:()=>{send({a:'mem',i:m.i});toast('Recalled '+m.name);}},[
      el('span',{className:'mn'},[el('div',{textContent:m.name}),el('div',{className:'mi',textContent:[m.ch,m.mode,m.info].filter(Boolean).join(' · ')})]),
      el('span',{className:'mf',textContent:m.mhz})]));
  }
}

// ---------------- render
let tickMode=null;
function setTicks(tx){
  if(tickMode===tx)return;tickMode=tx;const t=$('ticks');t.textContent='';
  for(const [l,f] of (tx?CFG.pwr_ticks:CFG.s_ticks)){const s=el('span',{textContent:l});s.style.left=(f*100)+'%';if(!tx&&f>CFG.s9)s.className='r';t.append(s);}
}
function showTag(id,text,show){const e=$(id);e.hidden=!show;if(show)e.textContent=text;}
let cwdsTouched=0;
function render(){
  const s=S,on=s.online;
  document.body.classList.toggle('offline',!on);
  $('led').className='led '+(!on?'off':(s.link?'ok':'warn'));
  $('status').textContent=on?((s.rig||'Rig')+(s.rig_off?' · switched off':s.link?' · online':' · no reply from rig')):(s.status||'Radio offline');
  const pw=$('pwr');pw.classList.toggle('on',!!s.rig_on);pw.innerHTML=s.rig_on?'&#9211; ON':'&#9211; OFF';
  $('vd').textContent='';
  $('utc').textContent=s.utc?s.utc+' UTC':'';
  $('freq').innerHTML=fmtHz(s.hz);$('freq').classList.toggle('dim',s.hz==null);
  $('mode').textContent=s.mode||'--';
  $('vfo').textContent=s.vfo_text||'VFO-A';
  const nar=s.toggles.nar;$('fil').hidden=!(nar&&nar[0]);
  const spl=s.toggles.split,dupt=(spl&&spl[0])?'SPLIT':({1:'+RPT',2:'-RPT'}[s.dup]);showTag('dup',dupt,!!dupt);
  const cl=['rit','xit'].filter(k=>s.toggles[k]&&s.toggles[k][0]).map(k=>k.toUpperCase()).join('/');showTag('sat',cl,!!cl);
  $('scan').hidden=!s.scan;
  $('bandlbl').textContent=s.band||'';
  $('busy').hidden=!s.busy;$('txb').hidden=!s.tx;
  // meter
  const tx=s.meter==='tx';setTicks(tx);
  $('mlab').textContent=tx?'Po':'S';
  const frac=Math.max(0,Math.min(1,tx?s.pwr:s.mfrac));
  $('mfill').style.clipPath='inset(0 '+(100-frac*100).toFixed(1)+'% 0 0)';
  $('mfill').className=tx?'tx':'';
  const pk=$('mpeak');pk.hidden=tx||!(s.peak>0);pk.style.left='calc('+(s.peak*100).toFixed(1)+'% - 1px)';
  $('mtext').textContent=s.mtext||'';
  $('mtext').style.color=tx?['#3ddc84','#ffa62b','#ff4a3d'][s.swr_sev]||'#fff':(s.mfrac>CFG.s9?'#ff4a3d':'#fff');
  $('info').textContent=s.info||'';$('info').style.color=tx?'#ffa62b':'';
  // sub band
  $('submode').textContent=s.sub_hz!=null?[s.sub_mode,s.sub_band].filter(Boolean).join(' '):'';
  $('subfreq').innerHTML=s.sub_hz!=null?fmtHz(s.sub_hz):'---.---';
  // buttons
  document.querySelectorAll('[data-mode]').forEach(b=>b.classList.toggle('on',b.dataset.mode===s.mode));
  document.querySelectorAll('[data-band]').forEach(b=>b.classList.toggle('on',b.dataset.band===s.band));
  document.querySelectorAll('[data-dup]').forEach(b=>b.classList.toggle('on',+b.dataset.dup===s.dup&&s.dup!==0));
  $('vtxa').classList.toggle('on',s.tx_b===false);$('vtxb').classList.toggle('on',s.tx_b===true);
  document.querySelectorAll('[data-key]').forEach(b=>{const t=s.toggles[b.dataset.key];b.classList.toggle('on',!!(t&&t[0]));
    const txt=t?t[1]:b.dataset.label;if(b.textContent!==txt)b.textContent=txt;});
  if(stepFromRig&&s.step){$('step').value=String(s.step);stepFromRig=false;}
  {const e=$('tone');if(document.activeElement!==e&&s.tone)e.value=s.tone;}
  $('ritv').textContent=(s.rit>=0?'+':'')+s.rit+' Hz';
  {const t=$('atutune'),a=s.toggles.atu;if(t){t.classList.toggle('on',!!s.atu_tuning||!!(a&&a[0]));t.textContent=s.atu_tuning?'TUNING':'ATU';}}
  const now=Date.now();
  for(const [sub,fmt,r,v] of lvRows){
    if(now-(touched[sub]||0)<2500)continue;
    const val=s.levels[sub];
    if(val!=null)r.value=val;
    v.textContent=levelText(fmt,val);
  }
  {const c=s.cwd||{},b=$('cwdb'),t=$('cwdt');b.classList.toggle('on',!!c.on);b.textContent=c.on?'DECODER ON':'DECODER OFF';
   $('cwdi').textContent=c.info||'';$('cwdn').textContent=c.sens_note||'';
   if(c.sens&&Date.now()-cwdsTouched>2500&&document.activeElement!==$('cwds'))$('cwds').value=c.sens;
   if(t.textContent!==(c.text||'')){const end=t.scrollTop+t.clientHeight>=t.scrollHeight-4;t.textContent=c.text||'';if(end)t.scrollTop=t.scrollHeight;}}
  updAudioUi();
  if(s.mem_rev!==memRev){const first=memRev===null;memRev=s.mem_rev;if(!first&&$('pMEM').classList.contains('on'))loadMem();}
}


// ---------------- audio: radio receive audio to this phone, this phone's microphone to the radio
const AR=16000;
const ULAW=new Float32Array(256);
for(let u=0;u<256;u++){const x=~u&255,e=(x>>4)&7,s=((((x&15)<<3)+0x84)<<e)-0x84;ULAW[u]=((x&128)?-s:s)/32768;}
function ulawEnc(f){
  let s=Math.round(Math.max(-1,Math.min(1,f))*32767);const sign=s<0?0x80:0;if(s<0)s=-s;s=Math.min(s,32635)+0x84;
  let e=7,mask=0x4000;while(e>0&&!(s&mask)){e--;mask>>=1;}
  return (~(sign|(e<<4)|((s>>(e+3))&15)))&255;
}
const A={ctx:null,ws:null,want:false,on:false,tx:false,txWant:false,mic:null,rxq:[],rxpos:0,primed:false,
  vol:+LS.get('vol','1'),micg:+LS.get('micg','1'),latch:LS.get('latch','0')==='1',rxpk:0,micpk:0,err:'',retry:null};
function rxAvail(){let n=-A.rxpos;for(const c of A.rxq)n+=c.length;return n;}
function rxPush(u8){
  const f=new Float32Array(u8.length);for(let i=0;i<u8.length;i++)f[i]=ULAW[u8[i]];
  A.rxq.push(f);if(A.rxq.length>60){A.rxq.splice(0,A.rxq.length-20);A.rxpos=0;}
}
function onPlay(e){
  const out=e.outputBuffer.getChannelData(0),n=out.length,step=AR/A.ctx.sampleRate;
  let av=rxAvail();
  if(!A.primed){if(av>=AR*0.12)A.primed=true;else{out.fill(0);A.rxpk*=0.9;return;}}
  while(av>AR*0.5&&A.rxq.length>1){av-=A.rxq[0].length-A.rxpos;A.rxq.shift();A.rxpos=0;}   // fell behind: catch up
  const g=A.tx?0:A.vol;let pk=0;
  for(let i=0;i<n;i++){
    const c=A.rxq[0];
    if(!c){out.fill(0,i);A.rxpos=0;A.primed=false;break;}
    const i0=A.rxpos|0,fr=A.rxpos-i0,s0=c[i0],s1=i0+1<c.length?c[i0+1]:(A.rxq[1]?A.rxq[1][0]:s0);
    const v=s0+(s1-s0)*fr;out[i]=v*g;const av2=v<0?-v:v;if(av2>pk)pk=av2;
    A.rxpos+=step;
    while(A.rxq.length&&A.rxpos>=A.rxq[0].length){A.rxpos-=A.rxq[0].length;A.rxq.shift();}
  }
  A.rxpk=Math.max(pk,A.rxpk*0.85);
}
let micPos=0;
function onMic(e){
  const inp=e.inputBuffer.getChannelData(0),len=inp.length,step=A.ctx.sampleRate/AR;
  const out=new Uint8Array(Math.ceil(len/step)+2);
  let p=micPos,k=0,pk=0;
  while(p<len){
    const a=p|0,b=Math.min(len,Math.max(a+1,(p+step)|0));let s=0;for(let j=a;j<b;j++)s+=inp[j];
    const v=s/(b-a)*A.micg;out[k++]=ulawEnc(v);const av=v<0?-v:v;if(av>pk)pk=av;p+=step;
  }
  micPos=p-len;A.micpk=Math.max(pk,A.micpk*0.8);
  if(A.tx&&A.ws&&A.ws.readyState===1)A.ws.send(out.subarray(0,k));
}
function ensureCtx(){
  if(A.ctx)return;
  const C=window.AudioContext||window.webkitAudioContext;A.ctx=new C();
  const p=A.ctx.createScriptProcessor(2048,1,1);p.onaudioprocess=onPlay;p.connect(A.ctx.destination);A.play=p;
}
function audioConnect(){
  if(A.ws||!A.want)return;
  if(!S||!S.atok){clearTimeout(A.retry);A.retry=setTimeout(audioConnect,1000);return;}
  const ws=new WebSocket((location.protocol==='https:'?'wss://':'ws://')+location.host+'/api/audio?t='+encodeURIComponent(S.atok));
  ws.binaryType='arraybuffer';A.ws=ws;
  ws.onopen=()=>{A.on=true;A.err='';updAudioUi();};
  ws.onmessage=ev=>{
    if(typeof ev.data==='string'){
      let m={};try{m=JSON.parse(ev.data);}catch(_){}
      if(m.err){A.err=m.err;toast(m.err);}
      if(m.ptt_drop){A.tx=false;A.txWant=false;toast('Transmit stopped: microphone audio stopped arriving');}
      updAudioUi();return;
    }
    rxPush(new Uint8Array(ev.data));
  };
  ws.onclose=()=>{
    const wasTx=A.tx;A.ws=null;A.on=false;A.tx=false;A.rxq=[];A.rxpos=0;A.primed=false;updAudioUi();
    if(wasTx)toast('Audio link lost — transmit stopped');
    if(A.want){clearTimeout(A.retry);A.retry=setTimeout(audioConnect,2000);}
  };
}
setInterval(()=>{if(A.ws&&A.ws.readyState===1)A.ws.send('{}');},4000);
function audioToggle(){
  if(A.want){A.want=false;pttUp();clearTimeout(A.retry);if(A.ws)A.ws.close();updAudioUi();return;}
  ensureCtx();A.ctx.resume();A.want=true;audioConnect();updAudioUi();
}
async function ensureMic(){
  if(A.mic)return true;
  if(!window.isSecureContext||!navigator.mediaDevices||!navigator.mediaDevices.getUserMedia){
    toast(S&&S.https_url?'Talk needs the secure page \u2014 tap the green button':'The microphone needs the https:// page');showTab('AUDIO');return false;}
  try{A.mic=await navigator.mediaDevices.getUserMedia({audio:{echoCancellation:true,noiseSuppression:true,autoGainControl:true}});}
  catch(e){toast('Microphone not allowed ('+e.name+')');return false;}
  const src=A.ctx.createMediaStreamSource(A.mic),p=A.ctx.createScriptProcessor(2048,1,1),z=A.ctx.createGain();
  z.gain.value=0;p.onaudioprocess=onMic;src.connect(p);p.connect(z);z.connect(A.ctx.destination);A.micNodes=[src,p,z];
  return true;
}
async function pttDown(){
  if(S&&(S.tx||S.ptt)&&!A.tx&&!A.txWant){send({a:'unkey'});toast('Releasing PTT');return;}   // keyed from the PC: tap releases
  if(A.latch&&(A.tx||A.txWant)){pttUp();return;}
  A.txWant=true;updAudioUi();
  ensureCtx();A.ctx.resume();
  if(!A.want)audioToggle();
  if(!await ensureMic()){A.txWant=false;updAudioUi();return;}
  for(let i=0;i<30&&!(A.ws&&A.ws.readyState===1);i++)await new Promise(r=>setTimeout(r,100));
  if(!A.txWant)return;
  if(!(A.ws&&A.ws.readyState===1)){toast('No audio connection to the PC');A.txWant=false;updAudioUi();return;}
  if(S&&!S.online){toast('Radio is offline');A.txWant=false;updAudioUi();return;}
  A.tx=true;micPos=0;A.ws.send(JSON.stringify({ptt:true}));updAudioUi();
}
function pttUp(){
  A.txWant=false;
  if(A.tx){A.tx=false;if(A.ws&&A.ws.readyState===1)A.ws.send(JSON.stringify({ptt:false}));}
  updAudioUi();
}
function updAudioUi(){
  const ab=$('abtn');ab.classList.toggle('on',A.want&&A.on);
  ab.textContent=A.want?(A.on?(S&&S.sql_muted?'AUDIO ON \u00b7 SQL':'AUDIO ON'):'CONNECTING…'):'AUDIO OFF';
  $('asqlnote').hidden=!(A.on&&S&&S.sql_muted);
  const pb=$('ptt'),rig=!!(S&&(S.tx||S.ptt)&&!A.tx&&!A.txWant);
  pb.classList.toggle('tx',A.tx);pb.classList.toggle('rig',rig);
  pb.textContent=A.tx?(A.latch?'TX — TAP TO STOP':'TX — RELEASE TO STOP'):A.txWant?'STARTING TX…':
    rig?'RIG IN TX — TAP TO RELEASE':(A.latch?'TAP TO TALK':'HOLD TO TALK');
  const err=A.err||(S&&S.audio_err)||'';$('aerr').hidden=!err;$('aerr').textContent=err;
  const hu=S&&S.https_url;$('ahlink').hidden=!hu;$('ahnone').hidden=!!hu;if(hu&&$('ahlink').href!==hu)$('ahlink').href=hu;
  if(S&&document.activeElement!==$('asql'))$('asql').checked=!!S.audio_sql;
  $('ainfo').textContent=(S&&A.on&&S.audio_info)||'';
}
function buildAudio(){
  const vol=$('vol'),mg=$('micg'),la=$('latch');
  vol.value=Math.round(A.vol*100);mg.value=Math.round(A.micg*100);la.checked=A.latch;
  const upd=()=>{$('volv').textContent=vol.value+'%';$('micgv').textContent=mg.value+'%';};upd();
  vol.oninput=()=>{A.vol=vol.value/100;LS.set('vol',String(A.vol));upd();};
  mg.oninput=()=>{A.micg=mg.value/100;LS.set('micg',String(A.micg));upd();};
  la.onchange=()=>{A.latch=la.checked;LS.set('latch',la.checked?'1':'0');pttUp();};
  $('ahttps').hidden=window.isSecureContext;
  $('asql').onchange=()=>{send({a:'audio_sql',on:$('asql').checked});};
  $('abtn').onclick=audioToggle;
  const pb=$('ptt');
  pb.addEventListener('pointerdown',e=>{e.preventDefault();try{pb.setPointerCapture(e.pointerId);}catch(_){}pttDown();});
  for(const ev of ['pointerup','pointercancel'])pb.addEventListener(ev,()=>{if(!A.latch)pttUp();});
  pb.addEventListener('contextmenu',e=>e.preventDefault());
  document.addEventListener('visibilitychange',()=>{if(document.hidden)pttUp();});
  window.addEventListener('pagehide',pttUp);
  (function meters(){
    $('rxlv').style.width=(A.on?Math.min(100,A.rxpk*130):0)+'%';
    $('miclv').style.width=(A.mic?Math.min(100,A.micpk*130):0)+'%';
    $('miclv').style.background=A.micpk>0.7?'var(--red)':'var(--green)';
    requestAnimationFrame(meters);
  })();
  updAudioUi();
}

// ---------------- installable app (Android: Chrome turns it into a real installed app)
let instEvt=null;
const standalone=window.matchMedia('(display-mode: standalone)').matches||navigator.standalone===true||/FTDX10App/.test(navigator.userAgent);
function instShow(on){$('instbtn').hidden=!on;$('insttop').hidden=!on;}
instShow(!standalone);                      // always offered unless it is already running as the app
window.addEventListener('beforeinstallprompt',e=>{e.preventDefault();instEvt=e;});
window.addEventListener('appinstalled',()=>{instShow(false);$('instov').hidden=true;toast('Installed — open it from your home screen');});
function instHelp(){
  const ua=navigator.userAgent,box=$('insttxt');box.textContent='';
  const p=(html)=>{const e=document.createElement('p');e.innerHTML=html;box.append(e);};
  if(!window.isSecureContext){
    p('The app can only be installed from the <b>secure (https)</b> page.');
    if(S&&S.https_url){const a=el('a',{className:'golink',href:S.https_url,textContent:'Open the secure page'});box.append(a);
      p('Then tap <b>&#11015; APP</b> again there.');}
    else p('On the PC: <b>Phone &rsaquo; Turn on HTTPS</b>, then open the https address it shows.');
  }else if(/iPhone|iPad|iPod/.test(ua)){
    p('Tap the <b>Share</b> button (square with an arrow), scroll down and tap <b>Add to Home Screen</b>, then <b>Add</b>.');
    p('On iPhone use <b>Safari</b> for this.');
  }else if(/SamsungBrowser/.test(ua)){
    p('Tap the <b>&#9776; menu</b> (bottom right) &rsaquo; <b>Add page to</b> &rsaquo; <b>Home screen</b>.');
  }else if(/Firefox/.test(ua)){
    p('Tap the <b>&#8942; menu</b> &rsaquo; <b>Install</b> (or <b>Add to Home screen</b>).');
  }else if(/Android/.test(ua)){
    p('Tap Chrome’s <b>&#8942; menu</b> (top right) &rsaquo; <b>Install app</b> (or <b>Add to Home screen</b> &rsaquo; <b>Install</b>).');
    p('It then appears in your app drawer like any other app.');
  }else{
    p('Click the <b>install</b> icon at the right of the address bar, or the browser menu &rsaquo; <b>Install</b>.');
  }
  $('instov').hidden=false;
}
async function instClick(){
  if(instEvt){instEvt.prompt();let ok=false;try{ok=(await instEvt.userChoice).outcome==='accepted';}catch(_){}instEvt=null;if(ok)instShow(false);return;}
  instHelp();
}
$('instbtn').onclick=instClick;$('insttop').onclick=instClick;
$('instok').onclick=()=>{$('instov').hidden=true;};
$('instov').onclick=e=>{if(e.target===$('instov'))$('instov').hidden=true;};
if('serviceWorker' in navigator&&window.isSecureContext){navigator.serviceWorker.register('sw.js').catch(()=>{});}

build();poll();
</script>
</body></html>
"""


LOGIN_PAGE = r"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="theme-color" content="#1b1c1f">
<title>FTDX10</title>
<link rel="manifest" href="manifest.webmanifest">
<link rel="icon" type="image/png" href="icon-512.png">
<link rel="apple-touch-icon" href="icon-512.png">
<style>
*{box-sizing:border-box}
html,body{margin:0;background:#1b1c1f;color:#eef1f5;font:16px/1.4 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
main{max-width:360px;margin:0 auto;padding:12vh 20px 40px;text-align:center}
img{width:88px;height:88px;border-radius:20px}
h1{font-size:22px;margin:14px 0 4px}p{color:#9aa1ab;font-size:14px;margin:0 0 22px}
input,button{width:100%;min-height:52px;border-radius:10px;font:600 17px system-ui,sans-serif}
input{background:#101113;color:#eef1f5;border:1px solid #393c42;padding:0 14px;margin-bottom:12px}
button{background:#1f5fc4;color:#fff;border:0}
.err{color:#ff8a80;font-size:14px;margin:0 0 12px;min-height:1px}
</style></head><body><main>
<img src="icon-512.png" alt="">
<h1>FTDX10 Monitor</h1><p>GM0OTB &middot; enter the phone access password set on the PC</p>
<form method="post" action="login">
<p class="err">__ERR__</p>
<input type="password" name="password" autocomplete="current-password" placeholder="Password" autofocus required>
<button type="submit">Sign in</button>
</form></main>
<script>if('serviceWorker' in navigator&&window.isSecureContext)navigator.serviceWorker.register('sw.js').catch(()=>{});</script>
</body></html>
"""

WEB_MANIFEST = json.dumps({
    "id": "/", "name": "FTDX10 Monitor", "short_name": "FTDX10", "start_url": "/", "scope": "/",
    "display": "standalone", "orientation": "portrait", "background_color": "#1b1c1f", "theme_color": "#1b1c1f",
    "description": "FTDX10 remote control by GM0OTB",
    "icons": [{"src": "icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any"}],
}).encode("utf-8")

# Lets Chrome install the page as an app. It deliberately caches nothing: the page is always live from the PC.
WEB_SW = b"""self.addEventListener('install',e=>self.skipWaiting());
self.addEventListener('activate',e=>e.waitUntil(self.clients.claim()));
self.addEventListener('fetch',e=>{});
"""

COOKIE_NAME = "ftdx10_auth"     # different from the IC9700 Monitor: cookies are shared per PC name


def _png_plain(size=512):
    """A simple app icon (used only if ftdx10.png is missing)."""
    rows = []
    for y in range(size):
        row = bytearray([0])
        for x in range(size):
            bar = size * 0.2 < x < size * 0.8 and size * 0.62 < y < size * 0.7 and x < size * (0.2 + 0.45)
            row += bytes((0x2d, 0x63, 0xc8)) if bar else bytes((0x1b, 0x1c, 0x1f))
        rows.append(bytes(row))
    raw = zlib.compress(b"".join(rows), 9)

    def chunk(t, d):
        return len(d).to_bytes(4, "big") + t + d + (zlib.crc32(t + d) & 0xFFFFFFFF).to_bytes(4, "big")
    ihdr = size.to_bytes(4, "big") * 2 + bytes((8, 2, 0, 0, 0))
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", raw) + chunk(b"IEND", b"")


def app_icon_png():
    for d in (getattr(sys, "_MEIPASS", None), BASE_DIR, os.path.dirname(os.path.abspath(__file__))):
        if d:
            try:
                with open(os.path.join(d, "ftdx10.png"), "rb") as f:
                    return f.read()
            except OSError:
                pass
    return _png_plain()


def web_page_bytes():
    """The phone page with this program's own mode / step / level / tone lists filled in."""
    cfg = {"version": APP_VERSION, "modes": MODE_LIST, "bands": [b[0] for b in BANDS],
           "steps": [[n, v] for n, v in STEPS], "ctcss": CTCSS,
           "levels": [[lab, p, lo, hi, fmt] for lab, p, dg, lo, hi, fmt in LEVELS],
           "macros": list(DEFAULT_MACROS),
           "toggles": {k: v[0] for k, v in TOGGLES.items()},
           "s_ticks": [[label, raw / METER_MAX] for label, raw in S_TICKS],
           "pwr_ticks": [[label, raw / METER_MAX] for label, raw in PWR_TICKS],
           "s9": S9_RAW / METER_MAX}
    return WEB_PAGE.replace("__CFG__", json.dumps(cfg)).encode("utf-8")


class _WebServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = sys.platform != "win32"     # on Windows this would let two copies share the port

    def handle_error(self, request, client_address):
        pass                                            # pythonw has no console to print to


class _WebHandler(BaseHTTPRequestHandler):
    server_version = "FTDX10Monitor"
    protocol_version = "HTTP/1.1"
    timeout = 60

    def log_message(self, *args):
        pass                                            # pythonw has no console to print to

    def _send(self, code, body=b"", ctype="application/json"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "same-origin")
        self.end_headers()
        if body and self.command != "HEAD":
            self.wfile.write(body)

    def _authed(self):
        """Signed in with the cookie from the sign-in page (or HTTP Basic, for older bookmarks)."""
        bridge = self.server.bridge
        for part in self.headers.get("Cookie", "").split(";"):
            k, _, v = part.strip().partition("=")
            if k == COOKIE_NAME and bridge.cookie_token and hmac.compare_digest(v.encode(), bridge.cookie_token.encode()):
                return True
        h = self.headers.get("Authorization", "")
        if h.startswith("Basic ") and bridge.password:
            try:
                pw = base64.b64decode(h[6:].strip()).decode("utf-8", "replace").split(":", 1)[1]
            except Exception:
                pw = ""
            if hmac.compare_digest(pw.encode("utf-8"), bridge.password.encode("utf-8")):
                return True
        return False

    def _login_page(self, err=""):
        body = LOGIN_PAGE.replace("__ERR__", err).encode("utf-8")
        self._send(200, body, "text/html; charset=utf-8")

    def _do_login(self):
        bridge = self.server.bridge
        try:
            n = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            n = -1
        if not 0 < n <= 4096:
            self._login_page("Please enter the password.")
            return
        form = urllib.parse.parse_qs(self.rfile.read(n).decode("utf-8", "replace"))
        pw = (form.get("password") or [""])[0]
        if not (bridge.password
                and hmac.compare_digest(pw.encode("utf-8"), bridge.password.encode("utf-8"))):
            time.sleep(1.0)                             # slow down password guessing
            self._login_page("Wrong password - try again.")
            return
        secure = "; Secure" if isinstance(self.connection, ssl.SSLSocket) else ""
        self.send_response(303)
        self.send_header("Location", "./")
        self.send_header("Set-Cookie", f"{COOKIE_NAME}={bridge.cookie_token}; Path=/; Max-Age=31536000; "
                                       f"HttpOnly; SameSite=Lax{secure}")
        self.send_header("Content-Length", "0")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()

    def _origin_ok(self):
        origin = self.headers.get("Origin")
        if not origin:
            return True
        ohost = origin.split("://", 1)[-1].strip("/").lower()
        hosts = {h.strip().lower() for h in (self.headers.get("Host", ""), self.headers.get("X-Forwarded-Host", "")) if h}
        if ohost in hosts:
            return True
        # Behind "tailscale serve" the page is https://<pc>.<tailnet>.ts.net and requests arrive via loopback
        return (origin.startswith("https://") and ohost.split(":")[0].endswith(".ts.net")
                and self.client_address[0] in ("127.0.0.1", "::1"))

    def _audio_upgrade(self):
        """WebSocket for phone audio. Authorised by a token from /api/state (that one needs the password)."""
        bridge = self.server.bridge
        q = urllib.parse.parse_qs(self.path.split("?", 1)[1] if "?" in self.path else "")
        tok = (q.get("t") or [""])[0]
        if not (bridge.audio_token and hmac.compare_digest(tok.encode(), bridge.audio_token.encode())):
            time.sleep(1.0)
            self._send(403, b'{"error":"forbidden"}')
            return
        key = self.headers.get("Sec-WebSocket-Key", "")
        if not self._origin_ok() or "websocket" not in self.headers.get("Upgrade", "").lower() or not key:
            self._send(400, b'{"error":"bad request"}')
            return
        accept = base64.b64encode(hashlib.sha1((key + WS_GUID).encode()).digest()).decode()
        self.send_response(101, "Switching Protocols")
        self.send_header("Upgrade", "websocket")
        self.send_header("Connection", "Upgrade")
        self.send_header("Sec-WebSocket-Accept", accept)
        self.end_headers()
        self.wfile.flush()
        self.close_connection = True
        sock = self.connection
        sock.settimeout(None)
        try:
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        except OSError:
            pass
        bridge.audio_session(WsConn(sock))

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path == "/api/audio":
            self._audio_upgrade()
            return
        bridge = self.server.bridge
        # files the browser needs to install the page as an app (nothing private in them)
        if path == "/manifest.webmanifest":
            self._send(200, WEB_MANIFEST, "application/manifest+json")
            return
        if path in ("/icon-512.png", "/favicon.ico"):
            self._send(200, bridge.icon, "image/png")
            return
        if path == "/sw.js":
            self._send(200, WEB_SW, "text/javascript")
            return
        if not self._authed():
            if path in ("/", "/index.html"):
                self._login_page()
            else:
                self._send(401, b'{"error":"sign in"}')
            return
        if path in ("/", "/index.html"):
            self._send(200, bridge.page, "text/html; charset=utf-8")
        elif path == "/api/state":
            with bridge.lock:
                body = bridge.state_json
            self._send(200, body)
        elif path == "/api/memories":
            with bridge.lock:
                body = bridge.mem_json
            self._send(200, body)
        else:
            self._send(404, b'{"error":"not found"}')

    do_HEAD = do_GET

    def do_POST(self):
        if self.path.split("?", 1)[0] == "/login":
            self._do_login()
            return
        if not self._authed():
            self._send(401, b'{"error":"sign in"}')
            return
        if self.path.split("?", 1)[0] != "/api/cmd":
            self._send(404, b'{"error":"not found"}')
            return
        # Only our own page may send commands: other web sites can't add this header without permission
        if self.headers.get("X-RIG") != "1" or not self._origin_ok():
            self._send(403, b'{"error":"forbidden"}')
            return
        try:
            n = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            n = -1
        if not 0 < n <= 4096:
            self._send(413, b'{"error":"bad length"}')
            return
        try:
            cmd = json.loads(self.rfile.read(n).decode("utf-8"))
        except Exception:
            cmd = None
        if not isinstance(cmd, dict) or not isinstance(cmd.get("a"), str):
            self._send(400, b'{"error":"bad command"}')
            return
        self.server.bridge.app.ui(self.server.bridge.app.web_command, cmd)   # runs on the Tk thread
        self._send(200, b'{"ok":true}')


class WebBridge:
    """Runs the phone page's web server on its own threads. It never touches Tk: it serves a snapshot
    the Tk thread publishes, and hands commands to the Tk thread through app.ui()."""

    def __init__(self, app):
        self.app = app
        self.lock = threading.Lock()
        self.state_json = b'{"online":false,"toggles":{},"levels":{}}'
        self.mem_json = b"[]"
        self.page = b""
        self.httpd = None
        self.thread = None
        self.port = None
        self.password = ""
        self.error = ""
        self.audio_token = ""
        self.cookie_token = ""
        self.icon = b""
        self.sessions = set()
        self.httpsd = None
        self.https_port = None
        self.https_url = ""
        self.https_error = ""

    @property
    def running(self):
        return self.httpd is not None

    def start_https(self, port, certfile, keyfile, name):
        """The same page on https, with the PC's own Tailscale certificate (phones need https for the mic)."""
        self.stop_https()
        if self.httpd is None:
            return False
        try:
            ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            ctx.minimum_version = ssl.TLSVersion.TLSv1_2
            ctx.load_cert_chain(certfile, keyfile)
            httpsd = _WebServer(("0.0.0.0", port), _WebHandler)
            # handshake on the connection's own thread, so one slow phone can't hold up the others
            httpsd.socket = ctx.wrap_socket(httpsd.socket, server_side=True, do_handshake_on_connect=False)
        except (OSError, ssl.SSLError, ValueError) as e:
            self.https_error = str(e)
            return False
        httpsd.bridge = self
        self.httpsd, self.https_port, self.https_error = httpsd, port, ""
        self.https_url = f"https://{name}:{port}/"
        threading.Thread(target=httpsd.serve_forever, kwargs={"poll_interval": 0.5}, daemon=True).start()
        return True

    def stop_https(self):
        httpsd, self.httpsd, self.https_port, self.https_url = self.httpsd, None, None, ""
        if httpsd is not None:
            try:
                httpsd.shutdown()
                httpsd.server_close()
            except Exception:
                pass

    def start(self, port, password, secret=""):
        self.stop()
        self.password = password
        # sign-in cookie: changes when the password changes, so a new password signs every phone out
        self.cookie_token = hmac.new((secret or "ftdx10").encode(), password.encode("utf-8"), hashlib.sha256).hexdigest()
        try:
            self.icon = app_icon_png()
            self.page = web_page_bytes()
            httpd = _WebServer(("0.0.0.0", port), _WebHandler)
        except OSError as e:
            self.error = str(e)
            return False
        httpd.bridge = self
        self.audio_token = secrets.token_urlsafe(18)
        self.httpd, self.port, self.error = httpd, port, ""
        self.thread = threading.Thread(target=httpd.serve_forever, kwargs={"poll_interval": 0.5}, daemon=True)
        self.thread.start()
        return True

    def stop(self):
        self.stop_https()
        httpd, self.httpd, self.port = self.httpd, None, None
        self.audio_token = ""
        with self.lock:
            sessions = list(self.sessions)
        for sess in sessions:
            sess.close()
        if httpd is not None:
            try:
                httpd.shutdown()
                httpd.server_close()
            except Exception:
                pass

    def audio_session(self, ws):
        """Runs on the connection's own thread until the phone disconnects."""
        app, eng = self.app, self.app.audio
        sess = AudioSession(ws)
        with self.lock:
            self.sessions.add(sess)
        ptt = False
        now = time.time()
        last_rx = last_audio = now
        err_sent = ""
        try:
            if eng is None:
                ws.send_json({"err": "Audio isn't set up on the PC: run  py -m pip install sounddevice  there "
                                     "and restart FTDX10 Monitor."})
            else:
                err = eng.add_listener(sess)
                if err:
                    ws.send_json({"err": err})
            while not sess.closed:
                try:
                    op, data = ws.recv()
                except socket.timeout:
                    op, data = None, b""
                now = time.time()
                if op == 0x8:
                    break
                if op is not None:
                    last_rx = now
                if op == 0x9:
                    ws.send(0xA, data)
                elif op == 0x2 and ptt and eng is not None:
                    last_audio = now
                    err = eng.feed(sess, data)
                    if err and err != err_sent:
                        err_sent = err
                        ws.send_json({"err": err})
                elif op == 0x1 and eng is not None:
                    try:
                        msg = json.loads(data.decode("utf-8"))
                    except Exception:
                        msg = None
                    if isinstance(msg, dict) and "ptt" in msg and bool(msg["ptt"]) != ptt:
                        ptt, last_audio = bool(msg["ptt"]), now
                        app.ui(app.web_ptt, ptt)
                if ptt and now - last_audio > 1.5:      # microphone audio stopped: never leave the rig keyed
                    ptt = False
                    app.ui(app.web_ptt, False)
                    ws.send_json({"ptt_drop": True})
                if now - last_rx > 12:                  # phone vanished without closing
                    break
        except (ConnectionError, OSError, ValueError):
            pass
        finally:
            if ptt:
                app.ui(app.web_ptt, False)
            if eng is not None:
                eng.remove_listener(sess)
            sess.close()
            with self.lock:
                self.sessions.discard(sess)

    def publish(self, state, mems=None):
        data = json.dumps(state, separators=(",", ":")).encode("utf-8")
        mdata = json.dumps(mems, separators=(",", ":")).encode("utf-8") if mems is not None else None
        with self.lock:
            self.state_json = data
            if mdata is not None:
                self.mem_json = mdata




# -----------------------------------------------------------------
# 5. MAIN APPLICATION
# -----------------------------------------------------------------
class FTDX10Controller:
    def __init__(self, root):
        self.root = root
        init_fonts(root)
        self.root.title(f"{RIG_TITLE} Monitor : By {APP_AUTHOR}")
        self.config = load_config()
        self.root.configure(bg=BG, highlightthickness=px(3), highlightbackground=BG, highlightcolor=BG)
        res_dir = getattr(sys, "_MEIPASS", BASE_DIR)
        try:
            self.root.iconbitmap(default=os.path.join(res_dir, "ftdx10.ico"))
        except Exception:
            try:
                self._icon_img = tk.PhotoImage(file=os.path.join(res_dir, "ftdx10.png"))
                self.root.iconphoto(True, self._icon_img)
            except Exception:
                pass

        self.ser = None
        self.running = False
        self.want_connect = True
        self.io_error = False
        self.io_lock = threading.Lock()
        self.cmdq = queue.Queue()
        self.uiq = queue.Queue()       # callbacks from the polling thread to the Tk thread
        self.poll_thread = None
        self.port_name = ""
        self.baud = self.config.get("baud", 38400)
        self.rig_name = ""

        self.is_tx = False
        self.flash_on = False
        self.swr_sev = 0
        self.pwr_frac = 0.0
        self.rx_busy = False
        self.cur_hz = None
        self.cur_mode = None
        self.vfo_mode = "0"
        self.mem_ch = ""
        self.tune_time = 0.0
        self.mode_time = 0.0
        self.mode_refresh = False
        self.pending_hz = None
        self.freq_queued = False
        self.pending_levels = {}
        self.level_touch = {}
        self.level_vals = {p: None for _, p, *_ in LEVELS}
        self._lvl_guard = False
        self.full_sync = True
        self.toggle_state = {k: None for k in TOGGLES}
        self.toggle_touch = {}
        self.toggle_btns = {k: [] for k in TOGGLES}
        self.dup_state = None          # repeater shift 0 / 1 (+) / 2 (-)
        self.dup_touch = 0.0
        self.rit_hz = 0
        self.ptt_on = False
        self.ptt_since = 0.0
        self.status_hold = 0.0
        self.link_ok = True
        self.tx_vfo_b = False

        self.meter_frac = 0.0
        self.meter_mode = "rx"
        self.peak_frac = 0.0
        self.peak_time = 0.0
        self.tx_text = {}
        self.scan = None
        self.sweep = None
        self._sweep_drawn = 0.0
        self.qso_log = load_qso_log()
        self.rxbuf = bytearray()
        self.hover_digit = None
        self.digit_hits = []
        self.freq_color = LCD_TEXT
        self._freq_key = None
        self._pending_draw = set()
        self.sub_hz = None             # VFO-B
        self.sub_mode = None
        self.sub_nak = 0
        self.memread = None
        self.memread_win = None

        self.slow_reads = [(k, (lambda k=k: self.read_toggle(k))) for k in TOGGLES]
        self.slow_reads += [("dup", self.read_shift), ("tone_hz", self.read_tone), ("ftx", self.read_ftx)]
        self.slow_idx = 0
        # Phone / browser access
        self.web = WebBridge(self)
        self.audio = AudioEngine(self) if AUDIO_READY else None
        self.atu_busy = False                 # a TUNE started from here is running
        self.atu_tuning = False               # the radio reports it is tuning (AC002)
        self.cwdec = CwDecoder(self)
        self.cwd_win = None
        self.cwdec.on_text = self.cwd_append
        self.web_keyed = False
        self.sql_live = (None, 0.0)          # (squelch open?, when) straight from the polling thread
        self.web_mem_dirty = True
        self.web_mem_rev = 0

        self.setup_styles()
        self.create_menu()
        self.create_widgets()
        self.fit_window()
        self.root.attributes("-topmost", bool(self.config.get("topmost")))
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.root.bind("<Up>", lambda e: self.key_step(+1))
        self.root.bind("<Down>", lambda e: self.key_step(-1))
        self.root.bind("<Prior>", lambda e: self.key_step(+1, 1_000_000))
        self.root.bind("<Next>", lambda e: self.key_step(-1, 1_000_000))

        self.flash_tx()
        self.clock_tick()
        self.ui_pump()

        if not SERIAL_READY:
            self.root.after(300, self.show_lib_error)
        else:
            self.root.after(100, lambda: self.auto_connect(quiet=False))
            self.root.after(RECONNECT_MS, self.reconnect_tick)
        self.start_web(quiet=True)
        self.root.after(500, self.web_tick)

    # ------------------------------------------------------------- setup
    def toggle_button(self, parent, key, width=40, height=26):
        label = TOGGLES[key][0]
        tone = "amber" if key in ("lock", "att") else "accent"
        b = RoundButton(parent, label, lambda: self.click_toggle(key), width=width, height=height, tone=tone)
        self.toggle_btns[key].append(b)
        return b

    def create_menu(self):
        menubar = tk.Menu(self.root)
        settings_menu = tk.Menu(menubar, tearoff=0)
        settings_menu.add_command(label="Settings...", command=self.open_settings)
        settings_menu.add_command(label="Phone access...", command=self.open_web_settings)
        settings_menu.add_command(label="Reconnect", command=self.user_reconnect)
        settings_menu.add_command(label="Disconnect", command=lambda: self.disconnect(user=True))
        settings_menu.add_separator()
        settings_menu.add_command(label="Re-read radio state", command=self.request_full_sync)
        menubar.add_cascade(label="Settings", menu=settings_menu)
        view_menu = tk.Menu(menubar, tearoff=0)
        self.topmost_var = tk.BooleanVar(value=bool(self.config.get("topmost")))
        view_menu.add_checkbutton(label="Always on top", variable=self.topmost_var,
                                  command=self.toggle_topmost)
        size_menu = tk.Menu(view_menu, tearoff=0)
        self.freq_size_var = tk.StringVar(value=self.config.get("freq_size", "Medium"))
        for name in FREQ_SIZES:
            size_menu.add_radiobutton(label=name, value=name, variable=self.freq_size_var,
                                      command=self.change_freq_size)
        view_menu.add_cascade(label="Frequency size", menu=size_menu)
        view_menu.add_separator()
        view_menu.add_command(label="CW decoder...", command=self.open_cw_decoder)
        menubar.add_cascade(label="View", menu=view_menu)
        phone_menu = tk.Menu(menubar, tearoff=0)
        phone_menu.add_command(label="Phone access, audio (RX / TX) && HTTPS...", command=self.open_web_settings)
        phone_menu.add_command(label="Turn on HTTPS (for the phone microphone)",
                               command=lambda: self.setup_https(self.root, lambda: None))
        phone_menu.add_separator()
        phone_menu.add_command(label="Open the phone page on this PC", command=self.open_phone_page)
        menubar.add_cascade(label="Phone", menu=phone_menu)
        menubar.add_command(label="About", command=self.show_about)
        self.root.config(menu=menubar)

    def show_about(self):
        win = tk.Toplevel(self.root)
        win.title("About")
        win.configure(bg=BG)
        win.resizable(False, False)
        win.transient(self.root)
        self.lbl(win, f"{RIG_TITLE} Monitor", font=F["big"]).pack(padx=50, pady=(22, 4))
        self.lbl(win, "Yaesu CAT control panel", fg=MUTED).pack()
        self.lbl(win, f"Version {APP_VERSION}", fg=ACCENT).pack(pady=(10, 2))
        self.lbl(win, f"Author: {APP_AUTHOR}", fg=ACCENT).pack(pady=2)
        self.lbl(win, "Wheel over a digit tunes that digit  ·  PgUp/PgDn = 1 MHz",
                 fg=MUTED, font=F["small"]).pack(pady=(10, 0), padx=16)
        self.btn(win, "OK", win.destroy, width=90).pack(pady=(14, 18))
        win.update_idletasks()
        x = self.root.winfo_rootx() + (self.root.winfo_width() - win.winfo_width()) // 2
        win.geometry(f"+{max(x, 0)}+{max(self.root.winfo_rooty() + 80, 0)}")
        win.grab_set()
        win.focus_set()
        win.bind("<Return>", lambda e: win.destroy())
        win.bind("<Escape>", lambda e: win.destroy())

    # ------------------------------------------------------------ layout
    def create_widgets(self):
        sbar = tk.Frame(self.root, bg=PANEL2, highlightthickness=1, highlightbackground=BORDER)
        sbar.pack(side=tk.BOTTOM, fill="x")
        self.lbl_led = tk.Canvas(sbar, width=px(10), height=px(10), bg=PANEL2, highlightthickness=0)
        self.lbl_led.pack(side="left", padx=(px(8), px(4)), pady=px(5))
        self.lbl_status = tk.Label(sbar, text="SYSTEM OFFLINE", bg=PANEL2, fg=MUTED, font=F["small_b"], anchor="w")
        self.lbl_status.pack(side="left", fill="x", expand=True)
        self.lbl_port = tk.Label(sbar, text="", bg=PANEL2, fg=DIM, font=F["small_b"])
        self.lbl_port.pack(side="right", padx=8)

        head = tk.Frame(self.root, bg=BG)
        head.pack(fill="x", padx=px(16), pady=(px(8), px(2)))
        self.btn_power = RoundButton(head, "POWER", self.power_click, width=74, height=26, tone="green")
        self.btn_power.pack(side="left", padx=(0, px(12)))
        tk.Label(head, text="F T D X 1 0", bg=BG, fg="#cfd4db", font=F["model"]).pack(side="left")
        tk.Label(head, text="  HF/50/70 MHz TRANSCEIVER", bg=BG, fg=DIM,
                 font=F["small_b"]).pack(side="left", pady=(px(4), 0))
        tk.Label(head, text=f"MONITOR {APP_VERSION} · {APP_AUTHOR}", bg=BG, fg=DIM,
                 font=F["small_b"]).pack(side="right", pady=(px(4), 0))

        bezel = tk.Frame(self.root, bg="#0c0d0f", highlightthickness=1, highlightbackground=LCD_EDGE)
        bezel.pack(fill="x", padx=px(12), pady=(px(2), px(6)))
        scr = tk.Frame(bezel, bg=LCD_BG)
        scr.pack(fill="both", expand=True, padx=px(5), pady=px(5))
        self.screen = scr

        def sep():
            tk.Frame(scr, bg=LCD_SEP, height=1).pack(fill="x", padx=px(4))

        self.status_canvas = tk.Canvas(scr, height=px(20), bg=LCD_BG, highlightthickness=0)
        self.status_canvas.pack(fill="x")
        self.status_canvas.bind("<Configure>", lambda e: self.draw_status())
        self.clock_text = "--:--"
        sep()

        tag_row = tk.Frame(scr, bg=LCD_BG)
        tag_row.pack(fill="x", pady=(px(4), 0))
        self.tags_canvas = tk.Canvas(tag_row, height=px(20), bg=LCD_BG, highlightthickness=0)
        self.tags_canvas.pack(side="left", fill="x", expand=True)
        self.tags_canvas.bind("<Configure>", lambda e: self.draw_tags())
        self.btn_vfo = RoundButton(tag_row, "A ⇄ B", self.swap_bands, width=70, height=20,
                                   font=F["lcd_s"], radius=4, style="soft")
        self.btn_vfo.pack(side="right", padx=px(6))

        def tag(text, tone="accent", solid=False, hide_off=True):
            return LcdTag(lambda: self.schedule("draw_tags"), text, tone, solid, hide_off)

        self.chip_main = tag("VFO-A", solid=True, hide_off=False)
        self.chip_main.active = True
        self.chip_mode = tag("--", hide_off=False)
        self.chip_fil = tag("NAR")
        self.chip_band = tag("BAND")
        self.chip_dup = tag("SPLIT", "amber")
        self.chip_sat = tag("RIT")
        self.chip_scan = tag("SCAN", "amber", solid=True)
        self.chip_busy = tag("BUSY", "green", solid=True)
        self.chip_tx = tag("TX", "red", solid=True)

        self.freq_canvas = tk.Canvas(scr, bg=LCD_BG, highlightthickness=0,
                                     height=F["freq"].metrics("linespace") + px(2))
        self.freq_canvas.pack(fill="x", padx=px(4), pady=(0, px(4)))
        self.freq_canvas.bind("<Configure>", lambda e: self.draw_freq(force=True))
        self.freq_canvas.bind("<MouseWheel>", lambda e: self.freq_wheel(e.x, 1 if e.delta > 0 else -1))
        self.freq_canvas.bind("<Button-4>", lambda e: self.freq_wheel(e.x, 1))
        self.freq_canvas.bind("<Button-5>", lambda e: self.freq_wheel(e.x, -1))
        self.freq_canvas.bind("<Motion>", self.freq_hover)
        self.freq_canvas.bind("<Leave>", lambda e: self.freq_hover(None))
        self.freq_canvas.bind("<Button-1>", lambda e: self.focus_freq_entry())

        self.meter_canvas = tk.Canvas(scr, height=px(56), bg=LCD_BG, highlightthickness=0)
        self.meter_canvas.pack(fill="x", padx=px(4))
        self.meter_canvas.bind("<Configure>", self.draw_meter)

        read_row = tk.Frame(scr, bg=LCD_BG)
        read_row.pack(fill="x", padx=px(12))
        self.lbl_smeter = tk.Label(read_row, text="", font=F["mono_b"], bg=LCD_BG, fg=LCD_TEXT)
        self.lbl_smeter.pack(side="left")
        self.lbl_info = tk.Label(read_row, text="", font=F["mono_b"], bg=LCD_BG, fg=LCD_LABEL)
        self.lbl_info.pack(side="right")
        sep()

        self.sub_canvas = tk.Canvas(scr, height=F["sub"].metrics("ascent") + px(10), bg=LCD_BG, highlightthickness=0, cursor="hand2")
        self.sub_canvas.pack(fill="x", padx=px(4))
        self.sub_canvas.bind("<Configure>", lambda e: self.draw_sub())
        self.sub_canvas.bind("<Double-Button-1>", lambda e: self.swap_bands())
        sep()

        self.levels_canvas = tk.Canvas(scr, height=px(20), bg=LCD_BG, highlightthickness=0)
        self.levels_canvas.pack(fill="x", padx=px(6), pady=(px(1), 0))
        self.levels_canvas.bind("<Configure>", self.draw_levels)

        tabbar = tk.Frame(scr, bg=LCD_BG)
        tabbar.pack(fill="x", padx=px(3), pady=(px(4), px(3)))
        self.tab_btns = {}
        for i, name in enumerate(TABS):
            tabbar.columnconfigure(i, weight=1, uniform="t")
            b = RoundButton(tabbar, name, lambda n=name: self.show_tab(n), width=40, height=24,
                            font=F["lcd_s"], radius=4, style="soft")
            b.grid(row=0, column=i, padx=px(1), sticky="ew")
            self.tab_btns[name] = b

        qf = tk.Frame(self.root, bg=BG)
        qf.pack(fill="x", padx=px(12), pady=(0, px(6)))
        keys = ["amp", "att", "agc", "nb", "nr", "anf", "nar", "lock"]
        for i, k in enumerate(keys):
            qf.columnconfigure(i, weight=1, uniform="q")
            self.toggle_button(qf, k, width=40, height=30).grid(row=0, column=i, padx=px(2), sticky="ew")
        qf.columnconfigure(len(keys), weight=2, uniform="q")
        self.btn_ptt = RoundButton(qf, "TRANSMIT", self.toggle_ptt, width=70, height=30, tone="red", solid=True,
                                   font=F["ui_b"])
        self.btn_ptt.grid(row=0, column=len(keys), padx=(px(6), px(2)), sticky="ew")

        stack = self.card(self.root, fill="both", expand=True, padx=px(12), pady=(0, px(8)))
        stack.rowconfigure(0, weight=1)
        stack.columnconfigure(0, weight=1)
        self.pages = {}
        for name in TABS:
            f = tk.Frame(stack, bg=PANEL)
            f.grid(row=0, column=0, sticky="nsew")
            self.pages[name] = f
        self.build_tune_tab(self.pages["TUNE"])
        self.build_levels_tab(self.pages["LEVELS"])
        self.build_vfo_tab(self.pages["VFO"])
        self.build_func_tab(self.pages["FUNC"])
        self.build_cw_tab(self.pages["CW"])
        self.build_memory_tab(self.pages["MEMORY"])
        self.build_scan_tab(self.pages["SCAN"])
        self.build_log_tab(self.pages["LOG"])
        self.cur_tab = None
        self.show_tab(self.config.get("tab", "TUNE"))
        self.update_port_label()
        self.set_led(MUTED)

    # ---------------------------------------------------------- tune tab
    def build_tune_tab(self, tab):
        self.caption(tab, "Mode").pack(anchor="w", padx=px(12), pady=(px(8), 0))
        mf = tk.Frame(tab, bg=PANEL)
        mf.pack(fill="x", padx=px(9), pady=(px(3), 0))
        self.mode_btns = {}
        cols = 7
        for i in range(cols):
            mf.columnconfigure(i, weight=1, uniform="m")
        for i, m in enumerate(MODE_LIST):
            b = self.btn(mf, m, lambda mm=m: self.set_radio_mode(mm), width=40)
            b.grid(row=i // cols, column=i % cols, padx=px(2), pady=px(2), sticky="ew")
            self.mode_btns[m] = b

        self.caption(tab, "Band").pack(anchor="w", padx=px(12), pady=(px(8), 0))
        bf = tk.Frame(tab, bg=PANEL)
        bf.pack(fill="x", padx=px(9), pady=(px(3), 0))
        self.band_btns = {}
        for i, (name, *_) in enumerate(BANDS):
            bf.columnconfigure(i % 6, weight=1, uniform="b")
            b = self.btn(bf, name, lambda n=name: self.band_click(n), width=40)
            b.grid(row=i // 6, column=i % 6, padx=px(2), pady=px(2), sticky="ew")
            self.band_btns[name] = b

        self.caption(tab, "Tuning").pack(anchor="w", padx=px(12), pady=(px(8), 0))
        row = tk.Frame(tab, bg=PANEL)
        row.pack(fill="x", padx=px(12), pady=(px(3), px(6)))
        self.lbl(row, "Step").pack(side="left")
        self.step_var = tk.StringVar()
        step_box = ttk.Combobox(row, textvariable=self.step_var, state="readonly", width=8,
                                values=[s[0] for s in STEPS], font=F["ui"])
        step_box.pack(side="left", padx=px(6))
        saved = self.config.get("step_hz", 1000)
        self.step_var.set(next((n for n, v in STEPS if v == saved), "1 kHz"))
        step_box.bind("<<ComboboxSelected>>", lambda e: self.config.update(step_hz=self.step_hz()))
        self.btn(row, "▼", lambda: self.step_tune(-1), width=34).pack(side="left", padx=px(2))
        self.btn(row, "▲", lambda: self.step_tune(+1), width=34).pack(side="left", padx=px(2))
        self.btn(row, "SET", self.change_frequency, width=50, tone="green").pack(side="right", padx=(px(6), 0))
        self.lbl(row, "MHz", fg=MUTED).pack(side="right")
        self.freq_entry = self.entry(row, width=12, justify="center")
        self.freq_entry.config(font=F["mono_b"])
        self.freq_entry.pack(side="right", padx=px(6), ipady=px(3))
        self.freq_entry.bind("<Return>", lambda event: self.change_frequency())

    # -------------------------------------------------------- levels tab
    def build_levels_tab(self, tab):
        grid = tk.Frame(tab, bg=PANEL)
        grid.pack(fill="both", expand=True, padx=px(8), pady=px(6))
        for c in (1, 4):
            grid.columnconfigure(c, weight=1)
        grid.columnconfigure(3, minsize=px(14))
        self.level_scales = {}
        self.level_labels = {}
        half = 7
        for i, (name, prefix, digits, lo, hi, fmt) in enumerate(LEVELS):
            col = 0 if i < half else 3
            row = i if i < half else i - half
            color = AMBER if prefix in ("PC", "MG", "PL", "VG", "ML1") else ACCENT
            self.lbl(grid, name, fg=MUTED, font=F["small"], anchor="w", width=10).grid(
                row=row, column=col, sticky="w", padx=(px(4), 0), pady=px(1))
            sc = LevelSlider(grid, command=lambda v, p=prefix: self.on_level(p, v), maxval=hi - lo,
                             center=(fmt == "shift"), color=color)
            sc.grid(row=row, column=col + 1, sticky="ew")
            if fmt == "shift":
                sc.bind("<Double-Button-1>", lambda e, s=sc: s._apply(1200))
            lb = tk.Label(grid, text="--", width=7, anchor="e", bg=PANEL, fg=TEXT, font=F["mono_s"])
            lb.grid(row=row, column=col + 2, padx=(0, px(4)))
            self.level_scales[prefix] = sc
            self.level_labels[prefix] = lb
        self.lbl(tab, "Double-click the IF SHIFT slider to centre it  ·  mouse wheel fine-adjusts",
                 fg=DIM, font=F["small"]).pack(side="bottom", pady=(0, px(6)))

    # ----------------------------------------------------------- vfo tab
    def build_vfo_tab(self, tab):
        self.caption(tab, "VFO A / B").pack(anchor="w", padx=px(12), pady=(px(8), 0))
        self.grid_row(tab, [("A ⇄ B", self.swap_bands),
                            ("A → B", lambda: self.cat_status("AB;", "VFO-A COPIED TO VFO-B")),
                            ("B → A", lambda: self.cat_status("BA;", "VFO-B COPIED TO VFO-A")),
                            ("RX on A", lambda: self.cat_status("VS0;", "VFO-A SELECTED")),
                            ("RX on B", lambda: self.cat_status("VS1;", "VFO-B SELECTED"))])
        self.caption(tab, "Split / transmit VFO").pack(anchor="w", padx=px(12), pady=(px(8), 0))
        sr = tk.Frame(tab, bg=PANEL)
        sr.pack(fill="x", padx=px(10), pady=px(3))
        for i in range(4):
            sr.columnconfigure(i, weight=1, uniform="s")
        self.toggle_button(sr, "split").grid(row=0, column=0, padx=px(3), sticky="ew")
        self.btn_txa = self.btn(sr, "TX on A", lambda: self.set_tx_vfo(False), width=40)
        self.btn_txa.grid(row=0, column=1, padx=px(3), sticky="ew")
        self.btn_txb = self.btn(sr, "TX on B", lambda: self.set_tx_vfo(True), width=40)
        self.btn_txb.grid(row=0, column=2, padx=px(3), sticky="ew")
        self.btn(sr, "Split +5 kHz", lambda: self.cat_status("ST2;", "SPLIT ON, B = A + 5 kHz"),
                 width=40).grid(row=0, column=3, padx=px(3), sticky="ew")

        self.caption(tab, "FM repeater shift (FM mode)").pack(anchor="w", padx=px(12), pady=(px(8), 0))
        _, b = self.grid_row(tab, [("Simplex", lambda: self.set_duplex(0)),
                                   ("+ shift", lambda: self.set_duplex(1)),
                                   ("- shift", lambda: self.set_duplex(2))])
        self.dup_btns = dict(zip((0, 1, 2), b))

        self.caption(tab, "CTCSS").pack(anchor="w", padx=px(12), pady=(px(8), 0))
        tr = tk.Frame(tab, bg=PANEL)
        tr.pack(fill="x", padx=px(12), pady=px(3))
        self.toggle_button(tr, "ctcss", width=90).pack(side="left")
        self.lbl(tr, "OFF → TONE (encode) → TSQL (enc/dec)", fg=DIM, font=F["small"]).pack(side="left", padx=px(8))
        self.lbl(tr, "Hz", fg=MUTED).pack(side="right")
        self.tone_var = tk.StringVar(value="88.5")
        tb = ttk.Combobox(tr, textvariable=self.tone_var, state="readonly", width=6,
                          values=[f"{t:.1f}" for t in CTCSS], font=F["ui"])
        tb.pack(side="right", padx=px(4))
        tb.bind("<<ComboboxSelected>>", lambda e: self.set_tone(self.tone_var.get()))
        self.lbl(tr, "Tone").pack(side="right")

    # ---------------------------------------------------------- func tab
    def build_func_tab(self, tab):
        self.caption(tab, "Receive").pack(anchor="w", padx=px(12), pady=(px(8), 0))
        fr = tk.Frame(tab, bg=PANEL)
        fr.pack(fill="x", padx=px(10), pady=px(3))
        for i, k in enumerate(["amp", "att", "agc", "nb", "nr", "anf", "nar"]):
            fr.columnconfigure(i, weight=1, uniform="fr")
            self.toggle_button(fr, k).grid(row=0, column=i, padx=px(2), sticky="ew")

        th = tk.Frame(tab, bg=PANEL)
        th.pack(fill="x", padx=px(12), pady=(px(8), 0))
        self.caption(th, "Transmit").pack(side="left")
        self.lbl(th, "ATU: click = tune  \u00b7  right-click = tuner off", fg=MUTED,
                 font=F["small"]).pack(side="right")
        ft = tk.Frame(tab, bg=PANEL)
        ft.pack(fill="x", padx=px(10), pady=px(3))
        for i, k in enumerate(["proc", "vox", "mon", "bkin", "keyer", "lock"]):
            ft.columnconfigure(i, weight=1, uniform="ft")
            self.toggle_button(ft, k).grid(row=0, column=i, padx=px(2), sticky="ew")
        ft.columnconfigure(6, weight=1, uniform="ft")
        # ATU: a click starts the radio's tuning cycle (AC002); right-click switches the tuner off
        self.btn_tune = self.btn(ft, "ATU", self.atu_tune, width=40, tone="amber")
        self.btn_tune.grid(row=0, column=6, padx=px(2), sticky="ew")
        self.btn_tune.bind("<Button-3>", lambda e: self.atu_off())

        self.caption(tab, "Clarifier (RIT / XIT)").pack(anchor="w", padx=px(12), pady=(px(8), 0))
        rr = tk.Frame(tab, bg=PANEL)
        rr.pack(fill="x", padx=px(12), pady=px(3))
        self.toggle_button(rr, "rit", width=50).pack(side="left")
        self.toggle_button(rr, "xit", width=50).pack(side="left", padx=(px(4), 0))
        self.btn(rr, "−50", lambda: self.nudge_rit(-50), width=42).pack(side="left", padx=(px(10), px(2)))
        self.btn(rr, "−10", lambda: self.nudge_rit(-10), width=42).pack(side="left", padx=px(2))
        self.lbl_rit = tk.Label(rr, text="+0 Hz", width=8, bg=FIELD, fg=ACCENT, font=F["mono_b"],
                                highlightthickness=1, highlightbackground=BORDER)
        self.lbl_rit.pack(side="left", padx=px(4), ipady=px(3))
        self.lbl_rit.bind("<MouseWheel>", lambda e: self.nudge_rit(10 if e.delta > 0 else -10))
        self.lbl_rit.bind("<Button-4>", lambda e: self.nudge_rit(10))
        self.lbl_rit.bind("<Button-5>", lambda e: self.nudge_rit(-10))
        self.btn(rr, "+10", lambda: self.nudge_rit(10), width=42).pack(side="left", padx=px(2))
        self.btn(rr, "+50", lambda: self.nudge_rit(50), width=42).pack(side="left", padx=px(2))
        self.btn(rr, "CLEAR", lambda: self.set_rit(0), width=54, tone="amber").pack(side="left", padx=px(6))

        orow = tk.Frame(tab, bg=PANEL)
        orow.pack(fill="x", padx=px(12), pady=(px(10), px(3)))
        self.btn(orow, "Re-read radio", self.request_full_sync, width=100).pack(side="right")

    # ------------------------------------------------------------ cw tab
    def build_cw_tab(self, tab):
        self.caption(tab, f"Send CW (rig in CW mode, sent via keyer memory {CW_SLOT})").pack(
            anchor="w", padx=px(12), pady=(px(8), 0))
        row = tk.Frame(tab, bg=PANEL)
        row.pack(fill="x", padx=px(12), pady=px(3))
        self.cw_entry = self.entry(row, width=30)
        self.cw_entry.config(font=F["mono_b"])
        self.cw_entry.pack(side="left", fill="x", expand=True, ipady=px(3))
        self.cw_entry.bind("<Return>", lambda e: self.send_cw(self.cw_entry.get(), clear=True))
        self.btn(row, "SEND", lambda: self.send_cw(self.cw_entry.get(), clear=True), width=60,
                 tone="green").pack(side="left", padx=(px(6), px(2)))

        self.caption(tab, "Macros  ·  {MYCALL}  {CALL} = Log tab callsign").pack(anchor="w", padx=px(12),
                                                                              pady=(px(8), 0))
        mg = tk.Frame(tab, bg=PANEL)
        mg.pack(fill="x", padx=px(12), pady=px(2))
        mg.columnconfigure(1, weight=1)
        mg.columnconfigure(3, weight=1)
        self.macro_entries = []
        for i, text in enumerate(self.config["cw_macros"]):
            r, c = i % 3, (i // 3) * 2
            self.btn(mg, f"M{i + 1}", lambda n=i: self.send_macro(n), width=40).grid(
                row=r, column=c, padx=(0 if c == 0 else px(10), px(4)), pady=px(2))
            e = self.entry(mg, width=18)
            e.insert(0, text)
            e.grid(row=r, column=c + 1, sticky="ew", ipady=px(2))
            e.bind("<FocusOut>", lambda ev: self.save_macros())
            self.macro_entries.append(e)

        pr = tk.Frame(tab, bg=PANEL)
        pr.pack(fill="x", padx=px(12), pady=(px(6), px(4)))
        self.lbl(pr, "Play rig keyer memory", fg=MUTED, font=F["small"]).pack(side="left")
        for n in range(1, CW_SLOT):
            self.btn(pr, str(n), lambda k=n: self.cat_status(f"KY{k};", f"PLAYING KEYER MEMORY {k}"),
                     width=34).pack(side="left", padx=px(2))
        self.btn(pr, "CW DECODER", self.open_cw_decoder, width=96, tone="green").pack(side="right")

    # ------------------------------------------------------- CW decoder window
    def open_cw_decoder(self):
        if self.cwd_win is not None and self.cwd_win.winfo_exists():
            self.cwd_win.deiconify()
            self.cwd_win.lift()
            return
        win = tk.Toplevel(self.root)
        self.cwd_win = win
        win.title("CW Decoder - FTDX10 Monitor")
        win.configure(bg=PANEL)
        win.geometry(self.config.get("cwd_geom") or f"{px(560)}x{px(250)}")
        win.minsize(px(380), px(160))
        if self.config.get("topmost"):
            win.attributes("-topmost", True)
        top = tk.Frame(win, bg=PANEL)
        top.pack(fill="x", padx=px(10), pady=(px(8), px(4)))
        self.cwd_onbtn = self.btn(top, "ON", self.cwd_toggle, width=52, tone="green")
        self.cwd_onbtn.pack(side="left")
        self.cwd_led = tk.Canvas(top, width=px(16), height=px(16), bg=PANEL, highlightthickness=0)
        self.cwd_led.pack(side="left", padx=(px(10), px(4)))
        self.cwd_led.create_oval(px(2), px(2), px(14), px(14), fill=FIELD, outline=BORDER, tags="led")
        self.cwd_bar = tk.Canvas(top, width=px(90), height=px(8), bg=FIELD, highlightthickness=0)
        self.cwd_bar.pack(side="left", padx=px(4))
        self.cwd_bar.create_rectangle(0, 0, 0, px(8), fill=ACCENT, width=0, tags="bar")
        self.cwd_info = self.lbl(top, "", fg=MUTED, font=F["mono_b"], width=17, anchor="w")
        self.cwd_info.pack(side="left", padx=(px(8), 0))
        self.btn(top, "CLEAR", self.cwd_clear, width=56).pack(side="right")
        row2 = tk.Frame(win, bg=PANEL)
        row2.pack(fill="x", padx=px(10), pady=(0, px(5)))
        self.lbl(row2, "Tone", fg=MUTED, font=F["small"]).pack(side="left")
        self.cwd_tone_var = tk.StringVar(value=self.cwdec.tone_mode)
        cb = ttk.Combobox(row2, textvariable=self.cwd_tone_var, values=["Auto", "Rig pitch"], width=9,
                          state="readonly")
        cb.pack(side="left", padx=(px(4), px(14)))
        cb.bind("<<ComboboxSelected>>", lambda e: self.cwd_set_tone())
        self.lbl(row2, "Sensitivity", fg=MUTED, font=F["small"]).pack(side="left")
        self.cwd_sens_var = tk.StringVar(value=self.cwdec.sens)
        cs = ttk.Combobox(row2, textvariable=self.cwd_sens_var, values=CWD_SENS_NAMES, width=8,
                          state="readonly")
        cs.pack(side="left", padx=px(4))
        cs.bind("<<ComboboxSelected>>", lambda e: self.cwd_set_sens(self.cwd_sens_var.get()))
        self.cwd_sens_note = self.lbl(row2, "", fg=MUTED, font=F["small"], anchor="w")
        self.cwd_sens_note.pack(side="left", padx=px(8), fill="x", expand=True)
        body = tk.Frame(win, bg=LCD_BG, highlightthickness=1, highlightbackground=BORDER)
        body.pack(fill="both", expand=True, padx=px(10))
        sb = ttk.Scrollbar(body, orient="vertical")
        txt = tk.Text(body, bg=LCD_BG, fg=LCD_TEXT, font=F["cw"], wrap="word", relief="flat", bd=0,
                      padx=px(8), pady=px(6), insertwidth=0, yscrollcommand=sb.set, cursor="arrow")
        sb.config(command=txt.yview)
        sb.pack(side="right", fill="y")
        txt.pack(side="left", fill="both", expand=True)
        txt.insert("end", self.cwdec.text)
        txt.see("end")
        txt.bind("<Key>", lambda e: None if (e.state & 4 and e.keysym.lower() in ("c", "a")) else "break")
        self.cwd_text = txt
        self.cwd_status = self.lbl(win, "", fg=MUTED, font=F["small"], anchor="w")
        self.cwd_status.pack(fill="x", padx=px(10), pady=(px(3), px(6)))
        win.protocol("WM_DELETE_WINDOW", self.close_cw_decoder)
        self.cwdec.on_text = self.cwd_append
        if not self.cwdec.active:
            self.cwdec.start()
        self.cwd_tick()

    def close_cw_decoder(self):
        win = self.cwd_win
        if win is not None and win.winfo_exists():
            self.config["cwd_geom"] = win.geometry()
            win.destroy()
        self.cwd_win = None
        self.cwdec.stop()

    def cwd_toggle(self):
        if self.cwdec.active:
            self.cwdec.stop()
        else:
            self.cwdec.start()
        self.cwd_tick(once=True)

    def cwd_set_tone(self):
        mode = self.cwd_tone_var.get()
        self.cwdec.tone_mode = mode
        self.config["cwd_tone"] = mode

    def cwd_set_sens(self, name):
        if name not in CWD_SENS_NAMES:
            return
        self.cwdec.sens = name
        self.config["cwd_sens"] = name
        if self.cwd_win is not None and self.cwd_win.winfo_exists():
            self.cwd_sens_var.set(name)

    def cwd_sens_text(self):
        """A few words on what the sensitivity setting is doing."""
        d = self.cwdec
        if d.sens == "Auto":
            return "backed off: static / noise" if d.backoff else "most sensitive, follows the speed"
        return {"Low": "strong signals only", "Normal": "clean signals",
                "High": "weak signals", "Max": "weakest signals; more noise errors"}.get(d.sens, "")

    def cwd_clear(self):
        self.cwdec.clear()
        if self.cwd_win is not None and self.cwd_win.winfo_exists():
            self.cwd_text.delete("1.0", "end")

    def cwd_append(self, ch):
        if self.cwd_win is None or not self.cwd_win.winfo_exists():
            return
        t = self.cwd_text
        at_end = t.yview()[1] > 0.98
        t.insert("end", ch)
        if float(t.index("end-1c").split(".")[0]) > 400:
            t.delete("1.0", "100.0")
        if at_end:
            t.see("end")

    def cwd_tick(self, once=False):
        win = self.cwd_win
        if win is None or not win.winfo_exists():
            return
        d = self.cwdec
        on = d.active
        self.cwd_onbtn.set_active(on, "ON" if on else "OFF", tone="green" if on else "red")
        sig = on and d.snr_ok
        self.cwd_led.itemconfig("led", fill=(GREEN if d.key else ACCENT_DIM) if sig else FIELD)
        w = int(px(90) * (d.level if sig else 0))
        self.cwd_bar.coords("bar", 0, 0, w, px(8))
        self.cwd_info.config(text=f"{d.tone} Hz  {d.wpm()} WPM" if sig else ("waiting for CW" if on else ""))
        if not on:
            st = d.error or "Decoder off"
        elif self.audio is not None and self.audio.in_stream is not None:
            st = f"Listening to {self.audio.in_name}"
            if self.audio.squelched():
                st += " \u00b7 muted: rig squelch is closed"
        else:
            st = (self.audio.error if self.audio is not None else "") or "Opening the radio's audio..."
        self.cwd_status.config(text=st, fg=RED if (not on and d.error) else MUTED)
        self.cwd_sens_note.config(text=self.cwd_sens_text())
        if not once:
            self.root.after(100, self.cwd_tick)

    def send_macro(self, n):
        self.save_macros()
        call = self.qso_call.get().strip().upper() if hasattr(self, "qso_call") else ""
        self.send_cw(expand_macro(self.config["cw_macros"][n], self.config.get("mycall", ""), call))

    def send_cw(self, text, clear=False):
        """Load the text into the rig's keyer memory and play it (50 characters per load)."""
        if not self.running:
            return
        txt = cw_clean(text).strip()
        if not txt:
            return
        if clear:
            self.cw_entry.delete(0, tk.END)
        chunks = [txt[i:i + 50] for i in range(0, len(txt), 50)]
        wpm = self.level_vals.get("KS") or 20

        def job():
            for i, ch in enumerate(chunks):
                self.cat(f"KM{CW_SLOT}{ch};", reply=False)
                self.cat(f"KY{CW_SLOT};", reply=False)
                if i < len(chunks) - 1:
                    time.sleep(len(ch) * 12 / max(4, wpm) + 0.5)   # ~10 dot units per character
            self.ui(self.flash_status, f"CW: {txt}", ACCENT)
        self.post(job)

    # ------------------------------------------------------- memory tab
    def open_memread(self):
        if self.memread_win is not None and self.memread_win.winfo_exists():
            self.memread_win.lift()
            return
        win = tk.Toplevel(self.root)
        self.memread_win = win
        win.title("Read memories from radio")
        win.configure(bg=PANEL)
        win.resizable(False, False)
        win.transient(self.root)
        self.caption(win, "Channels").grid(row=0, column=0, sticky="w", padx=px(14), pady=(px(12), px(2)))
        cf = tk.Frame(win, bg=PANEL)
        cf.grid(row=1, column=0, columnspan=2, sticky="w", padx=px(14))
        self.mr_from = self.spin(cf, 1, 99, 1, 1, width=4)
        self.mr_from.pack(side="left")
        self.lbl(cf, "to", fg=MUTED).pack(side="left", padx=px(6))
        self.mr_to = self.spin(cf, 1, 99, 1, 99, width=4)
        self.mr_to.pack(side="left")
        self.lbl(cf, "(memory channels 001-099)", fg=DIM, font=F["small"]).pack(side="left", padx=px(8))
        self.mr_replace = tk.BooleanVar(value=True)
        self.check(win, "Replace channels read from the radio last time", self.mr_replace).grid(
            row=2, column=0, columnspan=2, sticky="w", padx=px(10), pady=(px(10), 0))
        self.mr_bar = tk.Canvas(win, width=px(360), height=px(14), bg=FIELD, highlightthickness=1,
                                highlightbackground=BORDER)
        self.mr_bar.grid(row=3, column=0, columnspan=2, padx=px(14), pady=(px(12), px(4)), sticky="ew")
        self.mr_label = tk.Label(win, text="Ready. The display keeps updating while reading.", bg=PANEL,
                                 fg=MUTED, font=F["small"], anchor="w")
        self.mr_label.grid(row=4, column=0, columnspan=2, sticky="w", padx=px(14))
        bt = tk.Frame(win, bg=PANEL)
        bt.grid(row=5, column=0, columnspan=2, pady=(px(10), px(14)))
        self.mr_start = self.btn(bt, "Start", self.start_memread, width=90, tone="green")
        self.mr_start.pack(side="left", padx=px(4))
        self.btn(bt, "Stop", self.cancel_memread, width=80, tone="red").pack(side="left", padx=px(4))
        self.btn(bt, "Close", win.destroy, width=80).pack(side="left", padx=px(4))
        self.memread_progress(0, 1, 0)
        win.update_idletasks()
        x = self.root.winfo_rootx() + (self.root.winfo_width() - win.winfo_width()) // 2
        win.geometry(f"+{max(x, 0)}+{self.root.winfo_rooty() + px(120)}")

    def start_memread(self):
        if not self.running:
            messagebox.showinfo("Memories", "Connect to the radio first.", parent=self.memread_win)
            return
        if self.memread is not None:
            return
        try:
            lo, hi = int(self.mr_from.get()), int(self.mr_to.get())
        except ValueError:
            lo, hi = 1, 99
        lo, hi = max(1, min(lo, hi)), min(99, max(lo, hi))
        if self.scan:
            self.stop_scan()
        self.memread = {"todo": deque(range(lo, hi + 1)), "total": hi - lo + 1, "done": 0, "found": [],
                        "cmd": "MT", "errors": 0, "noreply": 0, "cancel": False,
                        "replace": self.mr_replace.get(), "error": ""}
        self.mr_start.set_active(True, "Reading ...")
        self.mr_label.config(text="Reading ...", fg=MUTED)

    def memread_step(self):            # polling thread
        mr = self.memread
        if mr is None:
            return
        for _ in range(4):
            if mr["cancel"] or not mr["todo"]:
                break
            ch = mr["todo"][0]
            ans = self.cat(f"{mr['cmd']}{ch:03d};")
            if ans is None:
                mr["noreply"] += 1
                if mr["noreply"] >= 5 and not mr["found"]:
                    mr["error"] = "no reply from the rig"
                    mr["cancel"] = True
                    break
            elif ans == "?":
                # Empty channel - or the rig doesn't know MT. Ask again with MR (no tag) to tell them apart;
                # only after MR has answered where MT failed twice do we stop trying MT altogether.
                if mr["cmd"] == "MT":
                    alt = self.cat(f"MR{ch:03d};")
                    r = parse_info(alt) if alt and alt != "?" else None
                    if r and r["hz"] > 0:
                        mr["errors"] += 1
                        if mr["errors"] >= 2:
                            mr["cmd"] = "MR"
                        mr["found"].append({"ch": f"M-{ch:03d}", "hz": r["hz"], "mode": r["mode"],
                                            "dup": r["shift"], "tone_mode": r["ctcss"], "name": ""})
            else:
                r = parse_info(ans)
                if r and r["hz"] > 0:
                    mr["found"].append({"ch": f"M-{ch:03d}", "hz": r["hz"], "mode": r["mode"],
                                        "dup": r["shift"], "tone_mode": r["ctcss"], "name": r["tag"]})
            mr["todo"].popleft()
            mr["done"] += 1
        self.ui(self.memread_progress, mr["done"], mr["total"], len(mr["found"]))
        if mr["cancel"] or not mr["todo"]:
            self.memread = None
            self.ui(self.memread_finished, False, mr)

    def memread_finished(self, aborted=False, mr=None):
        win_ok = self.memread_win is not None and self.memread_win.winfo_exists()
        if mr is None:
            if win_ok and aborted:
                self.mr_start.set_active(False, "Start")
            return
        found = mr["found"]
        if found:
            entries = []
            for r in found:
                e = {"name": r["name"] or r["ch"], "hz": r["hz"], "mode": r["mode"], "src": "radio",
                     "ch": r["ch"], "dup": r["dup"], "tone_mode": r["tone_mode"]}
                entries.append(e)
            mems = self.config["memories"]
            if mr["replace"]:
                mems[:] = [m for m in mems if m.get("src") != "radio"]
            mems.extend(entries)
            save_config(self.config)
            self.refresh_mem_tree()
        if mr["error"]:
            msg, col = f"Stopped: {mr['error']}.", RED
        else:
            msg = f"Done: {len(found)} programmed channel(s) imported from {mr['done']} read."
            if mr["cancel"]:
                msg = f"Stopped: {len(found)} channel(s) imported from {mr['done']} read."
            col = GREEN
        if win_ok:
            self.mr_label.config(text=msg, fg=col)
            self.mr_start.set_active(False, "Start")
        self.flash_status(msg.upper(), col, 5)

    def recall_memory(self):
        i, m = self.selected_memory()
        if m is not None:
            self.recall_mem(m)

    def recall_mem(self, m):
        self.request_frequency(m["hz"])
        if m.get("mode") in MODE_REVERSE:
            self.set_radio_mode(m["mode"])
        if m.get("mode") in ("FM", "FM-N", "DATA-FM", "DATA-FM-N"):
            if m.get("dup") in (0, 1, 2):
                self.set_duplex(m["dup"])
            if m.get("tone_mode") in (0, 1, 2):
                self.set_toggle_value("ctcss", m["tone_mode"])

    def select_memory_on_rig(self):
        i, m = self.selected_memory()
        if m is None:
            return
        ch = str(m.get("ch", ""))
        if not ch.startswith("M-"):
            messagebox.showinfo("Memories", "Only channels read from the radio have a rig channel number.\n"
                                            "Use Recall to tune the VFO instead.")
            return
        self.cat_status(f"MC{ch[2:]};", f"RIG MEMORY {ch[2:]} SELECTED")
        self.mode_refresh = True

    # --------------------------------------------------- connection mgmt
    def update_port_label(self):
        web = f" · PHONE :{self.web.port}" if self.web.running else ""
        if self.running:
            self.lbl_port.config(text=f"{self.port_name} · {self.baud} · CAT{web}")
        else:
            self.lbl_port.config(text="CAT" + web)

    def auto_connect(self, quiet=True):
        try:
            ports = list(serial.tools.list_ports.comports())
            names = [p.device for p in ports]
            saved = self.config.get("port", AUTO_PORT)
            sport = None
            if saved != AUTO_PORT:
                if saved in names:
                    sport = saved
                else:
                    self.set_status(f"WAITING FOR {saved} ...", ORANGE)
                    return False
            else:
                # The FTDX10's USB port shows two COM ports; CAT is on the "Enhanced" one
                enh = [p.device for p in ports if "enhanced" in (p.description or "").lower()]
                sport = enh[0] if enh else (names[0] if names else None)
            if not sport:
                self.set_status("NO TRANSCEIVER FOUND - WAITING (plug in / power on the rig)", ORANGE)
                return False
            return self.connect(sport, self.config.get("baud", 38400), quiet=quiet)
        except Exception as e:
            self.set_status("AUTO-CONNECT PORT FAULT", RED)
            if not quiet:
                messagebox.showerror("Error", f"Hardware connection initialization failed:\n{str(e)}")
            return False

    def connect(self, sport, baud=38400, quiet=False):
        self.disconnect()
        try:
            ser = serial.Serial()
            ser.port, ser.baudrate, ser.timeout = sport, baud, 0.3
            ser.bytesize, ser.parity, ser.stopbits = 8, "N", 1
            ser.rts = False            # don't key the rig through RTS / DTR when the port opens
            ser.dtr = False
            ser.open()
            self.ser = ser
        except Exception as e:
            self.ser = None
            self.set_status(f"PORT FAULT ON {sport} - RETRYING", RED)
            if not quiet:
                messagebox.showerror("Error", f"Could not open {sport}:\n{str(e)}")
            return False
        self.want_connect = True
        self.io_error = False
        self.rxbuf.clear()
        self.port_name, self.baud = sport, baud
        self.full_sync = True
        self.rig_name = ""
        self.running = True
        self.link_ok = True
        self.rig_off = False
        self.set_status(f"ONLINE - RIG CONNECTED ON {sport} @ {baud}", GREEN)
        self.update_port_label()
        self.poll_thread = threading.Thread(target=self.poll_radio, daemon=True)
        self.poll_thread.start()
        return True

    def _raw_write(self, text):
        ser = self.ser
        if not ser:
            return
        try:
            ser.write(text.encode("ascii"))
            ser.flush()
        except Exception:
            pass

    def disconnect(self, user=False, lost=False):
        if user:
            self.want_connect = False
        had = self.running or self.ser is not None
        self.running = False
        if self.poll_thread and self.poll_thread.is_alive() and self.poll_thread is not threading.current_thread():
            self.poll_thread.join(timeout=3)
        self.poll_thread = None
        if self.ptt_on or self.is_tx:
            self._raw_write("TX0;")
        self.ptt_on = False
        self.memread = None
        try:
            if self.ser and self.ser.is_open:
                self.ser.close()
        except Exception:
            pass
        self.ser = None
        self.io_error = False
        self.rxbuf.clear()
        while True:
            try:
                self.cmdq.get_nowait()
            except queue.Empty:
                break
        self.freq_queued = False
        self.pending_levels.clear()
        if not (had or user):
            return
        self.is_tx = False
        self.cur_hz = None
        self.cur_mode = None
        self.scan = None
        self.btn_scan.set_active(False, "START SCAN")
        self.set_scan_badge(None)
        if not lost:
            self.set_status("SYSTEM OFFLINE", MUTED)
        self.update_port_label()
        self.draw_freq(force=True)
        self.chip_mode.set_active(False, "--")
        self.chip_fil.set_active(False)
        self.chip_band.set_active(False, "BAND")
        self.chip_main.set_active(True, "VFO-A")
        self.rx_busy = False
        self.meter_mode = "rx"
        self.meter_frac = 0.0
        self.peak_frac = 0.0
        self.lbl_smeter.config(text="", fg=LCD_TEXT)
        self.lbl_info.config(text="")
        self.sub_hz = self.sub_mode = None
        self.draw_sub()
        self.level_vals = {p: None for _, p, *_ in LEVELS}
        self.toggle_state = {k: None for k in TOGGLES}
        for k in TOGGLES:
            self.refresh_toggle(k)
        self.dup_state = None
        self.refresh_duplex()
        self.refresh_mode_buttons()
        self.btn_ptt.set_active(False, "TRANSMIT")
        self.refresh_power()
        self.draw_levels()
        self.draw_meter()
        self.draw_status()
        self.memread_finished(aborted=True)

    def on_close(self):
        self.config["geometry"] = self.root.geometry()
        self.config["step_hz"] = self.step_hz()
        self.save_macros()
        save_config(self.config)
        self.want_connect = False
        self.disconnect(user=True)
        self.web.stop()
        self.cwdec.stop()
        if self.audio is not None:
            self.audio.close()
        self.root.destroy()

    def open_settings(self):
        if not SERIAL_READY:
            messagebox.showerror("Error", "pyserial library missing!\nRun: python -m pip install pyserial")
            return
        win = tk.Toplevel(self.root)
        win.title("Settings")
        win.configure(bg=PANEL)
        win.resizable(False, False)
        win.transient(self.root)
        win.grab_set()

        def row(r, text):
            self.lbl(win, text, fg=MUTED).grid(row=r, column=0, padx=px(14), pady=px(5), sticky="w")

        row(0, "COM port (Enhanced)")
        port_var = tk.StringVar()
        port_box = ttk.Combobox(win, textvariable=port_var, state="readonly", width=40, font=F["ui"])
        port_box.grid(row=0, column=1, padx=px(14), pady=(px(14), px(5)), sticky="w")
        row(1, "CAT rate")
        baud_var = tk.StringVar(value=str(self.config.get("baud", 38400)))
        ttk.Combobox(win, textvariable=baud_var, state="readonly", width=10, font=F["ui"],
                     values=[str(b) for b in BAUD_RATES]).grid(row=1, column=1, padx=px(14), pady=px(5), sticky="w")
        row(2, "My callsign")
        call_entry = self.entry(win, width=12)
        call_entry.grid(row=2, column=1, padx=px(14), pady=px(5), sticky="w", ipady=px(2))
        call_entry.insert(0, self.config.get("mycall", ""))
        row(3, "TX time-out (s)")
        tot = self.spin(win, 10, 600, 10, self.config.get("tx_timeout", 180), width=6)
        tot.grid(row=3, column=1, padx=px(14), pady=px(5), sticky="w")
        self.lbl(win, "Match the CAT RATE set in the radio's menu.", fg=DIM, font=F["small"]).grid(
            row=4, column=0, columnspan=2, padx=px(14), sticky="w")

        def refresh_ports(select=None):
            entries = [AUTO_PORT]
            for p in sorted(serial.tools.list_ports.comports(), key=lambda x: x.device):
                entries.append(f"{p.device} - {p.description}")
            port_box["values"] = entries
            wanted = select or self.config.get("port", AUTO_PORT)
            choice = entries[0]
            for e in entries:
                if e.split(" - ")[0] == wanted:
                    choice = e
                    break
            port_var.set(choice)

        def apply_settings():
            port = port_var.get().split(" - ")[0]
            try:
                baud = int(baud_var.get())
            except ValueError:
                baud = 38400
            try:
                timeout = max(10, min(600, int(tot.get())))
            except ValueError:
                timeout = 180
            self.config.update(port=port, baud=baud, mycall=call_entry.get().strip().upper(), tx_timeout=timeout)
            save_config(self.config)
            win.destroy()
            self.want_connect = True
            if port == AUTO_PORT:
                self.disconnect()
                self.auto_connect(quiet=False)
            else:
                self.connect(port, baud)

        btns = tk.Frame(win, bg=PANEL)
        btns.grid(row=5, column=0, columnspan=2, pady=(px(10), px(14)))
        self.btn(btns, "Refresh", refresh_ports, width=80).pack(side="left", padx=px(4))
        self.btn(btns, "Save & connect", apply_settings, width=120, tone="green").pack(side="left", padx=px(4))
        self.btn(btns, "Cancel", win.destroy, width=80).pack(side="left", padx=px(4))
        refresh_ports()

    # ---------------------------------------------------------- CAT I/O
    def _drain(self):
        ser = self.ser
        if ser and ser.is_open and ser.in_waiting:
            ser.read(ser.in_waiting)          # discard stale / auto-information output
        self.rxbuf.clear()

    def cat(self, cmd, reply=True):
        """Send one CAT command ("FA;" ...). For reads returns the answer without ';',
        "?" if the rig rejected it, or None on timeout. Set commands return "" straight away."""
        ser = self.ser
        if not ser or not ser.is_open:
            return None
        prefix = cmd[:2]
        try:
            with self.io_lock:
                self._drain()
                ser.write(cmd.encode("ascii"))
                if not reply:
                    return ""
                deadline = time.time() + REPLY_TIMEOUT
                while time.time() < deadline:
                    chunk = ser.read(max(1, ser.in_waiting))
                    if chunk:
                        self.rxbuf += chunk
                    while b";" in self.rxbuf:
                        i = self.rxbuf.index(b";")
                        msg = bytes(self.rxbuf[:i]).decode("ascii", "replace").lstrip("\r\n ")  # keep tag spaces
                        del self.rxbuf[:i + 1]
                        if msg == "?":
                            return "?"
                        if msg.startswith(prefix):
                            return msg
                    if not chunk:
                        return None
                    if len(self.rxbuf) > 4096:
                        self.rxbuf.clear()
                return None
        except Exception:
            self.io_error = True
            return None

    def post(self, fn):
        if self.running:
            self.cmdq.put(fn)

    def post_cat(self, cmd):
        self.post(lambda: self.cat(cmd, reply=False))

    def cat_status(self, cmd, want):
        """Send a set command, then report in the status bar (Yaesu sets have no ACK; '?' = rejected)."""
        def job():
            self.cat(cmd, reply=False)
            time.sleep(0.05)
            ser = self.ser
            rejected = False
            try:
                if ser and ser.in_waiting:
                    rejected = b"?;" in ser.read(ser.in_waiting)
            except Exception:
                pass
            if rejected:
                self.ui(self.flash_status, f"RIG REJECTED {cmd} (not available now?)", RED)
            else:
                self.ui(self.flash_status, want, GREEN, 2.5)
        self.post(job)

    # ------------------------------------------------------------ readers
    def read_toggle(self, key):
        _, prefix, vals, _, digits = TOGGLES[key]
        ans = self.cat("AC;" if key == "atu" else prefix + ";")
        if not ans or ans == "?" or not ans.startswith(prefix):
            return None
        if key == "atu":                      # AC00 0 off / 1 on / 2 tuning
            try:
                v = int(ans[4])
            except (ValueError, IndexError):
                return None
            self.atu_tuning = v == 2
            return 1 if v >= 1 else 0
        try:
            v = int(ans[len(prefix):len(prefix) + digits])
        except ValueError:
            return None
        if key == "agc" and v >= 4:
            v = 4                             # AUTO-FAST/MID/SLOW -> AUTO
        return v

    def read_shift(self):
        ans = self.cat("OS0;")
        try:
            return int(ans[3]) if ans and ans.startswith("OS0") else None
        except (ValueError, IndexError):
            return None

    def read_tone(self):
        ans = self.cat("CN00;")
        try:
            n = int(ans[4:7]) if ans and ans.startswith("CN00") else None
        except ValueError:
            return None
        return CTCSS[n] if n is not None and 0 <= n < len(CTCSS) else None

    def read_ftx(self):
        ans = self.cat("FT;")
        return ans[2] if ans and ans.startswith("FT") and len(ans) >= 3 else None

    def read_sub(self):
        """VFO-B frequency and mode (OI = opposite VFO information). Returns (hz, mode) or None."""
        ans = self.cat("OI;")
        info = parse_info(ans) if ans and ans != "?" else None
        if info:
            self.sub_nak = 0
            return info["hz"], info["mode"]
        fb = self.cat("FB;")
        if fb and fb.startswith("FB") and fb[2:].isdigit():
            self.sub_nak = 0
            return int(fb[2:]), None
        self.sub_nak += 1
        return None

    def read_levels(self):
        for _, prefix, *_ in LEVELS:
            if not self.running:
                return
            v = level_parse(prefix, self.cat(prefix + ";"))
            if v is not None:
                self.ui(self.set_level_ui, prefix, v)

    def identify(self):
        ans = self.cat("ID;")
        if ans and ans.startswith("ID"):
            self.rig_name = RIG_TITLE if ans[2:] == RIG_ID else f"YAESU ID {ans[2:]}"
            self.ui(self.set_link, True)

    # ------------------------------------------------------ polling thread
    def poll_radio(self):
        cycle = 0
        miss = 0
        identified = False
        me = threading.current_thread()
        while self.running:
            self.run_queue()
            st = {}
            info = parse_info(self.cat("IF;"))
            if self.io_error:
                break
            if info is None:
                miss += 1
                if miss == LINK_MISS_LIMIT:
                    self.ui(self.safe_update_ui, {"link": False})
                time.sleep(0.25)
                continue
            if miss >= LINK_MISS_LIMIT:
                st["link"] = True
            miss = 0
            st["hz"], st["mode"], st["vfo"], st["ch"] = info["hz"], info["mode"], info["vfo"], info["ch"]
            st["clar"] = info["clar"]

            if not identified:
                identified = True
                self.cat("AI0;", reply=False)          # no unsolicited auto-information
                self.identify()

            if self.memread is not None:
                self.memread_step()

            ans = self.cat("TX;")
            tx = (ans[2] in "12") if ans and ans.startswith("TX") and len(ans) >= 3 else None
            st["tx"] = tx

            s_raw, busy = None, None
            if tx:
                st["p_raw"] = self._meter("RM5")
                st["swr"] = self._meter("RM6")
                st["alc"] = self._meter("RM4")
                if cycle % 2:
                    st["comp"] = self._meter("RM3")
                else:
                    st["id"] = self._meter("RM7")
            elif tx is False:
                sm = self.cat("SM0;")
                try:
                    s_raw = int(sm[3:6]) if sm and sm.startswith("SM0") else None
                except ValueError:
                    s_raw = None
                by = self.cat("BY;")
                busy = (by[2] == "1") if by and by.startswith("BY") and len(by) >= 3 else None
                st["s_raw"], st["sql"] = s_raw, busy
                if busy is not None:
                    self.sql_live = (bool(busy), time.time())

            if self.io_error:
                break

            if self.full_sync:
                self.full_sync = False
                slow = []
                for key, fn in self.slow_reads:
                    v = fn()
                    if v is not None:
                        slow.append((key, v))
                st["slow"] = slow
                st["sub"] = self.read_sub()
                self.read_levels()
            elif cycle % 2 == 1 and not self.scan:
                key, fn = self.slow_reads[self.slow_idx % len(self.slow_reads)]
                self.slow_idx += 1
                v = fn()
                if v is not None:
                    st["slow"] = [(key, v)]
            elif cycle % 4 == 2 and not self.scan and self.sub_nak < 3:
                st["sub"] = self.read_sub()
            elif cycle % 6 == 4 and not self.scan:
                prefix = LEVELS[(cycle // 6) % len(LEVELS)][1]
                v = level_parse(prefix, self.cat(prefix + ";"))
                if v is not None:
                    self.ui(self.set_level_ui, prefix, v)

            st["scan"] = self.scan_step(tx, busy, s_raw)
            self.ui(self.safe_update_ui, st)
            cycle += 1
            time.sleep(0.03)
        if self.io_error:
            self.ui(self.on_link_lost, me)

    def _meter(self, cmd):
        ans = self.cat(cmd + ";")
        try:
            return int(ans[3:6]) if ans and ans.startswith(cmd) else None
        except ValueError:
            return None

    def scan_step(self, tx, busy, s_raw):
        """Runs on the polling thread. Returns 'scan', 'hold' or None."""
        sc = self.scan
        if not sc:
            return None
        now = time.time()
        if tx:
            sc["hold_until"] = now + sc["hold"]
            return "hold"
        settled = now - sc["last_move"] >= SCAN_SETTLE
        if settled and s_raw is not None and 0 <= sc["idx"] < len(sc["levels"]):
            old = sc["levels"][sc["idx"]]
            sc["levels"][sc["idx"]] = s_raw if old is None else max(old, s_raw)
        signal = settled and ((sc["use_sql"] and busy) or
                              (sc["use_s"] and s_raw is not None and s_raw >= sc["s_thresh"]))
        if signal:
            sc["hold_until"] = now + sc["hold"]
        if now < sc["hold_until"]:
            return "hold"
        if now - sc["last_move"] >= sc["dwell"]:
            sc["idx"] = (sc["idx"] + 1) % len(sc["items"])
            hz, mode = sc["items"][sc["idx"]]
            self.cat(f"FA{int(hz):09d};", reply=False)
            if mode in MODE_REVERSE:
                self.cat(f"MD0{MODE_REVERSE[mode]};", reply=False)
            sc["last_move"] = time.time()
        return "scan"

    # ----------------------------------------------------------- UI update
    def safe_update_ui(self, st):
        if not self.running:
            return
        now = time.time()
        if st.get("link") is not None:
            self.set_link(st["link"])

        hz = st.get("hz")
        if hz is not None:
            if now - self.tune_time > 0.8:
                self.cur_hz = hz
            b = band_of(self.cur_hz or hz)
            self.chip_band.set_active(bool(b), b.upper() if b else "BAND")
            if b:
                self.config["band_last"][b] = hz
            for name, btn in self.band_btns.items():
                btn.set_active(name == b)
        if st.get("vfo") is not None:
            self.vfo_mode = st["vfo"]
            txt = VFO_MODE_TEXT.get(st["vfo"], "VFO-A")
            if txt in ("MEM", "M.TUNE"):
                txt = f"{txt} {st.get('ch', '')}".strip()
            self.chip_main.set_active(True, txt)
        if st.get("clar") is not None and now - self.toggle_touch.get("rit_hz", 0) > 1.5:
            if st["clar"] != self.rit_hz:
                self.rit_hz = st["clar"]
                self.lbl_rit.config(text=f"{self.rit_hz:+d} Hz")

        mode = st.get("mode")
        if mode and now - self.mode_time > 1.0:
            self.cur_mode = mode
            self.chip_mode.set_active(True, mode)
            self.refresh_mode_buttons()

        tx = st.get("tx")
        if tx is not None:
            self.is_tx = tx
            if not tx and self.ptt_on and now - self.ptt_since > 1.5:
                self.ptt_on = False
            new_mode = "tx" if tx else "rx"
            if new_mode != self.meter_mode:
                self.meter_mode = new_mode
                self.meter_frac = 0.0
                self.peak_frac = 0.0
                self.swr_sev = 0
                self.pwr_frac = 0.0
                self.tx_text = {}
                self.lbl_info.config(text="")
                self.lbl_smeter.config(text="")
            self.refresh_ptt()

        if tx:
            if st.get("swr") is not None:
                raw = st["swr"]
                self.meter_frac = min(raw / METER_MAX, 1.0)
                text, self.swr_sev = swr_from_raw(raw)
                self.lbl_smeter.config(text=text, fg=(LCD_GREEN, LCD_ORANGE, LCD_RED)[self.swr_sev])
            if st.get("p_raw") is not None:
                self.pwr_frac = min(st["p_raw"] / METER_MAX, 1.0)
                self.tx_text["po"] = f"Po {watts_from_raw(st['p_raw']):.0f}W"
            if st.get("alc") is not None:
                self.tx_text["alc"] = f"ALC {alc_pct(st['alc'])}%"
            if st.get("comp") is not None:
                self.tx_text["comp"] = f"COMP {comp_db(st['comp']):.0f}dB"
            if st.get("id") is not None:
                self.tx_text["id"] = f"Id {id_amps(st['id']):.1f}A"
            parts = [self.tx_text[k] for k in ("po", "alc", "comp", "id") if k in self.tx_text]
            self.lbl_info.config(text="  ".join(parts), fg=LCD_ORANGE)
        elif tx is False and st.get("s_raw") is not None:
            raw = st["s_raw"]
            self.meter_frac = min(raw / METER_MAX, 1.0)
            self.lbl_smeter.config(text=s_label(raw), fg=LCD_TEXT if raw <= S9_RAW else LCD_RED)
            if self.meter_frac >= self.peak_frac:
                self.peak_frac, self.peak_time = self.meter_frac, now
            elif now - self.peak_time > 1.5:
                self.peak_frac = max(self.meter_frac, self.peak_frac - 0.03)
            self.lbl_info.config(text=f"PEAK {s_label(self.peak_frac * METER_MAX)}", fg=LCD_LABEL)
        if tx is False and st.get("sql") is not None:
            self.rx_busy = bool(st["sql"])
        elif tx:
            self.rx_busy = False

        for key, val in st.get("slow", []):
            self.apply_remote(key, val)
        if "sub" in st:
            sub = st["sub"]
            new = (sub[0], sub[1] or self.sub_mode) if sub else (self.sub_hz, self.sub_mode)
            if new != (self.sub_hz, self.sub_mode) or (sub is None and self.sub_nak >= 3):
                self.sub_hz, self.sub_mode = new
                self.draw_sub()

        if "scan" in st and self.scan is not None:
            self.set_scan_badge(st["scan"])
            if self.cur_tab == "SCAN" and now - self._sweep_drawn > 0.35:
                self._sweep_drawn = now
                self.draw_sweep()

        self.draw_freq()
        self.draw_meter()

    def apply_remote(self, key, val):
        now = time.time()
        if key in TOGGLES:
            if now - self.toggle_touch.get(key, 0) < 1.5:
                return
            self.toggle_state[key] = val
            self.refresh_toggle(key)
            if key == "split":
                self.refresh_duplex()
        elif key == "dup":
            if now - self.dup_touch < 1.5:
                return
            self.dup_state = val
            self.refresh_duplex()
        elif key == "tone_hz":
            self.tone_var.set(f"{val:.1f}")
        elif key == "ftx":
            self.tx_vfo_b = (val == "1")
            self.btn_txa.set_active(not self.tx_vfo_b)
            self.btn_txb.set_active(self.tx_vfo_b)
            self.draw_sub()

    # ------------------------------------------------- phone / browser access
    def start_web(self, quiet=True, parent=None):
        self.web.stop()
        if self.config.get("web_on") and self.config.get("web_password"):
            port = int(self.config.get("web_port", WEB_DEFAULT_PORT))
            if not self.config.get("web_secret"):
                self.config["web_secret"] = secrets.token_hex(16)
                save_config(self.config)
            if self.web.start(port, self.config["web_password"], self.config["web_secret"]):
                self.web_mem_dirty = True
                self.start_https(quiet=quiet)
            elif quiet:
                err = self.web.error
                self.root.after(1500, lambda: self.flash_status(f"PHONE ACCESS NOT STARTED: {err}", RED, 8))
            else:
                messagebox.showerror("Phone access", f"Could not start on port {port}:\n{self.web.error}\n\n"
                                     "Is another copy of the program already running? Try a different port.",
                                     parent=parent or self.root)
        self.update_port_label()

    def start_https(self, quiet=True):
        """Start the https page if a certificate has been fetched; renew it in the background when old."""
        name = self.config.get("web_https_name")
        if not (self.web.running and name and os.path.exists(CERT_PATH) and os.path.exists(KEY_PATH)):
            return
        port = int(self.config.get("web_https_port", 8074))
        if not self.web.start_https(port, CERT_PATH, KEY_PATH, name) and not quiet:
            messagebox.showerror("HTTPS", f"Could not start the https page on port {port}:\n{self.web.https_error}")
        try:
            age = time.time() - os.path.getmtime(CERT_PATH)
        except OSError:
            age = 0
        if age > 30 * 86400 and not getattr(self, "_cert_renewing", False):   # Tailscale certificates last 90 days
            self._cert_renewing = True

            def job():
                ok, _ = fetch_ts_cert(name)
                self._cert_renewing = False
                if ok:
                    self.ui(self.start_https)
            threading.Thread(target=job, daemon=True).start()

    def web_tick(self):
        try:
            if self.web.running:
                mems = None
                if self.web_mem_dirty:
                    self.web_mem_dirty = False
                    mems = self.web_memories()
                self.web.publish(self.web_state(), mems)
            if self.audio is not None:
                self.audio.idle_check()
        except Exception:
            pass
        finally:
            self.root.after(300, self.web_tick)

    def _web_toggle(self, key):
        label, _, vals, texts, _ = TOGGLES[key]
        v = self.toggle_state.get(key)
        if v is None:
            return None
        return [bool(key in ALWAYS_LIT or v != vals[0]), texts[vals.index(v)] if (texts and v in vals) else label]

    def web_state(self):
        """Snapshot of what the window shows, for the phone page (Tk thread)."""
        on = self.running
        vfo_text = VFO_MODE_TEXT.get(self.vfo_mode, "VFO-A")
        if vfo_text in ("MEM", "M.TUNE"):
            vfo_text = f"{vfo_text} {self.mem_ch}".strip()
        return {
            "online": on, "link": self.link_ok, "status": self.lbl_status.cget("text"), "rig": self.rig_name,
            "rig_on": self.radio_is_on(), "rig_off": bool(on and self.rig_off),
            "utc": self.clock_text, "hz": self.cur_hz if on else None, "mode": self.cur_mode if on else None,
            "band": band_of(self.cur_hz) if (on and self.cur_hz) else "", "vfo_text": vfo_text,
            "tx": bool(on and self.is_tx), "busy": bool(on and self.rx_busy and not self.is_tx),
            "ptt": bool(on and self.ptt_on), "meter": self.meter_mode, "mfrac": round(self.meter_frac, 3),
            "peak": round(self.peak_frac, 3), "pwr": round(self.pwr_frac, 3), "swr_sev": self.swr_sev,
            "mtext": self.lbl_smeter.cget("text"), "info": self.lbl_info.cget("text"),
            "sub_hz": self.sub_hz if on else None, "sub_mode": self.sub_mode if on else None,
            "sub_band": band_of(self.sub_hz) if (on and self.sub_hz) else "",
            "toggles": {k: self._web_toggle(k) for k in TOGGLES},
            "levels": dict(self.level_vals),
            "dup": self.dup_state if on else None, "rit": self.rit_hz, "tx_b": self.tx_vfo_b if on else None,
            "tone": self.tone_var.get(), "step": self.step_hz(),
            "scan": bool(self.scan), "mem_rev": self.web_mem_rev,
            "atok": self.web.audio_token, "audio_sql": bool(self.config.get("audio_sql", True)),
            "sql_muted": bool(self.audio is not None and self.audio.listener_count() and self.audio.squelched()),
            "https_url": self.web.https_url,
            "atu_tuning": bool(on and (self.atu_busy or self.atu_tuning)),
            "cwd": {"on": self.cwdec.active, "text": self.cwdec.text[-240:],
                    "info": (f"{self.cwdec.tone} Hz \u00b7 {self.cwdec.wpm()} WPM" if self.cwdec.snr_ok
                             else "waiting for CW") if self.cwdec.active else (self.cwdec.error or ""),
                    "sens": self.cwdec.sens, "sens_note": self.cwd_sens_text()},
            "audio_info": self.audio.status() if self.audio is not None else "",
            "audio_err": (self.audio.error if self.audio is not None else
                          "Audio isn't set up on the PC: run  py -m pip install sounddevice  there and restart the program."),
        }

    def sql_in_use(self):
        """Squelch turned up above fully open?"""
        return (self.level_vals.get("SQ0") or 0) > 0

    def web_memories(self):
        return [{"i": i, "name": m["name"], "mhz": hz_to_mhz(m["hz"]), "mode": m.get("mode") or "",
                 "ch": m.get("ch", ""), "info": mem_info(m)} for i, m in enumerate(self.config["memories"])]

    def web_command(self, c):
        """A command from the phone page (runs on the Tk thread, same as clicking in the window)."""
        a = c.get("a")
        try:
            if a == "power":
                self.power_set(bool(c.get("on")), " FROM PHONE")
                return
            if a == "tune":
                self.request_frequency(int(c["hz"]))
            elif a == "step":
                step = int(c.get("step") or 0)
                self.step_tune(1 if int(c["dir"]) > 0 else -1, step if step in dict(STEPS).values() else None)
            elif a == "mode" and c.get("mode") in MODE_REVERSE:
                self.set_radio_mode(c["mode"])
            elif a == "band" and c.get("band") in [b[0] for b in BANDS]:
                self.band_click(c["band"])
            elif a == "toggle" and c.get("key") in TOGGLES:
                self.click_toggle(c["key"])
            elif a == "level" and c.get("sub") in LEVEL_DEF:
                p = c["sub"]
                lo, hi = LEVEL_DEF[p][3], LEVEL_DEF[p][4]
                v = max(lo, min(hi, int(c["v"])))
                self.level_scales[p].set(v - lo)
                self.on_level(p, v - lo)
            elif a == "dup" and c.get("code") in (0, 1, 2):
                self.set_duplex(int(c["code"]))
            elif a == "tone":
                t = f"{float(c['t']):.1f}"
                if t in [f"{x:.1f}" for x in CTCSS]:
                    self.tone_var.set(t)
                    self.set_tone(t)
            elif a == "rit":
                d = int(c["d"])
                if d in (-50, -10, 10, 50):
                    self.nudge_rit(d)
            elif a == "rit_clear":
                self.set_rit(0)
            elif a == "swap":
                self.swap_bands()
            elif a == "vfo" and c.get("op") in ("AB", "BA"):
                self.cat_status(f"{c['op']};", "VFO-A COPIED TO VFO-B" if c["op"] == "AB" else "VFO-B COPIED TO VFO-A")
            elif a == "txvfo":
                self.set_tx_vfo(bool(c.get("b")))
            elif a == "macro":
                n = int(c["n"])
                if 0 <= n < len(self.config["cw_macros"]):
                    self.send_macro(n)
            elif a == "atu_tune":
                self.atu_tune(" FROM PHONE")
            elif a == "atu_off":
                self.atu_off()
            elif a == "cwdec":
                if c.get("on"):
                    self.cwdec.on_text = self.cwd_append
                    self.cwdec.start()
                else:
                    self.cwdec.stop()
                if self.cwd_win is not None and self.cwd_win.winfo_exists():
                    self.cwd_tick(once=True)
            elif a == "cwd_clear":
                self.cwd_clear()
            elif a == "cwd_sens":
                self.cwd_set_sens(str(c.get("v")))
            elif a == "keyer":
                n = int(c["n"])
                if 1 <= n < CW_SLOT:
                    self.cat_status(f"KY{n};", f"PLAYING KEYER MEMORY {n}")
            elif a == "mem":
                i = int(c["i"])
                if 0 <= i < len(self.config["memories"]):
                    self.recall_mem(self.config["memories"][i])
            elif a == "audio_sql":
                self.config["audio_sql"] = bool(c.get("on"))
                save_config(self.config)
            elif a == "unkey":                 # release PTT, whoever keyed it
                if self.running and (self.ptt_on or self.is_tx):
                    self.ptt_on = False
                    self.web_keyed = False
                    self.post_cat("TX0;")
                    self.refresh_ptt()
                    self.flash_status("PTT RELEASED FROM PHONE", AMBER)
        except (KeyError, TypeError, ValueError):
            pass

    def web_addresses(self):
        port = self.web.port or self.config.get("web_port", WEB_DEFAULT_PORT)
        host = socket.gethostname()
        ips = set()
        try:
            for info in socket.getaddrinfo(host, None, socket.AF_INET):
                ips.add(info[4][0])
        except OSError:
            pass
        # Tailscale addresses are in 100.64.0.0/10
        ts = sorted(ip for ip in ips if ip.startswith("100.") and 64 <= int(ip.split(".")[1]) <= 127)
        return [f"http://{ip}:{port}" for ip in ts] + [f"http://{host.lower()}:{port}"]

    def web_ptt(self, on):
        """PTT from a phone's TALK button (Tk thread). The audio link drops it if the phone goes quiet."""
        if not self.running:
            return
        if on:
            if self.ptt_on or self.is_tx:
                return
            self.ptt_on = True
            self.web_keyed = True
            self.ptt_since = time.time()
            self.refresh_ptt()

            def job():
                self.cat("TX1;", reply=False)
                time.sleep(0.05)
                try:
                    if self.ser and self.ser.in_waiting and b"?;" in self.ser.read(self.ser.in_waiting):
                        self.ptt_on = False
                        self.ui(self.flash_status, "RIG REJECTED PTT FROM PHONE", RED)
                except Exception:
                    pass
            self.post(job)
            self.flash_status("TX FROM PHONE", AMBER, 2)
        elif self.web_keyed:
            self.web_keyed = False
            if self.ptt_on or self.is_tx:
                self.ptt_on = False
                self.post_cat("TX0;")
                self.refresh_ptt()

    def open_phone_page(self):
        if not self.web.running:
            messagebox.showinfo("Phone", "Phone access is off. Turn it on in Phone > Phone access first.")
            self.open_web_settings()
            return
        webbrowser.open(self.web.https_url or f"http://127.0.0.1:{self.web.port}/")

    def setup_https(self, parent, done):
        """Get this PC's https certificate from Tailscale and start the https page."""
        if not self.web.running:
            messagebox.showinfo("HTTPS", "Tick 'Allow access from my phone', set a password and click Save first.",
                                parent=parent)
            return
        busy = tk.Toplevel(parent)
        busy.title("HTTPS")
        busy.configure(bg=PANEL)
        busy.transient(parent)
        self.lbl(busy, "Getting a certificate from Tailscale...\nThis can take up to a minute.", fg=TEXT).pack(
            padx=px(24), pady=px(18))

        def finish(ok, info):
            try:
                busy.destroy()
            except tk.TclError:
                pass
            if ok:
                self.config["web_https_name"] = info
                save_config(self.config)
                self.start_https(quiet=False)
                done()
                if self.web.https_url:
                    messagebox.showinfo("HTTPS", "HTTPS is on. On your phone open:\n\n" + self.web.https_url +
                                        "\n\nThe TALK button (microphone) works on this address.", parent=parent)
                return
            if info == "NOT_ENABLED":
                if messagebox.askyesno(
                        "HTTPS",
                        "HTTPS certificates are switched off for your Tailscale network. This is a one-time "
                        "switch in your Tailscale account:\n\n"
                        "1. On the page that opens, find 'HTTPS Certificates' (MagicDNS must be on as well)\n"
                        "2. Click 'Enable HTTPS' and confirm\n"
                        "3. Come back here and click 'Turn on HTTPS' again\n\nOpen the Tailscale page now?",
                        parent=parent):
                    webbrowser.open("https://login.tailscale.com/admin/dns")
            else:
                messagebox.showerror("HTTPS", "Tailscale could not provide a certificate:\n\n" + info[-900:],
                                     parent=parent)

        def job():
            ok, info = fetch_ts_cert(None)
            self.ui(finish, ok, info)
        threading.Thread(target=job, daemon=True).start()

    def open_web_settings(self):
        win = tk.Toplevel(self.root)
        win.title("Phone access")
        win.configure(bg=PANEL)
        win.resizable(False, False)
        win.transient(self.root)
        win.grab_set()

        on_var = tk.BooleanVar(value=bool(self.config.get("web_on")))
        self.check(win, "Allow access from my phone / browser", on_var).grid(
            row=0, column=0, columnspan=3, sticky="w", padx=px(10), pady=(px(12), px(4)))
        self.lbl(win, "Port", fg=MUTED).grid(row=1, column=0, sticky="w", padx=px(14), pady=px(5))
        port_sp = self.spin(win, 1024, 65535, 1, self.config.get("web_port", WEB_DEFAULT_PORT), width=7)
        port_sp.grid(row=1, column=1, sticky="w", padx=px(4))
        self.lbl(win, "Password", fg=MUTED).grid(row=2, column=0, sticky="w", padx=px(14), pady=px(5))
        pw = self.entry(win, width=22, show="•")
        pw.insert(0, self.config.get("web_password", ""))
        pw.grid(row=2, column=1, sticky="w", padx=px(4), ipady=px(2))
        show_var = tk.BooleanVar(value=False)
        self.check(win, "Show", show_var).grid(row=2, column=2, sticky="w", padx=(px(6), px(14)))
        show_var.trace_add("write", lambda *a: pw.config(show="" if show_var.get() else "•"))

        self.caption(win, "Open on your phone").grid(row=3, column=0, columnspan=3, sticky="w",
                                                    padx=px(14), pady=(px(12), 0))
        info = tk.Label(win, text="", bg=PANEL, fg=TEXT, font=F["mono_b"], justify="left", anchor="w")
        info.grid(row=4, column=0, columnspan=3, sticky="w", padx=px(14), pady=(px(2), 0))
        hrow = tk.Frame(win, bg=PANEL)
        hrow.grid(row=5, column=0, columnspan=3, sticky="w", padx=px(14), pady=(px(6), 0))

        def refresh_info():
            if self.web.running:
                lines = self.web_addresses()
                if self.web.https_url:
                    lines = [self.web.https_url + "   <- use this one (microphone works)"] + lines
                info.config(text="\n".join(lines), fg=GREEN)
            elif self.web.error:
                info.config(text=f"Not running: {self.web.error}", fg=RED)
            else:
                info.config(text="Off", fg=MUTED)

        self.btn(hrow, "Turn on HTTPS (needed for the phone microphone)",
                 lambda: self.setup_https(win, refresh_info), width=330, tone="accent").pack(side="left")

        # ---- audio devices
        self.caption(win, "Audio - FTDX10 USB audio").grid(row=6, column=0, columnspan=3, sticky="w",
                                                             padx=px(14), pady=(px(14), 0))
        in_var = tk.StringVar(value=self.config.get("audio_in", AUDIO_AUTO))
        out_var = tk.StringVar(value=self.config.get("audio_out", AUDIO_AUTO))
        if AUDIO_READY:
            ins = [AUDIO_AUTO] + [n for _, n in AudioEngine.devices("input")]
            outs = [AUDIO_AUTO] + [n for _, n in AudioEngine.devices("output")]
        else:
            ins, outs = [AUDIO_AUTO], [AUDIO_AUTO]
        self.lbl(win, "Receive audio from", fg=MUTED).grid(row=7, column=0, sticky="w", padx=px(14), pady=px(4))
        ttk.Combobox(win, textvariable=in_var, values=ins, state="readonly" if AUDIO_READY else "disabled",
                     width=36, font=F["ui"]).grid(row=7, column=1, columnspan=2, sticky="w", padx=px(4))
        self.lbl(win, "Transmit audio to", fg=MUTED).grid(row=8, column=0, sticky="w", padx=px(14), pady=px(4))
        ttk.Combobox(win, textvariable=out_var, values=outs, state="readonly" if AUDIO_READY else "disabled",
                     width=36, font=F["ui"]).grid(row=8, column=1, columnspan=2, sticky="w", padx=px(4))
        if AUDIO_READY:
            note = ("Radio: for transmit audio from the phone set the mode's MOD SOURCE to REAR and\n"
                    "REAR SELECT to USB in the FTDX10 menu (back to MIC for the hand mic).\n"
                    "The phone asks for the password once and remembers it. On the https address,\n"
                    "Chrome on Android offers 'Install app' to put it on your home screen as an app.\n"
                    "TX from the phone stops by itself if its connection or microphone drops,\n"
                    "and the PTT time-out in Settings still applies.")
            ncol = DIM
        else:
            note = ("Audio needs one more package on this PC. Open a command prompt and run:\n"
                    "    py -m pip install sounddevice\n"
                    "then restart FTDX10 Monitor. (Reinstalling with the new setup does this for you.)")
            ncol = AMBER
        tk.Label(win, bg=PANEL, fg=ncol, font=F["small"], justify="left", text=note).grid(
            row=9, column=0, columnspan=3, sticky="w", padx=px(14), pady=(px(8), 0))

        def apply():
            try:
                port = int(port_sp.get())
                if not 1024 <= port <= 65535:
                    raise ValueError
            except ValueError:
                messagebox.showerror("Phone access", "The port must be a number from 1024 to 65535.", parent=win)
                return
            password = pw.get()
            if on_var.get() and len(password) < 6:
                messagebox.showerror("Phone access", "Choose a password of at least 6 characters.", parent=win)
                return
            audio_changed = (in_var.get(), out_var.get()) != (self.config.get("audio_in", AUDIO_AUTO),
                                                               self.config.get("audio_out", AUDIO_AUTO))
            restart = (bool(on_var.get()), port, password) != (bool(self.config.get("web_on")),
                                                              self.config.get("web_port"),
                                                              self.config.get("web_password"))
            self.config.update(web_on=bool(on_var.get()), web_port=port, web_password=password,
                               audio_in=in_var.get(), audio_out=out_var.get())
            save_config(self.config)
            if restart or not self.web.running:
                self.start_web(quiet=False, parent=win)
            if audio_changed and self.audio is not None:
                threading.Thread(target=self.audio.restart, daemon=True).start()
            refresh_info()

        bt = tk.Frame(win, bg=PANEL)
        bt.grid(row=10, column=0, columnspan=3, pady=(px(12), px(14)))
        self.btn(bt, "Save", apply, width=90, tone="green").pack(side="left", padx=px(4))
        self.btn(bt, "Close", win.destroy, width=80).pack(side="left", padx=px(4))
        refresh_info()

    # --------------------------------------------------------- toggles
    def set_toggle_value(self, key, nxt):
        if not self.running:
            return
        label, prefix, vals, _, digits = TOGGLES[key]
        self.toggle_state[key] = nxt
        self.toggle_touch[key] = time.time()
        self.refresh_toggle(key)
        if key == "split":
            self.refresh_duplex()
        cmd = f"{prefix}{nxt:0{digits}d};"

        def job():
            self.cat(cmd, reply=False)
            time.sleep(0.05)
            v = self.read_toggle(key)
            if v is not None and v != nxt and key != "agc":
                self.ui(self.flash_status, f"RIG DID NOT ACCEPT {label} (not available in this mode?)", RED)
                self.toggle_touch[key] = 0
                self.ui(self.apply_remote, key, v)
        self.post(job)

    def refresh_toggle(self, key):
        if key == "atu":
            self.refresh_tune()
        label, _, vals, texts, _ = TOGGLES[key]
        v = self.toggle_state.get(key)
        text = texts[vals.index(v)] if (texts and v in vals) else label
        lit = v is not None and (key in ALWAYS_LIT or v != vals[0])
        for b in self.toggle_btns.get(key, []):
            b.set_active(lit, text)
        if key in ("rit", "xit"):
            on = [k.upper() for k in ("rit", "xit") if self.toggle_state.get(k) == 1]
            self.chip_sat.set_active(bool(on), "/".join(on) or "RIT")
        elif key == "nar":
            self.chip_fil.set_active(lit, "NAR")
        self.schedule("draw_status")

    def set_duplex(self, code):
        if not self.running:
            return
        self.dup_state = code
        self.dup_touch = time.time()
        self.refresh_duplex()
        self.cat_status(f"OS0{code};", {0: "SIMPLEX", 1: "+ SHIFT", 2: "- SHIFT"}[code])

    def refresh_duplex(self):
        split = self.toggle_state.get("split") == 1
        text = "SPLIT" if split else SHIFT_TEXT.get(self.dup_state)
        self.chip_dup.set_active(bool(text), text or "SPLIT")
        for code, b in getattr(self, "dup_btns", {}).items():
            b.set_active(self.dup_state == code and code != 0)

    def set_tone(self, text):
        try:
            idx = CTCSS.index(float(text))
        except ValueError:
            return
        self.cat_status(f"CN00{idx:03d};", f"CTCSS {float(text):.1f} Hz")

    def set_tx_vfo(self, b):
        self.tx_vfo_b = b
        self.btn_txa.set_active(not b)
        self.btn_txb.set_active(b)
        self.cat_status("FT3;" if b else "FT2;", f"TRANSMIT ON VFO-{'B' if b else 'A'}")
        self.draw_sub()

    def nudge_rit(self, d):
        if not self.running:
            return
        self.rit_hz = max(-9990, min(9990, self.rit_hz + d))
        self.toggle_touch["rit_hz"] = time.time()
        self.lbl_rit.config(text=f"{self.rit_hz:+d} Hz")
        self.post_cat(f"RU{d:04d};" if d > 0 else f"RD{-d:04d};")

    def set_rit(self, hz):
        if not self.running:
            return
        self.rit_hz = 0
        self.toggle_touch["rit_hz"] = time.time()
        self.lbl_rit.config(text="+0 Hz")
        self.post_cat("RC;")

    def refresh_mode_buttons(self):
        for m, b in self.mode_btns.items():
            b.set_active(m == self.cur_mode)

    # ------------------------------------------------------------ PTT
    def toggle_ptt(self):
        if not self.running:
            return
        want = not (self.ptt_on or self.is_tx)
        self.ptt_on = want
        self.ptt_since = time.time()
        self.refresh_ptt()
        self.post_cat("TX1;" if want else "TX0;")

    def ptt_watchdog(self):
        if self.ptt_on:
            if time.time() - self.ptt_since > self.config.get("tx_timeout", 180):
                self.ptt_on = False
                self.post_cat("TX0;")
                self.flash_status("TX TIME-OUT - PTT RELEASED", RED, 6)
            self.refresh_ptt()

    # --------------------------------------------------------- tuning
    def apply_pending_freq(self):
        self.freq_queued = False
        hz = self.pending_hz
        if hz is not None:
            self.cat(f"FA{int(hz):09d};", reply=False)

    def set_radio_mode(self, mode_name, fil=None):
        if not self.running:
            return
        code = MODE_REVERSE.get(mode_name)
        if code is not None:
            self.post_cat(f"MD0{code};")
            self.mode_refresh = True
            self.mode_time = time.time()
            self.cur_mode = mode_name
            self.chip_mode.set_active(True, mode_name)
            self.refresh_mode_buttons()

    def swap_bands(self):
        if not self.running:
            return
        self.cat_status("SV;", "VFO-A ⇄ VFO-B SWAPPED")
        self.tune_time = 0.0
        self.mode_time = 0.0
        if self.scan:
            self.stop_scan()

    # --------------------------------------------------------- levels
    def on_level(self, prefix, slider_value):
        lo = LEVEL_DEF[prefix][3]
        a = lo + int(round(float(slider_value)))
        self.level_vals[prefix] = a
        self.draw_levels()
        self.level_labels[prefix].config(text=level_text(prefix, a))
        if self._lvl_guard:
            return
        self.level_touch[prefix] = time.time()
        self.pending_levels[prefix] = a
        self.post(self.apply_levels)

    def apply_levels(self):
        while self.pending_levels:
            try:
                prefix, a = self.pending_levels.popitem()
            except KeyError:
                break
            self.cat(level_set_cmd(prefix, a), reply=False)

    def set_level_ui(self, prefix, a):
        if time.time() - self.level_touch.get(prefix, 0) < 2.0:
            return
        self.level_vals[prefix] = a
        self.draw_levels()
        self._lvl_guard = True
        try:
            self.level_scales[prefix].set(a - LEVEL_DEF[prefix][3])
            self.level_labels[prefix].config(text=level_text(prefix, a))
        finally:
            self._lvl_guard = False

    # ---------------------------------------------------------- drawing
    def flash_tx(self):
        self.flash_on = not self.flash_on
        tx = self.is_tx and self.running
        self.chip_tx.set_active(tx, dim=tx and not self.flash_on)
        self.chip_busy.set_active(self.rx_busy and self.running and not tx)
        high_swr = tx and self.swr_sev == 2
        border = RED if (high_swr and self.flash_on) else BG
        self.root.config(highlightbackground=border, highlightcolor=border)
        color = LCD_RED if (high_swr and self.flash_on) else LCD_TEXT
        if color != self.freq_color:
            self.freq_color = color
            self.draw_freq(force=True)
        self.root.after(250, self.flash_tx)

    STATUS_ORDER = ["amp", "att", "agc", "nb", "nr", "anf", "nar", "proc", "vox", "mon", "bkin",
                    "keyer", "atu", "ctcss", "rit", "xit", "split", "lock"]

    def draw_status(self):
        c = self.status_canvas
        c.delete("all")
        w, h = c.winfo_width(), c.winfo_height()
        if w < 50:
            return
        cy = h / 2
        x = px(6)
        font = F["lcd_s"]
        if not self.running:
            c.create_text(x, cy, text="CAT OFFLINE", fill=LCD_DIM, font=font, anchor="w")
        else:
            for key in self.STATUS_ORDER:
                label, _, vals, texts, _ = TOGGLES[key]
                v = self.toggle_state.get(key)
                if v is None or not (key in ALWAYS_LIT or v != vals[0]):
                    continue
                text = texts[vals.index(v)] if (texts and v in vals) else label
                fg = LCD_ORANGE if key in ("att", "lock", "split") else LCD_TEXT
                x += self._lcd_box(c, x, cy, text, font, fg=fg, outline=LCD_DIM) + px(3)
                if x > w - px(130):
                    break
        xr = w - px(6)
        c.create_text(xr, cy, text=self.clock_text, fill=LCD_TEXT, font=F["lcd"], anchor="e")
        xr -= F["lcd"].measure(self.clock_text) + px(4)
        c.create_text(xr, cy, text="UTC", fill=LCD_LABEL, font=font, anchor="e")

    def draw_sub(self):
        c = self.sub_canvas
        c.delete("all")
        w, h = c.winfo_width(), c.winfo_height()
        if w < 50:
            return
        big, small = F["sub"], F["sub_s"]
        base = h - px(5)                                   # digit baseline, kept inside this line
        cy = base - big.metrics("ascent") * 0.36           # centre of the digits, for the tags
        font = F["lcd_s"]
        label = "VFO-B"
        tw = font.measure(label) + 2 * px(6)
        rrect(c, px(6), cy - px(8), px(6) + tw, cy + px(8), px(2), fill=LCD_SUB, outline=LCD_SUB)
        c.create_text(px(6) + tw / 2, cy, text=label, fill="#ffffff", font=font)
        x = px(10) + tw
        if self.running and (self.tx_vfo_b or self.toggle_state.get("split") == 1) and self.tx_vfo_b:
            x += self._lcd_box(c, x, cy, "TX", font, fg=LCD_RED, outline=LCD_RED, padx=5, h=16) + px(6)
        hz = self.sub_hz if self.running else None
        if hz is not None and self.sub_mode:
            x += self._lcd_box(c, x, cy, self.sub_mode, font, fg=LCD_LABEL, outline=LCD_DIM, padx=6, h=16) + px(6)
        if hz is not None and band_of(hz):
            c.create_text(x, cy, text=band_of(hz), fill=LCD_LABEL, font=F["lcd"], anchor="w")
        if hz is None:
            main_txt, hz_txt, col = ("---.---" if self.running else "  "), "", LCD_DIM
        else:
            main_txt = f"{hz // 1_000_000}.{(hz % 1_000_000) // 1000:03d}"
            hz_txt = f".{(hz % 1000) // 10:02d}"
            col = LCD_LABEL
        xr = w - px(10) - F["lcd"].measure("MHz") - px(8)
        # anchor "s" puts the bottom of the text box (baseline + descent) at y, so add each font's descent
        c.create_text(xr + px(6), base + F["lcd_s"].metrics("descent"), text="MHz", fill=LCD_DIM,
                      font=F["lcd_s"], anchor="sw")
        c.create_text(xr, base + small.metrics("descent"), text=hz_txt, fill=col, font=small, anchor="se")
        xr -= small.measure(hz_txt)
        c.create_text(xr, base + big.metrics("descent"), text=main_txt, fill=col, font=big, anchor="se")

    def draw_levels(self, event=None):
        c = self.levels_canvas
        c.delete("all")
        w = max(c.winfo_width(), 100)
        colw = w / len(BAR_LEVELS)
        n = 20
        colors = {"AG0": LCD_TEXT, "PC": LCD_ORANGE, "SQ0": LCD_GREEN}
        # label / value widths follow the font, so nothing overlaps at 125-150 % Windows scaling
        lab_w = F["lcd_s"].measure("PWR") + px(8)
        val_w = F["lcd_s"].measure("100W") + px(10)
        for col, (prefix, short) in enumerate(BAR_LEVELS):
            _, _, _, lo, hi, _ = LEVEL_DEF[prefix]
            x0 = col * colw + 4
            c.create_text(x0, 10, text=short, anchor="w", fill=LCD_LABEL, font=F["lcd_s"])
            bx0 = x0 + lab_w
            bx1 = (col + 1) * colw - val_w
            seg = (bx1 - bx0) / n
            v = self.level_vals.get(prefix)
            filled = 0 if v is None else int(round((v - lo) / (hi - lo) * n))
            for k in range(n):
                fill = colors[prefix] if k < filled else LCD_SEG_OFF
                c.create_rectangle(bx0 + k * seg + 1, 6, bx0 + (k + 1) * seg - 1, 14, fill=fill, outline="")
            c.create_text(bx1 + 4, 10, text=level_text(prefix, v), anchor="w",
                          fill=LCD_TEXT if v is not None else LCD_DIM, font=F["lcd_s"])
        c.scale("all", 0, 0, 1, SCALE)

    def draw_meter(self, event=None):
        c = self.meter_canvas
        c.delete("all")
        w = max(c.winfo_width(), 100)
        x0, x1 = px(40), w - px(22)
        bar_w = x1 - x0
        sf = F["lcd_s"]
        if self.meter_mode == "tx":
            c.create_text(px(10), 20, text="Po", anchor="w", fill=LCD_TEXT, font=F["lcd"])
            for label, raw in PWR_TICKS:
                x = x0 + (raw / METER_MAX) * bar_w
                c.create_line(x, 11, x, 14, fill=LCD_LABEL)
                c.create_text(x, 0, text=label, anchor="n", fill=LCD_TEXT, font=sf)
            self._bar(c, x0, bar_w, 15, 24, self.pwr_frac, lambda t: LCD_TEXT)
            c.create_text(px(10), 38, text="SWR", anchor="w", fill=LCD_TEXT, font=F["lcd"])
            limit = 126 / METER_MAX
            self._bar(c, x0, bar_w, 33, 42, self.meter_frac, lambda t: LCD_TEXT if t <= limit else LCD_RED)
            for label, raw in SWR_TICKS:
                x = x0 + (raw / METER_MAX) * bar_w
                c.create_line(x, 43, x, 46, fill=LCD_LABEL)
                c.create_text(x, 46, text=label, anchor="n", fill=LCD_RED if raw > 126 else LCD_TEXT, font=sf)
        else:
            c.create_text(px(12), 26, text="S", anchor="w", fill=LCD_TEXT, font=F["ui_b"])
            for label, raw in S_TICKS:
                x = x0 + (raw / METER_MAX) * bar_w
                col = LCD_RED if raw > S9_RAW else LCD_TEXT
                c.create_line(x, 12, x, 16, fill=col)
                c.create_text(x, 0, text=label if raw < 255 else "+60dB", anchor="ne" if raw >= 255 else "n",
                              fill=col, font=sf)
            xs9 = x0 + (S9_RAW / METER_MAX) * bar_w
            c.create_line(x0, 16, xs9, 16, fill=LCD_LABEL)
            c.create_line(xs9, 16, x1, 16, fill=LCD_RED, width=2)
            s9 = S9_RAW / METER_MAX
            self._bar(c, x0, bar_w, 19, 33, self.meter_frac, lambda t: LCD_SBLUE if t <= s9 else LCD_RED)
            if self.peak_frac > 0:
                n = 60
                seg_w = bar_w / n
                i = min(int(self.peak_frac * n), n - 1)
                xa = x0 + i * seg_w + 1
                c.create_rectangle(xa, 18, xa + max(2, seg_w - 2), 34, fill=LCD_ORANGE, outline="")
            for label, raw in PWR_TICKS:
                x = x0 + (raw / METER_MAX) * bar_w
                c.create_line(x, 36, x, 39, fill=LCD_DIM)
                c.create_text(x, 40, text=label, anchor="n", fill=LCD_DIM, font=sf)
            c.create_text(px(10), 45, text="Po", anchor="w", fill=LCD_DIM, font=sf)
        c.scale("all", 0, 0, 1, SCALE)


    def atu_tune(self, who=""):
        """Start the FTDX10's internal antenna tuner (AC002;). The radio transmits a carrier while it tunes."""
        if not self.running or self.atu_busy:
            return
        if not self.radio_is_on():
            self.flash_status("RADIO IS OFF - CAN'T TUNE", RED, 3)
            return
        self.atu_busy = True
        self.refresh_tune()
        self.flash_status(f"ATU TUNING{who} - the radio transmits a carrier while it tunes ...", AMBER, 12)
        self.toggle_touch["atu"] = time.time()

        def job():
            ok = None
            try:
                self.cat("AC002;", reply=False)
                time.sleep(0.8)
                t0 = time.time()
                seen = False
                while time.time() < t0 + 15 and self.running:
                    ans = self.cat("AC;")
                    if ans and ans.startswith("AC00") and len(ans) >= 5:
                        if ans[4] == "2":
                            seen = True               # the radio says it is tuning
                        elif seen or (time.time() > t0 + 3 and not self.is_tx):
                            ok = ans[4] == "1"        # finished: tuner on = matched
                            break
                    elif ans == "?":
                        ok = False
                        break
                    time.sleep(0.4)
            finally:
                def done():
                    self.atu_busy = False
                    self.atu_tuning = False
                    self.refresh_tune()
                    if ok:
                        self.toggle_state["atu"] = 1
                        self.refresh_toggle("atu")
                        self.flash_status("ATU TUNED", GREEN, 3)
                    elif ok is False:
                        self.flash_status("ATU DID NOT TUNE (check the antenna, band and RF power)", RED, 5)
                    else:
                        self.flash_status("ATU: no answer from the radio", ORANGE, 4)
                self.ui(done)
        self.post(job)

    def refresh_tune(self):
        b = getattr(self, "btn_tune", None)
        if b is not None:
            busy = self.atu_busy or self.atu_tuning
            on = busy or self.toggle_state.get("atu") == 1
            b.set_active(on, "TUNING" if busy else "ATU", tone="amber")

    def atu_off(self):
        """Switch the antenna tuner off (right-click on ATU, or a long press on the phone)."""
        if self.running and not self.atu_busy:
            self.set_toggle_value("atu", 0)
            self.flash_status("ATU OFF", MUTED, 2)

    def click_toggle(self, key):
        if not self.running:
            return
        vals = TOGGLES[key][2]
        cur = self.toggle_state.get(key)
        nxt = vals[(vals.index(cur) + 1) % len(vals)] if cur in vals else vals[1]
        self.set_toggle_value(key, nxt)

    # ---- shared with the IC-9700 Monitor (unchanged)
    def show_lib_error(self):
        messagebox.showerror("Error", "pyserial library missing!\nRun: python -m pip install pyserial")
        self.root.destroy()

    def setup_styles(self):
        st = ttk.Style(self.root)
        try:
            st.theme_use("clam")
        except tk.TclError:
            pass
        st.configure("TCombobox", fieldbackground=FIELD, background=BTN, foreground=TEXT,
                     arrowcolor=MUTED, bordercolor=BORDER, lightcolor=BORDER, darkcolor=BORDER,
                     padding=(4, 2))
        st.map("TCombobox", fieldbackground=[("readonly", FIELD)], foreground=[("readonly", TEXT)],
               selectbackground=[("readonly", FIELD)], selectforeground=[("readonly", TEXT)],
               bordercolor=[("focus", ACCENT_LO)], arrowcolor=[("active", ACCENT)])
        self.root.option_add("*TCombobox*Listbox.background", PANEL)
        self.root.option_add("*TCombobox*Listbox.foreground", TEXT)
        self.root.option_add("*TCombobox*Listbox.selectBackground", ACCENT_DIM)
        self.root.option_add("*TCombobox*Listbox.selectForeground", ACCENT)
        self.root.option_add("*TCombobox*Listbox.font", F["ui"])
        st.configure("Treeview", background=FIELD, fieldbackground=FIELD, foreground=TEXT,
                     rowheight=px(22), borderwidth=0, font=F["ui"])
        st.map("Treeview", background=[("selected", ACCENT_DIM)], foreground=[("selected", ACCENT)])
        st.configure("Treeview.Heading", background=PANEL, foreground=MUTED, relief="flat",
                     font=F["small_b"], borderwidth=0)
        st.map("Treeview.Heading", background=[("active", BTN)])
        st.layout("Treeview", [("Treeview.treearea", {"sticky": "nswe"})])
        for sname in ("TScrollbar", "Vertical.TScrollbar"):
            st.configure(sname, background=BTN, troughcolor=FIELD, arrowcolor=MUTED,
                         bordercolor=FIELD, lightcolor=BTN, darkcolor=BTN, gripcount=0)
        st.map("Vertical.TScrollbar", background=[("active", BTN_HOVER)])
        st.configure("Vertical.TScrollbar", background=BTN, troughcolor=FIELD, arrowcolor=MUTED,
                     bordercolor=FIELD, lightcolor=BTN, darkcolor=BTN, gripcount=0)

    def btn(self, parent, text, cmd, width=64, height=26, tone="accent"):
        return RoundButton(parent, text, cmd, width=width, height=height, tone=tone)

    def lbl(self, parent, text, **kw):
        kw.setdefault("bg", parent.cget("bg"))
        kw.setdefault("fg", TEXT)
        kw.setdefault("font", F["ui"])
        return tk.Label(parent, text=text, **kw)

    def caption(self, parent, text):
        return tk.Label(parent, text=text.upper(), bg=parent.cget("bg"), fg=MUTED, font=F["small_b"])

    def entry(self, parent, width=12, **kw):
        return tk.Entry(parent, width=width, font=F["ui"], bg=FIELD, fg=TEXT, insertbackground=ACCENT,
                        relief="flat", highlightthickness=1, highlightbackground=BORDER,
                        highlightcolor=ACCENT_LO, disabledbackground=FIELD, **kw)

    def spin(self, parent, lo, hi, inc, default, width=5):
        sp = tk.Spinbox(parent, from_=lo, to=hi, increment=inc, width=width, bg=FIELD, fg=TEXT,
                        insertbackground=ACCENT, buttonbackground=BTN, relief="flat",
                        highlightthickness=1, highlightbackground=BORDER, highlightcolor=ACCENT_LO,
                        font=F["ui"])
        sp.delete(0, tk.END)
        sp.insert(0, str(default))
        return sp

    def check(self, parent, text, var):
        return tk.Checkbutton(parent, text=text, variable=var, bg=parent.cget("bg"), fg=TEXT,
                              selectcolor=FIELD, activebackground=parent.cget("bg"), activeforeground=TEXT,
                              font=F["ui"], highlightthickness=0, bd=0)

    def card(self, parent, **pack):
        fr = tk.Frame(parent, bg=PANEL, highlightthickness=1, highlightbackground=BORDER)
        if pack:
            fr.pack(**pack)
        return fr

    def grid_row(self, parent, items, pady=3, padx=10, uniform="g"):
        """items: list of (text, cmd[, tone]) or ready widgets factories; returns list of buttons."""
        fr = tk.Frame(parent, bg=parent.cget("bg"))
        fr.pack(fill="x", padx=padx, pady=pady)
        out = []
        for i, it in enumerate(items):
            fr.columnconfigure(i, weight=1, uniform=uniform)
            b = self.btn(fr, it[0], it[1], width=40, tone=it[2] if len(it) > 2 else "accent")
            b.grid(row=0, column=i, padx=px(3), sticky="ew")
            out.append(b)
        return fr, out

    def fit_window(self):
        self.root.update_idletasks()
        try:
            req_h = int(self.root.winfo_reqheight())
            req_w = int(self.root.winfo_reqwidth())
        except Exception:
            req_h, req_w = 760, 560
        m = re.match(r"(\d+)x\d+([+-]-?\d+[+-]-?\d+)?", self.config.get("geometry") or "")
        min_w = max(px(540), req_w)
        width = max(min_w, int(m.group(1))) if m else min_w
        pos = (m.group(2) or "") if m else ""
        self.root.minsize(min_w, req_h)
        self.root.geometry(f"{width}x{req_h}{pos}")

    def toggle_topmost(self):
        self.config["topmost"] = bool(self.topmost_var.get())
        self.root.attributes("-topmost", self.config["topmost"])

    def show_tab(self, name):
        self.cur_tab = name
        self.config["tab"] = name
        self.pages[name].tkraise()
        for n, b in self.tab_btns.items():
            b.set_active(n == name)
        if name == "SCAN":
            self.draw_sweep()

    def focus_freq_entry(self):
        self.show_tab("TUNE")
        self.freq_entry.focus_set()

    def save_macros(self):
        self.config["cw_macros"] = [e.get() for e in self.macro_entries]

    def build_memory_tab(self, tab):
        cols = ("ch", "name", "mhz", "mode", "info")
        box = tk.Frame(tab, bg=FIELD, highlightthickness=1, highlightbackground=BORDER)
        box.pack(fill="both", expand=True, padx=px(10), pady=(px(10), px(4)))
        self.mem_tree = ttk.Treeview(box, columns=cols, show="headings", height=5, selectmode="browse")
        for c, text, w in (("ch", "CH", 64), ("name", "NAME", 130), ("mhz", "MHZ", 90), ("mode", "MODE", 50),
                           ("info", "DUP / TONE", 120)):
            self.mem_tree.heading(c, text=text, anchor="w")
            self.mem_tree.column(c, width=px(w), anchor="w")
        sb = ttk.Scrollbar(box, orient="vertical", command=self.mem_tree.yview)
        self.mem_tree.configure(yscrollcommand=sb.set)
        self.mem_tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.mem_tree.bind("<Double-1>", lambda e: self.recall_memory())

        row = tk.Frame(tab, bg=PANEL)
        row.pack(fill="x", padx=px(10), pady=px(3))
        self.lbl(row, "Name").pack(side="left")
        self.mem_name = self.entry(row, width=14)
        self.mem_name.pack(side="left", padx=px(6), ipady=px(2))
        self.mem_name.bind("<Return>", lambda e: self.add_memory())
        self.btn(row, "Save current", self.add_memory, width=92, tone="green").pack(side="left", padx=px(2))
        self.btn(row, "Overwrite", self.update_memory, width=74).pack(side="left", padx=px(2))
        self.btn(row, "Read from radio", self.open_memread, width=118, tone="accent").pack(side="right", padx=px(2))
        row2 = tk.Frame(tab, bg=PANEL)
        row2.pack(fill="x", padx=px(10), pady=(px(2), px(8)))
        self.btn(row2, "Recall", self.recall_memory, width=70).pack(side="left", padx=px(2))
        self.btn(row2, "Delete", self.delete_memory, width=70, tone="red").pack(side="left", padx=px(2))
        self.btn(row2, "Select on rig", self.select_memory_on_rig, width=96).pack(side="left", padx=px(2))
        self.btn(row2, "Export CSV", self.export_memories, width=86).pack(side="right", padx=px(2))
        self.btn(row2, "Import CSV", self.import_memories, width=86).pack(side="right", padx=px(2))
        self.refresh_mem_tree()

    def refresh_mem_tree(self):
        self.web_mem_dirty = True
        self.web_mem_rev += 1
        self.mem_tree.delete(*self.mem_tree.get_children())
        for i, m in enumerate(self.config["memories"]):
            self.mem_tree.insert("", "end", iid=str(i), values=(
                m.get("ch", ""), m["name"], hz_to_mhz(m["hz"]), m.get("mode") or "", mem_info(m)))

    def cancel_memread(self):
        if self.memread is not None:
            self.memread["cancel"] = True

    def memread_progress(self, done, total, found):
        win = self.memread_win
        if win is None or not win.winfo_exists():
            return
        c = self.mr_bar
        c.delete("all")
        w, h = int(c["width"]), int(c["height"])
        c.create_rectangle(0, 0, w * done / max(1, total), h, fill=ACCENT_LO, outline="")
        if done:
            self.mr_label.config(text=f"Channel {done} of {total}  ·  {found} programmed", fg=MUTED)

    def add_memory(self):
        if self.cur_hz is None:
            messagebox.showinfo("Memories", "No frequency yet - connect to the radio first.")
            return
        name = self.mem_name.get().strip() or hz_to_mhz(self.cur_hz)
        self.config["memories"].append({"name": name, "hz": int(self.cur_hz), "mode": self.cur_mode})
        save_config(self.config)
        self.mem_name.delete(0, tk.END)
        self.refresh_mem_tree()

    def update_memory(self):
        i, m = self.selected_memory()
        if m is None or self.cur_hz is None:
            return
        m["hz"], m["mode"] = int(self.cur_hz), self.cur_mode
        if self.mem_name.get().strip():
            m["name"] = self.mem_name.get().strip()
            self.mem_name.delete(0, tk.END)
        save_config(self.config)
        self.refresh_mem_tree()

    def selected_memory(self):
        sel = self.mem_tree.selection()
        if not sel:
            return None, None
        i = int(sel[0])
        return i, self.config["memories"][i]

    def delete_memory(self):
        i, m = self.selected_memory()
        if m is None:
            return
        del self.config["memories"][i]
        save_config(self.config)
        self.refresh_mem_tree()

    def export_memories(self):
        if not self.config["memories"]:
            messagebox.showinfo("Memories", "No memories to export.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".csv", initialfile="ic9700_memories.csv",
                                            filetypes=[("CSV", "*.csv"), ("All files", "*.*")])
        if not path:
            return
        try:
            with open(path, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["name", "freq_mhz", "mode"])
                for m in self.config["memories"]:
                    w.writerow([m["name"], f"{m['hz'] / 1e6:.6f}", m.get("mode") or ""])
        except Exception as e:
            messagebox.showerror("Memories", f"Could not write file:\n{e}")

    def import_memories(self):
        path = filedialog.askopenfilename(filetypes=[("CSV", "*.csv"), ("All files", "*.*")])
        if not path:
            return
        added = 0
        try:
            with open(path, newline="", encoding="utf-8-sig") as f:
                for row in csv.DictReader(f):
                    try:
                        hz = int(round(float(str(row.get("freq_mhz", "")).replace(",", ".")) * 1e6))
                        mode = (row.get("mode") or "").strip().upper() or None
                        self.config["memories"].append({
                            "name": (row.get("name") or hz_to_mhz(hz)).strip(), "hz": hz,
                            "mode": mode if mode in MODE_REVERSE else None})
                        added += 1
                    except (ValueError, TypeError):
                        pass
        except Exception as e:
            messagebox.showerror("Memories", f"Could not read file:\n{e}")
            return
        save_config(self.config)
        self.refresh_mem_tree()
        messagebox.showinfo("Memories", f"Imported {added} channel(s).\n(CSV columns: name, freq_mhz, mode)")

    def build_scan_tab(self, tab):
        self.scan_src = tk.StringVar(value="range")
        top = tk.Frame(tab, bg=PANEL)
        top.pack(fill="x", padx=px(10), pady=(px(8), px(2)))
        for text, val in (("Range", "range"), ("Memories", "mem")):
            tk.Radiobutton(top, text=text, variable=self.scan_src, value=val, bg=PANEL, fg=TEXT,
                           selectcolor=FIELD, activebackground=PANEL, activeforeground=TEXT,
                           font=F["ui"], highlightthickness=0).pack(side="left", padx=(0, px(6)))
        self.scan_from = self.entry(top, width=9)
        self.scan_from.pack(side="left", padx=(px(6), px(2)), ipady=px(2))
        self.scan_from.insert(0, "14.000")
        self.lbl(top, "–", fg=MUTED).pack(side="left")
        self.scan_to = self.entry(top, width=9)
        self.scan_to.pack(side="left", padx=px(2), ipady=px(2))
        self.scan_to.insert(0, "14.350")
        self.lbl(top, "MHz", fg=MUTED).pack(side="left", padx=px(2))
        self.scan_step_var = tk.StringVar(value="1 kHz")
        ttk.Combobox(top, textvariable=self.scan_step_var, state="readonly", width=8,
                     values=[s[0] for s in STEPS], font=F["ui"]).pack(side="left", padx=px(4))

        opt = tk.Frame(tab, bg=PANEL)
        opt.pack(fill="x", padx=px(10), pady=px(2))
        self.lbl(opt, "Dwell ms").pack(side="left")
        self.scan_dwell = self.spin(opt, 300, 3000, 50, 400)
        self.scan_dwell.pack(side="left", padx=px(4))
        self.lbl(opt, "Hold s").pack(side="left", padx=(px(6), 0))
        self.scan_hold = self.spin(opt, 1, 30, 1, 3, width=3)
        self.scan_hold.pack(side="left", padx=px(4))
        self.scan_sql = tk.BooleanVar(value=True)
        self.scan_use_s = tk.BooleanVar(value=False)
        self.check(opt, "Squelch", self.scan_sql).pack(side="left", padx=(px(8), 0))
        self.check(opt, "S ≥", self.scan_use_s).pack(side="left", padx=(px(4), 0))
        self.scan_s = self.spin(opt, 1, 9, 1, 3, width=2)
        self.scan_s.pack(side="left", padx=px(2))

        self.sweep_canvas = tk.Canvas(tab, height=px(92), bg=FIELD, highlightthickness=1,
                                      highlightbackground=BORDER, cursor="crosshair")
        self.sweep_canvas.pack(fill="both", expand=True, padx=px(10), pady=px(4))
        self.sweep_canvas.bind("<Configure>", lambda e: self.draw_sweep())
        self.sweep_canvas.bind("<Button-1>", self.sweep_click)

        brow = tk.Frame(tab, bg=PANEL)
        brow.pack(fill="x", padx=px(10), pady=(0, px(8)))
        self.btn_scan = RoundButton(brow, "START SCAN", self.toggle_scan, width=120, height=28, tone="amber",
                                    solid=True, font=F["ui_b"])
        self.btn_scan.pack(side="left")
        self.btn(brow, "Clear plot", self.clear_sweep, width=80).pack(side="left", padx=px(6))
        self.lbl(brow, "Click the plot to tune  ·  manual tuning stops the scan",
                 fg=DIM, font=F["small"]).pack(side="right")

    def toggle_scan(self):
        if self.scan:
            self.stop_scan()
        else:
            self.start_scan()

    def start_scan(self):
        if not self.running:
            messagebox.showinfo("Scan", "Connect to the radio first.")
            return
        try:
            if self.scan_src.get() == "mem":
                items = [(m["hz"], m.get("mode")) for m in self.config["memories"]]
                if not items:
                    messagebox.showinfo("Scan", "No memory channels saved yet (see the MEMORY tab).")
                    return
            else:
                lo = int(round(float(self.scan_from.get().replace(",", ".")) * 1_000_000))
                hi = int(round(float(self.scan_to.get().replace(",", ".")) * 1_000_000))
                step = dict(STEPS)[self.scan_step_var.get()]
                if hi <= lo:
                    raise ValueError("'To' must be higher than 'From'.")
                if (hi - lo) // step > 5000:
                    raise ValueError("Range has too many steps - use a larger step.")
                items = [(f, None) for f in range(lo, hi + 1, step)]
            dwell = max(MIN_DWELL, int(self.scan_dwell.get()) / 1000)
            hold = max(1, int(self.scan_hold.get()))
            s_thr = int(inv_interp(STR_CAL, (int(self.scan_s.get()) - 9) * 6))
        except (ValueError, KeyError) as e:
            messagebox.showerror("Scan", str(e) if str(e) and "invalid literal" not in str(e)
                                 and "could not convert" not in str(e) else "Check the scan settings.")
            return
        if not (self.scan_sql.get() or self.scan_use_s.get()):
            messagebox.showinfo("Scan", "Choose a stop condition (squelch and/or S-meter).")
            return
        if not (self.sweep and self.sweep["items"] == items):
            self.sweep = {"items": items, "levels": [None] * len(items), "idx": -1}
        self.scan = {"items": items, "idx": -1, "hold_until": 0.0, "last_move": 0.0, "dwell": dwell,
                     "hold": hold, "use_sql": self.scan_sql.get(), "use_s": self.scan_use_s.get(),
                     "s_thresh": s_thr, "levels": self.sweep["levels"], "sweep": self.sweep}
        self.btn_scan.set_active(True, "STOP SCAN")
        self.set_scan_badge("scan")
        self.draw_sweep()

    def stop_scan(self):
        self.scan = None
        self.btn_scan.set_active(False, "START SCAN")
        self.set_scan_badge(None)
        self.draw_sweep()

    def set_scan_badge(self, state):
        if state == "scan":
            self.chip_scan.set_active(True, "SCAN", tone="amber")
        elif state == "hold":
            self.chip_scan.set_active(True, "HOLD", tone="green")
        else:
            self.chip_scan.set_active(False, "SCAN")

    def clear_sweep(self):
        if self.sweep:
            self.sweep["levels"][:] = [None] * len(self.sweep["levels"])
        self.draw_sweep()

    def draw_sweep(self):
        c = self.sweep_canvas
        c.delete("all")
        w, h = c.winfo_width(), c.winfo_height()
        if w < 20:
            return
        pad, top, bot = px(8), px(8), h - px(16)
        sw = self.sweep
        # S9 guide line
        y9 = bot - (S9_RAW / METER_MAX) * (bot - top)
        c.create_line(pad, y9, w - pad, y9, fill=BORDER, dash=(2, 3))
        c.create_text(w - pad, y9 - 1, text="S9", anchor="se", fill=DIM, font=F["small_b"])
        c.create_line(pad, bot, w - pad, bot, fill=BORDER)
        if not sw:
            c.create_text(w / 2, (top + bot) / 2, text="Band activity appears here while scanning",
                          fill=DIM, font=F["small"])
            return
        items, levels = sw["items"], sw["levels"]
        n = len(items)
        span = w - 2 * pad
        cols = max(1, min(n, int(span)))
        colw = span / cols
        for col in range(cols):
            i0 = col * n // cols
            i1 = max(i0 + 1, (col + 1) * n // cols)
            vals = [v for v in levels[i0:i1] if v is not None]
            if not vals:
                continue
            v = max(vals)
            x = pad + (col + 0.5) * colw
            bh = max(1, (min(v, METER_MAX) / METER_MAX) * (bot - top))
            color = lerp_color(ACCENT_LO, ACCENT, v / S9_RAW) if v <= S9_RAW else lerp_color(AMBER, RED, (v - S9_RAW) / 121)
            c.create_line(x, bot, x, bot - bh, fill=color, width=max(1, colw - (1 if colw > 3 else 0)))
        if self.scan and 0 <= self.scan["idx"] < n:
            x = pad + (self.scan["idx"] + 0.5) / n * span
            c.create_line(x, top, x, bot, fill=AMBER)
        c.create_text(pad, h - px(2), text=hz_to_mhz(items[0][0]), anchor="sw", fill=MUTED, font=F["small_b"])
        c.create_text(w - pad, h - px(2), text=hz_to_mhz(items[-1][0]), anchor="se", fill=MUTED, font=F["small_b"])
        self.sweep_geom = (pad, span, n)

    def sweep_click(self, e):
        if not self.sweep or not hasattr(self, "sweep_geom"):
            return
        pad, span, n = self.sweep_geom
        idx = int((e.x - pad) / span * n)
        if 0 <= idx < n:
            hz, mode = self.sweep["items"][idx]
            self.request_frequency(hz)
            if mode in MODE_REVERSE:
                self.set_radio_mode(mode)

    def build_log_tab(self, tab):
        form = tk.Frame(tab, bg=PANEL)
        form.pack(fill="x", padx=px(10), pady=(px(8), px(2)))
        self.lbl(form, "Call", fg=MUTED, font=F["small"]).grid(row=0, column=0, sticky="w")
        self.qso_call = self.entry(form, width=11)
        self.qso_call.config(font=F["mono_b"])
        self.qso_call.grid(row=1, column=0, padx=(0, px(4)), ipady=px(2))
        self.qso_call.bind("<KeyRelease>", lambda e: self.check_dupe())
        self.lbl(form, "RST S / R", fg=MUTED, font=F["small"]).grid(row=0, column=1, columnspan=2, sticky="w")
        self.qso_rs = self.entry(form, width=4)
        self.qso_rs.grid(row=1, column=1, padx=(0, px(2)), ipady=px(2))
        self.qso_rs.insert(0, "59")
        self.qso_rr = self.entry(form, width=4)
        self.qso_rr.grid(row=1, column=2, padx=(0, px(4)), ipady=px(2))
        self.qso_rr.insert(0, "59")
        self.lbl(form, "Name", fg=MUTED, font=F["small"]).grid(row=0, column=3, sticky="w")
        self.qso_name = self.entry(form, width=10)
        self.qso_name.grid(row=1, column=3, padx=(0, px(4)), ipady=px(2))
        self.lbl(form, "Grid", fg=MUTED, font=F["small"]).grid(row=0, column=4, sticky="w")
        self.qso_grid = self.entry(form, width=7)
        self.qso_grid.grid(row=1, column=4, padx=(0, px(4)), ipady=px(2))
        self.lbl(form, "Notes", fg=MUTED, font=F["small"]).grid(row=0, column=5, sticky="w")
        self.qso_notes = self.entry(form, width=12)
        self.qso_notes.grid(row=1, column=5, sticky="ew", ipady=px(2))
        form.columnconfigure(5, weight=1)
        for e in (self.qso_call, self.qso_rs, self.qso_rr, self.qso_name, self.qso_grid, self.qso_notes):
            e.bind("<Return>", lambda ev: self.add_qso())

        r2 = tk.Frame(tab, bg=PANEL)
        r2.pack(fill="x", padx=px(10), pady=px(3))
        self.btn(r2, "LOG QSO", self.add_qso, width=90, tone="green").pack(side="left")
        self.lbl_dupe = tk.Label(r2, text="", bg=PANEL, fg=AMBER, font=F["small_b"])
        self.lbl_dupe.pack(side="left", padx=px(8))
        self.lbl_count = tk.Label(r2, text="", bg=PANEL, fg=MUTED, font=F["small_b"])
        self.lbl_count.pack(side="right")

        cols = ("utc", "call", "mhz", "mode", "rst", "name", "notes")
        box = tk.Frame(tab, bg=FIELD, highlightthickness=1, highlightbackground=BORDER)
        box.pack(fill="both", expand=True, padx=px(10), pady=px(2))
        self.qso_tree = ttk.Treeview(box, columns=cols, show="headings", height=4, selectmode="browse")
        for c, text, w in (("utc", "UTC", 104), ("call", "CALL", 72), ("mhz", "MHZ", 78), ("mode", "MODE", 46),
                           ("rst", "RST", 46), ("name", "NAME", 60), ("notes", "NOTES", 80)):
            self.qso_tree.heading(c, text=text, anchor="w")
            self.qso_tree.column(c, width=px(w), anchor="w")
        sb = ttk.Scrollbar(box, orient="vertical", command=self.qso_tree.yview)
        self.qso_tree.configure(yscrollcommand=sb.set)
        self.qso_tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        row = tk.Frame(tab, bg=PANEL)
        row.pack(fill="x", padx=px(10), pady=(px(3), px(8)))
        self.btn(row, "Delete", self.delete_qso, width=70, tone="red").pack(side="left", padx=px(2))
        self.btn(row, "Export CSV", self.export_csv, width=86).pack(side="right", padx=px(2))
        self.btn(row, "Export ADIF", self.export_adif, width=90).pack(side="right", padx=px(2))
        self.refresh_qso_tree()

    def refresh_qso_tree(self):
        self.qso_tree.delete(*self.qso_tree.get_children())
        for i, q in enumerate(self.qso_log):
            utc = f"{q['date'][:4]}-{q['date'][4:6]}-{q['date'][6:]} {q['time'][:2]}:{q['time'][2:4]}"
            self.qso_tree.insert("", 0, iid=str(i), values=(
                utc, q["call"], hz_to_mhz(q["hz"]), q.get("mode", ""),
                f"{q.get('rst_s', '')}/{q.get('rst_r', '')}", q.get("name", ""), q.get("notes", "")))
        self.lbl_count.config(text=f"{len(self.qso_log)} QSO{'s' if len(self.qso_log) != 1 else ''}")

    def check_dupe(self):
        call = self.qso_call.get().strip().upper()
        if not call:
            self.lbl_dupe.config(text="")
            return
        band = band_of(self.cur_hz) if self.cur_hz else ""
        prev = [q for q in self.qso_log if q["call"] == call]
        if not prev:
            self.lbl_dupe.config(text="NEW CALL", fg=GREEN)
        elif band and any(band_of(q["hz"]) == band for q in prev):
            last = max(prev, key=lambda q: q["date"] + q["time"])
            self.lbl_dupe.config(text=f"WORKED ON {band.upper()} · last {last['date'][:4]}-{last['date'][4:6]}-"
                                      f"{last['date'][6:]}", fg=AMBER)
        else:
            self.lbl_dupe.config(text=f"WORKED {len(prev)}x (new band)", fg=ACCENT)

    def add_qso(self):
        call = self.qso_call.get().strip().upper()
        if not call:
            messagebox.showinfo("Log", "Enter a callsign.")
            return
        if self.cur_hz is None:
            messagebox.showinfo("Log", "No frequency yet - connect to the radio first.")
            return
        now = datetime.now(timezone.utc)
        self.qso_log.append({
            "date": now.strftime("%Y%m%d"), "time": now.strftime("%H%M%S"), "call": call,
            "hz": int(self.cur_hz), "mode": self.cur_mode or "", "rst_s": self.qso_rs.get().strip(),
            "rst_r": self.qso_rr.get().strip(), "name": self.qso_name.get().strip(),
            "grid": self.qso_grid.get().strip().upper(), "notes": self.qso_notes.get().strip()})
        save_qso_log(self.qso_log)
        for e in (self.qso_call, self.qso_name, self.qso_grid, self.qso_notes):
            e.delete(0, tk.END)
        self.lbl_dupe.config(text="")
        self.refresh_qso_tree()
        self.flash_status(f"LOGGED {call}", GREEN)

    def delete_qso(self):
        sel = self.qso_tree.selection()
        if not sel:
            return
        if messagebox.askyesno("Log", "Delete the selected QSO?"):
            del self.qso_log[int(sel[0])]
            save_qso_log(self.qso_log)
            self.refresh_qso_tree()

    def export_adif(self):
        if not self.qso_log:
            messagebox.showinfo("Log", "The log is empty.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".adi", initialfile="ic9700_log.adi",
                                            filetypes=[("ADIF", "*.adi"), ("All files", "*.*")])
        if path:
            try:
                with open(path, "w", encoding="ascii", newline="\n") as f:
                    f.write(adif_document(self.qso_log, self.config.get("mycall", "")))
            except Exception as e:
                messagebox.showerror("Log", f"Could not write file:\n{e}")

    def export_csv(self):
        if not self.qso_log:
            messagebox.showinfo("Log", "The log is empty.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".csv", initialfile="ic9700_log.csv",
                                            filetypes=[("CSV", "*.csv"), ("All files", "*.*")])
        if path:
            try:
                with open(path, "w", newline="", encoding="utf-8") as f:
                    w = csv.writer(f)
                    w.writerow(["date_utc", "time_utc", "call", "freq_mhz", "mode", "rst_sent", "rst_rcvd",
                                "name", "grid", "notes"])
                    for q in self.qso_log:
                        w.writerow([q["date"], q["time"], q["call"], hz_to_mhz(q["hz"]), q.get("mode", ""),
                                    q.get("rst_s", ""), q.get("rst_r", ""), q.get("name", ""),
                                    q.get("grid", ""), q.get("notes", "")])
            except Exception as e:
                messagebox.showerror("Log", f"Could not write file:\n{e}")

    def set_led(self, color):
        c = self.lbl_led
        c.delete("all")
        s = px(10)
        c.create_oval(1, 1, s - 1, s - 1, fill=color, outline="")

    def set_status(self, text, color):
        self.lbl_status.config(text=text, fg=color)
        self.set_led(color)

    def flash_status(self, text, color, secs=4.0):
        """Temporary status message; reverts to the link status afterwards."""
        self.set_status(text, color)
        self.status_hold = time.time() + secs

        def back():
            if time.time() >= self.status_hold and self.running:
                self.set_link(self.link_ok)
        self.root.after(int(secs * 1000) + 50, back)

    def user_reconnect(self):
        self.want_connect = True
        self.disconnect()
        self.auto_connect(quiet=False)

    def on_link_lost(self, thread):
        if thread is not self.poll_thread or not self.want_connect:
            return
        self.disconnect(lost=True)
        self.set_status("CONNECTION LOST - RETRYING ...", ORANGE)

    def reconnect_tick(self):
        try:
            if SERIAL_READY and self.want_connect and not self.running:
                self.auto_connect(quiet=True)
        finally:
            self.root.after(RECONNECT_MS, self.reconnect_tick)

    def request_full_sync(self):
        self.full_sync = True
        if self.running:
            self.flash_status("RE-READING RADIO STATE ...", ACCENT, 2)

    def run_queue(self):
        while True:
            try:
                fn = self.cmdq.get_nowait()
            except queue.Empty:
                break
            try:
                fn()
            except Exception:
                pass

    def ui(self, fn, *args):
        """Thread-safe: queue a call for the Tk main loop (never touch Tk from the polling thread)."""
        self.uiq.put((fn, args))

    def ui_pump(self):
        try:
            for _ in range(200):
                try:
                    fn, args = self.uiq.get_nowait()
                except queue.Empty:
                    break
                try:
                    fn(*args)
                except Exception:
                    pass
        finally:
            self.root.after(30, self.ui_pump)

    # ------------------------------------------------------------ power on / off
    def radio_is_on(self):
        return bool(self.running and self.link_ok and not self.rig_off)

    def refresh_power(self):
        if not hasattr(self, "btn_power"):
            return
        on = self.radio_is_on()
        self.btn_power.set_active(on, "POWER" if on or not self.rig_off else "POWER OFF",
                                  tone="green" if on else "red", dim=not on and not self.running)

    def power_click(self):
        if not self.running:
            messagebox.showinfo("Power", "The program isn't connected to the radio's USB port.\n"
                                "Plug in the USB cable (the radio can be off) and wait for the port to open.")
            return
        if self.radio_is_on() and not messagebox.askyesno("Power", "Switch the FTDX10 OFF?"):
            return
        self.power_set(not self.radio_is_on())

    def power_set(self, on, who=""):
        """Switch the radio on / off (Tk thread). Used by the POWER key and by the phone page."""
        if not self.running:
            return
        if not on:
            if self.ptt_on or self.is_tx:
                self.ptt_on = False
                self.post_cat("TX0;")

            def off():
                self.cat("PS0;", reply=False)
                self.rig_off = True
                self.ui(self.set_link, False)
            self.post(off)
            self.flash_status(f"SWITCHING THE RADIO OFF{who} ...", AMBER, 3)
        else:
            self.post(self.power_on_job)
            self.flash_status(f"SWITCHING THE RADIO ON{who} ...", AMBER, 8)

    def power_on_job(self):                      # polling thread
        """FTDX10 CAT manual: send dummy data, then PS1; again after 1 s and before 2 s."""
        self.cat("PS1;", reply=False)
        time.sleep(1.2)
        self.cat("PS1;", reply=False)
        self.rig_off = False
        self.full_sync = True
        self.ui(self.refresh_power)

    def set_link(self, ok):
        self.link_ok = ok
        if ok:
            self.rig_off = False
        self.refresh_power()
        if time.time() < self.status_hold:
            return
        if not ok and self.rig_off:
            self.set_status("RADIO SWITCHED OFF - press POWER (top left) to switch it on", MUTED)
            return
        if ok:
            rig = f"{self.rig_name} " if self.rig_name else "RIG "
            self.set_status(f"ONLINE - {rig}CONNECTED ON {self.port_name} @ {self.baud}", GREEN)
        else:
            self.set_status("PORT OPEN BUT NO REPLY FROM RIG - CHECK POWER / COM PORT / CAT RATE", ORANGE)

    def refresh_ptt(self):
        on = self.ptt_on or self.is_tx
        if on and self.ptt_on:
            left = int(self.config.get("tx_timeout", 180) - (time.time() - self.ptt_since))
            self.btn_ptt.set_active(True, f"TX  {max(0, left)}s")
        elif on:
            self.btn_ptt.set_active(True, "TX")
        else:
            self.btn_ptt.set_active(False, "TRANSMIT")

    def step_hz(self):
        return dict(STEPS).get(self.step_var.get(), 12500)

    def step_tune(self, direction, step=None):
        if not self.running or self.cur_hz is None:
            return
        step = step or self.step_hz()
        cur = int(self.cur_hz)
        new = (cur // step + 1) * step if direction > 0 else ((cur - 1) // step) * step
        self.request_frequency(new)

    def key_step(self, direction, step=None):
        if isinstance(self.root.focus_get(), (tk.Entry, tk.Spinbox, ttk.Combobox)):
            return
        self.step_tune(direction, step)

    def freq_wheel(self, x, direction):
        if not self.running or self.cur_hz is None:
            return
        place = self.digit_at(x)
        if place:
            self.request_frequency(int(self.cur_hz) + direction * place)
        else:
            self.step_tune(direction)

    def digit_at(self, x):
        for x0, x1, place in self.digit_hits:
            if x0 <= x <= x1:
                return place
        return None

    def freq_hover(self, e):
        place = self.digit_at(e.x) if e is not None else None
        if place != self.hover_digit:
            self.hover_digit = place
            self.draw_freq(force=True)

    def request_frequency(self, hz, stop_scan=True):
        if not self.running:
            return
        hz = int(hz)
        if not (100_000 <= hz <= 2_000_000_000):
            return
        if stop_scan and self.scan:
            self.stop_scan()
        self.cur_hz = hz
        self.tune_time = time.time()
        self.draw_freq()
        b = band_of(hz)
        self.chip_band.set_active(bool(b), b.upper() if b else "BAND")
        self.pending_hz = hz
        if not self.freq_queued:
            self.freq_queued = True
            self.post(self.apply_pending_freq)

    def band_click(self, name):
        default = next(b[3] for b in BANDS if b[0] == name)
        self.request_frequency(self.config["band_last"].get(name, default))

    def change_frequency(self):
        if not self.running:
            return
        raw = self.freq_entry.get().strip().replace(",", ".")
        if not raw:
            return
        try:
            hz = int(round(float(raw) * 1_000_000))
            if not (100_000 <= hz <= 2_000_000_000):
                raise ValueError
        except ValueError:
            messagebox.showerror("Error", "Enter a valid frequency.\nExamples: 145.173 or 433.200")
            return
        self.request_frequency(hz)
        self.freq_entry.delete(0, tk.END)

    def schedule(self, name):
        """Coalesce redraw requests: run self.<name>() once when Tk is idle."""
        if name in self._pending_draw:
            return
        self._pending_draw.add(name)

        def run():
            self._pending_draw.discard(name)
            getattr(self, name)()
        self.root.after_idle(run)

    def clock_tick(self):
        self.clock_text = datetime.now(timezone.utc).strftime("%H:%M:%S")
        self.draw_status()
        self.ptt_watchdog()
        self.root.after(1000, self.clock_tick)

    def _lcd_box(self, c, x, cy, text, font, fg=LCD_TEXT, fill="", outline=None, padx=4, h=14):
        tw = font.measure(text)
        wbox = tw + 2 * px(padx)
        rrect(c, x, cy - px(h) / 2, x + wbox, cy + px(h) / 2, px(2), fill=fill,
              outline=outline if outline is not None else fg)
        c.create_text(x + wbox / 2, cy, text=text, fill=fg, font=font)
        return wbox

    def draw_tags(self):
        c = self.tags_canvas
        c.delete("all")
        w, h = c.winfo_width(), c.winfo_height()
        if w < 50:
            return
        cy = h / 2
        font = F["lcd_s"]
        solid_fill = {"red": LCD_RED, "green": LCD_GREEN, "amber": LCD_ORANGE, "accent": LCD_MAIN}

        def draw(t, x, right=False):
            if not t.active and t.hide_off:
                return 0
            text = t.text
            if t.solid and t.active:
                fill = solid_fill.get(t.tone, LCD_MAIN)
                if t.dim_active:
                    fill = lerp_color(fill, LCD_BG, 0.65)
                fg = "#ffffff" if t.tone in ("accent", "red") else "#000000"
                if t.dim_active:
                    fg = LCD_LABEL
                outline = fill
            elif not t.active:
                fill, fg, outline = "", LCD_DIM, LCD_DIM
            else:
                fill = ""
                fg = LCD_ORANGE if t.tone == "amber" else LCD_TEXT
                outline = LCD_ORANGE if t.tone == "amber" else LCD_LABEL
            tw = font.measure(text) + 2 * px(6)
            x0 = x - tw if right else x
            rrect(c, x0, cy - px(8), x0 + tw, cy + px(8), px(2), fill=fill, outline=outline)
            c.create_text(x0 + tw / 2, cy, text=text, fill=fg, font=font)
            return tw + px(4)

        x = px(6)
        for t in (self.chip_main, self.chip_mode, self.chip_fil, self.chip_dup, self.chip_sat, self.chip_scan):
            x += draw(t, x)
        if self.chip_band.active:
            c.create_text(x + px(4), cy, text=self.chip_band.text, fill=LCD_LABEL, font=F["lcd"], anchor="w")

        xr = w - px(4)
        for t in (self.chip_tx, self.chip_busy):
            xr -= draw(t, xr, right=True)

    def _freq_layout(self, ndig):
        """Widths of the frequency pieces for the current fonts: (MHz digit, dot, small dot, small digit)."""
        big, small = F["freq"], F["freq_s"]
        cw, sw = big.measure("8"), small.measure("8")
        dw, sdw = big.measure("."), small.measure(".")
        return cw, dw, sdw, sw, ndig * cw + 3 * cw + dw + sdw + 2 * sw

    def fit_freq_font(self, width, ndig):
        """Scale the frequency fonts so the readout spans the full screen width."""
        share, max_size = FREQ_SIZES.get(self.config.get("freq_size", "Medium"), FREQ_SIZES["Medium"])
        avail = max(200, (width - px(16)) * share)
        big, small = F["freq"], F["freq_s"]
        size = 40
        for _ in range(3):                 # converge: font sizes are in points, widths in pixels
            big.configure(size=size)
            small.configure(size=max(10, int(size * 0.6)))
            total = self._freq_layout(ndig)[4]
            new = max(20, min(max_size, int(size * avail / max(1, total))))
            if new == size:
                break
            size = new
        big.configure(size=size)
        small.configure(size=max(10, int(size * 0.6)))
        while size > 20 and self._freq_layout(ndig)[4] > avail:      # never overflow
            size -= 1
            big.configure(size=size)
            small.configure(size=max(10, int(size * 0.6)))
        h = big.metrics("linespace") + px(10)           # full text height plus a margin
        if abs(int(self.freq_canvas["height"]) - h) > 1:
            self.freq_canvas.configure(height=h)
            self.schedule("refit_height")

    def draw_freq(self, force=False):
        hz = self.cur_hz if self.running else None
        s = f"{hz:010d}" if hz is not None else None
        first_sig = 0
        if s:
            while first_sig < 3 and s[first_sig] == "0":
                first_sig += 1
        else:
            first_sig = 1                  # placeholder "---.---.--"
        ndig = 4 - first_sig
        w = self.freq_canvas.winfo_width()
        # Size the digits for the widest frequency this radio can show (2 MHz digits), so the
        # readout keeps the same size on every band instead of growing on low bands
        if w != getattr(self, "_freq_fit", None) and w > 50:
            self._freq_fit = w
            self.fit_freq_font(w, 2)
            force = True
        key = (hz, self.freq_color, self.hover_digit, w)
        if not force and key == self._freq_key:
            return
        self._freq_key = key
        c = self.freq_canvas
        c.delete("all")
        h = c.winfo_height()
        if w < 50:
            return
        big, small = F["freq"], F["freq_s"]
        cw, dw, sdw, sw, total = self._freq_layout(ndig)
        x = (w - total) / 2
        baseline = int(c["height"]) - px(10) - big.metrics("descent")   # one shared baseline for all digits
        self.digit_hits = []
        color = self.freq_color if hz is not None else LCD_DIM

        def digit(i, font, width):
            nonlocal x
            place = 10 ** (9 - i)
            ch = s[i] if s is not None else "-"
            c.create_text(x + width / 2, baseline + font.metrics("descent"), text=ch, fill=color, font=font,
                          anchor="s")
            if hz is not None and self.hover_digit == place:
                c.create_line(x + px(3), baseline + px(3), x + width - px(3), baseline + px(3), fill=ACCENT,
                              width=px(3))
            self.digit_hits.append((x, x + width, place))
            x += width

        def dot(font, width):
            nonlocal x
            c.create_text(x + width / 2, baseline + font.metrics("descent"), text=".", fill=color, font=font,
                          anchor="s")
            x += width

        for i in range(first_sig, 4):
            digit(i, big, cw)
        dot(big, dw)
        for i in range(4, 7):
            digit(i, big, cw)
        dot(small, sdw)
        x_hz = x
        for i in range(7, 9):
            digit(i, small, sw)
        # unit sits in the free space above the small 10 Hz digits
        top_small = baseline - small.metrics("ascent") * 0.78
        c.create_text((x_hz + x) / 2, top_small - px(4), text="MHz", fill=LCD_LABEL, font=F["lcd"], anchor="s")

    def _bar(self, c, x0, bar_w, y0, y1, frac, color_fn, n=60):
        seg_w = bar_w / n
        filled = int(round(frac * n))
        for i in range(n):
            xa, xb = x0 + i * seg_w + 1, x0 + (i + 1) * seg_w - 1
            fill = color_fn((i + 0.5) / n) if i < filled else LCD_SEG_OFF
            c.create_rectangle(xa, y0, xb, y1, fill=fill, outline="")

    def change_freq_size(self):
        self.config["freq_size"] = self.freq_size_var.get()
        self._freq_fit = None              # force a re-fit at the new size
        self.draw_freq(force=True)
        self.schedule("refit_height")

    def refit_height(self):
        self.root.update_idletasks()
        h = self.root.winfo_reqheight()
        w = max(self.root.winfo_width(), self.root.winfo_reqwidth())
        self.root.minsize(self.root.winfo_reqwidth(), h)
        self.root.geometry(f"{w}x{h}")


if __name__ == "__main__":
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)   # crisp text on high-DPI screens
        except Exception:
            pass
    root = tk.Tk()
    app = FTDX10Controller(root)
    root.mainloop()

# Troubleshooting

| Message or symptom | What to do |
| --- | --- |
| PORT OPEN BUT NO REPLY FROM RIG | Radio off, wrong COM port (use the **Enhanced** one), or the baud rate differs from the radio's CAT RATE |
| No COM ports for the radio | Install the Yaesu FTDX10 virtual COM port driver |
| Port busy | Another program (logger, WSJT-X) has the Enhanced COM port open: close it, or use the radio's other CAT routes |
| Settings not saved / "Access is denied" turning on HTTPS | Use version 1.5 or later (files are kept in AppData when installed) |
| Phone page can't be reached | Program running on the PC; Tailscale connected on both PC and phone; port 8075 (http) or 8076 (https) |
| TALK / microphone doesn't work | Use the **https** address (port 8076), not http |
| Phone audio silent | Choose the FTDX10's USB audio in Phone access; check AF output on the radio |
| Nothing transmitted from the phone | Radio: the mode's MOD SOURCE = REAR and REAR SELECT = USB |
| Builds | See [Windows builds](windows-installer.md#if-a-build-stops) |

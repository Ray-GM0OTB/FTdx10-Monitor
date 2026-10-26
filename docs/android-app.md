# Android app

*FTDX10* is the [phone page](phone-page.md) as a proper Android app: its own icon, full screen, no browser bars, and the microphone permission asked once. It talks to FTDX10 Monitor on your PC exactly like the phone page does.

## Building it (on the PC)

1. Put `build_apk.bat`, `build_apk.py` and `ftdx10.png` (the app icon) in one folder.
2. Double-click **build_apk.bat**.
3. The result is **FTDX10_Remote.apk** in the same folder.

The first build needs the Android tools. If you have already built the IC-9700 apps on this PC, their tools (in `%LOCALAPPDATA%\IC9700AndroidSDK`) are used and nothing is downloaded. Otherwise the builder downloads Java (if missing) and about 150 MB of Android tools into `%LOCALAPPDATA%\FTDX10AndroidSDK`. A log is written to `build_apk_log.txt`.

The app is signed with a key kept in that SDK folder. Keep it: updates must be signed with the same key, or Android asks you to uninstall the old version first.

## Installing it on the phone

1. Copy **FTDX10_Remote.apk** to the phone (USB cable, Google Drive, email to yourself…).
2. Open it on the phone. Allow **Install unknown apps** for the app you opened it with, if asked.
3. Open **FTDX10**, enter the PC's https address (from **Phone > Phone access** on the PC, e.g. `https://my-pc.tail1234.ts.net:8076/`) and sign in with the phone password.

The phone needs Tailscale connected, and FTDX10 Monitor must be running on the PC. The app installs beside the IC-9700 apps.

"""
FTDX10 Remote - builds the Android app (APK) for the FTDX10 Monitor phone page.  by GM0OTB

Run build_apk.bat (or:  py build_apk.py).  Needs an internet connection the first time:
  * Java (JDK 17) - installed with winget if it isn't on this PC
  * Android platform 34 and build-tools 34.0.0, straight from Google's repository (about 150 MB),
    kept in %LOCALAPPDATA%\\FTDX10AndroidSDK so later builds are quick (no spaces: the Android .bat
    tools fail on paths with spaces). If the IC-9700 apps were built on this PC, their tools in
    %LOCALAPPDATA%\\IC9700AndroidSDK are used and nothing is downloaded.
Result: FTDX10_Remote.apk next to this script. Copy it to the phone and open it to install.

The signing key is kept in the SDK folder above. Keep it: an update to the app must be signed with
the same key, otherwise Android asks you to uninstall the old version first.
"""
import glob
import io
import os
import re
import shutil
import struct
import subprocess
import sys
import urllib.request
import zipfile
import zlib

LITE = False                     # FTDX10 Monitor has one phone page

APP_VERSION = "1.0"
APP_VERSION_CODE = 1
PACKAGE = "uk.gm0otb.ftdx10"
APP_LABEL = "FTDX10"
APP_TITLE = "FTDX10 Remote"
PLATFORM = "android-34"
BUILD_TOOLS = "34.0.0"
REPO_XML = "https://dl.google.com/android/repository/repository2-3.xml"
KEY_PASS = "ftdx10remote"

HERE = os.path.dirname(os.path.abspath(__file__))


def _sdk_dir():
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    # Already built the IC-9700 apps on this PC? Use the Android tools downloaded for them.
    for name in ("IC9700AndroidSDK", "FTDX10AndroidSDK"):
        for d in (os.path.join(base, name), "C:\\" + name):
            if " " not in d and os.path.isdir(os.path.join(d, "platforms", PLATFORM)):
                return d
    d = os.path.join(base, "FTDX10AndroidSDK")
    if " " in d and sys.platform == "win32":         # e.g. a user name with a space in it
        d = r"C:\FTDX10AndroidSDK"
    return d


SDK = _sdk_dir()
BUILD = os.path.join(SDK, "apk_build_ftdx10")   # no spaces in the path
OUT_APK = os.path.join(HERE, "FTDX10_Remote.apk")
KEYSTORE = os.path.join(SDK, "ftdx10_remote.keystore")
LOG = os.path.join(HERE, "build_apk_log.txt")
WIN = sys.platform == "win32"

MANIFEST = """<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android" package="%s">
    <uses-permission android:name="android.permission.INTERNET"/>
    <uses-permission android:name="android.permission.RECORD_AUDIO"/>
    <uses-permission android:name="android.permission.MODIFY_AUDIO_SETTINGS"/>
    <application android:label="%s" android:icon="@mipmap/ic_launcher"
        android:usesCleartextTraffic="true" android:allowBackup="false"
        android:theme="@android:style/Theme.Material.NoActionBar">
        <activity android:name=".MainActivity" android:exported="true"
            android:launchMode="singleTask"
            android:windowSoftInputMode="adjustResize"
            android:configChanges="orientation|screenSize|screenLayout|smallestScreenSize|keyboard|keyboardHidden|uiMode|navigation">
            <intent-filter>
                <action android:name="android.intent.action.MAIN"/>
                <category android:name="android.intent.category.LAUNCHER"/>
            </intent-filter>
        </activity>
    </application>
</manifest>
""" % (PACKAGE, APP_LABEL)

JAVA = r'''package __PACKAGE__;

import android.Manifest;
import android.app.Activity;
import android.app.AlertDialog;
import android.content.DialogInterface;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.net.Uri;
import android.os.Bundle;
import android.text.InputType;
import android.util.TypedValue;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.view.WindowManager;
import android.view.inputmethod.EditorInfo;
import android.webkit.CookieManager;
import android.webkit.PermissionRequest;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.TextView;

/** FTDX10 Remote: the FTDX10 Monitor phone page as an app (by GM0OTB). */
public class MainActivity extends Activity {
    private static final int REQ_MIC = 1;
    private static final String PAGE = "__PAGE__";
    private static final int BG = Color.rgb(27, 28, 31);
    private WebView web;
    private SharedPreferences prefs;
    private PermissionRequest pendingPerm;
    private boolean onSetup;
    private String url = "";

    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        getWindow().setStatusBarColor(BG);
        getWindow().setNavigationBarColor(Color.rgb(21, 22, 24));
        prefs = getSharedPreferences("ftdx10", MODE_PRIVATE);
        url = prefs.getString("url", "");
        if (url.length() == 0) {
            showSetup(null);
        } else {
            showWeb();
        }
    }

    private int dp(int v) {
        return (int) TypedValue.applyDimension(TypedValue.COMPLEX_UNIT_DIP, v, getResources().getDisplayMetrics());
    }

    // ---------------------------------------------------------------- setup screen
    private void showSetup(String problem) {
        onSetup = true;
        LinearLayout box = new LinearLayout(this);
        box.setOrientation(LinearLayout.VERTICAL);
        box.setBackgroundColor(BG);
        box.setPadding(dp(24), dp(48), dp(24), dp(24));

        TextView title = new TextView(this);
        title.setText("__TITLE__");
        title.setTextColor(Color.WHITE);
        title.setTextSize(TypedValue.COMPLEX_UNIT_SP, 26);
        title.setGravity(Gravity.CENTER_HORIZONTAL);
        box.addView(title);

        TextView by = new TextView(this);
        by.setText("GM0OTB");
        by.setTextColor(Color.rgb(154, 161, 171));
        by.setGravity(Gravity.CENTER_HORIZONTAL);
        by.setPadding(0, dp(2), 0, dp(24));
        box.addView(by);

        if (problem != null) {
            TextView err = new TextView(this);
            err.setText(problem);
            err.setTextColor(Color.rgb(255, 166, 43));
            err.setTextSize(TypedValue.COMPLEX_UNIT_SP, 15);
            err.setPadding(0, 0, 0, dp(20));
            box.addView(err);
        }

        TextView help = new TextView(this);
        help.setText("Address of FTDX10 Monitor on your PC (shown in Phone > Phone access on the PC). "
                + "Use the https address so the TALK button can use the microphone.");
        help.setTextColor(Color.rgb(200, 205, 212));
        help.setTextSize(TypedValue.COMPLEX_UNIT_SP, 15);
        help.setPadding(0, 0, 0, dp(10));
        box.addView(help);

        final EditText addr = new EditText(this);
        addr.setSingleLine(true);
        addr.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_URI);
        addr.setImeOptions(EditorInfo.IME_ACTION_GO);
        addr.setHint("https://my-pc.tail1234.ts.net:8076/");
        addr.setHintTextColor(Color.rgb(92, 97, 106));
        addr.setTextColor(Color.WHITE);
        addr.setText(url);
        box.addView(addr, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.WRAP_CONTENT));

        Button go = new Button(this);
        go.setText("CONNECT");
        go.setTextColor(Color.WHITE);
        go.setBackgroundColor(Color.rgb(31, 95, 196));
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, dp(56));
        lp.topMargin = dp(16);
        box.addView(go, lp);

        TextView note = new TextView(this);
        note.setText("The phone needs Tailscale connected, and FTDX10 Monitor must be running on the PC.\n\n"
                + "Back button while connected: change this address or exit.");
        note.setTextColor(Color.rgb(154, 161, 171));
        note.setTextSize(TypedValue.COMPLEX_UNIT_SP, 13);
        note.setPadding(0, dp(24), 0, 0);
        box.addView(note);

        go.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                connect(addr.getText().toString());
            }
        });
        addr.setOnEditorActionListener(new TextView.OnEditorActionListener() {
            @Override
            public boolean onEditorAction(TextView v, int actionId, android.view.KeyEvent event) {
                connect(addr.getText().toString());
                return true;
            }
        });
        setContentView(box);
    }

    private void connect(String text) {
        String u = text.trim();
        if (u.length() == 0) {
            return;
        }
        if (!u.startsWith("http://") && !u.startsWith("https://")) {
            u = "https://" + u;
        }
        Uri parsed = Uri.parse(u);
        if (parsed.getHost() == null) {
            showSetup("That doesn't look like an address: " + text);
            return;
        }
        String path = parsed.getPath();
        if (PAGE.length() > 0 && (path == null || path.length() <= 1)) {
            u = (u.endsWith("/") ? u : u + "/") + PAGE;          // the PC address alone opens this app's page
        }
        url = u;
        prefs.edit().putString("url", url).apply();
        showWeb();
    }

    // ---------------------------------------------------------------- the phone page
    private void showWeb() {
        onSetup = false;
        if (web == null) {
            web = new WebView(this);
            web.setBackgroundColor(BG);
            WebSettings s = web.getSettings();
            s.setJavaScriptEnabled(true);
            s.setDomStorageEnabled(true);
            s.setMediaPlaybackRequiresUserGesture(false);
            s.setCacheMode(WebSettings.LOAD_NO_CACHE);
            s.setUserAgentString(s.getUserAgentString() + " FTDX10App/__VERSION__");
            CookieManager cm = CookieManager.getInstance();
            cm.setAcceptCookie(true);
            cm.setAcceptThirdPartyCookies(web, true);
            web.setWebChromeClient(new WebChromeClient() {
                @Override
                public void onPermissionRequest(final PermissionRequest request) {
                    runOnUiThread(new Runnable() {
                        @Override
                        public void run() {
                            handlePermission(request);
                        }
                    });
                }
            });
            web.setWebViewClient(new WebViewClient() {
                @Override
                public void onReceivedError(WebView view, WebResourceRequest request, WebResourceError error) {
                    if (request.isForMainFrame()) {
                        showSetup("Can't reach " + url + "\n(" + error.getDescription() + ")\n\n"
                                + "Check that FTDX10 Monitor is running on the PC and Tailscale is connected on this phone.");
                    }
                }

                @Override
                public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                    Uri target = request.getUrl();
                    String host = Uri.parse(url).getHost();
                    if (host != null && host.equalsIgnoreCase(target.getHost())) {
                        return false;                   // our own pages (also the https page) stay in the app
                    }
                    try {
                        startActivity(new Intent(Intent.ACTION_VIEW, target));
                    } catch (Exception e) {
                        // no browser: ignore
                    }
                    return true;
                }
            });
        }
        if (web.getParent() != null) {
            ((ViewGroup) web.getParent()).removeView(web);
        }
        setContentView(web);
        web.loadUrl(url);
    }

    private void handlePermission(PermissionRequest request) {
        boolean wantsMic = false;
        for (String r : request.getResources()) {
            if (PermissionRequest.RESOURCE_AUDIO_CAPTURE.equals(r)) {
                wantsMic = true;
            }
        }
        if (!wantsMic) {
            request.deny();
            return;
        }
        if (checkSelfPermission(Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED) {
            request.grant(new String[]{PermissionRequest.RESOURCE_AUDIO_CAPTURE});
        } else {
            pendingPerm = request;
            requestPermissions(new String[]{Manifest.permission.RECORD_AUDIO}, REQ_MIC);
        }
    }

    @Override
    public void onRequestPermissionsResult(int code, String[] permissions, int[] results) {
        if (code == REQ_MIC && pendingPerm != null) {
            if (results.length > 0 && results[0] == PackageManager.PERMISSION_GRANTED) {
                pendingPerm.grant(new String[]{PermissionRequest.RESOURCE_AUDIO_CAPTURE});
            } else {
                pendingPerm.deny();
            }
            pendingPerm = null;
        }
    }

    @Override
    public void onBackPressed() {
        if (onSetup) {
            if (web != null && url.length() > 0) {
                showWeb();
            } else {
                finish();
            }
            return;
        }
        if (web != null && web.canGoBack()) {
            web.goBack();
            return;
        }
        new AlertDialog.Builder(this)
                .setTitle("__TITLE__")
                .setItems(new CharSequence[]{"Reload", "Change PC address", "Exit"}, new DialogInterface.OnClickListener() {
                    @Override
                    public void onClick(DialogInterface d, int which) {
                        if (which == 0) {
                            web.reload();
                        } else if (which == 1) {
                            showSetup(null);
                        } else {
                            finish();
                        }
                    }
                })
                .setNegativeButton("Cancel", null)
                .show();
    }

    @Override
    protected void onPause() {
        super.onPause();
        CookieManager.getInstance().flush();       // stay signed in
    }

    @Override
    protected void onDestroy() {
        if (web != null) {
            web.destroy();
            web = null;
        }
        super.onDestroy();
    }
}
'''.replace("__VERSION__", APP_VERSION).replace("__PACKAGE__", PACKAGE).replace("__TITLE__", APP_TITLE) \
    .replace("__PAGE__", "lite" if LITE else "")


# ------------------------------------------------------------------ helpers
def say(msg, end="\n"):
    print(msg, end=end, flush=True)
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(msg + end)
    except OSError:
        pass


def fail(msg):
    say("\nERROR: " + msg)
    say(f"(Everything above is also in {LOG} - send that file if you need help.)")
    sys.exit(1)


def run(cmd, input=None, env=None, **kw):
    """Run a tool, showing (and logging) everything it prints."""
    cmd = [str(c) for c in cmd]
    say("  > " + " ".join(f'"{c}"' if " " in c else c for c in cmd))
    try:
        p = subprocess.Popen(cmd, stdin=subprocess.PIPE if input is not None else subprocess.DEVNULL,
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env)
    except OSError as e:
        fail(f"could not start {cmd[0]}: {e}")
    if input is not None:
        try:
            p.stdin.write(input.encode())
            p.stdin.close()
        except OSError:
            pass
    for line in iter(p.stdout.readline, b""):
        say("    " + line.decode("utf-8", "replace").rstrip())
    p.wait()
    if p.returncode != 0:
        fail(f"{os.path.basename(cmd[0])} failed (exit code {p.returncode}) - see the messages above.")
    return p


def missing_tools():
    d = os.path.join(SDK, "build-tools", BUILD_TOOLS)
    out = []
    for name in ("aapt2", "d8", "zipalign", "apksigner"):
        if not any(os.path.exists(os.path.join(d, name + ext)) for ext in (".exe", ".bat", "")):
            out.append(name)
    return out


def tool(name):
    """Build-tools on Windows are .exe or .bat."""
    base = os.path.join(SDK, "build-tools", BUILD_TOOLS, name)
    for ext in (".exe", ".bat", ""):
        if os.path.exists(base + ext):
            return base + ext
    fail(f"{name} not found in {os.path.dirname(base)}")


def download(url, dest):
    say(f"  downloading {url}")
    req = urllib.request.Request(url, headers={"User-Agent": "FTDX10-Remote-build"})
    with urllib.request.urlopen(req, timeout=120) as r, open(dest, "wb") as f:
        total = int(r.headers.get("Content-Length") or 0)
        done = 0
        while True:
            chunk = r.read(1 << 20)
            if not chunk:
                break
            f.write(chunk)
            done += len(chunk)
            if total:
                print(f"\r  {done * 100 // total}% of {total // (1 << 20)} MB", end="", flush=True)
    print()


# ------------------------------------------------------------------ 1. Java
def find_jdk():
    def ok(home):
        return home and os.path.exists(os.path.join(home, "bin", "javac" + (".exe" if WIN else "")))

    if ok(os.environ.get("JAVA_HOME")):
        return os.environ["JAVA_HOME"]
    javac = shutil.which("javac")
    if javac:
        home = os.path.dirname(os.path.dirname(os.path.realpath(javac)))
        if ok(home):
            return home
    pats = [r"C:\Program Files\Microsoft\jdk-*", r"C:\Program Files\Eclipse Adoptium\jdk-*",
            r"C:\Program Files\Java\jdk-*", r"C:\Program Files\Zulu\zulu-*", r"C:\Program Files\Android\Android Studio\jbr"]
    for p in pats:
        for home in sorted(glob.glob(p), reverse=True):
            if ok(home):
                return home
    return None


def java_version(home):
    try:
        out = subprocess.run([os.path.join(home, "bin", "javac"), "-version"], capture_output=True, text=True)
        m = re.search(r"(\d+)", (out.stdout or "") + (out.stderr or ""))
        return int(m.group(1)) if m else 0
    except OSError:
        return 0


def ensure_jdk():
    say("[1/5] Java")
    home = find_jdk()
    if home and java_version(home) >= 17:
        say(f"  using {home}")
        return home
    if not WIN:
        fail("Install a JDK 17 or newer and run this again.")
    say("  JDK 17 not found - installing Microsoft OpenJDK 17 with winget ...")
    subprocess.run(["winget", "install", "--id", "Microsoft.OpenJDK.17", "-e",
                    "--accept-package-agreements", "--accept-source-agreements"])
    home = find_jdk()
    if not home or java_version(home) < 17:
        fail("Could not install Java automatically. Install 'Microsoft Build of OpenJDK 17' from "
             "https://learn.microsoft.com/java/openjdk/download and run this again.")
    say(f"  using {home}")
    return home


# ------------------------------------------------------------------ 2. Android SDK
# The two packages needed (platform 34, build-tools 34.0.0) are downloaded straight from Google's
# repository and unpacked: no sdkmanager (it is being replaced and mangles "a;b" names on Windows).
REPO_BASE = "https://dl.google.com/android/repository/"


def repo_archive(xml_text, path):
    """(url, sha1, size) of the Windows (or any-OS) archive for a package in repository2-3.xml."""
    import xml.etree.ElementTree as ET
    root = ET.fromstring(xml_text)
    for pkg in root.iter():
        if not pkg.tag.endswith("remotePackage") or pkg.get("path") != path:
            continue
        best = None
        for arch in pkg.iter():
            if not arch.tag.endswith("archive"):
                continue
            host = next((e.text for e in arch.iter() if e.tag.endswith("host-os")), None)
            comp = next((e for e in arch.iter() if e.tag.endswith("complete")), None)
            if comp is None:
                continue
            url = next((e.text for e in comp.iter() if e.tag.endswith("url")), None)
            sha1 = next((e.text for e in comp.iter() if e.tag.endswith("checksum")), None)
            size = next((e.text for e in comp.iter() if e.tag.endswith("size")), "0")
            if not url:
                continue
            if host in (None, "windows" if WIN else "linux"):
                best = (url if "://" in url else REPO_BASE + url, (sha1 or "").strip(), int(size or 0))
                if host:
                    break
        if best:
            return best
    return None


def install_package(xml_text, path, dest):
    info = repo_archive(xml_text, path)
    if not info:
        fail(f"{path} is not listed in Google's Android repository any more - tell GM0OTB / update build_apk.py")
    url, sha1, size = info
    say(f"  {path}: {url} ({size // (1 << 20)} MB)")
    z = os.path.join(SDK, "download.zip")
    try:
        download(url, z)
    except Exception as e:
        fail(f"could not download {url}: {e}\nCheck the internet connection and run this again.")
    if sha1:
        import hashlib
        h = hashlib.sha1()
        with open(z, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        if h.hexdigest().lower() != sha1.lower():
            os.remove(z)
            fail(f"the download of {path} is damaged (checksum mismatch) - run this again")
    tmp = os.path.join(SDK, "unpack_tmp")
    shutil.rmtree(tmp, ignore_errors=True)
    with zipfile.ZipFile(z) as zf:
        zf.extractall(tmp)
    os.remove(z)
    top = os.listdir(tmp)
    src = os.path.join(tmp, top[0]) if len(top) == 1 and os.path.isdir(os.path.join(tmp, top[0])) else tmp
    shutil.rmtree(dest, ignore_errors=True)
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    shutil.move(src, dest)
    shutil.rmtree(tmp, ignore_errors=True)


def ensure_sdk(jdk):
    say("[2/5] Android SDK (first time only: about 150 MB)")
    os.makedirs(SDK, exist_ok=True)
    pdir = os.path.join(SDK, "platforms", PLATFORM)
    bdir = os.path.join(SDK, "build-tools", BUILD_TOOLS)
    need_platform = not os.path.exists(os.path.join(pdir, "android.jar"))
    need_tools = bool(missing_tools())
    if not (need_platform or need_tools):
        say(f"  using {SDK}")
        return
    say("  By building you accept the Android SDK licence: https://developer.android.com/studio/terms")
    say("  reading Google's package list ...")
    try:
        req = urllib.request.Request(REPO_XML, headers={"User-Agent": "FTDX10-Remote-build"})
        with urllib.request.urlopen(req, timeout=60) as r:
            xml_text = r.read().decode("utf-8", "replace")
    except Exception as e:
        fail(f"could not read {REPO_XML}: {e}")
    if need_platform:
        install_package(xml_text, f"platforms;{PLATFORM}", pdir)
    if need_tools:
        install_package(xml_text, f"build-tools;{BUILD_TOOLS}", bdir)
    if not os.path.exists(os.path.join(pdir, "android.jar")) or missing_tools():
        found = ", ".join(sorted(os.listdir(bdir))[:40]) if os.path.isdir(bdir) else "(nothing)"
        fail("the Android packages unpacked, but the tools aren't where expected.\n"
             f"  in {bdir}: {found}\n"
             "If antivirus software is running it may have removed aapt2.exe - allow that folder and run this again.")
    say("  Android SDK ready")


# ------------------------------------------------------------------ 3. sources + icon
def png(size, colour=(0x5a, 0xb8, 0xff)):
    """Simple launcher icon (used when ftdx10.png isn't next to this script)."""
    rows = []
    for y in range(size):
        row = bytearray([0])
        for x in range(size):
            r = ((x - size / 2) ** 2 + (y - size / 2) ** 2) ** 0.5
            ring = size * 0.30 < r < size * 0.40
            bar = abs(x - size / 2) < size * 0.05 and size * 0.12 < y < size * 0.52
            row += bytes(colour) if (ring and y > size * 0.32) or bar else bytes((0x1b, 0x1c, 0x1f))
        rows.append(bytes(row))

    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(b"".join(rows), 9)) + chunk(b"IEND", b""))


def write_sources():
    say("[3/5] App sources")
    shutil.rmtree(BUILD, ignore_errors=True)
    src = os.path.join(BUILD, "src", *PACKAGE.split("."))
    os.makedirs(src)
    with open(os.path.join(src, "MainActivity.java"), "w", encoding="utf-8") as f:
        f.write(JAVA)
    with open(os.path.join(BUILD, "AndroidManifest.xml"), "w", encoding="utf-8") as f:
        f.write(MANIFEST)
    icon_dir = os.path.join(BUILD, "res", "mipmap-xxxhdpi")
    os.makedirs(icon_dir)
    dest = os.path.join(icon_dir, "ic_launcher.png")
    own = os.path.join(HERE, "ftdx10.png")
    base = own
    if os.path.exists(own):
        shutil.copy(own, dest)
        say(f"  icon: {os.path.basename(own)}")
    elif LITE and os.path.exists(base) and lite_badge(base, dest):
        say("  icon: ic9700.png with a green LITE badge (put ic9700_lite.png here to use your own)")
    else:
        with open(dest, "wb") as f:
            f.write(png(192, (0x2f, 0xd1, 0x6b) if LITE else (0x5a, 0xb8, 0xff)))
        say("  icon: built-in (put %s next to this script to use your own)" % os.path.basename(own))


def lite_badge(src, dest):
    """ic9700.png with a green LITE band across the bottom, so the two apps look different."""
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        subprocess.run([sys.executable, "-m", "pip", "install", "--quiet", "pillow"], capture_output=True)
        try:
            from PIL import Image, ImageDraw, ImageFont
        except ImportError:
            return False
    try:
        im = Image.open(src).convert("RGBA").resize((192, 192))
        d = ImageDraw.Draw(im)
        d.rectangle([0, 136, 192, 192], fill=(0x2f, 0xd1, 0x6b, 255))
        try:
            font = ImageFont.truetype("arialbd.ttf" if WIN else "DejaVuSans-Bold.ttf", 40)
        except OSError:
            font = ImageFont.load_default()
        d.text((96, 164), "LITE", fill=(0, 0x2b, 0x12, 255), font=font, anchor="mm")
        im.save(dest)
        return True
    except Exception:
        return False


# ------------------------------------------------------------------ 4. build
def build(jdk):
    say("[4/5] Building")
    jar = os.path.join(SDK, "platforms", PLATFORM, "android.jar")
    env = dict(os.environ, JAVA_HOME=jdk)
    env["PATH"] = os.path.join(jdk, "bin") + os.pathsep + env.get("PATH", "")
    res_zip = os.path.join(BUILD, "res.zip")
    run([tool("aapt2"), "compile", "--dir", os.path.join(BUILD, "res"), "-o", res_zip], env=env)
    unsigned = os.path.join(BUILD, "unsigned.apk")
    run([tool("aapt2"), "link", "-o", unsigned, "-I", jar, "--manifest", os.path.join(BUILD, "AndroidManifest.xml"),
         "--min-sdk-version", "24", "--target-sdk-version", "34",
         "--version-code", str(APP_VERSION_CODE), "--version-name", APP_VERSION, res_zip], env=env)
    classes = os.path.join(BUILD, "classes")
    os.makedirs(classes)
    javas = glob.glob(os.path.join(BUILD, "src", "**", "*.java"), recursive=True)
    run([os.path.join(jdk, "bin", "javac"), "-encoding", "UTF-8", "-source", "8", "-target", "8",
         "-Xlint:-options", "-bootclasspath", jar, "-classpath", jar, "-d", classes] + javas, env=env)
    dex_dir = os.path.join(BUILD, "dex")
    os.makedirs(dex_dir)
    class_files = glob.glob(os.path.join(classes, "**", "*.class"), recursive=True)
    run([tool("d8"), "--release", "--min-api", "24", "--lib", jar, "--output", dex_dir] + class_files, env=env)
    with zipfile.ZipFile(unsigned, "a", zipfile.ZIP_DEFLATED) as zf:
        zf.write(os.path.join(dex_dir, "classes.dex"), "classes.dex")
    aligned = os.path.join(BUILD, "aligned.apk")
    run([tool("zipalign"), "-p", "-f", "4", unsigned, aligned], env=env)
    return aligned, env


# ------------------------------------------------------------------ 5. sign
def sign(aligned, jdk, env):
    say("[5/5] Signing")
    if not os.path.exists(KEYSTORE):
        say("  creating the app's signing key (kept in the SDK folder - keep it for future updates)")
        run([os.path.join(jdk, "bin", "keytool"), "-genkeypair", "-keystore", KEYSTORE, "-alias", "ftdx10",
             "-keyalg", "RSA", "-keysize", "2048", "-validity", "10000", "-storepass", KEY_PASS,
             "-keypass", KEY_PASS, "-dname", "CN=GM0OTB, O=FTDX10 Remote"], env=env)
    if os.path.exists(OUT_APK):
        os.remove(OUT_APK)
    run([tool("apksigner"), "sign", "--ks", KEYSTORE, "--ks-key-alias", "ftdx10", "--ks-pass", "pass:" + KEY_PASS,
         "--key-pass", "pass:" + KEY_PASS, "--out", OUT_APK, aligned], env=env)
    run([tool("apksigner"), "verify", OUT_APK], env=env)


def main():
    try:
        os.remove(LOG)
    except OSError:
        pass
    say(f"{APP_TITLE} - Android app builder (GM0OTB)\n")
    say(f"  Python {sys.version.split()[0]}, SDK folder {SDK}")
    jdk = ensure_jdk()
    ensure_sdk(jdk)
    write_sources()
    aligned, env = build(jdk)
    sign(aligned, jdk, env)
    shutil.rmtree(BUILD, ignore_errors=True)
    say(f"\nDone: {OUT_APK}  ({os.path.getsize(OUT_APK) // 1024} KB)")
    say("Copy it to the phone (USB, Google Drive, e-mail ...), open it and allow 'install unknown apps' when asked.")


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except BaseException:
        import traceback
        say("\nUNEXPECTED ERROR:\n" + traceback.format_exc())
        say(f"(Also saved in {LOG} - send that file if you need help.)")
        sys.exit(1)

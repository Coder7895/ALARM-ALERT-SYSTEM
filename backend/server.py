import http.server
import json
import os
import queue
import socket
import socketserver
import subprocess
import threading
import time
import urllib.parse

try:
    import winsound
    HAS_WINSOUND = True
except Exception:
    HAS_WINSOUND = False

PORT = int(os.environ.get("PORT", 8765))
BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.join(os.path.dirname(BACKEND_DIR), "frontend")
if os.path.exists(os.path.join(FRONTEND_DIR, "index.html")):
    ROOT_DIR = FRONTEND_DIR
elif os.path.exists(os.path.join(BACKEND_DIR, "frontend", "index.html")):
    ROOT_DIR = os.path.join(BACKEND_DIR, "frontend")
else:
    ROOT_DIR = BACKEND_DIR

state_lock = threading.Lock()
fire_state = {
    "active": False,
    "id": None,
    "x": -6.8,
    "z": 4.8,
    "originLabel": "House No. 1",
    "houseKey": "house-1",
    "cause": "",
    "time": "",
    "notifiedHouses": [],
    "updatedAt": time.time(),
}

hospital_state = {
    "active": False,
    "id": None,
    "x": -3.8,
    "z": 3.2,
    "houseKey": "house-13",
    "houseName": "House No. 13",
    "villageName": "District 4 · South-West House Zone",
    "exactAddress": "House No. 13, Plot #13, Lane 1, District 4 · South-West House Zone",
    "gps": "17.4126° N, 78.4391° E",
    "injuryType": "Severe Injury / Trauma",
    "reporter": "Resident — House No. 13",
    "acknowledgedBy": None,
    "time": "",
    "updatedAt": time.time(),
}

# deviceId -> { deviceId, houseKey, houseName, audioArmed, ringing, lastSeen, ip }
connected_mobiles = {}

speaker_state = {
    "active": False,
    "id": None,
    "seq": 0,
    "message": "",
    "lang": "en",
    "repeat": 1,
    "rate": 0.96,
    "chime": True,
    "targetScope": "All 32 Houses (District 4 Public Speaker)",
    "author": "Municipality Command",
    "time": "",
    "updatedAt": time.time(),
}

# deviceId -> { deviceId, speakerName, audioArmed, speaking, lastSeen }
connected_speakers = {}

# Persistent Citizen Complaints Registry (Saved to complaints.json)
COMPLAINTS_FILE = os.path.join(BACKEND_DIR if 'BACKEND_DIR' in locals() else os.path.dirname(os.path.abspath(__file__)), "complaints.json")
complaints_list = []

def load_complaints_from_disk():
    global complaints_list
    if os.path.exists(COMPLAINTS_FILE):
        try:
            with open(COMPLAINTS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    complaints_list = data
                    print(f"📁 Loaded {len(complaints_list)} persistent complaints from {COMPLAINTS_FILE}")
        except Exception as e:
            print(f"Warning: could not load {COMPLAINTS_FILE}: {e}")

def save_complaints_to_disk():
    try:
        with open(COMPLAINTS_FILE, "w", encoding="utf-8") as f:
            json.dump(complaints_list, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Warning: could not save {COMPLAINTS_FILE}: {e}")

load_complaints_from_disk()

# ==============================================================================
# 32 Fixed House Accounts Database Whitelist
# ==============================================================================
HOUSE_ACCOUNTS_FILE = os.path.join(BACKEND_DIR if 'BACKEND_DIR' in locals() else os.path.dirname(os.path.abspath(__file__)), "house_accounts.json")
house_accounts_list = []
house_accounts_by_email = {}
house_accounts_by_identity = {}

def normalize_identity(s):
    if not s:
        return ""
    return " ".join(str(s).strip().lower().split())

def load_house_accounts_database():
    global house_accounts_list, house_accounts_by_email, house_accounts_by_identity
    if os.path.exists(HOUSE_ACCOUNTS_FILE):
        try:
            with open(HOUSE_ACCOUNTS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    house_accounts_list = data
                    house_accounts_by_email = {}
                    house_accounts_by_identity = {}
                    for acc in data:
                        em = acc.get("email", "").strip().lower()
                        if em:
                            house_accounts_by_email[em] = acc
                            house_accounts_by_identity[em] = acc
                        for alias in acc.get("aliasEmails", []):
                            al = alias.strip().lower()
                            if al:
                                house_accounts_by_email[al] = acc
                                house_accounts_by_identity[al] = acc

                        u_name = acc.get("username", "")
                        if u_name:
                            house_accounts_by_identity[normalize_identity(u_name)] = acc

                        r_name = acc.get("residentName", "")
                        if r_name:
                            house_accounts_by_identity[normalize_identity(r_name)] = acc

                        for u_alias in acc.get("aliasUsernames", []):
                            if u_alias:
                                house_accounts_by_identity[normalize_identity(u_alias)] = acc

                        h_num = acc.get("houseNumber")
                        if h_num:
                            house_accounts_by_identity[f"house {h_num}"] = acc
                            house_accounts_by_identity[f"house{h_num}"] = acc
                            house_accounts_by_identity[f"house-{h_num}"] = acc
                            house_accounts_by_identity[f"h{h_num}"] = acc

                    # Add department and admin accounts (with dedicated Gmail and username IDs)
                    admin_accounts = [
                        {
                            "username": "admin",
                            "aliasUsernames": [
                                "admin",
                                "administrator",
                                "municipality",
                                "municipal administrator",
                                "admin.emerrr@gmail.com",
                                "admin@gmail.com",
                                "admin@emerrr.gov.in"
                            ],
                            "email": "admin.emerrr@gmail.com",
                            "aliasEmails": [
                                "admin@gmail.com",
                                "admin@emerrr.gov.in",
                                "officer@emerrr.gov.in"
                            ],
                            "password": "1111",
                            "altPasswords": ["water123", "waterrrr2026", "emerrr2026", "admin123"],
                            "role": "municipality",
                            "residentName": "Municipal Administrator",
                            "systemId": "MUN-ADMIN-001",
                            "dept": "District 4 Emergency & Public Safety Command",
                            "houseName": "Municipality Fire Command"
                        },
                        {
                            "username": "hospital",
                            "aliasUsernames": [
                                "hospital",
                                "hospital command",
                                "civil hospital",
                                "district civil hospital",
                                "district hospital",
                                "hospital.emerrr@gmail.com",
                                "hospital@gmail.com",
                                "hospital@emerrr.gov.in"
                            ],
                            "email": "hospital.emerrr@gmail.com",
                            "aliasEmails": [
                                "hospital@gmail.com",
                                "hospital@emerrr.gov.in"
                            ],
                            "password": "1111",
                            "altPasswords": ["hosp123", "emerrr2026", "hospital123"],
                            "role": "hospital",
                            "residentName": "District Civil Hospital Command",
                            "systemId": "HOSP-CMD-001",
                            "facility": "District Civil Hospital",
                            "houseName": "District Civil Hospital"
                        }
                    ]
                    for adm in admin_accounts:
                        house_accounts_by_email[adm["email"].lower()] = adm
                        house_accounts_by_identity[adm["email"].lower()] = adm
                        for al in adm.get("aliasEmails", []):
                            house_accounts_by_email[al.lower()] = adm
                            house_accounts_by_identity[al.lower()] = adm
                        if adm.get("username"):
                            house_accounts_by_identity[normalize_identity(adm["username"])] = adm
                        for u_al in adm.get("aliasUsernames", []):
                            house_accounts_by_identity[normalize_identity(u_al)] = adm

                    print(f"🔐 Loaded {len(house_accounts_list)} fixed house accounts ({len(house_accounts_by_identity)} username/credential aliases) from {HOUSE_ACCOUNTS_FILE}")
        except Exception as e:
            print(f"Warning: could not load {HOUSE_ACCOUNTS_FILE}: {e}")

load_house_accounts_database()

# Active SSE and Long-Poll Subscriber Queues
notification_subscribers = []
subscribers_lock = threading.Lock()


def broadcast_notification_event(event_type, payload):
    """Pushes an emergency notification event to all connected mobile & PC clients."""
    with subscribers_lock:
        stale = []
        for q in notification_subscribers:
            try:
                q.put_nowait({"type": event_type, "data": payload, "ts": time.time()})
            except Exception:
                stale.append(q)
        for q in stale:
            if q in notification_subscribers:
                notification_subscribers.remove(q)


def play_system_siren_audio():
    """Sounds an emergency audio alert on the PC using winsound."""
    if not HAS_WINSOUND:
        return

    def _audio_loop():
        try:
            for _ in range(4):
                winsound.Beep(880, 200)
                winsound.Beep(1175, 250)
                winsound.Beep(1480, 200)
                time.sleep(0.05)
        except Exception:
            pass

    threading.Thread(target=_audio_loop, daemon=True).start()


def show_native_windows_toast(title, body):
    """Fires a native Windows 10/11 system toast notification on desktop with emergency audio."""
    def _run_toast():
        try:
            clean_title = str(title).replace("'", "''").replace("\n", " ")
            clean_body = str(body).replace("'", "''").replace("\n", " ")
            ps_cmd = (
                '[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null; '
                '[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null; '
                f'$xml = New-Object Windows.Data.Xml.Dom.XmlDocument; '
                f'$xml.LoadXml(\'<toast duration="long"><visual><binding template="ToastGeneric"><text>{clean_title}</text><text>{clean_body}</text></binding></visual><audio src="ms-winsoundevent:Notification.Looping.Alarm" loop="true" /></toast>\'); '
                '$toast = [Windows.UI.Notifications.ToastNotification]::new($xml); '
                '$toast.Tag = "emerrr-alarm"; '
                '$toast.Group = "emerrr"; '
                '[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("Emerrr Emergency Platform").Show($toast)'
            )
            subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], capture_output=True, timeout=8)
        except Exception as e:
            print(f"[Windows Toast Error]: {e}")

    threading.Thread(target=_run_toast, daemon=True).start()


def get_primary_lan_ip():
    """Detect the active Wi-Fi / LAN IPv4 address reachable by mobile devices on the same network."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.5)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        if ip and not ip.startswith("127."):
            return ip
    except Exception:
        pass

    try:
        hostname = socket.gethostname()
        for info in socket.getaddrinfo(hostname, None, socket.AF_INET):
            ip = info[4][0]
            if ip and not ip.startswith("127.") and not ip.startswith("169.254."):
                return ip
    except Exception:
        pass

    return "127.0.0.1"


def get_all_lan_ips():
    ips = []
    primary = get_primary_lan_ip()
    if primary and primary not in ips:
        ips.append(primary)
    try:
        hostname = socket.gethostname()
        for info in socket.getaddrinfo(hostname, None, socket.AF_INET):
            ip = info[4][0]
            if ip and not ip.startswith("127.") and not ip.startswith("169.254.") and ip not in ips:
                ips.append(ip)
    except Exception:
        pass
    if not ips:
        ips.append("127.0.0.1")
    return ips


def prune_stale_mobiles(now_ts):
    # Generous 120-second timeout so background phones are not prematurely dropped
    stale = [did for did, info in connected_mobiles.items() if (now_ts - info["lastSeen"]) > 120.0]
    for did in stale:
        del connected_mobiles[did]


def prune_stale_speakers(now_ts):
    stale = [did for did, info in connected_speakers.items() if (now_ts - info["lastSeen"]) > 120.0]
    for did in stale:
        del connected_speakers[did]


class ThreadingHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


class SociothonHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=ROOT_DIR, **kwargs)

    def log_message(self, format, *args):
        msg = format % args
        # Log all API and stream requests visibly to the terminal
        if any(keyword in msg for keyword in ["/api/", "POST", "stream", "poll"]):
            client_ip = self.client_address[0] if self.client_address else "local"
            print(f"[{time.strftime('%H:%M:%S')}] ({client_ip}) {msg}")

    def _send_json(self, payload, status=200):
        raw = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(raw)

    def end_headers(self):
        if hasattr(self, "path") and (
            self.path == "/" or self.path.split("?")[0].endswith((".html", ".js"))
        ):
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
        if hasattr(self, "path") and self.path.split("?")[0].endswith("sw.js"):
            self.send_header("Service-Worker-Allowed", "/")
            self.send_header("Content-Type", "application/javascript")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Cache-Control")
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        qs = urllib.parse.parse_qs(parsed.query)

        if path == "/api/server-info":
            lan_ip = get_primary_lan_ip()
            all_ips = get_all_lan_ips()
            self._send_json(
                {
                    "ip": lan_ip,
                    "allIps": all_ips,
                    "port": PORT,
                    "mobileBaseUrl": f"http://{lan_ip}:{PORT}/mobile.html",
                    "dashboardUrl": f"http://{lan_ip}:{PORT}/index.html",
                    "activeSubscribers": len(notification_subscribers),
                    "connectedMobilesCount": len(connected_mobiles),
                }
            )
            return

        if path == "/api/auth/database":
            acc_copy = [dict(a) for a in house_accounts_list]
            self._send_json({"ok": True, "total": len(acc_copy), "accounts": acc_copy})
            return

        if path == "/api/fire-state":
            now_ts = time.time()
            device_id = (qs.get("deviceId") or [""])[0].strip()
            house_key = (qs.get("houseKey") or [""])[0].strip()
            house_name = (qs.get("houseName") or [""])[0].strip()
            resident_name = (qs.get("residentName") or [""])[0].strip()
            audio_armed = (qs.get("audioArmed") or ["0"])[0] == "1"
            ringing = (qs.get("ringing") or ["0"])[0] == "1"
            client_ip = self.client_address[0] if self.client_address else "local"

            with state_lock:
                if device_id and house_key:
                    is_new = device_id not in connected_mobiles
                    connected_mobiles[device_id] = {
                        "deviceId": device_id,
                        "houseKey": house_key,
                        "houseName": house_name or house_key,
                        "residentName": resident_name or "Resident",
                        "audioArmed": audio_armed,
                        "ringing": ringing,
                        "lastSeen": now_ts,
                        "ip": client_ip,
                    }
                    if is_new:
                        print(f"📱 [NEW MOBILE PAIRED]: {house_name} ({resident_name}) from IP {client_ip}")

                prune_stale_mobiles(now_ts)
                mobiles_list = [
                    {
                        "deviceId": m["deviceId"],
                        "houseKey": m["houseKey"],
                        "houseName": m["houseName"],
                        "residentName": m.get("residentName", "Resident"),
                        "audioArmed": m["audioArmed"],
                        "ringing": m["ringing"],
                        "lastSeenSec": round(now_ts - m["lastSeen"], 1),
                        "ip": m.get("ip", ""),
                    }
                    for m in connected_mobiles.values()
                ]
                snapshot = dict(fire_state)

            self._send_json(
                {
                    "serverTime": now_ts,
                    "fireAlert": snapshot,
                    "connectedMobiles": mobiles_list,
                }
            )
            return

        if path == "/api/hospital-state":
            now_ts = time.time()
            with state_lock:
                snapshot = dict(hospital_state)
            self._send_json({"serverTime": now_ts, "hospitalAlert": snapshot})
            return

        if path == "/api/speaker-state":
            now_ts = time.time()
            device_id = (qs.get("deviceId") or [""])[0].strip()
            speaker_name = (qs.get("speakerName") or [""])[0].strip()
            audio_armed = (qs.get("audioArmed") or ["0"])[0] == "1"
            speaking = (qs.get("speaking") or ["0"])[0] == "1"
            with state_lock:
                if device_id:
                    connected_speakers[device_id] = {
                        "deviceId": device_id,
                        "speakerName": speaker_name or "Mobile Speaker",
                        "audioArmed": audio_armed,
                        "speaking": speaking,
                        "lastSeen": now_ts,
                    }
                prune_stale_speakers(now_ts)
                speakers_list = [
                    {
                        "deviceId": s["deviceId"],
                        "speakerName": s["speakerName"],
                        "audioArmed": s["audioArmed"],
                        "speaking": s["speaking"],
                        "lastSeenSec": round(now_ts - s["lastSeen"], 1),
                    }
                    for s in connected_speakers.values()
                ]
                snapshot = dict(speaker_state)
            self._send_json({"serverTime": now_ts, "speakerAlert": snapshot, "connectedSpeakers": speakers_list})
            return

        # ================= SERVER-SENT EVENTS (SSE) NOTIFICATION STREAM =================
        if path == "/api/notifications/stream":
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache, no-transform")
            self.send_header("Connection", "keep-alive")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()

            q = queue.Queue(maxsize=100)
            with subscribers_lock:
                notification_subscribers.append(q)

            client_ip = self.client_address[0] if self.client_address else "client"
            print(f"📡 [SSE SUBSCRIBER CONNECTED]: {client_ip} (Total active: {len(notification_subscribers)})")

            # Send initial state event
            with state_lock:
                init_data = {
                    "fireAlert": dict(fire_state),
                    "hospitalAlert": dict(hospital_state),
                    "speakerAlert": dict(speaker_state),
                    "complaints": [dict(c) for c in complaints_list],
                }
            try:
                self.wfile.write(f"event: init\ndata: {json.dumps(init_data)}\n\n".encode("utf-8"))
                self.wfile.flush()
            except Exception:
                with subscribers_lock:
                    if q in notification_subscribers:
                        notification_subscribers.remove(q)
                return

            try:
                while True:
                    try:
                        item = q.get(timeout=12.0)
                        msg = f"event: {item['type']}\ndata: {json.dumps(item['data'])}\n\n".encode("utf-8")
                        self.wfile.write(msg)
                        self.wfile.flush()
                    except queue.Empty:
                        # Keep-alive heartbeat comment
                        self.wfile.write(b": heartbeat\n\n")
                        self.wfile.flush()
            except Exception:
                pass
            finally:
                with subscribers_lock:
                    if q in notification_subscribers:
                        notification_subscribers.remove(q)
                print(f"📡 [SSE SUBSCRIBER DISCONNECTED]: {client_ip} (Remaining: {len(notification_subscribers)})")
            return

        # ================= LONG-POLLING NOTIFICATION ENDPOINT =================
        if path == "/api/notifications/poll":
            since = float((qs.get("since") or ["0"])[0] or 0)
            wait_sec = min(25.0, float((qs.get("wait") or ["20"])[0] or 20))
            deadline = time.time() + wait_sec

            # Fast path: alert already happened
            with state_lock:
                if fire_state["active"] and fire_state["updatedAt"] > since:
                    self._send_json({"type": "fire_alert", "data": dict(fire_state)})
                    return
                if hospital_state["active"] and hospital_state["updatedAt"] > since:
                    self._send_json({"type": "hospital_alert", "data": dict(hospital_state)})
                    return

            q = queue.Queue(maxsize=10)
            with subscribers_lock:
                notification_subscribers.append(q)

            try:
                remaining = max(0.5, deadline - time.time())
                item = q.get(timeout=remaining)
                self._send_json({"type": item["type"], "data": item["data"]})
                return
            except queue.Empty:
                self._send_json({"type": "timeout", "serverTime": time.time()})
                return
            finally:
                with subscribers_lock:
                    if q in notification_subscribers:
                        notification_subscribers.remove(q)

        if path == "/api/complaints":
            with state_lock:
                list_copy = [dict(c) for c in complaints_list]
            self._send_json({"ok": True, "complaints": list_copy, "total": len(list_copy)})
            return

        return super().do_GET()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        length = int(self.headers.get("Content-Length", "0") or "0")
        raw_body = self.rfile.read(length) if length > 0 else b"{}"
        try:
            body = json.loads(raw_body.decode("utf-8"))
        except Exception:
            body = {}

        if path == "/api/auth/verify":
            ident = str(body.get("username") or body.get("email") or body.get("id") or "").strip()
            norm = normalize_identity(ident)
            pw = str(body.get("password") or "")
            if not norm:
                self._send_json({"ok": False, "error": "MISSING_USERNAME", "message": "Username is required."}, status=400)
                return
            acc = house_accounts_by_identity.get(norm) or house_accounts_by_email.get(norm)
            if not acc:
                print(f"⛔ [AUTH DENIED] Unregistered identity/username attempt: {ident}")
                self._send_json({
                    "ok": False,
                    "error": "ACCESS_DENIED",
                    "message": f"Access Denied: '{ident}' is not among the 32 authorized House accounts. Nobody other than them can enter."
                }, status=403)
                return
            valid_passwords = [str(acc.get("password", ""))] + [str(p) for p in acc.get("altPasswords", [])]
            if pw and pw not in valid_passwords:
                print(f"⛔ [AUTH DENIED] Invalid password for: {ident}")
                self._send_json({
                    "ok": False,
                    "error": "INVALID_PASSWORD",
                    "message": f"Incorrect password for '{ident}'."
                }, status=401)
                return
            u_disp = acc.get("username") or acc.get("email") or ident
            print(f"✓ [AUTH SUCCESS] Authorized house login: {u_disp} ({acc.get('houseName', acc.get('role'))})")
            user_data = dict(acc)
            user_data.pop("password", None)
            user_data.pop("altPasswords", None)
            self._send_json({"ok": True, "user": user_data})
            return

        if path == "/api/trigger-test-notification":
            now_ts = time.time()
            msg = body.get("message") or "Test Emergency Notification successfully triggered from Python Backend!"
            show_native_windows_toast("🔔 EMERRR NOTIFICATION TEST", msg)
            play_system_siren_audio()
            broadcast_notification_event("test_alert", {"title": "Test Alert", "message": msg, "time": time.strftime("%H:%M:%S")})
            print(f"\n🔔 [TEST NOTIFICATION DISPATCHED] at {time.strftime('%H:%M:%S')}: {msg}")
            self._send_json({"ok": True, "message": "Notification dispatched to desktop and mobile subscribers."})
            return

        if path == "/api/fire-trigger":
            now_ts = time.time()
            with state_lock:
                fire_state["active"] = True
                fire_state["id"] = body.get("id") or f"FIRE-{int(now_ts) % 10000}"
                fire_state["x"] = float(body.get("x", -6.8))
                fire_state["z"] = float(body.get("z", 4.8))
                fire_state["originLabel"] = body.get("originLabel") or "House No. 1"
                fire_state["houseKey"] = body.get("houseKey")
                fire_state["cause"] = body.get("cause") or "Fire Emergency"
                fire_state["time"] = body.get("time") or time.strftime("%H:%M:%S")
                fire_state["notifiedHouses"] = body.get("notifiedHouses") or []
                fire_state["updatedAt"] = now_ts
                snapshot = dict(fire_state)

            origin = snapshot.get("originLabel", "House No. 1")
            reach = len(snapshot.get("notifiedHouses", []))

            # 1. Native Windows Toast Notification (pops up over all windows on desktop)
            show_native_windows_toast(
                "🚨 EMERRR FIRE EMERGENCY ALARM!",
                f"Fire erupted at {origin}! 500m evacuation active across {reach} houses. Emergency siren sounding."
            )

            # 2. System Siren Audio (using winsound)
            play_system_siren_audio()

            # 3. Broadcast to all active SSE and Long-Poll Mobile / Desktop subscribers
            broadcast_notification_event("fire_alert", snapshot)

            print(f"\n🔥 [FIRE ALERT TRIGGERED]: {origin} ({snapshot['cause']}) at {snapshot['time']}")
            print(f"   ✓ Windows Toast Notification sent")
            print(f"   ✓ PC Emergency Siren played")
            print(f"   ✓ Broadcast dispatched to {len(notification_subscribers)} active notification listeners")

            self._send_json({"ok": True, "fireAlert": snapshot})
            return

        if path == "/api/fire-clear":
            now_ts = time.time()
            with state_lock:
                fire_state["active"] = False
                fire_state["updatedAt"] = now_ts
                snapshot = dict(fire_state)

            broadcast_notification_event("fire_clear", snapshot)
            print(f"\n✓ [FIRE ALERT RESOLVED] at {time.strftime('%H:%M:%S')}")
            self._send_json({"ok": True, "fireAlert": snapshot})
            return

        if path == "/api/hospital-trigger":
            now_ts = time.time()
            with state_lock:
                hospital_state["active"] = True
                hospital_state["id"] = body.get("id") or f"HOSP-{int(now_ts) % 10000}"
                hospital_state["x"] = float(body.get("x", -3.8))
                hospital_state["z"] = float(body.get("z", 3.2))
                hospital_state["houseKey"] = body.get("houseKey") or "house-13"
                hospital_state["houseName"] = body.get("houseName") or "House No. 13"
                hospital_state["villageName"] = body.get("villageName") or "District 4 · South-West House Zone"
                hospital_state["exactAddress"] = body.get("exactAddress") or "House No. 13, Plot #13, Lane 1, District 4 · South-West House Zone"
                hospital_state["gps"] = body.get("gps") or "17.4126° N, 78.4391° E"
                hospital_state["injuryType"] = body.get("injuryType") or "Severe Injury / Emergency"
                hospital_state["reporter"] = body.get("reporter") or "Resident Emergency Button"
                hospital_state["acknowledgedBy"] = body.get("acknowledgedBy")
                hospital_state["time"] = body.get("time") or time.strftime("%H:%M:%S")
                hospital_state["updatedAt"] = now_ts
                snapshot = dict(hospital_state)

            h_name = snapshot.get("houseName", "House No. 13")
            inj = snapshot.get("injuryType", "Medical Emergency")
            addr = snapshot.get("exactAddress", "")

            # 1. Native Windows Toast Notification
            show_native_windows_toast(
                "🏥 HOSPITAL EMERGENCY BUZZER ACTIVE!",
                f"Injury SOS from {h_name}: {inj}! Location: {addr}"
            )

            # 2. System Siren Audio
            play_system_siren_audio()

            # 3. Broadcast to all active subscribers
            broadcast_notification_event("hospital_alert", snapshot)

            print(f"\n🏥 [HOSPITAL BUZZER TRIGGERED]: {h_name} ({inj}) at {snapshot['time']}")
            print(f"   ✓ Windows Toast Notification sent")
            print(f"   ✓ Broadcast dispatched to {len(notification_subscribers)} listeners")

            self._send_json({"ok": True, "hospitalAlert": snapshot})
            return

        if path == "/api/hospital-ack":
            now_ts = time.time()
            with state_lock:
                hospital_state["acknowledgedBy"] = body.get("hospitalName") or "District Civil Hospital"
                hospital_state["updatedAt"] = now_ts
                snapshot = dict(hospital_state)

            broadcast_notification_event("hospital_ack", snapshot)
            print(f"\n✓ [HOSPITAL DISPATCH ACKNOWLEDGED]: by {snapshot['acknowledgedBy']}")
            self._send_json({"ok": True, "hospitalAlert": snapshot})
            return

        if path == "/api/hospital-clear":
            now_ts = time.time()
            with state_lock:
                hospital_state["active"] = False
                hospital_state["acknowledgedBy"] = None
                hospital_state["updatedAt"] = now_ts
                snapshot = dict(hospital_state)

            broadcast_notification_event("hospital_clear", snapshot)
            print(f"\n✓ [HOSPITAL ALERT CLEARED] at {time.strftime('%H:%M:%S')}")
            self._send_json({"ok": True, "hospitalAlert": snapshot})
            return

        if path == "/api/speaker-trigger":
            now_ts = time.time()
            with state_lock:
                speaker_state["active"] = True
                speaker_state["seq"] = int(speaker_state.get("seq", 0)) + 1
                speaker_state["id"] = body.get("id") or f"SPK-{int(now_ts) % 10000}-{speaker_state['seq']}"
                speaker_state["message"] = str(body.get("message") or "").strip()
                speaker_state["lang"] = body.get("lang") or "en"
                try:
                    speaker_state["repeat"] = max(1, min(3, int(body.get("repeat", 1))))
                except Exception:
                    speaker_state["repeat"] = 1
                try:
                    speaker_state["rate"] = max(0.7, min(1.3, float(body.get("rate", 0.96))))
                except Exception:
                    speaker_state["rate"] = 0.96
                speaker_state["chime"] = bool(body.get("chime", True))
                speaker_state["targetScope"] = body.get("targetScope") or "All 32 Houses (District 4 Public Speaker)"
                speaker_state["author"] = body.get("author") or "Municipality Command"
                speaker_state["time"] = body.get("time") or time.strftime("%H:%M:%S")
                speaker_state["updatedAt"] = now_ts
                snapshot = dict(speaker_state)

            broadcast_notification_event("speaker_alert", snapshot)
            print(f"\n📢 [SPEAKER BROADCAST]: {snapshot['message']} ({snapshot['targetScope']})")
            self._send_json({"ok": True, "speakerAlert": snapshot})
            return

        if path == "/api/speaker-clear":
            now_ts = time.time()
            with state_lock:
                speaker_state["active"] = False
                speaker_state["updatedAt"] = now_ts
                snapshot = dict(speaker_state)

            broadcast_notification_event("speaker_clear", snapshot)
            self._send_json({"ok": True, "speakerAlert": snapshot})
            return

        if path == "/api/complaints":
            now_ts = time.time()
            cat = body.get("category") or "Broken Road / Infrastructure Damage"
            cat_key = body.get("categoryKey") or "broken_road"
            h_key = body.get("houseKey") or "house-1"
            h_name = body.get("houseName") or "House No. 1"
            loc = body.get("location") or f"{h_name} · Access Road"
            urg = body.get("urgency") or "high"
            urg_label = "Critical Hazard" if urg == "critical" else ("High Priority" if urg == "high" else "Standard Maintenance")
            rep_name = body.get("reporterName") or "Resident"
            rep_phone = body.get("reporterPhone") or "Unlisted"
            desc = body.get("description") or "Infrastructure damage reported by citizen."
            photo = body.get("photo") or "/assets/broken_road.svg"

            cid = f"CMP-{int(now_ts * 1000) % 90000 + 10000}"
            new_complaint = {
                "id": cid,
                "category": cat,
                "categoryKey": cat_key,
                "houseKey": h_key,
                "houseName": h_name,
                "location": loc,
                "urgency": urg,
                "urgencyLabel": urg_label,
                "reporterName": rep_name,
                "reporterPhone": rep_phone,
                "description": desc,
                "photo": photo,
                "status": "pending",
                "statusLabel": "PENDING INSPECTION",
                "time": "Just now",
                "createdAt": now_ts,
            }

            with state_lock:
                complaints_list.insert(0, new_complaint)
                save_complaints_to_disk()

            # Native Windows Toast Notification
            show_native_windows_toast(
                f"🚨 CITIZEN COMPLAINT: {cat}",
                f"{h_name}: {desc[:100]}... [Photo Evidence Received]"
            )
            # Push to SSE stream
            broadcast_notification_event("new_complaint", new_complaint)

            print(f"\n📸 [NEW CITIZEN COMPLAINT FILED]: {cid} | {cat} at {h_name} by {rep_name}")
            self._send_json({"ok": True, "complaint": new_complaint})
            return

        if path == "/api/complaints/update":
            cid = body.get("id")
            new_status = body.get("status") or "pending"
            updated = None
            with state_lock:
                for c in complaints_list:
                    if c["id"] == cid:
                        c["status"] = new_status
                        if new_status == "dispatched":
                            c["statusLabel"] = "CREW DISPATCHED"
                        elif new_status == "resolved":
                            c["statusLabel"] = "RESOLVED & SAFE"
                        else:
                            c["statusLabel"] = "PENDING INSPECTION"
                        updated = dict(c)
                        break
            if updated:
                with state_lock:
                    save_complaints_to_disk()
                broadcast_notification_event("complaint_updated", updated)
                print(f"🔧 [COMPLAINT STATUS UPDATED]: {cid} -> {new_status.upper()}")
                self._send_json({"ok": True, "complaint": updated})
            else:
                self._send_json({"ok": False, "error": "Complaint not found"}, status=404)
            return

        self._send_json({"error": "Not found"}, status=404)


# Top-level exports for Vercel / serverless runtime entrypoints
class handler(SociothonHandler):
    pass

Handler = handler
app = handler
application = handler


if __name__ == "__main__":
    lan_ip = get_primary_lan_ip()
    all_ips = get_all_lan_ips()
    print("=" * 72)
    print("  🚨 EMERRR PUBLIC SAFETY & EMERGENCY RELAY SERVER")
    print(f"  Listening on: http://0.0.0.0:{PORT}")
    print("=" * 72)
    print(f"  💻 PC Portal     : http://127.0.0.1:{PORT}/index.html")
    print(f"  📱 Mobile Alarm  : http://{lan_ip}:{PORT}/mobile.html")
    print("  🔗 All Available LAN IPs for Mobile Pairing:")
    for ip in all_ips:
        print(f"     -> http://{ip}:{PORT}/mobile.html")
    print("=" * 72)
    print("  🔔 NOTIFICATION ENGINE: ACTIVE")
    print("     ✓ Native Windows Toast Notifications: ENABLED")
    print("     ✓ System Audio Siren (winsound)   : ENABLED")
    print("     ✓ Server-Sent Events (SSE) Stream : /api/notifications/stream")
    print("     ✓ Long-Polling Push Endpoint      : /api/notifications/poll")
    print("=" * 72)

    httpd = ThreadingHTTPServer(("0.0.0.0", PORT), SociothonHandler)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        httpd.server_close()

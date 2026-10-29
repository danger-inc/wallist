# Bildquellen und Stil-Bewertung für wallist.
# Alles hier läuft in Hintergrund-Threads und fasst keine GTK-Widgets an.
import http.cookiejar, io, json, math, re, urllib.parse, urllib.request

from PIL import Image, ImageFilter, ImageStat

UA = "Mozilla/5.0 (X11; Linux x86_64; rv:140.0) Gecko/20100101 Firefox/140.0"


def http_get(url, headers=None, opener=None, timeout=25):
    req = urllib.request.Request(url, headers={"User-Agent": UA, **(headers or {})})
    with (opener.open(req, timeout=timeout) if opener else urllib.request.urlopen(req, timeout=timeout)) as r:
        return r.read()


def is_landscape(w, h):
    return w >= h * 1.2  # Hochformat-Bilder taugen nicht als Desktop-Hintergrund


# ---------------- Wallhaven (offizielle API, beste Qualität) ----------------
def search_wallhaven(query, min_w, min_h, page):
    params = {"q": query, "categories": "110", "purity": "100", "atleast": f"{min_w}x{min_h}",
              "ratios": "landscape", "sorting": "relevance", "page": page}
    d = json.loads(http_get("https://wallhaven.cc/api/v1/search?" + urllib.parse.urlencode(params)))
    out = []
    for x in d.get("data", []):
        out.append({"source": "Wallhaven", "id": "wh-" + x["id"], "thumb": x["thumbs"]["large"],
                    "full": x["path"], "width": x["dimension_x"], "height": x["dimension_y"], "page": x["url"]})
    meta = d.get("meta", {})
    return out, meta.get("current_page", 1) < meta.get("last_page", 1)


# ---------------- Pinterest (inoffiziell, viele Bilder sind klein) ----------------
class Pinterest:
    def __init__(self):
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))
        self.csrf = None
        self.bookmarks = {}

    def _session(self):
        if self.csrf:
            return
        http_get("https://www.pinterest.com/", opener=self.opener)
        self.csrf = next((c.value for c in self.jar if c.name == "csrftoken"), "")

    def search(self, query, min_w, min_h, page):
        self._session()
        options = {"query": query, "scope": "pins", "page_size": 50}
        if page > 1:
            bm = self.bookmarks.get(query)
            if not bm:
                return [], False
            options["bookmarks"] = [bm]
        params = {"source_url": "/search/pins/?q=" + urllib.parse.quote(query),
                  "data": json.dumps({"options": options, "context": {}})}
        raw = http_get("https://www.pinterest.com/resource/BaseSearchResource/get/?" + urllib.parse.urlencode(params),
                       headers={"Accept": "application/json, text/javascript, */*; q=0.01",
                                "X-Requested-With": "XMLHttpRequest", "X-Pinterest-AppState": "active",
                                "X-Pinterest-PWS-Handler": "www/search/[scope].js", "X-CSRFToken": self.csrf,
                                "Referer": "https://www.pinterest.com/"}, opener=self.opener)
        resp = json.loads(raw)["resource_response"]
        self.bookmarks[query] = resp.get("bookmark")
        out = []
        for x in (resp.get("data") or {}).get("results", []):
            imgs = x.get("images") or {}
            o = imgs.get("orig")
            if not o or x.get("is_video") or o["width"] < min_w or o["height"] < min_h or not is_landscape(o["width"], o["height"]):
                continue
            thumb = (imgs.get("474x") or imgs.get("736x") or o)["url"]
            out.append({"source": "Pinterest", "id": "pin-" + str(x["id"]), "thumb": thumb, "full": o["url"],
                        "width": o["width"], "height": o["height"], "page": f"https://www.pinterest.com/pin/{x['id']}/"})
        return out, bool(self.bookmarks[query]) and self.bookmarks[query] != "-end-"


# ---------------- Cosmos (Seite auslesen, nur jugendfreie Bilder) ----------------
COSMOS_RE = re.compile(r'"url":"(https://cdn\.cosmos\.so/([0-9a-f-]{36}))","width":(\d+),"height":(\d+),'
                       r'"notSafeForWorkStatus":"(\w+)"')


def search_cosmos(query, min_w, min_h, page):
    if page > 1:
        return [], False  # Cosmos liefert ohne Login nur eine Seite
    html = http_get("https://www.cosmos.so/search/elements/" + urllib.parse.quote(query)).decode("utf-8", "ignore")
    html = html.replace('\\"', '"')
    out, seen = [], set()
    for url, mid, w, h, nsfw in COSMOS_RE.findall(html):
        w, h = int(w), int(h)
        if mid in seen or nsfw != "SAFE" or w < min_w or h < min_h or not is_landscape(w, h):
            continue
        seen.add(mid)
        out.append({"source": "Cosmos", "id": "cos-" + mid, "thumb": url + "?format=jpeg&w=480", "full": url,
                    "width": w, "height": h, "page": url})
    return out, False


# ---------------- Stil-Bewertung ----------------
# Mit Stil-KI (CLIP, lokal): vergleicht Inhalt und Malstil wie ein Mensch.
# Ohne (setup-ki.sh nicht gelaufen): grober Vergleich über Farben und Kanten.
import os
import numpy as np

MODEL = os.path.expanduser("~/.local/share/wallist/models/clip-vit-b32-vision-q.onnx")
MEAN = np.array([0.48145466, 0.4578275, 0.40821073], np.float32)
STD = np.array([0.26862954, 0.26130258, 0.27577711], np.float32)
_session = None
import threading, time
_lock = threading.Lock()
_last = [0.0]
_unload = None
IDLE_UNLOAD = 60            # Sekunden ohne Bewertung, dann gibt der Daemon die KI (~300 MB) wieder frei


def clip_installed():
    """Modell und onnxruntime sind da – ohne die Sitzung zu laden (für Statuszeilen)."""
    import importlib.util
    return os.path.exists(MODEL) and importlib.util.find_spec("onnxruntime") is not None


def clip_available():
    """Lädt die Stil-KI bei Bedarf; nach IDLE_UNLOAD Sekunden ohne Nutzung wird sie wieder entladen."""
    global _session, _unload
    with _lock:
        if _session is None:
            try:
                import onnxruntime as ort
                opts = ort.SessionOptions()
                opts.log_severity_level = 3
                opts.enable_cpu_mem_arena = False
                opts.enable_mem_pattern = False
                opts.intra_op_num_threads = 2
                _session = ort.InferenceSession(MODEL, opts, providers=["CPUExecutionProvider"])
            except Exception:
                _session = False
        _last[0] = time.monotonic()
        if _session and _unload is None:
            _arm()
        return bool(_session)


def _arm():
    global _unload
    _unload = threading.Timer(IDLE_UNLOAD, _free)
    _unload.daemon = True
    _unload.start()


def _free():
    global _session, _unload
    with _lock:
        _unload = None
        if time.monotonic() - _last[0] < IDLE_UNLOAD - 1:       # zwischendurch benutzt: weiter warten
            _arm()
            return
        _session = None
    import gc
    gc.collect()
    try:
        import ctypes
        ctypes.CDLL("libc.so.6").malloc_trim(0)
    except Exception:
        pass


def _crops(img):
    """Breitbilder: links, Mitte, rechts als Quadrate, damit nichts Wichtiges wegfällt."""
    im = img.convert("RGB")
    w, h = im.size
    side = min(w, h)
    xs = [0, (w - side) // 2, w - side] if w > h * 1.2 else [(w - side) // 2]
    out = []
    for x in xs:
        c = im.crop((x, (h - side) // 2, x + side, (h - side) // 2 + side)).resize((224, 224), Image.BICUBIC)
        out.append(((np.asarray(c, np.float32) / 255 - MEAN) / STD).transpose(2, 0, 1))
    return np.stack(out)


def features(img):
    if clip_available():
        sess = _session
        if not sess:
            return ("color", color_features(img))
        emb = sess.run(["image_embeds"], {"pixel_values": _crops(img)})[0].mean(0)
        return ("clip", (emb / np.linalg.norm(emb)).tolist())
    return ("color", color_features(img))


HUE_BINS = 12


def color_features(img):
    im = img.convert("RGB")
    im.thumbnail((96, 96))
    hsv = im.convert("HSV")
    hist = [0.0] * HUE_BINS
    for h, s, v in hsv.getdata():
        hist[h * HUE_BINS // 256] += (s / 255) * (v / 255)
    total = sum(hist) or 1
    hist = [x / total for x in hist]
    st = ImageStat.Stat(hsv)
    edges = ImageStat.Stat(im.convert("L").filter(ImageFilter.FIND_EDGES)).mean[0] / 255
    return hist + [st.mean[1] / 255, st.mean[2] / 255, st.stddev[2] / 128, min(1, edges * 4)]


def _color_distance(a, b):
    hist = sum(abs(x - y) for x, y in zip(a[:HUE_BINS], b[:HUE_BINS])) / 2
    sat, val, con, edge = (abs(x - y) for x, y in zip(a[HUE_BINS:], b[HUE_BINS:]))
    return 0.45 * hist + 0.2 * sat + 0.12 * val + 0.08 * con + 0.15 * edge


# Kalibriert an deinen Wallpapern: eigene ~0.75, gemalte Landschaften ~0.75, Fotos ~0.56-0.63
CLIP_LOW, CLIP_HIGH = 0.60, 0.86


def style_score(f, profile):
    """0..100: wie nah das Bild an deinen Wallpapern liegt (Mittel der zwei ähnlichsten)."""
    same = [p[1] for p in profile if p[0] == f[0]]
    if not same:
        return 50
    if f[0] == "clip":
        v = np.array(f[1])
        sims = sorted((float(np.dot(v, np.array(p))) for p in same), reverse=True)[:2]
        sim = sum(sims) / len(sims)
        return max(0, min(100, round(100 * (sim - CLIP_LOW) / (CLIP_HIGH - CLIP_LOW))))
    d = min(_color_distance(f[1], p) for p in same)
    return max(0, min(100, round(100 * (1 - d / 0.45))))


def image_from_bytes(data):
    im = Image.open(io.BytesIO(data))
    im.load()
    return im

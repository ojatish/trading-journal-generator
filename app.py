import streamlit as st
import zipfile, json, base64, io, re, csv
from pathlib import Path
from datetime import datetime

try:
    from PIL import Image as PILImage
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

TEMPLATE_PATH = Path(__file__).parent / "journal_template.html"
try:
    TEMPLATE_HTML = TEMPLATE_PATH.read_text(encoding="utf-8")
    assert "/*__TRADES_START__*/" in TEMPLATE_HTML, "Marker missing"
    TEMPLATE_ERROR = None
except Exception as e:
    TEMPLATE_HTML = None
    TEMPLATE_ERROR = str(e)

st.set_page_config(page_title="Trading Journal Generator", page_icon="⬡", layout="centered")
st.markdown("""
<style>
body,.stApp{background:#000!important}
.block-container{max-width:700px;padding-top:2rem}
h1{color:#c8a84b!important;font-size:1.9rem!important;font-weight:800!important}
h3{color:#888!important;font-weight:400!important;font-size:1rem!important}
.step{background:#0c0c0c;border:1px solid #222;border-radius:10px;padding:1.1rem 1.4rem;margin-bottom:.8rem}
.step-num{color:#c8a84b;font-weight:800;margin-right:6px}
.step p{color:#666;font-size:.88rem;margin:4px 0 0;line-height:1.55}
.stButton>button{background:#c8a84b!important;color:#000!important;font-weight:700!important;
  border:none!important;border-radius:7px!important;width:100%;font-size:1rem!important;
  padding:.6rem 2rem!important;margin-top:.8rem}
.stDownloadButton>button{background:#22c55e!important;color:#000!important;font-weight:700!important;
  border:none!important;border-radius:7px!important;width:100%;font-size:1rem!important;
  padding:.6rem 2rem!important}
hr{border-color:#1e1e1e!important}
</style>
""", unsafe_allow_html=True)

if TEMPLATE_ERROR:
    st.error(f"Template load failed: {TEMPLATE_ERROR}")
    st.stop()

st.markdown("## ⬡ Trading Journal Generator")
st.markdown("### Upload your Notion export → get your personal HTML journal")
st.markdown("---")

with st.expander("📋 How to export from Notion", expanded=False):
    st.markdown("""
1. Open your **Trading Dashboard** page in Notion
2. Click `···` top-right → **Export**
3. Choose **Markdown & CSV** and tick **Include subpages**
4. Download the zip — Notion may send multiple parts, upload all of them
""")
st.markdown("---")

# ── helpers ──────────────────────────────────────────────────────────

def compress_image(data: bytes) -> str:
    if HAS_PIL:
        try:
            img = PILImage.open(io.BytesIO(data)).convert("RGB")
            w, h = img.size
            if w > 1300 or h > 1000:
                r = min(1300/w, 1000/h)
                img = img.resize((int(w*r), int(h*r)), PILImage.LANCZOS)
            buf = io.BytesIO()
            img.save(buf, "JPEG", quality=80, optimize=True)
            return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()
        except Exception:
            pass
    return "data:image/png;base64," + base64.b64encode(data).decode()

def img_sort_key(fname: str) -> int:
    n = Path(fname).name
    if re.match(r"^image\.(png|jpe?g|webp)$", n, re.I): return 0
    m = re.search(r"image\s*(\d+)", n, re.I)
    return int(m.group(1)) if m else 99

def is_trade_id(s: str) -> bool:
    return bool(re.match(r"^[A-Z]{2,4}-[A-Z0-9]+$", s))

def extract_zip(raw: bytes):
    csv_rows = []
    images = {}

    def walk(zf: zipfile.ZipFile):
        for name in zf.namelist():
            if name.endswith(".csv"):
                try:
                    text = zf.read(name).decode("utf-8-sig")
                    rows = list(csv.DictReader(io.StringIO(text)))
                    if rows and "Name" in rows[0] and "Date" in rows[0]:
                        if "_all.csv" in name or not csv_rows:
                            csv_rows.clear()
                            csv_rows.extend(rows)
                except Exception:
                    pass

            parts = Path(name).parts
            for i, part in enumerate(parts):
                if is_trade_id(part):
                    fname = parts[-1] if len(parts) > i+1 else ""
                    if fname.lower().endswith((".png",".jpg",".jpeg",".webp")):
                        try:
                            data = zf.read(name)
                            images.setdefault(part, []).append((img_sort_key(fname), data))
                        except Exception:
                            pass
                    break

            if name.lower().endswith(".zip"):
                try:
                    with zipfile.ZipFile(io.BytesIO(zf.read(name))) as inner:
                        walk(inner)
                except Exception:
                    pass

    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        walk(zf)

    for tid in images:
        images[tid] = [b for _, b in sorted(images[tid], key=lambda x: x[0])]

    return csv_rows, images

def parse_float(v) -> float:
    try: return float(str(v).replace("%","").replace("+","").strip())
    except: return 0.0

def parse_int(v) -> int:
    try: return int(float(str(v).strip()))
    except: return 0

def parse_bool(v) -> bool:
    return str(v).strip().lower() in ("yes","true","1")

def parse_list(v) -> list:
    if not v or str(v).strip() in ("","N/A","nan"): return []
    return [x.strip() for x in str(v).split(",") if x.strip() and x.strip() != "N/A"]

def parse_date(raw: str):
    raw = raw.strip()
    part = re.sub(r"\s*\([^)]+\)", "", raw.split("→")[0]).strip()
    for fmt in ("%b %d %H:%M", "%B %d %H:%M", "%b %d", "%B %d"):
        try:
            dt = datetime.strptime(part, fmt).replace(year=datetime.now().year)
            return dt.strftime("%Y-%m-%d"), (dt.strftime("%H:%M") if "%H" in fmt else "")
        except ValueError:
            continue
    m = re.search(r"(\d{4}-\d{2}-\d{2})", raw)
    return (m.group(1) if m else raw[:10]), ""

def row_to_trade(row: dict, idx: int) -> dict:
    tid = row.get("Name","").strip() or f"TRADE-{idx+1}"
    raw_date = row.get("Date","")
    date_str, entry_time = parse_date(raw_date)
    exit_time = ""
    if "→" in raw_date:
        ep = re.sub(r"\s*\([^)]+\)", "", raw_date.split("→")[1]).strip()
        m = re.search(r"(\d{2}:\d{2})", ep)
        if m: exit_time = m.group(1)
    return {
        "id": tid, "date": date_str, "entry": entry_time, "exit": exit_time,
        "dow": row.get("Day of the Week","").strip(),
        "pair": row.get("Pair","").strip(),
        "direction": row.get("Direction","").strip(),
        "status": row.get("Status","").strip(),
        "result": row.get("Result","").strip(),
        "session": row.get("Session","").strip(),
        "hour": row.get("Hour","").strip(),
        "htfBias": row.get("HTF Bias","").strip(),
        "htfInducement": parse_bool(row.get("HTF Inducement Nearby","No")),
        "htfInducementType": row.get("HTF Inducement Type","N/A").strip(),
        "mtfConfluences": parse_list(row.get("MTF Confluences","")),
        "ltfConfirmation": parse_list(row.get("LTF Confirmation Type","")),
        "trend": row.get("Trend","").strip(),
        "slSize": parse_float(row.get("SL Size",0)),
        "percentRisked": parse_float(row.get("Percent Risked",0)),
        "conviction": parse_int(row.get("Conviction",0)),
        "entryType": row.get("Entry Type","").strip(),
        "exitType": row.get("Exit Type","").strip(),
        "rrDone": parse_float(row.get("RR Done",0)),
        "maxRR": parse_float(row.get("Max RR",0)),
        "idealRR": parse_float(row.get("Ideal RR",0)),
        "pnl": parse_float(row.get("PnL",0)),
        "executionQuality": row.get("Execution Quality","").strip(),
        "goodPoint": row.get("Good Point","").strip(),
        "badPoint": row.get("Bad Point","").strip(),
        "thoughtsDuring": row.get("Thoughts During","").strip(),
        "thoughtsAfter": row.get("Thoughts After","").strip(),
        "images": [], "createdAt": datetime.now().isoformat(),
    }

def inject_trades(html: str, trades: list) -> str:
    payload = json.dumps(trades, ensure_ascii=True)
    payload = payload.replace("</script>", "<\\/script>")
    return html.replace(
        "const SEED_TRADES = [/*__TRADES_START__*//*__TRADES_END__*/]",
        f"const SEED_TRADES = {payload}",
        1,
    )

# ── upload UI ────────────────────────────────────────────────────────
uploaded = st.file_uploader(
    "Drop your Notion export zip(s) here",
    type=["zip"], accept_multiple_files=True,
)

if not uploaded:
    st.markdown("""
<div class="step"><span class="step-num">1</span>Export from Notion
<p>Open your journal → ··· → Export → <strong>Markdown & CSV</strong> → include subpages → download zip</p></div>
<div class="step"><span class="step-num">2</span>Upload the zip(s) above
<p>Notion sometimes splits large exports — upload all parts at once</p></div>
<div class="step"><span class="step-num">3</span>Click Generate → Download HTML
<p>Open in any browser. Works fully offline. Saves everything locally on your device.</p></div>
""", unsafe_allow_html=True)

if uploaded and st.button("⚡ Generate My Journal"):
    prog = st.progress(0, text="Reading zips…")

    all_rows, all_images, seen = [], {}, set()

    for i, uf in enumerate(uploaded):
        prog.progress(int(i/len(uploaded)*30), text=f"Parsing {uf.name}…")
        try:
            rows, imgs = extract_zip(uf.read())
            for r in rows:
                rid = r.get("Name","").strip()
                if rid and rid not in seen:
                    all_rows.append(r); seen.add(rid)
            for tid, lst in imgs.items():
                all_images.setdefault(tid, lst)
        except Exception as e:
            st.warning(f"Problem with {uf.name}: {e}")

    if not all_rows:
        st.error(
            "No trade data found. Make sure you exported with "
            "**Markdown & CSV** selected and **Include subpages** ticked."
        )
        st.stop()

    prog.progress(35, text=f"Found {len(all_rows)} trades — embedding screenshots…")

    trades = []
    for i, row in enumerate(all_rows):
        trade = row_to_trade(row, i)
        tid = trade["id"]
        if tid in all_images:
            trade["images"] = []
            for img_bytes in all_images[tid]:
                try: trade["images"].append(compress_image(img_bytes))
                except: pass
        trades.append(trade)
        prog.progress(35 + int(i/len(all_rows)*55), text=f"Processed {tid}…")

    trades.sort(key=lambda t: t.get("date",""))

    prog.progress(93, text="Building HTML…")
    try:
        html_out = inject_trades(TEMPLATE_HTML, trades)
    except Exception as e:
        st.error(f"Injection failed: {e}")
        st.stop()

    prog.progress(100, text="Done!")
    total_imgs = sum(len(t["images"]) for t in trades)
    st.success(f"✅  {len(trades)} trades · {total_imgs} screenshots embedded")

    st.download_button(
        label="⬇ Download trading-journal.html",
        data=html_out.encode("utf-8"),
        file_name="trading-journal.html",
        mime="text/html",
    )
    st.caption("Open in Chrome / Firefox / Edge. Works offline. Everything saves locally.")

st.markdown("---")
st.markdown(
    '<p style="color:#2a2a2a;font-size:.75rem;text-align:center">'
    'Files processed in memory · nothing stored on server · free forever</p>',
    unsafe_allow_html=True,
)

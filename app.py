import streamlit as st
import zipfile, json, base64, io, re, csv, os
from pathlib import Path
from datetime import datetime

# ── Optional Pillow for compression ──────────────────────────────────
try:
    from PIL import Image as PILImage
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

# ── Page config ───────────────────────────────────────────────────────
st.set_page_config(
    page_title="Trading Journal Generator",
    page_icon="⬡",
    layout="centered",
)

# ── Custom CSS ────────────────────────────────────────────────────────
st.markdown("""
<style>
body, .stApp { background: #000 !important; color: #e4e4e4; }
.block-container { max-width: 720px; padding-top: 2rem; }
h1 { font-size: 2rem !important; font-weight: 800 !important; color: #c8a84b !important; letter-spacing: 0.03em; }
h3 { color: #a0a0a0 !important; font-weight: 400 !important; font-size: 1rem !important; margin-top: 0 !important; }
.stFileUploader { border: 1px solid #222 !important; border-radius: 10px !important; background: #0c0c0c !important; }
.stButton > button {
  background: #c8a84b !important; color: #000 !important; font-weight: 700 !important;
  border: none !important; border-radius: 7px !important; padding: 0.6rem 2rem !important;
  font-size: 1rem !important; width: 100%; margin-top: 1rem;
  transition: filter .15s; cursor: pointer;
}
.stButton > button:hover { filter: brightness(1.12) !important; }
.stDownloadButton > button {
  background: #22c55e !important; color: #000 !important; font-weight: 700 !important;
  border: none !important; border-radius: 7px !important; padding: 0.6rem 2rem !important;
  font-size: 1rem !important; width: 100%; margin-top: 0.5rem;
}
.stAlert { border-radius: 8px !important; }
hr { border-color: #1e1e1e !important; }
.step { background: #0c0c0c; border: 1px solid #222; border-radius: 10px; padding: 1.2rem 1.5rem; margin-bottom: 1rem; }
.step-num { color: #c8a84b; font-weight: 800; font-size: 1.1rem; margin-right: 8px; }
.step p { color: #787878; font-size: 0.9rem; margin-top: 4px; margin-bottom: 0; line-height: 1.6; }
</style>
""", unsafe_allow_html=True)

# ── Header ────────────────────────────────────────────────────────────
st.markdown("## ⬡ Trading Journal Generator")
st.markdown("### Upload your Notion export and get a ready-to-use HTML journal")
st.markdown("---")

# ── How it works ──────────────────────────────────────────────────────
with st.expander("How to export from Notion", expanded=False):
    st.markdown("""
**Step 1 — Export your Notion trading database:**
1. Open your Trading Dashboard page in Notion
2. Click `···` (three dots) in the top right
3. Click **Export**
4. Select **Markdown & CSV** — include subpages ✓
5. Click Export. Notion will email you a `.zip` file (or download directly)

**Step 2 — Upload here:**
You can upload 1, 2, or 3 zip files (Notion sometimes splits large exports).

**Step 3 — Download:**
Click Generate and download your personal `trading-journal.html`.
Open it in any browser — everything is saved locally on your device.
""")

st.markdown("---")

# ── Upload ────────────────────────────────────────────────────────────
uploaded = st.file_uploader(
    "Drop your Notion export zip(s) here",
    type=["zip"],
    accept_multiple_files=True,
    help="Notion sometimes splits exports into multiple zips — upload all of them"
)

# ── Core parsing ──────────────────────────────────────────────────────
def compress_image(img_bytes: bytes) -> str:
    if HAS_PIL:
        try:
            img = PILImage.open(io.BytesIO(img_bytes)).convert("RGB")
            w, h = img.size
            max_w, max_h = 1300, 1000
            if w > max_w or h > max_h:
                ratio = min(max_w / w, max_h / h)
                img = img.resize((int(w * ratio), int(h * ratio)), PILImage.LANCZOS)
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=80, optimize=True)
            b64 = base64.b64encode(buf.getvalue()).decode()
            return f"data:image/jpeg;base64,{b64}"
        except Exception:
            pass
    b64 = base64.b64encode(img_bytes).decode()
    return f"data:image/png;base64,{b64}"


def parse_date(raw: str):
    """Parse Notion date like 'Apr 30 13:14 (GMT+5:30) → 13:27' """
    raw = raw.strip()
    # Extract date part before the arrow
    part = raw.split("→")[0].strip()
    # Remove timezone
    part = re.sub(r'\s*\([^)]+\)', '', part).strip()
    # Try parsing 'Apr 30 13:14'
    for fmt in ('%b %d %H:%M', '%B %d %H:%M', '%b %d, %Y %H:%M', '%b %d'):
        try:
            dt = datetime.strptime(part, fmt)
            year = datetime.now().year
            return dt.replace(year=year).strftime('%Y-%m-%d'), dt.strftime('%H:%M') if '%H' in fmt else ''
        except ValueError:
            continue
    # Fallback: extract time with regex
    m = re.search(r'(\d{4}-\d{2}-\d{2})', raw)
    if m:
        return m.group(1), ''
    return raw[:10] if len(raw) >= 10 else raw, ''


def parse_pnl(raw: str) -> float:
    try:
        return float(raw.replace('%','').replace('+','').strip())
    except Exception:
        return 0.0


def parse_float(raw: str) -> float:
    try:
        return float(raw.replace('%','').replace('+','').strip())
    except Exception:
        return 0.0


def parse_int(raw: str) -> int:
    try:
        return int(float(raw.strip()))
    except Exception:
        return 0


def parse_bool(raw: str) -> bool:
    return raw.strip().lower() in ('yes', 'true', '1')


def parse_list(raw: str) -> list:
    if not raw or raw.strip() in ('N/A', '', 'nan'):
        return []
    return [x.strip() for x in raw.split(',') if x.strip() and x.strip() != 'N/A']


def parse_csv_row(row: dict, idx: int) -> dict:
    trade_id = row.get('Name', '').strip() or f"TRADE-{idx+1}"
    raw_date = row.get('Date', '')
    date_str, entry_time = parse_date(raw_date)

    # Extract exit time from date field (after →)
    exit_time = ''
    if '→' in raw_date:
        exit_part = raw_date.split('→')[1]
        exit_part = re.sub(r'\s*\([^)]+\)', '', exit_part).strip()
        m = re.search(r'(\d{2}:\d{2})', exit_part)
        if m:
            exit_time = m.group(1)

    # Determine result — Notion stores Win/Loss/Partial/Breakeven/Missed as text in Result col
    result = row.get('Result', '').strip()

    return {
        "id": trade_id,
        "date": date_str,
        "entry": entry_time,
        "exit": exit_time,
        "dow": row.get('Day of the Week', '').strip(),
        "pair": row.get('Pair', '').strip(),
        "direction": row.get('Direction', '').strip(),
        "status": row.get('Status', '').strip(),
        "result": result,
        "session": row.get('Session', '').strip(),
        "hour": row.get('Hour', '').strip(),
        "htfBias": row.get('HTF Bias', '').strip(),
        "htfInducement": parse_bool(row.get('HTF Inducement Nearby', 'No')),
        "htfInducementType": row.get('HTF Inducement Type', 'N/A').strip(),
        "mtfConfluences": parse_list(row.get('MTF Confluences', '')),
        "ltfConfirmation": parse_list(row.get('LTF Confirmation Type', '')),
        "trend": row.get('Trend', '').strip(),
        "slSize": parse_float(row.get('SL Size', '0')),
        "percentRisked": parse_float(row.get('Percent Risked', '0')),
        "conviction": parse_int(row.get('Conviction', '0')),
        "entryType": row.get('Entry Type', '').strip(),
        "exitType": row.get('Exit Type', '').strip(),
        "rrDone": parse_float(row.get('RR Done', '0')),
        "maxRR": parse_float(row.get('Max RR', '0')),
        "idealRR": parse_float(row.get('Ideal RR', '0')),
        "pnl": parse_pnl(row.get('PnL', '0')),
        "executionQuality": row.get('Execution Quality', '').strip(),
        "goodPoint": row.get('Good Point', '').strip(),
        "badPoint": row.get('Bad Point', '').strip(),
        "thoughtsDuring": row.get('Thoughts During', '').strip(),
        "thoughtsAfter": row.get('Thoughts After', '').strip(),
        "images": [],
        "createdAt": datetime.now().isoformat(),
    }


def img_sort_key(name: str) -> int:
    basename = Path(name).name
    if re.match(r'^image\.(png|jpg|jpeg|webp)$', basename, re.I):
        return 0
    m = re.search(r'image\s*(\d+)', basename, re.I)
    return int(m.group(1)) if m else 99


def extract_from_zip(zip_bytes: bytes):
    """Returns (trades_csv_rows, trade_images_dict)"""
    csv_rows = []
    trade_images = {}  # trade_id -> [(sort_key, bytes)]

    def walk_zip(zf: zipfile.ZipFile, prefix=''):
        nonlocal csv_rows
        for name in zf.namelist():
            # Find _all.csv (contains all records)
            if name.endswith('_all.csv') or (name.endswith('.csv') and 'Trading' in name and '_all' in name):
                try:
                    raw = zf.read(name).decode('utf-8-sig')
                    reader = csv.DictReader(io.StringIO(raw))
                    csv_rows = list(reader)
                except Exception:
                    pass
            # Fallback: any csv with trade data
            elif name.endswith('.csv') and 'Trading' in name and not csv_rows:
                try:
                    raw = zf.read(name).decode('utf-8-sig')
                    reader = csv.DictReader(io.StringIO(raw))
                    rows = list(reader)
                    if rows and 'Name' in rows[0]:
                        csv_rows = rows
                except Exception:
                    pass
            # Images inside trade folders
            parts = Path(name).parts
            for i, part in enumerate(parts):
                if re.match(r'^[A-Z]{2,4}-[A-Z0-9M]+$', part):
                    fname = parts[-1] if len(parts) > i + 1 else ''
                    if fname.lower().endswith(('.png','.jpg','.jpeg','.webp','.gif')):
                        try:
                            img_data = zf.read(name)
                            if part not in trade_images:
                                trade_images[part] = []
                            trade_images[part].append((img_sort_key(fname), img_data))
                        except Exception:
                            pass
                    break
            # Nested zips
            if name.endswith('.zip'):
                try:
                    inner_bytes = zf.read(name)
                    with zipfile.ZipFile(io.BytesIO(inner_bytes)) as inner_zf:
                        walk_zip(inner_zf, prefix=name)
                except Exception:
                    pass

    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        walk_zip(zf)

    # Sort images within each trade
    for tid in trade_images:
        trade_images[tid].sort(key=lambda x: x[0])
        trade_images[tid] = [b for _, b in trade_images[tid]]

    return csv_rows, trade_images


def build_journal_html(trades: list) -> str:
    """Load the HTML template and inject user's trades."""
    template_path = Path(__file__).parent / "journal_template.html"
    with open(template_path, 'r', encoding='utf-8') as f:
        html = f.read()

    trades_json = json.dumps(trades, ensure_ascii=False)
    # Replace the SEED_TRADES constant
    html = re.sub(
        r'const SEED_TRADES = \[[\s\S]*?\];',
        f'const SEED_TRADES = {trades_json};',
        html,
        count=1
    )
    return html


# ── Generate button ───────────────────────────────────────────────────
if uploaded:
    st.success(f"✓ {len(uploaded)} file(s) uploaded")

    if st.button("⚡ Generate My Journal"):
        with st.spinner("Parsing your trades and embedding screenshots..."):
            all_csv_rows = []
            all_images = {}

            for uf in uploaded:
                zip_bytes = uf.read()
                rows, imgs = extract_from_zip(zip_bytes)
                # Merge CSV rows (avoid duplicates by Name)
                existing_ids = {r.get('Name','') for r in all_csv_rows}
                for r in rows:
                    if r.get('Name','') not in existing_ids:
                        all_csv_rows.append(r)
                        existing_ids.add(r.get('Name',''))
                # Merge images
                for tid, img_list in imgs.items():
                    if tid not in all_images:
                        all_images[tid] = img_list

            if not all_csv_rows:
                st.error("Could not find trade data in the uploaded zip(s). Make sure you exported from Notion with 'Markdown & CSV' selected.")
            else:
                # Build trades list
                trades = []
                for i, row in enumerate(all_csv_rows):
                    trade = parse_csv_row(row, i)
                    tid = trade['id']
                    # Embed images
                    if tid in all_images:
                        with st.spinner(f"Compressing images for {tid}..."):
                            trade['images'] = [compress_image(b) for b in all_images[tid]]
                    trades.append(trade)

                # Sort by date
                trades.sort(key=lambda t: t.get('date',''))

                try:
                    html_out = build_journal_html(trades)
                    st.success(f"✅ Done! {len(trades)} trades loaded, {sum(len(t['images']) for t in trades)} screenshots embedded.")
                    st.download_button(
                        label="⬇ Download trading-journal.html",
                        data=html_out.encode('utf-8'),
                        file_name="trading-journal.html",
                        mime="text/html",
                    )
                    st.info("Open the downloaded file in any browser. All your data is saved locally — no account needed.")
                except FileNotFoundError:
                    st.error("Template file not found. Make sure journal_template.html is in the same folder as app.py.")
else:
    st.markdown("""
<div class="step"><span class="step-num">1</span> Export your Notion trading journal as <strong>Markdown & CSV</strong>
<p>In Notion: open your journal → ··· menu → Export → Markdown & CSV → include subpages</p></div>
<div class="step"><span class="step-num">2</span> Upload the zip file(s) above
<p>Notion may split large exports into multiple parts — upload all of them at once</p></div>
<div class="step"><span class="step-num">3</span> Click Generate → Download your HTML
<p>Open it in any browser. Works offline. Saves everything to your computer.</p></div>
""", unsafe_allow_html=True)

st.markdown("---")
st.markdown('<p style="color:#484848;font-size:0.8rem;text-align:center">Your files are processed in memory and never stored on any server.</p>', unsafe_allow_html=True)

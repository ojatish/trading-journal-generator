# ⬡ Trading Journal Generator

A free web app that converts a Notion trading journal export into a
fully self-contained offline HTML journal with charts, gallery, calendar,
and all your chart screenshots embedded — no Python, no installs needed.

## For community members (users)

1. Open the app link (shared by your server admin)
2. Export your Notion journal: **··· → Export → Markdown & CSV → include subpages**
3. Upload the zip(s) to the app
4. Click **Generate** and download `trading-journal.html`
5. Open it in any browser — works offline forever

---

## For the server owner (one-time deploy)

### Prerequisites
- A free [GitHub](https://github.com) account
- A free [Streamlit Community Cloud](https://streamlit.io/cloud) account (sign in with GitHub)

### Step 1 — Create a GitHub repository

1. Go to [github.com](https://github.com) → click **+** → **New repository**
2. Name it `trading-journal-generator`
3. Set it to **Public**
4. Click **Create repository**

### Step 2 — Upload the files

You need to upload these 3 files/folders to the repo root:

```
trading-journal-generator/
├── app.py
├── requirements.txt
├── journal_template.html
└── .streamlit/
    └── config.toml
```

**Easiest way — GitHub web UI:**

1. On your new repo page click **Add file → Upload files**
2. Drag and drop `app.py`, `requirements.txt`, `journal_template.html`
3. Click **Commit changes**
4. Now create the `.streamlit` folder: click **Add file → Create new file**
5. Type `.streamlit/config.toml` as the filename
6. Paste the contents of `config.toml` into the editor
7. Click **Commit changes**

### Step 3 — Deploy to Streamlit Cloud

1. Go to [share.streamlit.io](https://share.streamlit.io)
2. Click **New app**
3. Connect your GitHub account if prompted
4. Select:
   - **Repository:** `your-username/trading-journal-generator`
   - **Branch:** `main`
   - **Main file path:** `app.py`
5. Click **Deploy**

Streamlit will install dependencies and boot the app in ~2 minutes.
You'll get a permanent URL like `https://your-username-trading-journal-generator-app-xxxx.streamlit.app`

### Step 4 — Share with your Discord

Post that URL in your server. That's it.
Members just open the link, upload their Notion zip, download their HTML.

---

## Notes

- **Free forever** on Streamlit Community Cloud for public apps
- Apps sleep after ~7 days of no traffic — they wake up in ~30 seconds when visited
- No data is stored: files are processed in memory and immediately discarded
- Members' screenshots are compressed and embedded directly into their HTML file

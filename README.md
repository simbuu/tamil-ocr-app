# 🌸 Tamil Handwritten OCR — Flower Transaction Management System (v2)

Production-grade web app to digitise handwritten Tamil flower transaction records using EasyOCR + FastAPI.

## ✨ What's New in v2 — Data Collection & Analysis

| Feature | Purpose |
|---|---|
| **OCR Session Logging** | Every upload logged with image, raw OCR output, timing, confidence |
| **Correction Tracking** | Compare what OCR extracted vs. what user finally saved — per field |
| **Admin Review Page** (`/admin`) | Live dashboard of accuracy, corrections, low-confidence rows, failures |
| **Per-Field Accuracy** | See which fields (name/flower/weight) OCR struggles with |
| **Per-Flower Accuracy** | See which flowers OCR recognises most reliably |
| **User Feedback** | "Report Issue" button on every transaction, tracked in admin |
| **Training Data Export** | Download ZIP of images + labels for retraining |
| **Failed Sessions View** | Investigate every OCR crash |

## 🚀 Quick Start

```bash
unzip tamil-ocr-app-v2.zip && cd tamil-ocr-app-v2
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python main.py
# → http://localhost:8000
# → http://localhost:8000/admin   ← New review dashboard
```

## 📁 New Files Added in v2

```
app/models/
  ├── ocr_session.py        # NEW: Logs every OCR run
  └── feedback.py           # NEW: User-reported issues

app/services/
  ├── analytics_service.py  # NEW: Accuracy metrics, corrections
  └── export_service.py     # NEW: ZIP export for training data

app/routes/
  └── admin.py              # NEW: /api/admin/* endpoints

app/templates/
  └── admin.html            # NEW: Review dashboard with 6 tabs

app/models/transaction.py   # UPDATED: Now stores OCR-original values + edit tracking
app/routes/ocr.py           # UPDATED: Logs sessions, captures corrections
app/services/ocr_service.py # UPDATED: Per-stage timing instrumentation
```

## 🔑 Key URLs After Deployment

| Path | What's there |
|---|---|
| `/` | Dashboard (existing) |
| `/upload` | Upload + OCR (now tracks corrections) |
| `/transactions` | Records browser (now has Report Issue button) |
| `/rates` | Market rate management |
| `/reports` | PDF reports |
| **`/admin`** | **NEW — Accuracy dashboard, corrections, feedback, export** |
| `/docs` | Swagger API docs |

## 📊 The Admin Dashboard Tabs

1. **Field Accuracy** — % accuracy per field (customer / flower / weight)
2. **Per-Flower Accuracy** — Which flowers does OCR get right most often?
3. **Recent Corrections** — Side-by-side: what OCR said vs. what user saved
4. **Low Confidence** — Transactions where OCR confidence was < 60%
5. **Failed Sessions** — OCR crashes to investigate
6. **User Feedback** — Issues reported via the in-app button

## 📦 Exporting Training Data

Click **"⬇ Export Training Data"** in `/admin` to download a ZIP containing:

```
tamil-ocr-training-YYYYMMDD-HHMMSS.zip
├── README.md
├── images/                ← Original uploaded images
├── labels.jsonl           ← OCR vs ground truth per transaction
├── sessions.jsonl         ← Full OCR session metadata
└── stats.json
```

This data can be used to:
- **Fine-tune EasyOCR** on your customer's specific handwriting style
- **Benchmark alternative engines** (PaddleOCR, TrOCR, Tesseract) using the ground truth
- **Identify systematic errors** for targeted fixes

## 🚂 Deploying to Railway

Same as before — push to GitHub, connect Railway. The new `ocr_sessions` and `feedback` tables auto-create on first startup.

## 🔍 What to Watch for After Customer Trial

After your customer uses the app for a week, visit `/admin` and look at:

1. **Edit Rate** stat card — if > 30%, OCR is struggling. Check field accuracy tab.
2. **Per-Flower Accuracy** — flowers below 70% accuracy are top candidates for keyword tuning.
3. **Recent Corrections** — patterns here reveal systematic OCR errors.
4. **Failed Sessions** — any failures point to bugs or edge cases (very large images, etc.)
5. **User Feedback** — direct signal of what users find wrong.

Then export training data and use it to either tune the system or feed into a fine-tuned model.

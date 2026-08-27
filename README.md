# OptiStock — Data-Driven Inventory Management

A supply chain analytics dashboard built with Python and Streamlit. Tracks stock levels across 15 products, flags reorder alerts, and visualises inventory turnover ratios.

Built as part of a 4-week virtual internship with Mavenside.

---

## What's in this repo

```
mavenside_internship/
├── app.py                  ← Streamlit web app (main dashboard)
├── dashboard.html          ← Standalone HTML version (no Python needed to view)
├── inventory_data.csv      ← 15 products: SKU, cost, lead time, safety stock, reorder point
├── transactions.csv        ← 465 transactions: synthetic starting stock + real sales data
└── reorder_events.csv      ← Auto-generated log of every reorder/critical trigger (see below)
```

---

## Setup (Windows)

### 1. Install Python

Download and install Python from [python.org/downloads](https://www.python.org/downloads/).

> **Important:** On the first installer screen, check the box that says **"Add Python to PATH"** before clicking Install.

Verify it worked by opening PowerShell and running:

```
py --version
```

### 2. Clone the repo

```
git clone https://github.com/<your-username>/mavenside_internship.git
cd mavenside_internship
```

### 3. Install dependencies

```
pip install streamlit plotly pandas
```

This installs the three packages the app needs:
- `streamlit` — builds the web UI
- `plotly` — interactive charts
- `pandas` — data processing (groupby, merge, CSV reading)

---

## Running the dashboard

```
cd mavenside_internship
streamlit run app.py
```

The app opens automatically in your browser at **http://localhost:8501**

Press **R** in the browser at any time to reload with the latest CSV data.

---

## Using the dashboard

### Dashboard tab
- **KPI tiles** — total products, critical/warning/healthy counts, average weekly sales, total reorder events logged
- **Stock levels chart** — current stock vs reorder point vs safety stock for all 15 products
- **Stock health pie** — breakdown of alert statuses
- **Average weekly sales chart** — fast-moving vs slow-moving products ranked by units sold per week
- **Alert table** — colour-coded rows: red = critical, orange = warning, green = healthy

### Edit Data tab
- Edit safety stock, reorder point, unit cost, or lead time per product
- Add new transactions (restocks or sales) directly in the browser
- Click **Save Changes** — writes back to the CSV files and refreshes the dashboard

### Reorder Events tab
- Auto-generated feed of every sale that dropped a product to/below its Reorder Point or Safety Stock
- Fires the same day the sale happens (evaluated per-transaction, not on a periodic check)
- `New_Trigger = True` marks the first sale that pushed a product into that status; later sales while still flagged log again, marked `False`
- Written out to `reorder_events.csv` every time the app runs

---

## How alerts work

| Status | Condition | Meaning |
|---|---|---|
| CRITICAL | `Current_Level <= Safety_Stock` | Order immediately |
| WARNING | `Current_Level <= Reorder_Point` | Place an order soon |
| OK | `Current_Level > Reorder_Point` | Stock is healthy |

**Average Weekly Sales** = Total Units Sold ÷ number of weeks spanned by the transaction data (same date window applied to every product, so the comparison is consistent instead of each product using its own random slice of history). Products above the median are Fast-Moving; at or below are Slow-Moving. (ITR — Total Units Sold ÷ Current Stock Level — is still calculated and kept as a column, but Movement classification is now driven by the weekly rate since it's a more intuitive, consistent number for a store manager to read.)

---

## Data sources

- **Kaggle DataCo Smart Supply Chain Dataset** — real outbound sales data (top 15 products by order volume, 30 most recent sales each)
- **Synthetic starting stock** — one inbound row per product (labeled SYN001–SYN015) calculated as total window sales + half the reorder point as a buffer

---

## Running the standalone HTML dashboard

The `dashboard.html` file is a self-contained version that reads the CSVs via JavaScript. It requires a local server to run (browsers block direct file access for security).

With Python installed, run from the project folder:

```
python -m http.server 8080
```

Then open **http://localhost:8080/dashboard.html** in your browser.

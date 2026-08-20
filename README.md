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
└── transactions.csv        ← 465 transactions: synthetic starting stock + real sales data
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
- **KPI tiles** — total products, critical/warning/healthy counts, average ITR
- **Stock levels chart** — current stock vs reorder point vs safety stock for all 15 products
- **Stock health pie** — breakdown of alert statuses
- **Inventory turnover chart** — fast-moving vs slow-moving products ranked by ITR
- **Alert table** — colour-coded rows: red = critical, orange = warning, green = healthy

### Edit Data tab
- Edit safety stock, reorder point, unit cost, or lead time per product
- Add new transactions (restocks or sales) directly in the browser
- Click **Save Changes** — writes back to the CSV files and refreshes the dashboard

---

## How alerts work

| Status | Condition | Meaning |
|---|---|---|
| CRITICAL | `Current_Level <= Safety_Stock` | Order immediately |
| WARNING | `Current_Level <= Reorder_Point` | Place an order soon |
| OK | `Current_Level > Reorder_Point` | Stock is healthy |

**Inventory Turnover Ratio (ITR)** = Total Units Sold ÷ Current Stock Level. Products above the median ITR are classified as Fast-Moving; below as Slow-Moving.

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

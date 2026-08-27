# OptiStock — Data-Driven Inventory Management

A supply chain analytics dashboard built with Python and Streamlit. Tracks stock levels across 15 products, flags reorder alerts, and visualises inventory turnover ratios.

Built as part of a 4-week virtual internship with Mavenside.

---

## What's in this repo

```
mavenside_internship/
├── app.py                  ← Streamlit web app (main dashboard)
├── dashboard.html          ← Standalone HTML version (no Python needed to view)
├── inventory_data.csv      ← 15 products: SKU, cost, price, discount, lead time, safety stock, reorder point
└── transactions.csv        ← synthetic organic sales + restock history, 18 weeks ending today
```

**`inventory_data.csv` columns:** `SKU`, `Product_Name`, `Unit_Cost` (what we pay), `Lead_Time_Days`, `Safety_Stock`, `Reorder_Point`, `Unit_Price` (retail price), `Discount_Pct` (0-90, set from the app).

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

The app has four tabs:

### Action Center (first tab — the daily go-to view)
- **KPI tiles** — total products, critical/warning/healthy counts, average weekly sales, total inventory value
- **Needs Your Attention** — every flagged product, most urgent first, with days until stockout and lead time
- **Weekly Sales Trend** — one line chart, all 15 products, click a product in the legend to hide/show it, double-click to isolate it
- **Weekly Sales Velocity Detail** — pick a product from the dropdown to see its quantity + dollar sales, week over week

### Product Inventory tab
- **Inventory Table** — SKU, stock levels, status, unit price, discount %, and discounted price, colour-coded red/orange/green
- **Click a row** to open that product's weekly sales trend below the table, plus a discount slider + **Apply Discount** button that writes the new `Discount_Pct` back to `inventory_data.csv`
- **Stock levels chart** — current stock vs reorder point vs safety stock for all 15 products
- **Stock health pie** and **Average weekly sales chart** — fast-moving vs slow-moving products

### Inventory Data tab
- Edit safety stock, reorder point, unit cost, unit price, discount, or lead time per product
- Click **Save Inventory** — writes back to `inventory_data.csv`

### Transactions Data tab
- Sorted most-recent-first. Add new transactions (restocks or sales) directly in the browser
- Click **Save Transactions** — writes back to `transactions.csv`

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

- **Kaggle DataCo Smart Supply Chain Dataset** — top 15 products by order volume, used to pick real products/pricing
- **Synthetic sales + restock simulation** — each product gets a base weekly demand rate (scaled by price tier), mild seasonality, and random noise, split into individually-timed transactions across each week; stock depletes from sales and gets replenished by simulated restocks (labeled `SYN00x` for the initial stock, `RSTxxx` for restocks) whenever it runs low, capped so sales can never exceed what's actually in stock. Covers the 18 weeks ending today.

---

## Running the standalone HTML dashboard

The `dashboard.html` file is a self-contained version that reads the CSVs via JavaScript. It requires a local server to run (browsers block direct file access for security).

With Python installed, run from the project folder:

```
python -m http.server 8080
```

Then open **http://localhost:8080/dashboard.html** in your browser.

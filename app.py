import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(page_title="Inventory Tool Dashboard", layout="wide")
st.markdown("""
<style>
    [data-testid='stDeployButton'] {display:none}
    html { font-size: 19px; }
</style>
""", unsafe_allow_html=True)
st.title("Inventory Tool — Executive Dashboard")

# ─────────────────────────────────────────────
# LOAD DATA (runs every time so edits reflect immediately)
# ─────────────────────────────────────────────
inventory_df    = pd.read_csv('inventory_data.csv')
transactions_df = pd.read_csv('transactions.csv')

# ─────────────────────────────────────────────
# WEEK 2: Calculate Current Stock
# ─────────────────────────────────────────────
inbound  = transactions_df[transactions_df['Type'] == 'In'].groupby('SKU')['Quantity'].sum()
outbound = transactions_df[transactions_df['Type'] == 'Out'].groupby('SKU')['Quantity'].sum()

current_stock = inbound.subtract(outbound, fill_value=0).reset_index()
current_stock.columns = ['SKU', 'Current_Level']
current_stock['Current_Level'] = current_stock['Current_Level'].astype(int)

final_df = pd.merge(inventory_df, current_stock, on='SKU', how='left')
final_df['Needs_Reorder'] = final_df['Current_Level'] <= final_df['Reorder_Point']

# ─────────────────────────────────────────────
# WEEK 3: Stock Alerts
# ─────────────────────────────────────────────
def get_status(row):
    if row['Current_Level'] <= row['Safety_Stock']:
        return 'CRITICAL'
    elif row['Current_Level'] <= row['Reorder_Point']:
        return 'WARNING'
    else:
        return 'OK'

final_df['Status'] = final_df.apply(get_status, axis=1)

# ─────────────────────────────────────────────
# WEEK 3: Inventory Turnover Ratio + Weekly Sales Rate
# ─────────────────────────────────────────────
outbound_totals = transactions_df[transactions_df['Type'] == 'Out'].groupby('SKU')['Quantity'].sum().reset_index()
outbound_totals.columns = ['SKU', 'Total_Sold']

final_df = pd.merge(final_df, outbound_totals, on='SKU', how='left')
final_df['Total_Sold'] = final_df['Total_Sold'].fillna(0)
final_df['ITR'] = (final_df['Total_Sold'] / final_df['Current_Level']).round(2)

# Consistent weekly sales rate — same global date window applied to every
# product, so Fast/Slow-Moving compares apples to apples instead of each
# product's own random slice of transaction history.
tx_dates = pd.to_datetime(transactions_df['Date'])
total_weeks = max((tx_dates.max() - tx_dates.min()).days / 7, 1)

final_df['Avg_Weekly_Sales'] = (final_df['Total_Sold'] / total_weeks).round(2)

median_weekly_sales = final_df['Avg_Weekly_Sales'].median()
final_df['Movement'] = final_df['Avg_Weekly_Sales'].apply(
    lambda x: 'Fast-Moving' if x > median_weekly_sales else 'Slow-Moving'
)

# ─────────────────────────────────────────────
# AUTOMATION: Reorder Trigger Events Feed
# Replays every transaction in date order and logs an event the moment a
# sale drops a product to/below its Reorder Point or Safety Stock — the
# trigger fires the same day the sale happens, not on a periodic check.
# ─────────────────────────────────────────────
def build_reorder_events(inventory_df, transactions_df):
    thresholds = inventory_df.set_index('SKU')[['Safety_Stock', 'Reorder_Point']]
    names = inventory_df.set_index('SKU')['Product_Name']

    tx_sorted = transactions_df.copy()
    tx_sorted['Date'] = pd.to_datetime(tx_sorted['Date'])
    tx_sorted = tx_sorted.sort_values('Date').reset_index(drop=True)

    running_stock = {}
    last_status = {}
    events = []

    for _, tx in tx_sorted.iterrows():
        sku = tx['SKU']
        running_stock.setdefault(sku, 0)

        if tx['Type'] == 'In':
            running_stock[sku] += tx['Quantity']
            continue

        running_stock[sku] -= tx['Quantity']
        level = running_stock[sku]

        if sku not in thresholds.index:
            continue
        safety_stock  = thresholds.loc[sku, 'Safety_Stock']
        reorder_point = thresholds.loc[sku, 'Reorder_Point']

        if level <= safety_stock:
            status = 'CRITICAL'
        elif level <= reorder_point:
            status = 'WARNING'
        else:
            status = 'OK'

        if status in ('CRITICAL', 'WARNING'):
            events.append({
                'Date': tx['Date'].strftime('%Y-%m-%d'),
                'Transaction_ID': tx['Transaction_ID'],
                'SKU': sku,
                'Product_Name': names.get(sku, sku),
                'Quantity_Sold': tx['Quantity'],
                'Stock_After_Sale': level,
                'Safety_Stock': safety_stock,
                'Reorder_Point': reorder_point,
                'Trigger_Type': status,
                'New_Trigger': last_status.get(sku) != status,
            })
        last_status[sku] = status

    return pd.DataFrame(events)

reorder_events_df = build_reorder_events(inventory_df, transactions_df)
reorder_events_df.to_csv('reorder_events.csv', index=False)

# ─────────────────────────────────────────────
# TABS
# ─────────────────────────────────────────────
tab1, tab2, tab3, tab4 = st.tabs(["Dashboard", "Inventory Data", "Transactions Data", "Reorder Events"])

# ═════════════════════════════════════════════
# TAB 1 — DASHBOARD
# ═════════════════════════════════════════════
with tab1:
    st.caption(f"Kaggle DataCo Supply Chain · {len(inventory_df)} products · {len(transactions_df)} transactions")

    # KPI tiles
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    col1.metric("Total Products", len(final_df))
    col2.metric("Critical",  int((final_df['Status'] == 'CRITICAL').sum()))
    col3.metric("Warning",   int((final_df['Status'] == 'WARNING').sum()))
    col4.metric("Healthy",   int((final_df['Status'] == 'OK').sum()))
    col5.metric("Avg Weekly Sales", round(final_df['Avg_Weekly_Sales'].mean(), 2))
    col6.metric("Reorder Events", len(reorder_events_df))

    st.divider()

    # Chart 1: Stock vs Reorder Point vs Safety Stock
    st.subheader("Stock Levels vs. Reorder Point vs. Safety Stock")
    short_names = final_df['Product_Name'].str[:20]

    fig1 = go.Figure()
    fig1.add_bar(name='Current Stock', x=short_names, y=final_df['Current_Level'],  marker_color='#4C9BE8')
    fig1.add_bar(name='Reorder Point', x=short_names, y=final_df['Reorder_Point'],  marker_color='#F4A100')
    fig1.add_bar(name='Safety Stock',  x=short_names, y=final_df['Safety_Stock'],   marker_color='#E84C4C')
    fig1.update_layout(
        barmode='group',
        xaxis_tickangle=-40,
        yaxis_title='Units',
        legend=dict(orientation='h', y=1.1),
        height=450
    )
    st.plotly_chart(fig1, use_container_width=True)

    st.divider()

    # Chart 2 + 3 side by side
    left, right = st.columns(2)

    with left:
        st.subheader("Stock Health Overview")
        status_counts_df = final_df['Status'].value_counts().reset_index()
        status_counts_df.columns = ['Status', 'Count']
        fig2 = px.pie(
            status_counts_df,
            names='Status', values='Count', color='Status',
            color_discrete_map={'OK': '#2ECC71', 'WARNING': '#F4A100', 'CRITICAL': '#E84C4C'}
        )
        fig2.update_traces(textinfo='percent+label+value')
        st.plotly_chart(fig2, use_container_width=True)

    with right:
        st.subheader("Average Weekly Sales")
        weekly_sorted = final_df.sort_values('Avg_Weekly_Sales', ascending=False).copy()
        weekly_sorted['Short_Name'] = weekly_sorted['Product_Name'].str[:20]
        fig3 = px.bar(
            weekly_sorted, x='Short_Name', y='Avg_Weekly_Sales', color='Movement', text='Avg_Weekly_Sales',
            color_discrete_map={'Fast-Moving': '#2ECC71', 'Slow-Moving': '#E84C4C'}
        )
        fig3.update_layout(xaxis_tickangle=-40, yaxis_title='Units Sold / Week', xaxis_title='', height=400)
        fig3.update_traces(textposition='outside')
        st.plotly_chart(fig3, use_container_width=True)
        st.caption(
            f"**Avg Weekly Sales = Total Units Sold ÷ {total_weeks:.1f} weeks** "
            "(the same date window is used for every product, so the comparison is consistent) — "
            "a plain, easy-to-read measure of how fast each product actually moves. "
            "A higher number means it's flying off the shelf; a lower number means it's sitting "
            "and risks becoming dead stock. Products above the median are Fast-Moving, below are Slow-Moving."
        )

    st.divider()

    # Alert table with color coding
    st.subheader("Stock Alerts")
    display_df = final_df[['SKU', 'Product_Name', 'Current_Level', 'Safety_Stock', 'Reorder_Point', 'Status']].copy()

    def style_row(row):
        colors = {
            'CRITICAL': 'background-color: rgba(239, 68, 68, 0.15)',
            'WARNING':  'background-color: rgba(245, 158, 11, 0.15)',
            'OK':       'background-color: rgba(34, 197, 94, 0.15)',
        }
        return [colors.get(row['Status'], '')] * len(row)

    def style_status_cell(val):
        styles = {
            'CRITICAL': 'background-color: #ef4444; color: white; font-weight: 700',
            'WARNING':  'background-color: #f59e0b; color: white; font-weight: 700',
            'OK':       'background-color: #22c55e; color: white; font-weight: 700',
        }
        return styles.get(val, '')

    styled = (
        display_df.style
        .apply(style_row, axis=1)
        .map(style_status_cell, subset=['Status'])
    )
    st.dataframe(styled, use_container_width=True, hide_index=True)

# ═════════════════════════════════════════════
# TAB 2 — EDIT INVENTORY
# ═════════════════════════════════════════════
with tab2:
    st.subheader("Inventory Data")
    st.caption("Change Safety Stock, Reorder Point, Unit Cost, or Lead Time. Click Save when done.")

    edited_inventory = st.data_editor(
        inventory_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            'SKU':           st.column_config.TextColumn('SKU', disabled=True),
            'Product_Name':  st.column_config.TextColumn('Product Name', disabled=True),
            'Unit_Cost':     st.column_config.NumberColumn('Unit Cost ($)', min_value=0, format='$%.2f'),
            'Lead_Time_Days':st.column_config.NumberColumn('Lead Time (days)', min_value=1),
            'Safety_Stock':  st.column_config.NumberColumn('Safety Stock', min_value=0),
            'Reorder_Point': st.column_config.NumberColumn('Reorder Point', min_value=0),
        },
        key='inv_editor'
    )

    st.divider()

    if st.button("Save Inventory", type='primary', key='save_inv'):
        edited_inventory.to_csv('inventory_data.csv', index=False)
        st.success("Saved! Switch to Dashboard and press R to refresh.")
        st.rerun()

# ═════════════════════════════════════════════
# TAB 3 — EDIT TRANSACTIONS
# ═════════════════════════════════════════════
with tab3:
    st.subheader("Transactions Data")
    st.caption("Add new In/Out rows at the bottom, or edit existing ones. Click Save when done.")

    edited_transactions = st.data_editor(
        transactions_df,
        use_container_width=True,
        hide_index=True,
        num_rows='dynamic',
        column_config={
            'Transaction_ID': st.column_config.TextColumn('Transaction ID'),
            'SKU':            st.column_config.SelectboxColumn('SKU', options=sorted(inventory_df['SKU'].tolist())),
            'Date':           st.column_config.TextColumn('Date (YYYY-MM-DD)'),
            'Type':           st.column_config.SelectboxColumn('Type', options=['In', 'Out']),
            'Quantity':       st.column_config.NumberColumn('Quantity', min_value=1),
        },
        key='tx_editor'
    )

    st.divider()

    if st.button("Save Transactions", type='primary', key='save_tx'):
        edited_transactions.to_csv('transactions.csv', index=False)
        st.success("Saved! Switch to Dashboard and press R to refresh.")
        st.rerun()

# ═════════════════════════════════════════════
# TAB 4 — REORDER EVENTS (AUTOMATION FEED)
# ═════════════════════════════════════════════
with tab4:
    st.subheader("Automatic Reorder Trigger Events")
    st.caption(
        "Every time a sale drops a product to or below its Reorder Point or Safety Stock, "
        "an event is logged here automatically — triggered the same day the sale happens, "
        "not on a periodic check. This is the automation feed a store manager can audit. "
        "Saved to reorder_events.csv."
    )

    if reorder_events_df.empty:
        st.info("No reorder triggers in the current transaction history.")
    else:
        events_display = reorder_events_df.sort_values('Date', ascending=False).copy()

        def style_event_row(row):
            colors = {
                'CRITICAL': 'background-color: rgba(239, 68, 68, 0.15)',
                'WARNING':  'background-color: rgba(245, 158, 11, 0.15)',
            }
            return [colors.get(row['Trigger_Type'], '')] * len(row)

        styled_events = events_display.style.apply(style_event_row, axis=1)
        st.dataframe(styled_events, use_container_width=True, hide_index=True)

        st.caption(
            "`New_Trigger = True` marks the first sale that pushed a product into that status. "
            "Later sales while it's still flagged log another event too, but marked False, "
            "so the feed shows both the moment something first went wrong and everything since."
        )

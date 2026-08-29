import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(page_title="Mavenside Inventory Management", layout="wide")
st.markdown("""
<style>
    [data-testid='stDeployButton'] {display:none}
    html { font-size: 19px; }
</style>
""", unsafe_allow_html=True)
st.title("Mavenside Inventory Management")

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
# ACTION CENTER: Days Until Stockout, Financial Exposure, Recent Trend
# ─────────────────────────────────────────────
final_df['Daily_Rate'] = final_df['Avg_Weekly_Sales'] / 7
final_df['Days_Until_Stockout'] = final_df.apply(
    lambda r: round(r['Current_Level'] / r['Daily_Rate'], 1) if r['Daily_Rate'] > 0 else float('inf'),
    axis=1
)

final_df['Inventory_Value'] = (final_df['Current_Level'] * final_df['Unit_Cost']).round(2)

# ─────────────────────────────────────────────
# ACTION CENTER: Weekly Sales Trend (quantity + dollar) per product
# Bins every "Out" transaction into one of the last N weekly buckets so each
# product's sales can be plotted week over week, quantity and dollar both.
# ─────────────────────────────────────────────
n_weeks = int(total_weeks)
week_starts = pd.date_range(start=tx_dates.min().normalize(), periods=n_weeks, freq='7D')

out_tx = transactions_df[transactions_df['Type'] == 'Out'].copy()
out_tx['Date'] = pd.to_datetime(out_tx['Date'])
week_idx = ((out_tx['Date'] - week_starts[0]).dt.days // 7).clip(upper=n_weeks - 1)
out_tx['Week_Start'] = week_starts[week_idx.values]

weekly_sales = out_tx.groupby(['SKU', 'Week_Start'])['Quantity'].sum().reset_index()

# Fill in every product x every week, even weeks with zero sales, so the
# trend lines show real gaps instead of silently skipping them.
all_combos = pd.MultiIndex.from_product([inventory_df['SKU'], week_starts], names=['SKU', 'Week_Start'])
weekly_sales = weekly_sales.set_index(['SKU', 'Week_Start']).reindex(all_combos, fill_value=0).reset_index()
weekly_sales = weekly_sales.rename(columns={'Quantity': 'Quantity_Sold'})

weekly_sales = weekly_sales.merge(inventory_df[['SKU', 'Product_Name', 'Unit_Cost']], on='SKU', how='left')
weekly_sales['Dollar_Amount'] = (weekly_sales['Quantity_Sold'] * weekly_sales['Unit_Cost']).round(2)
weekly_sales = weekly_sales.sort_values(['SKU', 'Week_Start']).reset_index(drop=True)

# Discounted selling price
final_df['Discounted_Price'] = (final_df['Unit_Price'] * (1 - final_df['Discount_Pct'] / 100)).round(2)

def render_weekly_detail(product_name):
    """Dual-axis quantity/dollar chart + week-over-week table for one product.
    Shared by Action Center and the Product Inventory table's click-to-expand."""
    detail = weekly_sales[weekly_sales['Product_Name'] == product_name].sort_values('Week_Start').copy()

    fig_detail = go.Figure()
    fig_detail.add_bar(
        name='Quantity Sold', x=detail['Week_Start'], y=detail['Quantity_Sold'],
        marker_color='#4C9BE8', yaxis='y1'
    )
    fig_detail.add_scatter(
        name='Dollar Amount', x=detail['Week_Start'], y=detail['Dollar_Amount'],
        mode='lines+markers', marker_color='#F4A100', yaxis='y2'
    )
    fig_detail.update_layout(
        yaxis=dict(title='Units Sold'),
        yaxis2=dict(title='Dollar Amount ($)', overlaying='y', side='right'),
        legend=dict(orientation='h', y=1.12),
        height=350,
        margin=dict(t=30)
    )
    st.plotly_chart(fig_detail, use_container_width=True, key=f'weekly_detail_{product_name}')

    detail['Qty_Change_vs_Prior_Week'] = detail['Quantity_Sold'].diff()
    detail['Dollar_Change_vs_Prior_Week'] = detail['Dollar_Amount'].diff()
    detail_display = detail[[
        'Week_Start', 'Quantity_Sold', 'Qty_Change_vs_Prior_Week', 'Dollar_Amount', 'Dollar_Change_vs_Prior_Week'
    ]].copy()
    detail_display['Week_Start'] = detail_display['Week_Start'].dt.strftime('%Y-%m-%d')
    detail_display.columns = [
        'Week Starting', 'Quantity Sold', 'Qty Change vs Prior Week', 'Dollar Amount', '$ Change vs Prior Week'
    ]
    st.dataframe(detail_display, use_container_width=True, hide_index=True, key=f'weekly_table_{product_name}')
    st.caption("Week-over-week velocity for the selected product — first week has no prior week to compare against.")

# ─────────────────────────────────────────────
# TABS
# ─────────────────────────────────────────────
tab0, tab1, tab2, tab3 = st.tabs(["Action Center", "Product Inventory", "Inventory Data", "Transactions Data"])

# ═════════════════════════════════════════════
# TAB 0 — ACTION CENTER
# ═════════════════════════════════════════════
with tab0:
    # Top-level KPI tiles
    total_value = final_df['Inventory_Value'].sum()

    k1, k2, k3, k4, k5, k6 = st.columns(6)
    k1.metric("Total Products", len(final_df))
    k2.metric(
        "Insufficient Inventory",
        int((final_df['Status'] == 'CRITICAL').sum()),
        help="Current stock is at or below Safety Stock — the emergency buffer is gone. Order immediately."
    )
    k3.metric(
        "Reorder Needed",
        int((final_df['Status'] == 'WARNING').sum()),
        help="Current stock is at or below the Reorder Point, but still above Safety Stock. Time to place an order."
    )
    k4.metric(
        "Sufficient Inventory",
        int((final_df['Status'] == 'OK').sum()),
        help="Current stock is above the Reorder Point. No action needed right now."
    )
    k5.metric(
        "Avg Weekly Sales",
        round(final_df['Avg_Weekly_Sales'].mean(), 2),
        help=f"Average units sold per week across all products (Total Units Sold ÷ {total_weeks:.1f} weeks, "
             "the same date window for every product)."
    )
    k6.metric(
        "Total Inventory Value", f"${total_value:,.0f}",
        help="Current stock × unit cost, summed across all products."
    )

    st.divider()

    # Priority action list
    st.subheader("Needs Your Attention")
    priority = final_df[final_df['Status'] != 'OK'].copy()

    if priority.empty:
        st.success("Nothing needs attention right now — every product is sufficiently stocked.")
    else:
        severity_rank = {'CRITICAL': 0, 'WARNING': 1}
        priority['_rank'] = priority['Status'].map(severity_rank)
        priority = priority.sort_values(['_rank', 'Days_Until_Stockout'])

        priority_display = priority[[
            'SKU', 'Product_Name', 'Status', 'Current_Level',
            'Days_Until_Stockout', 'Lead_Time_Days', 'Safety_Stock', 'Reorder_Point'
        ]].copy()
        priority_display['Days_Until_Stockout'] = priority_display['Days_Until_Stockout'].apply(
            lambda x: f"{x:.1f}" if x != float('inf') else "—"
        )

        def style_priority_row(row):
            colors = {
                'CRITICAL': 'background-color: rgba(239, 68, 68, 0.15)',
                'WARNING':  'background-color: rgba(245, 158, 11, 0.15)',
            }
            return [colors.get(row['Status'], '')] * len(row)

        def style_priority_status(val):
            styles = {
                'CRITICAL': 'background-color: #ef4444; color: white; font-weight: 700',
                'WARNING':  'background-color: #f59e0b; color: white; font-weight: 700',
            }
            return styles.get(val, '')

        styled_priority = (
            priority_display.style
            .apply(style_priority_row, axis=1)
            .map(style_priority_status, subset=['Status'])
        )
        st.dataframe(styled_priority, use_container_width=True, hide_index=True)
        st.caption(
            "Sorted most urgent first: Insufficient Inventory before Reorder Needed, then by days until "
            "stockout. Lead Time is shown so you know how urgent placing the order really is — a 7-day-lead "
            "item flagged today is more urgent than a 2-day-lead item flagged today."
        )

    st.divider()

    # Weekly sales trend — every product, one chart, clickable legend
    st.subheader(f"Weekly Sales Trend — Last {n_weeks} Weeks")
    fig_trend = px.line(
        weekly_sales, x='Week_Start', y='Quantity_Sold', color='Product_Name',
        markers=True
    )
    fig_trend.update_layout(
        xaxis_title='Week', yaxis_title='Units Sold', height=500,
        legend_title_text='Product (click to hide, double-click to isolate)'
    )
    st.plotly_chart(fig_trend, use_container_width=True)
    st.caption(
        "Click a product in the legend to hide/show its line; double-click a product to isolate it and "
        "hide everything else. Every product has a point for every week, including weeks with zero sales."
    )

    st.divider()

    # Per-product weekly detail — quantity and dollar amount, week over week
    st.subheader("Weekly Sales Velocity Detail")
    selected_name = st.selectbox(
        "Select a product", options=sorted(inventory_df['Product_Name'].unique()), key='action_center_product'
    )
    render_weekly_detail(selected_name)

# ═════════════════════════════════════════════
# TAB 1 — PRODUCT INVENTORY
# ═════════════════════════════════════════════
with tab1:
    st.caption(f"Kaggle DataCo Supply Chain · {len(inventory_df)} products · {len(transactions_df)} transactions")

    # Inventory table with color coding, price/discount, and click-to-expand detail
    st.subheader("Inventory Table")
    st.caption("Click a product row to see its weekly sales trend and set a discount.")
    display_df = final_df[[
        'SKU', 'Product_Name', 'Current_Level', 'Safety_Stock', 'Reorder_Point', 'Status',
        'Unit_Price', 'Discount_Pct', 'Discounted_Price'
    ]].copy()
    display_df.columns = [
        'SKU', 'Product_Name', 'Current_Level', 'Safety_Stock', 'Reorder_Point', 'Status',
        'Unit Price', 'Discount %', 'Discounted Price'
    ]

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
        .format({'Unit Price': '${:.2f}', 'Discounted Price': '${:.2f}', 'Discount %': '{:.0f}%'})
    )
    table_event = st.dataframe(
        styled, use_container_width=True, hide_index=True,
        on_select='rerun', selection_mode='single-row', key='inventory_table'
    )

    selected_rows = table_event.selection.rows if table_event and table_event.selection else []
    if selected_rows:
        selected_sku = display_df.iloc[selected_rows[0]]['SKU']
        selected_product = display_df.iloc[selected_rows[0]]['Product_Name']
        current_discount = int(final_df.loc[final_df['SKU'] == selected_sku, 'Discount_Pct'].iloc[0])

        st.markdown(f"#### {selected_product}")

        dc1, dc2 = st.columns([3, 1])
        new_discount = dc1.slider(
            "Discount %", min_value=0, max_value=90, value=current_discount, key=f'discount_slider_{selected_sku}'
        )
        if dc2.button("Apply Discount", key=f'apply_discount_{selected_sku}'):
            inventory_df.loc[inventory_df['SKU'] == selected_sku, 'Discount_Pct'] = new_discount
            inventory_df.to_csv('inventory_data.csv', index=False)
            st.success(f"Discount updated to {new_discount}% for {selected_product}.")
            st.rerun()

        render_weekly_detail(selected_product)

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

# ═════════════════════════════════════════════
# TAB 2 — EDIT INVENTORY
# ═════════════════════════════════════════════
with tab2:
    st.subheader("Inventory Data")
    st.caption("Change Safety Stock, Reorder Point, Unit Cost, Unit Price, Discount, or Lead Time. Click Save when done.")

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
            'Unit_Price':    st.column_config.NumberColumn('Unit Price ($)', min_value=0, format='$%.2f'),
            'Discount_Pct':  st.column_config.NumberColumn('Discount (%)', min_value=0, max_value=90),
        },
        key='inv_editor'
    )

    st.divider()

    if st.button("Save Inventory", type='primary', key='save_inv'):
        edited_inventory.to_csv('inventory_data.csv', index=False)
        st.success("Saved! Switch to Product Inventory and press R to refresh.")
        st.rerun()

# ═════════════════════════════════════════════
# TAB 3 — EDIT TRANSACTIONS
# ═════════════════════════════════════════════
with tab3:
    st.subheader("Transactions Data")
    st.caption("Add new In/Out rows at the bottom, or edit existing ones. Click Save when done.")

    transactions_display = transactions_df.copy()
    transactions_display['_sort_date'] = pd.to_datetime(transactions_display['Date'])
    transactions_display = transactions_display.sort_values('_sort_date', ascending=False).drop(columns='_sort_date').reset_index(drop=True)

    edited_transactions = st.data_editor(
        transactions_display,
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
        st.success("Saved! Switch to Product Inventory and press R to refresh.")
        st.rerun()

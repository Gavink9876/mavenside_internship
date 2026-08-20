import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(page_title="OptiStock Dashboard", layout="wide")
st.title("OptiStock — Executive Dashboard")

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
# WEEK 3: Inventory Turnover Ratio
# ─────────────────────────────────────────────
outbound_totals = transactions_df[transactions_df['Type'] == 'Out'].groupby('SKU')['Quantity'].sum().reset_index()
outbound_totals.columns = ['SKU', 'Total_Sold']

final_df = pd.merge(final_df, outbound_totals, on='SKU', how='left')
final_df['ITR'] = (final_df['Total_Sold'] / final_df['Current_Level']).round(2)

median_itr = final_df['ITR'].median()
final_df['Movement'] = final_df['ITR'].apply(
    lambda x: 'Fast-Moving' if x >= median_itr else 'Slow-Moving'
)

# ─────────────────────────────────────────────
# TABS
# ─────────────────────────────────────────────
tab1, tab2 = st.tabs(["Dashboard", "Edit Data"])

# ═════════════════════════════════════════════
# TAB 1 — DASHBOARD
# ═════════════════════════════════════════════
with tab1:
    st.caption(f"Kaggle DataCo Supply Chain · {len(inventory_df)} products · {len(transactions_df)} transactions")

    # KPI tiles
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Total Products", len(final_df))
    col2.metric("Critical",  int((final_df['Status'] == 'CRITICAL').sum()))
    col3.metric("Warning",   int((final_df['Status'] == 'WARNING').sum()))
    col4.metric("Healthy",   int((final_df['Status'] == 'OK').sum()))
    col5.metric("Avg ITR",   round(final_df['ITR'].mean(), 2))

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
        st.subheader("Inventory Turnover Ratio")
        itr_sorted = final_df.sort_values('ITR', ascending=False).copy()
        itr_sorted['Short_Name'] = itr_sorted['Product_Name'].str[:20]
        fig3 = px.bar(
            itr_sorted, x='Short_Name', y='ITR', color='Movement', text='ITR',
            color_discrete_map={'Fast-Moving': '#2ECC71', 'Slow-Moving': '#E84C4C'}
        )
        fig3.update_layout(xaxis_tickangle=-40, yaxis_title='ITR', xaxis_title='', height=400)
        fig3.update_traces(textposition='outside')
        st.plotly_chart(fig3, use_container_width=True)

    st.divider()

    # Alert table with color coding
    st.subheader("Stock Alerts")
    display_df = final_df[['SKU', 'Product_Name', 'Current_Level', 'Safety_Stock', 'Reorder_Point', 'Status', 'ITR', 'Movement']].copy()

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
# TAB 2 — EDIT DATA
# ═════════════════════════════════════════════
with tab2:
    st.subheader("Edit Inventory Data")
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

    st.subheader("Edit Transactions")
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

    if st.button("Save Changes", type='primary'):
        edited_inventory.to_csv('inventory_data.csv', index=False)
        edited_transactions.to_csv('transactions.csv', index=False)
        st.success("Saved! Dashboard will reflect changes.")
        st.rerun()

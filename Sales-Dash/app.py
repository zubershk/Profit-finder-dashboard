import streamlit as st
import pandas as pd
import plotly.express as px

# 1. Page Configuration
st.set_page_config(page_title="Shopify Sales Intelligence", layout="wide")

# 2. Title & Intro
st.title("📊 E-commerce Profit-Finder Dashboard")
st.markdown("""
**How to use:**
1. View the sample data below to see how it works.
2. Upload your own CSV file in the sidebar to analyze your own sales.
""")
st.markdown("---")

# 3. Sidebar - File Uploader & Filters
st.sidebar.header("User Input")

# A. File Uploader
uploaded_file = st.sidebar.file_uploader("Upload your CSV file", type=["csv"])

# B. Load Data Logic
if uploaded_file is not None:
    # Use user's data if uploaded
    try:
        df = pd.read_csv(uploaded_file)
        st.sidebar.success("File Uploaded Successfully!")
    except Exception as e:
        st.error(f"Error reading file: {e}")
        st.stop()
else:
    # Use sample data if nothing uploaded
    try:
        df = pd.read_csv('sales_data.csv')
        st.sidebar.info("Showing Sample Data (Upload your CSV to change)")
    except FileNotFoundError:
        st.error("Sample data file not found. Please run generate_data.py first.")
        st.stop()

# Ensure 'Date' column is datetime
# (This handles if the user's CSV date format is standard)
if 'Date' in df.columns:
    df['Date'] = pd.to_datetime(df['Date'])
else:
    st.error("Your CSV must have a 'Date' column.")
    st.stop()

# 4. Sidebar Filters (Dynamic based on loaded data)
st.sidebar.subheader("Filter Data")
if 'Product' in df.columns:
    product_options = df["Product"].unique()
    product_filter = st.sidebar.multiselect(
        "Select Products:",
        options=product_options,
        default=product_options
    )
    # Apply Filter
    df_selection = df.query("Product == @product_filter")
else:
    st.warning("Your CSV needs a 'Product' column for filters to work.")
    df_selection = df

# 5. KPI Section (Key Performance Indicators)
# Check if columns exist before calculating
if {'Total Revenue', 'Total Profit'}.issubset(df_selection.columns):
    total_revenue = df_selection["Total Revenue"].sum()
    total_profit = df_selection["Total Profit"].sum()
    avg_order_value = df_selection["Total Revenue"].mean()

    left_column, middle_column, right_column = st.columns(3)
    with left_column:
        st.subheader("Total Revenue")
        st.subheader(f"₹ {total_revenue:,.0f}")
    with middle_column:
        st.subheader("Total Profit")
        st.subheader(f"₹ {total_profit:,.0f}")
    with right_column:
        st.subheader("Avg Order Value")
        st.subheader(f"₹ {avg_order_value:,.0f}")
else:
    st.warning("Your CSV needs 'Total Revenue' and 'Total Profit' columns to show KPIs.")

st.markdown("---")

# 6. Charts

# Chart 1: Sales by Product
if 'Product' in df_selection.columns and 'Total Revenue' in df_selection.columns:
    sales_by_product = df_selection.groupby("Product")[["Total Revenue"]].sum().sort_values(by="Total Revenue")
    fig_product_sales = px.bar(
        sales_by_product, 
        x="Total Revenue", 
        y=sales_by_product.index, 
        orientation="h", 
        title="<b>Sales by Product</b>",
        template="plotly_white"
    )
    
    # Chart 2: Daily Sales Trend
    daily_sales = df_selection.groupby("Date")[["Total Revenue"]].sum().reset_index()
    fig_daily_sales = px.line(
        daily_sales, 
        x="Date", 
        y="Total Revenue", 
        title="<b>Daily Revenue Trend</b>",
        template="plotly_white"
    )

    left_chart, right_chart = st.columns(2)
    left_chart.plotly_chart(fig_product_sales, use_container_width=True)
    right_chart.plotly_chart(fig_daily_sales, use_container_width=True)

# 7. Raw Data View
if st.checkbox("Show Raw Data"):
    st.dataframe(df_selection)
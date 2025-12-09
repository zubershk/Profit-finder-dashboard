import streamlit as st
import pandas as pd
import plotly.express as px
import random
from datetime import datetime, timedelta

# --- FUNCTION TO GENERATE DATA IF FILE IS MISSING ---
@st.cache_data
def generate_data():
    """Generates fake e-commerce data if no CSV is found."""
    num_rows = 500
    products = [
        {'name': 'Wireless Headphones', 'price': 2500, 'cost': 1200},
        {'name': 'Smart Watch', 'price': 4500, 'cost': 2000},
        {'name': 'Laptop Stand', 'price': 1200, 'cost': 500},
        {'name': 'Mechanical Keyboard', 'price': 6000, 'cost': 3500},
        {'name': 'USB-C Hub', 'price': 1500, 'cost': 600}
    ]
    data = []
    for i in range(num_rows):
        product = random.choice(products)
        date = datetime.now() - timedelta(days=random.randint(0, 30))
        quantity = random.randint(1, 3)
        data.append({
            'Order ID': f"ORD-{1000+i}",
            'Date': date.strftime('%Y-%m-%d'),
            'Product': product['name'],
            'Price': product['price'],
            'Cost': product['cost'],
            'Quantity': quantity,
            'Total Revenue': product['price'] * quantity,
            'Total Profit': (product['price'] - product['cost']) * quantity
        })
    return pd.DataFrame(data)

# --- PAGE CONFIG ---
st.set_page_config(page_title="Shopify Sales Intelligence", layout="wide")

st.title("E-commerce Profit-Finder Dashboard")
st.markdown("""
**How to use:**
1. View the sample data below to see how it works.
2. Upload your own CSV file in the sidebar to analyze your own sales.
""")
st.markdown("---")

# --- SIDEBAR & DATA LOADING ---
st.sidebar.header("User Input")
uploaded_file = st.sidebar.file_uploader("Upload your CSV file", type=["csv"])

if uploaded_file is not None:
    try:
        df = pd.read_csv(uploaded_file)
        st.sidebar.success("File Uploaded Successfully!")
    except Exception as e:
        st.error(f"Error reading file: {e}")
        st.stop()
else:
    df = generate_data()
    st.sidebar.info("Showing Sample Data (Upload your CSV to change)")

# --- ROBUST DATE PARSING ---
if 'Date' in df.columns:
    df['Date'] = pd.to_datetime(df['Date'].astype(str), errors='coerce')
    df = df.dropna(subset=['Date'])
    
    if df.empty:
        st.error("Error: The 'Date' column exists but contains no valid dates.")
        st.stop()
else:
    st.error("Your CSV must have a 'Date' column.")
    st.stop()

# --- SIDEBAR FILTERS ---
if 'Product' in df.columns:
    product_options = df["Product"].unique()
    product_filter = st.sidebar.multiselect(
        "Select Products:",
        options=product_options,
        default=product_options
    )
    df_selection = df.query("Product == @product_filter")
else:
    df_selection = df

# --- KPI SECTION ---
if {'Total Revenue', 'Total Profit'}.issubset(df_selection.columns):
    total_revenue = df_selection["Total Revenue"].sum()
    total_profit = df_selection["Total Profit"].sum()
    avg_order_value = df_selection["Total Revenue"].mean()

    col1, col2, col3 = st.columns(3)
    col1.metric("Total Revenue", f"₹ {total_revenue:,.0f}")
    col2.metric("Total Profit", f"₹ {total_profit:,.0f}")
    col3.metric("Avg Order Value", f"₹ {avg_order_value:,.0f}")
else:
    st.warning("Your CSV needs 'Total Revenue' and 'Total Profit' columns to show KPIs.")

st.markdown("---")

# --- CHARTS ---
if 'Product' in df_selection.columns and 'Total Revenue' in df_selection.columns:
    
    sales_by_product = df_selection.groupby("Product")[["Total Revenue"]].sum().sort_values(by="Total Revenue")
    fig_product = px.bar(
        sales_by_product, 
        x="Total Revenue", 
        y=sales_by_product.index, 
        orientation="h", 
        title="<b>Sales by Product</b>",
        template="plotly_white"
    )
    

    daily_sales = df_selection.groupby("Date")[["Total Revenue"]].sum().reset_index()
    fig_daily = px.line(
        daily_sales, 
        x="Date", 
        y="Total Revenue", 
        title="<b>Daily Revenue Trend</b>",
        template="plotly_white"
    )

    left, right = st.columns(2)
    left.plotly_chart(fig_product, use_container_width=True)
    right.plotly_chart(fig_daily, use_container_width=True)


if st.checkbox("Show Raw Data"):
    st.dataframe(df_selection)
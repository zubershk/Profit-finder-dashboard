# viz.py
from typing import Tuple, Optional
import pandas as pd
import plotly.express as px

def revenue_over_time(df: pd.DataFrame, date_col: str, revenue_col: str, freq: str = "W") -> px.line:
    """Aggregate revenue and return plotly figure. freq: 'D', 'W', 'M'"""
    agg = df.dropna(subset=[date_col, revenue_col]).copy()
    agg.set_index(date_col, inplace=True)
    grouped = agg[revenue_col].resample(freq).sum().reset_index()
    fig = px.line(grouped, x=date_col, y=revenue_col, title="Revenue over time", markers=True)
    fig.update_layout(hovermode="x unified")
    return fig

def profit_margin_over_time(df: pd.DataFrame, date_col: str) -> px.line:
    agg = df.dropna(subset=[date_col]).copy()
    agg.set_index(date_col, inplace=True)
    grouped = agg.resample("W").agg({"profit": "sum", "revenue__computed": "sum", "revenue": "sum"}).fillna(0)
    rev_sum = grouped.get("revenue", grouped.get("revenue__computed", None))
    margin = (grouped["profit"] / rev_sum).replace([float("inf"), -float("inf")], None)
    result = pd.DataFrame({ "date": grouped.index, "profit": grouped["profit"], "margin": margin })
    fig = px.line(result, x="date", y="margin", title="Profit margin over time", markers=True)
    fig.update_yaxes(tickformat=".0%")
    return fig

def top_products(df: pd.DataFrame, product_col: str, revenue_col: str, top_n: int = 10) -> px.bar:
    agg = df.groupby(product_col).agg({revenue_col: "sum", "profit": "sum"}).reset_index()
    agg = agg.sort_values(by=revenue_col, ascending=False).head(top_n)
    fig = px.bar(agg, x=product_col, y=revenue_col, hover_data=["profit"], title=f"Top {top_n} products by revenue")
    return fig

def category_pie(df: pd.DataFrame, category_col: str, revenue_col: str) -> px.pie:
    agg = df.groupby(category_col).agg({revenue_col: "sum"}).reset_index()
    fig = px.pie(agg, values=revenue_col, names=category_col, title="Revenue share by category")
    return fig

def sales_table(df: pd.DataFrame, n: int = 10) -> pd.DataFrame:
    # choose intelligent display columns
    display_candidates = ["_parsed_date", "date", "product", "category", "quantity", "revenue", "profit", "margin"]
    available = [c for c in display_candidates if c in df.columns]
    if not available:
        return df.head(n)
    return df[available].sort_values(by=available[0], ascending=False).head(n)

# app.py
import streamlit as st
from etl import read_uploaded_file, clean_dataframe, infer_schema
from viz import revenue_over_time, profit_margin_over_time, top_products, category_pie, sales_table
from utils import set_session_df, get_session_df, clear_session
import pandas as pd
import json
from io import BytesIO

st.set_page_config(page_title="Profit-Finder Dashboard", layout="wide", initial_sidebar_state="expanded")

st.title("Profit-Finder Dashboard")
st.markdown(
    "Upload your sales CSV or Excel and get instant, private insights. "
    "If auto-detection misses columns, use the Schema editor to map columns manually. "
    "Use Preview before applying changes."
)

# ---------- Sidebar: upload + global controls ----------
with st.sidebar:
    st.header("Upload & Controls")
    uploaded = st.file_uploader("Upload sales CSV or Excel (session-only)", type=["csv", "xlsx", "xls"], accept_multiple_files=False)
    st.markdown("Options")
    resample_choice = st.selectbox("Resample frequency for time series", options=["D", "W", "M"], index=1, help="D daily, W weekly, M monthly")
    top_n = st.number_input("Top products shown", min_value=3, max_value=50, value=10, step=1)
    if st.button("Clear session data"):
        clear_session()
        for k in ["_pf_raw_df", "_pf_inferred", "_pf_user_mapping", "_pf_applied_mapping"]:
            if k in st.session_state:
                del st.session_state[k]
        st.success("Session cleared")
        st.experimental_rerun()

# Load session df and schema if present
df, schema = get_session_df()

# ---------- Handle upload ----------
if uploaded is not None:
    try:
        raw_df = read_uploaded_file(uploaded)
        inferred = infer_schema(raw_df)
        # store raw/inferred for schema editor usage
        st.session_state["_pf_raw_df"] = raw_df
        st.session_state["_pf_inferred"] = inferred
        # perform a default clean with inferred mapping (non-strict)
        cleaned_df, auto_schema = clean_dataframe(raw_df, user_schema=None)
        set_session_df(cleaned_df, auto_schema)
        df, schema = get_session_df()
        st.success("File loaded and auto-processed. Use Schema editor below to adjust mappings.")
    except Exception as e:
        st.error(f"Failed to process file: {e}")
        st.stop()

# If nothing loaded, stop
if df is None:
    st.info("No data loaded yet. Upload a CSV or Excel file using the uploader in the sidebar.")
    st.stop()

# ---------- Schema editor + preview area ----------
with st.expander("Ingestion diagnostics & Schema editor", expanded=True):
    st.subheader("Auto-detected schema (suggestion)")
    inferred = st.session_state.get("_pf_inferred", {})
    st.json(inferred)
    st.markdown("If mapping looks wrong, change the mapping below, Preview, then Apply mapping. Use Revert to restore the auto-detected mapping.")

    raw_df = st.session_state.get("_pf_raw_df", df)
    columns = list(raw_df.columns)

    # canonical fields editable
    canonical_fields = ["date", "order_id", "product", "category", "quantity", "price", "cost", "revenue"]

    # Initialize stored user mapping in session state to persist choices across reruns
    if "_pf_user_mapping" not in st.session_state:
        default_map = {k: inferred.get(k) if inferred.get(k) else None for k in canonical_fields}
        st.session_state["_pf_user_mapping"] = default_map

    st.markdown("### Manual mapping (choose column or None)")
    cols = st.columns(2)
    for i, key in enumerate(canonical_fields):
        col = cols[i % 2]
        default = st.session_state["_pf_user_mapping"].get(key)
        options = ["None"] + columns
        default_choice = "None" if default is None else default
        sel = col.selectbox(f"{key}", options=options, index=options.index(default_choice) if default_choice in options else 0, key=f"map_{key}")
        st.session_state["_pf_user_mapping"][key] = None if sel == "None" else sel

    st.markdown("### Quick actions")
    quick_col1, quick_col2, quick_col3 = st.columns(3)
    with quick_col1:
        preview_btn = st.button("Preview mapping")
    with quick_col2:
        apply_btn = st.button("Apply mapping (overwrite session data)")
    with quick_col3:
        revert_btn = st.button("Revert to auto-detected schema")

    # One-click: re-apply auto-clean without manual mapping
    if st.button("Re-run auto-clean using inferred schema"):
        try:
            cleaned_df, auto_schema = clean_dataframe(raw_df, user_schema=None)
            set_session_df(cleaned_df, auto_schema)
            st.success("Auto-clean re-run complete.")
            st.experimental_rerun()
        except Exception as e:
            st.error(f"Auto-clean failed: {e}")

    # Mapping download
    mapping_json = json.dumps(st.session_state["_pf_user_mapping"], indent=2)
    b = BytesIO()
    b.write(mapping_json.encode("utf-8"))
    b.seek(0)
    st.download_button("Download mapping (JSON)", data=b, file_name="pf_mapping.json", mime="application/json")

    # Handle revert action
    if revert_btn:
        new_default = {k: inferred.get(k) if inferred.get(k) else None for k in canonical_fields}
        st.session_state["_pf_user_mapping"] = new_default
        try:
            cleaned_df, auto_schema = clean_dataframe(raw_df, user_schema=None)
            set_session_df(cleaned_df, auto_schema)
            st.success("Reverted to auto-detected mapping and reprocessed data.")
            st.experimental_rerun()
        except Exception as e:
            st.error(f"Revert action failed: {e}")

    # ---------- Preview logic (non-destructive) ----------
    if preview_btn:
        with st.spinner("Running preview..."):
            user_schema = st.session_state.get("_pf_user_mapping", {})
            try:
                preview_df, preview_schema = clean_dataframe(raw_df, user_schema=user_schema)
            except Exception as e:
                st.error(f"Preview failed: {e}")
                preview_df, preview_schema = None, None

            if preview_df is not None:
                st.markdown("#### Preview: sample rows with derived columns")
                sample_orig = raw_df.head(10).copy()
                sample_preview = preview_df.head(10).copy()

                orig_cols = list(sample_orig.columns)[:6]
                st.write("Original (first 6 columns for context)")
                st.dataframe(sample_orig[orig_cols])

                computed_cols = [c for c in ["revenue__computed", "cost__computed", "profit", "margin", "quantity__inferred"] if c in sample_preview.columns]
                show_cols = orig_cols + computed_cols
                for k, v in preview_schema.items():
                    if v in sample_preview.columns and v not in show_cols:
                        show_cols.append(v)

                st.write("Preview (cleaned + derived columns). This is non-destructive — data will not change until you Apply mapping.")
                st.dataframe(sample_preview[show_cols].head(10) if len(show_cols)>0 else sample_preview.head(10))

                total_rows_raw = len(raw_df)
                total_rows_preview = len(preview_df)
                dropped = total_rows_raw - total_rows_preview
                st.markdown("**Preview diagnostics**")
                st.write(f"Rows in uploaded file: {total_rows_raw:,}")
                st.write(f"Rows after applying mapping & cleaning: {total_rows_preview:,} (dropped {dropped:,})")

                null_stats = {}
                for k, col in preview_schema.items():
                    if col in preview_df.columns:
                        null_pct = preview_df[col].isna().mean()
                        null_stats[k] = f"{null_pct:.1%}"
                if null_stats:
                    st.write("Null rates (after clean) for mapped fields:")
                    st.json(null_stats)

                rev_col = preview_schema.get("revenue") or ("revenue__computed" if "revenue__computed" in preview_df.columns else None)
                kpi_cols = []
                if rev_col and rev_col in preview_df.columns:
                    kpi_cols.append(("Revenue (sum)", preview_df[rev_col].sum()))
                if "profit" in preview_df.columns:
                    kpi_cols.append(("Profit (sum)", preview_df["profit"].sum()))
                if "margin" in preview_df.columns:
                    mean_margin = preview_df["margin"].mean()
                    kpi_cols.append(("Avg margin", f"{(mean_margin * 100):.2f}%" if pd.notna(mean_margin) else "N/A"))
                if kpi_cols:
                    k1, k2, k3 = st.columns(3)
                    for i, (label, value) in enumerate(kpi_cols):
                        if i == 0:
                            k1.metric(label, f"{value:,.2f}" if isinstance(value, (int, float)) else value)
                        elif i == 1:
                            k2.metric(label, f"{value:,.2f}" if isinstance(value, (int, float)) else value)
                        elif i == 2:
                            k3.metric(label, value)

                st.success("Preview completed. If it looks correct, press 'Apply mapping' to overwrite session data.")
            else:
                st.error("Preview produced no rows. Check mapping choices.")

    # ---------- Apply mapping (destructive to session) ----------
    if apply_btn:
        with st.spinner("Applying mapping and reprocessing data..."):
            user_schema = st.session_state.get("_pf_user_mapping", {})
            try:
                cleaned_df, new_schema = clean_dataframe(raw_df, user_schema=user_schema)
                set_session_df(cleaned_df, new_schema)
                st.session_state["_pf_applied_mapping"] = user_schema
                st.success("Mapping applied and session data updated.")
                st.experimental_rerun()
            except Exception as e:
                st.error(f"Failed to apply mapping: {e}")

# ---------- Main dashboard (post-mapping) ----------
st.markdown("## Dashboard")

df, schema = get_session_df()

date_col = schema.get("date")
revenue_col = schema.get("revenue") or ("revenue__computed" if "revenue__computed" in df.columns else None)
product_col = schema.get("product", None)
category_col = schema.get("category", None)

if not date_col or date_col not in df.columns:
    st.warning("No parsed date column detected. Time series charts will be disabled until a date-like column exists in the mapping.")
if not revenue_col or revenue_col not in df.columns:
    st.warning("No revenue detected. Top-product and KPI charts may be limited unless you map revenue or price+quantity to compute revenue.")

colA, colB = st.columns([2, 1])

with colA:
    if date_col in df.columns and revenue_col in df.columns:
        try:
            fig_rev = revenue_over_time(df, date_col, revenue_col, freq=resample_choice)
            st.plotly_chart(fig_rev, use_container_width=True)
        except Exception as e:
            st.warning("Revenue time series not available: " + str(e))
    elif date_col in df.columns:
        st.info("Date parsed, but revenue column missing; map revenue or price+quantity to compute revenue.")

    if date_col in df.columns:
        try:
            fig_margin = profit_margin_over_time(df, date_col)
            st.plotly_chart(fig_margin, use_container_width=True)
        except Exception as e:
            st.warning("Could not compute profit margin over time: " + str(e))

    st.subheader("Sales sample (cleaned)")
    try:
        st.dataframe(sales_table(df, n=20))
    except Exception:
        st.dataframe(df.head(20))

with colB:
    if product_col and product_col in df.columns and revenue_col and revenue_col in df.columns:
        fig_top = top_products(df, product_col, revenue_col, top_n=top_n)
        st.plotly_chart(fig_top, use_container_width=True)
    if category_col and category_col in df.columns and revenue_col and revenue_col in df.columns:
        fig_cat = category_pie(df, category_col, revenue_col)
        st.plotly_chart(fig_cat, use_container_width=True)

# ---------- Drilldown filters ----------
st.sidebar.markdown("---")
st.sidebar.header("Drilldown")
if product_col and product_col in df.columns:
    unique_products = sorted(df[product_col].dropna().unique().tolist())[:1000]
    sel_product = st.sidebar.selectbox("Select product to filter", options=["All"] + unique_products)
else:
    sel_product = "All"

filtered = df.copy()
if sel_product != "All":
    filtered = filtered[filtered[product_col] == sel_product]

total_revenue = filtered[revenue_col].sum() if revenue_col in filtered.columns else 0.0
total_profit = filtered["profit"].sum() if "profit" in filtered.columns else 0.0
avg_margin = filtered["margin"].mean() if "margin" in filtered.columns else None

k1, k2, k3 = st.columns(3)
k1.metric("Revenue", f"{total_revenue:,.2f}")
k2.metric("Profit", f"{total_profit:,.2f}")
k3.metric("Avg margin", f"{(avg_margin * 100):.2f}%" if avg_margin is not None and pd.notna(avg_margin) else "N/A")

st.markdown("### Notes")
st.markdown(
    "- Preview runs a non-destructive cleanse using your mapping and displays computed columns and diagnostics.\n"
    "- Apply mapping updates the session data (this is reversible by re-running auto-clean or reverting to auto-detected schema).\n"
    "- Mapping JSON can be downloaded and re-uploaded later (manual re-use)."
)

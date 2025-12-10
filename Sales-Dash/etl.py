# etl.py
from typing import Tuple, Optional, Dict
import pandas as pd
import numpy as np
from dateutil import parser
import io
import logging

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# Canonical names and aliases
COL_ALIASES = {
    "order_id": ["order_id", "order", "id", "transaction_id", "txn_id"],
    "date": ["date", "order_date", "sale_date", "timestamp", "created_at"],
    "product": ["product", "product_name", "item", "sku", "title", "product_title"],
    "category": ["category", "product_category", "cat", "category_name"],
    "quantity": ["quantity", "qty", "units", "quantity_sold", "count"],
    "price": ["price", "unit_price", "selling_price", "price_per_unit"],
    "cost": ["cost", "unit_cost", "cost_price", "cogs"],
    "revenue": ["revenue", "total", "sale_amount", "amount", "subtotal"],
    "currency": ["currency", "curr"]
}

def _find_column(df_columns, candidates):
    cols = [c for c in df_columns]
    for cand in candidates:
        for c in cols:
            if c.lower().strip() == cand.lower().strip():
                return c
    # fuzzy fallback: contains
    for cand in candidates:
        for c in cols:
            if cand.lower() in c.lower():
                return c
    return None

def infer_schema(df: pd.DataFrame) -> dict:
    """Return mapping of canonical names to actual columns found in df."""
    found = {}
    cols = list(df.columns)
    for key, aliases in COL_ALIASES.items():
        matched = _find_column(cols, aliases)
        if matched:
            found[key] = matched
    return found

def parse_date_series(s: pd.Series) -> pd.Series:
    """Robust date parsing: tries pandas then dateutil as fallback."""
    s_parsed = pd.to_datetime(s, errors="coerce", infer_datetime_format=True)
    # if more than 10% parsed OK, keep; otherwise element-wise fallback
    if s_parsed.notna().sum() / max(1, len(s_parsed)) > 0.1:
        return s_parsed
    # element-wise fallback
    def _try_parse(x):
        if pd.isna(x):
            return pd.NaT
        try:
            return parser.parse(str(x), dayfirst=False)
        except Exception:
            try:
                return parser.parse(str(x), dayfirst=True)
            except Exception:
                return pd.NaT
    return s.map(_try_parse)

def coerce_numeric(s: pd.Series) -> pd.Series:
    """Strip currency symbols, commas and coerce to float."""
    if pd.api.types.is_numeric_dtype(s):
        return pd.to_numeric(s, errors="coerce")
    s2 = s.astype(str).str.replace(r"[^\d\.\-eE]", "", regex=True)
    return pd.to_numeric(s2, errors="coerce")

def compute_derived(df: pd.DataFrame, schema: dict) -> pd.DataFrame:
    """Create revenue, cost_total, profit, margin, units if possible."""
    # Defensive copy
    df = df.copy()

    # Ensure numeric coercion where columns exist
    for key in ["quantity", "price", "revenue", "cost"]:
        if key in schema and schema[key] in df.columns:
            df[schema[key]] = coerce_numeric(df[schema[key]])

    # If revenue missing but price and quantity present -> compute revenue
    if "revenue" not in schema or schema.get("revenue") not in df.columns:
        if "price" in schema and "quantity" in schema and schema["price"] in df.columns and schema["quantity"] in df.columns:
            try:
                df["revenue__computed"] = df[schema["price"]].astype(float) * df[schema["quantity"]].astype(float)
                schema["revenue"] = "revenue__computed"
            except Exception:
                pass

    # If cost is per-unit and quantity present, compute total cost
    if "cost" in schema and schema["cost"] in df.columns and "quantity" in schema and schema["quantity"] in df.columns:
        try:
            df["cost__computed"] = df[schema["cost"]].astype(float) * df[schema["quantity"]].astype(float)
            schema["cost_total"] = "cost__computed"
        except Exception:
            pass

    # Normalize column names used internally
    rev_col = schema.get("revenue")
    cost_col = schema.get("cost_total") or schema.get("cost")
    # coerce
    if rev_col and rev_col in df.columns:
        df[rev_col] = coerce_numeric(df[rev_col])
    if cost_col and cost_col in df.columns:
        df[cost_col] = coerce_numeric(df[cost_col])

    # Profit and margin
    if rev_col in df.columns and cost_col in df.columns:
        df["profit"] = df[rev_col].fillna(0) - df[cost_col].fillna(0)
        # margin safe compute
        def safe_margin(row):
            rev = row.get(rev_col, None)
            if rev in (None, 0, np.nan):
                return np.nan
            return row.get("profit", np.nan) / rev
        df["margin"] = df.apply(safe_margin, axis=1)
    else:
        df["profit"] = np.nan
        df["margin"] = np.nan

    # If quantity missing but revenue present and price present, try infer quantity = revenue / price
    if ("quantity" not in schema or schema.get("quantity") not in df.columns) and "price" in schema and schema["price"] in df.columns and (schema.get("revenue") in df.columns):
        try:
            df["quantity__inferred"] = (df[schema["revenue"]] / df[schema["price"]]).round().fillna(0)
            schema["quantity"] = "quantity__inferred"
        except Exception:
            pass

    return df

def clean_dataframe(df: pd.DataFrame, user_schema: Optional[Dict[str, Optional[str]]] = None) -> Tuple[pd.DataFrame, dict]:
    """
    Clean dataframe and return (df, schema).
    If user_schema is provided, it overrides auto-detection mappings.
    user_schema should be a dict mapping canonical names to column names (or None).
    """
    df = df.copy()
    df.columns = [c.strip() if isinstance(c, str) else c for c in df.columns]
    df.replace({"": pd.NA, "NA": pd.NA, "N/A": pd.NA}, inplace=True)

    inferred = infer_schema(df)
    # Start schema from inferred, then override with user_schema where provided
    schema = inferred.copy()
    if user_schema:
        for k, v in user_schema.items():
            if v is None or v == "None":
                if k in schema:
                    schema.pop(k, None)
            else:
                if v in df.columns:
                    schema[k] = v
                else:
                    logger.warning("User-provided mapping for %s -> %s not found in columns", k, v)

    # Parse date if present in schema
    if "date" in schema and schema["date"] in df.columns:
        try:
            df["_parsed_date"] = parse_date_series(df[schema["date"]])
            df["_parsed_date"] = pd.to_datetime(df["_parsed_date"], errors="coerce")
            schema["date"] = "_parsed_date"
        except Exception as e:
            logger.exception("Date parsing failed: %s", e)

    # Trim string columns like product, category, order_id
    for key in ["product", "category", "order_id"]:
        if key in schema and schema[key] in df.columns:
            df[schema[key]] = df[schema[key]].astype(str).fillna("Unknown").str.strip()

    # Fill quantity default if present but null
    if "quantity" in schema and schema["quantity"] in df.columns:
        try:
            df[schema["quantity"]] = coerce_numeric(df[schema["quantity"]])
            df[schema["quantity"]] = df[schema["quantity"]].fillna(1)
        except Exception:
            df[schema["quantity"]] = df[schema["quantity"]].fillna(1)

    # Compute derived fields (revenue, cost_total, profit, margin)
    df = compute_derived(df, schema)

    # Final: drop rows that have no date and no revenue and no product (keep rows with at least one of them)
    has_any = pd.Series(False, index=df.index)
    if "date" in schema and schema["date"] in df.columns:
        has_any |= df[schema["date"]].notna()
    if "revenue" in schema and schema["revenue"] in df.columns:
        has_any |= df[schema["revenue"]].notna()
    if "product" in schema and schema["product"] in df.columns:
        has_any |= df[schema["product"]].notna()
    df = df[has_any]

    df.reset_index(drop=True, inplace=True)
    return df, schema

def read_uploaded_file(uploaded_file) -> pd.DataFrame:
    """Accepts Streamlit UploadedFile or file-like object, reads into DataFrame."""
    try:
        uploaded_file.seek(0)
    except Exception:
        pass

    content = uploaded_file.read()
    # if BytesIO, decode safely
    if isinstance(content, bytes):
        # basic check for xlsx zip header PK
        header = content[:8]
        if header.startswith(b'PK'):
            try:
                return pd.read_excel(io.BytesIO(content))
            except Exception:
                try:
                    return pd.read_csv(io.StringIO(content.decode('utf-8', errors='replace')), engine='python')
                except Exception as e:
                    raise e
        content = content.decode('utf-8', errors='replace')

    sample = content[:10000]
    delimiter = ','
    if '\t' in sample and sample.count('\t') > sample.count(','):
        delimiter = '\t'
    try:
        df = pd.read_csv(io.StringIO(content), sep=delimiter, engine='python')
    except Exception:
        try:
            df = pd.read_csv(io.StringIO(content), engine='python')
        except Exception as e:
            logger.exception("CSV read failed: %s", e)
            raise e
    return df

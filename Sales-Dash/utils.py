# utils.py
import streamlit as st
import pandas as pd

SESSION_KEY_DF = "pf_df"
SESSION_KEY_SCHEMA = "pf_schema"

def set_session_df(df: pd.DataFrame, schema: dict):
    """
    Store cleaned DataFrame and schema mapping in session state.
    Keys:
      - SESSION_KEY_DF -> DataFrame
      - SESSION_KEY_SCHEMA -> dict mapping canonical -> column
    """
    st.session_state[SESSION_KEY_DF] = df
    st.session_state[SESSION_KEY_SCHEMA] = schema

def get_session_df():
    """
    Return tuple (df, schema). If not present, returns (None, None).
    Use this to read the current in-session dataset and schema.
    """
    return st.session_state.get(SESSION_KEY_DF, None), st.session_state.get(SESSION_KEY_SCHEMA, None)

def clear_session():
    """
    Remove stored DataFrame and schema from session state.
    Use when user clicks 'Clear session data' in the sidebar.
    """
    for k in [SESSION_KEY_DF, SESSION_KEY_SCHEMA]:
        if k in st.session_state:
            del st.session_state[k]

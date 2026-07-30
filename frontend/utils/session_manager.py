import streamlit as st


def initialize_session():

    if "messages" not in st.session_state:
        st.session_state.messages = []

    if "pdf_uploaded" not in st.session_state:
        st.session_state.pdf_uploaded = False
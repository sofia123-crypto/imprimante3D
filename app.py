import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, time
import os
import hashlib
import firebase_admin
from firebase_admin import credentials, firestore
import io
import random

# === CONFIGURATION FIREBASE ===
if not firebase_admin._apps:
    firebase_json = {
        "type": st.secrets["FIREBASE_TYPE"],
        "project_id": st.secrets["FIREBASE_PROJECT_ID"],
        "private_key_id": st.secrets["FIREBASE_PRIVATE_KEY_ID"],
        "private_key": st.secrets["FIREBASE_PRIVATE_KEY"].replace("\\n", "\n"),
        "client_email": st.secrets["FIREBASE_CLIENT_EMAIL"],
        "client_id": st.secrets["FIREBASE_CLIENT_ID"],
        "auth_uri": st.secrets["FIREBASE_AUTH_URI"],
        "token_uri": st.secrets["FIREBASE_TOKEN_URI"],
        "auth_provider_x509_cert_url": st.secrets["FIREBASE_AUTH_PROVIDER_CERT_URL"],
        "client_x509_cert_url": st.secrets["FIREBASE_CLIENT_CERT_URL"],
        "universe_domain": st.secrets["FIREBASE_UNIVERSE_DOMAIN"]
    }
    cred = credentials.Certificate(firebase_json)
    firebase_admin.initialize_app(cred)

db = firestore.client()

# === CONSTANTES ===
PRINTERS_A = [f"A{i+1}" for i in range(10)]
PRINTERS_B = [f"B{i+1}" for i in range(6)]
ALL_PRINTERS = PRINTERS_A + PRINTERS_B

# === 🔁 Exporter toutes les impressions depuis Firestore ===
def export_all_data_from_firestore():
    all_docs = db.collection("plannings").stream()
    all_data = []
    for doc in all_docs:
        date = doc.id
        impressions = doc.to_dict().get("impressions", [])
        for imp in impressions:
            imp["Date"] = date
            all_data.append(imp)
    df = pd.DataFrame(all_data)
    if not df.empty:
        df["Start"] = pd.to_datetime(df["Start"], errors="coerce")
        df["Duration"] = pd.to_numeric(df["Duration"], errors="coerce")
        df = df.dropna(subset=["Start", "Duration", "Printer"])
        df = df["Start"].between(df["Start"].min(), df["Start"].max())  # sanity check
        df = pd.DataFrame(all_data)
        df["Start"] = pd.to_datetime(df["Start"], errors="coerce")
        df["Duration"] = pd.to_numeric(df["Duration"], errors="coerce")
        df = df.dropna(subset=["Start", "Duration", "Printer"])
        df = df[["Date", "Start", "Duration", "Printer", "Ticket", "Color"]]
    return df

# === SESSION STATE ===
if "date" not in st.session_state:
    st.session_state.date = datetime.today().date()

# === SELECTEUR DE PÉRIODE POUR EXPORT CSV ===
st.subheader("🗖️ Exporter un bilan sur une période")

col1, col2 = st.columns(2)
with col1:
    start_date = st.date_input("Date de début", value=st.session_state.date.replace(day=1))
with col2:
    end_date = st.date_input("Date de fin", value=st.session_state.date)

if start_date > end_date:
    st.error("⛔ La date de début ne peut pas être après la date de fin.")
else:
    full_df = export_all_data_from_firestore()
    full_df["Start"] = pd.to_datetime(full_df["Start"], errors="coerce")
    full_df = full_df.dropna(subset=["Start", "Duration", "Printer"])

    mask = (full_df["Start"] >= pd.to_datetime(start_date)) & (full_df["Start"] <= pd.to_datetime(end_date) + timedelta(days=1))
    filtered_df = full_df[mask]

    if not filtered_df.empty:
        usage_summary = (
            filtered_df[filtered_df["Ticket"].notna()]
            .groupby("Printer")["Duration"]
            .sum()
            .fillna(0)
            .astype(int)
            .reset_index()
            .rename(columns={"Duration": "Durée (min)"})
        )

        csv_buffer = io.StringIO()
        usage_summary.to_csv(csv_buffer, index=False)

        st.download_button(
            label="💾 Télécharger le bilan pour cette période",
            data=csv_buffer.getvalue(),
            file_name=f"bilan_imprimantes_{start_date}_au_{end_date}.csv",
            mime="text/csv"
        )
    else:
        st.info("📅 Aucune donnée disponible pour la période choisie.")

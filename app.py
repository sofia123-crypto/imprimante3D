import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, time
import os
import hashlib
import firebase_admin
from firebase_admin import credentials, firestore
import json

# --- 🔐 CONFIGURATION FIREBASE À PARTIR DE SECRETS STREAMLIT ---
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

# --- CONSTANTES ---
PRINTERS_A = [f"A{i+1}" for i in range(10)]
PRINTERS_B = [f"B{i+1}" for i in range(6)]
ALL_PRINTERS = PRINTERS_A + PRINTERS_B
DATA_FOLDER = "data"

if not os.path.exists(DATA_FOLDER):
    os.makedirs(DATA_FOLDER)

# --- SESSION STATE ---
if "date" not in st.session_state:
    st.session_state.date = datetime.today().date()

# --- Fonctions fichiers ---
def date_to_filename(date):
    return os.path.join(DATA_FOLDER, f"planning_{date}.csv")

def load_planning(date):
    db = firestore.client()
    date_str = date.strftime("%Y-%m-%d")
    docs = db.collection("plannings").document(date_str).get()

    if docs.exists:
        data = docs.to_dict().get("impressions", [])
        df = pd.DataFrame(data)
        # Forcer les colonnes attendues même si elles sont absentes
        for col in ["Start", "Duration", "Printer", "Ticket", "Color"]:
            if col not in df.columns:
                df[col] = pd.NA
        return df
    else:
        # Renvoyer un DataFrame vide avec les bonnes colonnes
        return pd.DataFrame(columns=["Start", "Duration", "Printer", "Ticket", "Color"])



def save_planning(df, date):
    doc_ref = db.collection("plannings").document(str(date))
    df_copy = df.copy()
    df_copy["Start"] = df_copy["Start"].astype(str)
    # 🔧 CORRIGÉ ICI : on enregistre dans le champ "impressions" comme le chargement s'y attend
    doc_ref.set({"impressions": df_copy.to_dict(orient="records")})


def get_planning_with_previous_day(date):
    today_df = load_planning(date)
    previous_df = load_planning(date - timedelta(days=1))

    extended = []
    for _, row in previous_df.iterrows():
        start = row["Start"]
        end = start + timedelta(minutes=row["Duration"])
        if start.date() < date and end.date() >= date:
            adjusted_row = row.copy()
            adjusted_row["Start"] = datetime.combine(date, time(0, 0))
            adjusted_row["Duration"] = int((end - adjusted_row["Start"]).total_seconds() / 60)
            extended.append(adjusted_row)

    return pd.concat([today_df] + [pd.DataFrame(extended)], ignore_index=True)

# --- Autres fonctions ---
def validate_inputs(printer, start_time, ticket, duration):
    errors = []
    if printer not in ALL_PRINTERS:
        errors.append("Imprimante invalide.")
    if not (time(8,0) <= start_time <= time(17,0)):
        errors.append("L'heure de départ doit être entre 08:00 et 17:00.")
    if not ticket:
        errors.append("Le numéro du ticket est requis.")
    if duration <= 0 or duration > 24*60:
        errors.append("Durée invalide.")
    return errors

def generate_color(ticket):
    h = hashlib.md5(ticket.encode()).hexdigest()
    return "#" + h[:6]

def remove_entry(df, index):
    return df.drop(index).reset_index(drop=True)

def plot_gantt(df):
    import plotly.express as px
    from pandas import Timestamp

    if df.empty or not {"Start", "Duration", "Printer", "Ticket", "Color"}.issubset(df.columns):
        st.warning("⚠️ Impossible d'afficher le planning : données manquantes ou vides.")
        return

    df = df.copy()
    df["End"] = df["Start"] + pd.to_timedelta(df["Duration"], unit='m')

    all_printers_df = pd.DataFrame({"Printer": ALL_PRINTERS})
    df = pd.merge(all_printers_df, df, on="Printer", how="left")

    df["Start"] = df["Start"].fillna(Timestamp(st.session_state.date))
    df["End"] = df["End"].fillna(Timestamp(st.session_state.date))
    df["Ticket"] = df["Ticket"].fillna("Libre")
    df["Color"] = df["Color"].fillna("#e0e0e0")

    fig = px.timeline(
        df,
        x_start="Start",
        x_end="End",
        y="Printer",
        color="Ticket",
        color_discrete_sequence=df["Color"].tolist(),
        labels={"Printer": "Imprimantes", "Start": "Heure", "End": "Fin"},
    )

    fig.update_yaxes(categoryorder='array', categoryarray=ALL_PRINTERS[::-1])
    fig.update_layout(
        xaxis=dict(
            tickformat="%H:%M",
            range=[
                datetime.combine(st.session_state.date, time(0, 0)),
                datetime.combine(st.session_state.date + timedelta(days=1), time(0, 0))
            ],
            dtick=3600 * 1000,
            title="Heure"
        ),
        height=600,
        title=f"🕒 Planning du {st.session_state.date.strftime('%d/%m/%Y')}"
    )

    st.plotly_chart(fig, use_container_width=True)

# --- INTERFACE ---
st.set_page_config(page_title="📅 Planning Impression 3D", layout="wide")
st.title("📅 Planning Impression 3D - Atelier")

col1, col2, col3 = st.columns([1,3,1])
with col1:
    if st.button("⬅️ Jour précédent"):
        st.session_state.date -= timedelta(days=1)
with col3:
    if st.button("Jour suivant ➡️"):
        st.session_state.date += timedelta(days=1)
with col2:
    new_date = st.date_input("📆 Date", st.session_state.date)
    if new_date != st.session_state.date:
        st.session_state.date = new_date

with st.form("form_add"):
    st.subheader("➕ Ajouter une impression")
    colA, colB = st.columns(2)
    with colA:
        type_printer = st.selectbox("Type d’imprimante", ["A", "B"])
        printer_num = st.number_input("Numéro imprimante", min_value=1, max_value=10 if type_printer=="A" else 6, step=1)
        printer = f"{type_printer}{printer_num}"
    with colB:
        start_time = st.time_input("Heure de départ (08:00 - 17:00)", time(8,0))
        duration = st.number_input("Durée (minutes)", min_value=1, max_value=24*60, value=60)
        ticket = st.text_input("Numéro du ticket")
    add_btn = st.form_submit_button("Ajouter")

    if add_btn:
        errors = validate_inputs(printer, start_time, ticket, duration)
        if errors:
            for e in errors:
                st.error(e)
        else:
            start_dt = datetime.combine(st.session_state.date, start_time)
            end_dt = start_dt + timedelta(minutes=duration)

            current_df = load_planning(st.session_state.date)
            conflit = False
            for _, row in current_df.iterrows():
                if row["Printer"] != printer:
                    continue
                existing_start = row["Start"]
                existing_end = existing_start + timedelta(minutes=row["Duration"])
                if not (end_dt <= existing_start or start_dt >= existing_end):
                    conflit = True
                    break

            if conflit:
                st.error("❌ Conflit avec un créneau existant sur cette imprimante.")
            else:
                color = generate_color(ticket)
                new_line = {
                    "Printer": printer,
                    "Start": start_dt,
                    "Duration": duration,
                    "Ticket": ticket,
                    "Color": color
                }
                updated_df = pd.concat([current_df, pd.DataFrame([new_line])], ignore_index=True)
                save_planning(updated_df, st.session_state.date)
                st.success("✅ Impression ajoutée avec succès.")

                if end_dt.date() > st.session_state.date:
                    st.info("ℹ️ L'impression dépassera minuit et continuera le jour suivant.")

st.subheader("📋 Planning du jour")

full_df = get_planning_with_previous_day(st.session_state.date)

# ✅ Affiche message si aucune tâche, mais continue l'affichage du planning
if full_df["Ticket"].isna().all():
    st.info("Aucune impression planifiée pour cette date.")

# 🧪 Affichage debug même si les colonnes sont incorrectes
st.write("🧪 DEBUG planning : colonnes actuelles")
st.write(full_df.columns.tolist())
st.write(full_df.head())

# ✅ Affiche Gantt si les bonnes colonnes sont là
required_columns = {"Start", "End", "Printer", "Ticket"}
if required_columns.issubset(full_df.columns):
    # 🗑️ Annulation d'une impression
    to_delete = st.selectbox(
        "🗑️ Sélectionner une impression à annuler (par ticket)",
        options=full_df["Ticket"].unique()
    )
    if st.button("Annuler l’impression sélectionnée"):
        current_df = load_planning(st.session_state.date)
        idx = current_df[current_df["Ticket"] == to_delete].index
        if not idx.empty:
            current_df = remove_entry(current_df, idx[0])
            save_planning(current_df, st.session_state.date)
            st.success(f"❌ Impression '{to_delete}' annulée. veuillez rafraîchir la page!")
        else:
            st.warning("Ce ticket vient peut-être de la veille : modifiez le jour pour le supprimer.")

    # 📊 Affichage du diagramme de Gantt
    plot_gantt(full_df)
else:
    st.warning("⚠️ Impossible d'afficher le planning : colonnes manquantes.")


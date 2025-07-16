import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, time
import os
import hashlib

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

# Charger planning depuis fichier à chaque chargement
def date_to_filename(date):
    return os.path.join(DATA_FOLDER, f"planning_{date}.csv")

def load_planning(date):
    file = date_to_filename(date)
    if os.path.exists(file):
        df = pd.read_csv(file, parse_dates=["Start"])
        return df
    else:
        return pd.DataFrame(columns=["Printer", "Start", "Duration", "Ticket", "Color"])

def save_planning(df, date):
    file = date_to_filename(date)
    df.to_csv(file, index=False)

# Charger la dernière version du fichier CSV à chaque interaction
st.session_state.planning = load_planning(st.session_state.date)

# --- FONCTIONS UTILES ---
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

def plot_gantt(df):
    import plotly.express as px
    from pandas import Timestamp

    df = df.copy()
    df["End"] = df["Start"] + pd.to_timedelta(df["Duration"], unit='m')

    # Ajouter imprimantes manquantes pour affichage
    all_printers_df = pd.DataFrame({"Printer": ALL_PRINTERS})
    df = pd.merge(all_printers_df, df, on="Printer", how="left")

    df["Start"] = df["Start"].fillna(Timestamp(st.session_state.date))
    df["End"] = df["End"].fillna(Timestamp(st.session_state.date))
    df["Ticket"] = df["Ticket"].fillna("Libre")
    df["Color"] = df["Color"].fillna("#e0e0e0")  # gris clair

    fig = px.timeline(
        df,
        x_start="Start",
        x_end="End",
        y="Printer",
        color="Ticket",
        color_discrete_sequence=df["Color"].tolist(),
        labels={"Printer": "Imprimantes", "Start": "Heure", "End": "Fin"},
    )

    # Ordre d’affichage des imprimantes
    fig.update_yaxes(categoryorder='array', categoryarray=ALL_PRINTERS[::-1])

    # Afficher toute la journée : de 00:00 à 23:59 (ou plus si dépassement)
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

def remove_entry(df, index):
    return df.drop(index).reset_index(drop=True)

# --- INTERFACE ---
st.title("📅 Planning Impression 3D - Atelier")

# Navigation jour
col1, col2, col3 = st.columns([1,3,1])
with col1:
    if st.button("⬅️ Jour précédent"):
        st.session_state.date -= timedelta(days=1)
        st.session_state.planning = load_planning(st.session_state.date)
with col3:
    if st.button("Jour suivant ➡️"):
        st.session_state.date += timedelta(days=1)
        st.session_state.planning = load_planning(st.session_state.date)
with col2:
    new_date = st.date_input("📆 Date", st.session_state.date)
    if new_date != st.session_state.date:
        st.session_state.date = new_date
        st.session_state.planning = load_planning(st.session_state.date)

# Formulaire d'ajout
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
            # Vérifier conflits
            conflit = False
            for idx, row in st.session_state.planning.iterrows():
                if row["Printer"] != printer:
                    continue
                existing_start = row["Start"]
                existing_end = existing_start + timedelta(minutes=row["Duration"])
                new_end = start_dt + timedelta(minutes=duration)
                if not (new_end <= existing_start or start_dt >= existing_end):
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
                st.session_state.planning = pd.concat([st.session_state.planning, pd.DataFrame([new_line])], ignore_index=True)
                save_planning(st.session_state.planning, st.session_state.date)
                st.success("✅ Impression ajoutée avec succès.")
end_dt = start_dt + timedelta(minutes=duration)
if end_dt.date() > st.session_state.date:
    st.info("ℹ️ L'impression dépassera minuit et sera visible sur deux journées.")

# Affichage planning actuel
st.subheader("📋 Planning du jour")

if st.session_state.planning.empty:
    st.info("Aucune impression enregistrée pour ce jour.")
else:
    to_delete = st.selectbox("🗑️ Sélectionner une impression à annuler (par ticket)", options=st.session_state.planning["Ticket"].tolist())
    if st.button("Annuler l’impression sélectionnée"):
        idx = st.session_state.planning[st.session_state.planning["Ticket"] == to_delete].index[0]
        st.session_state.planning = remove_entry(st.session_state.planning, idx)
        save_planning(st.session_state.planning, st.session_state.date)
        st.success(f"❌ Impression '{to_delete}' annulée avec succès.")

# Affichage diagramme de Gantt
plot_gantt(st.session_state.planning)

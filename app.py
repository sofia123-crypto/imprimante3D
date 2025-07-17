import streamlit as st
import pandas as pd
import plotly.express as px
import os
from datetime import datetime, timedelta, time

st.set_page_config(page_title="📅 Planning des Impressions 3D", layout="wide")
st.title("📊 Planning actuel")
st.markdown("### Planning des impressions 3D")

# === Données simulées ou chargées ===
# Le CSV utilisé pour stocker les tâches
csv_path = "planning.csv"

# Imprimantes à toujours afficher
imprimantes_A = [f"A{i}" for i in range(1, 11)]
imprimantes_B = [f"B{i}" for i in range(1, 7)]
all_imprimantes = imprimantes_A + imprimantes_B

# === Chargement du planning actuel ===
if os.path.exists(csv_path):
    full_df = pd.read_csv(csv_path)
    full_df["Start"] = pd.to_datetime(full_df["Start"])
else:
    full_df = pd.DataFrame(columns=["Ticket", "Start", "Duration", "Imprimante"])

# Calcul de la colonne "End" et nettoyage
if not full_df.empty:
    full_df = full_df.dropna(subset=["Start", "Duration"])
    full_df["Duration"] = pd.to_numeric(full_df["Duration"], errors="coerce")
    full_df["End"] = full_df["Start"] + pd.to_timedelta(full_df["Duration"], unit="m")
    full_df["Imprimante"] = full_df["Imprimante"].astype(str)
    full_df["Ticket"] = full_df["Ticket"].astype(str)

# === Option pour afficher/masquer les imprimantes sans tâche ===
afficher_vides = st.checkbox("Afficher les imprimantes libres", value=True)

# Ajout des imprimantes vides si demandé
if afficher_vides:
    used = set(full_df["Imprimante"].unique())
    unused = set(all_imprimantes) - used
    lignes_vides = pd.DataFrame({
        "Ticket": ["Libre"] * len(unused),
        "Start": [datetime.now()] * len(unused),
        "End": [datetime.now()] * len(unused),
        "Imprimante": list(unused)
    })
    full_df = pd.concat([full_df, lignes_vides], ignore_index=True)

# === Gantt Chart ===
if not full_df.empty:
    fig = px.timeline(
        full_df,
        x_start="Start",
        x_end="End",
        y="Imprimante",
        color="Ticket",
        color_discrete_sequence=px.colors.qualitative.Vivid,
        title="Planification des impressions"
    )
    fig.update_yaxes(categoryorder="category ascending")
    fig.update_layout(
        height=600,
        margin=dict(l=20, r=20, t=30, b=20),
        xaxis_title="Heure",
        yaxis_title="Imprimante"
    )
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("Aucune tâche planifiée pour l'instant.")

# === Ajout d'une nouvelle tâche ===
st.markdown("---")
st.header("➕ Ajouter une tâche")

# Choix du type d'imprimante et numéro
col1, col2 = st.columns(2)
with col1:
    type_imprimante = st.selectbox("Type d'imprimante", ["A", "B"])
with col2:
    if type_imprimante == "A":
        numero = st.selectbox("Numéro d'imprimante", list(range(1, 11)))
    else:
        numero = st.selectbox("Numéro d'imprimante", list(range(1, 7)))

imprimante_choisie = f"{type_imprimante}{numero}"
ticket = st.text_input("Numéro du ticket")
duree = st.number_input("Durée (minutes)", min_value=1, max_value=480, value=30)

# Limiter choix d'heure de début entre 8h et 17h
horaires_autorises = [time(h, 0) for h in range(8, 18)]
heure_debut = st.selectbox("Heure de début", horaires_autorises)
date_debut = st.date_input("Date de début", value=datetime.today())

if st.button("Ajouter au planning"):
    dt_start = datetime.combine(date_debut, heure_debut)
    nouvelle_ligne = pd.DataFrame.from_dict({
        "Ticket": [ticket],
        "Start": [dt_start],
        "Duration": [duree],
        "Imprimante": [imprimante_choisie]
    })
    full_df = pd.concat([full_df, nouvelle_ligne], ignore_index=True)
    full_df.drop_duplicates(inplace=True)
    full_df.to_csv(csv_path, index=False)
    st.success(f"Tâche {ticket} ajoutée à {imprimante_choisie}.")
    st.experimental_rerun()

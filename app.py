import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta

st.set_page_config(page_title="📅 Planning des Imprimantes 3D", layout="wide")
st.title("🖨️ Gestion des Imprimantes 3D")

# === Paramètres ===
heures_jour = [f"{h:02d}:00" for h in range(8, 18)]  # De 08:00 à 17:00 uniquement
imprimantes_A = [f"A{i}" for i in range(1, 11)]
imprimantes_B = [f"B{i}" for i in range(1, 7)]
toutes_imprimantes = imprimantes_A + imprimantes_B

# === Initialisation session state ===
if "df" not in st.session_state:
    st.session_state.df = pd.DataFrame(columns=["Printer", "Start", "Duration", "End", "Task"])

# === Barre latérale : Ajout de tâche ===
st.sidebar.header("➕ Ajouter une tâche")

printer = st.sidebar.selectbox("Choisir une imprimante", toutes_imprimantes)
date = st.sidebar.date_input("Date de début", datetime.now().date())
heure = st.sidebar.selectbox("Heure de début", heures_jour)
duration = st.sidebar.number_input("Durée (min)", min_value=15, max_value=480, step=15)
task = st.sidebar.text_input("Nom de la tâche")

if st.sidebar.button("Ajouter au planning"):
    start = datetime.strptime(f"{date} {heure}", "%Y-%m-%d %H:%M")
    end = start + timedelta(minutes=duration)
    new_row = pd.DataFrame({
        "Printer": [printer],
        "Start": [start],
        "Duration": [duration],
        "End": [end],
        "Task": [task or "Tâche sans nom"]
    })
    st.session_state.df = pd.concat([st.session_state.df, new_row], ignore_index=True)
    st.success("✅ Tâche ajoutée au planning !")

# === Option : Afficher ou masquer imprimantes sans tâche ===
show_empty = st.checkbox("Afficher les imprimantes sans tâche", value=True)

# === Construction du DataFrame final ===
full_df = st.session_state.df.copy()

# Forcer typage propre pour éviter erreurs
full_df["Start"] = pd.to_datetime(full_df["Start"], errors="coerce")
full_df["Duration"] = pd.to_numeric(full_df["Duration"], errors="coerce")
mask = full_df["Start"].notna() & full_df["Duration"].notna()
full_df.loc[mask, "End"] = full_df.loc[mask, "Start"] + pd.to_timedelta(full_df.loc[mask, "Duration"], unit="m")

# Ajouter imprimantes vides si demandé
if show_empty:
    df_imprimantes = pd.DataFrame({"Printer": toutes_imprimantes})
    full_df = pd.merge(df_imprimantes, full_df, on="Printer", how="left")

# === Diagramme de Gantt ===
st.subheader("📊 Planning actuel")

if not full_df.empty and full_df["Start"].notna().any():
    color_discrete_sequence = px.colors.qualitative.Vivid  # Couleurs plus vives
    fig = px.timeline(
        full_df,
        x_start="Start",
        x_end="End",
        y="Printer",
        color="Task",
        title="Planning des impressions 3D",
        color_discrete_sequence=color_discrete_sequence
    )
    fig.update_yaxes(autorange="reversed")
    fig.update_layout(
        height=600,
        margin=dict(l=20, r=20, t=40, b=20),
        xaxis_title="Temps",
        yaxis_title="Imprimante"
    )
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("Aucune tâche planifiée pour le moment.")

# === Pied de page ===
st.markdown("""
---
👨‍🔧 *Développé pour la gestion interne des imprimantes 3D. Dernière mise à jour : juillet 2025.*
""")

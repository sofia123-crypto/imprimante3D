import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
import random
import os

# ---------- CONFIGURATION ----------
IMPRIMANTES_A = ['A' + str(i) for i in range(1, 11)]
IMPRIMANTES_B = ['B' + str(i) for i in range(1, 7)]
HEURE_MIN = 8 * 60   # 8h00 en minutes
HEURE_MAX = 17 * 60  # 17h00 en minutes

# ---------- INITIALISATION SESSION ----------
if 'date' not in st.session_state:
    st.session_state.date = datetime.today().date()
if 'planning' not in st.session_state:
    st.session_state.planning = pd.DataFrame(columns=['date', 'imprimante', 'ticket', 'debut', 'fin', 'couleur', 'type'])

# ---------- CHARGER / SAUVER CSV ----------
def charger_planning():
    if os.path.exists('planning.csv'):
        return pd.read_csv('planning.csv', parse_dates=['date'])
    return pd.DataFrame(columns=['date', 'imprimante', 'ticket', 'debut', 'fin', 'couleur', 'type'])

def sauvegarder_planning(df):
    df.to_csv('planning.csv', index=False)

# ---------- AJOUTER UN TICKET ----------
def ajouter_ticket(ticket, heure_depart, duree, type_poste):
    # Vérification des horaires
    if heure_depart < HEURE_MIN or heure_depart > HEURE_MAX:
        st.error("L'heure de départ doit être entre 08:00 et 17:00 !")
        return

    imprimantes = IMPRIMANTES_A if type_poste == 'A' else IMPRIMANTES_B
    planning = charger_planning()
    
    dispo = None
    for imp in imprimantes:
        # Vérifier si l'imprimante est libre sur toute la durée (y compris chevauchements inter-jours)
        en_conflit = planning[
            (planning['imprimante'] == imp) &
            (planning['date'] == st.session_state.date) &
            (
                ((planning['debut'] <= heure_depart) & (planning['fin'] > heure_depart)) |
                ((planning['debut'] < heure_depart + duree) & (planning['fin'] >= heure_depart + duree)) |
                ((planning['debut'] >= heure_depart) & (planning['fin'] <= heure_depart + duree))
            )
        ]
        if en_conflit.empty:
            dispo = imp
            break

    if dispo is None:
        st.warning("Aucune imprimante disponible pour cet horaire.")
        return

    couleur = "#%06x" % random.randint(0, 0xFFFFFF)

    nv_ticket = pd.DataFrame([{
        'date': st.session_state.date,
        'imprimante': dispo,
        'ticket': ticket,
        'debut': heure_depart,
        'fin': heure_depart + duree,
        'couleur': couleur,
        'type': type_poste
    }])

    planning = pd.concat([planning, nv_ticket], ignore_index=True)
    sauvegarder_planning(planning)
    st.success(f"Ticket {ticket} affecté à {dispo}")

# ---------- AFFICHER GANTT ----------
def afficher_gantt():
    planning = charger_planning()
    # Inclure les impressions qui commencent la veille et continuent
    df = planning[
        (planning['date'] == st.session_state.date) |
        (planning['date'] == st.session_state.date - timedelta(days=1))
    ]
    if df.empty:
        st.info("Aucune impression prévue pour ce jour.")
        return

    # Ajuster les heures si chevauchement
    df['start'] = df.apply(lambda row: max(row['debut'], 0), axis=1)
    df['end'] = df['fin']

    fig = px.timeline(
        df,
        x_start='start',
        x_end='end',
        y='imprimante',
        color='ticket',
        color_discrete_map={row['ticket']: row['couleur'] for idx, row in df.iterrows()},
        title=f"Planning du {st.session_state.date.strftime('%d/%m/%Y')}",
    )
    fig.update_layout(xaxis=dict(
        tickmode='linear',
        tick0=0,
        dtick=60,
        title='Minutes de la journée'
    ))
    st.plotly_chart(fig, use_container_width=True)

# ---------- INTERFACE UTILISATEUR ----------
st.title("Gestion Planning Impression 3D")

with st.form("ajout_ticket"):
    col1, col2 = st.columns(2)
    with col1:
        ticket = st.text_input("Numéro du ticket")
        type_poste = st.selectbox("Type de poste", ['A', 'B'])
    with col2:
        heure_depart = st.number_input("Heure de départ (minutes)", min_value=0, max_value=1440, value=480)
        duree = st.number_input("Durée (minutes)", min_value=1, max_value=1440, value=60)
    submitted = st.form_submit_button("Ajouter Impression")
    if submitted:
        ajouter_ticket(ticket, heure_depart, duree, type_poste)

st.markdown("---")
col1, col2 = st.columns(2)
if col1.button("Jour Précédent"):
    st.session_state.date -= timedelta(days=1)
if col2.button("Jour Suivant"):
    st.session_state.date += timedelta(days=1)

st.subheader(f"Planning du {st.session_state.date.strftime('%d/%m/%Y')}")
afficher_gantt()

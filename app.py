import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
import random
import os

# ---------- CONFIG ---------- #
if "date" not in st.session_state:
    st.session_state.date = datetime.today().date()

# ---------- FONCTIONS ---------- #
def load_data(date):
    filename = f"planning_{date}.csv"
    if os.path.exists(filename):
        return pd.read_csv(filename)
    else:
        return pd.DataFrame(columns=["PrinterID", "Start", "Duration", "Ticket", "Type", "Color"])

def save_data(df, date):
    df.to_csv(f"planning_{date}.csv", index=False)

def find_available_printer(df, start, duration, type_):
    printers = [f"{type_}{i+1}" for i in range(10 if type_ == "A" else 6)]
    for printer in printers:
        bookings = df[df["PrinterID"] == printer]
        overlaps = bookings[
            (pd.to_datetime(bookings["Start"]) < start + timedelta(minutes=duration)) &
            (pd.to_datetime(bookings["Start"]) + pd.to_timedelta(bookings["Duration"], 'm') > start)
        ]
        if overlaps.empty:
            return printer
    return None

# ---------- INTERFACE ---------- #
st.title(f"Planning Impression - {st.session_state.date}")

col1, col2, col3 = st.columns(3)
if col1.button("Jour précédent"):
    st.session_state.date -= timedelta(days=1)
if col3.button("Jour suivant"):
    st.session_state.date += timedelta(days=1)

df = load_data(st.session_state.date)

with st.form("add_ticket"):
    ticket = st.text_input("Numéro Ticket", "")
    type_ = st.selectbox("Type", ["A", "B"])
    start_time = st.time_input("Heure Début (08:00 - 17:00)", value=datetime.strptime("08:00", "%H:%M").time())
    duration = st.number_input("Durée (min)", min_value=1, max_value=1440, value=60)
    submitted = st.form_submit_button("Ajouter Impression")
    
    if submitted:
        start_datetime = datetime.combine(st.session_state.date, start_time)
        if not (8 <= start_time.hour <= 17):
            st.error("L'heure de début doit être entre 08:00 et 17:00")
        else:
            printer = find_available_printer(df, start_datetime, duration, type_)
            if printer:
                new_entry = {
                    "PrinterID": printer,
                    "Start": start_datetime,
                    "Duration": duration,
                    "Ticket": ticket,
                    "Type": type_,
                    "Color": f"#{random.randint(0, 0xFFFFFF):06x}"
                }
                df = pd.concat([df, pd.DataFrame([new_entry])], ignore_index=True)
                save_data(df, st.session_state.date)
                st.success(f"Impression ajoutée à {printer}")
            else:
                st.error("Aucune imprimante disponible")

# ---------- AFFICHAGE GANTT ---------- #
if not df.empty:
    df["End"] = pd.to_datetime(df["Start"]) + pd.to_timedelta(df["Duration"], unit='m')
    fig = px.timeline(df, x_start="Start", x_end="End", y="PrinterID", color="Ticket", color_discrete_sequence=df["Color"])
    fig.update_yaxes(autorange="reversed")
    fig.update_layout(xaxis=dict(tickformat="%H:%M"), height=600)
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("Aucune impression pour ce jour.")


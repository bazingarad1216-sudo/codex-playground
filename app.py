import json

import streamlit as st

from dog_nutrition.energy import ACTIVITY_FACTORS, calculate_mer, calculate_rer
from dog_nutrition.models import DogProfile

st.set_page_config(page_title="Dog Nutrition Energy Calculator", page_icon="🐶")
st.title("🐶 Dog Nutrition Energy Calculator")

with st.form("energy_form"):
    weight_kg = st.number_input("Weight (kg)", min_value=0.0001, value=10.0, step=0.1)
    neutered = st.toggle("Neutered", value=True)
    activity_options = ["low", "normal", "high"]
    activity = st.selectbox("Activity", options=activity_options, index=1)
    submitted = st.form_submit_button("Calculate")

if submitted:
    profile = DogProfile(
        weight_kg=float(weight_kg),
        neutered=bool(neutered),
        activity=activity,
    )
    rer = calculate_rer(profile.weight_kg)
    mer = calculate_mer(profile)
    activity_factor = ACTIVITY_FACTORS[profile.activity]

    result = {
        "weight_kg": profile.weight_kg,
        "neutered": profile.neutered,
        "activity": profile.activity,
        "activity_factor": activity_factor,
        "rer": round(rer, 2),
        "mer": round(mer, 2),
    }

    st.metric("RER", f"{result['rer']}")
    st.metric("MER", f"{result['mer']}")
    st.metric("Activity Factor", f"{activity_factor}")
    st.code(json.dumps(result, ensure_ascii=False), language="json")

import json
import os

import streamlit as st

from dog_nutrition.energy import ACTIVITY_FACTORS, calculate_mer, calculate_rer
from dog_nutrition.foods_db import (
    calculate_kcal_for_grams,
    connect_db,
    init_db,
    search_foods,
    search_foods_cn,
)
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

st.divider()
st.header("Food search (offline)")

food_db_path = os.environ.get("FOODS_DB_PATH", "foods.db")
search_term = st.text_input("Search food name", placeholder="e.g. chicken / 鸡胸肉")

with connect_db(food_db_path) as food_conn:
    init_db(food_conn)
    if not search_term.strip():
        matches = []
    elif any("\u4e00" <= ch <= "\u9fff" for ch in search_term):
        matches = search_foods_cn(food_conn, search_term, limit=20)
    else:
        matches = search_foods(food_conn, search_term, limit=20)

if not search_term.strip():
    st.caption("Enter a keyword to search foods from local SQLite DB.")
elif not matches:
    st.warning("No foods found. Import local FDC data first.")
else:
    labels = [f"{item.name} ({item.kcal_per_100g:.2f} kcal/100g)" for item in matches]
    selected_label = st.selectbox("Matched foods", options=labels)
    selected_food = matches[labels.index(selected_label)]
    grams = st.number_input("Grams", min_value=0.0, value=100.0, step=1.0)
    kcal = calculate_kcal_for_grams(
        kcal_per_100g=selected_food.kcal_per_100g,
        grams=float(grams),
    )
    st.metric("Calories", f"{kcal:.2f} kcal")
    with st.expander("Nutrition panel", expanded=True):
        st.write(f"- kcal per 100g: {selected_food.kcal_per_100g:.2f}")
        st.write(f"- kcal for {grams:.0f}g: {kcal:.2f}")
        st.write(f"- source: {selected_food.source}")
        st.write(f"- fdc_id: {selected_food.fdc_id}")

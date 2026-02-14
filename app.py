import os

import streamlit as st

from dog_nutrition.foods_db import connect_db, get_food_nutrients, init_db
from dog_nutrition.fdc_import import run_import
from dog_nutrition.models import DogProfile
from dog_nutrition.nrc import requirements_for_profile
from dog_nutrition.optimizer import optimize_recipe
from dog_nutrition.search import search_foods_cn

st.set_page_config(page_title="Dog Nutrition Planner", page_icon="🐶", layout="wide")
st.title("🐶 离线狗狗营养配方工具")

food_db_path = os.environ.get("FOODS_DB_PATH", "foods.db")
with connect_db(food_db_path) as conn:
    init_db(conn)

page = st.sidebar.radio("页面", ["中文搜索", "狗狗参数", "生成配方", "数据管理"])

if page == "中文搜索":
    st.header("中文搜索食材")
    query = st.text_input("输入食材", placeholder="鸡胸肉/鸡蛋/牛心/红薯/西蓝花")
    if query.strip():
        with connect_db(food_db_path) as conn:
            hits = search_foods_cn(conn, query, limit=15)
        if not hits:
            st.warning("未找到候选（或已被毒物过滤）")
        else:
            labels = [f"{h.food.name} | {h.food.kcal_per_100g:.1f} kcal/100g" for h in hits]
            idx = st.selectbox("候选", options=range(len(labels)), format_func=lambda i: labels[i])
            selected = hits[idx].food
            with connect_db(food_db_path) as conn:
                nutrients = get_food_nutrients(conn, selected.id)
            st.subheader(selected.name)
            st.write(f"热量：{selected.kcal_per_100g:.1f} kcal/100g")
            for n in nutrients:
                st.write(f"- {n.nutrient_key}: {n.amount_per_100g:.3g} {n.unit}")

if page == "狗狗参数":
    st.header("狗狗参数")
    weight = st.number_input("体重kg", min_value=0.1, value=10.0, step=0.1)
    neutered = st.toggle("是否绝育", value=True)
    activity = st.selectbox("活动水平", ["low", "normal", "high"], index=1)
    profile = DogProfile(weight_kg=float(weight), neutered=bool(neutered), activity=activity)
    mer, reqs = requirements_for_profile(profile)
    st.metric("MER", f"{mer:.1f} kcal/day")
    st.caption("NRC 2006 成犬维持阈值（按 MER 缩放）")
    for req in reqs:
        st.write(f"- {req.nutrient_key}: min={req.min_per_day:.2f}, max={req.max_per_day if req.max_per_day is not None else 'NA'}")
    st.session_state["profile"] = profile

if page == "生成配方":
    st.header("生成配方")
    mode = st.radio("喂养模式", ["纯自制", "混合商业狗粮", "混合罐头"], horizontal=True)
    st.caption(f"当前模式：{mode}")
    ids_raw = st.text_input("输入候选 food_id（逗号分隔）", placeholder="1,2,3")
    if st.button("生成"):
        profile = st.session_state.get("profile")
        if profile is None:
            st.error("请先在【狗狗参数】页面设置参数")
        else:
            ids = [int(x.strip()) for x in ids_raw.split(",") if x.strip().isdigit()]
            with connect_db(food_db_path) as conn:
                result = optimize_recipe(conn, profile, ids)
            if not result.feasible:
                st.error(f"不可行：{result.reason}")
            else:
                st.success("已生成可行配方")
                for item in result.items:
                    st.write(f"- {item.food_name}: {item.grams:.1f} g")

if page == "数据管理":
    st.header("数据管理")
    source = st.text_input("source", value="fdc")
    input_path = st.text_input("导入CSV/JSON路径", value="data/fdc/fdc_import_ready.csv")
    if st.button("执行导入"):
        imported, skipped = run_import(db_path=__import__('pathlib').Path(food_db_path), input_path=__import__('pathlib').Path(input_path), source=source)
        st.success(f"导入完成 imported={imported}, skipped_missing_energy={skipped}")

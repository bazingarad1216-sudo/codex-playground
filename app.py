from pathlib import Path
import os

import streamlit as st

from dog_nutrition.fdc_import import run_import
from dog_nutrition.foods_db import connect_db, get_food_nutrients, init_db
from dog_nutrition.models import DogProfile
from dog_nutrition.nrc import requirements_for_profile
from dog_nutrition.optimizer import optimize_recipe
from dog_nutrition.search import search_foods_cn
from dog_nutrition.toxicity import is_toxic_food_name

st.set_page_config(page_title="Dog Nutrition Planner", page_icon="🐶", layout="wide")
st.title("🐶 离线狗狗营养配方工具")

food_db_path = os.environ.get("FOODS_DB_PATH", "foods.db")
with connect_db(food_db_path) as conn:
    init_db(conn)

if "basket" not in st.session_state:
    st.session_state["basket"] = []

page = st.sidebar.radio("页面", ["中文搜索", "狗狗参数", "生成配方", "数据管理"])

if page == "中文搜索":
    st.header("中文搜索食材")
    query = st.text_input("输入食材", placeholder="鸡胸肉/鸡蛋/牛心/红薯/西蓝花")
    if query.strip():
        with connect_db(food_db_path) as conn:
            hits = search_foods_cn(conn, query, limit=20)
        if not hits:
            st.warning("未找到候选（或已被毒物过滤）")
        else:
            for h in hits:
                food = h.food
                if is_toxic_food_name(food.name):
                    continue
                cols = st.columns([4, 1, 1])
                cols[0].write(f"**{food.name}**  |  {food.kcal_per_100g:.1f} kcal/100g")
                if food.id in st.session_state["basket"]:
                    if cols[1].button("移除", key=f"remove_{food.id}"):
                        st.session_state["basket"] = [x for x in st.session_state["basket"] if x != food.id]
                else:
                    if cols[1].button("加入候选", key=f"add_{food.id}"):
                        st.session_state["basket"].append(food.id)
                if cols[2].button("看营养", key=f"detail_{food.id}"):
                    st.session_state["selected_food_id"] = food.id

    selected_food_id = st.session_state.get("selected_food_id")
    if selected_food_id is not None:
        with connect_db(food_db_path) as conn:
            row = conn.execute("SELECT id, name, kcal_per_100g FROM foods WHERE id = ?", (selected_food_id,)).fetchone()
            nutrients = get_food_nutrients(conn, selected_food_id)
        if row:
            st.subheader(f"营养面板：{row['name']}")
            st.write(f"热量：{row['kcal_per_100g']:.1f} kcal/100g")
            for group in ["宏量", "矿物质", "维生素", "EPA/DHA"]:
                subset = [n for n in nutrients if n.group == group]
                if subset:
                    st.markdown(f"**{group}**")
                    for n in subset:
                        st.write(f"- {n.nutrient_key}: {n.amount_per_100g:.3g} {n.unit}")

    st.divider()
    st.write(f"当前候选篮子：{len(st.session_state['basket'])} 项")

if page == "狗狗参数":
    st.header("狗狗参数")
    weight = st.number_input("体重kg", min_value=0.1, value=10.0, step=0.1)
    neutered = st.toggle("是否绝育", value=True)
    activity = st.selectbox("活动水平", ["low", "normal", "high"], index=1)
    profile = DogProfile(weight_kg=float(weight), neutered=bool(neutered), activity=activity)
    mer, reqs = requirements_for_profile(profile)
    st.metric("MER", f"{mer:.1f} kcal/day")
    st.session_state["profile"] = profile
    st.write("NRC(min/suggest/max)")
    table = []
    for r in reqs:
        table.append({"nutrient": r.nutrient_key, "min": round(r.min_per_day, 3), "suggest": round(r.suggest_per_day, 3), "max": None if r.max_per_day is None else round(r.max_per_day, 3)})
    st.dataframe(table, use_container_width=True)

if page == "生成配方":
    st.header("生成配方")
    mode = st.radio("喂养模式", ["纯自制", "混合商业狗粮", "混合罐头"], horizontal=True)
    st.caption(f"当前模式：{mode}")

    with connect_db(food_db_path) as conn:
        options = []
        for food_id in st.session_state["basket"]:
            row = conn.execute("SELECT id, name, kcal_per_100g FROM foods WHERE id = ?", (food_id,)).fetchone()
            if row and (not is_toxic_food_name(row["name"])):
                options.append((row["id"], f"{row['name']} ({row['kcal_per_100g']:.1f} kcal/100g)"))

    selected_ids = st.multiselect("候选食材", options=[x[0] for x in options], format_func=lambda fid: dict(options)[fid])

    if st.button("生成配方"):
        profile = st.session_state.get("profile")
        if profile is None:
            st.error("请先到【狗狗参数】设置体重/绝育/活动")
        elif not selected_ids:
            st.error("请先从候选篮子选择食材")
        else:
            with connect_db(food_db_path) as conn:
                result = optimize_recipe(conn, profile, list(selected_ids))
            if not result.feasible:
                st.error(f"不可行：{result.reason}")
            else:
                st.success("已生成可行配方")
                for item in result.items:
                    st.write(f"- {item.food_name}: {item.grams:.1f} g")
            if result.nrc_rows:
                table = []
                for row in result.nrc_rows:
                    table.append({
                        "nutrient": row.nutrient_key,
                        "min": round(row.minimum, 3),
                        "suggest": round(row.suggest, 3),
                        "max": None if row.maximum is None else round(row.maximum, 3),
                        "actual": round(row.actual, 3),
                        "status": row.status,
                    })
                st.dataframe(table, use_container_width=True)

if page == "数据管理":
    st.header("数据管理")
    source = st.text_input("source", value="fdc")
    input_path = st.text_input("导入JSON/CSV路径", value="data/fdc/fdc_import_ready.csv")
    st.caption("建议优先导入 FDC JSON（含 foodNutrients）；CSV 作为补充。")
    if st.button("执行导入"):
        imported, skipped = run_import(db_path=Path(food_db_path), input_path=Path(input_path), source=source)
        st.success(f"导入完成 imported={imported}, skipped_missing_energy={skipped}")

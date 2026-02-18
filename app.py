from pathlib import Path
import os

import streamlit as st

from dog_nutrition.fdc_import import run_import
from dog_nutrition.foods_db import connect_db, get_food_nutrients, init_db
from dog_nutrition.models import DogProfile
from dog_nutrition.nrc import requirements_for_profile
from dog_nutrition.nutrients import KEY_NUTRIENTS
from dog_nutrition.optimizer import optimize_recipe
from dog_nutrition.search import search_foods_cn
from dog_nutrition.toxicity import is_toxic_food_name

st.set_page_config(page_title="Dog Nutrition Planner", page_icon="🐶", layout="wide")
st.title("🐶 离线狗狗营养配方工具")

food_db_path = os.environ.get("FOODS_DB_PATH", "foods.db")
food_db_abs = str(Path(food_db_path).resolve())
with connect_db(food_db_path) as conn:
    init_db(conn)
    foods_count = conn.execute("SELECT COUNT(*) AS c FROM foods").fetchone()["c"]
    fn_count = conn.execute("SELECT COUNT(*) AS c FROM food_nutrients").fetchone()["c"]

if "basket" not in st.session_state:
    st.session_state["basket"] = []

st.sidebar.markdown("### 当前数据库")
st.sidebar.code(f"DB: {food_db_abs}")
st.sidebar.write(f"foods: {foods_count}")
st.sidebar.write(f"food_nutrients: {fn_count}")
st.sidebar.divider()
st.sidebar.markdown("### 候选篮子")
if not st.session_state["basket"]:
    st.sidebar.caption("篮子为空")
else:
    with connect_db(food_db_path) as conn:
        for fid in list(st.session_state["basket"]):
            row = conn.execute("SELECT name FROM foods WHERE id = ?", (fid,)).fetchone()
            if row is None:
                st.session_state["basket"] = [x for x in st.session_state["basket"] if x != fid]
                continue
            c1, c2 = st.sidebar.columns([3, 1])
            c1.write(row["name"])
            if c2.button("移除", key=f"sidebar_remove_{fid}"):
                st.session_state["basket"] = [x for x in st.session_state["basket"] if x != fid]

page = st.sidebar.radio("页面", ["中文搜索", "狗狗参数", "生成配方", "数据管理"])

if page == "中文搜索":
    st.header("中文搜索食材")
    st.caption(f"DB: {food_db_abs} | foods={foods_count} | food_nutrients={fn_count}")
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
                    if cols[1].button("移出篮子", key=f"remove_{food.id}"):
                        st.session_state["basket"] = [x for x in st.session_state["basket"] if x != food.id]
                else:
                    if cols[1].button("加入篮子", key=f"add_{food.id}"):
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
            nutrient_map = {n.nutrient_key: n for n in nutrients}
            panel_order = [
                "protein_g", "fat_g", "carb_g",
                "ca_mg", "p_mg", "k_mg", "na_mg", "mg_mg",
                "fe_mg", "zn_mg", "cu_mg", "mn_mg", "se_ug", "iodine_ug",
                "vit_a_ug", "vit_d_ug", "vit_e_mg",
                "thiamin_mg", "riboflavin_mg", "niacin_mg", "pantothenic_mg", "vit_b6_mg", "folate_ug", "vit_b12_ug",
                "epa_g", "dha_g",
            ]
            rows = []
            for key in panel_order:
                display_name, unit, group = KEY_NUTRIENTS[key]
                nutrient = nutrient_map.get(key)
                rows.append(
                    {
                        "group": group,
                        "nutrient": display_name,
                        "key": key,
                        "amount_per_100g": "NA" if nutrient is None else round(nutrient.amount_per_100g, 4),
                        "unit": unit,
                    }
                )
            st.dataframe(rows, use_container_width=True)
            st.caption(f"热量: {row['kcal_per_100g']:.2f} kcal/100g")

if page == "狗狗参数":
    st.header("狗狗参数")
    weight = st.number_input("体重kg", min_value=0.1, value=10.0, step=0.1)
    neutered = st.toggle("是否绝育", value=True)
    activity = st.selectbox("活动水平", ["low", "normal", "high"], index=1)
    profile = DogProfile(weight_kg=float(weight), neutered=bool(neutered), activity=activity)
    mer, reqs = requirements_for_profile(profile)
    st.metric("MER", f"{mer:.1f} kcal/day")
    st.session_state["profile"] = profile
    st.caption("NRC 指标按 MER 缩放（per-day）")
    table = []
    for r in reqs:
        unit = KEY_NUTRIENTS.get(r.nutrient_key, ("", "", ""))[1]
        table.append(
            {
                "nutrient": r.nutrient_key,
                "min": round(r.min_per_day, 3),
                "suggest": round(r.suggest_per_day, 3),
                "max": None if r.max_per_day is None else round(r.max_per_day, 3),
                "unit": unit,
            }
        )
    st.dataframe(table, use_container_width=True)

if page == "生成配方":
    st.header("生成配方")
    mode = st.radio("喂养模式", ["纯自制", "混合商业狗粮", "混合罐头"], horizontal=True)
    st.caption(f"当前模式：{mode}")

    with connect_db(food_db_path) as conn:
        options: list[tuple[int, str]] = []
        for food_id in st.session_state["basket"]:
            row = conn.execute("SELECT id, name, kcal_per_100g FROM foods WHERE id = ?", (food_id,)).fetchone()
            if row and (not is_toxic_food_name(row["name"])):
                options.append((row["id"], f"{row['name']} ({row['kcal_per_100g']:.1f} kcal/100g)"))

    if not options:
        st.info("候选篮子为空，请先到【中文搜索】加入食材。")
    selected_ids = st.multiselect(
        "候选食材（默认来自篮子）",
        options=[x[0] for x in options],
        default=[x[0] for x in options],
        format_func=lambda fid: dict(options)[fid],
    )

    if st.button("生成配方"):
        profile = st.session_state.get("profile")
        if profile is None:
            st.error("请先到【狗狗参数】设置体重/绝育/活动")
        elif not selected_ids:
            st.error("请先在篮子中添加并选择食材")
        else:
            with connect_db(food_db_path) as conn:
                result = optimize_recipe(conn, profile, list(selected_ids))
            if not result.feasible:
                st.error(f"不可行：{result.reason}")
            else:
                st.success("已生成可行配方")
                for item in result.items:
                    st.write(f"- {item.food_name}: {item.grams:.1f} g")

            table = []
            for row in result.nrc_rows:
                unit = KEY_NUTRIENTS.get(row.nutrient_key, ("", "", ""))[1]
                table.append(
                    {
                        "nutrient": row.nutrient_key,
                        "min": round(row.minimum, 3),
                        "suggest": round(row.suggest, 3),
                        "max": None if row.maximum is None else round(row.maximum, 3),
                        "actual": round(row.actual, 3),
                        "unit": unit,
                        "status": row.status,
                    }
                )
            st.dataframe(table, use_container_width=True)

if page == "数据管理":
    st.header("数据管理")
    source = st.text_input("source", value="fdc")
    input_path = st.text_input("导入JSON/CSV路径", value="data/fdc/fdc_import_ready.csv")
    st.caption("建议优先导入 FDC JSON（含 foodNutrients）；CSV 作为补充。")
    if st.button("执行导入"):
        imported, skipped = run_import(db_path=Path(food_db_path), input_path=Path(input_path), source=source)
        st.success(f"导入完成 imported={imported}, skipped_missing_energy={skipped}")

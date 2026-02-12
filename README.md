# Dog Nutrition Planner (NRC + The Forever Dog)

一个用于狗狗营养评估与食谱规划的应用草案：

- 输入狗狗信息（年龄、品种、性别、绝育、运动情况、体重）
- 计算每日热量需求（RER/MER）
- 计算每日营养目标（基于 NRC，结合 The Forever Dog 实践偏好）
- 评估当前食谱是否存在营养不足/过量
- （后续）自动生成更接近目标的食谱建议

---

## 运行 UI（Streamlit）

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
streamlit run app.py
```

## 1. MVP 范围（第一版）

第一版先聚焦「可计算、可评估」：

1. **狗狗信息输入**
   - 年龄（月）
   - 体重（kg）
   - 品种（可选自由输入）
   - 性别（公/母）
   - 绝育（是/否）
   - 活动量（低/中/高）

2. **每日热量计算**
   - RER：`70 * (体重kg ^ 0.75)`
   - MER：`RER * 系数`

3. **食谱营养评估**
   - 用户输入食材与克重
   - 系统汇总热量与营养素摄入
   - 对比目标，输出不足/适中/过量

4. **输出结果**
   - 每日热量目标 vs 当前食谱热量
   - 核心营养素状态表
   - 3 条可执行的调整建议

---

## 2. 数据模型（建议）

## 2.1 DogProfile

```json
{
  "id": "uuid",
  "name": "string",
  "age_months": 36,
  "weight_kg": 12.5,
  "breed": "Shiba Inu",
  "sex": "male|female",
  "neutered": true,
  "activity_level": "low|moderate|high",
  "life_stage": "puppy|adult|senior"
}
```

## 2.2 NutrientRequirement

```json
{
  "nutrient": "protein",
  "unit": "g",
  "basis": "per_day",
  "min": 45,
  "target": 55,
  "max": 80,
  "source": "NRC"
}
```

> 备注：内部可维护 `basis` 为 `per_1000kcal`，计算时再按 MER 换算为 `per_day`。

## 2.3 Ingredient

```json
{
  "id": "chicken_breast",
  "name": "鸡胸肉",
  "per_100g": {
    "kcal": 165,
    "protein_g": 31,
    "fat_g": 3.6,
    "calcium_mg": 15,
    "phosphorus_mg": 210
  }
}
```

## 2.4 Recipe

```json
{
  "id": "recipe_001",
  "name": "基础鸡肉饭",
  "items": [
    { "ingredient_id": "chicken_breast", "grams": 120 },
    { "ingredient_id": "pumpkin", "grams": 80 }
  ]
}
```

## 2.5 RecipeAnalysisResult

```json
{
  "total_kcal": 420,
  "kcal_target": 500,
  "kcal_gap": -80,
  "nutrients": [
    {
      "nutrient": "protein",
      "actual": 48,
      "target": 55,
      "status": "low"
    }
  ],
  "suggestions": [
    "蛋白质偏低，可增加 20-30g 高蛋白瘦肉。"
  ]
}
```

---

## 3. 计算规则（MVP 版）

## 3.1 热量

- `RER = 70 * weight_kg^0.75`
- `MER = RER * factor`

建议默认系数（可在后台配置）：

- 幼犬：2.0
- 成犬（已绝育，活动低）：1.4
- 成犬（已绝育，活动中）：1.6
- 成犬（未绝育，活动中）：1.8
- 高活动：2.0+
- 老年犬（低活动）：1.2~1.4

## 3.2 营养目标换算

若标准以 `每1000kcal` 给出：

- `daily_target = (MER / 1000) * nutrient_per_1000kcal`

对每个营养素给出：

- `min`
- `target`
- `max`（若有）

状态判断：

- `< min` => `low`
- `min~max`（或接近 target）=> `ok`
- `> max` => `high`

## 3.3 食谱营养汇总

对每个食材：

- `实际营养 = 每100g营养 * (grams / 100)`

再对所有食材求和，得到食谱总摄入并与目标对比。

---

## 4. API 草图（可直接开工）

## 4.1 计算需求

`POST /api/v1/requirements/calculate`

Request:

```json
{
  "dog_profile": {
    "age_months": 36,
    "weight_kg": 12.5,
    "sex": "male",
    "neutered": true,
    "activity_level": "moderate",
    "life_stage": "adult"
  }
}
```

Response:

```json
{
  "rer": 465,
  "mer": 744,
  "nutrient_requirements": [
    { "nutrient": "protein", "unit": "g", "min": 40, "target": 50, "max": 75 }
  ]
}
```

## 4.2 评估食谱

`POST /api/v1/recipes/analyze`

Request:

```json
{
  "dog_profile": {
    "age_months": 36,
    "weight_kg": 12.5,
    "sex": "male",
    "neutered": true,
    "activity_level": "moderate",
    "life_stage": "adult"
  },
  "recipe": {
    "name": "基础鸡肉饭",
    "items": [
      { "ingredient_id": "chicken_breast", "grams": 120 },
      { "ingredient_id": "pumpkin", "grams": 80 }
    ]
  }
}
```

Response:

```json
{
  "total_kcal": 420,
  "kcal_target": 744,
  "kcal_status": "low",
  "nutrients": [
    { "nutrient": "protein", "actual": 48, "target": 50, "status": "ok" },
    { "nutrient": "calcium", "actual": 280, "target": 900, "status": "low" }
  ],
  "suggestions": [
    "总热量偏低，建议提升 20-30% 总食材量。",
    "钙摄入不足，优先调整含钙食材或补充剂。"
  ]
}
```

---

## 5. 前端页面（最小流程）

1. **狗狗信息表单页**
2. **食谱输入/选择页**（下拉选择已有食谱 + 手动调整克重）
3. **结果页**（热量条形图 + 营养素状态表 + 调整建议）

---

## 6. 里程碑建议

- M1（本周）：完成需求计算 + 食谱评估后端
- M2（下周）：完成前端 3 页流程与基础可视化
- M3：加入自动配餐（规则引擎）
- M4：加入更完整营养数据库与报告导出

---

## 7. 注意事项

- NRC 与 The Forever Dog 口径并非完全同一类标准：
  - NRC 作为“营养定量基线”
  - The Forever Dog 作为“食材选择与实践偏好”
- 单位必须统一（mg/µg/IU、每1000kcal、每日绝对量）
- 食材缺失微量营养数据时，结果需标记“数据不完整”，避免误判

# AI-CARE Lung 後台系統更新說明 v2.0

## 📋 更新摘要

本次更新主要解決 **病人端（前台）與後台資料結構不一致** 的問題，確保兩邊資料能完整同步。

---

## 🔴 發現的問題

### 1. 症狀回報表 (Reports) 欄位不足

| 病人端有 | 後台原本 | 問題 |
|----------|---------|------|
| 7 項個別症狀分數 | 只有 overall_score | ❌ 無法儲存個別症狀 |
| 7 項症狀描述 | 無 | ❌ 文字描述遺失 |
| 回報方式 (ai_chat/voice) | 無 | ❌ 無法區分來源 |
| 安全檢查 (發燒/傷口) | 無 | ❌ 重要警示資訊遺失 |
| 開放式問題回答 | 無 | ❌ 有價值的 NLP 訓練資料遺失 |

### 2. 缺少對話記錄工作表 (Conversations)

病人端有完整的對話追蹤功能，但後台完全沒有對應的資料表，導致：
- 無法追蹤病人與 AI 的完整對話
- 無法進行 NLP 標註訓練
- 無法分析對話品質

### 3. 缺少成就記錄工作表 (Achievements)

病人端有遊戲化成就系統，但後台無法查看：
- 無法統計病人的成就解鎖情況
- 無法分析遊戲化機制效果
- 無法進行順從度激勵分析

---

## ✅ 更新內容

### 1. 更新 `gsheets_manager.py`

**新增的 REPORT_COLUMNS 欄位：**
```python
# 個別症狀分數 (0-10)
"pain_score", "fatigue_score", "dyspnea_score", "cough_score",
"sleep_score", "appetite_score", "mood_score"

# 個別症狀描述
"pain_description", "fatigue_description", "dyspnea_description",
"cough_description", "sleep_description", "appetite_description", "mood_description"

# 安全檢查
"has_fever", "has_wound_issue", "has_blood_in_sputum"

# 開放式問題
"open_ended_1", "open_ended_2", "additional_notes"

# 統計
"avg_score", "max_score_item", "report_method"
```

**新增的工作表：**
- `Conversations` - 對話記錄
- `Achievements` - 成就記錄
- `OpenEndedResponses` - 開放式問題回應
- `Compliance` - 順從度追蹤

**新增的函數：**
```python
# 對話記錄
get_conversations(patient_id, session_id)
save_conversation_message(message_data)
get_conversation_sessions(patient_id)

# 成就記錄
get_achievements(patient_id)
save_achievement(achievement_data)
get_patient_achievement_stats(patient_id)

# 順從度
get_patient_compliance_stats(patient_id)

# 警示計算（更新）
calculate_alert_level(report_data)  # 支援個別症狀
```

### 2. 更新 `setup_sheets.py`

- 自動檢查並新增缺少的欄位
- 自動建立缺少的工作表
- 提供更新報告和預覽功能

---

## 📦 部署步驟

### 步驟 1：備份現有資料
```bash
# 在 Google Sheets 中匯出現有資料為 CSV 備份
```

### 步驟 2：更新後台程式碼
```bash
# 將以下檔案替換到您的後台專案：
1. gsheets_manager.py  # 核心資料管理模組
2. setup_sheets.py     # 工作表初始化腳本
```

### 步驟 3：執行工作表更新
```bash
# 在 Streamlit Cloud 執行：
streamlit run setup_sheets.py

# 點擊「🚀 完整更新」按鈕
```

### 步驟 4：驗證更新
- 檢查 Google Sheets 是否新增了所有欄位
- 測試新增病人回報是否正常儲存
- 確認前後台資料同步

---

## ⚠️ 注意事項

1. **向下相容**：更新後的程式碼與舊資料相容，不會影響現有資料
2. **新增欄位為空**：已有的回報紀錄，新增的欄位會是空的，這是正常的
3. **API 配額**：首次更新可能會觸發較多 API 呼叫，建議在低峰時段執行

---

## 📊 前後台欄位對照表

### Reports 工作表

| 欄位名稱 | 類型 | 說明 | 病人端對應 |
|---------|------|------|-----------|
| report_id | string | 回報 ID | ✅ |
| patient_id | string | 病人 ID | ✅ |
| date | date | 回報日期 | ✅ |
| report_method | string | 回報方式 | ✅ ai_chat/questionnaire/voice |
| overall_score | int | 整體分數 (0-10) | ✅ |
| pain_score | int | 疼痛分數 (0-10) | 🆕 對應 MDASI-LC |
| fatigue_score | int | 疲勞分數 (0-10) | 🆕 |
| dyspnea_score | int | 呼吸困難分數 (0-10) | 🆕 |
| cough_score | int | 咳嗽分數 (0-10) | 🆕 |
| sleep_score | int | 睡眠分數 (0-10) | 🆕 |
| appetite_score | int | 食慾分數 (0-10) | 🆕 |
| mood_score | int | 心情分數 (0-10) | 🆕 |
| pain_description | text | 疼痛描述 | 🆕 |
| has_fever | Y/N | 是否發燒 | 🆕 安全檢查 |
| has_wound_issue | Y/N | 傷口是否異常 | 🆕 安全檢查 |
| alert_level | string | 警示等級 | ✅ green/yellow/red |

### Conversations 工作表（新增）

| 欄位名稱 | 類型 | 說明 |
|---------|------|------|
| message_id | string | 訊息 ID |
| session_id | string | 會話 ID |
| patient_id | string | 病人 ID |
| role | string | 角色 (patient/ai_assistant) |
| content | text | 訊息內容 |
| source | string | 來源 (raw_input/button/ai_generated) |
| detected_intent | string | 偵測到的意圖 |
| detected_emotion | string | 偵測到的情緒 |
| timestamp | datetime | 時間戳記 |

### Achievements 工作表（新增）

| 欄位名稱 | 類型 | 說明 |
|---------|------|------|
| record_id | string | 記錄 ID |
| patient_id | string | 病人 ID |
| achievement_id | string | 成就 ID |
| achievement_name | string | 成就名稱 |
| achievement_type | string | 類型 (streak/completion/special) |
| unlocked_date | date | 解鎖日期 |
| points_earned | int | 獲得積分 |

---

## 🔮 未來規劃

1. **NLP 標註介面**：後台新增對話標註功能
2. **順從度儀表板**：視覺化順從度統計
3. **成就統計報表**：分析遊戲化機制效果
4. **自動警示升級**：根據連續症狀自動調整警示等級

---

## 📞 技術支援

三軍總醫院 數位醫療中心
- Email: digital.medicine@tsgh.ndmctsgh.edu.tw

---

*最後更新：2024-12*

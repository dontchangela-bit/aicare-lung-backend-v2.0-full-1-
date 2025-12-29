"""
AI-CARE Lung - Google Sheets 初始化/更新腳本（v2.0）
=====================================================

功能：
1. 檢查現有工作表結構
2. 新增缺少的欄位
3. 建立缺少的工作表
4. 支援前後台資料同步
5. 產生更新報告

使用方式：
1. 在 Streamlit Cloud 的 secrets 設定好 gcp_service_account 和 spreadsheet_id
2. 執行此腳本：streamlit run setup_sheets.py

v2.0 更新：
- 新增 Reports 的個別症狀分數欄位
- 新增 Conversations 對話記錄工作表
- 新增 Achievements 成就記錄工作表
- 新增 OpenEndedResponses 開放式問題工作表
- 新增 Compliance 順從度追蹤工作表

三軍總醫院 數位醫療中心
"""

import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

# ============================================
# 完整欄位定義（v2.0 - 前後台整合）
# ============================================

WORKSHEETS_CONFIG = {
    # ============================================
    # 病人資料（後台完整版）
    # ============================================
    "Patients": [
        # 基本資料
        "patient_id", "name", "phone", "password", "password_hash",
        "birth_date", "age", "gender", "id_number",
        "emergency_contact", "emergency_phone",
        # 診斷資訊
        "diagnosis", "pathology", "clinical_stage", "pathological_stage", 
        "tumor_location", "tumor_size", "histology_type",
        # 手術資訊
        "surgery_type", "surgery_date", "surgery_approach", "resection_extent",
        "lymph_node_dissection", "surgical_margin", "complications",
        # 治療資訊
        "adjuvant_chemo", "adjuvant_radio", "target_therapy", "immunotherapy",
        "treatment_status", "treatment_notes",
        # 共病症與風險
        "comorbidities", "smoking_history", "risk_level",
        # 功能狀態
        "ecog_ps", "kps_score",
        # 系統欄位
        "status", "post_op_day", "consent_agreed", "consent_time", 
        "registered_at", "last_login",
        "notes"
    ],
    
    # ============================================
    # 症狀回報（v2.0 - 完整個別症狀）
    # ============================================
    "Reports": [
        # 基本資訊
        "report_id", "patient_id", "patient_name", 
        "date", "timestamp", "report_method",
        
        # 個別症狀分數（0-10，對應 MDASI-LC）
        "overall_score",
        "pain_score",
        "fatigue_score",
        "dyspnea_score",
        "cough_score",
        "sleep_score",
        "appetite_score",
        "mood_score",
        
        # 個別症狀描述
        "pain_description",
        "fatigue_description",
        "dyspnea_description",
        "cough_description",
        "sleep_description",
        "appetite_description",
        "mood_description",
        
        # 安全檢查
        "has_fever",
        "has_wound_issue",
        "has_blood_in_sputum",
        
        # 開放式問題
        "open_ended_1",
        "open_ended_2",
        "additional_notes",
        
        # 統計欄位
        "avg_score",
        "max_score_item",
        "messages_count",
        
        # AI 分析
        "symptoms_json",
        "conversation",
        "ai_summary",
        
        # 警示與處理
        "alert_level",
        "alert_handled",
        "handled_by",
        "handled_time",
        "handling_action",
        "handling_notes"
    ],
    
    # ============================================
    # 對話記錄（新增 - 對應病人端）
    # ============================================
    "Conversations": [
        "message_id",
        "session_id",
        "patient_id",
        "role",
        "content",
        "source",
        "input_method",
        "template_id",
        "detected_intent",
        "detected_emotion",
        "detected_urgency",
        "timestamp",
        # 標註欄位
        "annotated_intent",
        "annotated_emotion",
        "annotated_entities",
        "annotator_id",
        "annotation_time",
        "needs_review"
    ],
    
    # ============================================
    # 成就記錄（新增 - 對應病人端）
    # ============================================
    "Achievements": [
        "record_id",
        "patient_id",
        "patient_name",
        "achievement_id",
        "achievement_name",
        "achievement_type",
        "unlocked_date",
        "points_earned"
    ],
    
    # ============================================
    # 開放式問題回應（新增）
    # ============================================
    "OpenEndedResponses": [
        "response_id",
        "patient_id",
        "report_id",
        "question_id",
        "question_text",
        "question_category",
        "response_text",
        "input_method",
        "word_count",
        "detected_symptoms",
        "detected_emotion",
        "response_time"
    ],
    
    # ============================================
    # 順從度追蹤（新增）
    # ============================================
    "Compliance": [
        "record_id",
        "patient_id",
        "patient_name",
        "date",
        "expected_report",
        "actual_report",
        "reminder_level",
        "reminder_sent",
        "reminder_sent_time",
        "response_received"
    ],
    
    # ============================================
    # 衛教推播
    # ============================================
    "Education": [
        "push_id", "patient_id", "patient_name", "material_id", "material_title",
        "category", "push_type", "pushed_by", "pushed_at",
        "read_at", "status"
    ],
    
    # ============================================
    # 介入紀錄
    # ============================================
    "Interventions": [
        "intervention_id", "patient_id", "patient_name", "date", "timestamp",
        "intervention_type", "intervention_category", "method", "duration", 
        "problem_addressed", "content", "pre_symptom_score", "post_symptom_score",
        "outcome", "satisfaction", "referral", "referral_status", "follow_up_date",
        "created_by", "notes"
    ],
    
    # ============================================
    # 追蹤排程
    # ============================================
    "Schedules": [
        "schedule_id", "patient_id", "patient_name", "schedule_type",
        "scheduled_date", "scheduled_time", "location", "provider",
        "reminder_sent", "status", "result", "notes", "created_by", "created_at"
    ],
    
    # ============================================
    # 檢查結果
    # ============================================
    "LabResults": [
        "lab_id", "patient_id", "patient_name", "test_date", "test_type",
        "cea", "cyfra211", "scc", "nse", "other_markers",
        "wbc", "hgb", "plt", "creatinine", "ast", "alt",
        "imaging_type", "imaging_result", "imaging_comparison",
        "notes", "created_by"
    ],
    
    # ============================================
    # 功能狀態評估
    # ============================================
    "FunctionalAssessments": [
        "assessment_id", "patient_id", "patient_name", "assessment_date",
        "ecog_ps", "kps_score",
        "physical_function", "role_function", "emotional_function",
        "cognitive_function", "social_function", "global_qol",
        "notes", "created_by"
    ],
    
    # ============================================
    # 問題清單
    # ============================================
    "Problems": [
        "problem_id", "patient_id", "patient_name", "identified_date",
        "problem_category", "problem_description", "severity", "status",
        "goal", "target_date", "resolved_date", "created_by", "notes"
    ]
}


def get_connection():
    """取得 Google Sheets 連線"""
    try:
        credentials_dict = dict(st.secrets["gcp_service_account"])
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
        credentials = Credentials.from_service_account_info(credentials_dict, scopes=scopes)
        client = gspread.authorize(credentials)
        spreadsheet_id = st.secrets.get("spreadsheet_id", "")
        return client.open_by_key(spreadsheet_id)
    except Exception as e:
        st.error(f"連線失敗: {e}")
        return None


def check_and_update_worksheet(spreadsheet, sheet_name, required_columns):
    """檢查並更新工作表"""
    results = {
        "status": "unknown",
        "existing_columns": [],
        "added_columns": [],
        "message": ""
    }
    
    try:
        # 嘗試取得工作表
        try:
            worksheet = spreadsheet.worksheet(sheet_name)
            results["status"] = "exists"
            
            # 取得現有欄位
            existing_headers = worksheet.row_values(1)
            results["existing_columns"] = existing_headers
            
            # 找出缺少的欄位
            missing_columns = [col for col in required_columns if col not in existing_headers]
            
            if missing_columns:
                # 新增缺少的欄位
                start_col = len(existing_headers) + 1
                for i, col in enumerate(missing_columns):
                    worksheet.update_cell(1, start_col + i, col)
                results["added_columns"] = missing_columns
                results["message"] = f"新增 {len(missing_columns)} 個欄位"
            else:
                results["message"] = "欄位完整，無需更新"
                
        except gspread.WorksheetNotFound:
            # 建立新工作表
            worksheet = spreadsheet.add_worksheet(title=sheet_name, rows=1000, cols=len(required_columns))
            worksheet.append_row(required_columns)
            results["status"] = "created"
            results["added_columns"] = required_columns
            results["message"] = f"新建工作表，包含 {len(required_columns)} 個欄位"
            
    except Exception as e:
        results["status"] = "error"
        results["message"] = str(e)
    
    return results


def main():
    st.set_page_config(
        page_title="AI-CARE Lung - Sheets 設定 v2.0",
        page_icon="⚙️",
        layout="wide"
    )
    
    st.title("⚙️ Google Sheets 初始化/更新工具 v2.0")
    
    st.markdown("""
    ### 🆕 v2.0 更新內容
    
    此工具會檢查您的 Google Sheets 並確保前後台資料結構一致：
    
    | 工作表 | 說明 | 狀態 |
    |--------|------|------|
    | **Reports** | 新增 7 項個別症狀分數 + 描述欄位 | 🔄 更新 |
    | **Conversations** | 對話記錄（對應病人端） | 🆕 新增 |
    | **Achievements** | 成就記錄（遊戲化系統） | 🆕 新增 |
    | **OpenEndedResponses** | 開放式問題回應 | 🆕 新增 |
    | **Compliance** | 順從度追蹤 | 🆕 新增 |
    
    ---
    """)
    
    # 連線測試
    st.markdown("### 1️⃣ 連線測試")
    
    spreadsheet = get_connection()
    
    if spreadsheet:
        st.success(f"✅ 成功連線到: {spreadsheet.title}")
        st.info(f"📋 Spreadsheet ID: {spreadsheet.id}")
    else:
        st.error("❌ 無法連線，請檢查 secrets 設定")
        st.stop()
    
    # 顯示目前狀態
    st.markdown("### 2️⃣ 目前工作表狀態")
    
    existing_sheets = [ws.title for ws in spreadsheet.worksheets()]
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**現有工作表：**")
        for sheet in existing_sheets:
            if sheet in WORKSHEETS_CONFIG:
                st.write(f"✅ {sheet}")
            else:
                st.write(f"📄 {sheet} (非系統工作表)")
    
    with col2:
        st.markdown("**需要的工作表：**")
        for sheet in WORKSHEETS_CONFIG.keys():
            if sheet in existing_sheets:
                st.write(f"✅ {sheet}")
            else:
                st.write(f"🆕 {sheet} (將新建)")
    
    # 新增工作表預覽
    st.markdown("### 📊 新增/更新欄位預覽")
    
    preview_tabs = st.tabs(["Reports (更新)", "Conversations (新增)", "Achievements (新增)", "其他"])
    
    with preview_tabs[0]:
        st.markdown("#### Reports 工作表 - 新增的症狀欄位")
        new_report_cols = [
            "report_method", "pain_score", "fatigue_score", "dyspnea_score", 
            "cough_score", "sleep_score", "appetite_score", "mood_score",
            "pain_description", "fatigue_description", "dyspnea_description",
            "cough_description", "sleep_description", "appetite_description", "mood_description",
            "has_fever", "has_wound_issue", "has_blood_in_sputum",
            "open_ended_1", "open_ended_2", "additional_notes", "avg_score", "max_score_item"
        ]
        st.code(", ".join(new_report_cols))
    
    with preview_tabs[1]:
        st.markdown("#### Conversations 工作表 - 對話記錄")
        st.code(", ".join(WORKSHEETS_CONFIG["Conversations"]))
        st.info("💡 此工作表用於儲存病人與 AI 的完整對話記錄，支援 NLP 標註訓練")
    
    with preview_tabs[2]:
        st.markdown("#### Achievements 工作表 - 成就記錄")
        st.code(", ".join(WORKSHEETS_CONFIG["Achievements"]))
        st.info("💡 此工作表用於追蹤病人解鎖的成就，支援遊戲化激勵機制")
    
    with preview_tabs[3]:
        st.markdown("#### 其他新增工作表")
        st.markdown("**OpenEndedResponses**")
        st.code(", ".join(WORKSHEETS_CONFIG["OpenEndedResponses"]))
        st.markdown("**Compliance**")
        st.code(", ".join(WORKSHEETS_CONFIG["Compliance"]))
    
    # 執行更新
    st.markdown("### 3️⃣ 執行更新")
    
    col1, col2 = st.columns(2)
    
    with col1:
        run_full = st.button("🚀 完整更新（所有工作表）", type="primary", use_container_width=True)
    
    with col2:
        run_new_only = st.button("🆕 只新增缺少的工作表", use_container_width=True)
    
    if run_full or run_new_only:
        st.markdown("---")
        
        progress = st.progress(0)
        status_container = st.empty()
        
        results_summary = []
        
        sheets_to_process = WORKSHEETS_CONFIG.keys()
        if run_new_only:
            sheets_to_process = [s for s in WORKSHEETS_CONFIG.keys() if s not in existing_sheets]
        
        for i, sheet_name in enumerate(sheets_to_process):
            progress.progress((i + 1) / len(list(sheets_to_process)))
            status_container.info(f"正在處理: {sheet_name}...")
            
            result = check_and_update_worksheet(spreadsheet, sheet_name, WORKSHEETS_CONFIG[sheet_name])
            result["sheet_name"] = sheet_name
            results_summary.append(result)
        
        status_container.success("✅ 處理完成！")
        
        # 顯示結果
        st.markdown("### 📋 更新報告")
        
        for result in results_summary:
            sheet_name = result["sheet_name"]
            
            if result["status"] == "created":
                st.success(f"🆕 **{sheet_name}**: {result['message']}")
            elif result["status"] == "exists" and result["added_columns"]:
                st.warning(f"➕ **{sheet_name}**: {result['message']}")
                with st.expander(f"查看新增的欄位"):
                    st.write(result["added_columns"])
            elif result["status"] == "exists":
                st.info(f"✅ **{sheet_name}**: {result['message']}")
            else:
                st.error(f"❌ **{sheet_name}**: {result['message']}")
        
        # 統計
        st.markdown("---")
        created = len([r for r in results_summary if r["status"] == "created"])
        updated = len([r for r in results_summary if r["status"] == "exists" and r["added_columns"]])
        unchanged = len([r for r in results_summary if r["status"] == "exists" and not r["added_columns"]])
        
        col1, col2, col3 = st.columns(3)
        col1.metric("🆕 新建工作表", created)
        col2.metric("➕ 更新工作表", updated)
        col3.metric("✅ 無需更新", unchanged)
        
        st.balloons()
    
    # 欄位參考
    st.markdown("### 4️⃣ 完整欄位參考")
    
    with st.expander("查看所有工作表欄位定義"):
        for sheet_name, columns in WORKSHEETS_CONFIG.items():
            is_new = sheet_name not in existing_sheets
            badge = "🆕 新增" if is_new else ""
            st.markdown(f"**{sheet_name}** ({len(columns)} 欄位) {badge}")
            st.code(", ".join(columns))
            st.markdown("---")
    
    # 前後台對應說明
    st.markdown("### 5️⃣ 前後台資料對應")
    
    st.markdown("""
    | 病人端欄位 | 後台欄位 | 說明 |
    |-----------|---------|------|
    | 疼痛分數 | pain_score | 0-10 分 |
    | 疲勞分數 | fatigue_score | 0-10 分 |
    | 呼吸困難分數 | dyspnea_score | 0-10 分 |
    | 咳嗽分數 | cough_score | 0-10 分 |
    | 睡眠分數 | sleep_score | 0-10 分 |
    | 食慾分數 | appetite_score | 0-10 分 |
    | 心情分數 | mood_score | 0-10 分 |
    | 回報方式 | report_method | ai_chat / questionnaire / voice |
    | 發燒 | has_fever | Y/N |
    | 傷口異常 | has_wound_issue | Y/N |
    """)


if __name__ == "__main__":
    main()

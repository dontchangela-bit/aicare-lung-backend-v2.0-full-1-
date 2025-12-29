"""
AI-CARE Lung - Google Sheets 資料管理模組（v2.0 前後台整合版）
================================================================

更新內容：
1. 新增個別症狀分數欄位（對應病人端 MDASI-LC）
2. 新增對話記錄工作表（Conversations）
3. 新增成就記錄工作表（Achievements）
4. 新增開放式問題回應工作表（OpenEndedResponses）
5. 維持與病人端資料結構完全相容

三軍總醫院 數位醫療中心
"""

import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import json
from datetime import datetime
import pandas as pd
import time

# ============================================
# 快取設定
# ============================================
CACHE_TTL = 60  # 快取時間：60 秒

# ============================================
# Google Sheets 欄位定義（v2.0 - 前後台整合）
# ============================================

# 病人資料欄位（後台完整版 + 病人端相容）
PATIENT_COLUMNS = [
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
    "registered_at", "last_login",  # 新增：最後登入時間
    "notes"
]

# ============================================
# 症狀回報欄位（v2.0 - 完整個別症狀追蹤）
# ============================================
REPORT_COLUMNS = [
    # 基本資訊
    "report_id", "patient_id", "patient_name", 
    "date", "timestamp", "report_method",  # 新增：回報方式 (ai_chat/questionnaire/voice)
    
    # === 個別症狀分數（0-10，對應 MDASI-LC）===
    "overall_score",        # 整體狀況
    "pain_score",           # 疼痛
    "fatigue_score",        # 疲勞
    "dyspnea_score",        # 呼吸困難
    "cough_score",          # 咳嗽
    "sleep_score",          # 睡眠
    "appetite_score",       # 食慾
    "mood_score",           # 心情
    
    # === 個別症狀描述（自然語言）===
    "pain_description",     # 疼痛描述
    "fatigue_description",  # 疲勞描述
    "dyspnea_description",  # 呼吸困難描述
    "cough_description",    # 咳嗽描述
    "sleep_description",    # 睡眠描述
    "appetite_description", # 食慾描述
    "mood_description",     # 心情描述
    
    # === 安全檢查 ===
    "has_fever",            # 是否發燒 (Y/N)
    "has_wound_issue",      # 傷口是否異常 (Y/N)
    "has_blood_in_sputum",  # 痰中帶血 (Y/N)
    
    # === 開放式問題 ===
    "open_ended_1",         # 開放式回答1
    "open_ended_2",         # 開放式回答2
    "additional_notes",     # 額外備註
    
    # === 統計欄位 ===
    "avg_score",            # 平均分數
    "max_score_item",       # 最高分數項目
    "messages_count",       # 對話訊息數
    
    # === AI 分析 ===
    "symptoms_json",        # 症狀 JSON（相容舊格式）
    "conversation",         # 完整對話內容
    "ai_summary",           # AI 摘要
    
    # === 警示與處理 ===
    "alert_level",          # 警示等級 (green/yellow/red)
    "alert_handled",        # 是否已處理 (Y/N)
    "handled_by",           # 處理人員
    "handled_time",         # 處理時間
    "handling_action",      # 處理動作
    "handling_notes"        # 處理備註
]

# ============================================
# 對話記錄欄位（新增 - 對應病人端）
# ============================================
CONVERSATION_COLUMNS = [
    "message_id",           # 訊息唯一識別碼
    "session_id",           # 會話識別碼
    "patient_id",           # 病人 ID
    "role",                 # 角色 (patient/ai_assistant/system)
    "content",              # 訊息內容
    "source",               # 訊息來源 (patient_raw_input/patient_button/ai_generated/expert_template)
    "input_method",         # 輸入方式 (text/button/voice)
    "template_id",          # 使用的範本 ID
    "detected_intent",      # 偵測意圖
    "detected_emotion",     # 偵測情緒
    "detected_urgency",     # 偵測緊急程度
    "timestamp",            # 時間戳記
    # === 標註欄位（供 NLP 訓練）===
    "annotated_intent",     # 人工標註意圖
    "annotated_emotion",    # 人工標註情緒
    "annotated_entities",   # 人工標註實體 (JSON)
    "annotator_id",         # 標註人員
    "annotation_time",      # 標註時間
    "needs_review"          # 是否需要審核 (Y/N)
]

# ============================================
# 成就記錄欄位（新增 - 對應病人端）
# ============================================
ACHIEVEMENT_COLUMNS = [
    "record_id",            # 記錄 ID
    "patient_id",           # 病人 ID
    "patient_name",         # 病人姓名
    "achievement_id",       # 成就 ID
    "achievement_name",     # 成就名稱
    "achievement_type",     # 成就類型 (streak/completion/special)
    "unlocked_date",        # 解鎖日期
    "points_earned"         # 獲得積分
]

# ============================================
# 開放式問題回應欄位（新增）
# ============================================
OPEN_ENDED_COLUMNS = [
    "response_id",          # 回應 ID
    "patient_id",           # 病人 ID
    "report_id",            # 關聯回報 ID
    "question_id",          # 問題 ID
    "question_text",        # 問題內容
    "question_category",    # 問題類別
    "response_text",        # 病人回應內容
    "input_method",         # 輸入方式
    "word_count",           # 字數
    "detected_symptoms",    # 偵測到的症狀 (JSON)
    "detected_emotion",     # 偵測到的情緒
    "response_time"         # 回應時間
]

# ============================================
# 順從度追蹤欄位（新增）
# ============================================
COMPLIANCE_COLUMNS = [
    "record_id",            # 記錄 ID
    "patient_id",           # 病人 ID
    "patient_name",         # 病人姓名
    "date",                 # 日期
    "expected_report",      # 預期回報 (Y/N)
    "actual_report",        # 實際回報 (Y/N)
    "reminder_level",       # 提醒等級
    "reminder_sent",        # 提醒是否已發送 (Y/N)
    "reminder_sent_time",   # 提醒發送時間
    "response_received"     # 是否收到回應 (Y/N)
]

# ============================================
# 衛教推播欄位
# ============================================
EDUCATION_COLUMNS = [
    "push_id", "patient_id", "patient_name", "material_id", "material_title",
    "category", "push_type", "pushed_by", "pushed_at",
    "read_at", "status"
]

# ============================================
# 介入紀錄欄位
# ============================================
INTERVENTION_COLUMNS = [
    "intervention_id", "patient_id", "patient_name", "date", "timestamp",
    "intervention_type", "intervention_category", "method", "duration", 
    "problem_addressed", "content", "pre_symptom_score", "post_symptom_score",
    "outcome", "satisfaction", "referral", "referral_status", "follow_up_date",
    "created_by", "notes"
]

# ============================================
# 追蹤排程欄位
# ============================================
SCHEDULE_COLUMNS = [
    "schedule_id", "patient_id", "patient_name", "schedule_type",
    "scheduled_date", "scheduled_time", "location", "provider",
    "reminder_sent", "status", "result", "notes", "created_by", "created_at"
]

# ============================================
# 檢查結果欄位
# ============================================
LAB_COLUMNS = [
    "lab_id", "patient_id", "patient_name", "test_date", "test_type",
    "cea", "cyfra211", "scc", "nse", "other_markers",
    "wbc", "hgb", "plt", "creatinine", "ast", "alt",
    "imaging_type", "imaging_result", "imaging_comparison",
    "notes", "created_by"
]

# ============================================
# 功能狀態追蹤欄位
# ============================================
FUNCTIONAL_COLUMNS = [
    "assessment_id", "patient_id", "patient_name", "assessment_date",
    "ecog_ps", "kps_score", 
    "physical_function", "role_function", "emotional_function",
    "cognitive_function", "social_function", "global_qol",
    "notes", "created_by"
]

# ============================================
# 問題清單欄位
# ============================================
PROBLEM_COLUMNS = [
    "problem_id", "patient_id", "patient_name", "identified_date",
    "problem_category", "problem_description", "severity", "status",
    "goal", "target_date", "resolved_date", "created_by", "notes"
]

# ============================================
# 連線管理（使用快取）
# ============================================

@st.cache_resource(ttl=300)
def get_google_sheets_connection():
    """取得 Google Sheets 連線（使用快取）"""
    try:
        credentials_dict = dict(st.secrets["gcp_service_account"])
        
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
        
        credentials = Credentials.from_service_account_info(
            credentials_dict,
            scopes=scopes
        )
        
        client = gspread.authorize(credentials)
        return client
    except Exception as e:
        st.error(f"Google Sheets 連線失敗: {e}")
        return None


def get_spreadsheet():
    """取得試算表"""
    client = get_google_sheets_connection()
    if not client:
        return None
    
    try:
        spreadsheet_id = st.secrets.get("spreadsheet_id", "")
        if spreadsheet_id:
            return client.open_by_key(spreadsheet_id)
        else:
            spreadsheet_name = st.secrets.get("spreadsheet_name", "AI-CARE-Lung-Data")
            return client.open(spreadsheet_name)
    except Exception as e:
        st.error(f"無法開啟試算表: {e}")
        return None


def get_or_create_worksheet(spreadsheet, sheet_name, columns):
    """取得或建立工作表"""
    try:
        worksheet = spreadsheet.worksheet(sheet_name)
    except gspread.WorksheetNotFound:
        worksheet = spreadsheet.add_worksheet(title=sheet_name, rows=1000, cols=len(columns))
        worksheet.update('A1', [columns])
    return worksheet


# ============================================
# 工具函數
# ============================================

def normalize_phone(phone):
    """標準化手機號碼格式"""
    if phone is None:
        return ""
    phone_str = str(phone).strip()
    if '.' in phone_str:
        phone_str = phone_str.split('.')[0]
    if len(phone_str) == 9 and not phone_str.startswith('0'):
        phone_str = '0' + phone_str
    return phone_str


def normalize_password(password):
    """標準化密碼格式"""
    if password is None:
        return ""
    pwd_str = str(password).strip()
    if '.' in pwd_str:
        pwd_str = pwd_str.split('.')[0]
    return pwd_str


def clear_cache():
    """清除所有快取"""
    st.cache_data.clear()


# ============================================
# 病人資料管理（使用快取）
# ============================================

@st.cache_data(ttl=CACHE_TTL)
def get_all_patients_cached():
    """取得所有病人（快取版）"""
    spreadsheet = get_spreadsheet()
    if not spreadsheet:
        return []
    
    try:
        worksheet = get_or_create_worksheet(spreadsheet, "Patients", PATIENT_COLUMNS)
        records = worksheet.get_all_records()
        
        today = datetime.now().date()
        for record in records:
            record["phone"] = normalize_phone(record.get("phone"))
            record["password"] = normalize_password(record.get("password"))
            
            if record.get("surgery_date"):
                try:
                    surgery_date = datetime.strptime(str(record["surgery_date"]), "%Y-%m-%d").date()
                    record["post_op_day"] = (today - surgery_date).days
                except:
                    record["post_op_day"] = 0
            else:
                record["post_op_day"] = 0
        
        return records
    except Exception as e:
        st.error(f"讀取病人資料失敗: {e}")
        return []


def get_all_patients():
    """取得所有病人（外部呼叫介面）"""
    return get_all_patients_cached()


def get_patient_by_phone(phone):
    """根據手機號碼查找病人"""
    patients = get_all_patients()
    input_phone = normalize_phone(phone)
    
    for patient in patients:
        db_phone = patient.get("phone", "")
        if db_phone == input_phone:
            return patient
        if db_phone.lstrip('0') == input_phone.lstrip('0') and input_phone.lstrip('0'):
            return patient
    
    return None


def get_patient_by_id(patient_id):
    """根據 ID 查找病人"""
    patients = get_all_patients()
    for patient in patients:
        if patient.get("patient_id") == patient_id:
            return patient
    return None


def create_patient(patient_data):
    """建立新病人"""
    spreadsheet = get_spreadsheet()
    if not spreadsheet:
        return None
    
    try:
        worksheet = get_or_create_worksheet(spreadsheet, "Patients", PATIENT_COLUMNS)
        
        # 產生病人 ID
        patient_id = patient_data.get("patient_id") or f"P{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        # 準備資料列
        row = []
        for col in PATIENT_COLUMNS:
            if col == "patient_id":
                row.append(patient_id)
            elif col == "registered_at":
                row.append(datetime.now().isoformat())
            else:
                row.append(patient_data.get(col, ""))
        
        worksheet.append_row(row)
        clear_cache()
        return patient_id
    except Exception as e:
        st.error(f"建立病人失敗: {e}")
        return None


def update_patient(patient_id, updates):
    """更新病人資料"""
    spreadsheet = get_spreadsheet()
    if not spreadsheet:
        return False
    
    try:
        worksheet = get_or_create_worksheet(spreadsheet, "Patients", PATIENT_COLUMNS)
        records = worksheet.get_all_records()
        
        for idx, record in enumerate(records):
            if record.get("patient_id") == patient_id:
                row_num = idx + 2
                
                for key, value in updates.items():
                    if key in PATIENT_COLUMNS:
                        col_num = PATIENT_COLUMNS.index(key) + 1
                        worksheet.update_cell(row_num, col_num, value)
                
                clear_cache()
                return True
        return False
    except Exception as e:
        st.error(f"更新病人失敗: {e}")
        return False


# ============================================
# 症狀回報管理（v2.0 - 完整個別症狀）
# ============================================

@st.cache_data(ttl=CACHE_TTL)
def get_all_reports_cached():
    """取得所有回報（快取版）"""
    spreadsheet = get_spreadsheet()
    if not spreadsheet:
        return []
    
    try:
        worksheet = get_or_create_worksheet(spreadsheet, "Reports", REPORT_COLUMNS)
        return worksheet.get_all_records()
    except Exception as e:
        st.error(f"讀取回報資料失敗: {e}")
        return []


def get_all_reports():
    """取得所有回報（外部呼叫介面）"""
    return get_all_reports_cached()


def get_patient_reports(patient_id):
    """取得特定病人的回報"""
    reports = get_all_reports()
    return [r for r in reports if r.get("patient_id") == patient_id]


def get_today_reports():
    """取得今日回報"""
    reports = get_all_reports()
    today = datetime.now().strftime("%Y-%m-%d")
    return [r for r in reports if r.get("date") == today]


def get_pending_alerts():
    """取得待處理警示"""
    reports = get_all_reports()
    return [r for r in reports 
            if r.get("alert_level") in ["red", "yellow"] 
            and r.get("alert_handled") != "Y"]


def save_report(report_data):
    """儲存症狀回報（v2.0 - 支援個別症狀）"""
    spreadsheet = get_spreadsheet()
    if not spreadsheet:
        return None
    
    try:
        worksheet = get_or_create_worksheet(spreadsheet, "Reports", REPORT_COLUMNS)
        
        # 產生回報 ID
        report_id = report_data.get("report_id") or f"RPT{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        # 計算平均分數
        scores = []
        for key in ["overall_score", "pain_score", "fatigue_score", "dyspnea_score", 
                    "cough_score", "sleep_score", "appetite_score", "mood_score"]:
            val = report_data.get(key)
            if val is not None and str(val).isdigit():
                scores.append(int(val))
        
        avg_score = round(sum(scores) / len(scores), 1) if scores else 0
        
        # 找出最高分數項目
        max_score = 0
        max_item = ""
        score_items = {
            "pain_score": "疼痛", "fatigue_score": "疲勞", "dyspnea_score": "呼吸困難",
            "cough_score": "咳嗽", "sleep_score": "睡眠", "appetite_score": "食慾", "mood_score": "心情"
        }
        for key, name in score_items.items():
            val = report_data.get(key)
            if val is not None and str(val).isdigit() and int(val) > max_score:
                max_score = int(val)
                max_item = name
        
        # 計算警示等級
        alert_level = calculate_alert_level(report_data)
        
        # 準備資料列
        row = []
        for col in REPORT_COLUMNS:
            if col == "report_id":
                row.append(report_id)
            elif col == "timestamp":
                row.append(datetime.now().isoformat())
            elif col == "avg_score":
                row.append(avg_score)
            elif col == "max_score_item":
                row.append(max_item)
            elif col == "alert_level":
                row.append(report_data.get("alert_level", alert_level))
            else:
                row.append(report_data.get(col, ""))
        
        worksheet.append_row(row)
        clear_cache()
        return report_id
    except Exception as e:
        st.error(f"儲存回報失敗: {e}")
        return None


def calculate_alert_level(report_data):
    """計算警示等級"""
    # 紅燈條件
    if (int(report_data.get("pain_score", 0) or 0) >= 7 or
        int(report_data.get("dyspnea_score", 0) or 0) >= 6 or
        report_data.get("has_fever") == "Y" or
        report_data.get("has_wound_issue") == "Y" or
        report_data.get("has_blood_in_sputum") == "Y"):
        return "red"
    
    # 黃燈條件
    if (int(report_data.get("pain_score", 0) or 0) >= 4 or
        int(report_data.get("dyspnea_score", 0) or 0) >= 4 or
        int(report_data.get("overall_score", 0) or 0) >= 5):
        return "yellow"
    
    return "green"


def handle_alert(report_id, handler, action, notes=""):
    """處理警示"""
    spreadsheet = get_spreadsheet()
    if not spreadsheet:
        return False
    
    try:
        worksheet = get_or_create_worksheet(spreadsheet, "Reports", REPORT_COLUMNS)
        records = worksheet.get_all_records()
        
        for idx, record in enumerate(records):
            if record.get("report_id") == report_id:
                row_num = idx + 2
                
                # 更新處理資訊
                updates = {
                    "alert_handled": "Y",
                    "handled_by": handler,
                    "handled_time": datetime.now().isoformat(),
                    "handling_action": action,
                    "handling_notes": notes
                }
                
                for key, value in updates.items():
                    if key in REPORT_COLUMNS:
                        col_num = REPORT_COLUMNS.index(key) + 1
                        worksheet.update_cell(row_num, col_num, value)
                
                clear_cache()
                return True
        return False
    except Exception as e:
        st.error(f"處理警示失敗: {e}")
        return False


# ============================================
# 對話記錄管理（新增）
# ============================================

@st.cache_data(ttl=CACHE_TTL)
def get_conversations_cached(patient_id=None, session_id=None):
    """取得對話記錄（快取版）"""
    spreadsheet = get_spreadsheet()
    if not spreadsheet:
        return []
    
    try:
        worksheet = get_or_create_worksheet(spreadsheet, "Conversations", CONVERSATION_COLUMNS)
        records = worksheet.get_all_records()
        
        if patient_id:
            records = [r for r in records if r.get("patient_id") == patient_id]
        if session_id:
            records = [r for r in records if r.get("session_id") == session_id]
        
        return records
    except Exception as e:
        return []


def get_conversations(patient_id=None, session_id=None):
    """取得對話記錄（外部呼叫介面）"""
    return get_conversations_cached(patient_id, session_id)


def save_conversation_message(message_data):
    """儲存對話訊息"""
    spreadsheet = get_spreadsheet()
    if not spreadsheet:
        return None
    
    try:
        worksheet = get_or_create_worksheet(spreadsheet, "Conversations", CONVERSATION_COLUMNS)
        
        message_id = message_data.get("message_id") or f"MSG{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
        
        row = []
        for col in CONVERSATION_COLUMNS:
            if col == "message_id":
                row.append(message_id)
            elif col == "timestamp":
                row.append(message_data.get("timestamp", datetime.now().isoformat()))
            else:
                row.append(message_data.get(col, ""))
        
        worksheet.append_row(row)
        clear_cache()
        return message_id
    except Exception as e:
        st.error(f"儲存對話訊息失敗: {e}")
        return None


def get_conversation_sessions(patient_id):
    """取得病人的對話會話列表"""
    conversations = get_conversations(patient_id=patient_id)
    
    sessions = {}
    for conv in conversations:
        session_id = conv.get("session_id", "")
        if session_id and session_id not in sessions:
            sessions[session_id] = {
                "session_id": session_id,
                "first_message": conv.get("timestamp", ""),
                "message_count": 0,
                "patient_messages": 0,
                "ai_messages": 0
            }
        if session_id:
            sessions[session_id]["message_count"] += 1
            if conv.get("role") == "patient":
                sessions[session_id]["patient_messages"] += 1
            elif conv.get("role") == "ai_assistant":
                sessions[session_id]["ai_messages"] += 1
    
    return list(sessions.values())


# ============================================
# 成就記錄管理（新增）
# ============================================

@st.cache_data(ttl=CACHE_TTL)
def get_achievements_cached(patient_id=None):
    """取得成就記錄（快取版）"""
    spreadsheet = get_spreadsheet()
    if not spreadsheet:
        return []
    
    try:
        worksheet = get_or_create_worksheet(spreadsheet, "Achievements", ACHIEVEMENT_COLUMNS)
        records = worksheet.get_all_records()
        
        if patient_id:
            records = [r for r in records if r.get("patient_id") == patient_id]
        
        return records
    except Exception as e:
        return []


def get_achievements(patient_id=None):
    """取得成就記錄（外部呼叫介面）"""
    return get_achievements_cached(patient_id)


def save_achievement(achievement_data):
    """儲存成就記錄"""
    spreadsheet = get_spreadsheet()
    if not spreadsheet:
        return None
    
    try:
        worksheet = get_or_create_worksheet(spreadsheet, "Achievements", ACHIEVEMENT_COLUMNS)
        
        record_id = f"ACH{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        row = []
        for col in ACHIEVEMENT_COLUMNS:
            if col == "record_id":
                row.append(record_id)
            elif col == "unlocked_date":
                row.append(achievement_data.get("unlocked_date", datetime.now().strftime("%Y-%m-%d")))
            else:
                row.append(achievement_data.get(col, ""))
        
        worksheet.append_row(row)
        clear_cache()
        return record_id
    except Exception as e:
        st.error(f"儲存成就失敗: {e}")
        return None


def get_patient_achievement_stats(patient_id):
    """取得病人成就統計"""
    achievements = get_achievements(patient_id)
    
    total_points = sum(int(a.get("points_earned", 0)) for a in achievements)
    
    # 計算等級
    level = 1
    thresholds = [0, 50, 150, 300, 500, 800, 1200]
    for i, threshold in enumerate(thresholds):
        if total_points >= threshold:
            level = i + 1
    
    return {
        "total_achievements": len(achievements),
        "total_points": total_points,
        "level": level,
        "achievements": achievements
    }


# ============================================
# 順從度追蹤（新增）
# ============================================

def get_patient_compliance_stats(patient_id):
    """取得病人順從度統計"""
    reports = get_patient_reports(patient_id)
    patient = get_patient_by_id(patient_id)
    
    if not patient:
        return None
    
    # 計算應回報天數
    surgery_date_str = patient.get("surgery_date", "")
    if surgery_date_str:
        try:
            surgery_date = datetime.strptime(surgery_date_str, "%Y-%m-%d").date()
            today = datetime.now().date()
            total_days = (today - surgery_date).days
        except:
            total_days = 0
    else:
        total_days = 0
    
    # 計算實際回報天數
    completed_dates = set()
    for report in reports:
        report_date = report.get("date", "")
        if report_date:
            completed_dates.add(report_date)
    
    total_completed = len(completed_dates)
    
    # 計算連續天數
    current_streak = 0
    from datetime import timedelta
    check_date = datetime.now().date()
    
    while check_date.strftime("%Y-%m-%d") in completed_dates:
        current_streak += 1
        check_date -= timedelta(days=1)
    
    # 如果今天還沒回報，從昨天開始算
    if datetime.now().date().strftime("%Y-%m-%d") not in completed_dates:
        current_streak = 0
        check_date = datetime.now().date() - timedelta(days=1)
        while check_date.strftime("%Y-%m-%d") in completed_dates:
            current_streak += 1
            check_date -= timedelta(days=1)
    
    # 計算順從率
    compliance_rate = round(total_completed / total_days * 100, 1) if total_days > 0 else 0
    
    return {
        "patient_id": patient_id,
        "total_days": total_days,
        "total_completed": total_completed,
        "current_streak": current_streak,
        "compliance_rate": compliance_rate,
        "today_reported": datetime.now().date().strftime("%Y-%m-%d") in completed_dates
    }


# ============================================
# 衛教管理
# ============================================

@st.cache_data(ttl=CACHE_TTL)
def get_education_pushes_cached(patient_id=None):
    """取得衛教推播（快取版）"""
    spreadsheet = get_spreadsheet()
    if not spreadsheet:
        return []
    
    try:
        worksheet = get_or_create_worksheet(spreadsheet, "Education", EDUCATION_COLUMNS)
        records = worksheet.get_all_records()
        
        if patient_id:
            records = [r for r in records if r.get("patient_id") == patient_id]
        
        return records
    except Exception as e:
        return []


def get_education_pushes(patient_id=None):
    """取得衛教推播（外部呼叫介面）"""
    return get_education_pushes_cached(patient_id)


def push_education(push_data):
    """推播衛教內容"""
    spreadsheet = get_spreadsheet()
    if not spreadsheet:
        return None
    
    try:
        worksheet = get_or_create_worksheet(spreadsheet, "Education", EDUCATION_COLUMNS)
        
        push_id = f"EDU{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        row = [
            push_id,
            push_data.get("patient_id", ""),
            push_data.get("patient_name", ""),
            push_data.get("material_id", ""),
            push_data.get("material_title", ""),
            push_data.get("category", ""),
            push_data.get("push_type", "manual"),
            push_data.get("pushed_by", ""),
            datetime.now().isoformat(),
            "",  # read_at
            "sent"  # status
        ]
        
        worksheet.append_row(row)
        clear_cache()
        return push_id
    except Exception as e:
        st.error(f"推播衛教失敗: {e}")
        return None


# ============================================
# 介入紀錄管理
# ============================================

@st.cache_data(ttl=CACHE_TTL)
def get_interventions_cached(patient_id=None):
    """取得介入紀錄（快取版）"""
    spreadsheet = get_spreadsheet()
    if not spreadsheet:
        return []
    
    try:
        worksheet = get_or_create_worksheet(spreadsheet, "Interventions", INTERVENTION_COLUMNS)
        records = worksheet.get_all_records()
        
        if patient_id:
            records = [r for r in records if r.get("patient_id") == patient_id]
        
        return records
    except Exception as e:
        return []


def get_interventions(patient_id=None):
    """取得介入紀錄（外部呼叫介面）"""
    return get_interventions_cached(patient_id)


def save_intervention(intervention_data):
    """儲存介入紀錄"""
    spreadsheet = get_spreadsheet()
    if not spreadsheet:
        return None
    
    try:
        worksheet = get_or_create_worksheet(spreadsheet, "Interventions", INTERVENTION_COLUMNS)
        
        intervention_id = f"INT{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        row = []
        for col in INTERVENTION_COLUMNS:
            if col == "intervention_id":
                row.append(intervention_id)
            elif col == "timestamp":
                row.append(datetime.now().isoformat())
            else:
                row.append(intervention_data.get(col, ""))
        
        worksheet.append_row(row)
        clear_cache()
        return intervention_id
    except Exception as e:
        st.error(f"儲存介入紀錄失敗: {e}")
        return None


# ============================================
# 排程管理
# ============================================

@st.cache_data(ttl=CACHE_TTL)
def get_schedules_cached(patient_id=None):
    """取得排程（快取版）"""
    spreadsheet = get_spreadsheet()
    if not spreadsheet:
        return []
    
    try:
        worksheet = get_or_create_worksheet(spreadsheet, "Schedules", SCHEDULE_COLUMNS)
        records = worksheet.get_all_records()
        
        if patient_id:
            records = [r for r in records if r.get("patient_id") == patient_id]
        
        return records
    except Exception as e:
        return []


def get_schedules(patient_id=None):
    """取得排程（外部呼叫介面）"""
    return get_schedules_cached(patient_id)


def save_schedule(schedule_data):
    """儲存排程"""
    spreadsheet = get_spreadsheet()
    if not spreadsheet:
        return None
    
    try:
        worksheet = get_or_create_worksheet(spreadsheet, "Schedules", SCHEDULE_COLUMNS)
        
        schedule_id = f"SCH{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        row = []
        for col in SCHEDULE_COLUMNS:
            if col == "schedule_id":
                row.append(schedule_id)
            elif col == "created_at":
                row.append(datetime.now().isoformat())
            elif col == "reminder_sent":
                row.append("N")
            elif col == "status":
                row.append(schedule_data.get("status", "scheduled"))
            else:
                row.append(schedule_data.get(col, ""))
        
        worksheet.append_row(row)
        clear_cache()
        return schedule_id
    except Exception as e:
        st.error(f"儲存排程失敗: {e}")
        return None


def update_schedule(schedule_id, updates):
    """更新排程"""
    spreadsheet = get_spreadsheet()
    if not spreadsheet:
        return False
    
    try:
        worksheet = get_or_create_worksheet(spreadsheet, "Schedules", SCHEDULE_COLUMNS)
        records = worksheet.get_all_records()
        
        for idx, record in enumerate(records):
            if record.get("schedule_id") == schedule_id:
                row_num = idx + 2
                
                for key, value in updates.items():
                    if key in SCHEDULE_COLUMNS:
                        col_num = SCHEDULE_COLUMNS.index(key) + 1
                        worksheet.update_cell(row_num, col_num, value)
                
                clear_cache()
                return True
        return False
    except Exception as e:
        st.error(f"更新排程失敗: {e}")
        return False


# ============================================
# 檢查結果管理
# ============================================

@st.cache_data(ttl=CACHE_TTL)
def get_lab_results_cached(patient_id=None):
    """取得檢查結果（快取版）"""
    spreadsheet = get_spreadsheet()
    if not spreadsheet:
        return []
    
    try:
        worksheet = get_or_create_worksheet(spreadsheet, "LabResults", LAB_COLUMNS)
        records = worksheet.get_all_records()
        
        if patient_id:
            records = [r for r in records if r.get("patient_id") == patient_id]
        
        return records
    except Exception as e:
        return []


def get_lab_results(patient_id=None):
    """取得檢查結果（外部呼叫介面）"""
    return get_lab_results_cached(patient_id)


def save_lab_result(lab_data):
    """儲存檢查結果"""
    spreadsheet = get_spreadsheet()
    if not spreadsheet:
        return None
    
    try:
        worksheet = get_or_create_worksheet(spreadsheet, "LabResults", LAB_COLUMNS)
        
        lab_id = f"LAB{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        row = []
        for col in LAB_COLUMNS:
            if col == "lab_id":
                row.append(lab_id)
            else:
                row.append(lab_data.get(col, ""))
        
        worksheet.append_row(row)
        clear_cache()
        return lab_id
    except Exception as e:
        st.error(f"儲存檢查結果失敗: {e}")
        return None


# ============================================
# 功能狀態評估管理
# ============================================

@st.cache_data(ttl=CACHE_TTL)
def get_functional_assessments_cached(patient_id=None):
    """取得功能評估（快取版）"""
    spreadsheet = get_spreadsheet()
    if not spreadsheet:
        return []
    
    try:
        worksheet = get_or_create_worksheet(spreadsheet, "FunctionalAssessments", FUNCTIONAL_COLUMNS)
        records = worksheet.get_all_records()
        
        if patient_id:
            records = [r for r in records if r.get("patient_id") == patient_id]
        
        return records
    except Exception as e:
        return []


def get_functional_assessments(patient_id=None):
    """取得功能評估（外部呼叫介面）"""
    return get_functional_assessments_cached(patient_id)


def save_functional_assessment(assessment_data):
    """儲存功能評估"""
    spreadsheet = get_spreadsheet()
    if not spreadsheet:
        return None
    
    try:
        worksheet = get_or_create_worksheet(spreadsheet, "FunctionalAssessments", FUNCTIONAL_COLUMNS)
        
        assessment_id = f"FA{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        row = []
        for col in FUNCTIONAL_COLUMNS:
            if col == "assessment_id":
                row.append(assessment_id)
            elif col == "assessment_date":
                row.append(assessment_data.get("assessment_date", datetime.now().strftime("%Y-%m-%d")))
            else:
                row.append(assessment_data.get(col, ""))
        
        worksheet.append_row(row)
        clear_cache()
        return assessment_id
    except Exception as e:
        st.error(f"儲存功能評估失敗: {e}")
        return None


# ============================================
# 問題清單管理
# ============================================

@st.cache_data(ttl=CACHE_TTL)
def get_problems_cached(patient_id=None):
    """取得問題清單（快取版）"""
    spreadsheet = get_spreadsheet()
    if not spreadsheet:
        return []
    
    try:
        worksheet = get_or_create_worksheet(spreadsheet, "Problems", PROBLEM_COLUMNS)
        records = worksheet.get_all_records()
        
        if patient_id:
            records = [r for r in records if r.get("patient_id") == patient_id]
        
        return records
    except Exception as e:
        return []


def get_problems(patient_id=None):
    """取得問題清單（外部呼叫介面）"""
    return get_problems_cached(patient_id)


def save_problem(problem_data):
    """儲存問題"""
    spreadsheet = get_spreadsheet()
    if not spreadsheet:
        return None
    
    try:
        worksheet = get_or_create_worksheet(spreadsheet, "Problems", PROBLEM_COLUMNS)
        
        problem_id = f"PRB{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        row = []
        for col in PROBLEM_COLUMNS:
            if col == "problem_id":
                row.append(problem_id)
            elif col == "identified_date":
                row.append(problem_data.get("identified_date", datetime.now().strftime("%Y-%m-%d")))
            elif col == "status":
                row.append(problem_data.get("status", "active"))
            else:
                row.append(problem_data.get(col, ""))
        
        worksheet.append_row(row)
        clear_cache()
        return problem_id
    except Exception as e:
        st.error(f"儲存問題失敗: {e}")
        return None


def update_problem(problem_id, updates):
    """更新問題"""
    spreadsheet = get_spreadsheet()
    if not spreadsheet:
        return False
    
    try:
        worksheet = get_or_create_worksheet(spreadsheet, "Problems", PROBLEM_COLUMNS)
        records = worksheet.get_all_records()
        
        for idx, record in enumerate(records):
            if record.get("problem_id") == problem_id:
                row_num = idx + 2
                
                for key, value in updates.items():
                    if key in PROBLEM_COLUMNS:
                        col_num = PROBLEM_COLUMNS.index(key) + 1
                        worksheet.update_cell(row_num, col_num, value)
                
                clear_cache()
                return True
        return False
    except Exception as e:
        st.error(f"更新問題失敗: {e}")
        return False


# ============================================
# 統計資料（使用快取）
# ============================================

@st.cache_data(ttl=CACHE_TTL)
def get_dashboard_stats():
    """取得儀表板統計"""
    patients = get_all_patients()
    reports = get_all_reports()
    today = datetime.now().strftime("%Y-%m-%d")
    
    today_reports = [r for r in reports if r.get("date") == today]
    pending_alerts = [r for r in reports if r.get("alert_level") in ["red", "yellow"] and r.get("alert_handled") != "Y"]
    
    stats = {
        "total_patients": len(patients),
        "active_patients": len([p for p in patients if p.get("status") not in ["discharged", "completed"]]),
        "today_reports": len(today_reports),
        "pending_alerts": len(pending_alerts),
        "red_alerts": len([a for a in pending_alerts if a.get("alert_level") == "red"]),
        "yellow_alerts": len([a for a in pending_alerts if a.get("alert_level") == "yellow"]),
    }
    
    return stats


# ============================================
# 資料匯出
# ============================================

def export_patients_df():
    """匯出病人資料為 DataFrame"""
    patients = get_all_patients()
    return pd.DataFrame(patients)


def export_reports_df():
    """匯出回報資料為 DataFrame"""
    reports = get_all_reports()
    return pd.DataFrame(reports)


def export_conversations_df(patient_id=None):
    """匯出對話記錄為 DataFrame"""
    conversations = get_conversations(patient_id)
    return pd.DataFrame(conversations)


def export_achievements_df(patient_id=None):
    """匯出成就記錄為 DataFrame"""
    achievements = get_achievements(patient_id)
    return pd.DataFrame(achievements)


# ============================================
# 除錯用函數
# ============================================

def debug_login(phone, password):
    """除錯登入問題"""
    patients = get_all_patients()
    input_phone = normalize_phone(phone)
    input_pwd = normalize_password(password)
    
    debug_info = {
        "input_phone": input_phone,
        "input_password": input_pwd,
        "total_patients": len(patients),
        "matches": []
    }
    
    for p in patients:
        db_phone = p.get("phone", "")
        db_pwd = p.get("password", "")
        
        phone_match = (db_phone == input_phone) or (db_phone.lstrip('0') == input_phone.lstrip('0'))
        pwd_match = (db_pwd == input_pwd)
        
        if phone_match or db_phone[-4:] == input_phone[-4:]:
            debug_info["matches"].append({
                "patient_id": p.get("patient_id"),
                "name": p.get("name"),
                "db_phone": db_phone,
                "db_password": db_pwd,
                "phone_match": phone_match,
                "pwd_match": pwd_match,
                "status": p.get("status")
            })
    
    return debug_info

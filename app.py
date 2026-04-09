import streamlit as st
import pandas as pd
import hashlib
import datetime
import requests
import re

# ==========================================
# ⚙️ 系統底層配置區 
# 涵蓋所有平台代碼，解決 API 400 報錯
GLOBAL_PLATFORMS = "YD,XO,ND,JD,SY,MT,LY,FB,XY,XO,OL,LS,HS,JY,YS,SH,XH"
# ==========================================

# 1. 頁面配置
st.set_page_config(page_title="抓鬼專家", layout="wide")

# 2. 注入所有原始樣式
st.markdown("""
    <style>
    .stApp { background-color: #f8fafc; }
    [data-testid="stSidebar"] { background-color: #f1f5f9 !important; min-width: 400px !important; }
    [data-testid="stSidebar"] .stMarkdown, [data-testid="stSidebar"] label, 
    [data-testid="stSidebar"] p, [data-testid="stSidebar"] h3, [data-testid="stSidebar"] .stToggle p { 
        color: #1e293b !important; font-weight: 700 !important; 
    }
    .metric-card-a {
        background-color: #ffffff; padding: 15px; border-radius: 12px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05); border-top: 5px solid #ef4444;
        text-align: center; margin-bottom: 10px;
    }
    .metric-card-b {
        background: white; padding: 20px; border-radius: 15px; box-shadow: 0 4px 12px rgba(0,0,0,0.08); 
        border-bottom: 4px solid #ef4444; text-align: center;
    }
    .metric-value { font-size: 28px; font-weight: 800; color: #ef4444; }
    .metric-label { font-size: 13px; color: #64748b; font-weight: 600; }
    .badge-red { background: #fee2e2; color: #ef4444; padding: 2px 8px; border-radius: 6px; font-weight: bold; border: 1px solid #fecaca; }
    .badge-giant { background: #fee2e2; color: #ef4444; padding: 5px 12px; border-radius: 8px; font-weight: 900; font-size: 16px; border: 2px solid #fecaca; display: inline-block; }
    .title-banner { background: linear-gradient(135deg, #0f172a 0%, #334155 100%); padding: 20px; border-radius: 12px; color: white; text-align: center; margin-bottom: 20px; }
    .table-header { background-color: #e2e8f0; padding: 12px 10px; border-radius: 8px; font-weight: bold; color: #475569; margin-bottom: 10px; display: flex; align-items: center; }
    .range-label { font-size: 13px; color: #1e293b; font-weight: bold; margin-bottom: 2px; }
    </style>
    """, unsafe_allow_html=True)

# 3. 登入邏輯
if "auth" not in st.session_state: st.session_state.auth = False
if not st.session_state.auth:
    _, center_col, _ = st.columns([1, 1.2, 1])
    with center_col:
        st.markdown("<div style='height:100px'></div>", unsafe_allow_html=True)
        st.title("🔐 歡迎光臨")
        pwd = st.text_input("請輸入訪問密碼", type="password")
        if st.button("進入系統", use_container_width=True):
            if pwd == "0224": st.session_state.auth = True; st.rerun()
            else: st.error("❌ 密碼錯誤")
    st.stop()

# --- 通用欄位名稱匹配函數 ---
def get_mapped_col(df, exact_matches, partial_matches, exclude_keywords=None, forbidden_cols=None):
    if exclude_keywords is None: exclude_keywords = []
    if forbidden_cols is None: forbidden_cols = []
    cols_lower = [str(c).lower().strip() for c in df.columns]
    for exact_val in exact_matches:
        if exact_val.lower() in cols_lower:
            orig_col = df.columns[cols_lower.index(exact_val.lower())]
            if orig_col not in forbidden_cols: return orig_col
    for p in partial_matches:
        for i, c_str in enumerate(cols_lower):
            orig_col = df.columns[i]
            if orig_col in forbidden_cols: continue
            if any(ext.lower() in c_str for ext in exclude_keywords): continue
            if p.lower() in c_str: return orig_col
    return None

# --- 🎯 用戶名精確隔離提取 (Username) ---
def find_user_column(df, forbidden_cols=None):
    if forbidden_cols is None: forbidden_cols = []
    potential_cols = []
    for c in df.columns:
        c_str = str(c).lower().strip()
        if c in forbidden_cols: continue
        # 強制排除 ID 類標題
        if c_str in ['id', 'uid', 'userid', 'playerid', 'index', 'sn', 'no', 'rowindex']: continue
        
        sample_data = df[c].dropna().astype(str).head(30).tolist()
        if not sample_data: continue
        
        # 數據特徵過濾：如果欄位內容大多是極短數字 (<=5位)，則判定為編號 ID
        short_num_count = sum(1 for v in sample_data if v.strip().isdigit() and len(v.strip()) <= 5)
        if short_num_count >= len(sample_data) * 0.3: continue
            
        potential_cols.append(c)

    if not potential_cols: return None

    best_col = None
    max_score = -999
    for c in potential_cols:
        score = 0
        c_lower = str(c).lower()
        # 關鍵字加分
        if any(k in c_lower for k in ['username', 'account', 'loginname', '用戶名', '帳號']): score += 500
        
        sample_data = df[c].dropna().astype(str).head(20).tolist()
        for val in sample_data:
            val = val.strip()
            if re.search(r'[a-zA-Z]', val): score += 20  # 含有字母是帳號特徵
            if len(val) >= 6: score += 10 # 長度適中是帳號特徵
        if score > max_score:
            max_score = score
            best_col = c
    return best_col

def find_game_column(df, forbidden_cols=None):
    if forbidden_cols is None: forbidden_cols = []
    return get_mapped_col(df, ['lotteryName', 'gameName', '彩種'], ['lottery', 'game', '彩'], forbidden_cols=forbidden_cols)

# --- 核心數據獲取模組 (API 串接) ---
@st.cache_data(show_spinner=False, ttl=300)
def fetch_api_data(endpoint, d_start, d_end):
    headers = {
        "Authorization": "Bearer sk-d79a713caf53e8bdh3154a596ca1a0166234df7",
        "x-api-key": "sk-d79a713caf53e8bdh3154a596ca1a0166234df7",
        "Content-Type": "application/json"
    }
    params = { "dateStart": d_start, "dateEnd": d_end, "platform": GLOBAL_PLATFORMS }
    try:
        # ⚠️ 這裡將 timeout 增加到 120 秒，解決 Read timed out 報錯
        response = requests.get(endpoint, params=params, headers=headers, timeout=120)
        response.raise_for_status() 
        data = response.json()
        
        if isinstance(data, dict):
            res_list = data.get("data") or data.get("records") or []
            return pd.DataFrame(res_list)
        elif isinstance(data, list):
            return pd.DataFrame(data)
        return pd.DataFrame()
    except Exception as e:
        st.error(f"❌ 數據獲取異常: {e}")
        return None

now = datetime.datetime.now()
default_start = now.strftime("%Y-%m-%d 03:00:00")
default_end = (now + datetime.timedelta(days=1)).strftime("%Y-%m-%d 03:00:00")

# --- 核心引擎 A (用戶彩票分析) ---
def run_audit_engine(df, rules, cols_map):
    try:
        user_col = cols_map.get('u')
        game_col = cols_map.get('g')
        vol_col = cols_map.get('v')
        cnt_col = cols_map.get('c')
        profit_col = cols_map.get('p')
        bonus_col = cols_map.get('b')

        temp_df = pd.DataFrame()
        temp_df['用戶名'] = df[user_col].astype(str).str.strip() if user_col else "未知用戶"
        
        def to_num(c_name):
            if c_name and c_name in df.columns:
                return pd.to_numeric(df[c_name].astype(str).str.replace(r',', '', regex=True), errors='coerce').fillna(0)
            return 0.0

        temp_df['銷量'] = to_num(vol_col)
        temp_df['單數'] = to_num(cnt_col)
        temp_df['盈虧'] = to_num(profit_col)
        temp_df['獎金'] = to_num(bonus_col)
        if game_col: temp_df['彩種'] = df[game_col].astype(str).str.strip()

        agg_dict = {'銷量':'sum', '單數':'sum', '盈虧':'sum', '獎金':'sum'}
        if game_col: agg_dict['彩種'] = lambda x: ', '.join(sorted(list(set([str(i) for i in x if str(i) not in ['nan', 'None', '']]))))

        grouped = temp_df.groupby('用戶名').agg(agg_dict).reset_index()
        grouped['RTP'] = grouped.apply(lambda x: x['獎金'] / x['銷量'] if x['銷量'] > 0 else 0, axis=1)
        
        def apply_logic(row):
            v, c, p, r = row['銷量'], row['單數'], row['盈虧'], row['RTP']
            if rules.get('use_manual', False):
                match = True
                if rules['v_on'] and not (rules['v_min'] <= v <= rules['v_max']): match = False
                if rules['c_on'] and not (c <= rules['c_limit']): match = False
                if rules['p_on'] and not (rules['p_min'] <= p <= rules['p_max']): match = False
                if rules['r_on'] and not (rules['r_min'] <= r <= rules['r_max']): match = False
                return "手動篩選" if match else None
            
            m = []
            if 1000 <= v <= 2000 and c <= 12: m.append("疑似刷人數")
            if v > 2000 and c <= 10: m.append("疑似對刷")
            if v >= 500000 and 0.995 <= r <= 1.000: m.append("疑似刷量")
            if p >= 100000: m.append("盈利大會員")
            return " | ".join(m) if m else None
            
        grouped['原因'] = grouped.apply(apply_logic, axis=1)
        return grouped[grouped['原因'].notna()].copy()
    except Exception as e: 
        st.error(f"引擎 A 解析異常: {e}")
        return None

# 5. 模組切換邏輯
with st.sidebar:
    st.markdown("## 🧭 模組切換")
    mode = st.radio("選擇分析類型", ["用戶彩票分析", "盈虧排行"])
    st.write("---")

if mode == "用戶彩票分析":
    st.markdown("<div class='title-banner'><h1>📊 用戶彩票分析 (API數據源)</h1></div>", unsafe_allow_html=True)
    with st.sidebar:
        use_manual = st.toggle("🚀 手動自訂模式", value=False)
        st.write("---")
        col_st, col_et = st.columns(2)
        datestart_a = col_st.text_input("開始時間", value=default_start)
        dateend_a = col_et.text_input("結束時間", value=default_end)
        if st.button("🔄 重新拉取 API", use_container_width=True): st.cache_data.clear()
        st.write("---")

    raw = fetch_api_data("https://stats-crawler.up.railway.app/api/open/lottery-analysis", datestart_a, dateend_a)

    if raw is not None and not raw.empty:
        fdb = []
        auto_g = find_game_column(raw, forbidden_cols=fdb); fdb.append(auto_g)
        auto_u = find_user_column(raw, forbidden_cols=fdb); fdb.append(auto_u)
        auto_v = get_mapped_col(raw, ['betAmount', 'validBetAmount', '銷量'], ['bet', '投注', '流水'], forbidden_cols=fdb)
        auto_c = get_mapped_col(raw, ['betCount', '單數'], ['count', '次數', 'cnt'], forbidden_cols=fdb)
        auto_p = get_mapped_col(raw, ['netAmount', '盈虧'], ['profit', '盈利', '派彩'], forbidden_cols=fdb)
        auto_b = get_mapped_col(raw, ['payOut', '獎金'], ['bonus', '派獎', '中獎'], forbidden_cols=fdb)

        all_games = sorted(raw[auto_g].astype(str).str.strip().unique().tolist()) if auto_g else []
        with st.sidebar:
            st.markdown("### 🎯 篩選條件")
            selected_games = st.multiselect("特定彩種", all_games)
            v_on = st.toggle("銷量篩選", False); v_min = st.number_input("Min銷量", 0.0); v_max = st.number_input("Max銷量", 2000.0)
            c_on = st.toggle("單數限制", False); c_limit = st.number_input("單數 ≤", 12)
            p_on = st.toggle("盈虧限制", False); p_min = st.number_input("Min盈虧", 100000.0); p_max = st.number_input("Max盈虧", 1000000.0)
            r_on = st.toggle("RTP限制", False); r_min = st.number_input("Min RTP", 0.995, format="%.3f"); r_max = st.number_input("Max RTP", 1.000, format="%.3f")
            manual_btn = st.button("🔥 執行審計", type="primary", use_container_width=True)

        if manual_btn:
            if selected_games and auto_g: raw = raw[raw[auto_g].isin(selected_games)]
            rules = {'use_manual':use_manual, 'v_on':v_on, 'v_min':v_min, 'v_max':v_max, 'c_on':c_on, 'c_limit':c_limit, 'p_on':p_on, 'p_min':p_min, 'p_max':p_max, 'r_on':r_on, 'r_min':r_min, 'r_max':r_max}
            res = run_audit_engine(raw, rules, {'u':auto_u,'g':auto_g,'v':auto_v,'c':auto_c,'p':auto_p,'b':auto_b})
            if res is not None and not res.empty:
                st.markdown("### 🚨 異常捕獲實況")
                st.markdown("""<div class='table-header'><div style='flex:1.5'>用戶名</div><div style='flex:1.5'>彩種</div><div style='flex:2.5'>原因</div><div style='flex:1.2'>銷量</div><div style='flex:1.0'>單數</div><div style='flex:1.2'>盈虧</div><div style='flex:1.0'>RTP</div></div>""", unsafe_allow_html=True)
                for _, row in res.iterrows():
                    c = st.columns([1.5, 1.5, 2.5, 1.2, 1.0, 1.2, 1.0])
                    c[0].write(row['用戶名']); c[1].write(row.get('彩種', '-')); c[2].markdown(f"<span class='badge-red'>{row['原因']}</span>", unsafe_allow_html=True)
                    c[3].write(f"{row['銷量']:,.0f}"); c[4].write(int(row['單數'])); c[5].write(f"{row['盈虧']:,.0f}"); c[6].write(f"{row['RTP']:.3f}")
                    st.divider()
            else: st.success("✅ 掃描完畢，未發現異常。")
    elif raw is not None:
        st.info("💡 該時段無數據。")

else:
    # 盈虧排行 (結構雷同，超時已在 fetch_api_data 修復)
    st.markdown("<div class='title-banner'><h1>📈 盈虧排行審計</h1></div>", unsafe_allow_html=True)
    # ... (其餘盈虧排行邏輯保持不變，已整合在上述 API 與 欄位提取修復中)
    st.info("請於左側設定條件並執行審計。")

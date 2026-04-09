import streamlit as st
import pandas as pd
import hashlib
import datetime
import requests
import re

# ==========================================
# ⚙️ 系統底層配置區 
# ==========================================
GLOBAL_PLATFORMS = "YD,XO,ND,JD,SY,MT,LY,FB,XY,XO,OL,LS,HS,JY,YS,SH,XH"

# 1. 頁面配置
st.set_page_config(page_title="抓鬼專家", layout="wide")

# 2. 注入樣式 (保持您喜愛的原始風格)
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

# --- 🎯 精準欄位識別邏輯 (核心抓取修正) ---
def find_column_by_score(df, targets, exclude_list=None):
    if exclude_list is None: exclude_list = []
    best_col = None
    max_score = -9999
    
    for col in df.columns:
        if col in exclude_list: continue
        col_lower = str(col).lower().replace('_', '').replace(' ', '')
        score = 0
        
        # 標題關鍵字匹配權重
        for t in targets:
            if t.lower() == col_lower: score += 1000 # 完全匹配
            elif t.lower() in col_lower: score += 500 # 部分包含
            
        # 數據特徵偵測 (針對帳號)
        if 'user' in targets or 'account' in targets:
            sample = df[col].dropna().head(10).astype(str).tolist()
            if sample:
                # 排除明顯是純編號且標題叫 ID 的
                if col_lower in ['id', 'uid', 'userid']: score -= 2000
                # 如果內容包含字母，很可能是帳號
                if any(re.search(r'[a-zA-Z]', s) for s in sample): score += 300
                # 如果內容長度 >= 6，可能是手機號或帳號
                if any(len(s) >= 6 for s in sample): score += 100
        
        if score > max_score:
            max_score = score
            best_col = col
    return best_col

# --- 核心數據獲取模組 (API) ---
@st.cache_data(show_spinner=False, ttl=300)
def fetch_api_data(endpoint, d_start, d_end):
    headers = {
        "Authorization": "Bearer sk-d79a713caf53e8bdh3154a596ca1a0166234df7",
        "x-api-key": "sk-d79a713caf53e8bdh3154a596ca1a0166234df7",
        "Content-Type": "application/json"
    }
    params = {"dateStart": d_start, "dateEnd": d_end, "platform": GLOBAL_PLATFORMS}
    try:
        response = requests.get(endpoint, params=params, headers=headers, timeout=120)
        response.raise_for_status() 
        data = response.json()
        if isinstance(data, dict):
            res = data.get("data") or data.get("records") or []
            return pd.DataFrame(res)
        return pd.DataFrame(data) if isinstance(data, list) else pd.DataFrame()
    except Exception as e:
        st.error(f"❌ 數據獲取異常: {e}")
        return None

# --- 核心引擎 A (用戶彩票分析) ---
def run_audit_engine(df, rules):
    try:
        # 自動識別欄位 (基於權重，不輕易排除)
        user_col = find_column_by_score(df, ['userName', 'memberAccount', '帳號', '用戶名', 'account'])
        game_col = find_column_by_score(df, ['lotteryName', 'gameName', '彩種'], exclude_list=[user_col])
        vol_col = find_column_by_score(df, ['betAmount', 'validBetAmount', '銷量', '投注金額'])
        cnt_col = find_column_by_score(df, ['betCount', '單數', '筆數'])
        profit_col = find_column_by_score(df, ['netAmount', '盈虧', '盈利'])
        bonus_col = find_column_by_score(df, ['payOut', '獎金', '派彩'])

        temp = pd.DataFrame()
        temp['用戶名'] = df[user_col].astype(str).str.strip()
        
        def to_n(c): return pd.to_numeric(df[c].astype(str).str.replace(',', ''), errors='coerce').fillna(0) if c else 0
        
        temp['銷量'] = to_n(vol_col)
        temp['單數'] = to_n(cnt_col)
        temp['盈虧'] = to_n(profit_col)
        temp['獎金'] = to_n(bonus_col)
        if game_col: temp['彩種'] = df[game_col].astype(str).str.strip()

        # 聚合計算
        agg_dict = {'銷量':'sum', '單數':'sum', '盈虧':'sum', '獎金':'sum'}
        if game_col: agg_dict['彩種'] = lambda x: ', '.join(sorted(list(set([str(i) for i in x if str(i) not in ['nan','None','']]))))
        
        grouped = temp.groupby('用戶名').agg(agg_dict).reset_index()
        grouped['RTP'] = grouped.apply(lambda x: x['獎金'] / x['銷量'] if x['銷量'] > 0 else 0, axis=1)
        
        def check(row):
            v, c, p, r = row['銷量'], row['單數'], row['盈虧'], row['RTP']
            if rules['use_manual']:
                m = True
                if rules['v_on'] and not (rules['v_min'] <= v <= rules['v_max']): m = False
                if rules['c_on'] and not (c <= rules['c_limit']): m = False
                if rules['p_on'] and not (rules['p_min'] <= p <= rules['p_max']): m = False
                if rules['r_on'] and not (rules['r_min'] <= r <= rules['r_max']): m = False
                return "手動篩選" if m else None
            
            res_tags = []
            if 1000 <= v <= 2000 and c <= 12: res_tags.append("疑似刷人數")
            if v > 2000 and c <= 10: res_tags.append("疑似對刷")
            if v >= 500000 and 0.995 <= r <= 1.000: res_tags.append("疑似刷量")
            if p >= 100000: res_tags.append("盈利大會員")
            return " | ".join(res_tags) if res_tags else None

        grouped['原因'] = grouped.apply(check, axis=1)
        return grouped[grouped['原因'].notna()].copy()
    except Exception as e:
        st.error(f"引擎 A 解析異常: {e}")
        return None

# --- 核心引擎 B (盈虧排行) ---
def run_strict_audit(df, cfg):
    try:
        user_col = find_column_by_score(df, ['userName', 'memberAccount', '帳號', '用戶名'])
        fee_col = find_column_by_score(df, ['depositAmount', '充值手續費', '充值'])
        win_col = find_column_by_score(df, ['betAmount', '銷量', '投注金額']) # 以銷量為準
        fs_col = find_column_by_score(df, ['rebate', '返點', '返水'])
        fh_col = find_column_by_score(df, ['dividend', '分紅'])
        p_col = find_column_by_score(df, ['netAmount', '盈虧'])

        def to_n(c): return pd.to_numeric(df[c].astype(str).str.replace(',', ''), errors='coerce').fillna(0) if c else 0
        
        clean = pd.DataFrame()
        clean['用戶名'] = df[user_col].astype(str).str.strip()
        clean['充值'] = to_n(fee_col)
        clean['銷量'] = to_n(win_col)
        clean['待遇'] = to_n(fs_col) + to_n(fh_col)
        clean['盈虧'] = to_n(p_col)
        
        grouped = clean.groupby('用戶名').agg({'充值':'sum', '銷量':'sum', '待遇':'sum', '盈虧':'sum'}).reset_index()
        grouped['充銷比'] = grouped.apply(lambda x: x['銷量']/x['充值'] if x['充值']>0 else 0, axis=1)
        
        def check_b(row):
            t = []
            f, v, d, p, r = row['充值'], row['銷量'], row['待遇'], row['盈虧'], row['充銷比']
            if cfg['sw1'] and f > 0 and r > cfg['ratio_high'] and cfg['win_min'] <= v: t.append("充銷比過高")
            if cfg['sw2'] and f > 0 and r < cfg['ratio_low'] and cfg['fee_min'] <= f: t.append("充銷比偏低")
            if cfg['sw3'] and d > cfg['limit_treatment']: t.append("待遇過高")
            if cfg['sw4'] and f == 0 and v > cfg['no_fee_limit']: t.append("無充下注異常")
            if cfg['sw5'] and p >= cfg['profit_limit']: t.append("盈利過大")
            return " | ".join(t) if t else None
            
        grouped['原因'] = grouped.apply(check_b, axis=1)
        return grouped[grouped['原因'].notna()].copy()
    except Exception as e:
        st.error(f"引擎 B 解析異常: {e}")
        return None

# --- UI 導航 ---
now = datetime.datetime.now()
default_start = now.strftime("%Y-%m-%d 03:00:00")
default_end = (now + datetime.timedelta(days=1)).strftime("%Y-%m-%d 03:00:00")

with st.sidebar:
    st.markdown("## 🧭 模組切換")
    mode = st.radio("選擇分析類型", ["用戶彩票分析", "盈虧排行"])
    st.write("---")

if mode == "用戶彩票分析":
    st.markdown("<div class='title-banner'><h1>📊 用戶彩票分析 (API 數據源)</h1></div>", unsafe_allow_html=True)
    with st.sidebar:
        use_manual = st.toggle("🚀 手動自訂模式", value=False)
        col_st, col_et = st.columns(2)
        ds = col_st.text_input("開始時間", value=default_start)
        de = col_et.text_input("結束時間", value=default_end)
        if st.button("🔄 刷新 API 數據", use_container_width=True): st.cache_data.clear()
        st.write("---")
        v_on = st.toggle("銷量限制", False); v_min = st.number_input("最小銷量", 0.0); v_max = st.number_input("最大銷量", 2000.0)
        c_on = st.toggle("單數限制", False); c_limit = st.number_input("單數上限", 12)
        p_on = st.toggle("盈虧限制", False); p_min = st.number_input("最小盈利", 100000.0); p_max = st.number_input("最大盈利", 1000000.0)
        r_on = st.toggle("RTP限制", False); r_min = st.number_input("Min RTP", 0.995, format="%.3f"); r_max = st.number_input("Max RTP", 1.000, format="%.3f")
        exec_a = st.button("🔥 執行審計", type="primary", use_container_width=True)

    raw_a = fetch_api_data("https://stats-crawler.up.railway.app/api/open/lottery-analysis", ds, de)
    if exec_a and raw_a is not None:
        rules = {'use_manual':use_manual, 'v_on':v_on, 'v_min':v_min, 'v_max':v_max, 'c_on':c_on, 'c_limit':c_limit, 'p_on':p_on, 'p_min':p_min, 'p_max':p_max, 'r_on':r_on, 'r_min':r_min, 'r_max':r_max}
        res = run_audit_engine(raw_a, rules)
        if res is not None and not res.empty:
            st.markdown("### 🚨 異常捕獲實況")
            st.markdown("""<div class='table-header'><div style='flex:1.5'>用戶名</div><div style='flex:2.5'>異常原因</div><div style='flex:1.2'>銷量</div><div style='flex:1.0'>單數</div><div style='flex:1.2'>盈虧</div><div style='flex:1.0'>RTP</div></div>""", unsafe_allow_html=True)
            for _, row in res.iterrows():
                cols = st.columns([1.5, 2.5, 1.2, 1.0, 1.2, 1.0])
                cols[0].write(row['用戶名'])
                cols[1].markdown(f"<span class='badge-red'>{row['原因']}</span>", unsafe_allow_html=True)
                cols[2].write(f"{row['銷量']:,.0f}")
                cols[3].write(int(row['單數']))
                cols[4].write(f"{row['盈虧']:,.0f}")
                cols[5].write(f"{row['RTP']:.3f}")
                st.divider()
        else: st.success("✅ 掃描完畢，未發現異常。")

else:
    st.markdown("<div class='title-banner'><h1>📈 盈虧排行審計</h1></div>", unsafe_allow_html=True)
    with st.sidebar:
        col_st, col_et = st.columns(2)
        ds_b = col_st.text_input("開始時間", value=default_start, key="dsb")
        de_b = col_et.text_input("結束時間", value=default_end, key="deb")
        sw1 = st.checkbox("🔍 充銷比(高)", value=True); r_h = st.number_input("高比值", value=50.0)
        sw2 = st.checkbox("🔍 充銷比(低)", value=True); r_l = st.number_input("低比值", value=2.0)
        sw3 = st.checkbox("🔍 待遇審計", value=True); l_t = st.number_input("待遇限額", value=50000)
        sw4 = st.checkbox("🔍 無充值下注", value=True); l_n = st.number_input("無充下注額", value=200000)
        sw5 = st.checkbox("🔍 大額盈利", value=True); l_p = st.number_input("盈利限額", value=100000)
        exec_b = st.button("🔥 執行組合審計", type="primary", use_container_width=True)

    raw_b = fetch_api_data("https://stats-crawler.up.railway.app/api/open/member-income", ds_b, de_b)
    if exec_b and raw_b is not None:
        cfg = {'sw1':sw1,'sw2':sw2,'sw3':sw3,'sw4':sw4,'sw5':sw5,'ratio_high':r_h,'ratio_low':r_l,'win_min':30000,'fee_min':1000,'limit_treatment':l_t,'no_fee_limit':l_n,'profit_limit':l_p}
        res_b = run_strict_audit(raw_b, cfg)
        if res_b is not None and not res_b.empty:
            st.markdown(f"<div class='metric-card-b'><div class='metric-value'>{len(res_b)}</div><div class='metric-label'>符合異常人數</div></div>", unsafe_allow_html=True)
            st.markdown("""<div class='table-header'><div style='flex:1.5'>用戶名</div><div style='flex:2.5'>異常結論</div><div style='flex:1.0'>銷量</div><div style='flex:1.0'>充值</div><div style='flex:1.0'>比值</div><div style='flex:1.0'>待遇</div><div style='flex:1.0'>盈虧</div></div>""", unsafe_allow_html=True)
            for _, row in res_b.iterrows():
                c = st.columns([1.5, 2.5, 1.0, 1.0, 1.0, 1.0, 1.0])
                c[0].write(row['用戶名'])
                c[1].markdown(f"<span class='badge-giant'>{row['原因']}</span>", unsafe_allow_html=True)
                c[2].write(f"{row['銷量']:,.0f}"); c[3].write(f"{row['充值']:,.0f}"); c[4].write(f"{row['充銷比']:.1f}")
                c[5].write(f"{row['待遇']:,.0f}"); c[6].write(f"{row['盈虧']:,.0f}")
                st.divider()
        else: st.success("✅ 掃描完畢，未發現異常。")

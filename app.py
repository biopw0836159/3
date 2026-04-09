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
    [data-testid="stSidebar"] { background-color: #1e293b !important; min-width: 400px !important; }
    [data-testid="stSidebar"] .stMarkdown, [data-testid="stSidebar"] label, 
    [data-testid="stSidebar"] p, [data-testid="stSidebar"] h3, [data-testid="stSidebar"] .stToggle p { 
        color: #f1f5f9 !important; font-weight: 700 !important; 
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
    cols_clean = [str(c).lower().replace('_', '').replace(' ', '') for c in df.columns]

    for exact_val in exact_matches:
        if exact_val.lower() in cols_lower:
            orig_col = df.columns[cols_lower.index(exact_val.lower())]
            if orig_col not in forbidden_cols: return orig_col
            
    for exact_val in exact_matches:
        exact_clean = exact_val.lower().replace('_', '').replace(' ', '')
        if exact_clean in cols_clean:
            orig_col = df.columns[cols_clean.index(exact_clean)]
            if orig_col not in forbidden_cols: return orig_col
                
    for p in partial_matches:
        for i, c_str in enumerate(cols_lower):
            orig_col = df.columns[i]
            if orig_col in forbidden_cols: continue
            if any(ext.lower() in c_str for ext in exclude_keywords): continue
            if p.lower() in c_str:
                return orig_col
    return None

# --- 🎯 終極權重排序 ---
USER_EXACT = [
    'username', 'memberaccount', 'account', 'loginname', '帐号', '帳號', '用户名', '用戶名', 
    'member_name', 'user_name', 'membername'
]
USER_PARTIAL = ['account', 'user', '玩家', '会员', '會員', 'login', '帐号', '账号']

GAME_EXACT = [
    'lotteryname', 'gamename', '彩种名称', '彩種名稱', '彩种', '彩種', 'lottery', 'game'
]
GAME_PARTIAL = ['lottery', 'game', '游戏', '遊戲', '玩法', '彩']

USER_EXCLUDE = [
    'time', 'date', 'level', 'agent', 'parent', 'type', 'status', 'ip', 
    'remark', 'game', 'lottery', 'group', 'code', '时间', '時間', 
    '日期', '代理', '状态', '狀態', 'id', 'uid', 'userid', 'playerid', 'agentid', 'merchantid',
    'bet', 'amount', 'profit', 'win', 'loss', 'payout', 'bonus', 'fee'
]

# --- 🎯 表頭精確隔離提取 (Game) ---
def find_game_column(df, forbidden_cols=None):
    if forbidden_cols is None: forbidden_cols = []
    col = get_mapped_col(df, GAME_EXACT, GAME_PARTIAL, forbidden_cols=forbidden_cols)
    return col

# --- 🎯 表頭精確隔離提取 (Username) - 強化修正版 ---
def find_user_column(df, forbidden_cols=None):
    """
    修正邏輯：
    1. 絕對禁止選取標題為 'id', 'uid', 'index' 等欄位。
    2. 檢查數據內容，如果 20% 以上是 <= 6 位的純數字，則判定為內部 ID，直接封殺。
    3. 優先選擇包含英文字母或長度 > 6 的欄位。
    """
    if forbidden_cols is None: forbidden_cols = []
    
    potential_cols = []
    
    for c in df.columns:
        c_str = str(c).lower().strip()
        # 1. 硬性排除黑名單與標題完全等於 id 的欄位
        if c in forbidden_cols: continue
        if c_str in ['id', 'uid', 'userid', 'playerid', 'index', 'sn', 'no']: continue
        
        sample_data = df[c].dropna().astype(str).head(30).tolist()
        if not sample_data: continue
        
        # 2. 數據內容特徵偵測
        # 計算短數字 (長度 <= 6 的純數字) 的比例
        short_num_count = sum(1 for v in sample_data if v.strip().isdigit() and len(v.strip()) <= 6)
        
        # 如果短數字比例過高，判定為 ID，排除
        if short_num_count >= len(sample_data) * 0.2:
            continue
            
        potential_cols.append(c)

    if not potential_cols:
        # 如果都被排除了，退而求其次找包含 account 或 username 關鍵字的
        for c in df.columns:
            if any(k in str(c).lower() for k in ['account', 'user', 'name', '帳', '賬']):
                return c
        return df.columns[0] # 最後無奈之舉

    # 3. 在潛在欄位中根據權重評分
    best_col = None
    max_score = -999
    
    for c in potential_cols:
        score = 0
        c_lower = str(c).lower()
        
        # 標題加分
        if any(k == c_lower for k in USER_EXACT): score += 500
        if any(k in c_lower for k in USER_PARTIAL): score += 100
        
        # 數據內容加分
        sample_data = df[c].dropna().astype(str).head(20).tolist()
        for val in sample_data:
            val = val.strip()
            if re.search(r'[a-zA-Z]', val): score += 20  # 含有字母通常是帳號
            if len(val) >= 7: score += 10               # 較長通常是帳號
            if val.isdigit() and len(val) < 5: score -= 50 # 極短數字扣分

        if score > max_score:
            max_score = score
            best_col = c
            
    return best_col if best_col else potential_cols[0]

# --- 核心數據獲取模組 (API 串接) ---
@st.cache_data(show_spinner=False, ttl=300)
def fetch_api_data(endpoint, d_start, d_end):
    d_start = str(d_start).strip()
    d_end = str(d_end).strip()
    
    headers = {
        "Authorization": "Bearer sk-d79a713caf53e8bdh3154a596ca1a0166234df7",
        "x-api-key": "sk-d79a713caf53e8bdh3154a596ca1a0166234df7",
        "Content-Type": "application/json"
    }
    params = { "dateStart": d_start, "dateEnd": d_end, "platform": GLOBAL_PLATFORMS }
    
    try:
        response = requests.get(endpoint, params=params, headers=headers, timeout=30)
        response.raise_for_status() 
        data = response.json()
        
        if isinstance(data, dict):
            if "data" in data: df = pd.DataFrame(data["data"]) if data["data"] else pd.DataFrame()
            elif "records" in data: df = pd.DataFrame(data["records"]) if data["records"] else pd.DataFrame()
            else: df = pd.DataFrame()
        elif isinstance(data, list):
            df = pd.DataFrame(data) if data else pd.DataFrame()
        else:
            df = pd.DataFrame()
        return df
    except Exception as e:
        st.error(f"❌ 數據獲取異常: {e}")
        return None

now = datetime.datetime.now()
default_start = now.strftime("%Y-%m-%d 03:00:00")
default_end = (now + datetime.timedelta(days=1)).strftime("%Y-%m-%d 03:00:00")

# --- 核心引擎 A (用戶彩票分析) ---
def run_audit_engine(df, rules, cols_map=None):
    try:
        df.columns = [str(c).strip() for c in df.columns]
        
        if cols_map:
            user_col = cols_map.get('u')
            game_col = cols_map.get('g')
            vol_col = cols_map.get('v')
            cnt_col = cols_map.get('c')
            profit_col = cols_map.get('p')
            bonus_col = cols_map.get('b')
        else:
            forbidden = []
            game_col = find_game_column(df, forbidden_cols=forbidden)
            if game_col: forbidden.append(game_col)
            
            user_col = find_user_column(df, forbidden_cols=forbidden)
            if user_col: forbidden.append(user_col)
            
            vol_col = get_mapped_col(df, ['betAmount', 'validBetAmount', '销量', '投注金额'], ['bet', '投注', '流水', 'vol'], forbidden_cols=forbidden)
            cnt_col = get_mapped_col(df, ['betCount', '单数', '总单数'], ['count', '次数', '笔数', 'cnt'], forbidden_cols=forbidden)
            profit_col = get_mapped_col(df, ['netAmount', 'winAmount', '盈亏'], ['profit', '盈利', '派彩'], forbidden_cols=forbidden)
            bonus_col = get_mapped_col(df, ['payOut', '奖金', '总奖金'], ['bonus', '派奖', '中奖'], forbidden_cols=forbidden)

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

# --- 核心引擎 B (盈虧排行) ---
def run_strict_audit(df, cfg):
    try:
        df.columns = [str(c).strip() for c in df.columns]
        forbidden = []
        game_col = find_game_column(df, forbidden_cols=forbidden)
        if game_col: forbidden.append(game_col)
        user_col = find_user_column(df, forbidden_cols=forbidden)
        if user_col: forbidden.append(user_col)
        
        def get_col_val(keywords_exact, keywords_partial):
            col = get_mapped_col(df, keywords_exact, keywords_partial, forbidden_cols=forbidden)
            if col: 
                forbidden.append(col)
                return col, pd.to_numeric(df[col].astype(str).str.replace(r',', '', regex=True), errors='coerce').fillna(0)
            return None, pd.Series([0.0]*len(df), index=df.index)

        _, fee_s = get_col_val(['个人充值手续费', '充值手续费', 'depositAmount'], ['充值', 'deposit'])
        _, win_s = get_col_val(['个人派奖', '销量', '投注金额', 'betAmount'], ['派奖', '銷量', 'bet'])
        _, fs_s = get_col_val(['个人自身返点', '返水', 'rebate'], ['返点', '返水'])
        _, fh_s = get_col_val(['系统分红', '分红'], ['分红', 'dividend'])
        p_col = get_mapped_col(df, ['netAmount', 'winAmount', '盈亏'], ['profit', '盈利', '派彩'], forbidden_cols=forbidden)

        clean_df = pd.DataFrame()
        clean_df['用戶名'] = df[user_col].astype(str).str.strip() if user_col else "未知"
        clean_df['個人充值手續費'] = fee_s
        clean_df['個人派獎'] = win_s
        clean_df['個人自身返點/返水'] = fs_s
        clean_df['個人系統分紅'] = fh_s
        clean_df['盈虧'] = pd.to_numeric(df[p_col].astype(str).str.replace(r',', '', regex=True), errors='coerce').fillna(0) if p_col else 0
        if game_col: clean_df['彩種'] = df[game_col].astype(str).str.strip()

        agg_dict = {'個人充值手續費':'sum','個人派獎':'sum','個人自身返點/返水':'sum','個人系統分紅':'sum','盈虧':'sum'}
        if game_col: agg_dict['彩種'] = lambda x: ', '.join(sorted(list(set([str(i) for i in x if str(i) not in ['nan', 'None', '']]))))

        grouped = clean_df.groupby('用戶名').agg(agg_dict).reset_index()
        
        def apply_rules(row):
            tags = []
            fee, win, fs, fh, p = row['個人充值手續費'], row['個人派獎'], row['個人自身返點/返水'], row['個人系統分紅'], row['盈虧']
            treatment = fs + fh
            if cfg['sw1'] and fee > 0:
                if (win / fee) > cfg['ratio_high'] and cfg['win_min'] <= win <= cfg['win_max']: tags.append("充銷比過高")
            if cfg['sw2'] and fee > 0:
                if (win / fee) < cfg['ratio_low'] and cfg['fee_min'] <= fee <= cfg['fee_max']: tags.append("充銷比偏低")
            if cfg['sw3'] and treatment > cfg['limit_treatment']: tags.append("待遇過高")
            if cfg['sw4'] and fee == 0 and win > cfg['no_fee_limit']: tags.append("無充下注異常")
            if cfg['sw5'] and p >= cfg['profit_limit']: tags.append("盈利過大")
            return " | ".join(tags) if tags else None
            
        grouped['原因'] = grouped.apply(apply_rules, axis=1)
        grouped['銷量'] = grouped['個人派獎']; grouped['充值'] = grouped['個人充值手續費']
        grouped['待遇'] = grouped['個人自身返點/返水'] + grouped['個人系統分紅']
        grouped['充銷比'] = grouped.apply(lambda x: x['銷量']/x['充值'] if x['充值']>0 else 0, axis=1)
        return grouped[grouped['原因'].notna()].copy()
    except Exception as e: 
        st.error(f"引擎 B 解析異常: {e}")
        return None

# 4. 側邊欄導航
with st.sidebar:
    st.markdown("## 🧭 模組切換")
    mode = st.radio("選擇分析類型", ["用戶彩票分析", "盈虧排行"])
    st.write("---")

# 5. 模組邏輯切換
if mode == "用戶彩票分析":
    st.markdown("<div class='title-banner'><h1>📊 用戶彩票分析 (API數據源)</h1></div>", unsafe_allow_html=True)
    
    with st.sidebar:
        st.markdown("### ⚙️ 審計控制中心")
        use_manual = st.toggle("🚀 手動自訂模式", value=False)
        st.write("---")
        st.markdown("### 📅 日期時間篩選")
        col_st, col_et = st.columns(2)
        datestart_a = col_st.text_input("開始時間", value=default_start, key="ds_a")
        dateend_a = col_et.text_input("結束時間", value=default_end, key="de_a")
        if st.button("🔄 重新拉取 API 數據", use_container_width=True): st.cache_data.clear()
        st.write("---")

    raw = fetch_api_data("https://stats-crawler.up.railway.app/api/open/lottery-analysis", datestart_a, dateend_a)

    if raw is not None and not raw.empty:
        forbidden_ui = []
        auto_g = find_game_column(raw, forbidden_cols=forbidden_ui)
        if auto_g: forbidden_ui.append(auto_g)
        auto_u = find_user_column(raw, forbidden_cols=forbidden_ui)
        if auto_u: forbidden_ui.append(auto_u)
        auto_v = get_mapped_col(raw, ['betAmount', 'validBetAmount', '销量'], ['bet', '投注', '流水'], forbidden_cols=forbidden_ui)
        auto_c = get_mapped_col(raw, ['betCount', '单数'], ['count', '次数', 'cnt'], forbidden_cols=forbidden_ui)
        auto_p = get_mapped_col(raw, ['netAmount', 'winAmount', '盈亏'], ['profit', '盈利', '派彩'], forbidden_cols=forbidden_ui)
        auto_b = get_mapped_col(raw, ['payOut', '奖金'], ['bonus', '派奖', '中奖'], forbidden_cols=forbidden_ui)

        cols_map_a = {'u': auto_u, 'v': auto_v, 'c': auto_c, 'p': auto_p, 'b': auto_b, 'g': auto_g}
        all_games = sorted(raw[auto_g].astype(str).str.strip().dropna().unique().tolist()) if auto_g else []

        with st.sidebar:
            st.markdown("### 🎯 彩種篩選")
            selected_games = st.multiselect("請選擇彩種", all_games, default=[], key="ms_a")
            st.write("---")
            v_on = st.toggle("銷量篩選", False); v_min = st.number_input("Min銷量", 0.0); v_max = st.number_input("Max銷量", 2000.0)
            c_on = st.toggle("單數限制", False); c_limit = st.number_input("單數 ≤", 12)
            p_on = st.toggle("盈虧限制", False); p_min = st.number_input("Min盈虧", 100000.0); p_max = st.number_input("Max盈虧", 1000000.0)
            r_on = st.toggle("RTP限制", False); r_min = st.number_input("Min RTP", 0.995, format="%.3f"); r_max = st.number_input("Max RTP", 1.000, format="%.3f")
            manual_btn = st.button("🔥 執行審計", type="primary", use_container_width=True)
            rules = {'use_manual':use_manual, 'v_on':v_on, 'v_min':v_min, 'v_max':v_max, 'c_on':c_on, 'c_limit':c_limit, 'p_on':p_on, 'p_min':p_min, 'p_max':p_max, 'r_on':r_on, 'r_min':r_min, 'r_max':r_max}

        if manual_btn:
            if selected_games and auto_g: raw = raw[raw[auto_g].astype(str).str.strip().isin(selected_games)]
            res = run_audit_engine(raw, rules, cols_map_a)
            if res is not None and not res.empty:
                st.markdown("### 🚨 異常捕獲實況")
                k1, k2, k3, k4 = st.columns(4)
                k1.markdown(f"<div class='metric-card-a'><div class='metric-value'>{len(res)}</div><div class='metric-label'>鎖定異常總數</div></div>", unsafe_allow_html=True)
                k2.markdown(f"<div class='metric-card-a'><div class='metric-value'>{len(res[res['原因'].str.contains('刷量')])}</div><div class='metric-label'>疑似刷量</div></div>", unsafe_allow_html=True)
                k3.markdown(f"<div class='metric-card-a'><div class='metric-value'>{len(res[res['原因'].str.contains('盈利')])}</div><div class='metric-label'>盈利大員</div></div>", unsafe_allow_html=True)
                k4.markdown(f"<div class='metric-card-a'><div class='metric-value'>{len(res[res['原因'].str.contains('對刷')])}</div><div class='metric-label'>疑似對刷</div></div>", unsafe_allow_html=True)
                
                st.markdown("""<div class='table-header'><div style='flex:1.5'>用戶名</div><div style='flex:1.5'>彩種</div><div style='flex:2.5'>原因</div><div style='flex:1.2'>銷量</div><div style='flex:1.0'>單數</div><div style='flex:1.2'>盈虧</div><div style='flex:1.0'>RTP</div></div>""", unsafe_allow_html=True)
                with st.container(height=500):
                    for _, row in res.iterrows():
                        c = st.columns([1.5, 1.5, 2.5, 1.2, 1.0, 1.2, 1.0])
                        c[0].write(row['用戶名'])
                        c[1].write(row.get('彩種', '-'))
                        c[2].markdown(f"<span class='badge-red'>{row['原因']}</span>", unsafe_allow_html=True)
                        c[3].write(f"{row['銷量']:,.0f}")
                        c[4].write(int(row['單數']))
                        c[5].write(f"{row['盈虧']:,.0f}")
                        c[6].write(f"{row['RTP']:.3f}")
                        st.divider()
            else: st.success("✅ 掃描完畢，未發現異常。")

else:
    st.markdown("<div class='title-banner'><h1>📈 盈虧排行審計 (API數據源)</h1></div>", unsafe_allow_html=True)
    with st.sidebar:
        col_st, col_et = st.columns(2)
        datestart_b = col_st.text_input("開始時間", value=default_start, key="ds_b")
        dateend_b = col_et.text_input("結束時間", value=default_end, key="de_b")
        st.write("---")
        sw1 = st.checkbox("🔍 充銷比(高)", value=True); l_ratio_h = st.number_input("高比值", value=50.0)
        sw2 = st.checkbox("🔍 充銷比(低)", value=True); l_ratio_l = st.number_input("低比值", value=2.0)
        sw3 = st.checkbox("🔍 待遇審計", value=True); l_treat = st.number_input("待遇額", value=50000)
        sw4 = st.checkbox("🔍 無充值下注", value=True); l_no_fee = st.number_input("下注額", value=200000)
        sw5 = st.checkbox("🔍 大額盈利", value=True); l_profit = st.number_input("盈利額", value=100000)
        audit_btn = st.button("🔥 執行組合審計", type="primary", use_container_width=True)
        config = {'sw1':sw1,'sw2':sw2,'sw3':sw3,'sw4':sw4,'sw5':sw5,'ratio_high':l_ratio_h,'win_min':30000,'win_max':99999999,'ratio_low':l_ratio_l,'fee_min':1000,'fee_max':2000,'limit_treatment':l_treat,'no_fee_limit':l_no_fee,'profit_limit':l_profit}

    raw_b = fetch_api_data("https://stats-crawler.up.railway.app/api/open/member-income", datestart_b, dateend_b)
    if audit_btn and raw_b is not None:
        res_b = run_strict_audit(raw_b, config)
        if res_b is not None:
            st.markdown(f"<div class='metric-card-b'><div class='metric-value'>{len(res_b)}</div><div class='metric-label'>符合異常人數</div></div>", unsafe_allow_html=True)
            if not res_b.empty:
                st.markdown("""<div class='table-header'><div style='flex:1.5'>用戶名</div><div style='flex:2.5'>異常結論</div><div style='flex:1.0'>銷量</div><div style='flex:1.0'>充值</div><div style='flex:1.0'>比值</div><div style='flex:1.0'>待遇</div><div style='flex:1.0'>盈虧</div></div>""", unsafe_allow_html=True)
                with st.container(height=500):
                    for _, row in res_b.iterrows():
                        c = st.columns([1.5, 2.5, 1.0, 1.0, 1.0, 1.0, 1.0])
                        c[0].write(row['用戶名'])
                        c[1].markdown(f"<span class='badge-giant'>{row['原因']}</span>", unsafe_allow_html=True)
                        c[2].write(f"{row['銷量']:,.0f}")
                        c[3].write(f"{row['充值']:,.0f}")
                        c[4].write(f"{row['充銷比']:.1f}")
                        c[5].write(f"{row['待遇']:,.0f}")
                        c[6].write(f"{row['盈虧']:,.0f}")
                        st.divider()

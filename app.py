import streamlit as st
import pandas as pd
import hashlib
import datetime
import requests

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
    .sidebar-hint { color: #ef4444 !important; font-size: 11px !important; font-weight: 600; margin-top: -5px; margin-bottom: 10px; display: block; }
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

# --- 通用欄位名稱匹配函數 (極致嚴謹修正版) ---
def get_mapped_col(df, exact_matches, partial_matches, exclude_keywords=None):
    """優先進行全字精確匹配，避免錯抓。若無精確匹配再使用模糊比對(嚴格排除特定關鍵字)。"""
    if exclude_keywords is None:
        exclude_keywords = []
        
    # 1. 完全精確匹配 (忽略大小寫與首尾空格)
    for c in df.columns:
        if str(c).lower().strip() in [x.lower() for x in exact_matches]: 
            return c
            
    # 2. 去除底線與空格的精確匹配 (針對如 user_name -> username)
    for c in df.columns:
        c_clean = str(c).lower().replace('_', '').replace(' ', '')
        for x in exact_matches:
            if c_clean == x.lower().replace('_', '').replace(' ', ''):
                return c
                
    # 3. 模糊匹配 (嚴格排除干擾字)
    for c in df.columns:
        c_str = str(c).lower().strip()
        if any(ext.lower() in c_str for ext in exclude_keywords):
            continue
        if any(p.lower() in c_str for p in partial_matches): 
            return c
    return None

# 定義高度共用的用戶名匹配規則，確保兩個引擎抓取邏輯完全一致且防呆
USER_EXACT = ['userName', 'username', '用户名', '用戶名', '账号', '帳號', '会员账号', '會員帳號', '会员名', '會員名', 'memberName', 'loginName', 'name', 'account', 'uname', 'player']
USER_PARTIAL = ['user', 'account', '玩家', '会员', '會員', 'member', 'name', 'login']
USER_EXCLUDE = ['id', 'time', 'date', 'level', 'agent', 'parent', 'type', 'status', 'ip', 'remark', 'game', 'lottery', 'play', 'group', 'code', '时间', '時間', '日期', '代理', '状态', '狀態']

# --- 核心數據獲取模組 (API 串接) ---
@st.cache_data(show_spinner=False, ttl=300)
def fetch_api_data(endpoint, d_start, d_end):
    """通用 API 數據獲取函數，帶快取避免頻繁請求"""
    d_start = str(d_start).strip()
    d_end = str(d_end).strip()
    
    headers = {
        "Authorization": "Bearer sk-d79a713caf53e8bdh3154a596ca1a0166234df7",
        "x-api-key": "sk-d79a713caf53e8bdh3154a596ca1a0166234df7",
        "Content-Type": "application/json"
    }
    
    params = {
        "dateStart": d_start,
        "dateEnd": d_end,
        "platform": GLOBAL_PLATFORMS 
    }
    
    try:
        response = requests.get(endpoint, params=params, headers=headers, timeout=30)
        response.raise_for_status() 
        data = response.json()
        
        if isinstance(data, dict):
            if "data" in data:
                if not data["data"]: return pd.DataFrame()
                df = pd.DataFrame(data["data"])
            elif "records" in data:
                if not data["records"]: return pd.DataFrame()
                df = pd.DataFrame(data["records"])
            else:
                st.warning("⚠️ 接口回傳成功，但響應中未包含有效的會員數據。")
                return pd.DataFrame()
        elif isinstance(data, list):
            if not data: return pd.DataFrame()
            df = pd.DataFrame(data)
        else:
            st.warning("⚠️ 接口回傳格式異常，無法解析。")
            return pd.DataFrame()
            
        return df
    except requests.exceptions.HTTPError as e:
        st.error(f"❌ 接口響應錯誤 (HTTP {e.response.status_code}): {e.response.text}")
        return None
    except Exception as e:
        st.error(f"❌ 網路或解析異常: {e}")
        return None

# --- 時間動態預設值計算 ---
now = datetime.datetime.now()
default_start = now.strftime("%Y-%m-%d 03:00:00")
default_end = (now + datetime.timedelta(days=1)).strftime("%Y-%m-%d 03:00:00")

# --- 核心引擎 A (用戶彩票分析) ---
def run_audit_engine(df, rules):
    try:
        df.columns = [str(c).strip() for c in df.columns]
        
        # 🟢 極致嚴謹修正：套用共用規則，並徹底排除時間、ID、代理等欄位
        user_col = get_mapped_col(df, USER_EXACT, USER_PARTIAL, exclude_keywords=USER_EXCLUDE)
        vol_col = get_mapped_col(df, ['betAmount', 'validBetAmount', '销量', '銷量', '总销量', '總銷量'], ['bet', '投注', '下注', '流水', 'vol', '销', '銷'])
        cnt_col = get_mapped_col(df, ['betCount', '单数', '單數', '总单数', '總單數'], ['count', '次数', '次數', '笔数', '筆數', 'cnt', '单', '單'])
        profit_col = get_mapped_col(df, ['netAmount', 'winAmount', '盈亏', '盈虧', '总盈亏', '總盈虧'], ['profit', '盈利', '派彩', '输赢', '輸贏'])
        bonus_col = get_mapped_col(df, ['payOut', '奖金', '獎金', '总奖金', '總獎金'], ['bonus', '派奖', '派獎', '中奖', '中獎', '返奖', '返獎'])
        game_col = get_mapped_col(df, ['lotteryName', 'platform', '彩种', '彩種', '平台', 'gameName'], ['lottery', 'game', '游戏', '遊戲', '玩法', '彩'])

        temp_df = pd.DataFrame()
        
        if user_col:
            temp_df['用戶名'] = df[user_col].astype(str)
        else:
            # 安全降級 fallback：排除明顯不是用戶名稱的欄位
            safe_cols = []
            for c in df.columns:
                c_str = str(c).lower()
                if c != game_col and not any(k in c_str for k in ['time', 'date', 'id', 'agent', 'parent', 'ip', 'level', 'game', 'lottery', '时间', '時間', '日期', '状态', '狀態']):
                    safe_cols.append(c)
            temp_df['用戶名'] = df[safe_cols[0]].astype(str) if safe_cols else df.columns[0]
            
        def to_num(c_name):
            if c_name and c_name in df.columns:
                return pd.to_numeric(df[c_name].astype(str).str.replace(r',', '', regex=True), errors='coerce').fillna(0)
            return 0.0

        temp_df['銷量'] = to_num(vol_col)
        temp_df['單數'] = to_num(cnt_col)
        temp_df['盈虧'] = to_num(profit_col)
        temp_df['獎金'] = to_num(bonus_col)
        
        if game_col:
            temp_df['彩種'] = df[game_col].astype(str)

        agg_dict = {'銷量':'sum', '單數':'sum', '盈虧':'sum', '獎金':'sum'}
        if game_col:
            agg_dict['彩種'] = lambda x: ', '.join(sorted(list(set([str(i) for i in x if str(i).strip() not in ['nan', 'None', '']]))))

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
        import traceback
        st.error(f"引擎 A 解析異常: {e}\n{traceback.format_exc()}")
        return None

# --- 核心引擎 B (盈虧排行) ---
def run_strict_audit(df, cfg):
    try:
        df.columns = [str(c).strip() for c in df.columns]
        last_col = df.columns[-1]
        
        # 🟢 極致嚴謹修正：與引擎 A 完全同步，保證不再抓錯
        user_col = get_mapped_col(df, USER_EXACT, USER_PARTIAL, exclude_keywords=USER_EXCLUDE)
        game_col = get_mapped_col(df, ['lotteryName', 'platform', '彩种', '彩種', '平台', 'gameName'], ['lottery', 'game', '游戏', '遊戲', '玩法', '彩'])

        clean_df = pd.DataFrame()
        
        if user_col:
            clean_df['用戶名'] = df[user_col].astype(str)
        else:
            safe_cols = []
            for c in df.columns:
                c_str = str(c).lower()
                if c != game_col and not any(k in c_str for k in ['time', 'date', 'id', 'agent', 'parent', 'ip', 'level', 'game', 'lottery', '时间', '時間', '日期', '状态', '狀態']):
                    safe_cols.append(c)
            clean_df['用戶名'] = df[safe_cols[0]].astype(str) if safe_cols else df.columns[0]
            
        def get_col_val(keywords_exact, keywords_partial):
            col = get_mapped_col(df, keywords_exact, keywords_partial)
            if col:
                return pd.to_numeric(df[col].astype(str).str.replace(r',', '', regex=True), errors='coerce').fillna(0)
            return pd.Series([0.0]*len(df), index=df.index)

        # 兼容中文與 API 英文列名，確保必定拿到數值
        clean_df['個人充值手續費'] = get_col_val(['个人充值手续费', '個人充值手續費', '充值手续费', '充值手續費', '充值', 'depositAmount', 'deposit'], ['充值', 'deposit'])
        clean_df['個人派獎'] = get_col_val(['个人派奖', '個人派獎', '派奖', '派獎', '总派奖', '總派獎', '销量', '銷量', 'betAmount', 'validBetAmount'], ['派奖', '派獎', 'payOut', '销量', '銷量', 'bet'])
        clean_df['個人自身返點/返水'] = get_col_val(['个人自身返点/返水', '個人自身返點/返水', '个人自身返点', '個人自身返點', '个人返水', '個人返水', '返点', '返點', '返水'], ['返点', '返點', '返水', 'rebate'])
        clean_df['個人系統分紅'] = get_col_val(['个人系统分红', '個人系統分紅', '系统分红', '系統分紅', '分红', '分紅'], ['分红', '分紅', 'dividend'])
        
        profit_col = get_mapped_col(df, ['netAmount', 'winAmount', '盈亏', '盈虧', '总盈亏', '總盈虧'], ['profit', '盈利', '派彩'])
        if profit_col:
            clean_df['盈虧'] = pd.to_numeric(df[profit_col].astype(str).str.replace(r',', '', regex=True), errors='coerce').fillna(0)
        else:
            clean_df['盈虧'] = pd.to_numeric(df[last_col].astype(str).str.replace(r',', '', regex=True), errors='coerce').fillna(0)
        
        if game_col:
            clean_df['彩種'] = df[game_col].astype(str)

        agg_dict = {'個人充值手續費':'sum','個人派獎':'sum','個人自身返點/返水':'sum','個人系統分紅':'sum','盈虧':'sum'}
        if game_col:
            agg_dict['彩種'] = lambda x: ', '.join(sorted(list(set([str(i) for i in x if str(i).strip() not in ['nan', 'None', '']]))))

        grouped = clean_df.groupby('用戶名').agg(agg_dict).reset_index()
        
        def apply_rules(row):
            tags = []
            fee, win, fs, fh, p = row['個人充值手續費'], row['個人派獎'], row['個人自身返點/返水'], row['個人系統分紅'], row['盈虧']
            treatment = fs + fh
            
            if cfg['sw1'] and fee > 0:
                ratio = win / fee
                if ratio > cfg['ratio_high'] and cfg['win_min'] <= win <= cfg['win_max']: tags.append("充銷比過高")
            if cfg['sw2'] and fee > 0:
                ratio = win / fee
                if ratio < cfg['ratio_low'] and cfg['fee_min'] <= fee <= cfg['fee_max']: tags.append("充銷比偏低")
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
        import traceback
        st.error(f"引擎 B 解析異常: {e}\n{traceback.format_exc()}")
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
        
        if st.button("🔄 重新拉取 API 數據", use_container_width=True):
            st.cache_data.clear()
            
        st.write("---")

    raw = None
    all_games = []
    game_col = None
    selected_games = []

    api_url_a = "https://stats-crawler.up.railway.app/api/open/lottery-analysis"
    with st.spinner("正在向 API 請求最新彩票分析數據，請稍候..."):
        raw = fetch_api_data(api_url_a, datestart_a, dateend_a)

    if raw is not None and not raw.empty:
        req_hash = hashlib.md5(f"{datestart_a}_{dateend_a}_{GLOBAL_PLATFORMS}".encode()).hexdigest()
        if st.session_state.get("last_req_a") != req_hash:
            st.session_state.read_set_a = set()
            st.session_state.last_req_a = req_hash
            
        game_col = get_mapped_col(raw, ['lotteryName', 'platform', '彩种', '彩種', '平台', 'gameName'], ['lottery', 'game', '游戏', '遊戲', '玩法'])
        if game_col:
            all_games = sorted(raw[game_col].astype(str).dropna().unique().tolist())

    with st.sidebar:
        st.markdown("### 🎯 彩種篩選 (可複選)")
        selected_games = st.multiselect("請選擇查詢特定彩種 (留空代表查全部)", all_games, default=[], key="ms_a")
        st.write("---")
        
        v_on = st.toggle("銷量篩選", False); v_min = st.number_input("Min銷量", 0.0); v_max = st.number_input("Max銷量", 2000.0)
        c_on = st.toggle("單數限制", False); c_limit = st.number_input("單數 ≤", 12)
        p_on = st.toggle("盈虧限制", False); p_min = st.number_input("Min盈虧", 100000.0); p_max = st.number_input("Max盈虧", 1000000.0)
        r_on = st.toggle("RTP限制", False); r_min = st.number_input("Min RTP", 0.995, format="%.3f"); r_max = st.number_input("Max RTP", 1.000, format="%.3f")
        manual_btn = st.button("🔥 執行審計", type="primary", use_container_width=True)
        rules = {'use_manual':use_manual, 'v_on':v_on, 'v_min':v_min, 'v_max':v_max, 'c_on':c_on, 'c_limit':c_limit, 'p_on':p_on, 'p_min':p_min, 'p_max':p_max, 'r_on':r_on, 'r_min':r_min, 'r_max':r_max}

    if manual_btn: st.session_state.trigger_a = True

    if st.session_state.get('trigger_a', False) and raw is not None:
        if raw.empty:
            st.warning("⚠️ 查無 API 初始數據。")
        else:
            if datestart_a.strip() and dateend_a.strip():
                dt_start_a = pd.to_datetime(datestart_a, errors='coerce')
                dt_end_a = pd.to_datetime(dateend_a, errors='coerce')
                
                if pd.notna(dt_start_a) and pd.notna(dt_end_a):
                    if len(dateend_a.strip()) <= 10:
                        dt_end_a = dt_end_a.replace(hour=23, minute=59, second=59)
                        
                    time_cols = [c for c in raw.columns if any(k in str(c).lower() for k in ['时间', '時間', '日期', 'date', 'time', '下注', '派彩', '创建', '創建'])]
                    if time_cols:
                        t_col = time_cols[0]
                        raw[t_col] = pd.to_datetime(raw[t_col], errors='coerce')
                        raw = raw[(raw[t_col] >= dt_start_a) & (raw[t_col] <= dt_end_a)]

            if selected_games and game_col:
                raw = raw[raw[game_col].isin(selected_games)]
                
            if raw.empty:
                st.warning("⚠️ 經過時間或彩種條件篩選後，查無符合的數據。請放寬篩選條件。")
            else:
                st.session_state.res_data_a = run_audit_engine(raw, rules)
                res = st.session_state.get("res_data_a")
                
                if res is not None and not res.empty:
                    st.markdown("### 🚨 異常捕獲實況")
                    k1, k2, k3, k4, k5 = st.columns(5)
                    k1.markdown(f"<div class='metric-card-a'><div class='metric-value'>{len(res)}</div><div class='metric-label'>鎖定異常總數</div></div>", unsafe_allow_html=True)
                    k2.markdown(f"<div class='metric-card-a'><div class='metric-value'>{len(res[res['原因'].str.contains('刷人數')])}</div><div class='metric-label'>疑似刷人數</div></div>", unsafe_allow_html=True)
                    k3.markdown(f"<div class='metric-card-a'><div class='metric-value'>{len(res[res['原因'].str.contains('刷量')])}</div><div class='metric-label'>疑似刷量</div></div>", unsafe_allow_html=True)
                    k4.markdown(f"<div class='metric-card-a'><div class='metric-value'>{len(res[res['原因'].str.contains('盈利')])}</div><div class='metric-label'>盈利大會員</div></div>", unsafe_allow_html=True)
                    k5.markdown(f"<div class='metric-card-a'><div class='metric-value'>{len(res[res['原因'].str.contains('對刷')])}</div><div class='metric-label'>疑似對刷</div></div>", unsafe_allow_html=True)
                    st.write("---")
                    sc1, sc2, sc3 = st.columns([1, 2, 2])
                    sort_col = sc2.selectbox("排序欄位", ["銷量", "盈虧", "單數", "RTP"], index=0, key="sort_a")
                    sort_dir = sc3.selectbox("排序順序", ["由大到小", "由小到大"], index=0, key="dir_a")
                    res = res.sort_values(by=sort_col, ascending=(sort_dir == "由小到大"))
                    
                    st.markdown("""<div class='table-header'><div style='flex:0.6'>核查</div><div style='flex:1.5'>用戶名</div><div style='flex:1.5'>彩種</div><div style='flex:2.5'>原因</div><div style='flex:1.2'>總銷量</div><div style='flex:1.0'>單數</div><div style='flex:1.2'>盈虧</div><div style='flex:1.0'>RTP</div></div>""", unsafe_allow_html=True)
                    with st.container(height=500):
                        for i, row in res.iterrows():
                            u = row['用戶名']; is_read = u in st.session_state.get("read_set_a", set())
                            cols = st.columns([0.6, 1.5, 1.5, 2.5, 1.2, 1.0, 1.2, 1.0])
                            if cols[0].checkbox(" ", key=f"ka_{u}_{i}", value=is_read): 
                                if "read_set_a" not in st.session_state: st.session_state.read_set_a = set()
                                st.session_state.read_set_a.add(u)
                            else: st.session_state.read_set_a.discard(u)
                            style = "color:#94a3b8; text-decoration:line-through;" if is_read else "color:#1e293b;"
                            
                            cols[1].markdown(f"<span style='{style}'>{u}</span>", unsafe_allow_html=True)
                            cols[2].markdown(f"<span style='{style}'>{row.get('彩種', '-')}</span>", unsafe_allow_html=True)
                            cols[3].markdown(f"<span class='badge-red'>{row['原因']}</span>", unsafe_allow_html=True)
                            cols[4].markdown(f"<span style='{style}'>{row['銷量']:,.0f}</span>", unsafe_allow_html=True)
                            cols[5].markdown(f"<span style='{style}'>{int(row['單數'])}</span>", unsafe_allow_html=True)
                            cols[6].markdown(f"<span style='{style}'>{row['盈虧']:,.0f}</span>", unsafe_allow_html=True)
                            cols[7].markdown(f"<span style='{style}'>{row['RTP']:.3f}</span>", unsafe_allow_html=True)
                            st.divider()
                    st.download_button("📥 導出結果", res.to_csv(index=False).encode('utf-8-sig'), "audit_a.csv")
                elif res is not None: 
                    st.success("✅ 掃描完畢，當前篩選條件下未發現任何符合的異常帳號。")

else: # 盈虧排行
    st.markdown("<div class='title-banner'><h1>📈 盈虧排行審計 (API數據源)</h1></div>", unsafe_allow_html=True)
    
    with st.sidebar:
        st.markdown("### 🛠️ 審計維度勾選")
        st.markdown("### 📅 日期時間篩選")
        col_st, col_et = st.columns(2)
        datestart_b = col_st.text_input("開始時間", value=default_start, key="ds_b")
        dateend_b = col_et.text_input("結束時間", value=default_end, key="de_b")
        
        if st.button("🔄 重新拉取 API 數據", key="refresh_b", use_container_width=True):
            st.cache_data.clear()
            
        st.write("---")

    raw_b = None
    all_games_b = []
    game_col_b = None
    selected_games_b = []

    api_url_b = "https://stats-crawler.up.railway.app/api/open/member-income"
    with st.spinner("正在向 API 請求盈虧排行數據，請稍候..."):
        raw_b = fetch_api_data(api_url_b, datestart_b, dateend_b)

    if raw_b is not None and not raw_b.empty:
        req_hash_b = hashlib.md5(f"{datestart_b}_{dateend_b}_{GLOBAL_PLATFORMS}".encode()).hexdigest()
        if st.session_state.get("last_req_b") != req_hash_b:
            st.session_state.read_set_b = set()
            st.session_state.last_req_b = req_hash_b
            
        game_col_b = get_mapped_col(raw_b, ['lotteryName', 'platform', '彩种', '彩種', '平台', 'gameName'], ['lottery', 'game', '游戏', '遊戲', '玩法', '彩'])
        if game_col_b:
            all_games_b = sorted(raw_b[game_col_b].astype(str).dropna().unique().tolist())

    with st.sidebar:
        st.markdown("### 🎯 彩種篩選 (可複選)")
        selected_games_b = st.multiselect("請選擇查詢特定彩種 (留空代表查全部)", all_games_b, default=[], key="ms_b")
        st.write("---")
        
        sw1 = st.checkbox("🔍 充銷比(高)審計", value=True); l_ratio_h = st.number_input("充銷比(高)設定值", value=50.0) if sw1 else 50.0
        if sw1:
            st.markdown("<div class='range-label'>📊 銷量區間 (在此區間內才跳異常)</div>", unsafe_allow_html=True)
            c1, c2 = st.columns(2); l_win_min = c1.number_input("銷量(小)", value=30000, key="wmin"); l_win_max = c2.number_input("銷量(大)", value=99999999, key="wmax")
        else: l_win_min, l_win_max = 30000, 99999999
        
        sw2 = st.checkbox("🔍 充銷比(低)審計", value=True); l_ratio_l = st.number_input("充銷比(低)設定值", value=2.0) if sw2 else 2.0
        if sw2:
            st.markdown("<div class='range-label'>💳 充值區間 (在此區間內才跳異常)</div>", unsafe_allow_html=True)
            c3, c4 = st.columns(2); l_fee_min = c3.number_input("充值(小)", value=1000, key="fmin"); l_fee_max = c4.number_input("充值(大)", value=2000, key="fmax")
        else: l_fee_min, l_fee_max = 1000, 2000
        
        sw3 = st.checkbox("🔍 待遇(返點+工資)審計", value=True); l_treat = st.number_input("待遇設定值", value=50000) if sw3 else 50000
        sw4 = st.checkbox("🔍 無充值下注審計", value=True); l_no_fee = st.number_input("下注額設定", value=200000) if sw4 else 200000
        sw5 = st.checkbox("🔍 大額盈利審計", value=True); l_profit = st.number_input("盈利設定", value=100000) if sw5 else 100000
        audit_btn = st.button("🔥 執行組合審計", type="primary", use_container_width=True)
        config = {'sw1':sw1,'sw2':sw2,'sw3':sw3,'sw4':sw4,'sw5':sw5,'ratio_high':l_ratio_h,'win_min':l_win_min,'win_max':l_win_max,'ratio_low':l_ratio_l,'fee_min':l_fee_min,'fee_max':l_fee_max,'limit_treatment':l_treat,'no_fee_limit':l_no_fee,'profit_limit':l_profit}

    if audit_btn: st.session_state.trigger_b = True

    if st.session_state.get('trigger_b', False) and raw_b is not None:
        if raw_b.empty:
            st.warning("⚠️ 查無 API 初始數據。")
        else:
            if datestart_b.strip() and dateend_b.strip():
                dt_start_b = pd.to_datetime(datestart_b, errors='coerce')
                dt_end_b = pd.to_datetime(dateend_b, errors='coerce')
                
                if pd.notna(dt_start_b) and pd.notna(dt_end_b):
                    if len(dateend_b.strip()) <= 10:
                        dt_end_b = dt_end_b.replace(hour=23, minute=59, second=59)
                        
                    time_cols_b = [c for c in raw_b.columns if any(k in str(c).lower() for k in ['时间', '時間', '日期', 'date', 'time', '下注', '派彩', '创建', '創建'])]
                    if time_cols_b:
                        t_col_b = time_cols_b[0]
                        raw_b[t_col_b] = pd.to_datetime(raw_b[t_col_b], errors='coerce')
                        raw_b = raw_b[(raw_b[t_col_b] >= dt_start_b) & (raw_b[t_col_b] <= dt_end_b)]

            if selected_games_b and game_col_b:
                raw_b = raw_b[raw_b[game_col_b].isin(selected_games_b)]

            if raw_b.empty:
                st.warning("⚠️ 經過時間或彩種條件篩選後，查無符合的數據。請放寬篩選條件。")
            else:
                st.session_state.res_data_b = run_strict_audit(raw_b, config)
                res = st.session_state.res_data_b
                
                if res is not None:
                    st.markdown(f"<div class='metric-card-b'><div style='font-size:14px;color:#64748b'>符合選定區間異常人數</div><div class='metric-value'>{len(res)}</div></div>", unsafe_allow_html=True)
                    if not res.empty:
                        sc1, sc2, sc3 = st.columns([1, 2, 2])
                        sort_col = sc2.selectbox("排序欄位", ["銷量", "充值", "充銷比", "待遇", "盈虧"], index=4, key="sort_b")
                        sort_dir = sc3.selectbox("排序方向", ["由大到小", "由小到大"], index=0, key="dir_b")
                        res = res.sort_values(by=sort_col, ascending=(sort_dir == "由小到大"))
                        
                        st.markdown("""<div class='table-header'><div style='flex:0.6'>確認</div><div style='flex:1.5'>用戶名</div><div style='flex:1.5'>彩種</div><div style='flex:2.5'>異常結論</div><div style='flex:1.0'>銷量</div><div style='flex:1.0'>充值</div><div style='flex:1.0'>比值</div><div style='flex:1.0'>待遇</div><div style='flex:1.0'>盈虧</div></div>""", unsafe_allow_html=True)
                        with st.container(height=500):
                            for i, row in res.iterrows():
                                u = row['用戶名']; is_read = u in st.session_state.get("read_set_b", set())
                                cols = st.columns([0.6, 1.5, 1.5, 2.5, 1.0, 1.0, 1.0, 1.0, 1.0])
                                if cols[0].checkbox(" ", key=f"fb_{u}_{i}", value=is_read):
                                    if "read_set_b" not in st.session_state: st.session_state.read_set_b = set()
                                    st.session_state.read_set_b.add(u)
                                else: st.session_state.read_set_b.discard(u)
                                style = "color:#94a3b8; text-decoration:line-through;" if is_read else "color:#1e293b;"
                                
                                cols[1].markdown(f"<span style='{style}'>{u}</span>", unsafe_allow_html=True)
                                cols[2].markdown(f"<span style='{style}'>{row.get('彩種', '-')}</span>", unsafe_allow_html=True)
                                cols[3].markdown(f"<span class='badge-giant'>{row['原因']}</span>", unsafe_allow_html=True)
                                cols[4].markdown(f"<span style='{style}'>{row['銷量']:,.1f}</span>", unsafe_allow_html=True)
                                cols[5].markdown(f"<span style='{style}'>{row['充值']:,.1f}</span>", unsafe_allow_html=True)
                                cols[6].markdown(f"<span style='{style}'>{row['充銷比']:.2f}</span>", unsafe_allow_html=True)
                                cols[7].markdown(f"<span style='{style}'>{row['待遇']:,.1f}</span>", unsafe_allow_html=True)
                                cols[8].markdown(f"<span style='{style}'>{row['盈虧']:,.1f}</span>", unsafe_allow_html=True)
                                st.divider()

import streamlit as st
import pandas as pd
import datetime
import requests
import re

# ==========================================
# ⚙️ 系統底層配置區 
# ==========================================
GLOBAL_PLATFORMS = "YD,XO,ND,JD,SY,MT,LY,FB,XY,XO,OL,LS,HS,JY,YS,SH,XH"

# 1. 頁面配置
st.set_page_config(page_title="抓鬼專家 (嚴謹模式)", layout="wide")

# 2. 注入樣式
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

# --- 🎯 嚴謹欄位識別邏輯 (防呆防錯) ---
def find_best_column(df, category, exclude_cols=None):
    if exclude_cols is None: exclude_cols = []
    
    # 嚴謹的關鍵字對應表 (按優先級，已加入簡體中文兼容)
    keywords_map = {
        'user': ['username', 'memberaccount', 'account', 'userid', 'uid', '用戶名', '用户名', '帳號', '账号', '玩家', 'user', 'member'],
        'game': ['lotteryname', 'gamename', '彩種', '彩种', '遊戲', '游戏', 'game', '玩法', 'lottery'],
        'volume': ['validbetamount', 'betamount', '銷量', '销量', '投注金額', '投注金额', '打碼量', '打码量', '有效投注', 'amount', 'bet'],
        'count': ['betcount', '單數', '单数', '筆數', '笔数', '注數', '注数', '下注數', '下注数', '投注笔数', 'count'],
        'profit': ['netamount', '盈虧', '盈亏', '盈利', '派彩', 'profit', '客贏', '客赢', 'net'],
        'bonus': ['payout', '獎金', '奖金', '派彩', '中獎金額', '中奖金额', 'winamount', 'win', 'prize'],
        'deposit': ['depositamount', '充值', '存款', '入款', '充值金額', '充值金额', 'deposit'],
        'fee': ['feeamount', '充值手續費', '充值手续费', '手續費', '手续费', 'fee'],
        'rebate': ['rebate', '返點', '返点', '返水', '退水', '活動', '活动'],
        'dividend': ['dividend', '分紅', '分红', '紅利', '红利', '派息']
    }
    
    targets = keywords_map.get(category, [])
    available_cols = [c for c in df.columns if c not in exclude_cols]
    
    # 預處理欄位名稱：全小寫、去除底線、去除空白，大幅增加匹配容錯率
    col_norm_map = {c: str(c).lower().replace('_', '').replace(' ', '') for c in available_cols}
    
    # 第一階段：完全精確匹配 (忽略大小寫與底線)
    for t in targets:
        for col in available_cols:
            if col_norm_map[col] == t: return col
            
    # 第二階段：包含關鍵字 (防呆)
    for t in targets:
        for col in available_cols:
            col_norm = col_norm_map[col]
            if t in col_norm:
                # 嚴格防止 user 抓到 game 或時間欄位 (已解禁 id 限制，防誤傷 userid)
                if category == 'user' and any(k in col_norm for k in ['game', 'lottery', 'time', 'date', 'ip']): continue
                # 防止 game 抓到 user 欄位
                if category == 'game' and any(k in col_norm for k in ['user', 'account', 'member']): continue
                return col
                
    return None

# --- 強制清洗無效用戶名 (核心排除純數字/彩種名) ---
def is_valid_user(username):
    u = str(username).strip()
    # 排除空值或系統預設詞
    if not u or u.lower() in ['nan', 'none', 'null', '總計', '合计', 'total', '0', 'undefined']: return False
    
    # 排除純數字且長度過短 (<= 5 表示很可能是 ID 代碼而非帳號)
    if u.isdigit() and len(u) <= 5: return False 
    
    # 排除包含彩種關鍵字的字串
    game_keywords = ['彩', '飛艇', '賽車', '百家樂', '龍虎', '輪盤', '快3', '快三', '11選5', 'pk10', '六合', '特碼', '真人', '體育', '電競', '分分', '秒秒', '遊戲', '測試', 'test']
    if any(k in u for k in game_keywords): return False
    
    return True

# --- 數據強健轉換 (正則提煉純數字) ---
def to_n(df, col_name):
    if not col_name or col_name not in df.columns: return 0
    # 利用正則 [^\d\.\-] 替換掉所有非數字、小數點和負號的字符，確保不會因為逗號($/¥)轉換失敗
    s = df[col_name].fillna('0').astype(str)
    s = s.str.replace(r'[^\d\.\-]', '', regex=True)
    s = s.replace(r'^[.\-]*$', '0', regex=True) # 處理空字串或純符號
    s = s.replace('', '0')
    return pd.to_numeric(s, errors='coerce').fillna(0)

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

# --- 核心引擎 A (智能切換：用戶分析 / 彩種分析) ---
def run_audit_engine(df, rules):
    try:
        user_col = find_best_column(df, 'user')
        game_col = find_best_column(df, 'game', [user_col] if user_col else [])
        
        target_type = "user"
        target_col = user_col
        
        # 💡 動態降級機制：如果找不到用戶名，但有彩種名稱，則切換為彩種風控分析
        if not user_col:
            if game_col:
                target_type = "game"
                target_col = game_col
            else:
                return None, f"無法辨識『用戶名』或『彩種』欄位。當前可用欄位: {list(df.columns)}", None
        
        vol_col = find_best_column(df, 'volume', [target_col, game_col])
        cnt_col = find_best_column(df, 'count', [target_col, game_col, vol_col])
        profit_col = find_best_column(df, 'profit', [target_col, game_col, vol_col, cnt_col])
        bonus_col = find_best_column(df, 'bonus', [target_col, game_col, vol_col, cnt_col, profit_col])

        temp = pd.DataFrame()
        temp['分析對象'] = df[target_col].astype(str).str.strip()
        temp['銷量'] = to_n(df, vol_col)
        temp['單數'] = to_n(df, cnt_col)
        temp['盈虧'] = to_n(df, profit_col)
        temp['獎金'] = to_n(df, bonus_col)

        # ✨ 關鍵攔截：若分析對象是會員，清洗過濾掉純短數字和彩種名
        if target_type == 'user':
            temp = temp[temp['分析對象'].apply(is_valid_user)]
            if temp.empty: return None, "過濾後無有效會員數據 (可能原資料無合法用戶名)", target_type

        # 聚合計算
        agg_dict = {'銷量':'sum', '單數':'sum', '盈虧':'sum', '獎金':'sum'}
        grouped = temp.groupby('分析對象').agg(agg_dict).reset_index()
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
            
            if target_type == 'user':
                # 會員專屬風控規則
                if 1000 <= v <= 2000 and c <= 12: res_tags.append("疑似刷人數")
                if v > 2000 and c <= 10: res_tags.append("疑似對刷")
                if v >= 500000 and 0.995 <= r <= 1.000: res_tags.append("疑似刷量")
                if p >= 100000: res_tags.append("盈利大會員")
            else:
                # 彩種專屬風控規則
                if v >= 500000 and r >= 1.000: res_tags.append("高RTP殺數異常")
                if c >= 2000 and p <= -50000: res_tags.append("莊家高虧損")
                if v >= 1000000 and 0.98 <= r <= 1.02: res_tags.append("流水池可疑")
                if p >= 100000: res_tags.append("高獲利彩種")

            return " | ".join(res_tags) if res_tags else None

        grouped['原因'] = grouped.apply(check, axis=1)
        
        debug_info = {
            "解析模式": "會員明細分析" if target_type == 'user' else "彩種彙總分析",
            "目標欄位映射": target_col, "遊戲欄位映射": game_col, "銷量欄位映射": vol_col,
            "單數欄位映射": cnt_col, "盈虧欄位映射": profit_col, "獎金欄位映射": bonus_col
        }
        return grouped[grouped['原因'].notna()].copy(), debug_info, target_type
    except Exception as e:
        return None, f"引擎 A 解析異常: {e}", None

# --- 核心引擎 B (盈虧排行) ---
def run_strict_audit(df, cfg):
    try:
        user_col = find_best_column(df, 'user')
        if not user_col: return None, f"無法辨識『用戶名』欄位。當前可用欄位: {list(df.columns)}"
        
        fee_col = find_best_column(df, 'deposit', [user_col])
        win_col = find_best_column(df, 'volume', [user_col, fee_col])
        fs_col = find_best_column(df, 'rebate', [user_col, fee_col, win_col])
        fh_col = find_best_column(df, 'dividend', [user_col, fee_col, win_col, fs_col])
        p_col = find_best_column(df, 'profit', [user_col, fee_col, win_col, fs_col, fh_col])

        clean = pd.DataFrame()
        clean['用戶名'] = df[user_col].astype(str).str.strip()
        clean['充值'] = to_n(df, fee_col)
        clean['銷量'] = to_n(df, win_col)
        clean['待遇'] = to_n(df, fs_col) + to_n(df, fh_col)
        clean['盈虧'] = to_n(df, p_col)
        
        # ✨ 關鍵攔截：清洗過濾掉純短數字和彩種名
        clean = clean[clean['用戶名'].apply(is_valid_user)]
        if clean.empty: return None, "過濾後無有效數據 (可能原資料無合法用戶名)"
        
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
        
        debug_info = {
            "用戶欄位映射": user_col, "充值欄位映射": fee_col, "銷量欄位映射": win_col,
            "返點欄位映射": fs_col, "分紅欄位映射": fh_col, "盈虧欄位映射": p_col
        }
        return grouped[grouped['原因'].notna()].copy(), debug_info
    except Exception as e:
        return None, f"引擎 B 解析異常: {e}"

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
    if exec_a and raw_a is not None and not raw_a.empty:
        rules = {'use_manual':use_manual, 'v_on':v_on, 'v_min':v_min, 'v_max':v_max, 'c_on':c_on, 'c_limit':c_limit, 'p_on':p_on, 'p_min':p_min, 'p_max':p_max, 'r_on':r_on, 'r_min':r_min, 'r_max':r_max}
        res, info, target_type = run_audit_engine(raw_a, rules)
        
        if res is not None:
            with st.expander("🛠️ 程式驗證與欄位映射 (嚴謹模式)", expanded=False):
                st.json(info)
                
            if target_type == 'game':
                st.warning("⚠️ **數據源通知**：當前 API 來源僅包含『彩種彙總』，缺乏會員明細。系統已自動啟動備援策略，切換為 **【彩種異常風控分析】**。")
                
            if not res.empty:
                st.markdown("### 🚨 異常捕獲實況")
                col_name = "用戶名" if target_type == 'user' else "異常彩種"
                st.markdown(f"""<div class='table-header'><div style='flex:1.5'>{col_name}</div><div style='flex:2.5'>異常原因</div><div style='flex:1.2'>銷量</div><div style='flex:1.0'>單數</div><div style='flex:1.2'>盈虧</div><div style='flex:1.0'>RTP</div></div>""", unsafe_allow_html=True)
                for _, row in res.iterrows():
                    cols = st.columns([1.5, 2.5, 1.2, 1.0, 1.2, 1.0])
                    cols[0].write(row['分析對象'])
                    cols[1].markdown(f"<span class='badge-red'>{row['原因']}</span>", unsafe_allow_html=True)
                    cols[2].write(f"{row['銷量']:,.0f}")
                    cols[3].write(int(row['單數']))
                    cols[4].write(f"{row['盈虧']:,.0f}")
                    cols[5].write(f"{row['RTP']:.3f}")
                    st.divider()
            else: st.success("✅ 掃描完畢，未發現異常。")
        else:
            st.error(f"❌ 解析失敗: {info}")
    elif exec_a:
        st.warning("⚠️ 未獲取到數據，請確認時間區間或 API 狀態。")

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
    if exec_b and raw_b is not None and not raw_b.empty:
        cfg = {'sw1':sw1,'sw2':sw2,'sw3':sw3,'sw4':sw4,'sw5':sw5,'ratio_high':r_h,'ratio_low':r_l,'win_min':30000,'fee_min':1000,'limit_treatment':l_t,'no_fee_limit':l_n,'profit_limit':l_p}
        res_b, info_b = run_strict_audit(raw_b, cfg)
        
        if res_b is not None:
            with st.expander("🛠️ 程式驗證與欄位映射 (嚴謹模式)", expanded=False):
                st.json(info_b)
                
            if not res_b.empty:
                st.markdown(f"<div class='metric-card-b'><div class='metric-value'>{len(res_b)}</div><div class='metric-label'>符合異常人數</div></div>", unsafe_allow_html=True)
                st.markdown("""<div class='table-header'><div style='flex:1.5'>用戶名</div><div style='flex:2.5'>異常結論</div><div style='flex:1.0'>銷量</div><div style='flex:1.0'>充值</div><div style='flex:1.0'>比值</div><div style='flex:1.0'>待遇</div><div style='flex:1.0'>盈虧</div></div>""", unsafe_allow_html=True)
                for _, row in res_b.iterrows():
                    c = st.columns([1.5, 2.5, 1.0, 1.0, 1.0, 1.0, 1.0])
                    c[0].write(row['用戶名'])
                    c[1].markdown(f"<span class='badge-giant'>{row['原因']}</span>", unsafe_allow_html=True)
                    c[2].write(f"{row['銷量']:,.0f}"); c[3].write(f"{row['充值']:,.0f}"); c[4].write(f"{row['充銷比']:.1f}")
                    c[5].write(f"{row['待遇']:,.0f}"); c[6].write(f"{row['盈虧']:,.0f}")
                    st.divider()
            else: st.success("✅ 掃描完畢，真實有效用戶中未發現異常。")
        else:
            st.error(f"❌ 解析失敗: {info_b}")
    elif exec_b:
        st.warning("⚠️ 未獲取到數據，請確認時間區間或 API 狀態。")

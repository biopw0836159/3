import streamlit as st
import pandas as pd
import datetime
import time
from urllib.parse import urlparse

# -------------------------------------------------------------
# 【終極 WAF 突破套件載入】
# 使用 curl_cffi 來完美偽裝 Chrome 瀏覽器的 TLS/JA3 底層指紋
# -------------------------------------------------------------
try:
    from curl_cffi import requests as cffi_requests
    HAS_CFFI = True
except ImportError:
    import requests
    HAS_CFFI = False

# 1. 页面配置
st.set_page_config(page_title="抓鬼专家", layout="wide")

# 2. 注入所有原始样式
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

# 偵測是否安裝了突破套件
if not HAS_CFFI:
    st.error("🚨 系統檢測到缺少 AWS WAF 突破套件 `curl_cffi`，請在終端機執行 `pip install curl_cffi`，否則您將持續被防火牆攔截！")

# 3. 登录逻辑
if "auth" not in st.session_state: st.session_state.auth = False
if not st.session_state.auth:
    _, center_col, _ = st.columns([1, 1.2, 1])
    with center_col:
        st.markdown("<div style='height:100px'></div>", unsafe_allow_html=True)
        st.title("🔐 欢迎光临")
        pwd = st.text_input("请输入访问密码", type="password")
        if st.button("进入系统", use_container_width=True):
            if pwd == "0224": st.session_state.auth = True; st.rerun()
            else: st.error("❌ 密码错误")
    st.stop()

# --- API 獲取引擎 (導入真實 Chrome 116 瀏覽器 TLS 偽裝) ---
def fetch_api_data(url, dt_start, dt_end, platform):
    API_KEY = "sk-d79a713caf53e8bdh3154a596ca1a0166234df7"
    
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "X-API-Key": API_KEY,
        "apikey": API_KEY,
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1"
    }
    
    start_str = dt_start.strftime("%Y-%m-%d %H:%M:%S")
    end_str = dt_end.strftime("%Y-%m-%d %H:%M:%S")
    
    params = {
        "dateStart": start_str,
        "dateEnd": end_str,
        "platform": platform, 
        "apiKey": API_KEY, 
        "key": API_KEY 
    }
    
    try:
        if HAS_CFFI:
            # 這是突破 AWS WAF 的核心：直接模擬 Chrome 116 的底層特徵
            session = cffi_requests.Session(impersonate="chrome116")
        else:
            # 如果沒安裝，退回會被擋的舊方法
            session = requests.Session()
            headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            
        response = session.get(url, headers=headers, params=params, timeout=30)
        
        # 嚴謹偵測初階 CC 防護 (setTimeout 800ms 跳轉)
        if response.status_code == 200 and "location.href=" in response.text and "_r=" in response.text and "setTimeout" in response.text:
            time.sleep(0.9) 
            parsed_url = urlparse(url)
            base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
            timestamp = int(time.time() * 1000)
            bypass_url = f"{base_url}/?_r={timestamp}"
            headers["Referer"] = response.url
            session.get(bypass_url, headers=headers, timeout=15)
            response = session.get(url, headers=headers, params=params, timeout=45)

        # 錯誤狀態碼攔截
        if not response.ok:
            st.error(f"⚠️ API 請求失敗 (狀態碼 {response.status_code})")
            return None
            
        # 嚴謹偵測高階 AWS WAF 防護 (如果偽裝失敗，或者沒裝 curl_cffi)
        if "awsWafCookieDomainList" in response.text or "challenge.js" in response.text:
            st.error("🛑 嚴重系統警告：遭到目標網站 AWS WAF 防火牆攔截")
            st.warning("💡 診斷結論：您的請求指紋被 AWS 識破了。請確認您已正確安裝並啟用 `curl_cffi` 套件來進行瀏覽器偽裝。")
            with st.expander("🔍 點擊查看防火牆攔截特徵"):
                st.text("特徵字眼包含: awsWafCookieDomainList, challenge.js")
            return None
            
        # 其他未知的 HTML 頁面阻擋
        if response.text.strip().startswith('<!DOCTYPE') or '<html' in response.text.lower():
            st.error("❌ 伺服器防護極為嚴格，請求被徹底攔截 (非 JSON 數據)。")
            with st.expander("🔍 點擊查看伺服器實際回傳內容"):
                st.text(response.text[:2000])
            return None
            
        # 空字串處理
        if not response.text or not response.text.strip():
            return pd.DataFrame()
            
        # 嘗試解析 JSON
        try:
            data = response.json()
        except ValueError: 
            st.error("❌ 伺服器回傳了非 JSON 的無效資料格式！")
            return None
        
        if isinstance(data, dict) and 'data' in data:
            return pd.DataFrame(data['data'])
        return pd.DataFrame(data)
        
    except Exception as e:
        st.error(f"⚠️ 系統發生網路連線或未預期錯誤: {e}")
        return None

# --- 精準獲取平台欄位 ---
def get_platform_col(df):
    exact_cols = ['platform', 'site', '平台', 'sitecode', 'site_code']
    lower_cols = {str(c).strip().lower(): c for c in df.columns}
    for col in exact_cols:
        if col in lower_cols: return lower_cols[col]
    for c in df.columns:
        if any(a in str(c).lower().strip() for a in ['平台', 'platform', 'site']): return c
    return None

# --- 絕對嚴謹的帳號欄位提取引擎 (V4: 強制排除彩種與無效數字) ---
def get_exact_user_col(df):
    """
    結合欄位名稱與實際資料內容進行極度嚴格的雙重驗證。
    保證只拿真正的用戶名，絕對不要「台灣PK10」或「123」。
    """
    exact_user_cols = ['username', 'account', '用户名', '用戶名', '账号', '帳號', '会员账号', 'member', 'loginname', 'membername', 'user_name', 'user_account']
    lower_cols = {str(c).strip().lower(): c for c in df.columns}
    
    # 1. 絕對精準名稱直擊 (若 API 乖乖用標準名稱，直接命中)
    for col in exact_user_cols:
        if col in lower_cols:
            return lower_cols[col]
            
    # 2. 禁忌關鍵字：只要欄位名稱包含這些，直接秒殺排除
    forbidden_col_names = ['彩', '游戏', 'game', 'lottery', '平台', 'site', 'time', 'date', '期号', '订单', 'id', '单号', '金额', '盈亏', '状态', '名称']
    
    # 擴充：彩種與無效數據特徵庫 (包含台灣、奇趣等常誤判字眼)
    game_keywords = ['pk10', '分分彩', '时时彩', '快3', '快三', '六合彩', '赛车', '飞艇', '百家乐', '体育', '电竞', '彩票', '真人', '龙虎', '三分', '五分', '秒速', '奇趣', '台湾', '澳洲', '极速']
    
    best_candidate = None
    
    for c in df.columns:
        c_str = str(c).lower().strip()
        
        # 欄位名稱包含禁忌字直接跳過
        if any(f in c_str for f in forbidden_col_names): continue
            
        sample = df[c].dropna().astype(str).head(20)
        if sample.empty: continue
        
        # 嚴格審查 A：只要樣本中出現任何一個彩種特徵字，此欄位連同資料全部判定為無效
        is_game_col = False
        for val in sample:
            if any(gk in val.lower() for gk in game_keywords):
                is_game_col = True
                break
        if is_game_col: continue
            
        # 嚴格審查 B：絕對封殺「流水號」與「短ID」
        # 若所有樣本字串都是純數字，且平均長度小於 6 碼 (帳號很少小於6碼純數字)，直接排除
        if all(val.isdigit() for val in sample):
            avg_num_len = sum(len(val) for val in sample) / len(sample)
            if avg_num_len < 6:
                continue
                
        # 若通過上述極端測試，且名稱包含以下字根，即認定為帳號
        if any(k in c_str for k in ['user', 'account', '会员', '帐', '帳', '名']):
            return c
            
        # 最嚴格的盲猜備案：必須是字串型態，平均長度在 5~25 之間，且不全為純數字短碼
        if best_candidate is None and sample.dtype == object:
            avg_len = sum(len(val) for val in sample) / len(sample)
            if 5 <= avg_len <= 25 and not all(val.isdigit() and len(val)<6 for val in sample): 
                best_candidate = c

    # 如果真的一無所獲，回傳第一欄位作為不得已的預設
    return best_candidate if best_candidate else df.columns[0]

# --- 核心引擎 A ---
def run_audit_engine(df, rules):
    try:
        if df is None or df.empty: return None
        df.columns = [str(c).strip() for c in df.columns]
        
        final_user_col = get_exact_user_col(df)
        platform_col = get_platform_col(df)

        mapping = {
            'vol': ['销量', '投注', 'betAmount', 'amount', '打码'],
            'cnt': ['单数', '次数', 'betCount', 'count', '笔数'],
            'profit': ['盈亏', '盈利', 'profit', 'winloss'],
            'bonus': ['奖金', '派奖', '中奖', 'winAmount', 'bonus', '派彩']
        }
        
        final_cols = {'user': final_user_col}
        for k, aliases in mapping.items():
            for col in df.columns:
                if any(a.lower() in str(col).lower() for a in aliases): final_cols[k] = col; break
                
        game_cols = [c for c in df.columns if any(g in str(c).lower() for g in ['彩种', '游戏', '彩种名称', 'game', 'lottery'])]
        has_game = len(game_cols) > 0

        temp_df = pd.DataFrame()
        temp_df['用户名'] = df[final_cols['user']].astype(str)
        temp_df['平台'] = df[platform_col].astype(str) if platform_col else "-" 
        
        temp_df['销量'] = pd.to_numeric(df[final_cols.get('vol', df.columns[1])].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
        temp_df['单数'] = pd.to_numeric(df[final_cols.get('cnt', df.columns[2])].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
        temp_df['盈亏'] = pd.to_numeric(df[final_cols.get('profit', df.columns[-1])].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
        temp_df['奖金'] = pd.to_numeric(df[final_cols.get('bonus', df.columns[3])].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
        
        if has_game:
            temp_df['彩种'] = df[game_cols[0]].astype(str)

        agg_dict = {'销量':'sum', '单数':'sum', '盈亏':'sum', '奖金':'sum'}
        agg_dict['平台'] = lambda x: ', '.join(sorted(list(set([str(i) for i in x if str(i).strip() not in ['nan', 'None', '']])))) 
        
        if has_game:
            agg_dict['彩种'] = lambda x: ', '.join(sorted(list(set([str(i) for i in x if str(i).strip() not in ['nan', 'None', '']]))))

        grouped = temp_df.groupby('用户名').agg(agg_dict).reset_index()
        grouped['RTP'] = grouped.apply(lambda x: x['奖金'] / x['销量'] if x['销量'] > 0 else 0, axis=1)
        
        def apply_logic(row):
            v, c, p, r = row['销量'], row['单数'], row['盈亏'], row['RTP']
            
            if rules.get('use_manual', False):
                match = True
                if rules['v_on'] and not (rules['v_min'] <= v <= rules['v_max']): match = False
                if rules['c_on'] and not (c <= rules['c_limit']): match = False
                if rules['p_on'] and not (rules['p_min'] <= p <= rules['p_max']): match = False
                if rules['r_on'] and not (rules['r_min'] <= r <= rules['r_max']): match = False
                return "手动筛选" if match else None
                
            m = []
            if 1000 <= v <= 2000 and c <= 12: m.append("疑似刷人数")
            if v > 2000 and c <= 10: m.append("疑似对刷")
            if v >= 500000 and 0.995 <= r <= 1.000: m.append("疑似刷量")
            if p >= 100000: m.append("盈利大会员")
            
            return " | ".join(m) if m else None
            
        grouped['原因'] = grouped.apply(apply_logic, axis=1)
        return grouped[grouped['原因'].notna()].copy()
    except Exception as e:
        st.error(f"分析引擎發生異常: {e}")
        return None

# --- 核心引擎 B ---
def run_strict_audit(df, cfg):
    try:
        if df is None or df.empty: return None
        df.columns = [str(c).strip() for c in df.columns]
        
        final_user_col = get_exact_user_col(df)
        platform_col = get_platform_col(df)

        profit_col = None
        for c in df.columns:
            if any(p in str(c).lower() for p in ['盈亏', '盈利', 'profit']):
                profit_col = c
                break
        if not profit_col: profit_col = df.columns[-1]

        game_cols = [c for c in df.columns if any(g in str(c).lower() for g in ['彩种', '游戏', '彩种名称', 'game', 'lottery'])]
        has_game = len(game_cols) > 0

        clean_df = pd.DataFrame()
        clean_df['用户名'] = df[final_user_col].astype(str)
        clean_df['平台'] = df[platform_col].astype(str) if platform_col else "-" 
        
        target_mappings = {
            '个人充值手续费': ['充值', 'recharge', 'fee', '个人充值手续费'],
            '个人派奖': ['派奖', 'payout', 'win', '个人派奖'],
            '个人自身返点/返水': ['返点', '返水', 'rebate', '个人自身返点/返水'],
            '个人系统分红': ['分红', 'dividend', '个人系统分红']
        }
        
        for std_col, aliases in target_mappings.items():
            matched_col = None
            for c in df.columns:
                if any(a in str(c) for a in aliases): matched_col = c; break
            if matched_col:
                clean_df[std_col] = pd.to_numeric(df[matched_col], errors='coerce').fillna(0)
            else:
                clean_df[std_col] = 0

        clean_df['盈亏'] = pd.to_numeric(df[profit_col], errors='coerce').fillna(0)
        
        if has_game:
            clean_df['彩种'] = df[game_cols[0]].astype(str)

        agg_dict = {'个人充值手续费':'sum','个人派奖':'sum','个人自身返点/返水':'sum','个人系统分红':'sum','盈亏':'sum'}
        agg_dict['平台'] = lambda x: ', '.join(sorted(list(set([str(i) for i in x if str(i).strip() not in ['nan', 'None', '']])))) 
        
        if has_game:
            agg_dict['彩种'] = lambda x: ', '.join(sorted(list(set([str(i) for i in x if str(i).strip() not in ['nan', 'None', '']]))))

        grouped = clean_df.groupby('用户名').agg(agg_dict).reset_index()
        
        def apply_rules(row):
            tags = []
            fee, win, fs, fh, p = row['个人充值手续费'], row['个人派奖'], row['个人自身返点/返水'], row['个人系统分红'], row['盈亏']
            treatment = fs + fh
            
            if cfg['sw1'] and fee > 0:
                ratio = win / fee
                if ratio > cfg['ratio_high'] and cfg['win_min'] <= win <= cfg['win_max']: tags.append("充销比过高")
            if cfg['sw2'] and fee > 0:
                ratio = win / fee
                if ratio < cfg['ratio_low'] and cfg['fee_min'] <= fee <= cfg['fee_max']: tags.append("充销比偏低")
            if cfg['sw3'] and treatment > cfg['limit_treatment']: tags.append("待遇过高")
            if cfg['sw4'] and fee == 0 and win > cfg['no_fee_limit']: tags.append("无充下注异常")
            if cfg['sw5'] and p >= cfg['profit_limit']: tags.append("盈利过大")
            
            return " | ".join(tags) if tags else None
            
        grouped['原因'] = grouped.apply(apply_rules, axis=1)
        grouped['销量'] = grouped['个人派奖']; grouped['充值'] = grouped['个人充值手续费']
        grouped['待遇'] = grouped['个人自身返点/返水'] + grouped['个人系统分红']
        grouped['充销比'] = grouped.apply(lambda x: x['销量']/x['充值'] if x['充值']>0 else 0, axis=1)
        return grouped[grouped['原因'].notna()].copy()
    except Exception as e:
        st.error(f"分析引擎發生異常: {e}")
        return None

# 4. 侧边栏导航、時間平台設定與獲取數據按鈕
with st.sidebar:
    st.markdown("## 🧭 模块切换")
    mode = st.radio("选择分析类型", ["用户彩票分析", "盈亏排行"])
    st.write("---")

    st.markdown("### 📅 時間與平台參數設定")
    st.caption("⌚ 預設區間為 當天 03:00 - 隔天 03:00，可自由調整。")
    
    today = datetime.date.today()
    tomorrow = today + datetime.timedelta(days=1)
    default_time = datetime.time(3, 0)
    
    c1, c2 = st.columns(2)
    api_date_start = c1.date_input("開始日期", today)
    api_time_start = c2.time_input("開始時間", default_time)
    
    c3, c4 = st.columns(2)
    api_date_end = c3.date_input("結束日期", tomorrow)
    api_time_end = c4.time_input("結束時間", default_time)
    
    dt_start = datetime.datetime.combine(api_date_start, api_time_start)
    dt_end = datetime.datetime.combine(api_date_end, api_time_end)
    
    platform_options = ["", "YD", "ND", "JD", "SY", "MT", "LY", "FB", "XY", "XO", "OL", "LS", "HS", "JY", "SH", "XH"]
    api_platform = st.selectbox("🏢 目標平台", options=platform_options, format_func=lambda x: "全平台 (查詢所有平台)" if x == "" else x)
    
    actual_request_platform = api_platform if api_platform != "" else ",".join([p for p in platform_options if p != ""])
    
    fetch_clicked = st.button("🔄 獲取 API 數據", type="primary", use_container_width=True)
    
    if fetch_clicked:
        if mode == "用户彩票分析":
            with st.spinner("正在連線抓取【用户彩票分析】數據..."):
                raw_data = fetch_api_data("https://stats-crawler.up.railway.app/api/open/lottery-analysis", dt_start, dt_end, actual_request_platform)
                if raw_data is not None and not raw_data.empty:
                    st.session_state.raw_data_a = raw_data
                    st.session_state.read_set_a = set()
                    st.success("✅ 數據獲取成功！")
                elif raw_data is not None and raw_data.empty:
                    st.warning("⚠️ 此區間/平台查無資料或回傳為空")
        else:
            with st.spinner("正在連線抓取【盈亏排行】數據..."):
                raw_data = fetch_api_data("https://stats-crawler.up.railway.app/api/open/member-income", dt_start, dt_end, actual_request_platform)
                if raw_data is not None and not raw_data.empty:
                    st.session_state.raw_data_b = raw_data
                    st.session_state.read_set_b = set()
                    st.success("✅ 數據獲取成功！")
                elif raw_data is not None and raw_data.empty:
                    st.warning("⚠️ 此區間/平台查無資料或回傳為空")
    
    st.write("---")

# 5. 模块逻辑切换 (渲染主畫面與側邊過濾器)
if mode == "用户彩票分析":
    st.markdown("<div class='title-banner'><h1>📊 用户彩票分析</h1></div>", unsafe_allow_html=True)

    raw = st.session_state.get("raw_data_a")
    all_games = []
    game_col = None
    selected_games = []

    if raw is not None:
        game_cols = [c for c in raw.columns if any(g in str(c).lower() for g in ['彩种', '游戏', '彩种名称', 'game', 'lottery'])]
        if game_cols:
            game_col = game_cols[0]
            all_games = sorted(raw[game_col].astype(str).dropna().unique().tolist())

    with st.sidebar:
        st.markdown("### ⚙️ 审计控制中心")
        use_manual = st.toggle("🚀 手动自定义模式", value=False)
        st.write("---")
        
        st.markdown("### 🎯 彩种筛选 (可复选)")
        selected_games = st.multiselect("请选择查询特定彩种 (留空代表查全部)", all_games, default=[], key="ms_a")
        st.write("---")
        
        v_on = st.toggle("销量筛选", False); v_min = st.number_input("Min销量", 0.0); v_max = st.number_input("Max销量", 2000.0)
        c_on = st.toggle("单数限制", False); c_limit = st.number_input("单数 ≤", 12)
        p_on = st.toggle("盈亏限制", False); p_min = st.number_input("Min盈亏", 100000.0); p_max = st.number_input("Max盈亏", 1000000.0)
        r_on = st.toggle("RTP限制", False); r_min = st.number_input("Min RTP", 0.995, format="%.3f"); r_max = st.number_input("Max RTP", 1.000, format="%.3f")
        rules = {'use_manual':use_manual, 'v_on':v_on, 'v_min':v_min, 'v_max':v_max, 'c_on':c_on, 'c_limit':c_limit, 'p_on':p_on, 'p_min':p_min, 'p_max':p_max, 'r_on':r_on, 'r_min':r_min, 'r_max':r_max}

    if raw is not None:
        filtered_raw = raw.copy()
        if selected_games and game_col:
            filtered_raw = filtered_raw[filtered_raw[game_col].isin(selected_games)]
            st.caption(f"📍 当前已筛选彩种: {', '.join(selected_games)}")
            
        res = run_audit_engine(filtered_raw, rules)
        
        if res is not None and not res.empty:
            st.markdown("### 🚨 异常捕获实况")
            k1, k2, k3, k4, k5 = st.columns(5)
            k1.markdown(f"<div class='metric-card-a'><div class='metric-value'>{len(res)}</div><div class='metric-label'>锁定异常总数</div></div>", unsafe_allow_html=True)
            k2.markdown(f"<div class='metric-card-a'><div class='metric-value'>{len(res[res['原因'].str.contains('刷人数')])}</div><div class='metric-label'>疑似刷人数</div></div>", unsafe_allow_html=True)
            k3.markdown(f"<div class='metric-card-a'><div class='metric-value'>{len(res[res['原因'].str.contains('刷量')])}</div><div class='metric-label'>疑似刷量</div></div>", unsafe_allow_html=True)
            k4.markdown(f"<div class='metric-card-a'><div class='metric-value'>{len(res[res['原因'].str.contains('盈利')])}</div><div class='metric-label'>盈利大会员</div></div>", unsafe_allow_html=True)
            k5.markdown(f"<div class='metric-card-a'><div class='metric-value'>{len(res[res['原因'].str.contains('对刷')])}</div><div class='metric-label'>疑似对刷</div></div>", unsafe_allow_html=True)
            st.write("---")
            sc1, sc2, sc3 = st.columns([1, 2, 2])
            sort_col = sc2.selectbox("排序字段", ["销量", "盈亏", "单数", "RTP"], index=0, key="sort_a")
            sort_dir = sc3.selectbox("排序顺序", ["由大到小", "由小到大"], index=0, key="dir_a")
            res = res.sort_values(by=sort_col, ascending=(sort_dir == "由小到大"))
            
            st.markdown("""<div class='table-header'><div style='flex:0.6'>核查</div><div style='flex:1.0'>平台</div><div style='flex:1.5'>用户名</div><div style='flex:1.5'>彩种</div><div style='flex:2.0'>原因</div><div style='flex:1.0'>总销量</div><div style='flex:0.8'>单数</div><div style='flex:1.0'>盈亏</div><div style='flex:0.8'>RTP</div></div>""", unsafe_allow_html=True)
            with st.container(height=500):
                for i, row in res.iterrows():
                    u = row['用户名']; is_read = u in st.session_state.get("read_set_a", set())
                    cols = st.columns([0.6, 1.0, 1.5, 1.5, 2.0, 1.0, 0.8, 1.0, 0.8])
                    if cols[0].checkbox(" ", key=f"ka_{u}_{i}", value=is_read): 
                        if "read_set_a" not in st.session_state: st.session_state.read_set_a = set()
                        st.session_state.read_set_a.add(u)
                    else: st.session_state.read_set_a.discard(u)
                    style = "color:#94a3b8; text-decoration:line-through;" if is_read else "color:#1e293b;"
                    
                    cols[1].markdown(f"<span style='{style}'>{row.get('平台', '-')}</span>", unsafe_allow_html=True)
                    cols[2].markdown(f"<span style='{style}'>{u}</span>", unsafe_allow_html=True)
                    cols[3].markdown(f"<span style='{style}'>{row.get('彩种', '-')}</span>", unsafe_allow_html=True)
                    cols[4].markdown(f"<span class='badge-red'>{row['原因']}</span>", unsafe_allow_html=True)
                    cols[5].markdown(f"<span style='{style}'>{row['销量']:,.0f}</span>", unsafe_allow_html=True)
                    cols[6].markdown(f"<span style='{style}'>{int(row['单数'])}</span>", unsafe_allow_html=True)
                    cols[7].markdown(f"<span style='{style}'>{row['盈亏']:,.0f}</span>", unsafe_allow_html=True)
                    cols[8].markdown(f"<span style='{style}'>{row['RTP']:.3f}</span>", unsafe_allow_html=True)
                    st.divider()
            st.download_button("📥 导出结果", res.to_csv(index=False).encode('utf-8-sig'), "audit_a.csv")
        elif res is not None: st.success("✅ 扫描完毕，未发现异常。")

else: # 盈亏排行
    st.markdown("<div class='title-banner'><h1>📈 盈亏排行审计</h1></div>", unsafe_allow_html=True)
    
    raw_b = st.session_state.get("raw_data_b")
    all_games_b = []
    game_col_b = None
    selected_games_b = []

    if raw_b is not None:
        game_cols_b = [c for c in raw_b.columns if any(g in str(c).lower() for g in ['彩种', '游戏', '彩种名称', 'game', 'lottery'])]
        if game_cols_b:
            game_col_b = game_cols_b[0]
            all_games_b = sorted(raw_b[game_col_b].astype(str).dropna().unique().tolist())

    with st.sidebar:
        st.markdown("### 🛠️ 审计维度勾选")
        
        st.markdown("### 🎯 彩种筛选 (可复选)")
        selected_games_b = st.multiselect("请选择查询特定彩种 (留空代表查全部)", all_games_b, default=[], key="ms_b")
        st.write("---")
        
        sw1 = st.checkbox("🔍 充销比(高)审计", value=True); l_ratio_h = st.number_input("充销比(高)设定值", value=50.0) if sw1 else 50.0
        if sw1:
            st.markdown("<div class='range-label'>📊 销量区间 (在此区间内才跳异常)</div>", unsafe_allow_html=True)
            c1, c2 = st.columns(2); l_win_min = c1.number_input("销量(小)", value=30000, key="wmin"); l_win_max = c2.number_input("销量(大)", value=99999999, key="wmax")
            st.markdown("<span class='sidebar-hint'>💡 预防销量虽高但金额无意义会员</span>", unsafe_allow_html=True)
        else: l_win_min, l_win_max = 30000, 99999999
        
        sw2 = st.checkbox("🔍 充销比(低)审计", value=True); l_ratio_l = st.number_input("充销比(低)设定值", value=2.0) if sw2 else 2.0
        if sw2:
            st.markdown("<div class='range-label'>💳 充值区间 (在此区间内才跳异常)</div>", unsafe_allow_html=True)
            c3, c4 = st.columns(2); l_fee_min = c3.number_input("充值(小)", value=1000, key="fmin"); l_fee_max = c4.number_input("充值(大)", value=2000, key="fmax")
            st.markdown("<span class='sidebar-hint'>💡 预防充值过少或特定额度洗钱</span>", unsafe_allow_html=True)
        else: l_fee_min, l_fee_max = 1000, 2000
        
        sw3 = st.checkbox("🔍 待遇(返点+工资)审计", value=True); l_treat = st.number_input("待遇设定值", value=50000) if sw3 else 50000
        sw4 = st.checkbox("🔍 无充值下注审计", value=True); l_no_fee = st.number_input("下注额设定", value=200000) if sw4 else 200000
        sw5 = st.checkbox("🔍 大额盈利审计", value=True); l_profit = st.number_input("盈利设定", value=100000) if sw5 else 100000
        
        config = {'sw1':sw1,'sw2':sw2,'sw3':sw3,'sw4':sw4,'sw5':sw5,'ratio_high':l_ratio_h,'win_min':l_win_min,'win_max':l_win_max,'ratio_low':l_ratio_l,'fee_min':l_fee_min,'fee_max':l_fee_max,'limit_treatment':l_treat,'no_fee_limit':l_no_fee,'profit_limit':l_profit}

    if raw_b is not None:
        filtered_raw_b = raw_b.copy()
        if selected_games_b and game_col_b:
            filtered_raw_b = filtered_raw_b[filtered_raw_b[game_col_b].isin(selected_games_b)]
            st.caption(f"📍 当前已筛选彩种: {', '.join(selected_games_b)}")

        res = run_strict_audit(filtered_raw_b, config)
        
        if res is not None:
            st.markdown(f"<div class='metric-card-b'><div style='font-size:14px;color:#64748b'>符合选定区间异常人数</div><div class='metric-value'>{len(res)}</div></div>", unsafe_allow_html=True)
            if not res.empty:
                sc1, sc2, sc3 = st.columns([1, 2, 2])
                sort_col = sc2.selectbox("排序字段", ["销量", "充值", "充销比", "待遇", "盈亏"], index=4, key="sort_b")
                sort_dir = sc3.selectbox("排序方向", ["由大到小", "由小到大"], index=0, key="dir_b")
                res = res.sort_values(by=sort_col, ascending=(sort_dir == "由小到大"))
                
                st.markdown("""<div class='table-header'><div style='flex:0.6'>确认</div><div style='flex:1.0'>平台</div><div style='flex:1.5'>用户名</div><div style='flex:1.2'>彩种</div><div style='flex:2.0'>异常结论</div><div style='flex:1.0'>销量</div><div style='flex:1.0'>充值</div><div style='flex:0.8'>比值</div><div style='flex:1.0'>待遇</div><div style='flex:1.0'>盈亏</div></div>""", unsafe_allow_html=True)
                with st.container(height=500):
                    for i, row in res.iterrows():
                        u = row['用户名']; is_read = u in st.session_state.get("read_set_b", set())
                        cols = st.columns([0.6, 1.0, 1.5, 1.2, 2.0, 1.0, 1.0, 0.8, 1.0, 1.0])
                        if cols[0].checkbox(" ", key=f"fb_{u}_{i}", value=is_read):
                            if "read_set_b" not in st.session_state: st.session_state.read_set_b = set()
                            st.session_state.read_set_b.add(u)
                        else: st.session_state.read_set_b.discard(u)
                        style = "color:#94a3b8; text-decoration:line-through;" if is_read else "color:#1e293b;"
                        
                        cols[1].markdown(f"<span style='{style}'>{row.get('平台', '-')}</span>", unsafe_allow_html=True)
                        cols[2].markdown(f"<span style='{style}'>{u}</span>", unsafe_allow_html=True)
                        cols[3].markdown(f"<span style='{style}'>{row.get('彩种', '-')}</span>", unsafe_allow_html=True)
                        cols[4].markdown(f"<span class='badge-giant'>{row['原因']}</span>", unsafe_allow_html=True)
                        cols[5].markdown(f"<span style='{style}'>{row['销量']:,.1f}</span>", unsafe_allow_html=True)
                        cols[6].markdown(f"<span style='{style}'>{row['充值']:,.1f}</span>", unsafe_allow_html=True)
                        cols[7].markdown(f"<span style='{style}'>{row['充销比']:.2f}</span>", unsafe_allow_html=True)
                        cols[8].markdown(f"<span style='{style}'>{row['待遇']:,.1f}</span>", unsafe_allow_html=True)
                        cols[9].markdown(f"<span style='{style}'>{row['盈亏']:,.1f}</span>", unsafe_allow_html=True)
                        st.divider()

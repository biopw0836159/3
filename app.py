import streamlit as st
import pandas as pd
import requests
import datetime

# 1. 页面配置
st.set_page_config(page_title="抓鬼专家", layout="wide")

# 2. 注入所有原始样式 (合并两份代码的 CSS)
st.markdown("""
    <style>
    .stApp { background-color: #f8fafc; }
    [data-testid="stSidebar"] { background-color: #f1f5f9 !important; min-width: 400px !important; }
    [data-testid="stSidebar"] .stMarkdown, [data-testid="stSidebar"] label, 
    [data-testid="stSidebar"] p, [data-testid="stSidebar"] h3, [data-testid="stSidebar"] .stToggle p { 
        color: #1e293b !important; font-weight: 700 !important; 
    }
    /* 统计看板 A */
    .metric-card-a {
        background-color: #ffffff; padding: 15px; border-radius: 12px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05); border-top: 5px solid #ef4444;
        text-align: center; margin-bottom: 10px;
    }
    /* 统计看板 B */
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

# --- API 獲取引擎 ---
def fetch_api_data(url, dt_start, dt_end, platform):
    """通用 API 數據獲取函式"""
    API_KEY = "sk-d79a713caf53e8bdh3154a596ca1a0166234df7"
    
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "X-API-Key": API_KEY,
        "apikey": API_KEY,
        "Accept": "application/json"
    }
    
    # 將使用者選擇的日期與時間轉為標準字串格式
    start_str = dt_start.strftime("%Y-%m-%d %H:%M:%S")
    end_str = dt_end.strftime("%Y-%m-%d %H:%M:%S")
    
    params = {
        "dateStart": start_str,
        "dateEnd": end_str,
        "platform": platform.strip() if platform else "", # 若空白則傳送空字串代表全平台
        "apiKey": API_KEY, 
        "key": API_KEY 
    }
    
    try:
        response = requests.get(url, headers=headers, params=params, timeout=60)
        response.raise_for_status() # 檢查 HTTP 狀態碼
        data = response.json()
        
        # 兼容常見 API JSON 結構 (直接回傳陣列 或 包在 data 欄位內)
        if isinstance(data, dict) and 'data' in data:
            df = pd.DataFrame(data['data'])
        else:
            df = pd.DataFrame(data)
            
        return df
        
    except requests.exceptions.HTTPError as http_err:
        # 抓取伺服器的真實錯誤訊息並印出
        error_body = response.text if response.text else "伺服器未提供錯誤說明"
        st.error(f"⚠️ API 請求失敗 (狀態碼 {response.status_code})")
        st.warning(f"**伺服器拒絕原因:** `{error_body}`")
        st.info(f"**實際發送的完整網址 (供核對):**\n`{response.url}`")
        return None
    except Exception as e:
        st.error(f"API 請求發生未預期的錯誤！詳細錯誤: {e}")
        return None

# --- 核心引擎 A ---
def run_audit_engine(df, rules):
    try:
        if df.empty: return None
        df.columns = [str(c).strip() for c in df.columns]
        
        # 精準識別「帳號」欄位 (避開純數字 ID 與 彩種名稱)
        user_aliases = ['账号', '帳號', '用户名', '用戶名', '会员', 'user', 'account']
        user_candidates = [c for c in df.columns if any(a in str(c).lower() for a in user_aliases)]
        
        valid_user_col = None
        for c in user_candidates:
            if any(forbidden in str(c) for forbidden in ['彩种', '游戏', 'game']):
                continue
            sample = df[c].dropna().astype(str).head(10)
            if sample.empty: continue
            # 判斷是否為純數字短字串 (如 ID)，若是則過濾
            short_digits_count = sum(1 for x in sample if x.isdigit() and len(x) < 5)
            if short_digits_count < len(sample) * 0.5:
                valid_user_col = c
                break
                
        final_user_col = valid_user_col if valid_user_col else (user_candidates[0] if user_candidates else df.columns[0])

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
                
        # 提取彩种字段
        game_cols = [c for c in df.columns if any(g in str(c) for g in ['彩种', '游戏', '彩种名称', 'Game', 'lottery'])]
        has_game = len(game_cols) > 0

        temp_df = pd.DataFrame()
        temp_df['用户名'] = df[final_cols['user']].astype(str)
        temp_df['销量'] = pd.to_numeric(df[final_cols.get('vol', df.columns[1])].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
        temp_df['单数'] = pd.to_numeric(df[final_cols.get('cnt', df.columns[2])].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
        temp_df['盈亏'] = pd.to_numeric(df[final_cols.get('profit', df.columns[-1])].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
        temp_df['奖金'] = pd.to_numeric(df[final_cols.get('bonus', df.columns[3])].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
        
        if has_game:
            temp_df['彩种'] = df[game_cols[0]].astype(str)

        # 聚合规则
        agg_dict = {'销量':'sum', '单数':'sum', '盈亏':'sum', '奖金':'sum'}
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
        if df.empty: return None
        df.columns = [str(c).strip() for c in df.columns]
        
        # 尋找用戶名 (避開彩種與純數字 ID)
        user_aliases = ['账号', '帳號', '用户名', '用戶名', '会员', 'user', 'account']
        user_candidates = [c for c in df.columns if any(a in str(c).lower() for a in user_aliases)]
        valid_user_col = None
        for c in user_candidates:
            if '彩种' in str(c) or '游戏' in str(c): continue
            sample = df[c].dropna().astype(str).head(10)
            if sum(1 for x in sample if x.isdigit() and len(x) < 5) < len(sample) * 0.5:
                valid_user_col = c
                break
        final_user_col = valid_user_col if valid_user_col else (user_candidates[0] if user_candidates else df.columns[0])

        # 尋找盈虧欄位
        profit_col = None
        for c in df.columns:
            if any(p in str(c).lower() for p in ['盈亏', '盈利', 'profit']):
                profit_col = c
                break
        if not profit_col: profit_col = df.columns[-1]

        # 提取彩种字段
        game_cols = [c for c in df.columns if any(g in str(c) for g in ['彩种', '游戏', '彩种名称', 'Game', 'lottery'])]
        has_game = len(game_cols) > 0

        clean_df = pd.DataFrame()
        clean_df['用户名'] = df[final_user_col].astype(str)
        
        # 彈性尋找目標欄位
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

        # 聚合规则
        agg_dict = {'个人充值手续费':'sum','个人派奖':'sum','个人自身返点/返水':'sum','个人系统分红':'sum','盈亏':'sum'}
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

# 4. 侧边栏导航 & 日期選擇器
with st.sidebar:
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
    
    # 修改：預設為空字串，提示更新為留白代表全平台
    api_platform = st.text_input("🏢 目標平台代碼", value="", help="留白代表全平台，可逗号分隔多平台，如 XO 或 XO,XO2")
    st.write("---")

    st.markdown("## 🧭 模块切换")
    mode = st.radio("选择分析类型", ["用户彩票分析", "盈亏排行"])
    st.write("---")

# 5. 模块逻辑切换
if mode == "用户彩票分析":
    st.markdown("<div class='title-banner'><h1>📊 用户彩票分析</h1></div>", unsafe_allow_html=True)
    
    col_btn, _ = st.columns([1, 4])
    # 修改：直接發送請求，不再阻擋平台為空
    if col_btn.button("🔄 獲取 API 數據", type="primary", use_container_width=True):
        with st.spinner("正在連線抓取數據..."):
            raw_data = fetch_api_data("https://stats-crawler.up.railway.app/api/open/lottery-analysis", dt_start, dt_end, api_platform)
            if raw_data is not None and not raw_data.empty:
                st.session_state.raw_data_a = raw_data
                st.session_state.read_set_a = set()
                st.success("✅ 數據獲取成功！")
            else:
                st.warning("⚠️ 此區間查無資料或回傳為空 (若上方有顯示錯誤訊息請參考)")

    raw = st.session_state.get("raw_data_a")
    all_games = []
    game_col = None
    selected_games = []

    if raw is not None:
        game_cols = [c for c in raw.columns if any(g in str(c) for g in ['彩种', '游戏', '彩种名称', 'Game', 'lottery'])]
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
            
            st.markdown("""<div class='table-header'><div style='flex:0.6'>核查</div><div style='flex:1.5'>用户名</div><div style='flex:1.5'>彩种</div><div style='flex:2.5'>原因</div><div style='flex:1.2'>总销量</div><div style='flex:1.0'>单数</div><div style='flex:1.2'>盈亏</div><div style='flex:1.0'>RTP</div></div>""", unsafe_allow_html=True)
            with st.container(height=500):
                for i, row in res.iterrows():
                    u = row['用户名']; is_read = u in st.session_state.get("read_set_a", set())
                    cols = st.columns([0.6, 1.5, 1.5, 2.5, 1.2, 1.0, 1.2, 1.0])
                    if cols[0].checkbox(" ", key=f"ka_{u}_{i}", value=is_read): 
                        if "read_set_a" not in st.session_state: st.session_state.read_set_a = set()
                        st.session_state.read_set_a.add(u)
                    else: st.session_state.read_set_a.discard(u)
                    style = "color:#94a3b8; text-decoration:line-through;" if is_read else "color:#1e293b;"
                    
                    cols[1].markdown(f"<span style='{style}'>{u}</span>", unsafe_allow_html=True)
                    cols[2].markdown(f"<span style='{style}'>{row.get('彩种', '-')}</span>", unsafe_allow_html=True)
                    cols[3].markdown(f"<span class='badge-red'>{row['原因']}</span>", unsafe_allow_html=True)
                    cols[4].markdown(f"<span style='{style}'>{row['销量']:,.0f}</span>", unsafe_allow_html=True)
                    cols[5].markdown(f"<span style='{style}'>{int(row['单数'])}</span>", unsafe_allow_html=True)
                    cols[6].markdown(f"<span style='{style}'>{row['盈亏']:,.0f}</span>", unsafe_allow_html=True)
                    cols[7].markdown(f"<span style='{style}'>{row['RTP']:.3f}</span>", unsafe_allow_html=True)
                    st.divider()
            st.download_button("📥 导出结果", res.to_csv(index=False).encode('utf-8-sig'), "audit_a.csv")
        elif res is not None: st.success("✅ 扫描完毕，未发现异常。")

else: # 盈亏排行
    st.markdown("<div class='title-banner'><h1>📈 盈亏排行审计</h1></div>", unsafe_allow_html=True)
    
    col_btn, _ = st.columns([1, 4])
    # 修改：直接發送請求，不再阻擋平台為空
    if col_btn.button("🔄 獲取 API 數據", type="primary", use_container_width=True):
        with st.spinner("正在連線抓取數據..."):
            raw_data = fetch_api_data("https://stats-crawler.up.railway.app/api/open/member-income", dt_start, dt_end, api_platform)
            if raw_data is not None and not raw_data.empty:
                st.session_state.raw_data_b = raw_data
                st.session_state.read_set_b = set()
                st.success("✅ 數據獲取成功！")
            else:
                st.warning("⚠️ 此區間查無資料或回傳為空 (若上方有顯示錯誤訊息請參考)")
    
    raw_b = st.session_state.get("raw_data_b")
    all_games_b = []
    game_col_b = None
    selected_games_b = []

    if raw_b is not None:
        game_cols_b = [c for c in raw_b.columns if any(g in str(c) for g in ['彩种', '游戏', '彩种名称', 'Game', 'lottery'])]
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
                
                st.markdown("""<div class='table-header'><div style='flex:0.6'>确认</div><div style='flex:1.5'>用户名</div><div style='flex:1.5'>彩种</div><div style='flex:2.5'>异常结论</div><div style='flex:1.0'>销量</div><div style='flex:1.0'>充值</div><div style='flex:1.0'>比值</div><div style='flex:1.0'>待遇</div><div style='flex:1.0'>盈亏</div></div>""", unsafe_allow_html=True)
                with st.container(height=500):
                    for i, row in res.iterrows():
                        u = row['用户名']; is_read = u in st.session_state.get("read_set_b", set())
                        cols = st.columns([0.6, 1.5, 1.5, 2.5, 1.0, 1.0, 1.0, 1.0, 1.0])
                        if cols[0].checkbox(" ", key=f"fb_{u}_{i}", value=is_read):
                            if "read_set_b" not in st.session_state: st.session_state.read_set_b = set()
                            st.session_state.read_set_b.add(u)
                        else: st.session_state.read_set_b.discard(u)
                        style = "color:#94a3b8; text-decoration:line-through;" if is_read else "color:#1e293b;"
                        
                        cols[1].markdown(f"<span style='{style}'>{u}</span>", unsafe_allow_html=True)
                        cols[2].markdown(f"<span style='{style}'>{row.get('彩种', '-')}</span>", unsafe_allow_html=True)
                        cols[3].markdown(f"<span class='badge-giant'>{row['原因']}</span>", unsafe_allow_html=True)
                        cols[4].markdown(f"<span style='{style}'>{row['销量']:,.1f}</span>", unsafe_allow_html=True)
                        cols[5].markdown(f"<span style='{style}'>{row['充值']:,.1f}</span>", unsafe_allow_html=True)
                        cols[6].markdown(f"<span style='{style}'>{row['充销比']:.2f}</span>", unsafe_allow_html=True)
                        cols[7].markdown(f"<span style='{style}'>{row['待遇']:,.1f}</span>", unsafe_allow_html=True)
                        cols[8].markdown(f"<span style='{style}'>{row['盈亏']:,.1f}</span>", unsafe_allow_html=True)
                        st.divider()

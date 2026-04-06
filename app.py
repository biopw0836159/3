import streamlit as st
import pandas as pd
import hashlib
from streamlit_gsheets import GSheetsConnection

# 1. 頁面配置
st.set_page_config(page_title="審計專家系統 V72", layout="wide")

# 2. 注入所有原始樣式 (保留大號字體、看板顏色、紅色開關)
st.markdown("""
    <style>
    .stApp { background-color: #f8fafc; }
    [data-testid="stSidebar"] { background-color: #f1f5f9 !important; min-width: 400px !important; }
    [data-testid="stSidebar"] label, [data-testid="stSidebar"] p, [data-testid="stSidebar"] h3 { 
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

# 3. 登錄邏輯 (密碼 0224)
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

# --- ☁️ 雲端同步函數 ---
def fetch_cloud_data(worksheet_name):
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        df = conn.read(worksheet=worksheet_name, ttl=0)
        return df
    except Exception as e:
        st.sidebar.error(f"雲端讀取失敗: {e}")
        return None

# --- 核心引擎 A (用戶彩票分析邏輯) ---
def run_audit_engine(df, rules):
    try:
        df.columns = [str(c).strip() for c in df.columns]
        mapping = {'user':['用戶名','賬號','會員'],'vol':['銷量','投注'],'cnt':['單數','次數'],'profit':['盈虧','盈利'],'bonus':['獎金','派獎','中獎']}
        final_cols = {}
        for k, aliases in mapping.items():
            for col in df.columns:
                if any(a in col for a in aliases): final_cols[k] = col; break
        temp_df = pd.DataFrame()
        temp_df['用戶名'] = df[final_cols['user']].astype(str)
        temp_df['銷量'] = pd.to_numeric(df[final_cols['vol']].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
        temp_df['單數'] = pd.to_numeric(df[final_cols['cnt']].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
        temp_df['盈虧'] = pd.to_numeric(df[final_cols['profit']].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
        temp_df['獎金'] = pd.to_numeric(df[final_cols['bonus']].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
        grouped = temp_df.groupby('用戶名').agg({'銷量':'sum', '單數':'sum', '盈虧':'sum', '獎金':'sum'}).reset_index()
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
    except: return None

# --- 核心引擎 B (盈虧排行邏輯) ---
def run_strict_audit(df, cfg):
    try:
        df.columns = [str(c).strip() for c in df.columns]
        last_col = df.columns[-1]
        clean_df = pd.DataFrame()
        clean_df['用戶名'] = df['用戶名'].astype(str)
        target_cols = ['個人充值手續費', '個人派獎', '個人自身返點/返水', '個人系統分紅']
        for col in target_cols: clean_df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        clean_df['盈虧'] = pd.to_numeric(df[last_col], errors='coerce').fillna(0)
        grouped = clean_df.groupby('用戶名').agg({'個人充值手續費':'sum','個人派獎':'sum','個人自身返點/返水':'sum','個人系統分紅':'sum','盈虧':'sum'}).reset_index()
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
    except: return None

# 4. 側邊欄導航切換
with st.sidebar:
    st.markdown("## 🧭 模塊切換")
    mode = st.radio("選擇分析類型", ["用戶彩票分析", "盈虧排行"])
    st.write("---")
    if st.button("🔄 同步後台最新數據", use_container_width=True, type="primary"):
        # 同步兩張表
        st.session_state.raw_data_a = fetch_cloud_data("Sheet1")
        st.session_state.raw_data_b = fetch_cloud_data("Sheet2")
        st.toast("✅ 雲端同步完成！")

# 5. 模塊分頁邏輯
if mode == "用戶彩票分析":
    with st.sidebar:
        st.markdown("### ⚙️ 審計控制中心")
        
        # --- 新增：動態彩種篩選 ---
        selected_game = "全部彩種"
        if "raw_data_a" in st.session_state and st.session_state.raw_data_a is not None:
            df_source = st.session_state.raw_data_a
            if '彩種' in df_source.columns:
                game_list = ["全部彩種"] + sorted(df_source['彩種'].dropna().unique().tolist())
                selected_game = st.selectbox("🎯 選擇篩選彩種", game_list)
            else:
                st.warning("⚠️ 表格中未找到『彩種』欄位")

        use_manual = st.toggle("🚀 手動自定義模式", value=False)
        st.write("---")
        v_on = st.toggle("銷量篩選", False); v_min = st.number_input("Min銷量", 0.0); v_max = st.number_input("Max銷量", 2000.0)
        c_on = st.toggle("單數限制", False); c_limit = st.number_input("單數 ≤", 12)
        p_on = st.toggle("盈虧限制", False); p_min = st.number_input("Min盈虧", 100000.0); p_max = st.number_input("Max盈虧", 1000000.0)
        r_on = st.toggle("RTP限制", False); r_min = st.number_input("Min RTP", 0.995, format="%.3f"); r_max = st.number_input("Max RTP", 1.000, format="%.3f")
        manual_btn = st.button("🔥 重新計算", type="secondary")
        rules = {'use_manual':use_manual, 'v_on':v_on, 'v_min':v_min, 'v_max':v_max, 'c_on':c_on, 'c_limit':c_limit, 'p_on':p_on, 'p_min':p_min, 'p_max':p_max, 'r_on':r_on, 'r_min':r_min, 'r_max':r_max}

    st.markdown("<div class='title-banner'><h1>📊 用戶彩票分析</h1></div>", unsafe_allow_html=True)
    file = st.file_uploader("📂 手動丟這邊 (或使用左側同步)", type=["xlsx", "csv"], key="file_a")
    
    # 獲取資料
    df_to_analyze = None
    if file:
        df_to_analyze = pd.read_excel(file) if file.name.endswith('.xlsx') else pd.read_csv(file)
        st.session_state.raw_data_a = df_to_analyze
    elif "raw_data_a" in st.session_state:
        df_to_analyze = st.session_state.raw_data_a

    if df_to_analyze is not None:
        # 執行彩種過濾
        if selected_game != "全部彩種":
            df_to_analyze = df_to_analyze[df_to_analyze['彩種'] == selected_game]
            st.caption(f"📍 正在篩選彩種：{selected_game}")

        res = run_audit_engine(df_to_analyze, rules)
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
            sort_col = sc2.selectbox("排序字段", ["銷量", "盈虧", "單數", "RTP"], index=0, key="sa")
            sort_dir = sc3.selectbox("排序順序", ["由大到小", "由小到大"], index=0, key="da")
            res = res.sort_values(by=sort_col, ascending=(sort_dir == "由小到大"))
            
            st.markdown("""<div class='table-header'><div style='flex:0.8'>核查</div><div style='flex:2'>用戶名</div><div style='flex:2.5'>原因</div><div style='flex:1.5'>總銷量</div><div style='flex:1.2'>單數</div><div style='flex:1.5'>盈虧</div><div style='flex:1.2'>RTP</div></div>""", unsafe_allow_html=True)
            with st.container(height=500):
                for i, row in res.iterrows():
                    u = row['用戶名']; is_read = u in st.session_state.get("read_set_a", set())
                    cols = st.columns([0.8, 2, 2.5, 1.5, 1.2, 1.5, 1.2])
                    if cols[0].checkbox(" ", key=f"ka_{u}_{i}", value=is_read): 
                        if "read_set_a" not in st.session_state: st.session_state.read_set_a = set()
                        st.session_state.read_set_a.add(u)
                    else: st.session_state.read_set_a.discard(u)
                    style = "color:#94a3b8; text-decoration:line-through;" if is_read else "color:#1e293b;"
                    cols[1].markdown(f"<span style='{style}'>{u}</span>", unsafe_allow_html=True)
                    cols[2].markdown(f"<span class='badge-red'>{row['原因']}</span>", unsafe_allow_html=True)
                    cols[3].markdown(f"<span style='{style}'>{row['銷量']:,.0f}</span>", unsafe_allow_html=True)
                    cols[4].markdown(f"<span style='{style}'>{int(row['單數'])}</span>", unsafe_allow_html=True)
                    cols[5].markdown(f"<span style='{style}'>{row['盈虧']:,.0f}</span>", unsafe_allow_html=True)
                    cols[6].markdown(f"<span style='{style}'>{row['RTP']:.3f}</span>", unsafe_allow_html=True)
                    st.divider()
        elif res is not None: st.success("✅ 目前篩選條件下，無任何異常會員。")

else: # 盈虧排行分頁
    with st.sidebar:
        st.markdown("### 🛠️ 審計維度勾選")
        sw1 = st.checkbox("🔍 充銷比(高)審計", value=True); l_ratio_h = st.number_input("比值(高)", value=50.0) if sw1 else 50.0
        if sw1:
            c1, c2 = st.columns(2); l_win_min = c1.number_input("銷量(小)", 30000, key="wm"); l_win_max = c2.number_input("銷量(大)", 99999999, key="wx")
        else: l_win_min, l_win_max = 30000, 99999999
        sw2 = st.checkbox("🔍 充銷比(低)審計", value=True); l_ratio_l = st.number_input("比值(低)", value=2.0) if sw2 else 2.0
        if sw2:
            c3, c4 = st.columns(2); l_fee_min = c3.number_input("充值(小)", 1000, key="fm"); l_fee_max = c4.number_input("充值(大)", 2000, key="fx")
        else: l_fee_min, l_fee_max = 1000, 2000
        sw3 = st.checkbox("🔍 待遇審計", value=True); l_treat = st.number_input("待遇設定", 50000, key="tv") if sw3 else 50000
        sw4 = st.checkbox("🔍 無充下注", value=True); l_no_fee = st.number_input("下注設定", 200000, key="nv") if sw4 else 200000
        sw5 = st.checkbox("🔍 大額盈利", value=True); l_profit = st.number_input("盈利設定", 100000, key="pv") if sw5 else 100000
        audit_btn = st.button("🔥 重新排行審計", type="primary", use_container_width=True)
        config = {'sw1':sw1,'sw2':sw2,'sw3':sw3,'sw4':sw4,'sw5':sw5,'ratio_high':l_ratio_h,'win_min':l_win_min,'win_max':l_win_max,'ratio_low':l_ratio_l,'fee_min':l_fee_min,'fee_max':l_fee_max,'limit_treatment':l_treat,'no_fee_limit':l_no_fee,'profit_limit':l_profit}

    st.markdown("<div class='title-banner'><h1>📈 盈虧排行審計</h1></div>", unsafe_allow_html=True)
    file_b = st.file_uploader("📂 手動丟這邊", type=["xlsx"], key="file_b")
    
    df_b = None
    if file_b:
        df_b = pd.read_excel(file_b)
        st.session_state.raw_data_b = df_b
    elif "raw_data_b" in st.session_state:
        df_b = st.session_state.raw_data_b

    if df_b is not None:
        res_b = run_strict_audit(df_b, config)
        if res_b is not None:
            st.markdown(f"<div class='metric-card-b'><div style='font-size:14px;color:#64748b'>符合選定區間異常人數</div><div class='metric-value'>{len(res_b)}</div></div>", unsafe_allow_html=True)
            if not res_b.empty:
                sc1, sc2, sc3 = st.columns([1, 2, 2])
                sort_col = sc2.selectbox("排序字段", ["銷量", "充值", "充銷比", "待遇", "盈虧"], index=4, key="sb")
                sort_dir = sc3.selectbox("排序方向", ["由大到小", "由小到大"], index=0, key="db")
                res_b = res_b.sort_values(by=sort_col, ascending=(sort_dir == "由小到大"))
                st.markdown("""<div class='table-header'><div style='flex:0.8'>確認</div><div style='flex:1.5'>用戶名</div><div style='flex:3'>異常結論 (大號字體)</div><div style='flex:1.2'>銷量</div><div style='flex:1.2'>充值</div><div style='flex:1.2'>比值</div><div style='flex:1.2'>待遇</div><div style='flex:1.2'>盈虧</div></div>""", unsafe_allow_html=True)
                with st.container(height=500):
                    for i, row in res_b.iterrows():
                        u = row['用戶名']; is_read = u in st.session_state.get("read_set_b", set())
                        cols = st.columns([0.8, 1.5, 3, 1.2, 1.2, 1.2, 1.2, 1.2])
                        if cols[0].checkbox(" ", key=f"fb_{u}_{i}", value=is_read):
                            if "read_set_b" not in st.session_state: st.session_state.read_set_b = set()
                            st.session_state.read_set_b.add(u)
                        else: st.session_state.read_set_b.discard(u)
                        style = "color:#94a3b8; text-decoration:line-through;" if is_read else "color:#1e293b;"
                        cols[1].markdown(f"<span style='{style}'>{u}</span>", unsafe_allow_html=True)
                        cols[2].markdown(f"<span class='badge-giant'>{row['原因']}</span>", unsafe_allow_html=True)
                        cols[3].markdown(f"<span style='{style}'>{row['銷量']:,.1f}</span>", unsafe_allow_html=True)
                        cols[4].markdown(f"<span style='{style}'>{row['充值']:,.1f}</span>", unsafe_allow_html=True)
                        cols[5].markdown(f"<span style='{style}'>{row['充銷比']:.2f}</span>", unsafe_allow_html=True)
                        cols[6].markdown(f"<span style='{style}'>{row['待遇']:,.1f}</span>", unsafe_allow_html=True)
                        cols[7].markdown(f"<span style='{style}'>{row['盈虧']:,.1f}</span>", unsafe_allow_html=True)
                        st.divider()

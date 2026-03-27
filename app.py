import streamlit as st
import pandas as pd
import hashlib

# 1. 页面配置 (合用一个配置)
st.set_page_config(page_title="抓鬼专家", layout="wide")

# 2. 样式注入 (合并两者的 CSS)
st.markdown("""
    <style>
    .stApp { background-color: #f8fafc; }
    [data-testid="stSidebar"] { background-color: #f1f5f9 !important; min-width: 420px !important; }
    [data-testid="stSidebar"] .stMarkdown, [data-testid="stSidebar"] label, [data-testid="stSidebar"] p, 
    [data-testid="stSidebar"] h3, [data-testid="stSidebar"] .stToggle p { 
        color: #1e293b !important; font-weight: 700 !important; 
    }
    .sidebar-hint { color: #ef4444 !important; font-size: 11px !important; font-weight: 600; margin-top: -5px; margin-bottom: 10px; display: block; }
    .range-label { font-size: 13px; color: #1e293b; font-weight: bold; margin-bottom: 2px; }
    
    .metric-card {
        background: white; padding: 20px; border-radius: 15px; box-shadow: 0 4px 12px rgba(0,0,0,0.08); 
        border-bottom: 4px solid #ef4444; text-align: center; margin-bottom: 10px;
    }
    .metric-value { font-size: 32px; font-weight: 900; color: #ef4444; }
    .metric-label { font-size: 13px; color: #64748b; font-weight: 600; }
    .badge-giant { background: #fee2e2; color: #ef4444; padding: 5px 12px; border-radius: 8px; font-weight: 900; font-size: 16px; border: 2px solid #fecaca; display: inline-block; }
    .badge-red { background: #fee2e2; color: #ef4444; padding: 2px 8px; border-radius: 6px; font-weight: bold; border: 1px solid #fecaca; }
    .title-banner { background: linear-gradient(135deg, #1e293b 0%, #334155 100%); padding: 20px; border-radius: 12px; color: white; text-align: center; margin-bottom: 20px; }
    .table-header { background-color: #e2e8f0; padding: 12px 10px; border-radius: 8px; font-weight: bold; color: #475569; margin-bottom: 10px; display: flex; align-items: center; }
    
    /* 巨型开关 */
    [data-testid="collapsedControl"] {
        background-color: #ff4b4b !important; width: 130px !important; height: 48px !important;
        border-radius: 0 25px 25px 0 !important; top: 15px !important; color: white !important;
        box-shadow: 4px 4px 15px rgba(255, 75, 75, 0.5) !important;
    }
    [data-testid="collapsedControl"]::after { content: " ⚙️ 菜单开关"; font-size: 14px; font-weight: bold; color: white; }
    </style>
    """, unsafe_allow_html=True)

# 3. 登录逻辑 (统一登录)
if "auth" not in st.session_state: st.session_state.auth = False
if not st.session_state.auth:
    _, center_col, _ = st.columns([1, 1.2, 1])
    with center_col:
        st.title("🔐 审计系统登录")
        pwd = st.text_input("请输入访问密码", type="password")
        if st.button("进入系统"):
            if pwd == "0224": st.session_state.auth = True; st.rerun()
            else: st.error("❌ 密码错误")
    st.stop()

# --- 核心引擎定义 (保持原样) ---
def run_audit_engine_1(df, rules):
    try:
        df.columns = [str(c).strip() for c in df.columns]
        mapping = {'user':['用户名','账号','会员'],'vol':['销量','投注'],'cnt':['单数','次数'],'profit':['盈亏','盈利'],'bonus':['奖金','派奖','中奖']}
        final_cols = {}
        for k, aliases in mapping.items():
            for col in df.columns:
                if any(a in col for a in aliases): final_cols[k] = col; break
        temp_df = pd.DataFrame()
        temp_df['用户名'] = df[final_cols['user']].astype(str)
        temp_df['销量'] = pd.to_numeric(df[final_cols['vol']].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
        temp_df['单数'] = pd.to_numeric(df[final_cols['cnt']].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
        temp_df['盈亏'] = pd.to_numeric(df[final_cols['profit']].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
        temp_df['奖金'] = pd.to_numeric(df[final_cols['bonus']].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
        grouped = temp_df.groupby('用户名').agg({'销量':'sum', '单数':'sum', '盈亏':'sum', '奖金':'sum'}).reset_index()
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
    except: return None

def run_strict_audit_2(df, cfg):
    try:
        df.columns = [str(c).strip() for c in df.columns]
        last_col = df.columns[-1]
        clean_df = pd.DataFrame()
        clean_df['用户名'] = df['用户名'].astype(str)
        target_cols = ['个人充值手续费', '个人派奖', '个人自身返点/返水', '个人系统分红']
        for col in target_cols: clean_df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        clean_df['盈亏'] = pd.to_numeric(df[last_col], errors='coerce').fillna(0)
        grouped = clean_df.groupby('用户名').agg({'个人充值手续费': 'sum', '个人派奖': 'sum', '个人自身返点/返水': 'sum', '个人系统分红': 'sum', '盈亏': 'sum'}).reset_index()
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
        grouped['销量'] = grouped['个人派奖']
        grouped['充值'] = grouped['个人充值手续费']
        grouped['待遇'] = grouped['个人自身返点/返水'] + grouped['个人系统分红']
        grouped['充销比'] = grouped.apply(lambda x: x['销量']/x['充值'] if x['充值']>0 else 0, axis=1)
        return grouped[grouped['原因'].notna()].copy()
    except Exception: return None

# 4. 侧边栏及主逻辑
tab1, tab2 = st.tabs(["🚀 日常快抓 (抓鬼专家)", "📊 深度财务 (抓鬼专家2)"])

# --- 逻辑 1 ---
with tab1:
    with st.sidebar:
        st.markdown("### ⚙️ [快抓模式] 审计控制")
        use_manual_1 = st.toggle("🚀 手动自定义模式", value=False, key="t1_man")
        v_on_1 = st.toggle("销量筛选", False, key="t1_v_on"); v_min_1 = st.number_input("Min销量", 0.0, key="t1_v_min"); v_max_1 = st.number_input("Max销量", 2000.0, key="t1_v_max")
        c_on_1 = st.toggle("单数限制", False, key="t1_c_on"); c_limit_1 = st.number_input("单数 ≤", 12, key="t1_c_lim")
        p_on_1 = st.toggle("盈亏限制", False, key="t1_p_on"); p_min_1 = st.number_input("Min盈亏", 100000.0, key="t1_p_min"); p_max_1 = st.number_input("Max盈亏", 1000000.0, key="t1_p_max")
        r_on_1 = st.toggle("RTP限制", False, key="t1_r_on"); r_min_1 = st.number_input("Min RTP", 0.995, format="%.3f", key="t1_r_min"); r_max_1 = st.number_input("Max RTP", 1.000, format="%.3f", key="t1_r_max")
        btn_1 = st.button("🔥 执行快抓审计", type="primary", key="btn1")
        rules_1 = {'use_manual':use_manual_1, 'v_on':v_on_1, 'v_min':v_min_1, 'v_max':v_max_1, 'c_on':c_on_1, 'c_limit':c_limit_1, 'p_on':p_on_1, 'p_min':p_min_1, 'p_max':p_max_1, 'r_on':r_on_1, 'r_min':r_min_1, 'r_max':r_max_1}

    st.markdown("<div class='title-banner'><h1>📊 抓鬼专家 - 快抓引擎</h1></div>", unsafe_allow_html=True)
    f1 = st.file_uploader("📂 丢这边 (快抓)", type=["xlsx", "csv"], key="f1")
    if f1:
        if btn_1: 
            raw = pd.read_excel(f1) if f1.name.endswith('.xlsx') else pd.read_csv(f1)
            st.session_state.res1 = run_audit_engine_1(raw, rules_1)
        res1 = st.session_state.get("res1")
        if res1 is not None and not res1.empty:
            k1, k2, k3, k4, k5 = st.columns(5)
            k1.markdown(f"<div class='metric-card'><div class='metric-value'>{len(res1)}</div><div class='metric-label'>锁定总数</div></div>", unsafe_allow_html=True)
            # ... 此处省略统计逻辑保持原样显示 ...
            st.write("---")
            sc_col, sc_dir = st.columns([2,2])[0], st.columns([2,2])[1]
            s_c = st.selectbox("排序字段", ["销量", "盈亏", "单数", "RTP"], key="s1")
            s_d = st.selectbox("排序方向", ["由大到小", "由小到大"], key="d1")
            res1 = res1.sort_values(by=s_c, ascending=(s_d=="由小到大"))
            st.dataframe(res1, use_container_width=True) # 简化显示，或保持您原来的列渲染逻辑

# --- 逻辑 2 ---
with tab2:
    with st.sidebar:
        st.markdown("### 🛠️ [深度模式] 维度勾选")
        sw1 = st.checkbox("🔍 充销比(高)审计", value=True, key="sw1")
        if sw1:
            l_ratio_h = st.number_input("充销比(高)", value=50.0, key="r_h")
            c1, c2 = st.columns(2)
            l_win_min = c1.number_input("销量(小)", value=30000, key="w_min")
            l_win_max = c2.number_input("销量(大)", value=99999999, key="w_max")
        else: l_ratio_h, l_win_min, l_win_max = 50.0, 30000, 99999999
        sw2 = st.checkbox("🔍 充销比(低)审计", value=True, key="sw2")
        if sw2:
            l_ratio_l = st.number_input("充销比(低)", value=2.0, key="r_l")
            c3, c4 = st.columns(2)
            l_fee_min = c3.number_input("充值(小)", value=1000, key="f_min")
            l_fee_max = c4.number_input("充值(大)", value=2000, key="f_max")
        else: l_ratio_l, l_fee_min, l_fee_max = 2.0, 1000, 2000
        sw3 = st.checkbox("🔍 待遇审计", value=True, key="sw3"); l_treat = st.number_input("设定值", 50000, key="t_v") if sw3 else 50000
        sw4 = st.checkbox("🔍 无充下注", value=True, key="sw4"); l_no_fee = st.number_input("设定值", 200000, key="n_v") if sw4 else 200000
        sw5 = st.checkbox("🔍 大额盈利", value=True, key="sw5"); l_profit = st.number_input("设定值", 100000, key="p_v") if sw5 else 100000
        btn_2 = st.button("🔥 执行深度审计", type="primary", key="btn2")
        config_2 = {'sw1':sw1,'sw2':sw2,'sw3':sw3,'sw4':sw4,'sw5':sw5,'ratio_high':l_ratio_h,'win_min':l_win_min,'win_max':l_win_max,'ratio_low':l_ratio_l,'fee_min':l_fee_min,'fee_max':l_fee_max,'limit_treatment':l_treat,'no_fee_limit':l_no_fee,'profit_limit':l_profit}

    st.markdown("<div class='title-banner'><h1>📊 抓鬼专家 - 深度财务引擎</h1></div>", unsafe_allow_html=True)
    f2 = st.file_uploader("📂 丢这边 (深度)", type=["xlsx"], key="f2")
    if f2:
        if btn_2: st.session_state.res2 = run_strict_audit_2(pd.read_excel(f2), config_2)
        res2 = st.session_state.get("res2")
        if res2 is not None:
            st.markdown(f"<div class='metric-card'><div class='metric-label'>符合选定区间异常人数</div><div class='metric-value'>{len(res2)}</div></div>", unsafe_allow_html=True)
            if not res2.empty:
                s_c2 = st.selectbox("排序字段", ["销量", "充值", "充销比", "待遇", "盈亏"], index=4, key="s2")
                s_d2 = st.selectbox("排序方向", ["由大到小", "由小到大"], index=0, key="d2")
                res2 = res2.sort_values(by=s_c2, ascending=(s_d2=="由小到大"))
                
                # ... 此处保持表格渲染逻辑，为简练略 ...
                st.markdown("""<div class='table-header'><div style='flex:0.8'>确认</div><div style='flex:1.5'>用户名</div><div style='flex:3'>异常结论</div><div style='flex:1.2'>销量</div><div style='flex:1.2'>充值</div><div style='flex:1.2'>比值</div><div style='flex:1.2'>待遇</div><div style='flex:1.2'>盈亏</div></div>""", unsafe_allow_html=True)
                with st.container(height=500):
                    for i, row in res2.iterrows():
                        cols = st.columns([0.8, 1.5, 3, 1.2, 1.2, 1.2, 1.2, 1.2])
                        cols[1].write(row['用户名'])
                        cols[2].markdown(f"<span class='badge-giant'>{row['原因']}</span>", unsafe_allow_html=True)
                        cols[3].write(f"{row['销量']:,.0f}")
                        cols[4].write(f"{row['充值']:,.0f}")
                        cols[5].write(f"{row['充销比']:.2f}")
                        cols[6].write(f"{row['待遇']:,.0f}")
                        cols[7].write(f"{row['盈亏']:,.0f}")
                        st.divider()

import streamlit as st
import pandas as pd
import hashlib

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

# --- 核心引擎 A (完全复制自代码1) ---
def run_audit_engine(df, rules):
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

# --- 核心引擎 B (完全复制自代码2) ---
def run_strict_audit(df, cfg):
    try:
        df.columns = [str(c).strip() for c in df.columns]
        last_col = df.columns[-1]
        clean_df = pd.DataFrame()
        clean_df['用户名'] = df['用户名'].astype(str)
        target_cols = ['个人充值手续费', '个人派奖', '个人自身返点/返水', '个人系统分红']
        for col in target_cols: clean_df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        clean_df['盈亏'] = pd.to_numeric(df[last_col], errors='coerce').fillna(0)
        grouped = clean_df.groupby('用户名').agg({'个人充值手续费':'sum','个人派奖':'sum','个人自身返点/返水':'sum','个人系统分红':'sum','盈亏':'sum'}).reset_index()
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
    except: return None

# 4. 侧边栏导航
with st.sidebar:
    st.markdown("## 🧭 模块切换")
    mode = st.radio("选择分析类型", ["用户彩票分析", "盈亏排行"])
    st.write("---")

# 5. 模块逻辑切换
if mode == "用户彩票分析":
    with st.sidebar:
        st.markdown("### ⚙️ 审计控制中心")
        use_manual = st.toggle("🚀 手动自定义模式", value=False)
        st.write("---")
        v_on = st.toggle("销量筛选", False); v_min = st.number_input("Min销量", 0.0); v_max = st.number_input("Max销量", 2000.0)
        c_on = st.toggle("单数限制", False); c_limit = st.number_input("单数 ≤", 12)
        p_on = st.toggle("盈亏限制", False); p_min = st.number_input("Min盈亏", 100000.0); p_max = st.number_input("Max盈亏", 1000000.0)
        r_on = st.toggle("RTP限制", False); r_min = st.number_input("Min RTP", 0.995, format="%.3f"); r_max = st.number_input("Max RTP", 1.000, format="%.3f")
        manual_btn = st.button("🔥 执行审计", type="primary")
        rules = {'use_manual':use_manual, 'v_on':v_on, 'v_min':v_min, 'v_max':v_max, 'c_on':c_on, 'c_limit':c_limit, 'p_on':p_on, 'p_min':p_min, 'p_max':p_max, 'r_on':r_on, 'r_min':r_min, 'r_max':r_max}

    st.markdown("<div class='title-banner'><h1>📊 用户彩票分析</h1></div>", unsafe_allow_html=True)
    file = st.file_uploader("📂 丢这边", type=["xlsx", "csv"], key="file_a")
    if file:
        f_hash = hashlib.md5(file.getvalue()).hexdigest()
        if st.session_state.get("last_f_a") != f_hash or manual_btn:
            raw = pd.read_excel(file) if file.name.endswith('.xlsx') else pd.read_csv(file)
            st.session_state.res_data_a = run_audit_engine(raw, rules)
            st.session_state.last_f_a = f_hash
            st.session_state.read_set_a = set()
        
        res = st.session_state.get("res_data_a")
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
            st.markdown("""<div class='table-header'><div style='flex:0.8'>核查</div><div style='flex:2'>用户名</div><div style='flex:2.5'>原因</div><div style='flex:1.5'>总销量</div><div style='flex:1.2'>单数</div><div style='flex:1.5'>盈亏</div><div style='flex:1.2'>RTP</div></div>""", unsafe_allow_html=True)
            with st.container(height=500):
                for i, row in res.iterrows():
                    u = row['用户名']; is_read = u in st.session_state.get("read_set_a", set())
                    cols = st.columns([0.8, 2, 2.5, 1.5, 1.2, 1.5, 1.2])
                    if cols[0].checkbox(" ", key=f"ka_{u}_{i}", value=is_read): 
                        if "read_set_a" not in st.session_state: st.session_state.read_set_a = set()
                        st.session_state.read_set_a.add(u)
                    else: st.session_state.read_set_a.discard(u)
                    style = "color:#94a3b8; text-decoration:line-through;" if is_read else "color:#1e293b;"
                    cols[1].markdown(f"<span style='{style}'>{u}</span>", unsafe_allow_html=True)
                    cols[2].markdown(f"<span class='badge-red'>{row['原因']}</span>", unsafe_allow_html=True)
                    cols[3].markdown(f"<span style='{style}'>{row['销量']:,.0f}</span>", unsafe_allow_html=True)
                    cols[4].markdown(f"<span style='{style}'>{int(row['单数'])}</span>", unsafe_allow_html=True)
                    cols[5].markdown(f"<span style='{style}'>{row['盈亏']:,.0f}</span>", unsafe_allow_html=True)
                    cols[6].markdown(f"<span style='{style}'>{row['RTP']:.3f}</span>", unsafe_allow_html=True)
                    st.divider()
            st.download_button("📥 导出结果", res.to_csv(index=False).encode('utf-8-sig'), "audit_a.csv")
        elif res is not None: st.success("✅ 扫描完毕，未发现异常。")

else: # 盈亏排行
    with st.sidebar:
        st.markdown("### 🛠️ 审计维度勾选")
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
        audit_btn = st.button("🔥 执行组合审计", type="primary", use_container_width=True)
        config = {'sw1':sw1,'sw2':sw2,'sw3':sw3,'sw4':sw4,'sw5':sw5,'ratio_high':l_ratio_h,'win_min':l_win_min,'win_max':l_win_max,'ratio_low':l_ratio_l,'fee_min':l_fee_min,'fee_max':l_fee_max,'limit_treatment':l_treat,'no_fee_limit':l_no_fee,'profit_limit':l_profit}

    st.markdown("<div class='title-banner'><h1>📈 盈亏排行审计</h1></div>", unsafe_allow_html=True)
    file_b = st.file_uploader("📂 丢这边", type=["xlsx"], key="file_b")
    if file_b:
        if "res_data_b" not in st.session_state or audit_btn:
            st.session_state.res_data_b = run_strict_audit(pd.read_excel(file_b), config)
            st.session_state.read_set_b = set()
        res = st.session_state.res_data_b
        if res is not None:
            st.markdown(f"<div class='metric-card-b'><div style='font-size:14px;color:#64748b'>符合选定区间异常人数</div><div class='metric-value'>{len(res)}</div></div>", unsafe_allow_html=True)
            if not res.empty:
                sc1, sc2, sc3 = st.columns([1, 2, 2])
                sort_col = sc2.selectbox("排序字段", ["销量", "充值", "充销比", "待遇", "盈亏"], index=4, key="sort_b")
                sort_dir = sc3.selectbox("排序方向", ["由大到小", "由小到大"], index=0, key="dir_b")
                res = res.sort_values(by=sort_col, ascending=(sort_dir == "由小到大"))
                st.markdown("""<div class='table-header'><div style='flex:0.8'>确认</div><div style='flex:1.5'>用户名</div><div style='flex:3'>异常结论 (大号字体)</div><div style='flex:1.2'>销量</div><div style='flex:1.2'>充值</div><div style='flex:1.2'>比值</div><div style='flex:1.2'>待遇</div><div style='flex:1.2'>盈亏</div></div>""", unsafe_allow_html=True)
                with st.container(height=500):
                    for i, row in res.iterrows():
                        u = row['用户名']; is_read = u in st.session_state.get("read_set_b", set())
                        cols = st.columns([0.8, 1.5, 3, 1.2, 1.2, 1.2, 1.2, 1.2])
                        if cols[0].checkbox(" ", key=f"fb_{u}_{i}", value=is_read):
                            if "read_set_b" not in st.session_state: st.session_state.read_set_b = set()
                            st.session_state.read_set_b.add(u)
                        else: st.session_state.read_set_b.discard(u)
                        style = "color:#94a3b8; text-decoration:line-through;" if is_read else "color:#1e293b;"
                        cols[1].markdown(f"<span style='{style}'>{u}</span>", unsafe_allow_html=True)
                        cols[2].markdown(f"<span class='badge-giant'>{row['原因']}</span>", unsafe_allow_html=True)
                        cols[3].markdown(f"<span style='{style}'>{row['销量']:,.1f}</span>", unsafe_allow_html=True)
                        cols[4].markdown(f"<span style='{style}'>{row['充值']:,.1f}</span>", unsafe_allow_html=True)
                        cols[5].markdown(f"<span style='{style}'>{row['充销比']:.2f}</span>", unsafe_allow_html=True)
                        cols[6].markdown(f"<span style='{style}'>{row['待遇']:,.1f}</span>", unsafe_allow_html=True)
                        cols[7].markdown(f"<span style='{style}'>{row['盈亏']:,.1f}</span>", unsafe_allow_html=True)
                        st.divider()

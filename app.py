import streamlit as st
import pandas as pd
import hashlib

# 1. 页面配置
st.set_page_config(page_title="抓鬼专家", layout="wide")

# 2. 注入样式 (保持所有名目与颜色)
st.markdown("""
    <style>
    .stApp { background-color: #f8fafc; }
    [data-testid="stSidebar"] { background-color: #f1f5f9 !important; min-width: 400px !important; }
    [data-testid="stSidebar"] label, [data-testid="stSidebar"] p, [data-testid="stSidebar"] h3 { 
        color: #1e293b !important; font-weight: 700 !important; 
    }
    .metric-card {
        background: white; padding: 20px; border-radius: 15px; box-shadow: 0 4px 12px rgba(0,0,0,0.08); 
        border-bottom: 4px solid #ef4444; text-align: center; margin-bottom: 10px;
    }
    .metric-value { font-size: 32px; font-weight: 900; color: #ef4444; }
    .badge-giant { background: #fee2e2; color: #ef4444; padding: 5px 12px; border-radius: 8px; font-weight: 900; font-size: 16px; border: 2px solid #fecaca; display: inline-block; }
    .badge-red { background: #fee2e2; color: #ef4444; padding: 2px 8px; border-radius: 6px; font-weight: bold; border: 1px solid #fecaca; }
    .title-banner { background: linear-gradient(135deg, #1e293b 0%, #334155 100%); padding: 20px; border-radius: 12px; color: white; text-align: center; margin-bottom: 20px; }
    .table-header { background-color: #e2e8f0; padding: 12px 10px; border-radius: 8px; font-weight: bold; color: #475569; margin-bottom: 10px; display: flex; align-items: center; }
    </style>
    """, unsafe_allow_html=True)

# 3. 登录逻辑 (0224)
if "auth" not in st.session_state: st.session_state.auth = False
if not st.session_state.auth:
    _, center_col, _ = st.columns([1, 1.2, 1])
    with center_col:
        st.title("🔐 欢迎光临")
        pwd = st.text_input("请输入访问密码", type="password")
        if st.button("进入系统"):
            if pwd == "0224": st.session_state.auth = True; st.rerun()
    st.stop()

# --- 核心引擎 (原封不动) ---
def engine_lottery(df, rules):
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

def engine_profit(df, cfg):
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
        grouped['销量'] = grouped['个人派奖']; grouped['充值'] = grouped['个人充值手续费']
        grouped['待遇'] = grouped['个人自身返点/返水'] + grouped['个人系统分红']
        grouped['充销比'] = grouped.apply(lambda x: x['销量']/x['充值'] if x['充值']>0 else 0, axis=1)
        return grouped[grouped['原因'].notna()].copy()
    except: return None

# 4. 标签页逻辑
tab_a, tab_b = st.tabs(["🚀 用户彩票分析", "📊 盈亏排行"])

# --- [分页 A: 用户彩票分析] ---
with tab_a:
    with st.sidebar:
        st.markdown("### ⚙️ [彩票分析] 筛选")
        use_manual_a = st.toggle("🚀 手动自定义模式", value=False, key="ma")
        v_on_a = st.toggle("销量筛选", False, key="va"); v_min_a = st.number_input("Min销量", 0.0, key="vmina"); v_max_a = st.number_input("Max销量", 2000.0, key="vmaxa")
        c_on_a = st.toggle("单数限制", False, key="ca"); c_limit_a = st.number_input("单数 ≤", 12, key="clima")
        p_on_a = st.toggle("盈亏限制", False, key="pa"); p_min_a = st.number_input("Min盈亏", 100000.0, key="pmina"); p_max_a = st.number_input("Max盈亏", 1000000.0, key="pmaxa")
        r_on_a = st.toggle("RTP限制", False, key="ra"); r_min_a = st.number_input("Min RTP", 0.995, format="%.3f", key="rmina"); r_max_a = st.number_input("Max RTP", 1.000, format="%.3f", key="rmaxa")
        btn_a = st.button("🔥 执行分析", type="primary", key="btna")
        rules_a = {'use_manual':use_manual_a, 'v_on':v_on_a, 'v_min':v_min_a, 'v_max':v_max_a, 'c_on':c_on_a, 'c_limit':c_limit_a, 'p_on':p_on_a, 'p_min':p_min_a, 'p_max':p_max_a, 'r_on':r_on_a, 'r_min':r_min_a, 'r_max':r_max_a}

    st.markdown("<div class='title-banner'><h1>📊 用户彩票分析</h1></div>", unsafe_allow_html=True)
    f_a = st.file_uploader("📂 丢这边 ", type=["xlsx", "csv"], key="fa")
    if f_a:
        if btn_a: st.session_state.ra = engine_lottery(pd.read_excel(f_a) if f_a.name.endswith('.xlsx') else pd.read_csv(f_a), rules_a)
        res_a = st.session_state.get("ra")
        if res_a is not None and not res_a.empty:
            st.dataframe(res_a, use_container_width=True)

# --- [分页 B: 盈亏排行] ---
with tab_b:
    with st.sidebar:
        st.markdown("### 🛠️ [盈亏排行] 维度勾选")
        sw1 = st.checkbox("🔍 充销比(高)审计", value=True, key="s1"); l_rh = st.number_input("设定值", 50.0, key="rh") if sw1 else 50.0
        c1, c2 = st.columns(2)
        l_wmin = c1.number_input("销量(小)", 30000, key="wm") if sw1 else 30000
        l_wmax = c2.number_input("销量(大)", 99999999, key="wx") if sw1 else 99999999
        
        sw2 = st.checkbox("🔍 充销比(低)审计", value=True, key="s2"); l_rl = st.number_input("设定值", 2.0, key="rl") if sw2 else 2.0
        c3, c4 = st.columns(2)
        l_fmin = c3.number_input("充值(小)", 1000, key="fm") if sw2 else 1000
        l_fmax = c4.number_input("充值(大)", 2000, key="fx") if sw2 else 2000
        
        sw3 = st.checkbox("🔍 待遇审计", value=True, key="s3"); l_tr = st.number_input("返点+工资设定", 50000, key="tv") if sw3 else 50000
        sw4 = st.checkbox("🔍 无充值下注", value=True, key="s4"); l_nf = st.number_input("下注额设定", 200000, key="nv") if sw4 else 200000
        sw5 = st.checkbox("🔍 大额盈利", value=True, key="s5"); l_pr = st.number_input("盈利设定", 100000, key="pv") if sw5 else 100000
        btn_b = st.button("🔥 执行排行审计", type="primary", key="btnb")
        cfg_b = {'sw1':sw1,'sw2':sw2,'sw3':sw3,'sw4':sw4,'sw5':sw5,'ratio_high':l_rh,'win_min':l_wmin,'win_max':l_wmax,'ratio_low':l_rl,'fee_min':l_fmin,'fee_max':l_fmax,'limit_treatment':l_tr,'no_fee_limit':l_nf,'profit_limit':l_pr}

    st.markdown("<div class='title-banner'><h1>📈 盈亏排行审计</h1></div>", unsafe_allow_html=True)
    f_b = st.file_uploader("📂 丢这边", type=["xlsx"], key="fb")
    if f_b:
        if btn_b: st.session_state.rb = engine_profit(pd.read_excel(f_b), cfg_b)
        res_b = st.session_state.get("rb")
        if res_b is not None:
            st.dataframe(res_b, use_container_width=True)

import streamlit as st
import pandas as pd
import hashlib

# 1. 页面配置
st.set_page_config(page_title="抓鬼专家", layout="wide")

# 2. 极致美化 CSS + 侧边栏箭头增强
st.markdown("""
    <style>
    .stApp { background-color: #f8fafc; }
    /* 侧边栏背景 */
    [data-testid="stSidebar"] { background-color: #1e293b !important; min-width: 350px !important; }
    [data-testid="stSidebar"] .stMarkdown, [data-testid="stSidebar"] label, [data-testid="stSidebar"] p, [data-testid="stSidebar"] h3 { 
        color: #ffffff !important; font-weight: 600 !important;
    }
    
    /* 【核心：增强左上角折叠按钮的可见度】 */
    [data-testid="collapsedControl"] {
        background-color: #ef4444 !important; /* 亮红色背景 */
        border-radius: 0 10px 10px 0 !important;
        width: 50px !important;
        height: 50px !important;
        top: 10px !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        box-shadow: 2px 2px 10px rgba(0,0,0,0.3) !important;
        z-index: 999999 !important;
    }
    [data-testid="collapsedControl"] svg {
        color: white !important; /* 箭头变白色 */
        transform: scale(1.5) !important; /* 箭头变大 */
    }
    
    /* 强力闪烁动画，提醒老大这里有开关 */
    @keyframes pulse-red {
        0% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.7); }
        70% { box-shadow: 0 0 0 15px rgba(239, 68, 68, 0); }
        100% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0); }
    }
    [data-testid="collapsedControl"] {
        animation: pulse-red 2s infinite;
    }

    div.stButton > button {
        width: 100%; border-radius: 8px; font-weight: bold;
        background-color: #ef4444 !important; color: white !important;
        border: none; padding: 12px;
    }
    .title-banner {
        background: linear-gradient(135deg, #0f172a 0%, #334155 100%);
        padding: 20px; border-radius: 12px; color: white; text-align: center; margin-bottom: 20px;
    }
    .badge {
        background-color: #fee2e2; color: #ef4444; padding: 2px 8px; 
        border-radius: 6px; font-size: 11px; font-weight: bold; border: 1px solid #fecaca;
    }
    .table-header {
        background-color: #e2e8f0; padding: 12px 10px; border-radius: 8px;
        font-weight: bold; color: #475569; margin-bottom: 10px; display: flex; align-items: center;
    }
    </style>
    """, unsafe_allow_html=True)

# 3. 登录逻辑 (0224)
if "auth" not in st.session_state: st.session_state.auth = False
if not st.session_state.auth:
    c1, c2, c3 = st.columns([1, 1.2, 1])
    with c2:
        st.title("🔐 请进")
        pwd = st.text_input("请输入访问密码", type="password")
        if st.button("进入系统"):
            if pwd == "0224": st.session_state.auth = True; st.rerun()
            else: st.error("密码错误")
    st.stop()

# 4. 核心审计引擎
def run_audit_engine(df, rules):
    try:
        df.columns = [str(c).strip() for c in df.columns]
        mapping = {'user':['用户名','账号','会员'],'vol':['销量','投注'],'cnt':['单数','次数'],'profit':['盈亏','盈利'],'rtp':['RTP','返还']}
        final_cols = {}
        for k, v in mapping.items():
            for c in df.columns:
                if any(a in c for a in v): final_cols[k] = c; break
        
        temp_df = pd.DataFrame()
        temp_df['用户名'] = df[final_cols['user']].astype(str)
        temp_df['销量'] = pd.to_numeric(df[final_cols['vol']].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
        temp_df['单数'] = pd.to_numeric(df[final_cols['cnt']].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
        temp_df['盈亏'] = pd.to_numeric(df[final_cols['profit']].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
        rtp_raw = pd.to_numeric(df[final_cols['rtp']].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
        temp_df['派奖额'] = temp_df['销量'] * rtp_raw

        grouped = temp_df.groupby('用户名').agg({'销量':'sum','单数':'sum','盈亏':'sum','派奖额':'sum'}).reset_index()
        grouped['RTP'] = grouped.apply(lambda x: x['派奖额'] / x['销量'] if x['销量'] > 0 else 0, axis=1)

        def apply_logic(row):
            v, c, p, r = row['销量'], row['单数'], row['盈亏'], row['RTP']
            if rules.get('use_manual', False):
                if rules['v_on'] and not (rules['v_min'] <= v <= rules['v_max']): return None
                if rules['c_on'] and not (c <= rules['c_limit']): return None
                if rules['p_on'] and not (rules['p_min'] <= p <= rules['p_max']): return None
                if rules['r_on'] and not (rules['r_min'] <= r <= rules['r_max']): return None
                return "手动筛选"
            m = []
            if 1000 <= v <= 2000 and c <= 12: m.append("疑似刷人数")
            if v > 2000 and c <= 10: m.append("疑似对刷")
            if v >= 500000 and 0.995 <= r <= 1.000: m.append("疑似刷量")
            if p >= 100000: m.append("盈利大会员")
            return " | ".join(m) if m else None

        grouped['原因'] = grouped.apply(apply_logic, axis=1)
        return grouped[grouped['原因'].notna()].copy()
    except: return None

# 5. 侧边栏
with st.sidebar:
    st.markdown("### ⚙️ 筛选控制台")
    st.markdown("👈 **点左上角红方块收起/展开**")
    use_manual = st.toggle("🚀 开启手动模式", value=False)
    v_on = st.toggle("销量筛选", False); v_min = st.number_input("Min", 0.0); v_max = st.number_input("Max", 2000.0)
    c_on = st.toggle("单数筛选", False); c_limit = st.number_input("单数 ≤", 12)
    p_on = st.toggle("盈亏筛选", False); p_min = st.number_input("盈亏 Min", -1000000.0); p_max = st.number_input("盈亏 Max", 100000.0)
    r_on = st.toggle("RTP筛选", False); r_min = st.number_input("RTP Min", 0.0); r_max = st.number_input("RTP Max", 1.0)
    manual_btn = st.button("✅ 确定执行手动筛选")
    rules = {'use_manual':use_manual, 'v_on':v_on, 'v_min':v_min, 'v_max':v_max, 'c_on':c_on, 'c_limit':c_limit, 'p_on':p_on, 'p_min':p_min, 'p_max':p_max, 'r_on':r_on, 'r_min':r_min, 'r_max':r_max}

# 6. 主页面
st.markdown("<div class='title-banner'><h1>📊 抓抓抓</h1></div>", unsafe_allow_html=True)
file = st.file_uploader("📂 丢这边", type=["xlsx", "csv"])

if file:
    current_hash = hashlib.md5(file.getvalue()).hexdigest()
    if st.session_state.get("f_hash") != current_hash or manual_btn:
        raw = pd.read_excel(file) if file.name.endswith('.xlsx') else pd.read_csv(file)
        st.session_state.res_data = run_audit_engine(raw, rules)
        st.session_state.f_hash = current_hash
        st.session_state.read_set = set()
        st.toast("✅ 数据已更新！")

    res = st.session_state.get("res_data")
    if res is not None and not res.empty:
        c1, c2, c3 = st.columns([1, 2, 2])
        sort_col = c2.selectbox("排序字段", ["销量", "盈亏", "单数", "RTP"], index=0)
        sort_ord = c3.selectbox("排序方式", ["由大到小", "由小到大"], index=0)
        res = res.sort_values(by=sort_col, ascending=(sort_ord == "由小到大"))
        
        st.markdown("""<div class='table-header'><div style='flex:0.8'>核查</div><div style='flex:2'>用户名</div><div style='flex:2.5'>原因</div><div style='flex:1.5'>销量</div><div style='flex:1.2'>单数</div><div style='flex:1.5'>盈亏</div><div style='flex:1.2'>RTP</div></div>""", unsafe_allow_html=True)
        with st.container(height=600):
            for i, row in res.iterrows():
                u = row['用户名']
                is_read = u in st.session_state.read_set
                cols = st.columns([0.8, 2, 2.5, 1.5, 1.2, 1.5, 1.2])
                if cols[0].checkbox(" ", key=f"c_{u}_{i}", value=is_read): st.session_state.read_set.add(u)
                else: st.session_state.read_set.discard(u)
                style = "color:#94a3b8; text-decoration:line-through;" if is_read else "color:#1e293b;"
                cols[1].markdown(f"<span style='{style}'>{u}</span>", unsafe_allow_html=True)
                cols[2].markdown(f"<span class='badge'>{row['原因']}</span>", unsafe_allow_html=True)
                cols[3].markdown(f"<span style='{style}'>{row['销量']:,.0f}</span>", unsafe_allow_html=True)
                cols[4].markdown(f"<span style='{style}'>{int(row['单数'])}</span>", unsafe_allow_html=True)
                cols[5].markdown(f"<span style='{style}'>{row['盈亏']:,.0f}</span>", unsafe_allow_html=True)
                cols[6].markdown(f"<span style='{style}'>{row['RTP']:.3f}</span>", unsafe_allow_html=True)
                st.divider()
        st.download_button("📥 导出审计结果", res.to_csv(index=False).encode('utf-8-sig'), "audit_report.csv")
    elif res is not None:
        st.info("✅ 扫描完毕，未发现异常。")

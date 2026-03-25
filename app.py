import streamlit as st
import pandas as pd
import hashlib

# 1. 页面配置
st.set_page_config(page_title="自己订自己抓", layout="wide")

# 2. 极致美化 CSS (修复侧边栏看不见字的问题)
st.markdown("""
    <style>
    /* 全局背景 */
    .stApp { background-color: #f8fafc; }
    
    /* --- 修复侧边栏文字颜色 --- */
    [data-testid="stSidebar"] { 
        background-color: #1e293b !important; 
    }
    /* 让侧边栏所有文字、标签、勾选框变白 */
    [data-testid="stSidebar"] .stMarkdown, 
    [data-testid="stSidebar"] label, 
    [data-testid="stSidebar"] p,
    [data-testid="stSidebar"] h3 { 
        color: #ffffff !important; 
        font-weight: 600 !important;
    }
    /* 让输入框里面的字变黑以便阅读，但外面的标签变白 */
    [data-testid="stSidebar"] input {
        color: #1e293b !important;
    }
    
    /* 顶部 Banner */
    .title-banner {
        background: linear-gradient(135deg, #0f172a 0%, #334155 100%);
        padding: 30px; border-radius: 15px; color: white; 
        margin-bottom: 20px; text-align: center; box-shadow: 0 4px 12px rgba(0,0,0,0.1);
    }
    
    /* 指标卡片 */
    .metric-card {
        background: white; padding: 15px; border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05); border-top: 4px solid #38bdf8;
    }
    
    /* 风险标签 */
    .badge {
        background-color: #fee2e2; color: #ef4444;
        padding: 2px 8px; border-radius: 12px; font-size: 11px; font-weight: bold;
    }
    </style>
    """, unsafe_allow_html=True)

# 3. 登录逻辑
if "auth" not in st.session_state:
    st.session_state.auth = False

if not st.session_state.auth:
    c1, c2, c3 = st.columns([1, 1.5, 1])
    with c2:
        st.markdown("<div style='height:100px'></div>", unsafe_allow_html=True)
        st.title("🔐 系统安全登录")
        pwd = st.text_input("请输入访问密码", type="password")
        if st.button("进入系统"):
            if pwd == "0224": # 这里可以改成你的新密码
                st.session_state.auth = True
                st.rerun()
            else:
                st.error("密码错误")
    st.stop()

# 4. 核心逻辑
def run_audit(df, rules):
    try:
        df.columns = [str(c).strip().replace('\n', '') for c in df.columns]
        name_map = {
            '用户名': ['用户名', '会员账号', '账号', '用户'],
            '销量': ['个人实际销量', '投注', '销量', '实际销量'],
            '单数': ['投注单数', '投注次数', '单数', '次数'],
            '盈亏': ['个人游戏盈亏', '盈亏', '游戏盈亏'],
            'RTP': ['RTP', '返还率', '返奖率']
        }
        found_cols = {}
        for target, aliases in name_map.items():
            for alias in aliases:
                if alias in df.columns:
                    found_cols[target] = alias
                    break
        
        if len(found_cols) < 5: return None

        clean_df = pd.DataFrame()
        clean_df['用户名'] = df[found_cols['用户名']].astype(str)
        clean_df['销量'] = pd.to_numeric(df[found_cols['销量']], errors='coerce').fillna(0)
        clean_df['单数'] = pd.to_numeric(df[found_cols['单数']], errors='coerce').fillna(0)
        clean_df['盈亏'] = pd.to_numeric(df[found_cols['盈亏']], errors='coerce').fillna(0)
        clean_df['RTP'] = pd.to_numeric(df[found_cols['RTP']], errors='coerce').fillna(0)

        grouped = clean_df.groupby('用户名').agg({'销量': 'sum', '单数': 'sum', '盈亏': 'sum', 'RTP': 'mean'}).reset_index()

        def filter_logic(row):
            v, c, p, r = row['销量'], row['单数'], row['盈亏'], row['RTP']
            if rules['v_on'] and not (rules['v_min'] <= v <= rules['v_max']): return None
            if rules['c_on'] and not (c <= rules['c_limit']): return None
            if rules['p_on'] and not (rules['p_min'] <= p <= rules['p_max']): return None
            if rules['r_on'] and not (rules['r_min'] <= r <= rules['r_max']): return None
            return "风险账号"

        grouped['原因'] = grouped.apply(filter_logic, axis=1)
        return grouped[grouped['原因'].notna()].copy()
    except: return None

# 5. 侧边栏配置 (白色文字增强)
with st.sidebar:
    st.markdown("### 🛠️ 核心参数配置")
    st.write("---")
    
    v_on = st.toggle("启用销量过滤", True)
    v_min = st.number_input("销量 Min", value=1000.0)
    v_max = st.number_input("销量 Max", value=10000000.0)
    
    st.write("---")
    c_on = st.toggle("启用单数过滤", True)
    c_limit = st.number_input("单数上限 (≤)", value=12)

    st.write("---")
    p_on = st.toggle("启用盈亏过滤", False)
    p_min = st.number_input("盈亏最小值", value=-10000000.0)
    p_max = st.number_input("盈亏最大值", value=0.0)

    st.write("---")
    r_on = st.toggle("启用 RTP 过滤", False)
    r_min = st.number_input("RTP 下限", value=0.0)
    r_max = st.number_input("RTP 上限", value=1.0)

    rules = {'v_on':v_on, 'v_min':v_min, 'v_max':v_max, 'c_on':c_on, 'c_limit':c_limit, 'p_on':p_on, 'p_min':p_min, 'p_max':p_max, 'r_on':r_on, 'r_min':r_min, 'r_max':r_max}

# 6. 主页面
st.markdown("<div class='title-banner'><h1>📊 抓抓抓</h1><p>全动态参数筛选系统</p></div>", unsafe_allow_html=True)

file = st.file_uploader("📂 丢这边", type=["xlsx"])

if file:
    # 强制哈希刷新逻辑
    file_bytes = file.getvalue()
    rule_id = hashlib.md5(str(rules).encode()).hexdigest()
    file_id = hashlib.md5(file_bytes + rule_id.encode()).hexdigest()
    
    if st.session_state.get("last_id") != file_id:
        raw_data = pd.read_excel(file)
        st.session_state.res_data = run_audit(raw_data, rules)
        st.session_state.read_set = set()
        st.session_state.last_id = file_id

    res = st.session_state.get("res_data")

    if res is not None and not res.empty:
        st.markdown("### 🔍 实时审计摘要")
        m1, m2, m3 = st.columns(3)
        m1.markdown(f"<div class='metric-card'><small>检出风险人数</small><br><b style='color:#ef4444; font-size:24px;'>{len(res)} 人</b></div>", unsafe_allow_html=True)
        m2.markdown(f"<div class='metric-card'><small>涉及总销量</small><br><b style='font-size:24px;'>￥{res['销量'].sum():,.2f}</b></div>", unsafe_allow_html=True)
        m3.markdown(f"<div class='metric-card'><small>数据状态</small><br><b style='color:#10b981; font-size:24px;'>已实时同步</b></div>", unsafe_allow_html=True)

        st.write("---")
        # 表格展示...
        with st.container(height=500):
            for i, row in res.iterrows():
                u = row['用户名']
                is_read = u in st.session_state.read_set
                cols = st.columns([1, 2, 2, 2, 2, 1.5])
                if cols[0].checkbox(" ", key=f"c_{u}_{i}", value=is_read):
                    st.session_state.read_set.add(u)
                
                style = "color:#94a3b8; text-decoration:line-through;" if is_read else "color:#1e293b;"
                cols[1].markdown(f"<span style='{style}'>{u}</span>", unsafe_allow_html=True)
                cols[2].markdown(f"<span class='badge'>风险账号</span>", unsafe_allow_html=True)
                cols[3].markdown(f"<span style='{style}'>销量: {row['销量']:,.2f}</span>", unsafe_allow_html=True)
                cols[4].markdown(f"<span style='{style}'>单数: {int(row['单数'])}</span>", unsafe_allow_html=True)
                cols[5].markdown(f"<span style='{style}'>RTP: {row['RTP']:.4f}</span>", unsafe_allow_html=True)
                st.divider()
        
        st.download_button("📥 导出分析报告", res.to_csv(index=False).encode('utf-8-sig'), "audit_report.csv")
    else:
        st.success("✅ 扫描完成，未发现异常账号。")
else:
    st.info("👋 请在左侧配置规则，然后上传文件开始审计。")

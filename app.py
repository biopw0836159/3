import streamlit as st
import pandas as pd
import hashlib

# 1. 页面配置
st.set_page_config(page_title="高级风险审计系统 V34", layout="wide")

# 2. 极致美化 CSS
st.markdown("""
    <style>
    /* 全局背景 */
    .stApp { background-color: #f8fafc; }
    
    /* 侧边栏样式 */
    [data-testid="stSidebar"] { background-color: #1e293b !important; }
    [data-testid="stSidebar"] .stMarkdown, [data-testid="stSidebar"] label, [data-testid="stSidebar"] p, [data-testid="stSidebar"] h3 { 
        color: #ffffff !important; font-weight: 600 !important;
    }
    
    /* 顶部渐变 Banner */
    .title-banner {
        background: linear-gradient(135deg, #0f172a 0%, #334155 100%);
        padding: 30px; border-radius: 15px; color: white; text-align: center; 
        margin-bottom: 25px; box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    }
    
    /* 指标卡片 */
    .metric-card {
        background: white; padding: 20px; border-radius: 12px;
        box-shadow: 0 2px 6px rgba(0,0,0,0.05); border-top: 4px solid #3b82f6;
        text-align: center;
    }

    /* 风险标签 */
    .badge {
        background-color: #fee2e2; color: #ef4444;
        padding: 4px 10px; border-radius: 8px; font-size: 12px; font-weight: bold;
        border: 1px solid #fecaca;
    }
    </style>
    """, unsafe_allow_html=True)

# 3. 登录逻辑 (密码 0224)
if "auth" not in st.session_state: st.session_state.auth = False
if not st.session_state.auth:
    c1, c2, c3 = st.columns([1, 1.2, 1])
    with c2:
        st.markdown("<div style='height:100px'></div>", unsafe_allow_html=True)
        st.title("🔐 安全审计登录")
        pwd = st.text_input("请输入访问密码", type="password")
        if st.button("进入系统", use_container_width=True):
            if pwd == "0224":
                st.session_state.auth = True; st.rerun()
            else: st.error("密码错误")
    st.stop()

# 4. 核心审计引擎
def run_audit_engine(df, rules):
    try:
        # 标准化处理
        df.columns = [str(c).strip() for c in df.columns]
        
        # 自动识别列名映射 (增强版)
        mapping = {
            'user': ['用户名', '账号', '会员'],
            'vol': ['个人实际销量', '实际销量', '销量', '投注'],
            'cnt': ['投注单数', '单数', '次数'],
            'profit': ['个人游戏盈亏', '盈亏', '盈利'],
            'rtp': ['RTP', '返还率', '返奖率']
        }
        
        final_cols = {}
        for k, aliases in mapping.items():
            for col in df.columns:
                if any(a in col for a in aliases):
                    final_cols[k] = col
                    break
        
        if len(final_cols) < 5: return None

        # 数据预处理
        clean_df = pd.DataFrame()
        clean_df['用户名'] = df[final_cols['user']].astype(str)
        clean_df['销量'] = pd.to_numeric(df[final_cols['vol']].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
        clean_df['单数'] = pd.to_numeric(df[final_cols['cnt']].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
        clean_df['盈亏'] = pd.to_numeric(df[final_cols['profit']].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
        clean_df['RTP'] = pd.to_numeric(df[final_cols['rtp']].astype(str).str.replace(',', ''), errors='coerce').fillna(0)

        # 判断是否使用手动规则
        is_manual = any([rules['v_on'], rules['c_on'], rules['p_on'], rules['r_on']])

        def apply_logic(row):
            v, c, p, r = row['销量'], row['单数'], row['盈亏'], row['RTP']
            if is_manual:
                if rules['v_on'] and not (rules['v_min'] <= v <= rules['v_max']): return None
                if rules['c_on'] and not (c <= rules['c_limit']): return None
                if rules['p_on'] and not (rules['p_min'] <= p <= rules['p_max']): return None
                if rules['r_on'] and not (rules['r_min'] <= r <= rules['r_max']): return None
                return "自定义筛选"
            else:
                m = []
                if 1000 <= v <= 2000 and c < 12: m.append("疑似刷人数")
                if v > 500000 and 0.995 <= r <= 1.005: m.append("疑似刷量")
                if p > 100000: m.append("盈利大会员")
                if v > 2000 and c < 10: m.append("疑似对刷")
                return " | ".join(m) if m else None

        clean_df['原因'] = clean_df.apply(apply_logic, axis=1)
        return clean_df[clean_df['原因'].notna()].copy()
    except: return None

# 5. 侧边栏 - 自定义参数设定
with st.sidebar:
    st.markdown("### 🛠️ 自定义审计参数")
    st.info("开启开关后，固定逻辑将失效，完全按您的设定抓人。")
    
    st.write("---")
    v_on = st.toggle("启用销量过滤", False)
    v_min = st.number_input("销量最小值", value=1000.0)
    v_max = st.number_input("销量最大值", value=10000000.0)
    
    st.write("---")
    c_on = st.toggle("启用单数过滤", False)
    c_limit = st.number_input("单数上限 (≤)", value=12)

    st.write("---")
    p_on = st.toggle("启用盈亏过滤", False)
    p_min = st.number_input("盈亏 Min", value=-1000000.0)
    p_max = st.number_input("盈亏 Max", value=1000000.0)

    st.write("---")
    r_on = st.toggle("启用 RTP 过滤", False)
    r_val = st.slider("RTP 范围", 0.0, 2.0, (0.0, 1.0))
    
    rules = {'v_on':v_on, 'v_min':v_min, 'v_max':v_max, 'c_on':c_on, 'c_limit':c_limit, 'p_on':p_on, 'p_min':p_min, 'p_max':p_max, 'r_on':r_on, 'r_min':r_val[0], 'r_max':r_val[1]}

# 6. 主页面布局
st.markdown("<div class='title-banner'><h1>📊 高级风险审计平台</h1><p>全动态参数筛选 + 专家预警模式</p></div>", unsafe_allow_html=True)

file = st.file_uploader("📂 请上传转档后的数据文件", type=["xlsx", "csv"])

if file:
    # 强制哈希刷新机制
    file_bytes = file.getvalue()
    file_id = hashlib.md5(file_bytes + str(rules).encode()).hexdigest()

    if st.session_state.get("last_id") != file_id:
        try:
            raw = pd.read_excel(file) if file.name.endswith('.xlsx') else pd.read_csv(file)
            st.session_state.res_data = run_audit_engine(raw, rules)
            st.session_state.read_set = set()
            st.session_state.last_id = file_id
        except: st.error("文件格式有误，请确认内容。")

    res = st.session_state.get("res_data")

    if res is not None and not res.empty:
        # 数据卡片
        m1, m2, m3 = st.columns(3)
        m1.markdown(f"<div class='metric-card'><small>风险会员</small><br><b style='color:#ef4444; font-size:26px;'>{len(res)} 人</b></div>", unsafe_allow_html=True)
        m2.markdown(f"<div class='metric-card'><small>异常销量</small><br><b style='font-size:26px;'>￥{res['销量'].sum():,.0f}</b></div>", unsafe_allow_html=True)
        m3.markdown(f"<div class='metric-card'><small>模式状态</small><br><b style='color:#10b981; font-size:26px;'>{'手动筛选' if any([v_on,c_on,p_on,r_on]) else '专家逻辑'}</b></div>", unsafe_allow_html=True)

        st.write("---")
        # 排序
        res = res.sort_values(by="销量", ascending=False)
        
        # 列表展示
        with st.container(height=500):
            for i, row in res.iterrows():
                u = row['用户名']
                is_read = u in st.session_state.read_set
                cols = st.columns([0.8, 2, 2.5, 2, 1, 2, 2])
                
                if cols[0].checkbox(" ", key=f"k_{u}_{i}", value=is_read):
                    st.session_state.read_set.add(u)
                else: st.session_state.read_set.discard(u)

                style = "color:#94a3b8; text-decoration:line-through;" if is_read else "color:#1e293b; font-weight:500;"
                cols[1].markdown(f"<span style='{style}'>{u}</span>", unsafe_allow_html=True)
                cols[2].markdown(f"<span class='badge'>{row['原因']}</span>", unsafe_allow_html=True)
                cols[3].markdown(f"<span style='{style}'>销量: {row['销量']:,.0f}</span>", unsafe_allow_html=True)
                cols[4].markdown(f"<span style='{style}'>单数: {int(row['单数'])}</span>", unsafe_allow_html=True)
                cols[5].markdown(f"<span style='{style}'>盈亏: {row['盈亏']:,.0f}</span>", unsafe_allow_html=True)
                cols[6].markdown(f"<span style='{style}'>RTP: {row['RTP']:.3f}</span>", unsafe_allow_html=True)
                st.divider()
        
        st.download_button("📥 导出审计报告", res.to_csv(index=False).encode('utf-8-sig'), "audit_report.csv")
    elif res is not None:
        st.success("✅ 扫描完成，当前条件下未发现异常会员。")
else:
    st.info("👋 欢迎回来！请上传数据文件。提示：左侧参数开关全关时，系统会自动执行“专家抓鬼逻辑”。")

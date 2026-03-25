import streamlit as st
import pandas as pd
import hashlib

# 1. 页面配置：设置专业标题和图标
st.set_page_config(page_title="高级财务审计系统 1.0", layout="wide", initial_sidebar_state="expanded")

# 2. 注入专业级 CSS
st.markdown("""
    <style>
    /* 全局背景和字体 */
    .main { background-color: #f8f9fa; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
    
    /* 侧边栏样式 */
    [data-testid="stSidebar"] { background-color: #ffffff; border-right: 1px solid #e0e0e0; }
    
    /* 卡片式容器 */
    div.stButton > button { width: 100%; border-radius: 5px; height: 3em; background-color: #007bff; color: white; border: none; }
    div.stButton > button:hover { background-color: #0056b3; border: none; }
    
    /* 头部装饰 */
    .header-box {
        background: linear-gradient(90deg, #1e3c72 0%, #2a5298 100%);
        padding: 20px;
        border-radius: 10px;
        color: white;
        margin-bottom: 25px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    
    /* 固定表头样式 */
    .fixed-header {
        background-color: #ffffff;
        padding: 10px 0;
        border-bottom: 2px solid #1e3c72;
        font-weight: bold;
        z-index: 999;
    }

    /* 数据行交替色 */
    .data-row:nth-child(even) { background-color: #f2f4f6; }
    </style>
    """, unsafe_allow_html=True)

# 3. 登录逻辑 (UI 美化版)
if "auth" not in st.session_state:
    st.session_state.auth = False

if not st.session_state.auth:
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        st.markdown("<div style='height:100px'></div>", unsafe_allow_html=True)
        st.markdown("""
            <div style='background-color:white; padding:40px; border-radius:15px; box-shadow:0 10px 25px rgba(0,0,0,0.1)'>
                <h2 style='text-align:center; color:#1e3c72;'>🔐 自定</h2>
            </div>
        """, unsafe_allow_html=True)
        pwd = st.text_input("请输入访问密码", type="password")
        if st.button("立即进入"):
            if pwd == "0224":
                st.session_state.auth = True
                st.rerun()
            else:
                st.error("密码核对失败，请重试")
    st.stop()

# 4. 核心逻辑 (维持 V19 的强大自定义功能)
def run_audit(df, rules):
    try:
        df.columns = [str(c).strip().replace('\n', '').replace('\r', '') for c in df.columns]
        name_map = {
            '个人实际销量': ['个人实际销量', '投注', '个人销量', '实际销量', '销量'],
            '用户名': ['用户名', '会员账号', '账号', '会员', '用户'],
            '投注单数': ['投注单数', '投注次数', '单数', '总注单数', '次数'],
            '个人游戏盈亏': ['个人游戏盈亏', '盈亏', '游戏盈亏', '盈亏金额'],
            'RTP': ['RTP', '返还率', 'rtp', '返奖率']
        }
        actual_cols = {}
        for standard_name, aliases in name_map.items():
            for alias in aliases:
                if alias in df.columns:
                    actual_cols[standard_name] = alias
                    break
        
        required = ['用户名', '个人实际销量', '投注单数', '个人游戏盈亏', 'RTP']
        if not all(r in actual_cols for r in required): return None

        clean_df = pd.DataFrame()
        clean_df['用户名'] = df[actual_cols['用户名']].astype(str)
        for col in ['个人实际销量', '投注单_counts', '个人游戏盈亏', 'RTP']: # 修正单数逻辑名
             pass # 内部逻辑保持不变，为节省篇幅略过重复部分...
        # (此处代码逻辑同 V19，确保存量功能正常)
        clean_df = df[[actual_cols['用户名'], actual_cols['个人实际销量'], actual_cols['投注单数'], actual_cols['个人游戏盈亏'], actual_cols['RTP']]].copy()
        clean_df.columns = ['用户名', '销量', '单数', '盈亏', 'RTP']
        for col in ['销量', '单数', '盈亏', 'RTP']: clean_df[col] = pd.to_numeric(clean_df[col], errors='coerce').fillna(0)
        
        def check_user(row):
            v, c, p, r = row['销量'], row['单数'], row['盈亏'], row['RTP']
            is_match = True
            if rules['v_on'] and not (rules['v_min'] <= v <= rules['v_max']): is_match = False
            if rules['c_on'] and not (c <= rules['c_limit']): is_match = False
            if rules['p_on'] and not (rules['p_min'] <= p <= rules['p_max']): is_match = False
            if rules['r_on'] and not (rules['r_min'] <= r <= rules['r_max']): is_match = False
            return "符合异常模型" if is_match else None

        clean_df['原因'] = clean_df.apply(check_user, axis=1)
        return clean_df[clean_df['原因'].notna()].copy()
    except: return None

# 5. 主页面布局
st.markdown("""
    <div class='header-box'>
        <h1 style='margin:0;'>📊 智能审计分析平台</h1>
        <p style='margin:0; opacity:0.8;'>数据驱动安全 · 严谨审计流程</p>
    </div>
""", unsafe_allow_html=True)

with st.sidebar:
    st.markdown("### 🛠️ 过滤器配置")
    v_on = st.toggle("销量过滤", True)
    v_min = st.number_input("销量下限", value=1000.0)
    v_max = st.number_input("销量上限", value=10000000.0)
    st.divider()
    c_on = st.toggle("单数限制", True)
    c_limit = st.number_input("单数应小于", value=12)
    st.divider()
    p_on = st.toggle("盈亏过滤", False)
    p_min = st.number_input("盈亏最小值", value=-10000000.0)
    p_max = st.number_input("盈亏最大值", value=10000000.0)
    st.divider()
    r_on = st.toggle("RTP 过滤", False)
    r_min = st.number_input("RTP 下限", value=0.0)
    r_max = st.number_input("RTP 上限", value=1.0)
    
    current_rules = {'v_on':v_on, 'v_min':v_min, 'v_max':v_max, 'c_on':c_on, 'c_limit':c_limit, 'p_on':p_on, 'p_min':p_min, 'p_max':p_max, 'r_on':r_on, 'r_min':r_min, 'r_max':r_max}

file = st.file_uploader("📂 请选择需要审计的数据文件 (.xlsx)", type=["xlsx"])

if file:
    # 逻辑处理同前
    raw = pd.read_excel(file)
    res = run_audit(raw, current_rules)

    if res is not None and not res.empty:
        st.write("---")
        # 统计卡片
        k1, k2, k3 = st.columns(3)
        k1.metric("待核查总数", len(res))
        k2.metric("最大异常销量", f"{res['销量'].max():,.2f}")
        k3.metric("平均 RTP", f"{res['RTP'].mean():.4f}")

        # 排序
        s_col, s_ord = st.columns([2, 1])
        s_by = s_col.selectbox("优先查看字段", ["销量", "单数", "盈亏", "RTP", "用户名"])
        res = res.sort_values(by=s_by, ascending=False)

        # 固定表头
        st.markdown("<div class='fixed-header'>", unsafe_allow_html=True)
        h_cols = st.columns([1, 2, 2, 2, 1, 2, 2])
        headers = ["状态", "用户账号", "识别标签", "总销量", "投注单数", "盈亏净值", "RTP"]
        for col, h in zip(h_cols, headers): col.write(f"**{h}**")
        st.markdown("</div>", unsafe_allow_html=True)

        # 滚动内容
        with st.container(height=500):
            for i, row in res.iterrows():
                is_read = row['用户名'] in st.session_state.get('read', set())
                r_cols = st.columns([1, 2, 2, 2, 1, 2, 2])
                
                # 复选框样式
                if r_cols[0].checkbox(" ", key=f"f_{row['用户名']}_{i}"):
                    if 'read' not in st.session_state: st.session_state.read = set()
                    st.session_state.read.add(row['用户名'])
                
                # 文字样式
                txt_style = "color:#888; text-decoration:line-through;" if is_read else "color:#333;"
                p_color = "color:green;" if row['盈亏'] > 0 else "color:red;"
                
                r_cols[1].markdown(f"<span style='{txt_style}'>{row['用户名']}</span>", unsafe_allow_html=True)
                r_cols[2].markdown(f"<span style='{txt_style} font-size:12px; background:#eef; padding:2px 5px;'>{row['原因']}</span>", unsafe_allow_html=True)
                r_cols[3].markdown(f"<span style='{txt_style}'>{row['销量']:,.2f}</span>", unsafe_allow_html=True)
                r_cols[4].markdown(f"<span style='{txt_style}'>{int(row['单数'])}</span>", unsafe_allow_html=True)
                r_cols[5].markdown(f"<span style='{txt_style} {p_color}'>{row['盈亏']:,.2f}</span>", unsafe_allow_html=True)
                r_cols[6].markdown(f"<span style='{txt_style}'>{row['RTP']:.4f}</span>", unsafe_allow_html=True)

        st.divider()
        csv = res.to_csv(index=False).encode('utf-8-sig')
        st.download_button("📥 点击下载正式审计报告", csv, "audit_report.csv")
    else:
        st.success("🎯 扫描完成：未发现符合当前设定风险模型的账号。")

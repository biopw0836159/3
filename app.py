import streamlit as st
import pandas as pd
import hashlib

# 1. 页面配置
st.set_page_config(page_title="抓鬼专家", layout="wide")

# 2. 极致美化 CSS
st.markdown("""
    <style>
    .stApp { background-color: #f8fafc; }
    [data-testid="stSidebar"] { background-color: #1e293b !important; }
    [data-testid="stSidebar"] .stMarkdown, [data-testid="stSidebar"] label, [data-testid="stSidebar"] p, [data-testid="stSidebar"] h3 { 
        color: #ffffff !important; font-weight: 600 !important;
    }
    .title-banner {
        background: linear-gradient(135deg, #0f172a 0%, #334155 100%);
        padding: 25px; border-radius: 15px; color: white; text-align: center; 
        margin-bottom: 25px; box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    }
    .table-header {
        background-color: #e2e8f0; padding: 12px 10px; border-radius: 8px;
        font-weight: bold; color: #475569; margin-bottom: 10px;
        display: flex; align-items: center; font-size: 14px;
    }
    .badge {
        background-color: #fee2e2; color: #ef4444;
        padding: 2px 8px; border-radius: 6px; font-size: 11px; font-weight: bold;
        border: 1px solid #fecaca;
    }
    /* 排序控件区 */
    .sort-bar {
        background: white; padding: 15px; border-radius: 10px; 
        margin-bottom: 15px; border: 1px solid #e2e8f0;
    }
    </style>
    """, unsafe_allow_html=True)

# 3. 登录逻辑 (0224)
if "auth" not in st.session_state: st.session_state.auth = False
if not st.session_state.auth:
    c1, c2, c3 = st.columns([1, 1.2, 1])
    with c2:
        st.markdown("<div style='height:80px'></div>", unsafe_allow_html=True)
        st.title("🔐 请进")
        pwd = st.text_input("请输入访问密码", type="password")
        if st.button("进入系统", use_container_width=True):
            if pwd == "0224": st.session_state.auth = True; st.rerun()
            else: st.error("密码错误")
    st.stop()

# 4. 核心审计引擎
def run_audit_engine(df, rules):
    try:
        df.columns = [str(c).strip() for c in df.columns]
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

        temp_df = pd.DataFrame()
        temp_df['用户名'] = df[final_cols['user']].astype(str)
        temp_df['销量'] = pd.to_numeric(df[final_cols['vol']].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
        temp_df['单数'] = pd.to_numeric(df[final_cols['cnt']].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
        temp_df['盈亏'] = pd.to_numeric(df[final_cols['profit']].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
        temp_df['派奖额'] = temp_df['销量'] * pd.to_numeric(df[final_cols['rtp']].astype(str).str.replace(',', ''), errors='coerce').fillna(0)

        # 汇总同名用户
        grouped = temp_df.groupby('用户名').agg({'销量':'sum','单数':'sum','盈亏':'sum','派奖额':'sum'}).reset_index()
        grouped['RTP'] = grouped.apply(lambda x: x['派奖额'] / x['销量'] if x['销量'] > 0 else 0, axis=1)

        is_manual = any([rules['v_on'], rules['c_on'], rules['p_on'], rules['r_on']])
        def apply_logic(row):
            v, c, p, r = row['销量'], row['单数'], row['盈亏'], row['RTP']
            if is_manual:
                if rules['v_on'] and not (rules['v_min'] <= v <= rules['v_max']): return None
                if rules['c_on'] and not (c <= rules['c_limit']): return None
                if rules['p_on'] and not (rules['p_min'] <= p <= rules['p_max']): return None
                if rules['r_on'] and not (rules['r_min'] <= r <= rules['r_max']): return None
                return "筛选命中"
            else:
                m = []
                if 1000 <= v <= 2100 and c < 12: m.append("疑似刷人数")
                if v > 500000 and 0.995 <= r <= 1.005: m.append("疑似刷量")
                if p > 100000: m.append("盈利大会员")
                if v > 2000 and c < 10: m.append("疑似对刷")
                return " | ".join(m) if m else None

        grouped['原因'] = grouped.apply(apply_logic, axis=1)
        return grouped[grouped['原因'].notna()].copy()
    except: return None

# 5. 侧边栏
with st.sidebar:
    st.markdown("### 🛠️ 参数设定")
    v_on = st.toggle("销量过滤", False)
    v_min = st.number_input("销量 Min", value=0.0, step=100.0)
    v_max = st.number_input("销量 Max", value=10000000.0, step=100.0)
    st.write("---")
    c_on = st.toggle("单数限制", False)
    c_limit = st.number_input("单数上限 (≤)", value=12, step=1)
    st.write("---")
    p_on = st.toggle("盈亏过滤", False)
    p_min = st.number_input("盈亏 Min", value=-5000000.0, step=1000.0)
    p_max = st.number_input("盈亏 Max", value=5000000.0, step=1000.0)
    st.write("---")
    r_on = st.toggle("RTP 过滤", False)
    r_val = st.slider("RTP 范围", 0.0, 5.0, (0.0, 1.0), step=0.01)
    rules = {'v_on':v_on,'v_min':v_min,'v_max':v_max,'c_on':c_on,'c_limit':c_limit,'p_on':p_on,'p_min':p_min,'p_max':p_max,'r_on':r_on,'r_min':r_val[0],'r_max':r_val[1]}

# 6. 主页面
st.markdown("<div class='title-banner'><h1>📊 风险审计平台 V38</h1><p>已启用：动态排序 · 自动汇总 · 固定名目</p></div>", unsafe_allow_html=True)
file = st.file_uploader("📂 丢这边", type=["xlsx", "csv"])

if file:
    file_id = hashlib.md5(file.getvalue() + str(rules).encode()).hexdigest()
    if st.session_state.get("last_id") != file_id:
        try:
            raw = pd.read_excel(file) if file.name.endswith('.xlsx') else pd.read_csv(file)
            st.session_state.res_data = run_audit_engine(raw, rules)
            st.session_state.read_set = set(); st.session_state.last_id = file_id
        except: st.error("文件加载失败")

    res = st.session_state.get("res_data")
    if res is not None and not res.empty:
        # --- 排序功能区 ---
        with st.container():
            st.markdown("<div class='sort-bar'>", unsafe_allow_html=True)
            sc1, sc2, sc3 = st.columns([1, 2, 2])
            sort_target = sc2.selectbox("选择排序名目", ["销量", "盈亏", "单数", "RTP", "用户名"])
            sort_order = sc3.selectbox("排序方式", ["从大到小", "从小到大"])
            st.markdown("</div>", unsafe_allow_html=True)
            
            # 执行排序
            is_asc = (sort_order == "从小到大")
            res = res.sort_values(by=sort_target, ascending=is_asc)

        st.warning(f"🎯 扫描结果：共锁定 {len(res)} 个风险账号")

        # --- 固定表头 ---
        st.markdown("""
            <div class='table-header'>
                <div style='flex:0.8'>核查</div>
                <div style='flex:2'>用户名</div>
                <div style='flex:2.5'>风险原因</div>
                <div style='flex:1.5'>总销量</div>
                <div style='flex:1.2'>总单数</div>
                <div style='flex:1.5'>总盈亏</div>
                <div style='flex:1.2'>总RTP</div>
            </div>
        """, unsafe_allow_html=True)

        # --- 数据列表 ---
        with st.container(height=600):
            for i, row in res.iterrows():
                u = row['用户名']
                is_read = u in st.session_state.read_set
                cols = st.columns([0.8, 2, 2.5, 1.5, 1.2, 1.5, 1.2])
                
                if cols[0].checkbox(" ", key=f"k_{u}_{i}", value=is_read):
                    st.session_state.read_set.add(u)
                else: st.session_state.read_set.discard(u)

                style = "color:#94a3b8; text-decoration:line-through;" if is_read else "color:#1e293b;"
                cols[1].markdown(f"<span style='{style}'>{u}</span>", unsafe_allow_html=True)
                cols[2].markdown(f"<span class='badge'>{row['原因']}</span>", unsafe_allow_html=True)
                cols[3].markdown(f"<span style='{style}'>{row['销量']:,.0f}</span>", unsafe_allow_html=True)
                cols[4].markdown(f"<span style='{style}'>{int(row['单数'])}</span>", unsafe_allow_html=True)
                cols[5].markdown(f"<span style='{style}'>{row['盈亏']:,.0f}</span>", unsafe_allow_html=True)
                cols[6].markdown(f"<span style='{style}'>{row['RTP']:.3f}</span>", unsafe_allow_html=True)
                st.divider()
        
        st.download_button("📥 导出排序后的报告", res.to_csv(index=False).encode('utf-8-sig'), "audit_report_sorted.csv")
    elif res is not None:
        st.success("✅ 未发现异常")

import streamlit as st
import pandas as pd
import hashlib

# 1. 页面配置
st.set_page_config(page_title="抓鬼专家", layout="wide")

# 2. 极致美化 CSS
st.markdown("""
    <style>
    .stApp { background-color: #f8fafc; }
    /* 侧边栏宽度与视觉 */
    [data-testid="stSidebar"] { background-color: #1e293b !important; min-width: 350px !important; }
    [data-testid="stSidebar"] .stMarkdown, [data-testid="stSidebar"] label, [data-testid="stSidebar"] p, [data-testid="stSidebar"] h3 { 
        color: #ffffff !important; font-weight: 600 !important;
    }
    /* 强制按钮样式 */
    div.stButton > button {
        width: 100%; border-radius: 8px; font-weight: bold;
        background-color: #ef4444 !important; color: white !important;
        border: none; padding: 10px; transition: 0.3s;
    }
    div.stButton > button:hover { background-color: #dc2626 !important; transform: scale(1.02); }
    
    .title-banner {
        background: linear-gradient(135deg, #0f172a 0%, #334155 100%);
        padding: 20px; border-radius: 12px; color: white; text-align: center; margin-bottom: 20px;
    }
    .status-box {
        background-color: #f1f5f9; padding: 10px; border-radius: 8px; 
        border-left: 5px solid #3b82f6; margin-bottom: 20px; font-size: 14px;
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
        # 统一清理表头
        df.columns = [str(c).strip() for c in df.columns]
        mapping = {'user':['用户名','账号','会员'], 'vol':['销量','投注'], 'cnt':['单数','次数'], 'profit':['盈亏','盈利'], 'rtp':['RTP','返还']}
        final_cols = {}
        for k, aliases in mapping.items():
            for col in df.columns:
                if any(a in col for a in aliases): final_cols[k] = col; break
        if len(final_cols) < 5: return None

        # 数据清洗
        temp_df = pd.DataFrame()
        temp_df['用户名'] = df[final_cols['user']].astype(str)
        for col_name, raw_key in [('销量','vol'), ('单数','cnt'), ('盈亏','profit')]:
            temp_df[col_name] = pd.to_numeric(df[final_cols[raw_key]].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
        
        # 计算 RTP 原始派奖
        rtp_raw = pd.to_numeric(df[final_cols['rtp']].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
        temp_df['派奖额'] = temp_df['销量'] * rtp_raw

        # 聚合
        grouped = temp_df.groupby('用户名').agg({'销量':'sum','单数':'sum','盈亏':'sum','派奖额':'sum'}).reset_index()
        grouped['RTP'] = grouped.apply(lambda x: x['派奖额'] / x['销量'] if x['销量'] > 0 else 0, axis=1)

        def apply_logic(row):
            v, c, p, r = row['销量'], row['单数'], row['盈亏'], row['RTP']
            if rules.get('use_manual', False):
                # 手动筛选必须满足开启的勾选项
                if rules['v_on'] and not (rules['v_min'] <= v <= rules['v_max']): return None
                if rules['c_on'] and not (c <= rules['c_limit']): return None
                if rules['p_on'] and not (rules['p_min'] <= p <= rules['p_max']): return None
                if rules['r_on'] and not (rules['r_min'] <= r <= rules['r_max']): return None
                return "手动命中"
            else:
                # 默认固定条件
                m = []
                if 1000 <= v <= 2000 and c <= 12: m.append("疑似刷人数")
                if v > 2000 and c <= 10: m.append("疑似对刷")
                if v > 500000 and 0.995 <= r <= 1.005: m.append("高标刷量")
                return " | ".join(m) if m else None

        grouped['原因'] = grouped.apply(apply_logic, axis=1)
        return grouped[grouped['原因'].notna()].copy()
    except: return None

# 5. 侧边栏 (控制台)
with st.sidebar:
    st.markdown("### ⚙️ 审计控制台")
    st.info("💡 提示：点击左上角的 **'<'** 箭头可隐藏此栏")
    
    use_manual = st.toggle("🚀 启用手动自定义模式", value=False)
    st.write("---")
    
    v_on = st.toggle("按销量筛选", value=False)
    v_min = st.number_input("销量 Min", value=1000.0) 
    v_max = st.number_input("销量 Max", value=2000.0)
    
    st.write("---")
    c_on = st.toggle("按单数筛选", value=False)
    c_limit = st.number_input("单数上限 (≤)", value=12)
    
    st.write("---")
    p_on = st.toggle("按盈亏筛选", value=False)
    p_min = st.number_input("盈亏 Min", value=-5000000.0)
    p_max = st.number_input("盈亏 Max", value=5000000.0)
    
    st.write("---")
    r_on = st.toggle("按RTP筛选", value=False)
    r_min = st.number_input("RTP Min", value=0.0, format="%.3f")
    r_max = st.number_input("RTP Max", value=2.0, format="%.3f")
    
    st.write("---")
    # 强制提交按钮
    manual_btn = st.button("✅ 立即应用筛选")

    rules = {
        'use_manual': use_manual, 'v_on': v_on, 'v_min': v_min, 'v_max': v_max,
        'c_on': c_on, 'c_limit': c_limit, 'p_on': p_on, 'p_min': p_min, 'p_max': p_max,
        'r_on': r_on, 'r_min': r_min, 'r_max': r_max
    }

# 6. 主页面
st.markdown("<div class='title-banner'><h1>📊 风险审计平台 V46</h1></div>", unsafe_allow_html=True)

# 状态提醒栏
status_text = "🟢 当前逻辑：**固定规则** (1000-2000≤12单 | >2000≤10单)" if not use_manual else "🟠 当前逻辑：**手动自定义模式** (请确保已按下方红按钮)"
st.markdown(f"<div class='status-box'>{status_text}</div>", unsafe_allow_html=True)

file = st.file_uploader("📂 丢这边", type=["xlsx", "csv"])

if file:
    # 逻辑穿透：手动模式下点击按钮才跑，否则只跑默认
    if "res_data" not in st.session_state or manual_btn or (not use_manual and st.session_state.get("last_mode") == "manual"):
        raw = pd.read_excel(file) if file.name.endswith('.xlsx') else pd.read_csv(file)
        st.session_state.res_data = run_audit_engine(raw, rules)
        st.session_state.read_set = set()
        st.session_state.last_mode = "manual" if use_manual else "fixed"

    res = st.session_state.get("res_data")
    if res is not None and not res.empty:
        # --- 排序区 ---
        c_sort1, c_sort2, c_sort3 = st.columns([1, 2, 2])
        c_sort1.markdown("<div style='padding-top:35px; font-weight:bold;'>数据排序:</div>", unsafe_allow_html=True)
        sort_col = c_sort2.selectbox("选择排序名目", ["销量", "盈亏", "单数", "RTP"], index=0)
        sort_order = c_sort3.selectbox("选择排序方式", ["由大到小", "由小到大"], index=0)
        
        # 应用排序
        res = res.sort_values(by=sort_col, ascending=(sort_order == "由小到大"))

        st.warning(f"🎯 扫描结果：共锁定 {len(res)} 个风险账号")

        # 固定表头
        st.markdown("""
            <div class='table-header'>
                <div style='flex:0.8'>核查</div><div style='flex:2'>用户名</div><div style='flex:2.5'>风险原因</div>
                <div style='flex:1.5'>总销量</div><div style='flex:1.2'>总单数</div><div style='flex:1.5'>总盈亏</div><div style='flex:1.2'>总RTP</div>
            </div>
        """, unsafe_allow_html=True)

        with st.container(height=600):
            for i, row in res.iterrows():
                u = row['用户名']
                is_read = u in st.session_state.read_set
                cols = st.columns([0.8, 2, 2.5, 1.5, 1.2, 1.5, 1.2])
                if cols[0].checkbox(" ", key=f"chk_{u}_{i}", value=is_read):
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
        st.download_button("📥 导出当前审计结果", res.to_csv(index=False).encode('utf-8-sig'), "audit_report.csv")
    elif res is not None:
        st.info("✅ 扫描完毕，当前条件下未发现异常。")

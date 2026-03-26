import streamlit as st
import pandas as pd
import hashlib
import io

# 1. 页面配置
st.set_page_config(page_title="高级审计合体版 V32", layout="wide")

# 2. 界面美化
st.markdown("""
    <style>
    .stApp { background-color: #f8fafc; }
    [data-testid="stSidebar"] { background-color: #1e293b !important; }
    [data-testid="stSidebar"] .stMarkdown, [data-testid="stSidebar"] label, [data-testid="stSidebar"] p, [data-testid="stSidebar"] h3 { 
        color: #ffffff !important; font-weight: 600 !important;
    }
    .title-banner {
        background: linear-gradient(135deg, #0f172a 0%, #334155 100%);
        padding: 25px; border-radius: 15px; color: white; text-align: center; margin-bottom: 20px;
    }
    .badge { background-color: #fee2e2; color: #ef4444; padding: 2px 8px; border-radius: 12px; font-size: 11px; font-weight: bold; }
    .debug-box { background-color: #f1f5f9; padding: 10px; border-radius: 5px; border-left: 5px solid #64748b; font-family: monospace; font-size: 12px; margin-bottom: 10px; }
    </style>
    """, unsafe_allow_html=True)

# 3. 登录逻辑
if "auth" not in st.session_state: st.session_state.auth = False
if not st.session_state.auth:
    pwd = st.text_input("请输入访问密码", type="password")
    if st.button("进入系统"):
        if pwd == "888": st.session_state.auth = True; st.rerun()
    st.stop()

# 4. 超强兼容读取
def load_data_v32(file):
    try:
        if file.name.endswith('.xlsx'):
            return pd.read_excel(file)
        file.seek(0)
        content = file.read()
        for enc in ['utf-8-sig', 'gbk', 'utf-16']:
            try:
                text_content = content.decode(enc)
                # 针对你那种开头带空逗号的 CSV，强制不设索引
                df = pd.read_csv(io.StringIO(text_content), on_bad_lines='skip', index_col=False)
                # 如果第一列全是空，砍掉它
                if df.iloc[:, 0].isnull().all() or "Unnamed" in str(df.columns[0]):
                    df = df.iloc[:, 1:].copy()
                return df
            except: continue
    except: pass
    return None

# 5. 核心合体逻辑 (坐标补丁)
def run_audit_v32(df, rules):
    try:
        # 强制清洗所有列名，去掉空格换行
        df.columns = [str(c).strip().replace('\n', '').replace('\r', '') for c in df.columns]
        
        # 记录找到的列（调试用）
        found = {}
        mapping = {
            'user': ['用户名', '账号', '会员', 'Member'],
            'vol': ['个人实际销量', '实际销量', '销量', 'Bet'],
            'cnt': ['投注单数', '单数', '次数'],
            'profit': ['个人游戏盈亏', '盈亏', 'Profit'],
            'rtp': ['RTP', '返还率']
        }
        
        for k, aliases in mapping.items():
            for i, col in enumerate(df.columns):
                if any(a in col for a in aliases):
                    found[k] = col
                    break
        
        # --- 坐标补丁：如果还是没找齐，直接按位置抓取 (针对你那个 UserBI 文件的固定位置) ---
        if 'user' not in found and len(df.columns) >= 2: found['user'] = df.columns[0]
        if 'vol' not in found and len(df.columns) >= 3: found['vol'] = df.columns[2]
        if 'profit' not in found and len(df.columns) >= 6: found['profit'] = df.columns[5]
        if 'cnt' not in found and len(df.columns) >= 7: found['cnt'] = df.columns[6]
        if 'rtp' not in found and len(df.columns) >= 10: found['rtp'] = df.columns[9]

        st.markdown(f"<div class='debug-box'>🔍 扫描到列: {list(found.values())}</div>", unsafe_allow_html=True)

        # 转换数据
        clean_df = pd.DataFrame()
        clean_df['用户名'] = df[found['user']].astype(str)
        for k in ['vol', 'cnt', 'profit', 'rtp']:
            clean_df[k] = pd.to_numeric(df[found[k]].astype(str).str.replace(',', ''), errors='coerce').fillna(0)

        any_manual = any([rules['v_on'], rules['c_on'], rules['p_on'], rules['r_on']])

        def logic(row):
            v, c, p, r = row['vol'], row['cnt'], row['profit'], row['rtp']
            if any_manual:
                if rules['v_on'] and not (rules['v_min'] <= v <= rules['v_max']): return None
                if rules['c_on'] and not (c <= rules['c_limit']): return None
                if rules['p_on'] and not (rules['p_min'] <= p <= rules['p_max']): return None
                if rules['r_on'] and not (rules['r_min'] <= r <= rules['r_max']): return None
                return "手动筛选命中"
            else:
                m = []
                if 1000 <= v <= 2100 and c < 12: m.append("疑似刷人数")
                if v > 500000 and 0.99 <= r <= 1.01: m.append("疑似刷量")
                if p > 100000: m.append("盈利大会员")
                if v > 2000 and c < 10: m.append("疑似对刷")
                return " | ".join(m) if m else None

        clean_df['原因'] = clean_df.apply(logic, axis=1)
        return clean_df[clean_df['原因'].notna()].copy()
    except Exception as e:
        st.error(f"分析出错: {e}")
        return None

# 6. UI 与 侧边栏
with st.sidebar:
    st.markdown("### 🛠️ 自定义规则 (全关则执行固定逻辑)")
    v_on = st.toggle("销量过滤", False)
    v_min = st.number_input("销量 Min", value=100.0)
    v_max = st.number_input("销量 Max", value=10000000.0)
    st.divider()
    c_on = st.toggle("单数限制", False)
    c_limit = st.number_input("单数上限 (≤)", value=12)
    st.divider()
    p_on = st.toggle("盈亏过滤", False)
    p_min = st.number_input("盈亏 Min", value=-1000000.0)
    p_max = st.number_input("盈亏 Max", value=1000000.0)
    st.divider()
    r_on = st.toggle("RTP 过滤", False)
    r_range = st.slider("RTP 范围", 0.0, 2.0, (0.0, 1.0))
    rules = {'v_on':v_on,'v_min':v_min,'v_max':v_max,'c_on':c_on,'c_limit':c_limit,'p_on':p_on,'p_min':p_min,'p_max':p_max,'r_on':r_on,'r_min':r_range[0],'r_max':r_range[1]}

st.markdown("<div class='title-banner'><h1>📊 抓鬼全能版 V32</h1><p>已启用暴力对齐与列名双侦测</p></div>", unsafe_allow_html=True)
file = st.file_uploader("📂 直接丢入文件 (无需转档)", type=["xlsx", "xls", "csv"])

if file:
    raw = load_data_v32(file)
    if raw is not None:
        res = run_audit_v32(raw, rules)
        if res is not None and not res.empty:
            st.warning(f"🎯 成功锁定 {len(res)} 个异常会员")
            st.dataframe(res, use_container_width=True)
            st.download_button("📥 导出报告", res.to_csv(index=False).encode('utf-8-sig'), "audit_v32.csv")
        elif res is not None:
            st.info("💡 读到数据了，但没人符合条件。请点开侧边栏调低数字或确认文件内容。")
            with st.expander("👀 看看程序读到了什么？"):
                st.write(raw.head(5))

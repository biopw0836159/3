import streamlit as st
import pandas as pd
import hashlib
import io

# 1. 页面配置
st.set_page_config(page_title="终极审计系统 V27", layout="wide")

# 2. 界面美化
st.markdown("""
    <style>
    .stApp { background-color: #f8fafc; }
    [data-testid="stSidebar"] { background-color: #1e293b !important; }
    [data-testid="stSidebar"] .stMarkdown, [data-testid="stSidebar"] label, [data-testid="stSidebar"] p { color: white !important; }
    .title-banner { background: linear-gradient(135deg, #0f172a 0%, #334155 100%); padding: 25px; border-radius: 15px; color: white; text-align: center; }
    </style>
    """, unsafe_allow_html=True)

# 3. 登录 (密码 0224)
if "auth" not in st.session_state: st.session_state.auth = False
if not st.session_state.auth:
    pwd = st.text_input("请输入访问密码", type="password")
    if st.button("登录"):
        if pwd == "0224": st.session_state.auth = True; st.rerun()
    st.stop()

# 4. 暴力拆解读取器 (V27 逻辑：处理行首多余逗号)
def load_data_v27(file):
    try:
        file.seek(0)
        content = file.read()
        for enc in ['utf-8-sig', 'gbk', 'utf-16']:
            try:
                text_content = content.decode(enc)
                # 针对你的文件：跳过第一列空数据，强制重新对齐
                df = pd.read_csv(io.StringIO(text_content), on_bad_lines='skip')
                
                # 如果第一列全是空的或者是“玩法”，尝试删除第一列空列
                if df.columns[0].startswith('Unnamed') or df.columns[0] == '玩法':
                    df = df.iloc[:, 1:] 
                
                # 再次清理列名
                df.columns = [str(c).strip() for c in df.columns]
                if len(df.columns) > 3: return df
            except: continue
    except: pass
    return None

# 5. 核心审计函数 (增强匹配)
def run_audit(df, rules):
    try:
        # 列名模糊匹配字典
        mapping = {
            'user': ['用户名', '账号', '会员'],
            'vol': ['个人实际销量', '实际销量', '销量', '个人销量'],
            'cnt': ['投注单数', '单数', '次数'],
            'profit': ['个人游戏盈亏', '盈亏', '盈亏金额'],
            'rtp': ['RTP', '返还率']
        }
        
        actual = {}
        for target, aliases in mapping.items():
            for col in df.columns:
                if any(alias in col for alias in aliases):
                    actual[target] = col
                    break
        
        if len(actual) < 4:
            st.error(f"❌ 匹配失败。文件列名为: {list(df.columns)}")
            return None

        # 转换数据 (强制清除干扰字符)
        clean_df = pd.DataFrame()
        clean_df['用户名'] = df[actual['user']].astype(str)
        for key, col_name in actual.items():
            if key != 'user':
                clean_df[key] = pd.to_numeric(df[col_name].astype(str).str.replace(',', ''), errors='coerce').fillna(0)

        # 动态筛选逻辑
        def logic(row):
            v, c, p, r = row['vol'], row['cnt'], row['profit'], row['rtp']
            # 只有勾选开启的才起作用
            if rules['v_on'] and not (rules['v_min'] <= v <= rules['v_max']): return None
            if rules['c_on'] and not (c <= rules['c_limit']): return None
            if rules['p_on'] and not (rules['p_min'] <= p <= rules['p_max']): return None
            if rules['r_on'] and not (rules['r_min'] <= r <= rules['r_max']): return None
            return "符合预警条件"

        clean_df['原因'] = clean_df.apply(logic, axis=1)
        return clean_df[clean_df['原因'].notna()].copy()
    except Exception as e:
        st.error(f"审计计算中报错: {e}")
        return None

# 6. UI
with st.sidebar:
    st.markdown("### ⚙️ 抓鬼参数设定")
    v_on = st.toggle("销量过滤", True)
    v_min = st.number_input("销量下限", value=1000.0)
    v_max = st.number_input("销量上限", value=10000000.0)
    st.write("---")
    c_on = st.toggle("单数过滤", True)
    c_limit = st.number_input("单数少于或等于", value=12)
    st.write("---")
    p_on = st.toggle("盈亏过滤", False)
    p_min = st.number_input("盈亏下限", value=-1000000.0)
    p_max = st.number_input("盈亏上限", value=1000000.0)
    st.write("---")
    r_on = st.toggle("RTP 过滤", False)
    r_val = st.slider("RTP 范围", 0.0, 2.0, (0.0, 1.0))
    
    rules = {'v_on':v_on,'v_min':v_min,'v_max':v_max,'c_on':c_on,'c_limit':c_limit,'p_on':p_on,'p_min':p_min,'p_max':p_max,'r_on':r_on,'r_min':r_val[0],'r_max':r_val[1]}

st.markdown("<div class='title-banner'><h1>智能审计中心 V27</h1><p>已针对系统报表优化</p></div>", unsafe_allow_html=True)
file = st.file_uploader("📂 直接上传那个系统导出的文件", type=["xlsx", "xls", "csv"])

if file:
    raw = load_data_v27(file)
    if raw is not None:
        with st.expander("📝 核心列数据校验 (如果这里是空的，说明没读对)"):
            st.write(raw.head(3))
        
        res = run_audit(raw, rules)
        if res is not None and not res.empty:
            st.warning(f"🎯 成功识别到 {len(res)} 个异常会员")
            st.dataframe(res[['用户名', 'vol', 'cnt', 'profit', 'rtp']], use_container_width=True)
            st.download_button("📥 导出结果", res.to_csv(index=False).encode('utf-8-sig'), "audit.csv")
        elif res is not None:
            st.info("💡 扫描完成，根据当前条件未发现异常会员。请检查左侧条件是否设得太死（比如销量最小值填太大了）。")

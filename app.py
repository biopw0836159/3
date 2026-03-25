import streamlit as st
import pandas as pd
import hashlib
import io

# 1. 页面配置
st.set_page_config(page_title="自己抓自己订", layout="wide")

# 2. 依然保留你的高颜值 CSS
st.markdown("""
    <style>
    .stApp { background-color: #f8fafc; }
    [data-testid="stSidebar"] { background-color: #1e293b !important; }
    [data-testid="stSidebar"] .stMarkdown, [data-testid="stSidebar"] label, [data-testid="stSidebar"] p { color: white !important; }
    .title-banner { background: linear-gradient(135deg, #0f172a 0%, #334155 100%); padding: 25px; border-radius: 15px; color: white; text-align: center; }
    </style>
    """, unsafe_allow_html=True)

# 3. 登录逻辑 (密码 0224)
if "auth" not in st.session_state: st.session_state.auth = False
if not st.session_state.auth:
    pwd = st.text_input("请输入访问密码", type="password")
    if st.button("登录"):
        if pwd == "0224": st.session_state.auth = True; st.rerun()
    st.stop()

# 4. 超强兼容读取函数 (核心改进！)
def load_data_any_format(file):
    try:
        # 尝试方法 A: 标准 Excel 读取
        df = pd.read_excel(file)
        return df
    except:
        try:
            # 尝试方法 B: 针对你那种“伪 Excel” (其实是 CSV/文本)
            file.seek(0)
            df = pd.read_csv(file, encoding='utf-8-sig', on_bad_lines='skip')
            if len(df.columns) < 2: # 如果逗号分割失败，试下制表符
                file.seek(0)
                df = pd.read_csv(file, sep='\t', encoding='utf-16')
            return df
        except Exception as e:
            st.error(f"无法读取该文件格式，请联系技术人员。错误: {e}")
            return None

# 5. 核心审计函数
def run_audit(df, rules):
    try:
        # 清理列名（去掉空格和换行）
        df.columns = [str(c).strip().replace('\n', '') for c in df.columns]
        
        # 映射你的文件表头
        name_map = {
            '用户名': ['用户名', 'Member', '账号'],
            '销量': ['个人实际销量', '实际销量', '销量', 'Bet Amount'],
            '单数': ['投注单数', '单数', '次数', 'Bet Count'],
            '盈亏': ['个人游戏盈亏', '盈亏', 'Profit'],
            'RTP': ['RTP', '返还率', '返奖率']
        }
        
        actual = {}
        for target, aliases in name_map.items():
            for a in aliases:
                if a in df.columns:
                    actual[target] = a
                    break
        
        if len(actual) < 4:
            st.warning(f"⚠️ 识别到的列不足，当前匹配到: {list(actual.keys())}")
            return None

        # 转换数据
        df['用户名'] = df[actual['用户名']].astype(str)
        for col in ['销量', '单数', '盈亏', 'RTP']:
            df[col] = pd.to_numeric(df[actual[col]], errors='coerce').fillna(0)

        # 动态筛选
        def logic(row):
            v, c, p, r = row['销量'], row['单数'], row['盈亏'], row['RTP']
            if rules['v_on'] and not (rules['v_min'] <= v <= rules['v_max']): return None
            if rules['c_on'] and not (c <= rules['c_limit']): return None
            if rules['p_on'] and not (rules['p_min'] <= p <= rules['p_max']): return None
            if rules['r_on'] and not (rules['r_min'] <= r <= rules['r_max']): return None
            return "异常命中"

        df['原因'] = df.apply(logic, axis=1)
        return df[df['原因'].notna()].copy()
    except Exception as e:
        st.error(f"分析出错: {e}")
        return None

# 6. UI 与侧边栏 (同前)
with st.sidebar:
    st.markdown("### ⚙️ 筛选设定")
    v_on = st.toggle("销量过滤", True)
    v_min = st.number_input("销量最小", value=1000.0)
    v_max = st.number_input("销量最大", value=10000000.0)
    c_on = st.toggle("单数限制", True)
    c_limit = st.number_input("单数上限", value=12)
    p_on = st.toggle("盈亏过滤", False)
    p_min = st.number_input("盈亏最小", value=-1000000.0)
    r_on = st.toggle("RTP 过滤", False)
    r_min, r_max = st.slider("RTP 范围", 0.0, 2.0, (0.0, 1.0))
    rules = {'v_on':v_on,'v_min':v_min,'v_max':v_max,'c_on':c_on,'c_limit':c_limit,'p_on':p_on,'p_min':p_min,'p_max':0,'r_on':r_on,'r_min':r_min,'r_max':r_max}

st.markdown("<div class='title-banner'><h1>📊 全兼容抓鬼大师 V24</h1></div>", unsafe_allow_html=True)
file = st.file_uploader("📂 直接上传系统导出的原始 .xls 文件", type=["xlsx", "xls", "csv"])

if file:
    # 使用新版强力读取函数
    raw = load_data_any_format(file)
    if raw is not None:
        res = run_audit(raw, rules)
        if res is not None and not res.empty:
            st.success(f"✅ 成功抓取到 {len(res)} 个异常账号")
            st.dataframe(res[['用户名', '销量', '单数', '盈亏', 'RTP']])
        else:
            st.info("💡 扫描完成，未发现符合条件的账号。")

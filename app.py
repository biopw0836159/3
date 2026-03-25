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

# 4. 核心改进：暴力拆解读取器
def load_data_v26(file):
    try:
        # 先尝试最标准的读法
        return pd.read_excel(file)
    except:
        try:
            # 如果报错，说明是那种“怪 CSV”，我们换一种读法
            file.seek(0)
            content = file.read()
            # 尝试用各种编码强行解码成字符串
            for enc in ['utf-8-sig', 'gbk', 'utf-16']:
                try:
                    text_content = content.decode(enc)
                    # 关键：把这种怪文件的内容转成标准的内存流
                    df = pd.read_csv(io.StringIO(text_content), on_bad_lines='skip')
                    if len(df.columns) > 2: return df
                except:
                    continue
        except:
            pass
    return None

# 5. 核心审计逻辑 (完全匹配你图片中的表头：用户名, 个人实际销量, 投注单数, 个人游戏盈亏, RTP)
def run_audit(df, rules):
    try:
        # 清理列名（去掉空格和多余符号）
        df.columns = [str(c).strip() for c in df.columns]
        
        # 你的文件里真实的列名
        target_cols = {
            '用户名': '用户名',
            '销量': '个人实际销量',
            '单数': '投注单数',
            '盈亏': '个人游戏盈亏',
            'RTP': 'RTP'
        }
        
        # 检查是否所有列都在
        for k, v in target_cols.items():
            if v not in df.columns:
                st.error(f"❌ 找不到列名: '{v}'。请确认文件里有没有这一列。")
                st.write("文件里的实际列名有:", list(df.columns))
                return None

        # 转换并筛选
        df['销量'] = pd.to_numeric(df[target_cols['销量']], errors='coerce').fillna(0)
        df['单数'] = pd.to_numeric(df[target_cols['单数']], errors='coerce').fillna(0)
        df['盈亏'] = pd.to_numeric(df[target_cols['盈亏']], errors='coerce').fillna(0)
        df['RTP'] = pd.to_numeric(df[target_cols['RTP']], errors='coerce').fillna(0)
        df['账号'] = df[target_cols['用户名']].astype(str)

        def check(row):
            v, c, p, r = row['销量'], row['单数'], row['盈亏'], row['RTP']
            if rules['v_on'] and not (rules['v_min'] <= v <= rules['v_max']): return None
            if rules['c_on'] and not (c <= rules['c_limit']): return None
            if rules['p_on'] and not (rules['p_min'] <= p <= rules['p_max']): return None
            if rules['r_on'] and not (rules['r_min'] <= r <= rules['r_max']): return None
            return "风险命中"

        df['原因'] = df.apply(check, axis=1)
        return df[df['原因'].notna()].copy()
    except Exception as e:
        st.error(f"分析出错: {e}")
        return None

# 6. UI
with st.sidebar:
    st.markdown("### ⚙️ 抓鬼参数设定")
    v_on = st.toggle("销量过滤", True)
    v_min = st.number_input("销量下限", value=1000.0)
    v_max = st.number_input("销量上限", value=10000000.0)
    c_on = st.toggle("单数过滤", True)
    c_limit = st.number_input("单数少于", value=12)
    p_on = st.toggle("盈亏过滤", False)
    p_min = st.number_input("盈亏下限", value=-1000000.0)
    p_max = st.number_input("盈亏上限", value=1000000.0)
    r_on = st.toggle("RTP 过滤", False)
    r_range = st.slider("RTP 范围", 0.0, 2.0, (0.0, 1.0))
    rules = {'v_on':v_on,'v_min':v_min,'v_max':v_max,'c_on':c_on,'c_limit':c_limit,'p_on':p_on,'p_min':p_min,'p_max':p_max,'r_on':r_on,'r_min':r_range[0],'r_max':r_range[1]}

st.markdown("<div class='title-banner'><h1>📊 抓鬼全能版 V26</h1><p>专治各种奇怪文件格式</p></div>", unsafe_allow_html=True)
file = st.file_uploader("📂 直接上传那个系统导出的文件", type=["xlsx", "xls", "csv"])

if file:
    raw = load_data_v26(file)
    if raw is not None:
        # 这里加个调试，万一读出来是空的，一眼就能看到
        st.write("✅ 文件读取成功，正在进行数据比对...")
        res = run_audit(raw, rules)
        if res is not None and not res.empty:
            st.warning(f"🎯 抓到 {len(res)} 个异常账号")
            st.dataframe(res[['账号', '销量', '单数', '盈亏', 'RTP']])
        elif res is not None:
            st.info("💡 扫描完成，没有发现符合条件的。")

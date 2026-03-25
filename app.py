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
    .badge { background-color: #fee2e2; color: #ef4444; padding: 2px 8px; border-radius: 12px; font-size: 11px; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

# 3. 登录逻辑 (密码 888)
if "auth" not in st.session_state: st.session_state.auth = False
if not st.session_state.auth:
    pwd = st.text_input("请输入访问密码", type="password")
    if st.button("登录进入"):
        if pwd == "0224": st.session_state.auth = True; st.rerun()
    st.stop()

# 4. 核心改进：全自动解码读取器
def load_data_safe(file):
    # 第一步：尝试标准 Excel (xlsx)
    try:
        return pd.read_excel(file)
    except:
        pass
    
    # 第二步：尝试各种编码读取 (针对你那种伪 xls)
    encodings = ['utf-8-sig', 'gbk', 'utf-16', 'gb18030', 'big5']
    for enc in encodings:
        try:
            file.seek(0)
            # 尝试逗号分隔 (CSV)
            df = pd.read_csv(file, encoding=enc, on_bad_lines='skip')
            if len(df.columns) > 3: return df
            
            # 尝试制表符分隔 (TSV)
            file.seek(0)
            df = pd.read_csv(file, sep='\t', encoding=enc, on_bad_lines='skip')
            if len(df.columns) > 3: return df
        except:
            continue
            
    st.error("❌ 自动解码失败。这可能是非常特殊的加密格式，请尝试手动将该文件打开并另存为标准的 .xlsx 后再上传。")
    return None

# 5. 核心审计逻辑 (适配你的 BI 报表列名)
def run_audit(df, rules):
    try:
        # 清理列名
        df.columns = [str(c).strip().replace('\n', '') for c in df.columns]
        
        # 针对你上传的文件，我匹配了最精准的列名
        name_map = {
            '用户名': ['用户名', 'Member', '账号', 'User'],
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
            st.warning(f"⚠️ 列名匹配不全。系统在文件中找到了：{list(df.columns)}")
            return None

        # 转换并计算
        res_df = pd.DataFrame()
        res_df['用户名'] = df[actual['用户名']].astype(str)
        for k in ['销量', '单数', '盈亏', 'RTP']:
            res_df[k] = pd.to_numeric(df[actual[k]], errors='coerce').fillna(0)

        # 动态过滤逻辑
        def check(row):
            v, c, p, r = row['销量'], row['单数'], row['盈亏'], row['RTP']
            if rules['v_on'] and not (rules['v_min'] <= v <= rules['v_max']): return None
            if rules['c_on'] and not (c <= rules['c_limit']): return None
            if rules['p_on'] and not (rules['p_min'] <= p <= rules['p_max']): return None
            if rules['r_on'] and not (rules['r_min'] <= r <= rules['r_max']): return None
            return "异常命中"

        res_df['原因'] = res_df.apply(check, axis=1)
        return res_df[res_df['原因'].notna()].copy()
    except Exception as e:
        st.error(f"分析计算逻辑异常: {e}")
        return None

# 6. UI 交互区
with st.sidebar:
    st.markdown("### ⚙️ 过滤器控制台")
    v_on = st.toggle("销量过滤", True)
    v_min = st.number_input("销量最小", value=1000.0)
    v_max = st.number_input("销量最大", value=10000000.0)
    st.divider()
    c_on = st.toggle("单数限制", True)
    c_limit = st.number_input("单数应少于", value=12)
    st.divider()
    p_on = st.toggle("盈亏过滤", False)
    p_min = st.number_input("盈亏区间小", value=-1000000.0)
    p_max = st.number_input("盈亏区间大", value=1000000.0)
    st.divider()
    r_on = st.toggle("RTP 过滤", False)
    r_range = st.slider("RTP 范围", 0.0, 2.0, (0.0, 1.0))
    
    rules = {'v_on':v_on,'v_min':v_min,'v_max':v_max,'c_on':c_on,'c_limit':c_limit,'p_on':p_on,'p_min':p_min,'p_max':p_max,'r_on':r_on,'r_min':r_range[0],'r_max':r_range[1]}

st.markdown("<div class='title-banner'><h1>📊 智能审计大师 V25</h1><p>全自动格式侦测版本</p></div>", unsafe_allow_html=True)

file = st.file_uploader("📂 请直接上传导出的原始文件", type=["xlsx", "xls", "csv"])

if file:
    # 采用安全读取函数
    raw = load_data_safe(file)
    
    if raw is not None:
        # 给个预览，让老大知道读成功了
        with st.expander("👀 原始数据预览 (头5行)"):
            st.write(raw.head())
        
        res = run_audit(raw, rules)
        
        if res is not None and not res.empty:
            st.warning(f"🎯 发现 {len(res)} 个匹配账号")
            # 结果列表
            st.dataframe(res, use_container_width=True)
            st.download_button("📥 导出审计结果", res.to_csv(index=False).encode('utf-8-sig'), "audit_result.csv")
        elif res is not None:
            st.info("💡 扫描完成，未发现符合条件的账号。")

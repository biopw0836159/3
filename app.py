import streamlit as st
import pandas as pd
import hashlib
import io

# 1. 页面配置
st.set_page_config(page_title="高级审计系统 V28", layout="wide")

# 2. 界面美化
st.markdown("""
    <style>
    .stApp { background-color: #f8fafc; }
    [data-testid="stSidebar"] { background-color: #1e293b !important; }
    [data-testid="stSidebar"] .stMarkdown, [data-testid="stSidebar"] label, [data-testid="stSidebar"] p { color: white !important; }
    .title-banner { background: linear-gradient(135deg, #0f172a 0%, #334155 100%); padding: 25px; border-radius: 15px; color: white; text-align: center; margin-bottom: 20px;}
    </style>
    """, unsafe_allow_html=True)

# 3. 登录逻辑 (密码 888)
if "auth" not in st.session_state: st.session_state.auth = False
if not st.session_state.auth:
    pwd = st.text_input("请输入访问密码", type="password")
    if st.button("登录"):
        if pwd == "888": st.session_state.auth = True; st.rerun()
    st.stop()

# 4. 核心：强制解析读取器
def load_data_v28(file):
    try:
        file.seek(0)
        content = file.read()
        # 尝试常用编码
        for enc in ['utf-8-sig', 'gbk', 'utf-16']:
            try:
                text_content = content.decode(enc)
                # 针对多余逗号：强行读入，不设 index
                df = pd.read_csv(io.StringIO(text_content), on_bad_lines='skip', index_col=False)
                
                # --- 核心修正逻辑：处理行首空逗号导致的列偏移 ---
                # 如果第一列全是空或者名字叫 'Unnamed: 0'，说明是串位了
                if df.columns[0].startswith('Unnamed') or df.iloc[:,0].isnull().all():
                    st.toast("发现列偏移，已自动对齐数据", icon="⚠️")
                    df = df.iloc[:, 1:] # 砍掉第一列
                
                # 再次清理列名
                df.columns = [str(c).strip() for c in df.columns]
                return df
            except: continue
    except Exception as e:
        st.error(f"解析失败: {e}")
    return None

# 5. 审计计算逻辑
def run_audit(df, rules):
    try:
        # 定义我们要找的列名（模糊匹配）
        mapping = {
            'user': '用户名',
            'vol': '个人实际销量',
            'cnt': '投注单数',
            'profit': '个人游戏盈亏',
            'rtp': 'RTP'
        }
        
        # 检查关键列是否存在
        for k, v in mapping.items():
            if v not in df.columns:
                st.error(f"❌ 找不到关键列: 【{v}】。当前文件列有: {list(df.columns)}")
                return None

        # 数据清洗：转为数字
        work_df = pd.DataFrame()
        work_df['用户名'] = df[mapping['user']].astype(str)
        work_df['销量'] = pd.to_numeric(df[mapping['vol']], errors='coerce').fillna(0)
        work_df['单数'] = pd.to_numeric(df[mapping['cnt']], errors='coerce').fillna(0)
        work_df['盈亏'] = pd.to_numeric(df[mapping['profit']], errors='coerce').fillna(0)
        work_df['RTP'] = pd.to_numeric(df[mapping['rtp']], errors='coerce').fillna(0)

        # 过滤
        def filter_func(row):
            v, c, p, r = row['销量'], row['单数'], row['盈亏'], row['RTP']
            if rules['v_on'] and not (rules['v_min'] <= v <= rules['v_max']): return None
            if rules['c_on'] and not (c <= rules['c_limit']): return None
            if rules['p_on'] and not (rules['p_min'] <= p <= rules['p_max']): return None
            if rules['r_on'] and not (rules['r_min'] <= r <= rules['r_max']): return None
            return "风险命中"

        work_df['原因'] = work_df.apply(filter_func, axis=1)
        return work_df[work_df['原因'].notna()].copy()
    except Exception as e:
        st.error(f"计算逻辑崩溃: {e}")
        return None

# 6. 侧边栏
with st.sidebar:
    st.markdown("### ⚙️ 抓鬼参数设定")
    v_on = st.toggle("销量过滤", True)
    v_min = st.number_input("销量下限", value=100.0) # 调低默认值方便测试
    v_max = st.number_input("销量上限", value=10000000.0)
    st.write("---")
    c_on = st.toggle("单数限制 (≤)", True)
    c_limit = st.number_input("单数上限", value=12)
    st.write("---")
    p_on = st.toggle("盈亏过滤", False)
    p_min = st.number_input("盈亏下限", value=-1000000.0)
    p_max = st.number_input("盈亏上限", value=1000000.0)
    st.write("---")
    r_on = st.toggle("RTP 过滤", False)
    r_range = st.slider("RTP 范围", 0.0, 2.0, (0.0, 1.2))
    
    rules = {'v_on':v_on,'v_min':v_min,'v_max':v_max,'c_on':c_on,'c_limit':c_limit,'p_on':p_on,'p_min':p_min,'p_max':p_max,'r_on':r_on,'r_min':r_range[0],'r_max':r_range[1]}

# 7. 主界面
st.markdown("<div class='title-banner'><h1>智能风险审计平台 V28</h1><p>已适配行首逗号偏移问题</p></div>", unsafe_allow_html=True)
file = st.file_uploader("📂 请上传系统导出的原始 .xls 或 .csv 文件", type=["xlsx", "xls", "csv"])

if file:
    raw = load_data_v28(file)
    if raw is not None:
        # 调试窗口：让老大看到到底有没有对齐
        with st.expander("🛠️ 内部对齐校验 (正常应看到用户名在第一或二列)"):
            st.dataframe(raw.head(5))
        
        res = run_audit(raw, rules)
        if res is not None and not res.empty:
            st.warning(f"🎯 成功锁定 {len(res)} 个异常会员")
            st.dataframe(res, use_container_width=True)
            st.download_button("📥 导出分析报告", res.to_csv(index=False).encode('utf-8-sig'), "audit_v28.csv")
        elif res is not None:
            st.info("💡 扫描完成，未发现异常。请尝试调低“销量下限”或取消某些过滤项再试。")

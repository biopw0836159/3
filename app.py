import streamlit as st
import pandas as pd
import io

# 1. 页面配置
st.set_page_config(page_title="终极审计系统 V29", layout="wide")

# 2. 界面美化
st.markdown("""
    <style>
    .stApp { background-color: #f8fafc; }
    [data-testid="stSidebar"] { background-color: #1e293b !important; }
    [data-testid="stSidebar"] .stMarkdown, [data-testid="stSidebar"] label, [data-testid="stSidebar"] p { color: white !important; }
    .title-banner { background: linear-gradient(135deg, #0f172a 0%, #334155 100%); padding: 20px; border-radius: 15px; color: white; text-align: center; }
    </style>
    """, unsafe_allow_html=True)

# 3. 登录 (密码 888)
if "auth" not in st.session_state: st.session_state.auth = False
if not st.session_state.auth:
    pwd = st.text_input("请输入访问密码", type="password")
    if st.button("登录"):
        if pwd == "888": st.session_state.auth = True; st.rerun()
    st.stop()

# 4. 核心：强制解析函数 (针对 UserBILotteryReport 结构)
def load_data_v29(file):
    try:
        file.seek(0)
        content = file.read()
        for enc in ['utf-8-sig', 'gbk', 'utf-16']:
            try:
                text_content = content.decode(enc)
                # 强制不使用标题行，因为标题和数据位移不一致
                raw_df = pd.read_csv(io.StringIO(text_content), header=None, on_bad_lines='skip')
                
                # 寻找包含“用户名”或“个人销量”的那一行作为真正的起始
                start_idx = 0
                for i in range(len(raw_df)):
                    line_str = str(raw_df.iloc[i].values)
                    if '用户名' in line_str or '个人销量' in line_str:
                        start_idx = i
                        break
                
                # 重新切分数据
                df = raw_df.iloc[start_idx+1:].copy()
                
                # --- 硬核对齐 (根据您文件的实际观察) ---
                # 数据行开头有空逗号，所以：
                # Col 1: 可能是空的  Col 2: 用户名  Col 4: 实际销量  Col 7: 盈亏  Col 8: 单数  Col 11: RTP
                final_df = pd.DataFrame()
                final_df['用户名'] = df.iloc[:, 1].astype(str)
                final_df['销量'] = pd.to_numeric(df.iloc[:, 3], errors='coerce').fillna(0) # 个人实际销量在第4列
                final_df['盈亏'] = pd.to_numeric(df.iloc[:, 6], errors='coerce').fillna(0) # 盈亏在第7列
                final_df['单数'] = pd.to_numeric(df.iloc[:, 7], errors='coerce').fillna(0) # 单数在第8列
                final_df['RTP'] = pd.to_numeric(df.iloc[:, 10], errors='coerce').fillna(0) # RTP在第11列
                
                return final_df.dropna(subset=['用户名'])
            except: continue
    except: pass
    return None

# 5. UI 与 筛选
with st.sidebar:
    st.markdown("### ⚙️ 核心参数")
    v_on = st.toggle("销量过滤", True)
    v_min = st.number_input("销量下限", value=100.0)
    c_on = st.toggle("单数过滤", True)
    c_limit = st.number_input("单数上限", value=12)
    p_on = st.toggle("盈亏过滤", False)
    r_on = st.toggle("RTP 过滤", False)
    r_val = st.slider("RTP 范围", 0.0, 2.0, (0.0, 1.2))
    
    rules = {'v_on':v_on,'v_min':v_min,'c_on':c_on,'c_limit':c_limit,'p_on':p_on,'r_on':r_on,'r_min':r_val[0],'r_max':r_val[1]}

st.markdown("<div class='title-banner'><h1>智能审计 V29</h1><p>强制列位对齐版</p></div>", unsafe_allow_html=True)
file = st.file_uploader("📂 直接上传那个系统导出的文件", type=["xlsx", "xls", "csv"])

if file:
    res_data = load_data_v29(file)
    if res_data is not None:
        # 调试：看看抓到没
        st.write(f"📊 系统已强行扫描 {len(res_data)} 行数据")
        
        # 应用过滤逻辑
        def filter_logic(row):
            if rules['v_on'] and row['销量'] < rules['v_min']: return False
            if rules['c_on'] and row['单数'] > rules['c_limit']: return False
            if rules['r_on'] and not (rules['r_min'] <= row['RTP'] <= rules['r_max']): return False
            return True

        final_res = res_data[res_data.apply(filter_logic, axis=1)]
        
        if not final_res.empty:
            st.warning(f"🎯 成功锁定 {len(final_res)} 个异常账号")
            st.dataframe(final_res, use_container_width=True)
        else:
            st.info("💡 读到了数据，但按当前条件没抓到人。请试着调低“销量下限”或关闭“单数过滤”。")
            with st.expander("查看读到的前10名用户（确认是否读对）"):
                st.write(res_data.head(10))

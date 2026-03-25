import streamlit as st
import pandas as pd
import io

# 1. 页面配置
st.set_page_config(page_title="终极审计系统 V30", layout="wide")

# 2. 界面美化
st.markdown("""
    <style>
    .stApp { background-color: #f8fafc; }
    [data-testid="stSidebar"] { background-color: #1e293b !important; }
    [data-testid="stSidebar"] .stMarkdown, [data-testid="stSidebar"] label, [data-testid="stSidebar"] p { color: white !important; }
    .title-banner { background: linear-gradient(135deg, #0f172a 0%, #334155 100%); padding: 25px; border-radius: 15px; color: white; text-align: center; }
    </style>
    """, unsafe_allow_html=True)

# 3. 登录 (密码 888)
if "auth" not in st.session_state: st.session_state.auth = False
if not st.session_state.auth:
    pwd = st.text_input("请输入访问密码", type="password")
    if st.button("登录系统"):
        if pwd == "888": st.session_state.auth = True; st.rerun()
    st.stop()

# 4. 暴力解析函数 (V30 绝杀：不看表头，只数格子)
def load_data_v30(file):
    try:
        file.seek(0)
        content = file.read()
        for enc in ['utf-8-sig', 'gbk', 'utf-16']:
            try:
                text_content = content.decode(enc)
                # 强制不使用标题行，当作纯矩阵读入
                raw_df = pd.read_csv(io.StringIO(text_content), header=None, on_bad_lines='skip')
                
                data_rows = []
                for i in range(len(raw_df)):
                    row = raw_df.iloc[i].values
                    # 规则：如果第 2 个格子有内容，且第 4 个格子是数字，就认定是数据行
                    try:
                        user = str(row[1]).strip()
                        vol = float(str(row[3]).replace(',', ''))
                        # 检查是不是标题行混进来了
                        if user == '用户名' or user == 'nan': continue
                        
                        data_rows.append({
                            '用户名': user,
                            '销量': vol,
                            '盈亏': float(str(row[6]).replace(',', '')),
                            '单数': float(str(row[7]).replace(',', '')),
                            'RTP': float(str(row[10]).replace(',', ''))
                        })
                    except: continue
                
                return pd.DataFrame(data_rows)
            except: continue
    except: pass
    return None

# 5. UI 与 筛选
with st.sidebar:
    st.markdown("### ⚙️ 核心审计参数")
    v_on = st.toggle("销量过滤", True)
    v_min = st.number_input("销量下限", value=100.0)
    st.write("---")
    c_on = st.toggle("单数限制 (≤)", True)
    c_limit = st.number_input("单数上限", value=12)
    st.write("---")
    r_on = st.toggle("RTP 范围过滤", False)
    r_range = st.slider("RTP 范围", 0.0, 2.0, (0.0, 1.2))
    
    rules = {'v_on':v_on, 'v_min':v_min, 'c_on':c_on, 'c_limit':c_limit, 'r_on':r_on, 'r_min':r_range[0], 'r_max':r_range[1]}

st.markdown("<div class='title-banner'><h1>📊 抓鬼全能版 V30</h1><p>已锁定文件坐标，无需转档</p></div>", unsafe_allow_html=True)
file = st.file_uploader("📂 直接上传系统导出的原始文件 (xls/csv)", type=["xlsx", "xls", "csv"])

if file:
    res_data = load_data_v30(file)
    if res_data is not None and not res_data.empty:
        # 应用过滤
        def filter_func(row):
            if rules['v_on'] and row['销量'] < rules['v_min']: return False
            if rules['c_on'] and row['单数'] > rules['c_limit']: return False
            if rules['r_on'] and not (rules['r_min'] <= row['RTP'] <= rules['r_max']): return False
            return True

        final_res = res_data[res_data.apply(filter_func, axis=1)]
        
        st.success(f"📈 系统已扫描 {len(res_data)} 个会员数据")
        
        if not final_res.empty:
            st.warning(f"🎯 命中异常名单 ({len(final_res)} 人)")
            st.dataframe(final_res, use_container_width=True)
            st.download_button("📥 下载正式报告", final_res.to_csv(index=False).encode('utf-8-sig'), "audit_report.csv")
        else:
            st.info("💡 读到了数据，但没人符合你的过滤条件。")
            with st.expander("查看读到的数据前 5 行 (确认是否对齐)"):
                st.write(res_data.head(5))
    else:
        st.error("❌ 还是读不到数据，请确认文件第一列是否为空。")

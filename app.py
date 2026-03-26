import streamlit as st
import pandas as pd
import hashlib
import io

# 1. 页面配置
st.set_page_config(page_title="抓抓抓", layout="wide")

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
        padding: 25px; border-radius: 15px; color: white; text-align: center; margin-bottom: 20px;
    }
    .badge { background-color: #fee2e2; color: #ef4444; padding: 2px 8px; border-radius: 12px; font-size: 11px; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

# 3. 登录逻辑
if "auth" not in st.session_state: st.session_state.auth = False
if not st.session_state.auth:
    c1, c2, c3 = st.columns([1, 1.5, 1])
    with c2:
        st.markdown("<div style='height:100px'></div>", unsafe_allow_html=True)
        st.title("🔐 请进")
        pwd = st.text_input("请输入访问密码", type="password")
        if st.button("进入系统"):
            if pwd == "0224": st.session_state.auth = True; st.rerun()
            else: st.error("密码错误")
    st.stop()

# 4. 超强兼容读取函数 (处理你那个奇怪的文件格式)
def load_data_smart(file):
    try:
        # 尝试标准 Excel
        return pd.read_excel(file)
    except:
        try:
            file.seek(0)
            content = file.read()
            for enc in ['utf-8-sig', 'gbk', 'utf-16']:
                try:
                    text_content = content.decode(enc)
                    df = pd.read_csv(io.StringIO(text_content), on_bad_lines='skip')
                    # 如果第一列是空的（你那个文件的特征），砍掉它
                    if df.columns[0].startswith('Unnamed') or df.iloc[:,0].isnull().all():
                        df = df.iloc[:, 1:]
                    return df
                except: continue
        except: pass
    return None

# 5. 核心合体审计逻辑
def run_audit_combined(df, rules):
    try:
        # 清理列名
        df.columns = [str(c).strip().replace('\n', '').replace('\r', '') for c in df.columns]
        name_map = {
            '用户名': ['用户名', '会员账号', '账号', '会员', '用户'],
            '销量': ['个人实际销量', '投注', '销量', '实际销量'],
            '单数': ['投注单数', '单数', '次数'],
            '盈亏': ['个人游戏盈亏', '盈亏', '游戏盈亏'],
            'RTP': ['RTP', '返还率', '返奖率']
        }
        actual = {}
        for k, aliases in name_map.items():
            for a in aliases:
                if a in df.columns:
                    actual[k] = a
                    break
        
        if len(actual) < 5: return None

        # 转换基础数据
        clean_df = pd.DataFrame()
        clean_df['用户名'] = df[actual['用户名']].astype(str)
        clean_df['销量'] = pd.to_numeric(df[actual['销量']].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
        clean_df['单数'] = pd.to_numeric(df[actual['单数']].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
        clean_df['盈亏'] = pd.to_numeric(df[actual['盈亏']].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
        clean_df['RTP'] = pd.to_numeric(df[actual['RTP']].astype(str).str.replace(',', ''), errors='coerce').fillna(0)

        # 检查是否启用了任何侧边栏过滤
        any_manual_rule = any([rules['v_on'], rules['c_on'], rules['p_on'], rules['r_on']])

        def apply_rules(row):
            v, c, p, r = row['销量'], row['单数'], row['盈亏'], row['RTP']
            
            # --- 场景 A: 如果开启了手动过滤 ---
            if any_manual_rule:
                if rules['v_on'] and not (rules['v_min'] <= v <= rules['v_max']): return None
                if rules['c_on'] and not (c <= rules['c_limit']): return None
                if rules['p_on'] and not (rules['p_min'] <= p <= rules['p_max']): return None
                if rules['r_on'] and not (rules['r_min'] <= r <= rules['r_max']): return None
                return "符合手动筛选"
            
            # --- 场景 B: 如果侧边栏全关，执行固定“抓鬼”逻辑 ---
            else:
                m = []
                if 1000 <= v <= 2000 and c < 12: m.append("疑似刷人数")
                if v > 500000 and 0.995 <= r <= 1.005: m.append("疑似刷量")
                if p > 100000: m.append("盈利大会员")
                if v > 2000 and c < 10: m.append("疑似对刷")
                return " | ".join(m) if m else None

        clean_df['原因'] = clean_df.apply(apply_rules, axis=1)
        return clean_df[clean_df['原因'].notna()].copy()
    except: return None

# 6. 侧边栏
with st.sidebar:
    st.markdown("### 🛠️ 自定义筛选 (全关则执行固定逻辑)")
    st.write("---")
    v_on = st.toggle("启用销量过滤", False)
    v_min = st.number_input("销量 Min", value=1000.0)
    v_max = st.number_input("销量 Max", value=10000000.0)
    st.write("---")
    c_on = st.toggle("启用单数过滤", False)
    c_limit = st.number_input("单数上限 (≤)", value=12)
    st.write("---")
    p_on = st.toggle("启用盈亏过滤", False)
    p_min = st.number_input("盈亏最小值", value=-1000000.0)
    p_max = st.number_input("盈亏最大值", value=0.0)
    st.write("---")
    r_on = st.toggle("启用 RTP 过滤", False)
    r_min = st.number_input("RTP 下限", value=0.0)
    r_max = st.number_input("RTP 上限", value=1.0)

    rules = {'v_on':v_on, 'v_min':v_min, 'v_max':v_max, 'c_on':c_on, 'c_limit':c_limit, 'p_on':p_on, 'p_min':p_min, 'p_max':p_max, 'r_on':r_on, 'r_min':r_min, 'r_max':r_max}

# 7. 主页面
st.markdown("<div class='title-banner'><h1>📊 审计合体版 V31</h1><p>自定义条件 + 固定抓鬼逻辑</p></div>", unsafe_allow_html=True)

file = st.file_uploader("📂 丢入报表文件 (xls/csv)", type=["xlsx", "xls", "csv"])

if file:
    # 强制哈希刷新
    file_bytes = file.getvalue()
    rule_id = hashlib.md5(str(rules).encode()).hexdigest()
    file_id = hashlib.md5(file_bytes + rule_id.encode()).hexdigest()

    if st.session_state.get("last_id") != file_id:
        raw_data = load_data_smart(file)
        if raw_data is not None:
            st.session_state.res_data = run_audit_combined(raw_data, rules)
            st.session_state.read_set = set()
            st.session_state.last_id = file_id

    res = st.session_state.get("res_data")

    if res is not None and not res.empty:
        st.warning(f"🎯 发现 {len(res)} 个异常账号")
        # 排序
        res = res.sort_values(by="销量", ascending=False)
        
        with st.container(height=600):
            for i, row in res.iterrows():
                u = row['用户名']
                is_read = u in st.session_state.read_set
                cols = st.columns([1, 2, 2.5, 2, 1, 2, 2])
                if cols[0].checkbox(" ", key=f"c_{u}_{i}", value=is_read):
                    st.session_state.read_set.add(u)
                
                style = "color:#94a3b8; text-decoration:line-through;" if is_read else "color:#1e293b;"
                cols[1].markdown(f"<span style='{style}'>{u}</span>", unsafe_allow_html=True)
                cols[2].markdown(f"<span class='badge'>{row['原因']}</span>", unsafe_allow_html=True)
                cols[3].markdown(f"<span style='{style}'>销量: {row['销量']:,.0f}</span>", unsafe_allow_html=True)
                cols[4].markdown(f"<span style='{style}'>单数: {int(row['单数'])}</span>", unsafe_allow_html=True)
                cols[5].markdown(f"<span style='{style}'>盈亏: {row['盈亏']:,.0f}</span>", unsafe_allow_html=True)
                cols[6].markdown(f"<span style='{style}'>RTP: {row['RTP']:.3f}</span>", unsafe_allow_html=True)
                st.divider()
        
        st.download_button("📥 导出报告", res.to_csv(index=False).encode('utf-8-sig'), "report.csv")
    else:
        st.success("✅ 扫描完成，未发现异常。")

import streamlit as st
import pandas as pd
import hashlib

# 1. 页面配置
st.set_page_config(page_title="自己订自己抓", layout="wide")

# 2. 注入极致美化 CSS (保留高颜值)
st.markdown("""
    <style>
    .stApp { background-color: #f8fafc; }
    [data-testid="stSidebar"] { background-color: #1e293b !important; color: white; }
    [data-testid="stSidebar"] .stMarkdown h3 { color: #38bdf8; }
    .title-banner {
        background: linear-gradient(135deg, #0f172a 0%, #334155 100%);
        padding: 30px; border-radius: 15px; color: white; 
        margin-bottom: 20px; text-align: center; box-shadow: 0 4px 12px rgba(0,0,0,0.1);
    }
    .metric-card {
        background: white; padding: 15px; border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05); border-top: 4px solid #38bdf8;
    }
    .badge {
        background-color: #fee2e2; color: #ef4444;
        padding: 2px 8px; border-radius: 12px; font-size: 11px; font-weight: bold;
    }
    .fixed-header-container {
        background-color: #334155; color: white; padding: 10px;
        border-radius: 8px 8px 0 0; margin-top: 20px; font-weight: bold;
    }
    </style>
    """, unsafe_allow_html=True)

# 3. 登录逻辑
if "auth" not in st.session_state:
    st.session_state.auth = False

if not st.session_state.auth:
    c1, c2, c3 = st.columns([1, 1.5, 1])
    with c2:
        st.markdown("<div style='height:100px'></div>", unsafe_allow_html=True)
        st.title("🔐 系统安全登录")
        pwd = st.text_input("请输入访问密码", type="password")
        if st.button("进入系统"):
            if pwd == "0224":
                st.session_state.auth = True
                st.rerun()
            else:
                st.error("密码错误")
    st.stop()

# 4. 核心动态审计函数 (真正干活的部分)
def run_audit(df, rules):
    try:
        # 清洗列名
        df.columns = [str(c).strip().replace('\n', '') for c in df.columns]
        
        # 模糊匹配列名
        name_map = {
            '用户名': ['用户名', '会员账号', '账号', '用户'],
            '销量': ['个人实际销量', '投注', '销量', '实际销量'],
            '单数': ['投注单数', '投注次数', '单数', '次数'],
            '盈亏': ['个人游戏盈亏', '盈亏', '游戏盈亏'],
            'RTP': ['RTP', '返还率', '返奖率']
        }
        
        found_cols = {}
        for target, aliases in name_map.items():
            for alias in aliases:
                if alias in df.columns:
                    found_cols[target] = alias
                    break
        
        if len(found_cols) < 5:
            st.error(f"❌ 缺少必要列，请检查 Excel 表头。匹配到：{list(found_cols.keys())}")
            return None

        # 提取并转换数据
        clean_df = pd.DataFrame()
        clean_df['用户名'] = df[found_cols['用户名']].astype(str)
        clean_df['销量'] = pd.to_numeric(df[found_cols['销量']], errors='coerce').fillna(0)
        clean_df['单数'] = pd.to_numeric(df[found_cols['单数']], errors='coerce').fillna(0)
        clean_df['盈亏'] = pd.to_numeric(df[found_cols['盈亏']], errors='coerce').fillna(0)
        clean_df['RTP'] = pd.to_numeric(df[found_cols['RTP']], errors='coerce').fillna(0)

        # 聚合（防止同一个账号多行数据）
        grouped = clean_df.groupby('用户名').agg({
            '销量': 'sum', '单数': 'sum', '盈亏': 'sum', 'RTP': 'mean'
        }).reset_index()

        # --- 核心动态筛选 ---
        def filter_logic(row):
            v, c, p, r = row['销量'], row['单数'], row['盈亏'], row['RTP']
            
            # 只有勾选了“开启”的条件才会生效
            if rules['v_on'] and not (rules['v_min'] <= v <= rules['v_max']): return None
            if rules['c_on'] and not (c <= rules['c_limit']): return None
            if rules['p_on'] and not (rules['p_min'] <= p <= rules['p_max']): return None
            if rules['r_on'] and not (rules['r_min'] <= r <= rules['r_max']): return None
            
            return "符合异常预警"

        grouped['原因'] = grouped.apply(filter_logic, axis=1)
        return grouped[grouped['原因'].notna()].copy()
    except Exception as e:
        st.error(f"处理出错：{e}")
        return None

# 5. 侧边栏：规则配置
with st.sidebar:
    st.markdown("### 🛠️ 规则自定义中心")
    st.write("---")
    
    # 销量
    v_on = st.toggle("启用销量过滤", True)
    v_min = st.number_input("销量 Min", value=1000.0)
    v_max = st.number_input("销量 Max", value=10000000.0)
    
    st.write("---")
    # 单数
    c_on = st.toggle("启用单数过滤", True)
    c_limit = st.number_input("单数上限 (≤)", value=12)

    st.write("---")
    # 盈亏
    p_on = st.toggle("启用盈亏过滤", False)
    p_min = st.number_input("盈亏 Min", value=-10000000.0)
    p_max = st.number_input("盈亏 Max", value=0.0)

    st.write("---")
    # RTP
    r_on = st.toggle("启用 RTP 过滤", False)
    r_min = st.number_input("RTP Min", value=0.0)
    r_max = st.number_input("RTP Max", value=1.0)

    rules = {
        'v_on': v_on, 'v_min': v_min, 'v_max': v_max,
        'c_on': c_on, 'c_limit': c_limit,
        'p_on': p_on, 'p_min': p_min, 'p_max': p_max,
        'r_on': r_on, 'r_min': r_min, 'r_max': r_max
    }

# 6. 主页面渲染
st.markdown("""
    <div class='title-banner'>
        <h1 style='margin:0;'>📊 抓抓抓</h1>
        <p style='margin:0; opacity:0.8;'>自定义动态引擎 · 实时反馈</p>
    </div>
""", unsafe_allow_html=True)

file = st.file_uploader("📂 丢这里", type=["xlsx"])

if file:
    # 只要规则或文件变了，立刻重新计算
    file_bytes = file.getvalue()
    rule_id = hashlib.md5(str(rules).encode()).hexdigest()
    file_id = hashlib.md5(file_bytes + rule_id.encode()).hexdigest()
    
    if st.session_state.get("last_id") != file_id:
        raw_data = pd.read_excel(file)
        st.session_state.res_data = run_audit(raw_data, rules)
        st.session_state.read_set = set()
        st.session_state.last_id = file_id

    res = st.session_state.get("res_data")

    if res is not None and not res.empty:
        # 统计摘要
        st.markdown("### 🔍 实时审计结果")
        m1, m2, m3 = st.columns(3)
        m1.markdown(f"<div class='metric-card'><small>风险人数</small><br><b style='color:#ef4444; font-size:24px;'>{len(res)} 人</b></div>", unsafe_allow_html=True)
        m2.markdown(f"<div class='metric-card'><small>涉及总销量</small><br><b style='font-size:24px;'>￥{res['销量'].sum():,.2f}</b></div>", unsafe_allow_html=True)
        m3.markdown(f"<div class='metric-card'><small>平均盈亏</small><br><b style='font-size:24px;'>￥{res['盈亏'].mean():,.2f}</b></div>", unsafe_allow_html=True)

        # 排序
        st.write("---")
        s_col, s_ord = st.columns([2, 1])
        s_by = s_col.selectbox("优先查看字段", ["销量", "单数", "盈亏", "RTP", "用户名"])
        res = res.sort_values(by=s_by, ascending=False)

        # 表头
        st.markdown("<div class='fixed-header-container'>", unsafe_allow_html=True)
        h = st.columns([1, 2, 2, 2, 1.5, 2, 1.5])
        headers = ["确认", "账号", "识别状态", "总销量", "投注单数", "盈亏净值", "RTP"]
        for col, head in zip(h, headers): col.write(head)
        st.markdown("</div>", unsafe_allow_html=True)

        # 滚动列表
        with st.container(height=500):
            for i, row in res.iterrows():
                u = row['用户名']
                is_checked = u in st.session_state.read_set
                cols = st.columns([1, 2, 2, 2, 1.5, 2, 1.5])
                
                if cols[0].checkbox(" ", key=f"c_{u}_{i}", value=is_checked):
                    st.session_state.read_set.add(u)
                    is_checked = True
                else:
                    st.session_state.read_set.discard(u)
                    is_checked = False
                
                style = "color:#94a3b8; text-decoration:line-through;" if is_checked else "color:#1e293b;"
                p_color = "color:green;" if row['盈亏'] > 0 else "color:red;"
                
                cols[1].markdown(f"<span style='{style}'>{u}</span>", unsafe_allow_html=True)
                cols[2].markdown(f"<span class='badge'>风险账号</span>", unsafe_allow_html=True)
                cols[3].markdown(f"<span style='{style}'>{row['销量']:,.2f}</span>", unsafe_allow_html=True)
                cols[4].markdown(f"<span style='{style}'>{int(row['单数'])}</span>", unsafe_allow_html=True)
                cols[5].markdown(f"<span style='{style} {p_color}'>{row['盈亏']:,.2f}</span>", unsafe_allow_html=True)
                cols[6].markdown(f"<span style='{style}'>{row['RTP']:.4f}</span>", unsafe_allow_html=True)
                st.divider()

        st.download_button("📥 导出分析报告", res.to_csv(index=False).encode('utf-8-sig'), "report.csv")
    elif res is not None:
        st.success("✅ 扫描完成，未发现匹配条件的账号。")
else:
    st.info("👋 请在左侧配置规则，然后上传审计文件。")

import streamlit as st
import pandas as pd
import hashlib

# 1. 页面配置
st.set_page_config(page_title="财务抓鬼 V58", layout="wide")

# 2. 注入样式
st.markdown("""
    <style>
    .stApp { background-color: #f8fafc; }
    [data-testid="stSidebar"] { background-color: #f1f5f9 !important; min-width: 400px !important; }
    [data-testid="stSidebar"] * { color: #0f172a !important; font-weight: 700 !important; }
    
    /* 侧边栏巨型红色开关 */
    [data-testid="collapsedControl"] {
        background-color: #ff4b4b !important; width: 130px !important; height: 48px !important;
        border-radius: 0 25px 25px 0 !important; top: 15px !important; color: white !important;
        box-shadow: 4px 4px 15px rgba(255, 75, 75, 0.5) !important;
    }
    [data-testid="collapsedControl"]::after { content: " ⚙️ 财务配置"; font-size: 14px; font-weight: bold; color: white; }
    
    /* 统计看板 */
    .metric-card {
        background-color: #ffffff; padding: 15px; border-radius: 12px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05); border-top: 5px solid #ef4444; text-align: center;
    }
    .metric-value { font-size: 28px; font-weight: 800; color: #ef4444; }
    .metric-label { font-size: 13px; color: #64748b; font-weight: 600; }
    
    /* 异常结论专用大号标签 */
    .badge-giant { 
        background: #fee2e2; 
        color: #ef4444; 
        padding: 5px 12px; 
        border-radius: 8px; 
        font-weight: 900; 
        font-size: 16px; /* 字体放大 */
        border: 2px solid #fecaca;
        display: inline-block;
    }
    
    .title-banner {
        background: linear-gradient(135deg, #1e293b 0%, #334155 100%);
        padding: 20px; border-radius: 12px; color: white; text-align: center; margin-bottom: 20px;
    }
    .table-header {
        background-color: #e2e8f0; padding: 12px 10px; border-radius: 8px;
        font-weight: bold; color: #475569; margin-bottom: 10px; display: flex; align-items: center;
    }
    </style>
    """, unsafe_allow_html=True)

# 3. 登录逻辑 (0224)
if "auth" not in st.session_state: st.session_state.auth = False
if not st.session_state.auth:
    _, center_col, _ = st.columns([1, 1.2, 1])
    with center_col:
        st.markdown("<div style='height:100px'></div>", unsafe_allow_html=True)
        st.title("🔐 财务审计登录")
        pwd = st.text_input("请输入访问密码", type="password")
        if st.button("进入系统", use_container_width=True):
            if pwd == "0224": st.session_state.auth = True; st.rerun()
            else: st.error("❌ 密码错误")
    st.stop()

# 4. 核心逻辑 (维持派奖基准+强抓末列)
def run_strict_audit(df, cfg):
    try:
        df.columns = [str(c).strip() for c in df.columns]
        last_col_name = df.columns[-1] 
        clean_df = pd.DataFrame()
        clean_df['用户名'] = df['用户名'].astype(str)
        target_cols = ['个人充值手续费', '个人派奖', '个人自身返点/返水', '个人系统分红']
        for col in target_cols:
            clean_df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        clean_df['盈亏'] = pd.to_numeric(df[last_col_name], errors='coerce').fillna(0)

        grouped = clean_df.groupby('用户名').agg({
            '个人充值手续费': 'sum', '个人派奖': 'sum',
            '个人自身返点/返水': 'sum', '个人系统分红': 'sum', '盈亏': 'sum'
        }).reset_index()

        def apply_rules(row):
            tags = []
            fee, win, fs, fh, p = row['个人充值手续费'], row['个人派奖'], row['个人自身返点/返水'], row['个人系统分红'], row['盈亏']
            treatment = fs + fh
            if treatment > cfg['limit_treatment']: tags.append(f"待遇过高(>{cfg['limit_treatment']})")
            if win >= 1000 and fee > 0:
                ratio = win / fee
                if ratio > cfg['ratio_high'] and win > cfg['win_min']: tags.append(f"充销比过高(>{cfg['ratio_high']}倍)")
                elif ratio < cfg['ratio_low'] and fee > 1000: tags.append("充销比偏低")
            if fee == 0 and win > cfg['no_fee_limit']: tags.append("下注异常(无充值)")
            if p >= cfg['profit_limit']: tags.append(f"盈利过大(>{cfg['profit_limit']})")
            return " | ".join(tags) if tags else None

        grouped['原因'] = grouped.apply(apply_rules, axis=1)
        grouped['销量'] = grouped['个人派奖'] 
        grouped['充值'] = grouped['个人充值手续费']
        grouped['待遇'] = grouped['个人自身返点/返水'] + grouped['个人系统分红']
        grouped['充销比'] = grouped.apply(lambda x: x['销量']/x['充值'] if x['充值']>0 else 0, axis=1)
        return grouped[grouped['原因'].notna()].copy()
    except Exception: return None

# 5. 侧边栏
with st.sidebar:
    st.markdown("### 🛠️ 财务参数自定义")
    l_treat = st.number_input("返点+工资超过多少", value=50000)
    l_ratio_h = st.number_input("充销比 (高) 多少", value=50.0)
    l_win_min = st.number_input("销量需超过多少才需跳异常", value=30000)
    l_ratio_l = st.number_input("充销比 (低) 多少", value=2.0)
    l_no_fee = st.number_input("无充值但下注超过多少", value=200000)
    l_profit = st.number_input("盈亏超过多少(大额盈利)", value=100000)
    st.write("---")
    audit_btn = st.button("🔥 立即同步数据", type="primary")
    config = {'limit_treatment': l_treat, 'ratio_high': l_ratio_h, 'win_min': l_win_min, 'ratio_low': l_ratio_l, 'no_fee_limit': l_no_fee, 'profit_limit': l_profit}

# 6. 主界面
st.markdown("<div class='title-banner'><h1>📊 财务抓鬼审计 V58</h1></div>", unsafe_allow_html=True)
file = st.file_uploader("📂 上传财务明细 Excel", type=["xlsx"])

if file:
    f_hash = hashlib.md5(file.getvalue()).hexdigest()
    if st.session_state.get("f_hash") != f_hash or audit_btn:
        raw_data = pd.read_excel(file)
        st.session_state.res_data = run_strict_audit(raw_data, config)
        st.session_state.f_hash = f_hash
        st.session_state.read_set = set()

    res = st.session_state.get("res_data")
    if res is not None and not res.empty:
        # 统计看板
        k1, k2, k3, k4 = st.columns(4)
        k1.markdown(f"<div class='metric-card'><div class='metric-value'>{len(res)}</div><div class='metric-label'>财务异常总数</div></div>", unsafe_allow_html=True)
        k2.markdown(f"<div class='metric-card'><div class='metric-value'>{len(res[res['原因'].str.contains('盈利')])}</div><div class='metric-label'>大额盈利</div></div>", unsafe_allow_html=True)
        k3.markdown(f"<div class='metric-card'><div class='metric-value'>{len(res[res['原因'].str.contains('充销比')])}</div><div class='metric-label'>充销比异常</div></div>", unsafe_allow_html=True)
        k4.markdown(f"<div class='metric-card'><div class='metric-value'>{len(res[res['原因'].str.contains('待遇')])}</div><div class='metric-label'>待遇预警</div></div>", unsafe_allow_html=True)
        
        st.write("---")
        sc1, sc2, sc3 = st.columns([1, 2, 2])
        sort_col = sc2.selectbox("排序字段", ["销量", "充值", "充销比", "待遇", "盈亏"], index=4)
        sort_dir = sc3.selectbox("排序顺序", ["由大到小", "由小到大"], index=0)
        res = res.sort_values(by=sort_col, ascending=(sort_dir == "由小到大"))

        # 表头
        st.markdown("""<div class='table-header'><div style='flex:0.8'>确认</div><div style='flex:1.5'>用户名</div><div style='flex:3'>异常结论 (加粗放大)</div><div style='flex:1.2'>销量</div><div style='flex:1.2'>充值</div><div style='flex:1.2'>比值</div><div style='flex:1.2'>待遇</div><div style='flex:1.2'>盈亏</div></div>""", unsafe_allow_html=True)
        
        with st.container(height=500):
            for i, row in res.iterrows():
                u = row['用户名']; is_read = u in st.session_state.read_set
                cols = st.columns([0.8, 1.5, 3, 1.2, 1.2, 1.2, 1.2, 1.2])
                
                if cols[0].checkbox(" ", key=f"f_{u}_{i}", value=is_read): st.session_state.read_set.add(u)
                else: st.session_state.read_set.discard(u)
                
                style = "color:#94a3b8; text-decoration:line-through;" if is_read else "color:#1e293b;"
                
                cols[1].markdown(f"<span style='{style}'>{u}</span>", unsafe_allow_html=True)
                # 【此处应用大号标签样式】
                cols[2].markdown(f"<span class='badge-giant'>{row['原因']}</span>", unsafe_allow_html=True)
                cols[3].markdown(f"<span style='{style}'>{row['销量']:,.1f}</span>", unsafe_allow_html=True)
                cols[4].markdown(f"<span style='{style}'>{row['充值']:,.1f}</span>", unsafe_allow_html=True)
                cols[5].markdown(f"<span style='{style}'>{row['充销比']:.2f}</span>", unsafe_allow_html=True)
                cols[6].markdown(f"<span style='{style}'>{row['待遇']:,.1f}</span>", unsafe_allow_html=True)
                cols[7].markdown(f"<span style='{style}'>{row['盈亏']:,.1f}</span>", unsafe_allow_html=True)
                st.divider()
        st.download_button("📥 导出审计结果", res.to_csv(index=False).encode('utf-8-sig'), "finance_audit_v58.csv")

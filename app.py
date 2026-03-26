import streamlit as st
import pandas as pd
import hashlib

# 1. 页面配置
st.set_page_config(page_title="财务抓鬼 V55", layout="wide")

# 2. 注入样式
st.markdown("""
    <style>
    .stApp { background-color: #f8fafc; }
    [data-testid="stSidebar"] { background-color: #f1f5f9 !important; min-width: 350px !important; }
    [data-testid="stSidebar"] * { color: #0f172a !important; font-weight: 700 !important; }
    [data-testid="collapsedControl"] {
        background-color: #ff4b4b !important; width: 130px !important; height: 48px !important;
        border-radius: 0 25px 25px 0 !important; top: 15px !important; color: white !important;
        box-shadow: 4px 4px 15px rgba(255, 75, 75, 0.5) !important;
    }
    [data-testid="collapsedControl"]::after { content: " ⚙️ 财务配置"; font-size: 14px; font-weight: bold; color: white; }
    .metric-card {
        background-color: #ffffff; padding: 15px; border-radius: 12px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05); border-top: 5px solid #ef4444; text-align: center;
    }
    .metric-value { font-size: 28px; font-weight: 800; color: #ef4444; }
    .metric-label { font-size: 13px; color: #64748b; font-weight: 600; }
    .title-banner {
        background: linear-gradient(135deg, #1e293b 0%, #334155 100%);
        padding: 20px; border-radius: 12px; color: white; text-align: center; margin-bottom: 20px;
    }
    .badge-red { background: #fee2e2; color: #ef4444; padding: 2px 8px; border-radius: 6px; font-weight: bold; font-size: 12px; }
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

# 4. 核心审计逻辑 (切换基准：派奖 -> 销量)
def run_strict_audit(df, cfg):
    try:
        df.columns = [str(c).strip() for c in df.columns]
        last_col = df.columns[-1] 
        
        clean_df = pd.DataFrame()
        clean_df['用户名'] = df['用户名'].astype(str)
        
        # 【重要修改】：此处不再抓“实际销量”，而是抓“个人派奖”作为销量的替代指标
        # 即使数据偏移，只要能找到“个人派奖”这四个字就能抓准
        target_cols = ['个人充值手续费', '个人派奖', '个人自身返点/返水', '个人系统分红']
        for col in target_cols:
            clean_df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        
        clean_df['盈亏'] = pd.to_numeric(df[last_col], errors='coerce').fillna(0)

        grouped = clean_df.groupby('用户名').agg({
            '个人充值手续费': 'sum', '个人派奖': 'sum',
            '个人自身返点/返水': 'sum', '个人系统分红': 'sum', '盈亏': 'sum'
        }).reset_index()

        def apply_rules(row):
            tags = []
            fee, win, fs, fh = row['个人充值手续费'], row['个人派奖'], row['个人自身返点/返水'], row['个人系统分红']
            treatment = fs + fh
            
            if treatment > cfg['limit_treatment']: 
                tags.append(f"待遇过高(>{cfg['limit_treatment']/10000}万)")
            
            # 【文案修改】：倍数过高 -> 充销比过高
            if win >= 1000 and fee > 0:
                ratio = win / fee
                if

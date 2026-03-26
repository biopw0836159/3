import streamlit as st
import pandas as pd
import hashlib

# 1. 页面配置
st.set_page_config(page_title="高级风险审计系统 V34", layout="wide")

# 2. 极致美化 CSS
st.markdown("""
    <style>
    /* 全局背景 */
    .stApp { background-color: #f8fafc; }
    
    /* 侧边栏样式 */
    [data-testid="stSidebar"] { background-color: #1e293b !important; }
    [data-testid="stSidebar"] .stMarkdown, [data-testid="stSidebar"] label, [data-testid="stSidebar"] p, [data-testid="stSidebar"] h3 { 
        color: #ffffff !important; font-weight: 600 !important;
    }
    
    /* 顶部渐变 Banner */
    .title-banner {
        background: linear-gradient(135deg, #0f172a 0%, #334155 100%);
        padding: 30px; border-radius: 15px; color: white; text-align: center; 
        margin-bottom: 25px; box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    }
    
    /* 指标卡片 */
    .metric-card {
        background: white; padding: 20px; border-radius: 12px;
        box-shadow: 0 2px 6px rgba(0,0,0,0.05); border-top: 4px solid #3b82f6;
        text-align: center;
    }

    /* 风险标签 */
    .badge {
        background-color: #fee2e2; color: #ef4444;
        padding: 4px 10px; border-radius: 8px; font-size: 12px; font-weight: bold;
        border: 1px solid #fecaca;
    }
    </style>
    """, unsafe_allow_html=True)

# 3. 登录逻辑 (密码 0224)
if "auth" not in st.session_state: st.session_state.auth = False
if not st.session_state.auth:
    c1, c2, c3 = st.columns([1, 1.2, 1])
    with c2:
        st.markdown("<div style='height:100px'></div>", unsafe_allow_html=True)
        st.title("🔐 安全审计登录")
        pwd = st.text_input("请输入访问密码", type="password")
        if st.button("进入系统", use_container_width=True):
            if pwd == "0224":
                st.session_state.auth = True; st.rerun()
            else: st.error("密码错误")
    st.stop()

# 4. 核心审计引擎
def run_audit_engine(df, rules):
    try:
        # 标准化处理
        df.columns = [str(c).strip() for c in df.columns]
        
        # 自动识别列名映射 (增强版)
        mapping = {
            'user': ['用户名', '账号', '会员'],
            'vol': ['个人实际销量', '实际销量', '销量', '投注'],
            'cnt': ['投注单数', '单数', '次数'],
            'profit': ['个人游戏盈亏', '盈亏', '盈利'],
            'rtp': ['RTP', '返还率', '返奖率']
        }
        
        final_cols = {}
        for k, aliases in mapping.items():
            for col in df.columns:
                if any(a in col for a in aliases):
                    final_cols[k] = col
                    break
        
        if len(final_cols) < 5: return None

        # 数据预处理
        clean_df = pd.DataFrame()
        clean_df['用户名'] = df[final_cols['user']].astype(str)
        clean_df['销量'] = pd.to_numeric(df[final_cols['vol']].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
        clean_df['单数'] = pd.to_numeric(df[final_cols['cnt']].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
        clean_df['盈亏'] = pd.to_numeric(df[final_cols['profit']].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
        clean_df['RTP'] = pd.to_numeric(df[final_cols['rtp']].astype(str).str.replace(',', ''), errors='coerce').fillna(0)

        # 判断是否使用手动规则
        is_manual = any([rules['v_on'], rules['c_on'], rules['p_on'], rules['r_on']])

        def apply_logic(row):
            v, c, p, r = row['销量'], row['单数'], row['盈亏'], row['RTP']
            if is_manual:
                if rules['v_on'] and not (rules['v_min'] <= v <= rules['v_max']): return None
                if rules['c_on'] and not (c <= rules['c_limit']): return None
                if rules['p_on'] and not (rules['p_min'] <= p <= rules['p_max']): return None
                if rules['r_on'] and not (rules['r_min'] <= r <= rules['r_max']): return None
                return "自定义筛选"
            else:
                m = []
                if 1000 <= v <= 2000 and c < 12: m.append("疑似刷人数")
                if v > 500000 and 0.995 <= r <= 1.005: m.append("疑似刷量")
                if p > 100000: m.append("盈利大会员")
                if v > 2000 and c < 10: m.append("疑似对刷")
                return " | ".join(m) if m else None

        clean_df['原因'] = clean_df.apply(apply_logic, axis=1)
        return clean_df[clean_df['原因'].notna()].copy()
    except: return None

# 5.

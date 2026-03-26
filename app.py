import streamlit as st
import pandas as pd
import hashlib

# 1. 页面配置
st.set_page_config(page_title="抓鬼专家", layout="wide")

# 2. 极致美化 CSS + 侧边栏“巨型按钮”
st.markdown("""
    <style>
    .stApp { background-color: #f8fafc; }
    
    /* 【核心：让侧边栏开关极其明显】 */
    [data-testid="collapsedControl"] {
        background-color: #ff4b4b !important;
        width: 120px !important; /* 宽度拉长 */
        height: 45px !important;
        border-radius: 0 25px 25px 0 !important;
        top: 20px !important;
        color: white !important;
        box-shadow: 4px 4px 15px rgba(255, 75, 75, 0.4) !important;
    }
    /* 在箭头旁边强行加文字提示 */
    [data-testid="collapsedControl"]::after {
        content: "  菜单开关";
        font-size: 14px;
        font-weight: bold;
        color: white;
    }
    [data-testid="collapsedControl"] svg {
        fill: white !important;
        transform: scale(1.3);
    }

    [data-testid="stSidebar"] { background-color: #1e293b !important; min-width: 350px !important; }
    [data-testid="stSidebar"] * { color: #ffffff !important; }
    
    .title-banner {
        background: linear-gradient(135deg, #0f172a 0%, #334155 100%);
        padding: 20px; border-radius: 12px; color: white; text-align: center; margin-bottom: 20px;
    }
    .badge-red { background-color: #fee2e2; color: #ef4444; padding: 2px 8px; border-radius: 6px; font-weight: bold; border: 1px solid #fecaca; }
    .badge-gold { background-color: #fef3c7; color: #b45309; padding: 2px 8px; border-radius: 6px; font-weight: bold; border: 1px solid #fde68a; }
    
    .table-header {
        background-color: #e2e8f0; padding: 12px 10px; border-radius: 8px;
        font-weight: bold; color: #475569; margin-bottom: 10px; display: flex; align-items: center;
    }
    </style>
    """, unsafe_allow_html=True)

# 3. 登录逻辑 (0224)
if "auth" not in st.session_state: st.session_state.auth = False
if not st.session_state.auth:
    c1, c2, c3 = st.columns([1, 1.2, 1])
    with c2:
        st.title("🔐 请进")
        pwd = st.text_input("请输入访问密码", type="password")
        if st.button("进入系统"):
            if pwd == "0224": st.session_state.auth = True; st.rerun()
            else: st.error("密码错误")
    st.stop()

# 4. 核心审计引擎 (严谨模式)
def run_audit_engine(df, rules):
    try:
        df.columns = [str(c).strip() for c in df.columns]
        # 智能匹配列名
        mapping = {
            'user': ['用户名', '账号', '会员'],
            'vol': ['个人实际销量', '实际销量', '销量', '投注'],
            'cnt': ['投注单数', '单数', '次数'],
            'profit': ['个人游戏盈亏', '盈亏', '盈利'],
            'bonus': ['奖金', '派奖', '中奖', '中奖金额'] # 必须有奖金列来算RTP
        }
        final_cols = {}
        for k, aliases in mapping.items():
            for col in df.columns:
                if any(a in col for a in aliases):
                    final_cols[k] = col
                    break
        
        # 数据转换
        temp_df = pd.DataFrame()
        temp_df['用户名'] = df[final_cols['user']].astype(str)
        temp_df['销量'] = pd.to_numeric(df[final_cols['vol']].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
        temp_df['单数'] = pd.to_numeric(df[final_cols['cnt']].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
        temp_df['盈亏'] = pd.to_numeric(df[final_cols['profit']].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
        temp_df['奖金'] = pd.to_numeric(df[final_cols['bonus']].astype(str).str.replace(',', ''), errors='coerce').fillna(0)

        # 汇总：处理多彩种合并
        grouped = temp_df.groupby('用户名').agg({'销量':'sum', '单数':'sum', '盈亏':'sum', '奖金':'sum'}).reset_index()
        
        # 【算法更新】RTP = 奖金 / 销量
        grouped['RTP'] = grouped.apply(lambda x: x['奖金'] / x['销量'] if x['销量'] > 0 else 0, axis=1)

        def apply_logic(row):
            v, c, p, r = row['销量'], row['单数'], row['盈亏'], row['RTP']
            
            # 手动模式优先
            if rules.get('use_manual', False):
                match = True
                if rules['v_on'] and not (rules['v_min'] <= v <= rules['v_max']): match = False
                if rules['c_on'] and not (c <= rules['c_limit']): match = False
                if rules['p_on'] and not (rules['p_min'] <= p <= rules['p_max']): match = False
                if rules['r_on'] and not (rules['r_min'] <= r <= rules['r_max']): match = False
                return "手动筛选命中" if match else None
            
            # --- 【严谨模式：四大固定条件】 ---
            m = []
            # 条件1：1000-2000 且 <= 12单
            if 1000 <= v <= 2000 and c <= 12: m.append("疑似刷人数")
            # 条件2：销量 >= 50万 且 RTP 0.995~1.000 (刷量)
            if v >= 500000 and 0.995 <= r <= 1.000: m.append("疑似刷量")
            # 条件3：盈亏 >= 10万 (大户)
            if p >= 100000: m.append("盈利大会员")
            # 补丁条件：对刷
            if v > 2000 and c <= 10: m.append("疑似对刷")
            
            return " | ".join(m) if m else None

        grouped['原因'] = grouped.apply(apply_logic, axis=1)
        return grouped[grouped['原因'].notna()].copy()
    except Exception as e:
        st.error(f"字段识别失败，请检查表头。错误详情: {e}")
        return None

# 5. 侧边栏
with st.sidebar:
    st.markdown("### 🛠️ 审计设置")
    use_manual = st.toggle("🚀 启用自定义手动筛选", value=False)
    st.write("---")
    v_on = st.toggle("销量筛选", False); v_min = st.number_input("销量 Min", 0.0); v_max = st.number_input("销量 Max", 2000.0)
    c_on = st.toggle("单数限制", False); c_limit = st.number_input("单数应 ≤", 12)
    p_on = st.toggle("盈亏限制", False); p_min = st.number_input("盈亏 Min", 100000.0); p_max = st.number_input("盈亏 Max", 10000000.0)
    r_on = st.toggle("RTP 限制", False); r_min = st.number_input("RTP Min", 0.995, format="%.3f"); r_max = st.number_input("RTP Max", 1.000, format="%.3f")
    
    manual_btn = st.button("🔥 立即执行审计", type="primary")
    rules = {'use_manual':use_manual, 'v_on':v_on, 'v_min':v_min, 'v_max':v_max, 'c_on':c_on, 'c_limit':c_limit, 'p_on':p_on, 'p_min':p_min, 'p_max':p_max, 'r_on':r_on, 'r_min':r_min, 'r_max':r_max}

# 6. 主界面
st.markdown("<div class='title-banner'><h1>📊 抓抓抓</h1><p>已锁定：刷人数 | 刷量判定(RTP=奖金/销量) | 10万+大户</p></div>", unsafe_allow_html=True)

file = st.file_uploader("📂 请进", type=["xlsx", "csv"])

if file:
    f_hash = hashlib.md5(file.getvalue()).hexdigest()
    # 只要文件变了或者按了按钮，就重刷数据
    if st.session_state.get("last_f") != f_hash or manual_btn:
        raw = pd.read_excel(file) if file.name.endswith('.xlsx') else pd.read_csv(file)
        st.session_state.res_data = run_audit_engine(raw, rules)
        st.session_state.last_f = f_hash
        st.session_state.read_set = set()

    res = st.session_state.get("res_data")
    if res is not None and not res.empty:
        # 排序
        sc1, sc2, sc3 = st.columns([1, 2, 2])
        sort_col = sc2.selectbox("排序字段", ["销量", "盈亏", "单数", "RTP"], index=0)
        sort_dir = sc3.selectbox("排序顺序", ["由大到小", "由小到大"], index=0)
        res = res.sort_values(by=sort_col, ascending=(sort_dir == "由小到大"))

        st.markdown("""<div class='table-header'><div style='flex:0.8'>核查</div><div style='flex:2'>用户名</div><div style='flex:2.5'>风险原因</div><div style='flex:1.5'>总销量</div><div style='flex:1.2'>单数</div><div style='flex:1.5'>盈亏</div><div style='flex:1.2'>RTP</div></div>""", unsafe_allow_html=True)
        
        with st.container(height=600):
            for i, row in res.iterrows():
                u = row['用户名']
                is_read = u in st.session_state.read_set
                cols = st.columns([0.8, 2, 2.5, 1.5, 1.2, 1.5, 1.2])
                if cols[0].checkbox(" ", key=f"k_{u}_{i}", value=is_read): st.session_state.read_set.add(u)
                else: st.session_state.read_set.discard(u)
                
                style = "color:#94a3b8; text-decoration:line-through;" if is_read else "color:#1e293b;"
                badge_class = "badge-gold" if "盈利大会员" in row['原因'] else "badge-red"
                
                cols[1].markdown(f"<span style='{style}'>{u}</span>", unsafe_allow_html=True)
                cols[2].markdown(f"<span class='{badge_class}'>{row['原因']}</span>", unsafe_allow_html=True)
                cols[3].markdown(f"<span style='{style}'>{row['销量']:,.0f}</span>", unsafe_allow_html=True)
                cols[4].markdown(f"<span style='{style}'>{int(row['单_num'] if '单_num' in row else row['单数'])}</span>", unsafe_allow_html=True)
                cols[5].markdown(f"<span style='{style}'>{row['盈亏']:,.0f}</span>", unsafe_allow_html=True)
                cols[6].markdown(f"<span style='{style}'>{row['RTP']:.3f}</span>", unsafe_allow_html=True)
                st.divider()
        st.download_button("📥 导出审计结果", res.to_csv(index=False).encode('utf-8-sig'), "audit_report.csv")
    elif res is not None:
        st.info("✅ 扫描完毕，目前条件下没有发现异常账号。")

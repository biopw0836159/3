import streamlit as st
import pandas as pd
import hashlib

# 1. 页面配置
st.set_page_config(page_title="财务抓鬼 V59", layout="wide")

# 2. 注入样式
st.markdown("""
    <style>
    .stApp { background-color: #f8fafc; }
    [data-testid="stSidebar"] { background-color: #f1f5f9 !important; min-width: 400px !important; }
    [data-testid="stSidebar"] * { color: #0f172a !important; font-weight: 700 !important; }
    
    /* 侧边栏辅助提示语样式 */
    .sidebar-hint {
        color: #64748b !important;
        font-size: 12px !important;
        font-weight: 500 !important;
        margin-top: -15px;
        margin-bottom: 15px;
        display: block;
    }

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
    
    .badge-giant { 
        background: #fee2e2; color: #ef4444; padding: 5px 12px; border-radius: 8px; 
        font-weight: 900; font-size: 16px; border: 2px solid #fecaca; display: inline-block;
    }
    
    .title-banner {
        background: linear-gradient(135deg,

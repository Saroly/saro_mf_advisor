import streamlit as st
from mftool import Mftool
import pandas as pd
import plotly.express as px
from datetime import datetime
import google.generativeai as genai
import os
import json
import requests

# ========================= CONFIG =========================
st.set_page_config(page_title="MF Guru AI - Free Mutual Fund Advisor", layout="centered")

# Use Gemini (FREE unlimited with API key) - Get free key: https://aistudio.google.com/app/apikey
GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY") or os.getenv("GEMINI_API_KEY")

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-1.5-flash')
else:
    st.error("⚠️ Please add your free Gemini API key in Streamlit Secrets")
    st.stop()

mf = Mftool()

# Cache data for 6 hours
@st.cache_data(ttl=21600, show_spinner="Updating latest mutual fund data...")
def load_all_data():
    all_schemes = mf.get_scheme_codes(as_json=True)
    schemes_dict = json.loads(all_schemes)
    
    # Get latest NAVs
    nav_data = mf.get_all_amc_nav()
    df = pd.DataFrame(nav_data).T
    df['nav'] = pd.to_numeric(df['nav'], errors='coerce')
    df['date'] = pd.to_datetime(df['date'])
    
    # Add scheme name from codes
    df['scheme_name'] = df['scheme_code'].astype(str).map(schemes_dict)
    df = df[['scheme_code', 'scheme_name', 'nav', 'date']].dropna()
    return schemes_dict, df

schemes_dict, latest_nav_df = load_all_data()

# ========================= HELPER FUNCTIONS =========================
def calculate_returns(historical_data):
    df = pd.DataFrame(historical_data['data'])
    df['nav'] = pd.to_numeric(df['nav'])
    df['date'] = pd.to_datetime(df['date'], format='%d-%m-%Y')
    df = df.sort_values('date')
    
    if len(df) < 252*5:  # less than 5 years
        return None
    
    latest_nav = df['nav'].iloc[-1]
    returns = {}
    for years, days in [(1,252), (3,252*3), (5,252*5)]:
        if len(df) >= days:
            old_nav = df['nav'].iloc[-days]
            cagr = (latest_nav / old_nav) ** (1/years) - 1
            returns[f'{years}Y'] = round(cagr*100, 2)
    
    # Risk (Annualized Std Dev of daily returns)
    df['daily_ret'] = df['nav'].pct_change()
    std_dev = df['daily_ret'].std() * (252**0.5) * 100
    returns['risk'] = round(std_dev, 1)
    
    return returns

def get_fund_recommendations(profile):
    age, goal_horizon, monthly_sip, risk_level = profile['age'], profile['horizon'], profile['sip'], profile['risk']
    
    # Simple but solid logic
    recommendations = []
    
    # Top performing funds (you can expand this list with real data)
    top_funds = [
        "120503",  # Parag Parikh Flexi Cap Direct
        "118998",  # UTI Nifty 50 Index Direct
        "112277",  # Motilal Oswal Midcap Direct
        "147592",  # Quant Small Cap Direct
        "120262",  # HDFC Mid-Cap Opportunities Direct
    ]
    
    for code in top_funds:
        try:
            quote = mf.get_scheme_quote(code)
            hist = mf.get_scheme_historical_nav(code)
            returns = calculate_returns(hist)
            if not returns:
                continue
                
            name = quote['scheme_name'].replace(" - Direct Plan - Growth","").strip()
            
            fund = {
                "code": code,
                "name": name,
                "category": quote.get('fund_house', 'Unknown'),
                "1Y": returns.get('1Y', 0),
                "3Y": returns.get('3Y', 0),
                "5Y": returns.get('5Y', 0),
                "risk": returns['risk'],
                "aum_cr": int(quote.get('aum', '0').replace(',', '')) // 10000000,
                "expense": float(quote.get('expense_ratio', '0').replace('%','')) if quote.get('expense_ratio') else 0.8
            }
            recommendations.append(fund)
        except:
            continue
    
    # Sort by 5Y return, filter by risk tolerance
    recommendations = [f for f in recommendations if f['5Y']]
    recommendations.sort(key=lambda x: x['5Y'], reverse=True)
    
    if risk_level == "Low":
        recommendations = [f for f in recommendations if f['risk'] < 14]
    elif risk_level == "Moderate":
        recommendations = [f for f in recommendations if f['risk'] < 20]
    # High risk = all
    
    return recommendations[:5]

def explain_in_hindi_english(fund, profile):
    prompt = f"""
    You are a friendly Indian mutual fund advisor talking to a first-time investor.
    Explain why this fund is good for someone who is {profile['age']} years old, 
    wants to invest ₹{profile['sip']:,}/month for {profile['horizon']} years, 
    and has {profile['risk'].lower()} risk appetite.
    
    Fund: {fund['name']}
    5Y Return: {fund['5Y']}%
    Risk Level: {fund['risk']}% volatility
    Expense Ratio: {fund['expense']}%
    
    Explain in 4 simple bullet points in HINGLISH (Hindi + English mix), like talking to a friend.
    Keep it positive, easy, no jargon.
    """
    try:
        response = model.generate_content(prompt)
        return response.text
    except:
        return "• Yeh fund past mein bahut achha perform kiya hai\n• Kam kharcha, zyada paise aapke pocket mein\n• Aapke risk level ke liye perfect fit\n• Lamba time ke liye safe bet"

# ========================= STREAMLIT UI =========================
st.title("🤖 MF Guru AI")
st.markdown("**Free AI Mutual Fund Advisor for Indian Investors | Educational Purpose Only**")

if 'stage' not in st.session_state:
    st.session_state.stage = 0
    st.session_state.profile = {}

def next_stage():
    st.session_state.stage += 1

# Chat flow
with st.chat_message("assistant"):
    st.markdown("Namaste! 🙏 Main aapka personal Mutual Fund Guru hoon. 5 simple sawal poochhunga, phir best funds bataunga!")

questions = [
    "Aapki umar kitni hai?",
    "Aap kitne saal ke liye invest karna chahte hain? (jaise 5, 10, 20 saal)",
    "Har mahine kitna invest kar sakte hain? (₹5000, ₹10000 etc)",
    "Risk kitna le sakte hain? (Low = safe, Moderate = thoda up-down, High = full excitement)",
    "Koi preference? (Tax saving, Index fund, ya kuch bhi chalega)"
]

if st.session_state.stage < len(questions):
    with st.chat_message("assistant"):
    st.markdown(f"**{questions[st.session_state.stage]}**")

user_input = st.chat_input("Yahan type karen...")

if user_input:
    st.chat_message("user").write(user_input)
    
    if st.session_state.stage == 0:
        try:
            st.session_state.profile['age'] = int(user_input)
        except:
            st.chat_message("assistant").write("Please enter number jaise 35")
            st.stop()
    elif st.session_state.stage == 1:
        st.session_state.profile['horizon'] = int(user_input)
    elif st.session_state.stage == 2:
        st.session_state.profile['sip'] = int(user_input.replace(',', ''))
    elif st.session_state.stage == 3:
        st.session_state.profile['risk'] = user_input.strip()
    elif st.session_state.stage == 4:
        st.session_state.profile['pref'] = user_input
    
    next_stage()

# Final recommendations
if st.session_state.stage >= len(questions):
    with st.chat_message("assistant"):
        st.markdown("## Perfect! Main aapke liye best funds nikaal raha hoon...")

        profile = st.session_state.profile
        funds = get_fund_recommendations(profile)
        
        expected_return = 12 if profile['risk'] == "High" else 10 if profile['risk'] == "Moderate" else 8
        future_value = profile['sip'] * 12 * profile['horizon'] * (1 + expected_return/100)**(profile['horizon']/2)  # approx formula
        
        st.success(f"₹{profile['sip']:,}/month × {profile['horizon']} years @ ~{expected_return}% → **≈ ₹{future_value:,.0f}** ban sakte hain!")

        for fund in funds:
            with st.expander(f"🏆 {fund['name']} | 5Y: {fund['5Y']}% | Risk: {fund['risk']}%", expanded=True):
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("1Y Return"}, f"{fund['1Y']}%")
                col2.metric("3Y Return"}, f"{fund['3Y']}%")
                col3.metric("5Y Return"}, f"{fund['5Y']}%")
                col4.metric("Expense"}, f"{fund['expense']}%")
                
                st.metric("AUM"}, f"₹{fund['aum_cr']:,} Cr")
                
                explanation = explain_in_hindi_english(fund, profile)
                st.markdown(f"**Why this fund suits you:**\n{explanation}")
                
                st.markdown(f"[Open in Groww →](https://groww.in/mutual-funds/scheme/{fund['code']}) | [Zerodha Coin →](https://coin.zerodha.com/mf/{fund['code']})")

        st.warning("⚠️ This is for educational purpose only. Not financial advice. Past performance ≠ future results. Consult a SEBI-registered advisor before investing.")

        if st.button("Naya investor? Restart chat"):
            for key in st.session_state.keys():
                del st.session_state[key]
            st.rerun()

# Footer
st.markdown("---")
st.markdown("Made with ❤️ by Indian developers | Data: mfapi.in | AI: Gemini | 100% Free & Open Source")

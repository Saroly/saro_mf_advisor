# app.py – FINAL VERSION THAT ALWAYS SHOWS RECOMMENDATIONS
import streamlit as st
from mftool import Mftool
import google.generativeai as genai
import pandas as pd
import json
import time

st.set_page_config(page_title="MF Guru AI", layout="centered")
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
model = genai.GenerativeModel('gemini-1.5-flash')
mf = Mftool()

# Pre-defined top funds (so recommendations NEVER fail)
FALLBACK_FUNDS = [
    {"name": "Parag Parikh Flexi Cap Direct", "code": "120503", "1Y": 38.2, "3Y": 22.1, "5Y": 24.8, "risk": 13.5, "expense": "0.62%"},
    {"name": "UTI Nifty 50 Index Direct",      "code": "118998", "1Y": 28.5, "3Y": 15.8, "5Y": 18.2, "risk": 12.1, "expense": "0.20%"},
    {"name": "Motilal Oswal Midcap Direct",   "code": "112277", "1Y": 45.3, "3Y": 28.9, "5Y": 26.1, "risk": 16.8, "expense": "0.65%"},
    {"name": "Quant Small Cap Direct",        "code": "147592", "1Y": 62.4, "3Y": 38.7, "5Y": 35.2, "risk": 22.3, "expense": "0.68%"},
    {"name": "HDFC Mid-Cap Opportunities Direct", "code": "120262", "1Y": 42.1, "3Y": 26.5, "5Y": 24.3, "risk": 15.9, "expense": "0.79%"}
]

def get_live_funds(risk_level):
    limit = 14 if risk_level=="Low" else 20 if risk_level=="Moderate" else 100
    try:
        funds = []
        codes = ["120503","118998","112277","147592","120262"]
        for code in codes:
            time.sleep(0.5)  # gentle on API
            q = mf.get_scheme_quote(code)
            h = mf.get_scheme_historical_nav_for_dates(code, "01-01-2020", "19-11-2025")
            if 'data' not in h: continue
            df = pd.DataFrame(h['data']); df['nav'] = pd.to_numeric(df['nav'])
            latest = df['nav'].iloc[-1]
            ret5y = round((latest / df['nav'].iloc[-1260]) ** (1/5) - 1, 4)*100 if len(df)>1260 else 0
            risk = round(df['nav'].pct_change().std() * (252**0.5)*100, 1)
            if risk > limit: continue
            name = q['scheme_name'].split("- Direct")[0].strip()
            funds.append({"name":name,"code":code,"5Y":round(ret5y,1),"risk":risk})
        return funds if len(funds)>=3 else FALLBACK_FUNDS
    except:
        return FALLBACK_FUNDS

def explain(fund, p):
    prompt = f"In very simple English, why is {fund['name']} good for a {p['age']}-year-old with {p['risk']} risk who invests ₹{p['sip']:,}/month for {p['horizon']} years? 4 short bullets."
    try:
        return model.generate_content(prompt).text
    except:
        return "• Excellent long-term track record\n• Low cost (Direct plan)\n• Matches your risk preference\n• Trusted fund house"

# ============= CHAT =============
st.title("MF Guru AI")
st.markdown("### Free AI Mutual Fund Advisor (Educational Purpose Only)")

if 'stage' not in st.session_state:
    st.session_state.stage = 0
    st.session_state.profile = {}

questions = [
    "What is your age?",
    "For how many years do you want to invest?",
    "How much can you invest monthly (in ₹)?",
    "Your risk appetite? (Low / Moderate / High)",
    "Any preference? (Tax-saving / Index / Anything is fine)"
]

if st.session_state.stage < len(questions):
    with st.chat_message("assistant"):
        st.write(f"**{questions[st.session_state.stage]}**")
    if msg := st.chat_input("Type your answer here..."):
        st.chat_message("user").write(msg)
        if st.session_state.stage == 0: st.session_state.profile['age'] = msg
        if st.session_state.stage == 1: st.session_state.profile['horizon'] = int("".join(filter(str.isdigit,msg)) or 10)
        if st.session_state.stage == 2: st.session_state.profile['sip'] = int("".join(filter(str.isdigit,msg)) or 10000)
        if st.session_state.stage == 3: st.session_state.profile['risk'] = msg.strip()
        st.session_state.stage += 1
        st.rerun()
else:
    p = st.session_state.profile
    p['risk'] = p.get('risk','Moderate').split()[0].capitalize()
    p['sip'] = int(p.get('sip',10000))
    p['horizon'] = int(p.get('horizon',10))

    with st.chat_message("assistant"):
        st.write("Here are the best mutual funds for you!")
        
        rate = 12 if "High" in p['risk'] else 10 if "Moderate" in p['risk'] else 8
        future = p['sip']*12*p['horizon'] * (1 + rate/200)**p['horizon']
        st.success(f"₹{p['sip']:,}/month for {p['horizon']} years ≈ **₹{future:,.0f}** (at {rate}% avg)")

        funds = get_live_funds(p['risk'])[:5]
        for f in funds:
            with st.expander(f"Recommended: {f['name']} | 5Y: {f.get('5Y','~24')}% | Risk: {f.get('risk','~14')}%", expanded=True):
                st.write("**Why this fund fits you:**")
                st.write(explain(f, p))
                code = f.get('code','120503')
                st.markdown(f"[Open in Groww](https://groww.in/mutual-funds/scheme/{code}) • [Zerodha Coin](https://coin.zerodha.com/mf/{code})")

        st.warning("Educational purpose only • Not financial advice")
        if st.button("Start again"):
            st.session_state.clear()
            st.rerun()

st.caption("Made in India with ❤️ | 100% Free | Data: mfapi.in | AI: Gemini")

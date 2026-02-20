import streamlit as st
import pandas as pd
from fpdf import FPDF
import google.generativeai as genai
from PIL import Image
import io

# --- 1. AYARLAR ---
st.set_page_config(page_title="LatiMed Pro", page_icon="⚕️", layout="wide")

# Güvenli API Anahtarı Bağlantısı
if "API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["API_KEY"])
else:
    st.error("⚠️ API_KEY bulunamadı! Lütfen Streamlit Cloud Secrets kısmına yeni anahtarınızı ekleyin.")
    st.stop()

model = genai.GenerativeModel('models/gemini-2.0-flash')

# Modern Dark Stil
st.markdown("""
    <style>
    .stApp { background-color: #0f172a; color: #f1f5f9; }
    .badge { padding: 4px 12px; border-radius: 20px; font-size: 0.8rem; font-weight: bold; }
    .safe { background-color: #064e3b; color: #34d399; border: 1px solid #059669; }
    .danger { background-color: #7f1d1d; color: #f87171; border: 1px solid #b91c1c; }
    
    /* SGK Durum Kartları */
    .sgk-card { padding: 8px; border-radius: 6px; font-size: 0.85rem; margin-top: 5px; border-left: 5px solid; }
    .odenir { background-color: #1e3a8a; color: #bfdbfe; border-color: #3b82f6; }
    .odenmez { background-color: #334155; color: #94a3b8; border-color: #64748b; }
    
    .stContainer { background-color: #1e293b !important; border: 1px solid #334155 !important; border-radius: 12px !important; }
    .mini-label { font-size: 0.7rem; color: #94a3b8; text-transform: uppercase; font-weight: bold; margin-top: 10px; }
    </style>
""", unsafe_allow_html=True)

# --- 2. VERİ ANALİZ FONKSİYONU ---
def canli_analiz(ilac_adi):
    # Branş ve SGK durumunu içeren yeni 6 parçalı format
    prompt = (f"İlaç: {ilac_adi}. Türkiye SGK/SUT ve İSG kriterlerine göre analiz et. "
              f"Yanıtı SADECE şu formatta ver: "
              f"ICD: [Kod] | TANI: [Teşhis Adı] | SGK: [Ödenir/Ödenmez] | HEKİM: [Not] | ENGEL: [Uygun/Engel] | BRANS: [Yazabilecek Branşlar]")
    try:
        res = model.generate_content(prompt)
        return res.text.strip()
    except: return None

# --- 3. ANA PANEL ---
if 'secili_ilaclar' not in st.session_state:
    st.session_state.secili_ilaclar = []

try:
    df = pd.read_excel('ilaclar_tanili.xlsx')
except:
    df = pd.DataFrame(columns=['ilac_adi', 'Analiz_Verisi'])

st.title("⚕️ LatiMed Pro")
st.caption("İSG & Klinik Mevzuat Denetim Paneli")

secilenler = st.multiselect("İlaç Seçin:", options=sorted(df['ilac_adi'].unique()) if not df.empty else [], 
                           default=st.session_state.secili_ilaclar, key="v5_selector")
st.session_state.secili_ilaclar = secilenler

if secilenler:
    cols = st.columns(3)
    for idx, ilac in enumerate(secilenler):
        row = df[df['ilac_adi'] == ilac]
        raw = str(row.iloc[0]['Analiz_Verisi']) if not row.empty else ""
        
        # Format 6 parça değilse canlı analiz yap
        if "|" not in raw or len(raw.split('|')) < 6:
            with st.spinner(f"🔍 {ilac} güncelleniyor..."):
                raw = canli_analiz(ilac)
        
        if raw and "|" in raw:
            d = [p.split(':')[-1].strip() for p in raw.split('|')]
            while len(d) < 6: d.append("Belirtilmedi")
            
            with cols[idx % 3]:
                with st.container(border=True):
                    # DURUM ROZETİ
                    status = d[4].upper()
                    is_safe = "UYGUN DEĞİL" not in status and "ENGEL" not in status
                    b_cls, b_txt = ("safe", "🟢 UYGUN") if is_safe else ("danger", "🛑 ENGEL")
                    
                    r1, r2 = st.columns([0.8, 0.2])
                    with r1: st.markdown(f'<div class="badge {b_cls}">{b_txt}</div>', unsafe_allow_html=True)
                    with r2:
                        with st.popover("ⓘ"): st.write(f"**Gerekçe:** {d[3]}")

                    st.markdown(f"### {ilac}")
                    
                    # 1. SGK ÖDEME DURUMU
                    is_paid = "ÖDENİR" in d[2].upper()
                    sgk_cls = "odenir" if is_paid else "odenmez"
                    st.markdown(f'<div class="sgk-card {sgk_cls}">📦 **SGK:** {d[2]}</div>', unsafe_allow_html=True)
                    
                    # 2. BRANŞ BİLGİSİ
                    st.markdown(f"👨‍⚕️ **Branşlar:** {d[5]}")
                    
                    # 3. SADE TANI ALANI (Kod ve Tanı)
                    st.markdown('<p class="mini-label">ICD-10 & TANI</p>', unsafe_allow_html=True)
                    st.code(f"{d[0]} - {d[1]}", language=None)
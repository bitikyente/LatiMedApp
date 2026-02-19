import streamlit as st
import pandas as pd
from fpdf import FPDF
import google.generativeai as genai
from PIL import Image
import io

# --- 1. AYARLAR VE TASARIM ---
st.set_page_config(page_title="LatiMed Pro", page_icon="⚕️", layout="wide")

# API Anahtarı Kontrolü (Streamlit Cloud Secrets)
if "API_KEY" in st.secrets:
    API_KEY = st.secrets["API_KEY"]
else:
    st.error("⚠️ API_KEY bulunamadı! Lütfen Streamlit Cloud Settings > Secrets kısmına anahtarınızı ekleyin.")
    st.stop()

genai.configure(api_key=API_KEY)
model = genai.GenerativeModel('models/gemini-2.0-flash')

# Modern Dark Stil
st.markdown("""
    <style>
    .stApp { background-color: #0f172a; color: #f1f5f9; }
    .badge { padding: 4px 12px; border-radius: 20px; font-size: 0.8rem; font-weight: bold; }
    .safe { background-color: #064e3b; color: #34d399; border: 1px solid #059669; }
    .danger { background-color: #7f1d1d; color: #f87171; border: 1px solid #b91c1c; }
    .status-card { padding: 10px; border-radius: 8px; font-size: 0.85rem; margin-top: 8px; border-left: 5px solid; }
    .sgk-odenir { background-color: #1e3a8a; color: #bfdbfe; border-color: #3b82f6; }
    .sgk-odenmez { background-color: #334155; color: #94a3b8; border-color: #64748b; }
    .stContainer { background-color: #1e293b !important; border: 1px solid #334155 !important; border-radius: 12px !important; }
    .mini-label { font-size: 0.75rem; color: #94a3b8; text-transform: uppercase; font-weight: bold; margin-top: 10px; }
    button[kind="secondary"] { background-color: transparent !important; border: none !important; color: #60a5fa !important; font-size: 1.2rem !important; }
    </style>
""", unsafe_allow_html=True)

if 'secili_ilaclar' not in st.session_state:
    st.session_state.secili_ilaclar = []

@st.cache_data
def load_data():
    try: return pd.read_excel('ilaclar_tanili.xlsx')
    except: return pd.DataFrame()

df = load_data()

# --- 2. GÜÇLENDİRİLMİŞ ANALİZ FONKSİYONU ---
def canli_analiz(ilac_adi):
    prompt = (f"İlaç: {ilac_adi}. Türkiye SGK/SUT ve İSG kriterlerine göre analiz et. "
              f"Yanıtı SADECE şu formatta ver (giriş cümlesi yazma): "
              f"ICD: [Kod] | TANI: [Teşhis Adı] | SGK: [Ödenir/Ödenmez] | HEKİM: [Klinik Not] | ENGEL: [Uygun/Engel] | BRANS: [Uzmanlıklar]")
    try:
        res = model.generate_content(prompt)
        text = res.text.strip()
        if "ICD:" in text: text = text[text.find("ICD:"):]
        return text
    except: return None

# --- HEADER & KAMERA ---
st.title("⚕️ LatiMed Pro")
st.caption("İSG & Klinik Mevzuat Paneli")

with st.expander("📷 Kamera ile Tara", expanded=False):
    img = st.camera_input("Kutuyu Okut")
    if img:
        res = model.generate_content(["İlaç adını oku:", Image.open(img)])
        ocr = res.text.strip().upper()
        if not df.empty and ocr:
            match = df[df['ilac_adi'].str.contains(ocr, case=False, na=False)]
            if not match.empty:
                st.session_state.secili_ilaclar.append(match.iloc[0]['ilac_adi'])
                st.rerun()

# --- 3. ANA PANEL ---
if not df.empty:
    secilenler = st.multiselect("İlaç Seçin:", options=sorted(df['ilac_adi'].unique()), 
                             default=st.session_state.secili_ilaclar, key="drug_selector_v3")
    st.session_state.secili_ilaclar = secilenler

    if secilenler:
        cols = st.columns(3)
        for idx, ilac in enumerate(secilenler):
            row = df[df['ilac_adi'] == ilac].iloc[0]
            raw = str(row['Analiz_Verisi'])
            
            # FORMAT KONTROLÜ (6 parça değilse canlı analiz yap)
            if "|" not in raw or len(raw.split('|')) < 6:
                with st.spinner(f"🔍 {ilac} güncelleniyor..."):
                    raw = canli_analiz(ilac)
            
            if raw and "|" in raw:
                d = [p.strip() for p in raw.split('|')]
                # Eksik parçaları "Bilgi yok" ile tamamla
                while len(d) < 6: d.append("Bilgi alınamadı")
                
                with cols[idx % 3]:
                    with st.container(border=True):
                        # DURUM VE POPUP
                        status = d[4].upper()
                        is_safe = "UYGUN DEĞİL" not in status and "ENGEL" not in status
                        b_cls, b_txt = ("safe", "🟢 UYGUN") if is_safe else ("danger", "🛑 ENGEL")
                        
                        r1, r2 = st.columns([0.8, 0.2])
                        with r1: st.markdown(f'<div class="badge {b_cls}">{b_txt}</div>', unsafe_allow_html=True)
                        with r2:
                            with st.popover("ⓘ"):
                                st.write(f"**Gerekçe:** {d[3].replace('HEKİM:', '').strip()}")

                        st.markdown(f"### {ilac}")
                        
                        # SGK DURUMU
                        sgk_v = d[2].replace('SGK:', '').strip()
                        sgk_cls = "sgk-odenir" if "ÖDENİR" in sgk_v.upper() else "sgk-odenmez"
                        st.markdown(f'<div class="status-card {sgk_cls}">📦 **SGK:** {sgk_v}</div>', unsafe_allow_html=True)
                        
                        # BRANŞ
                        st.markdown(f"👨‍⚕️ **Branşlar:** {d[5].replace('BRANS:', '').strip()}")
                        
                        # TEMİZ TANI
                        st.markdown('<p class="mini-label">ICD-10 & TANI</p>', unsafe_allow_html=True)
                        st.code(f"{d[0].replace('ICD:', '').strip()} - {d[1].replace('TANI:', '').strip()}", language=None)
            else:
                st.warning(f"⚠️ {ilac}: Veri formatı hatalı veya AI yanıt vermedi.")
else:
    st.error("Veritabanı taranıyor...")

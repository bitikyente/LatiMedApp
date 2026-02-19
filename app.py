import streamlit as st
import pandas as pd
from fpdf import FPDF
import google.generativeai as genai
from PIL import Image
import io
import re

# --- 1. AYARLAR VE MODERN DARK CSS ---
st.set_page_config(page_title="LatiMed Pro", page_icon="⚕️", layout="wide")

API_KEY = "AIzaSyCAIr-ejJ_Wfo3g-R-im3skFKKWDUvRY2E"
genai.configure(api_key=API_KEY)
model = genai.GenerativeModel('models/gemini-2.0-flash')

st.markdown("""
    <style>
    .stApp { background-color: #0f172a; color: #f1f5f9; }
    
    /* Rozetler */
    .badge { padding: 4px 12px; border-radius: 20px; font-size: 0.8rem; font-weight: bold; }
    .safe { background-color: #064e3b; color: #34d399; border: 1px solid #059669; }
    .danger { background-color: #7f1d1d; color: #f87171; border: 1px solid #b91c1c; }
    
    /* SGK ve Öneri Alanları */
    .sgk-card { background-color: #1e3a8a; color: #bfdbfe; padding: 10px; border-radius: 8px; font-size: 0.85rem; margin-top: 10px; border-left: 5px solid #3b82f6; }
    .hekim-oneri { background-color: #1e293b; border: 1px solid #334155; padding: 12px; border-radius: 8px; margin-top: 10px; font-style: italic; color: #cbd5e1; }
    
    .stContainer { background-color: #1e293b !important; border: 1px solid #334155 !important; border-radius: 12px !important; }
    .mini-label { font-size: 0.75rem; color: #94a3b8; text-transform: uppercase; font-weight: bold; margin-bottom: 2px; }
    
    /* Popover Buton Düzeltme */
    button[kind="secondary"] { background-color: transparent !important; border: none !important; color: #60a5fa !important; font-size: 1.2rem !important; }
    </style>
""", unsafe_allow_html=True)

# --- 2. SESSION STATE (SEÇİM KORUMA) ---
if 'secili_ilaclar' not in st.session_state:
    st.session_state.secili_ilaclar = []

@st.cache_data
def load_data():
    try: return pd.read_excel('ilaclar_tanili.xlsx')
    except: return pd.DataFrame()

df = load_data()

def canli_analiz(ilac_adi):
    # Prompt güncellendi: Giriş cümlesi yasaklandı
    prompt = (f"İlaç: {ilac_adi}. Türkiye SGK/SUT ve İSG kriterlerine göre analiz et. "
              f"SADECE şu formatta yanıt ver, giriş veya açıklama cümlesi ASLA yazma: "
              f"ICD: [Kod] | TANI: [Teşhis] | SGK: [Ödeme Kapsamı] | HEKİM: [Klinik Öneri] | ENGEL: [Uygun/Engel]")
    try:
        res = model.generate_content(prompt)
        text = res.text.strip()
        # Eğer yine de giriş cümlesi gelirse ICD'den öncesini temizle
        if "ICD:" in text:
            text = text[text.find("ICD:"):]
        return text
    except: return None

# --- HEADER & KAMERA ---
c1, c2 = st.columns([0.85, 0.15])
with c1:
    st.title("⚕️ LatiMed Pro")
    st.caption("İzmir İSG Klinik Karar Destek Paneli")
with c2:
    with st.popover("📷 Kamera", use_container_width=True):
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
    secilenler = st.multiselect(
        "İlaçları Seçin:", 
        options=sorted(df['ilac_adi'].unique()), 
        default=st.session_state.secili_ilaclar,
        key="drug_selector_widget" # Sabit key seçimi korur
    )
    st.session_state.secili_ilaclar = secilenler

    if secilenler:
        cols = st.columns(3)
        for idx, ilac in enumerate(secilenler):
            row = df[df['ilac_adi'] == ilac].iloc[0]
            raw = str(row['Analiz_Verisi'])
            
            # Veri bozuksa veya yoksa temiz analiz çek
            if "|" not in raw or len(raw.split('|')) < 5:
                with st.spinner(f"🔍 {ilac} analiz ediliyor..."):
                    raw = canli_analiz(ilac)
            
            if raw:
                d = [p.strip() for p in raw.split('|')]
                while len(d) < 5: d.append("Bilgi yok")
                
                with cols[idx % 3]:
                    with st.container(border=True):
                        # DURUM VE TIKLANABİLİR POPUP
                        status = d[4].upper()
                        is_safe = "UYGUN DEĞİL" not in status and "ENGEL" not in status
                        b_cls, b_txt = ("safe", "🟢 UYGUN") if is_safe else ("danger", "🛑 ENGEL")
                        
                        r1, r2 = st.columns([0.8, 0.2])
                        with r1:
                            st.markdown(f'<div class="badge {b_cls}">{b_txt}</div>', unsafe_allow_html=True)
                        with r2:
                            with st.popover("ⓘ"):
                                st.markdown("### Klinik Gerekçe")
                                st.write(d[3].replace('HEKİM:', '').strip())

                        st.markdown(f"### {ilac}")
                        
                        # SGK ÖDEME BİLGİSİ
                        sgk_v = d[2].replace('SGK:', '').strip()
                        if "ÖDENİR" in sgk_v.upper() or "KAPSAMINDA" in sgk_v.upper():
                            st.markdown(f'<div class="sgk-card">📘 **SGK:** {sgk_v}</div>', unsafe_allow_html=True)
                        
                        # ICD & TANI (Kopyalanabilir)
                        st.markdown('<p class="mini-label">ICD-10 & TANI</p>', unsafe_allow_html=True)
                        st.code(f"{d[0].replace('ICD:', '').strip()} | {d[1].replace('TANI:', '').strip()}", language=None)
                        
                        # HEKİM ÖNERİSİ
                        st.markdown('<p class="mini-label">Hekim Önerisi</p>', unsafe_allow_html=True)
                        st.markdown(f'<div class="hekim-oneri">👨‍⚕️ {d[3].replace("HEKİM:", "").strip()}</div>', unsafe_allow_html=True)
            else:
                st.error(f"⚠️ {ilac}: Veri alınamadı.")

        # --- ALT PANEL ---
        if len(secilenler) > 1:
            st.divider()
            with st.expander("⚠️ Çoklu İlaç Kombine Risk Analizi", expanded=True):
                with st.spinner("Analiz ediliyor..."):
                    resp = model.generate_content(f"Bu ilaçların kombine riskini özetle: {', '.join(secilenler)}")
                    st.write(resp.text)
else:
    st.error("Veritabanı taranıyor...")
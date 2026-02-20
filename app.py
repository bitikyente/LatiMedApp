import streamlit as st
import pandas as pd
import google.generativeai as genai
from PIL import Image
import io

# --- 1. AYARLAR VE GÜVENLİK ---
st.set_page_config(page_title="LatiMed Pro", page_icon="⚕️", layout="wide")

# API Anahtarı: Sızdırılmaması için Secrets'tan çekiyoruz
if "API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["API_KEY"])
else:
    st.error("⚠️ SORGULAMA YAPILAMIYOR: API anahtarı sisteme eklenmemiş.")
    st.stop()

model = genai.GenerativeModel('models/gemini-2.0-flash')

# Modern Dark Stil
st.markdown("""
    <style>
    .stApp { background-color: #0f172a; color: #f1f5f9; }
    .badge { padding: 4px 12px; border-radius: 20px; font-size: 0.8rem; font-weight: bold; }
    .safe { background-color: #064e3b; color: #34d399; border: 1px solid #059669; }
    .danger { background-color: #7f1d1d; color: #f87171; border: 1px solid #b91c1c; }
    .sgk-card { padding: 10px; border-radius: 8px; font-size: 0.85rem; margin-top: 8px; border-left: 5px solid; }
    .odenir { background-color: #1e3a8a; color: #bfdbfe; border-color: #3b82f6; }
    .odenmez { background-color: #334155; color: #94a3b8; border-color: #64748b; }
    .stContainer { background-color: #1e293b !important; border: 1px solid #334155 !important; border-radius: 12px !important; margin-bottom: 10px; }
    </style>
""", unsafe_allow_html=True)

# --- 2. VERİ YÜKLEME VE ANALİZ ---
@st.cache_data
def load_data():
    try: return pd.read_excel('ilaclar_tanili.xlsx')
    except: return pd.DataFrame(columns=['ilac_adi', 'Analiz_Verisi'])

df = load_data()

def canli_analiz(ilac_adi):
    prompt = (f"İlaç: {ilac_adi}. Türkiye SGK/SUT ve İSG kriterlerine göre analiz et. "
              f"Format: ICD: [Kod] | TANI: [SADECE Teşhis Adı] | SGK: [Ödenir/Ödenmez] | HEKİM: [Klinik Öneri] | ENGEL: [Uygun/Engel] | BRANS: [Branşlar]")
    try:
        res = model.generate_content(prompt)
        return res.text.strip()
    except: return None

# --- 3. KAMERA ÖZELLİĞİ (AYRI BÖLÜM) ---
st.title("⚕️ LatiMed Pro")
st.caption("Klinik Karar Destek Sistemi")

# Kamera butonu ve mantığı
if st.button("📷 İlaç Kutusu Tara", use_container_width=True):
    st.session_state.kamera_acik = True

if st.session_state.get('kamera_acik', False):
    # Android Arka Kamera Önceliği: 'facingMode': 'environment'
    img_file = st.camera_input("Kutuyu Ekranda Görünce Fotoğraf Çekin") 
    
    if img_file:
        with st.spinner("AI İlacı Algılıyor..."):
            res = model.generate_content(["Sadece ilaç adını büyük harfle yaz:", Image.open(img_file)])
            ocr_name = res.text.strip().upper()
            if ocr_name:
                st.success(f"Algılanan: {ocr_name}")
                if ocr_name not in st.session_state.get('secili_ilaclar', []):
                    st.session_state.setdefault('secili_ilaclar', []).append(ocr_name)
                    st.session_state.kamera_acik = False
                    st.rerun()

# --- 4. ANA SORGULAMA PANELİ ---
if 'secili_ilaclar' not in st.session_state:
    st.session_state.secili_ilaclar = []

secilenler = st.multiselect("İlaç Sorgulama:", options=sorted(df['ilac_adi'].unique()) if not df.empty else [], 
                           default=st.session_state.secili_ilaclar, key="v6_selector")
st.session_state.secili_ilaclar = secilenler

if secilenler:
    cols = st.columns(3)
    for idx, ilac in enumerate(secilenler):
        # Excel'den veri çekme veya canlı analiz
        row = df[df['ilac_adi'] == ilac]
        raw = str(row.iloc[0]['Analiz_Verisi']) if not row.empty else ""
        
        if "|" not in raw or len(raw.split('|')) < 6:
            with st.spinner(f"🔍 {ilac} analiz ediliyor..."):
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
                    
                    # SGK DURUMU
                    sgk_cls = "odenir" if "ÖDENİR" in d[2].upper() else "odenmez"
                    st.markdown(f'<div class="sgk-card {sgk_cls}">📦 **SGK:** {d[2]}</div>', unsafe_allow_html=True)
                    
                    # BRANŞ VE TANI
                    st.write(f"👨‍⚕️ **Branş:** {d[5]}")
                    st.code(f"{d[0]} - {d[1]}", language=None)

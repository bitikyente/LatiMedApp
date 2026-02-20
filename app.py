import streamlit as st
import pandas as pd
import google.generativeai as genai
from PIL import Image
import io

# --- 1. AYARLAR ---
st.set_page_config(page_title="LatiMed Pro", page_icon="⚕️", layout="wide")

if "API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["API_KEY"])
else:
    st.error("⚠️ API ANAHTARI HATASI: Lütfen Secrets kısmına yeni anahtarınızı ekleyin.")
    st.stop()

model = genai.GenerativeModel('models/gemini-2.0-flash')

# Modern Dark Stil
st.markdown("""
    <style>
    .stApp { background-color: #0f172a; color: #f1f5f9; }
    .badge { padding: 4px 12px; border-radius: 20px; font-size: 0.8rem; font-weight: bold; }
    .safe { background-color: #064e3b; color: #34d399; border: 1px solid #059669; }
    .danger { background-color: #7f1d1d; color: #f87171; border: 1px solid #b91c1c; }
    .status-card { padding: 8px; border-radius: 6px; font-size: 0.85rem; margin-top: 5px; border-left: 5px solid; }
    .sgk-true { background-color: #1e3a8a; color: #bfdbfe; border-color: #3b82f6; }
    .sgk-false { background-color: #334155; color: #94a3b8; border-color: #64748b; }
    .stContainer { background-color: #1e293b !important; border: 1px solid #334155 !important; border-radius: 12px !important; }
    .mini-label { font-size: 0.7rem; color: #94a3b8; text-transform: uppercase; font-weight: bold; margin-top: 10px; }
    </style>
""", unsafe_allow_html=True)

# --- 2. ANALİZ MOTORU (6 Parçalı) ---
def canli_analiz(ilac_adi):
    prompt = (f"İlaç: {ilac_adi}. Türkiye SGK/SUT ve İSG kriterlerine göre analiz et. "
              f"Yanıtı SADECE şu formatta ver: ICD: [Kod] | TANI: [Sadece İsim] | "
              f"SGK: [Ödenir/Ödenmez] | HEKİM: [Klinik Not] | ENGEL: [Uygun/Engel] | BRANS: [Uzmanlıklar]")
    try:
        res = model.generate_content(prompt)
        return res.text.strip()
    except: return None

# --- 3. KAMERA VE SORGULAMA ---
if 'secili_ilaclar' not in st.session_state:
    st.session_state.secili_ilaclar = []

st.title("⚕️ LatiMed Pro")
st.caption("Klinik Karar Destek Sistemi")

# Kamera Butonu
if st.button("📷 İlaç Kutusu Tara", use_container_width=True):
    st.session_state.cam = True

if st.session_state.get('cam', False):
    # Android arka kamera için ipucu: facingMode: environment
    foto = st.camera_input("Kutuyu Odaklayın ve Çekin")
    if foto:
        res = model.generate_content(["İlacın ismini yaz:", Image.open(foto)])
        isim = res.text.strip().upper()
        if isim not in st.session_state.secili_ilaclar:
            st.session_state.secili_ilaclar.append(isim)
            st.session_state.cam = False
            st.rerun()

# --- 4. SONUÇLAR ---
try:
    df = pd.read_excel('ilaclar_tanili.xlsx')
except:
    df = pd.DataFrame(columns=['ilac_adi', 'Analiz_Verisi'])

secilenler = st.multiselect("İlaç Sorgulama:", options=sorted(df['ilac_adi'].unique()) if not df.empty else [], 
                           default=st.session_state.secili_ilaclar, key="v_final")
st.session_state.secili_ilaclar = secilenler

if secilenler:
    cols = st.columns(3)
    for idx, ilac in enumerate(secilenler):
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
                    # DURUM VE POPUP
                    status = d[4].upper()
                    is_safe = "ENGEL" not in status and "UYGUN DEĞİL" not in status
                    b_cls, b_txt = ("safe", "🟢 UYGUN") if is_safe else ("danger", "🛑 ENGEL")
                    
                    st.markdown(f'<div class="badge {b_cls}">{b_txt}</div>', unsafe_allow_html=True)
                    st.markdown(f"### {ilac}")
                    
                    # SGK DURUMU
                    sgk_durum = d[2]
                    sgk_cls = "sgk-true" if "ÖDENİR" in sgk_durum.upper() else "sgk-false"
                    st.markdown(f'<div class="status-card {sgk_cls}">📦 **SGK:** {sgk_durum}</div>', unsafe_allow_html=True)
                    
                    # BRANŞ BİLGİSİ
                    st.write(f"👨‍⚕️ **Yazabilecek Branş:** {d[5]}")
                    
                    # SADE TANI
                    st.markdown('<p class="mini-label">ICD-10 & TANI</p>', unsafe_allow_html=True)
                    st.code(f"{d[0]} - {d[1]}", language=None)
                    
                    with st.expander("Detaylı Not"):
                        st.write(d[3])

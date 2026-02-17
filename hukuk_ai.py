import streamlit as st
import openai
from PyPDF2 import PdfReader

st.set_page_config(page_title="Hukuk Bürosu AI v3", layout="wide")
st.title("⚖️ Gelişmiş Hukuk Asistanı (İçtihat Destekli)")

api_key = st.sidebar.text_input("OpenAI API Anahtarınızı Girin:", type="password")

def metin_analiz_et(metin):
    client = openai.OpenAI(api_key=api_key)
    prompt = f"Aşağıdaki hukuki metni Olay, İddialar, Riskler ve Strateji olarak analiz et:\n\n{metin}"
    response = client.chat.completions.create(model="gpt-4o", messages=[{"role": "user", "content": prompt}])
    return response.choices[0].message.content

def dilekce_yaz_ictihatli(analiz_notlari):
    client = openai.OpenAI(api_key=api_key)
    # Burada "Seçenek A"yı devreye alıyoruz
    prompt = f"""
    Aşağıdaki analize dayanarak resmi bir dava dilekçesi yaz. 
    
    ÖNEMLİ: Dilekçenin sonuna 'HUKUKİ DAYANAKLAR VE EMSAL İLKELER' başlığı aç. 
    Bu bölümde, davanın konusuyla ilgili (örneğin işe iade, tazminat vb.) 
    Yargıtay'ın yerleşik içtihatlarından, genel hukuk ilkelerinden ve ilgili kanun maddelerinden 
    profesyonel bir dille bahset. Somut karar numarası veremiyorsan bile 'Yargıtay'ın yerleşik uygulamasına göre...' şeklinde genel ilkeleri belirt.

    Analiz:
    {analiz_notlari}
    """
    response = client.chat.completions.create(model="gpt-4o", messages=[{"role": "user", "content": prompt}])
    return response.choices[0].message.content

yuklenen_dosya = st.file_uploader("Analiz için PDF yükleyin", type="pdf")

if yuklenen_dosya and api_key:
    reader = PdfReader(yuklenen_dosya)
    ham_metin = "".join([page.extract_text() for page in reader.pages])
    
    if st.button("1. Analizi Başlat"):
        st.session_state['analiz'] = metin_analiz_et(ham_metin)
    
    if 'analiz' in st.session_state:
        st.info("Hukuki Analiz")
        st.write(st.session_state['analiz'])
        
        if st.button("2. İçtihat Destekli Dilekçe Oluştur"):
            st.session_state['dilekce'] = dilekce_yaz_ictihatli(st.session_state['analiz'])
            
    if 'dilekce' in st.session_state:
        st.success("İçtihat Destekli Dilekçe Taslağı")
        st.text_area("Düzenlenebilir Metin", value=st.session_state['dilekce'], height=500)
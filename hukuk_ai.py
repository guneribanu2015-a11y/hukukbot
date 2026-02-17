import streamlit as st
import openai
from PyPDF2 import PdfReader

# --- SAYFA AYARLARI ---
st.set_page_config(
    page_title="HukukBot - Akıllı Hukuk Asistanı", 
    page_icon="⚖️", 
    layout="wide"
)

# --- BAŞLIK VE AÇIKLAMA ---
st.title("⚖️ HukukBot v1.0")
st.markdown("""
**HukukBot**, dava dosyalarınızı analiz eder, riskleri belirler ve içtihat destekli dilekçe taslakları hazırlar.
*Sistem profesyonel bir yardımcı araçtır; nihai karar yetkisi avukata aittir.*
""")
st.divider()

# --- GÜVENLİ API ANAHTARI KONTROLÜ (Streamlit Secrets) ---
if "OPENAI_API_KEY" in st.secrets:
    api_key = st.secrets["OPENAI_API_KEY"]
else:
    st.sidebar.error("⚠️ API Anahtarı bulunamadı! Lütfen Streamlit Cloud ayarlarından 'Secrets' kısmına OPENAI_API_KEY tanımlayın.")
    st.stop()

# --- FONKSİYONLAR ---

def metin_analiz_et(metin):
    """Dosya içeriğini analiz eden fonksiyon."""
    client = openai.OpenAI(api_key=api_key)
    prompt = f"""
    Aşağıdaki hukuki metni (dilekçe, karar veya tutanak) bir kıdemli avukat titizliğiyle analiz et:
    1. OLAYIN ÖZETİ: Maddeler halinde kronolojik akış.
    2. KRİTİK İDDİALAR VE DAYANAKLAR: Tarafların temel argümanları.
    3. RİSK ANALİZİ: Davanın zayıf noktaları ve dikkat edilmesi gereken hukuki boşluklar.
    4. STRATEJİK TAVSİYE: Bir sonraki adım için önerilen hukuki yol haritası.

    Metin:
    {metin}
    """
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2
    )
    return response.choices[0].message.content

def dilekce_yaz_ictihatli(analiz_notlari):
    """Analize uygun, içtihat destekli dilekçe yazan fonksiyon."""
    client = openai.OpenAI(api_key=api_key)
    prompt = f"""
    Aşağıdaki hukuki analize dayanarak resmi, ağır ve profesyonel bir dava dilekçesi taslağı hazırla.
    
    ÖNEMLİ KURALLAR:
    - Dilekçenin sonuna 'HUKUKİ DAYANAKLAR VE EMSAL İLKELER' başlığı ekle.
    - Bu bölümde, konuyla ilgili bilinen Yargıtay yerleşik içtihatlarından ve genel hukuk ilkelerinden (örn: Son Çare İlkesi, Dürüstlük Kuralı vb.) bahset.
    - Boş bırakılması gereken yerleri [ ] içinde belirt.

    Analiz Notları:
    {analiz_notlari}
    """
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.5
    )
    return response.choices[0].message.content

# --- ARAYÜZ (KULLANICI PANELİ) ---

col1, col2 = st.columns([1, 2])

with col1:
    st.subheader("📁 Dosya İşlemleri")
    yuklenen_dosya = st.file_uploader("Analiz edilecek PDF dosyasını yükleyin", type="pdf")
    
    if yuklenen_dosya:
        # PDF'den metin çıkarma
        with st.spinner("Dosya okunuyor..."):
            reader = PdfReader(yuklenen_dosya)
            ham_metin = "".join([page.extract_text() for page in reader.pages if page.extract_text()])
            st.success("Dosya başarıyla yüklendi.")

        if st.button("🚀 1. Analizi Başlat"):
            st.session_state['analiz_sonucu'] = metin_analiz_et(ham_metin)

with col2:
    st.subheader("🔍 Hukuki İnceleme & Çıktılar")
    
    # 1. Analiz Çıktısı Gösterimi
    if 'analiz_sonucu' in st.session_state:
        st.info("Hukuki Analiz Raporu")
        st.markdown(st.session_state['analiz_sonucu'])
        
        st.divider()
        
        # 2. Dilekçe Yazma Butonu
        if st.button("⚖️ 2. İçtihat Destekli Dilekçe Taslağı Oluştur"):
            with st.spinner("Dilekçe kurgulanıyor..."):
                st.session_state['dilekce_metni'] = dilekce_yaz_ictihatli(st.session_state['analiz_sonucu'])
    
    # 3. Dilekçe Çıktısı ve İndirme
    if 'dilekce_metni' in st.session_state:
        st.success("Dilekçe Taslağı Hazır")
        st.text_area("Düzenlenebilir Dilekçe Metni", value=st.session_state['dilekce_metni'], height=500)
        st.download_button(
            label="📄 Dilekçeyi İndir (.txt)",
            data=st.session_state['dilekce_metni'],
            file_name="hukukbot_dilekce_taslagi.txt",
            mime="text/plain"
        )

# --- ALT BİLGİ ---
st.markdown("---")
st.caption("HukukBot | Yapay Zeka Destekli Hukuki Karar Destek Sistemi")

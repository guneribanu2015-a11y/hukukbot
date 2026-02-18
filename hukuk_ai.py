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
st.title("⚖️ HukukBot v2.5")
st.markdown("""
**HukukBot**, dava dosyalarınızı analiz eder, riskleri belirler ve **gerçek içtihat + güncel kanun metni destekli** dilekçe taslakları hazırlar.
*Sistem profesyonel bir yardımcı araçtır; nihai karar yetkisi avukata aittir.*
""")
st.divider()

# --- GÜVENLİ API ANAHTARI KONTROLÜ ---
if "OPENAI_API_KEY" in st.secrets:
    api_key = st.secrets["OPENAI_API_KEY"]
else:
    st.sidebar.error("⚠️ API Anahtarı bulunamadı! Lütfen Streamlit Cloud ayarlarından 'Secrets' kısmına OPENAI_API_KEY tanımlayın.")
    st.stop()

# --- FONKSİYONLAR ---

def pdf_metin_cek(dosya):
    """Herhangi bir PDF'den metin çıkarır."""
    reader = PdfReader(dosya)
    metin = "".join([
        page.extract_text() for page in reader.pages 
        if page.extract_text()
    ])
    return metin

def kanun_linki_olustur(kanun_numarasi):
    """
    Kanun numarasından direkt link oluşturur - metin çekmez
    """
    return f"https://www.mevzuat.gov.tr/mevzuat?MevzuatNo={kanun_numarasi}&MevzuatTur=1&MevzuatTertip=5"

def metin_analiz_et(metin):
    """Dava dosyasını analiz eder."""
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

def dilekce_yaz_gercek_ictihatli(analiz_notlari, ictihat_metni):
    """
    Gerçek içtihat metni varsa oradan alıntı yaparak dilekçe yazar.
    İçtihat yoksa genel hukuk ilkelerine dayanır, esas numarası uydurmaz.
    """
    client = openai.OpenAI(api_key=api_key)

    # İçtihat talimatı
    if ictihat_metni.strip():
        ictihat_talimati = f"""
        YÜKLENEN GERÇEK İÇTİHATLAR:
        {ictihat_metni}

        ÖNEMLİ KURALLAR — BUNLARA KESİNLİKLE UY:
        - Yukarıdaki içtihat metninden doğrudan alıntı yap.
        - Sadece metinde geçen gerçek esas numaralarını kullan.
        - KESİNLİKLE esas numarası uydurma. Metinde olmayan hiçbir karar numarası yazma.
        - İçtihat metninde hangi Yargıtay dairesi ve hangi tarih geçiyorsa aynen yaz.
        - Eğer içtihat metni belirli bir konuyu kapsamıyorsa, o konuda içtihat atfı yapma.
          Bunun yerine 'ilgili Yargıtay içtihadına göre' gibi genel ifade kullan.
        """
    else:
        ictihat_talimati = """
        ÖNEMLİ KURALLAR — BUNLARA KESİNLİKLE UY:
        - Hiçbir Yargıtay kararı esas numarası uydurma.
        - Esas numara yerine sadece genel hukuk ilkelerine atıf yap.
          Örnek: 'Yargıtay'ın yerleşik içtihadı gereğince' veya 'dürüstlük kuralı çerçevesinde'
        - Dilekçenin sonuna şu notu ekle:
          '[NOT: Bu bölümdeki içtihat atıfları avukat tarafından gerçek Yargıtay kararlarıyla 
          desteklenmeli ve esas numaraları eklenmelidir.]'
        """

    prompt = f"""
    Aşağıdaki hukuki analize dayanarak resmi, ağır ve profesyonel bir dava dilekçesi taslağı hazırla.

    {ictihat_talimati}

    DİĞER KURALLAR:
    - Dilekçenin sonuna 'HUKUKİ DAYANAKLAR VE EMSAL İLKELER' başlığı ekle.
    - Boş bırakılması gereken yerleri [ ] içinde belirt.
    - Taraf isimleri için [DAVACI ADI], [DAVALI ADI] kullan.

    ANALİZ NOTLARI:
    {analiz_notlari}
    """
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3
    )
    return response.choices[0].message.content

def serbest_komut_calistir(metin, komut):
    """Kullanıcının serbest komutuyla belge üzerinde işlem yapar."""
    client = openai.OpenAI(api_key=api_key)
    prompt = f"""
    Aşağıdaki hukuki belge üzerinde şu işlemi gerçekleştir: {komut}

    KURALLAR:
    - Hukuki dil ve terminolojiye uy.
    - İçtihat veya esas numarası ekleme — sadece istenen işlemi yap.
    - Çıktı profesyonel ve kullanıma hazır olsun.

    BELGE:
    {metin}
    """
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.4
    )
    return response.choices[0].message.content

# --- SESSION STATE BAŞLATMA ---
for key in ['analiz_sonucu', 'dilekce_metni', 'ictihat_metni', 'serbest_sonuc', 'arama_sonuclari']:
    if key not in st.session_state:
        st.session_state[key] = '' if key != 'arama_sonuclari' else []

# --- ARAYÜZ ---
col1, col2 = st.columns([1, 2])

# ── SOL PANEL ────────────────────────────────────────────────
with col1:
    st.subheader("📁 Dosya İşlemleri")

    # 1. Dava Dosyası
    st.markdown("**1. Analiz edilecek dosya**")
    yuklenen_dosya = st.file_uploader(
        "Dava dosyasını yükleyin", 
        type="pdf", 
        key="dava_pdf"
    )

    if yuklenen_dosya:
        with st.spinner("Dosya okunuyor..."):
            ham_metin = pdf_metin_cek(yuklenen_dosya)
        if ham_metin:
            st.success(f"✅ Dosya yüklendi ({len(ham_metin)} karakter)")
            st.session_state['ham_metin'] = ham_metin
        else:
            st.warning("⚠️ PDF'den metin çıkarılamadı.")
    
    # Analiz butonu dosya yüklendikten hemen sonra
    if st.session_state.get('ham_metin'):
        if st.button("🚀 1. Analizi Başlat", use_container_width=True):
            with st.spinner("🤖 Analiz yapılıyor..."):
                sonuc = metin_analiz_et(st.session_state['ham_metin'])
            st.session_state['analiz_sonucu'] = sonuc
            st.rerun()

    st.divider()

    # 2. İçtihat PDF'leri — YENİ
    st.markdown("**2. Yargıtay İçtihat Kararları** *(isteğe bağlı)*")
    st.caption("Gerçek esas numarası için kendi içtihat PDF'lerinizi yükleyin.")

    ictihat_dosyalari = st.file_uploader(
        "İçtihat PDF'lerini yükleyin (birden fazla olabilir)",
        type="pdf",
        key="ictihat_pdf",
        accept_multiple_files=True
    )

    if ictihat_dosyalari:
        tum_ictihat = ""
        for dosya in ictihat_dosyalari:
            with st.spinner(f"📖 {dosya.name} okunuyor..."):
                metin = pdf_metin_cek(dosya)
                tum_ictihat += f"\n\n--- {dosya.name} ---\n{metin}"
        st.session_state['ictihat_metni'] = tum_ictihat
        st.success(f"✅ {len(ictihat_dosyalari)} içtihat belgesi yüklendi")
    else:
        st.session_state['ictihat_metni'] = ''
        st.info("💡 İçtihat yüklenmezse dilekçede esas numarası yazılmaz.")

    st.divider()
    
    # 3. Kanun Linki Oluştur — Sadece Numara
    st.markdown("**3. Kanun Metni Linki** *(isteğe bağlı)*")
    st.caption("Kanun numarasından mevzuat.gov.tr linki oluşturur.")
    
    kanun_numarasi_input = st.text_input(
        "Kanun numarasını girin (örn: 5237, 6098, 4721)",
        key="kanun_no_input",
        placeholder="5237"
    )
    
    if st.button("🔗 Kanun Linkini Oluştur", use_container_width=True):
        if kanun_numarasi_input.strip():
            kanun_url = kanun_linki_olustur(kanun_numarasi_input.strip())
            st.session_state['kanun_url'] = kanun_url
            st.session_state['kanun_no_link'] = kanun_numarasi_input.strip()
            st.success(f"✅ Link oluşturuldu")
        else:
            st.warning("Lütfen kanun numarası girin")
    
    # Oluşturulan linki göster
    if st.session_state.get('kanun_url'):
        st.info(f"📜 {st.session_state.get('kanun_no_link', '?')} sayılı kanun")
        st.markdown(f"**[Kanunu Mevzuat.gov.tr'de Aç]({st.session_state['kanun_url']})**")
        st.caption("💡 İpucu: Sık kullanılan kanunlar - 5237 (TCK), 6098 (TBK), 4721 (TMK), 6100 (HMK)")

    st.divider()

# ── SAĞ PANEL ────────────────────────────────────────────────
with col2:
    st.subheader("🔍 Hukuki İnceleme & Çıktılar")

    # Analiz Sonucu
    if st.session_state['analiz_sonucu']:
        st.info("📋 Hukuki Analiz Raporu")
        st.markdown(st.session_state['analiz_sonucu'])
        st.divider()

        # İçtihat durumu göster
        if st.session_state['ictihat_metni']:
            st.success("⚖️ Gerçek içtihat yüklendi — esas numaraları belgeden alınacak")
        else:
            st.warning("⚠️ İçtihat yüklenmedi — esas numarası yazılmayacak, genel ilkeler kullanılacak")

        # Dilekçe Butonu
        if st.button("⚖️ 2. İçtihat Destekli Dilekçe Taslağı Oluştur", use_container_width=True):
            with st.spinner("✍️ Dilekçe hazırlanıyor..."):
                dilekce = dilekce_yaz_gercek_ictihatli(
                    st.session_state['analiz_sonucu'],
                    st.session_state['ictihat_metni']
                )
            st.session_state['dilekce_metni'] = dilekce
            st.rerun()

    # Dilekçe Çıktısı
    if st.session_state['dilekce_metni']:
        st.success("✅ Dilekçe Taslağı Hazır")
        duzenlenen = st.text_area(
            "Düzenlenebilir Dilekçe Metni", 
            value=st.session_state['dilekce_metni'], 
            height=400
        )
        st.download_button(
            label="📄 Dilekçeyi İndir (.txt)",
            data=duzenlenen,
            file_name="hukukbot_dilekce_taslagi.txt",
            mime="text/plain"
        )

        st.divider()

        # ── SERBEST KOMUT — YENİ ──────────────────────────
        st.markdown("#### 💬 Belge Üzerinde Serbest Komut")
        st.caption("Dilekçe üzerinde istediğin işlemi yaz.")

        komut_ornekleri = [
            "Seç veya kendin yaz...",
            "Bu dilekçeyi özetle",
            "Daha resmi bir dil kullan",
            "Sözleşme formatına çevir",
            "Savunma dilekçesi olarak yeniden yaz",
            "Madde madde listele",
            "İngilizceye çevir",
        ]
        secilen_ornek = st.selectbox("Hazır komutlar:", komut_ornekleri, key="komut_sec")

        serbest_komut = st.text_input(
            "Ya da kendin yaz:",
            value="" if secilen_ornek == "Seç veya kendin yaz..." else secilen_ornek,
            placeholder="örn: Bu dilekçeyi özetle, sadece 3 paragraf olsun"
        )

        if st.button("▶️ Komutu Çalıştır", use_container_width=True):
            if serbest_komut.strip():
                with st.spinner(f"⚙️ '{serbest_komut}' uygulanıyor..."):
                    sonuc = serbest_komut_calistir(
                        st.session_state['dilekce_metni'], 
                        serbest_komut
                    )
                st.session_state['serbest_sonuc'] = sonuc
                st.rerun()
            else:
                st.warning("Lütfen bir komut girin.")

    # Serbest Komut Sonucu
    if st.session_state['serbest_sonuc']:
        st.info("💬 Komut Sonucu")
        serbest_duzenlenen = st.text_area(
            "Düzenlenebilir Çıktı",
            value=st.session_state['serbest_sonuc'],
            height=300
        )
        st.download_button(
            label="📄 Sonucu İndir (.txt)",
            data=serbest_duzenlenen,
            file_name="hukukbot_komut_sonucu.txt",
            mime="text/plain"
        )

# --- ALT BİLGİ ---
st.markdown("---")
st.caption("HukukBot v2.5 | Yapay Zeka Destekli Hukuki Karar Destek Sistemi")

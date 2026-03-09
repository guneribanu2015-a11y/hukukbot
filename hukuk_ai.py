import streamlit as st
import openai
from PyPDF2 import PdfReader
import streamlit.components.v1 as components

# --- SAYFA AYARLARI ---
st.set_page_config(
    page_title="HukukBot - Akıllı Hukuk Asistanı", 
    page_icon="⚖️", 
    layout="wide"
)

# --- GOOGLE ANALYTİCS ---
components.html("""
<script async src="https://www.googletagmanager.com/gtag/js?id=G-LJ0PN6PSD1"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){dataLayer.push(arguments);}
  gtag('js', new Date());
  gtag('config', 'G-LJ0PN6PSD1');
</script>
""", height=0)

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
    """Kanun numarasından direkt link oluşturur."""
    return f"https://www.mevzuat.gov.tr/mevzuat?MevzuatNo={kanun_numarasi}&MevzuatTur=1&MevzuatTertip=5"

# --- POPÜLER KANUNLAR VERİTABANI ---
KANUN_VERITABANI = {
    # Ceza
    "türk ceza kanunu": ("5237", "Türk Ceza Kanunu"),
    "tck": ("5237", "Türk Ceza Kanunu"),
    "ceza muhakemesi": ("5271", "Ceza Muhakemesi Kanunu"),
    "cmk": ("5271", "Ceza Muhakemesi Kanunu"),
    "infaz": ("5275", "Ceza ve Güvenlik Tedbirlerinin İnfazı Hakkında Kanun"),
    
    # Medeni / Borçlar
    "türk medeni kanunu": ("4721", "Türk Medeni Kanunu"),
    "tmk": ("4721", "Türk Medeni Kanunu"),
    "medeni kanun": ("4721", "Türk Medeni Kanunu"),
    "türk borçlar kanunu": ("6098", "Türk Borçlar Kanunu"),
    "tbk": ("6098", "Türk Borçlar Kanunu"),
    "borçlar kanunu": ("6098", "Türk Borçlar Kanunu"),
    
    # Usul
    "hukuk muhakemeleri kanunu": ("6100", "Hukuk Muhakemeleri Kanunu"),
    "hmk": ("6100", "Hukuk Muhakemeleri Kanunu"),
    "icra ve iflas": ("2004", "İcra ve İflas Kanunu"),
    "iik": ("2004", "İcra ve İflas Kanunu"),
    "icra kanunu": ("2004", "İcra ve İflas Kanunu"),
    
    # İş / Sosyal
    "iş kanunu": ("4857", "İş Kanunu"),
    "işkanunu": ("4857", "İş Kanunu"),
    "sendikalar": ("6356", "Sendikalar ve Toplu İş Sözleşmesi Kanunu"),
    "sosyal sigortalar": ("5510", "Sosyal Sigortalar ve Genel Sağlık Sigortası Kanunu"),
    "ssgss": ("5510", "Sosyal Sigortalar ve Genel Sağlık Sigortası Kanunu"),
    
    # Ticaret / Vergi
    "türk ticaret kanunu": ("6102", "Türk Ticaret Kanunu"),
    "ttk": ("6102", "Türk Ticaret Kanunu"),
    "ticaret kanunu": ("6102", "Türk Ticaret Kanunu"),
    "gelir vergisi": ("193", "Gelir Vergisi Kanunu"),
    "katma değer vergisi": ("3065", "Katma Değer Vergisi Kanunu"),
    "kdv": ("3065", "Katma Değer Vergisi Kanunu"),
    "vergi usul": ("213", "Vergi Usul Kanunu"),
    "vuk": ("213", "Vergi Usul Kanunu"),
    
    # Anayasa / İdare
    "anayasa": ("2709", "Türkiye Cumhuriyeti Anayasası"),
    "idari yargılama": ("2577", "İdari Yargılama Usulü Kanunu"),
    "iyuk": ("2577", "İdari Yargılama Usulü Kanunu"),
    "kamulaştırma": ("2942", "Kamulaştırma Kanunu"),
    
    # Tüketici / Kişisel Veri
    "tüketicinin korunması": ("6502", "Tüketicinin Korunması Hakkında Kanun"),
    "tkhk": ("6502", "Tüketicinin Korunması Hakkında Kanun"),
    "kişisel verilerin korunması": ("6698", "Kişisel Verilerin Korunması Kanunu"),
    "kvkk": ("6698", "Kişisel Verilerin Korunması Kanunu"),
    
    # Aile / Miras
    "aile": ("4721", "Türk Medeni Kanunu"),
    "miras": ("4721", "Türk Medeni Kanunu"),
    "velayet": ("4721", "Türk Medeni Kanunu"),
}

def kanun_ara_isimden(giris, api_key):
    """
    Önce hardcode listede ara, bulamazsa OpenAI ile tahmin et.
    Döner: (kanun_no, kanun_adi, kaynak) veya None
    """
    temiz = giris.strip().lower()
    
    # 1. Doğrudan numara mı?
    if temiz.isdigit():
        return (temiz, f"{temiz} Sayılı Kanun", "numara")
    
    # 2. Hardcode listede ara (kısmi eşleşme)
    for anahtar, (no, ad) in KANUN_VERITABANI.items():
        if anahtar in temiz or temiz in anahtar:
            return (no, ad, "liste")
    
    # 3. OpenAI ile tahmin
    try:
        client = openai.OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{
                "role": "user",
                "content": f"""Türk hukukunda '{giris}' ile ilgili en uygun kanunun numarasını ve tam adını söyle.
SADECE şu formatta yanıt ver, başka hiçbir şey yazma:
NUMARA: [kanun numarası]
AD: [kanun tam adı]

Eğer emin değilsen veya böyle bir kanun yoksa:
NUMARA: YOK
AD: YOK"""
            }],
            temperature=0,
            max_tokens=100
        )
        yanit = response.choices[0].message.content.strip()
        satirlar = {s.split(":")[0].strip(): s.split(":", 1)[1].strip() 
                   for s in yanit.split("\n") if ":" in s}
        no = satirlar.get("NUMARA", "YOK")
        ad = satirlar.get("AD", "YOK")
        if no != "YOK" and no.strip():
            return (no, ad, "ai")
    except Exception:
        pass
    
    return None

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
    st.markdown("**1. Analiz edilecek dava dosyası**")
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
    
    # 3. Kanun Linki Oluştur — İsim veya Numara
    st.markdown("**3. Kanun Metni Linki** *(isteğe bağlı)*")
    st.caption("Kanun adı **veya** numarasıyla mevzuat.gov.tr linki oluşturur.")
    
    kanun_giris = st.text_input(
        "Kanun adı veya numarasını girin",
        key="kanun_giris_input",
        placeholder="örn: iş kanunu, TCK, 6098, borçlar..."
    )
    
    if st.button("🔗 Kanun Linkini Oluştur", use_container_width=True):
        if kanun_giris.strip():
            with st.spinner("Kanun aranıyor..."):
                sonuc = kanun_ara_isimden(kanun_giris.strip(), api_key)
            if sonuc:
                no, ad, kaynak = sonuc
                kanun_url = kanun_linki_olustur(no)
                st.session_state['kanun_url'] = kanun_url
                st.session_state['kanun_no_link'] = no
                st.session_state['kanun_ad_link'] = ad
                st.session_state['kanun_kaynak'] = kaynak
            else:
                st.error("❌ Kanun bulunamadı. Lütfen kanun numarasını doğrudan girin.")
                st.session_state['kanun_url'] = ''
        else:
            st.warning("Lütfen kanun adı veya numarası girin")
    
    # Oluşturulan linki göster
    if st.session_state.get('kanun_url'):
        kaynak = st.session_state.get('kanun_kaynak', '')
        kaynak_etiketi = {"numara": "🔢 Numara ile", "liste": "📋 Listeden", "ai": "🤖 AI ile bulundu"}.get(kaynak, "")
        st.info(f"📜 **{st.session_state.get('kanun_ad_link', '?')}** ({st.session_state.get('kanun_no_link', '?')} Sayılı Kanun)  \n{kaynak_etiketi}")
        st.markdown(f"**[Kanunu Mevzuat.gov.tr'de Aç ↗]({st.session_state['kanun_url']})**")
    
    with st.expander("💡 Örnek aramalar"):
        st.caption("TCK · iş kanunu · borçlar kanunu · TMK · HMK · KVKK · icra kanunu · ticaret kanunu")

    st.divider()

    # Analiz Butonu
    if st.session_state.get('ham_metin'):
        if st.button("🚀 1. Analizi Başlat", use_container_width=True):
            with st.spinner("🤖 Analiz yapılıyor..."):
                sonuc = metin_analiz_et(st.session_state['ham_metin'])
            st.session_state['analiz_sonucu'] = sonuc
            st.rerun()

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

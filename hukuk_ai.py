import streamlit as st
import openai
from PyPDF2 import PdfReader
import requests
from bs4 import BeautifulSoup
import re

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

def kelime_ile_kanun_ara(kelime):
    """
    mevzuat.gov.tr'de kelime ile arama yapar ve sonuçları listeler.
    Örnek: kelime_ile_kanun_ara("tazminat") → ilgili kanunları listeler
    """
    try:
        # mevzuat.gov.tr arama API'si
        arama_url = "https://www.mevzuat.gov.tr/MevzuatFihrist"
        
        params = {
            'Kelime': kelime,
            'MevzuatTur': '1',  # Kanunlar
            'MevzuatTertip': '5'
        }
        
        response = requests.get(arama_url, params=params, timeout=10)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Sonuç tablosunu bul
            sonuc_tablosu = soup.find('table', {'class': 'mevzuatTablo'})
            if not sonuc_tablosu:
                sonuc_tablosu = soup.find('table')
            
            if sonuc_tablosu:
                sonuclar = []
                satirlar = sonuc_tablosu.find_all('tr')[1:]  # İlk satır başlık
                
                for satir in satirlar[:10]:  # En fazla 10 sonuç
                    hucreler = satir.find_all('td')
                    if len(hucreler) >= 2:
                        # Kanun numarasını bul
                        link = satir.find('a', href=True)
                        if link:
                            href = link['href']
                            # URL'den kanun numarasını çıkar
                            match = re.search(r'MevzuatNo=(\d+)', href)
                            if match:
                                kanun_no = match.group(1)
                                kanun_adi = hucreler[1].get_text(strip=True) if len(hucreler) > 1 else link.get_text(strip=True)
                                sonuclar.append({
                                    'numara': kanun_no,
                                    'ad': kanun_adi
                                })
                
                return sonuclar if sonuclar else None
        
        return None
        
    except Exception as e:
        st.error(f"Arama hatası: {str(e)}")
        return None

def kanun_ara_ve_cek(kanun_numarasi):
    """
    mevzuat.gov.tr'den kanun numarasına göre kanun metnini çeker.
    Örnek: kanun_ara_ve_cek("5237") → Türk Ceza Kanunu metni
    """
    try:
        # mevzuat.gov.tr arama URL'si
        arama_url = f"https://www.mevzuat.gov.tr/MevzuatMetin/1.5.{kanun_numarasi}.pdf"
        
        # PDF'i indir
        response = requests.get(arama_url, timeout=10)
        
        if response.status_code == 200 and 'application/pdf' in response.headers.get('Content-Type', ''):
            # PDF içeriğini geçici dosyaya kaydet
            temp_path = f"/tmp/kanun_{kanun_numarasi}.pdf"
            with open(temp_path, 'wb') as f:
                f.write(response.content)
            
            # PDF'den metin çıkar
            with open(temp_path, 'rb') as f:
                reader = PdfReader(f)
                metin = "".join([
                    page.extract_text() for page in reader.pages 
                    if page.extract_text()
                ])
            
            return metin if metin.strip() else None
        else:
            # PDF bulunamadı, HTML sayfasını dene
            html_url = f"https://www.mevzuat.gov.tr/mevzuat?MevzuatNo={kanun_numarasi}&MevzuatTur=1&MevzuatTertip=5"
            response = requests.get(html_url, timeout=10)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Kanun metnini bul
                kanun_metni = soup.find('div', {'id': 'mevzuatContent'})
                if kanun_metni:
                    return kanun_metni.get_text(separator='\n', strip=True)
                
                # Alternatif: tüm metin içeriğini al
                metin = soup.get_text(separator='\n', strip=True)
                # Gereksiz kısımları temizle
                metin = re.sub(r'\n{3,}', '\n\n', metin)
                return metin if len(metin) > 100 else None
            
            return None
            
    except Exception as e:
        st.error(f"Kanun çekilirken hata: {str(e)}")
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

def dilekce_yaz_gercek_ictihatli(analiz_notlari, ictihat_metni, kanun_metni=""):
    """
    Gerçek içtihat metni ve kanun metni varsa oradan alıntı yaparak dilekçe yazar.
    İçtihat/kanun yoksa genel hukuk ilkelerine dayanır, esas numarası uydurmaz.
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
    
    # Kanun metni talimatı
    if kanun_metni.strip():
        kanun_talimati = f"""
        YÜKLENEN KANUN METNİ:
        {kanun_metni[:5000]}  

        KANUN KULLANIM KURALLARI:
        - Dilekçede kanun maddesine atıfta bulunurken yukarıdaki metinden alıntı yap.
        - Madde numaralarını ve içeriğini aynen kullan.
        - Kanun metninde olmayan madde uydurma.
        """
    else:
        kanun_talimati = """
        KANUN KULLANIM KURALLARI:
        - Genel olarak bilinen kanun maddelerine atıfta bulunabilirsin (TCK, TMK, HMK vb.).
        - Ama spesifik madde numarası ve içeriği vermekten kaçın, genel ifadeler kullan.
        """

    prompt = f"""
    Aşağıdaki hukuki analize dayanarak resmi, ağır ve profesyonel bir dava dilekçesi taslağı hazırla.

    {ictihat_talimati}
    
    {kanun_talimati}

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
for key in ['analiz_sonucu', 'dilekce_metni', 'ictihat_metni', 'serbest_sonuc', 'kanun_metni', 'arama_sonuclari']:
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
    
    # 3. Kanun Metni Arama — YENİ
    st.markdown("**3. Kanun Metni Otomatik Çek** *(isteğe bağlı)*")
    st.caption("Kelime veya numara ile mevzuat.gov.tr'den güncel kanun metni indirilir.")
    
    arama_tipi = st.radio(
        "Arama tipi:",
        ["Kelime ile ara", "Numara ile ara"],
        horizontal=True,
        key="arama_tipi"
    )
    
    if arama_tipi == "Kelime ile ara":
        kelime_input = st.text_input(
            "Kelime girin (örn: tazminat, velayet, kamulaştırma)",
            key="kelime_ara",
            placeholder="tazminat"
        )
        
        if st.button("🔍 Kanun Ara", use_container_width=True):
            if kelime_input.strip():
                with st.spinner(f"🔍 '{kelime_input}' araniyor..."):
                    sonuclar = kelime_ile_kanun_ara(kelime_input.strip())
                
                if sonuclar:
                    st.session_state['arama_sonuclari'] = sonuclar
                    st.success(f"✅ {len(sonuclar)} kanun bulundu")
                else:
                    st.error(f"❌ '{kelime_input}' için sonuç bulunamadı")
                    st.session_state['arama_sonuclari'] = []
            else:
                st.warning("Lütfen arama kelimesi girin")
        
        # Arama sonuçlarını göster
        if st.session_state.get('arama_sonuclari'):
            st.markdown("**Sonuçlar:**")
            secilen_kanun = st.selectbox(
                "Kanun seçin:",
                options=[f"{k['numara']} - {k['ad']}" for k in st.session_state['arama_sonuclari']],
                key="secilen_kanun"
            )
            
            if st.button("📜 Seçilen Kanunu Yükle", use_container_width=True):
                # Numara çıkar
                kanun_no = secilen_kanun.split(' - ')[0]
                with st.spinner(f"⚖️ {kanun_no} sayılı kanun çekiliyor..."):
                    kanun_metni = kanun_ara_ve_cek(kanun_no)
                
                if kanun_metni:
                    st.session_state['kanun_metni'] = kanun_metni
                    st.session_state['kanun_no'] = kanun_no
                    st.success(f"✅ {kanun_no} sayılı kanun yüklendi")
                    st.session_state['arama_sonuclari'] = []  # Sonuçları temizle
                    st.rerun()
                else:
                    st.error(f"❌ {kanun_no} sayılı kanun çekilemedi")
    
    else:  # Numara ile ara
        kanun_numarasi_input = st.text_input(
            "Kanun numarasını girin (örn: 5237, 6098)",
            key="kanun_no_input",
            placeholder="5237"
        )
        
        if st.button("📜 Kanun Metnini Çek", use_container_width=True):
            if kanun_numarasi_input.strip():
                with st.spinner(f"⚖️ {kanun_numarasi_input} sayılı kanun çekiliyor..."):
                    kanun_metni = kanun_ara_ve_cek(kanun_numarasi_input.strip())
                
                if kanun_metni:
                    st.session_state['kanun_metni'] = kanun_metni
                    st.session_state['kanun_no'] = kanun_numarasi_input.strip()
                    st.success(f"✅ {kanun_numarasi_input} sayılı kanun yüklendi ({len(kanun_metni)} karakter)")
                else:
                    st.error(f"❌ {kanun_numarasi_input} sayılı kanun bulunamadı")
                    st.session_state['kanun_metni'] = ''
            else:
                st.warning("Lütfen kanun numarası girin")
    
    # Yüklenen kanunu göster
    if st.session_state.get('kanun_metni'):
        st.info(f"📜 {st.session_state.get('kanun_no', '?')} sayılı kanun hazır")

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
                    st.session_state['ictihat_metni'],
                    st.session_state.get('kanun_metni', '')
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

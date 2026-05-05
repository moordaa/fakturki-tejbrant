import streamlit as st
from supabase import create_client, Client
from datetime import datetime
import pandas as pd
import time
import urllib.parse

# --- KONFIGURACJA ---
# Dane znajdziesz w Supabase: Project Settings -> API
URL = "https://hdmptdcuqxqutfgrgmrj.supabase.co"
KEY = "TU_WKLEJ_SWOJ_KLUCZ_API" 

supabase: Client = create_client(URL, KEY)

# Ustawienia strony w przeglądarce
st.set_page_config(page_title="fakturki-tejbrant", page_icon="🧾", layout="wide")

# Inicjalizacja sesji logowania
if 'zalogowany' not in st.session_state:
    st.session_state.zalogowany = False
    st.session_state.uzytkownik = ""
    st.session_state.rola = "użytkownik"

# --- EKRAN LOGOWANIA ---
if not st.session_state.zalogowany:
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.title("🧾 FAKTURKI-TEJBRANT")
        st.caption("Ewidencja wydatków firmowych")
        with st.container(border=True):
            l = st.text_input("Login")
            p = st.text_input("Hasło", type="password")
            if st.button("ZALOGUJ", use_container_width=True, type="primary"):
                # Szukamy użytkownika w tabeli pracownicy (tej samej co w systemie zamówień)
                res = supabase.table("pracownicy").select("*").eq("login", l).eq("haslo", p).execute()
                if res.data:
                    st.session_state.zalogowany = True
                    st.session_state.uzytkownik = l
                    st.session_state.rola = res.data[0].get('rola') or "użytkownik"
                    st.rerun()
                else:
                    st.error("Nieprawidłowe dane logowania!")
else:
    # --- MENU BOCZNE ---
    with st.sidebar:
        st.success(f"Zalogowano: **{st.session_state.uzytkownik}**")
        st.header("fakturki-tejbrant")
        st.divider()
        
        menu = st.radio("WYBIERZ AKCJĘ:", [
            "➕ Dodaj Wydatek", 
            "📂 Moje Wydatki", 
            "📊 Raporty i Księgowość", 
            "📖 Instrukcja"
        ])
        
        st.divider()
        if st.button("🔄 Odśwież dane", use_container_width=True):
            st.rerun()
        if st.button("🚪 Wyloguj", use_container_width=True):
            st.session_state.zalogowany = False
            st.rerun()

    # =========================================================================
    # ZAKŁADKA: DODAWANIE WYDATKU
    # =========================================================================
    if menu == "➕ Dodaj Wydatek":
        st.title("➕ Dodaj nowy zakup")
        
        with st.container(border=True):
            sklep = st.text_input("🏪 Sklep / Dostawca")
            
            # --- Żarty (Easter Eggs) ---
            cp = sklep.strip().lower()
            if cp == "69": st.balloons()
            if cp == "666": st.snow()

            col1, col2, col3 = st.columns(3)
            kwota = col1.number_input("💰 Kwota BRUTTO (zł)", min_value=0.0, step=0.01, format="%.2f")
            data_zak = col2.date_input("📅 Data zakupu", datetime.now())
            rodzaj_doc = col3.selectbox("📄 Dokument", ["Papierowy / Paragon", "KSeF", "E-mail (PDF)"])

            st.divider()
            c1, c2, c3 = st.columns(3)
            typ_sklepu = c1.selectbox("📍 Sklep", ["Stacjonarny", "Internetowy"])
            metoda = c2.selectbox("💳 Jak zapłacono", ["Karta", "Gotówka", "Przelew", "Pro-forma", "Pobranie"])
            status = c3.selectbox("📌 Status", ["Zapłacone", "Pobranie", "Przelew/Proforma", "Rozliczone"])

            st.divider()
            c4, c5, c6 = st.columns(3)
            odbiorca = c4.text_input("👤 Kto odebrał?", value=st.session_state.uzytkownik)
            platnik = c5.text_input("👤 Kto płacił?", value=st.session_state.uzytkownik)
            zrodlo = c6.selectbox("🏧 Źródło kasy", ["Karta firmowa", "Karta prywatna", "Gotówka", "Konto firmowe"])

            projekt = st.text_input("🏗️ Projekt / Cel (np. Budowa Sosnowa)")
            if projekt.lower() == "dla szefa": st.balloons()
            if projekt.lower() in ["fucha", "prywatne"]: st.warning("Uważaj, admin patrzy! 😉")

            uwagi = st.text_area("📝 Dodatkowe uwagi")

            st.divider()
            foto = None
            if st.toggle("📷 Włącz aparat i zrób zdjęcie"):
                foto = st.camera_input("Zrób zdjęcie faktury/paragonu")

            if st.button("ZAPISZ WYDATEK", type="primary", use_container_width=True):
                if sklep and kwota > 0:
                    url_zdj = ""
                    if foto:
                        with st.spinner("Wgrywanie zdjęcia..."):
                            nazwa = f"faktura_{int(time.time())}.jpg"
                            supabase.storage.from_("faktury_zdjecia").upload(nazwa, foto.getvalue(), {"content-type": "image/jpeg"})
                            url_zdj = supabase.storage.from_("faktury_zdjecia").get_public_url(nazwa)

                    miesiac_rok = data_zak.strftime("%Y-%m")

                    supabase.table("wydatki").insert({
                        "sklep": sklep, "kwota": kwota, "data_zakupu": str(data_zak),
                        "rodzaj_dokumentu": rodzaj_doc, "typ_sklepu": typ_sklepu, 
                        "metoda_platnosci": metoda, "status": status,
                        "odbiorca": odbiorca, "platnik": platnik, "zrodlo_srodkow": zrodlo,
                        "uwagi": f"PROJEKT: {projekt} | {uwagi}", "zdjecie_url": url_zdj, 
                        "zgloszone_przez": st.session_state.uzytkownik, "miesiac_rok": miesiac_rok
                    }).execute()
                    
                    st.success("Zapisano pomyślnie w systemie fakturki-tejbrant!")
                    time.sleep(1); st.rerun()
                else:
                    st.error("Sklep i kwota nie mogą być puste!")

    # =========================================================================
    # ZAKŁADKA: LISTA WYDATKÓW
    # =========================================================================
    elif menu == "📂 Moje Wydatki":
        st.title("📂 Historia Twoich zakupów")
        res = supabase.table("wydatki").select("*").eq("zgloszone_przez", st.session_state.uzytkownik).order("data_zakupu", desc=True).execute()
        
        if not res.data:
            st.info("Brak wpisów.")
        else:
            for r in res.data:
                with st.container(border=True):
                    c1, c2, c3 = st.columns([2,1,1])
                    c1.markdown(f"### {r['sklep']}")
                    c1.caption(f"Dokument: {r['rodzaj_dokumentu']} | Źródło: {r['zrodlo_srodkow']}")
                    c2.subheader(f"{r['kwota']} zł")
                    c3.write(f"📅 {r['data_zakupu']}")
                    
                    if r.get('zdjecie_url'):
                        with st.expander("🖼️ Zobacz zdjęcie"):
                            st.image(r['zdjecie_url'], use_container_width=True)
                    
                    if st.button("🗑️ Usuń", key=f"del_{r['id']}"):
                        supabase.table("wydatki").delete().eq("id", r['id']).execute()
                        st.rerun()

    # =========================================================================
    # ZAKŁADKA: RAPORTY (Dla księgowej)
    # =========================================================================
    elif menu == "📊 Raporty i Księgowość":
        st.title("📊 Rozliczenia miesięczne")
        
        res_all = supabase.table("wydatki").select("*").execute()
        if not res_all.data:
            st.info("Brak danych.")
        else:
            df = pd.DataFrame(res_all.data)
            miesiace = sorted(df['miesiac_rok'].unique(), reverse=True)
            sel_m = st.selectbox("📅 Wybierz miesiąc do rozliczenia", miesiace)
            
            df_m = df[df['miesiac_rok'] == sel_m]
            
            col_a, col_b, col_c = st.columns(3)
            col_a.metric("Suma całkowita", f"{df_m['kwota'].sum():.2f} zł")
            
            ksef_sum = df_m[df_m['rodzaj_dokumentu'] == 'KSeF']['kwota'].sum()
            col_b.metric("W tym KSeF", f"{ksef_sum:.2f} zł")
            
            pryw_sum = df_m[df_m['zrodlo_srodkow'] == 'Karta prywatna']['kwota'].sum()
            col_c.metric("Do zwrotu (z pryw. kart)", f"{pryw_sum:.2f} zł")
            
            st.divider()
            st.subheader(f"Szczegółowa lista: {sel_m}")
            st.dataframe(df_m[['data_zakupu', 'sklep', 'kwota', 'rodzaj_dokumentu', 'zrodlo_srodkow', 'status', 'uwagi']], use_container_width=True)
            
            csv = '\ufeff'.encode('utf8') + df_m.to_csv(index=False, sep=';').encode('utf-8')
            st.download_button(
                label=f"📥 Pobierz raport EXCEL (CSV) za {sel_m}",
                data=csv,
                file_name=f"fakturki_tejbrant_{sel_m}.csv",
                mime="text/csv",
                use_container_width=True,
                type="primary"
            )

    # =========================================================================
    # ZAKŁADKA: INSTRUKCJA
    # =========================================================================
    elif menu == "📖 Instrukcja":
        st.title("📖 Pomoc fakturki-tejbrant")
        st.info("Krótka ściąga, jak rozliczać wydatki:")
        st.markdown("""
        1.  **Zrób zdjęcie!** Zdjęcie paragonu lub faktury to podstawa. Nawet jak zgubisz papier, system ma kopię.
        2.  **Oznaczaj KSeF**: Jeśli wiesz, że to faktura KSeF, zaznacz to. Księgowa będzie wiedziała, że nie musi szukać papieru.
        3.  **Karta Prywatna**: Jeśli zapłaciłeś swoją kasą, system podliczy to w raporcie jako kwotę do zwrotu dla Ciebie.
        4.  **Raporty**: Na koniec miesiąca wystarczy pobrać plik CSV i wysłać go do księgowości.
        """)

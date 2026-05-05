import streamlit as st
from supabase import create_client, Client
from datetime import datetime
import pandas as pd
import time
import urllib.parse

# --- KONFIGURACJA ---
URL = "https://hdmptdcuqxqutfgrgmrj.supabase.co"
KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImhkbXB0ZGN1cXhxdXRmZ3JnbXJqIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzY3NzQ2NTksImV4cCI6MjA5MjM1MDY1OX0.ZI18vTCpYloVOdzpZuVHYVH2OwKJMsrQINgaJNl-vho" 

supabase: Client = create_client(URL, KEY)

st.set_page_config(page_title="fakturki-tejbrant", page_icon="🧾", layout="wide")

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
                res = supabase.table("pracownicy").select("*").eq("login", l).eq("haslo", p).execute()
                if res.data:
                    st.session_state.zalogowany = True
                    st.session_state.uzytkownik = l
                    st.session_state.rola = res.data[0].get('rola') or "użytkownik"
                    st.rerun()
                else:
                    st.error("Błędny login lub hasło!")
else:
    # --- MENU BOCZNE ---
    with st.sidebar:
        st.success(f"Zalogowano: **{st.session_state.uzytkownik}**")
        st.header("fakturki-tejbrant")
        st.divider()
        
        # Dynamiczne menu (Zarządzanie kontami tylko dla Admina)
        opcje = ["➕ Dodaj Wydatek", "📂 Moje Wydatki", "📊 Raporty i Księgowość", "📖 Instrukcja"]
        if st.session_state.rola == "admin":
            opcje.insert(3, "👥 Zarządzanie Kontami")
            
        menu = st.radio("WYBIERZ AKCJĘ:", opcje)
        
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
            
            # --- Easter Eggs ---
            cp = sklep.strip().lower()
            if cp == "69": st.balloons()
            if cp == "666": st.snow()

            col1, col2, col3 = st.columns(3)
            kwota = col1.number_input("💰 Kwota BRUTTO (zł)", min_value=0.0, step=0.01, format="%.2f")
            data_zak = col2.date_input("📅 Data zakupu", datetime.now())
            rodzaj_doc = col3.selectbox("📄 Rodzaj dokumentu", ["Papierowy / Paragon", "KSeF", "E-mail (PDF)"])

            st.divider()
            c1, c2, c3 = st.columns(3)
            typ_sklepu = c1.selectbox("📍 Miejsce zakupu", ["Stacjonarny", "Internetowy"])
            metoda = c2.selectbox("💳 Metoda płatności", ["Karta", "Gotówka", "Przelew", "Pro-forma", "Pobranie"])
            status = c3.selectbox("📌 Status płatności", ["Zapłacone", "Pobranie", "Przelew/Proforma", "Rozliczone"])

            st.divider()
            c4, c5, c6 = st.columns(3)
            odbiorca = c4.text_input("👤 Kto odebrał?", value=st.session_state.uzytkownik)
            platnik = c5.text_input("👤 Kto zapłacił?", value=st.session_state.uzytkownik)
            zrodlo = c6.selectbox("🏧 Skąd środki?", ["Karta firmowa", "Karta prywatna", "Gotówka", "Konto firmowe"])

            projekt = st.text_input("🏗️ Projekt / Cel (np. Budowa Sosnowa)")
            if projekt.lower() == "dla szefa": st.balloons()

            uwagi = st.text_area("📝 Dodatkowe uwagi")

            st.divider()
            foto = None
            if st.toggle("📷 Włącz aparat i zrób zdjęcie dokumentu"):
                foto = st.camera_input("Zrób zdjęcie")

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
                    
                    st.success("Zapisano pomyślnie w fakturki-tejbrant!")
                    time.sleep(1); st.rerun()
                else:
                    st.error("Uzupełnij nazwę sklepu i kwotę!")

    # =========================================================================
    # ZAKŁADKA: MOJE WYDATKI
    # =========================================================================
    elif menu == "📂 Moje Wydatki":
        st.title("📂 Twoja historia zakupów")
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
    # ZAKŁADKA: RAPORTY I KSIĘGOWOŚĆ
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
                file_name=f"faktury_tejbrant_{sel_m}.csv",
                mime="text/csv",
                use_container_width=True,
                type="primary"
            )

    # =========================================================================
    # ZAKŁADKA: ZARZĄDZANIE KONTAMI (TYLKO DLA ADMINA)
    # =========================================================================
    elif menu == "👥 Zarządzanie Kontami":
        st.title("👥 Zarządzanie kontami pracowników")
        
        with st.container(border=True):
            st.subheader("➕ Dodaj nowe konto")
            c1, c2, c3 = st.columns(3)
            n_log = c1.text_input("Podaj nowy Login")
            n_has = c2.text_input("Podaj nowe Hasło")
            n_rol = c3.selectbox("Rola w aplikacji", ["użytkownik", "admin"])
            
            if st.button("Utwórz konto", type="primary"):
                if n_log and n_has:
                    supabase.table("pracownicy").insert({"login": n_log, "haslo": n_has, "rola": n_rol}).execute()
                    st.success(f"Dodano użytkownika: {n_log}!")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("Login i hasło nie mogą być puste!")

        st.divider()
        st.subheader("📋 Lista aktywnych kont")
        res_p = supabase.table("pracownicy").select("*").order("login").execute()
        for p in res_p.data:
            with st.container(border=True):
                col_info, col_btn = st.columns([5, 1])
                rola_w = p.get('rola') or "użytkownik"
                col_info.markdown(f"👤 Login: **{p['login']}** | 🔑 Hasło: `{p['haslo']}` | 🛡️ Rola: `{rola_w}`")
                
                # Zabezpieczenie, żeby nie skasować konta "Szef"
                if p['login'].lower() != "szef":
                    if col_btn.button("🗑️ Usuń", key=f"del_user_{p['login']}", type="secondary"):
                        supabase.table("pracownicy").delete().eq("login", p['login']).execute()
                        st.rerun()

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

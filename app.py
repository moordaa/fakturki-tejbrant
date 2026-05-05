import streamlit as st
from supabase import create_client, Client
from datetime import datetime
import pandas as pd
import time
import urllib.parse

# --- KONFIGURACJA ---
URL = "https://hdmptdcuqxqutfgrgmrj.supabase.co"
# Wklejony Twój klucz:
KEY = "sb_publishable_aPIiW1rzHtM3vGcVaUuN-w_R9MadPTt"

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
                # Szukamy użytkownika w tabeli 'fakturki_konta'
                res = supabase.table("fakturki_konta").select("*").eq("login", l).eq("haslo", p).execute()
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
            
            cp = sklep.strip().lower()
            if cp == "69": st.balloons()
            if cp == "666": st.snow()

            col1, col2, col3 = st.columns(3)
            
            # ZMIANA: Możliwość wyboru "?" dla kwoty
            brak_kwoty = col1.checkbox("Brak kwoty (?)")
            kwota = col1.number_input("💰 Kwota BRUTTO (zł)", min_value=0.0, step=0.01, format="%.2f", disabled=brak_kwoty)
            
            brak_daty = col2.checkbox("Brak daty (?)")
            data_zak = col2.date_input("📅 Data zakupu", datetime.now(), disabled=brak_daty)
            
            rodzaj_doc = col3.selectbox("📄 Rodzaj dokumentu", ["Papierowy / Paragon", "KSeF", "E-mail (PDF)", "?"])

            st.divider()
            c1, c2, c3 = st.columns(3)
            typ_sklepu = c1.selectbox("📍 Miejsce zakupu", ["Stacjonarny", "Internetowy"])
            
            metoda = c2.selectbox("💳 Metoda płatności", ["Karta firmowa", "Karta prywatna", "Gotówka", "Pro forma", "Przelew"])
            
            # ZMIANA: Dodano "Przelew" do statusu płatności
            status = c3.selectbox("📌 Status płatności", ["Zapłacone", "Do opłacenia", "Przelew"])

            st.divider()
            c4, c5, c6 = st.columns(3)
            odbiorca = c4.text_input("👤 Kto odebrał?", value=st.session_state.uzytkownik)
            platnik = c5.text_input("👤 Kto zapłacił?", value=st.session_state.uzytkownik)
            zrodlo = c6.selectbox("🏧 Skąd środki?", ["Karta firmowa", "Karta prywatna", "Gotówka", "Konto firmowe"])

            projekt = st.text_input("🏗️ Projekt / Cel (np. Budowa Sosnowa)")
            if projekt.lower() == "dla szefa": st.balloons()

            uwagi = st.text_area("📝 Dodatkowe uwagi")

            st.divider()
            
            st.write("📎 **Dodaj dokument (Opcjonalne)**")
            opcja_dok = st.radio("Wybierz metodę dodania:", ["Brak", "📁 Wgraj plik (PDF lub zdjęcie z dysku)", "📷 Zrób zdjęcie aparatem"], horizontal=True)
            
            plik_upload = None
            foto = None
            
            if opcja_dok == "📁 Wgraj plik (PDF lub zdjęcie z dysku)":
                plik_upload = st.file_uploader("Wybierz plik", type=["png", "jpg", "jpeg", "pdf"])
            elif opcja_dok == "📷 Zrób zdjęcie aparatem":
                foto = st.camera_input("Zrób zdjęcie")

            if st.button("ZAPISZ WYDATEK", type="primary", use_container_width=True):
                if sklep and (brak_kwoty or kwota > 0):
                    url_zdj = ""
                    
                    dok_bytes = None
                    dok_nazwa = ""
                    dok_mime = ""
                    
                    if plik_upload:
                        dok_bytes = plik_upload.getvalue()
                        ext = plik_upload.name.split('.')[-1].lower()
                        dok_nazwa = f"faktura_{int(time.time())}.{ext}"
                        dok_mime = "application/pdf" if ext == "pdf" else f"image/{ext}"
                        if dok_mime == "image/jpg": dok_mime = "image/jpeg"
                    elif foto:
                        dok_bytes = foto.getvalue()
                        dok_nazwa = f"faktura_{int(time.time())}.jpg"
                        dok_mime = "image/jpeg"

                    if dok_bytes:
                        with st.spinner("Wgrywanie dokumentu..."):
                            supabase.storage.from_("faktury_zdjecia").upload(dok_nazwa, dok_bytes, {"content-type": dok_mime})
                            url_zdj = supabase.storage.from_("faktury_zdjecia").get_public_url(dok_nazwa)

                    # Obsługa znaku zapytania dla kwoty i daty
                    kwota_val = "?" if brak_kwoty else kwota
                    
                    if brak_daty:
                        data_zak_str = "?"
                        miesiac_rok = datetime.now().strftime("%Y-%m")
                    else:
                        data_zak_str = str(data_zak)
                        miesiac_rok = data_zak.strftime("%Y-%m")

                    supabase.table("wydatki").insert({
                        "sklep": sklep, "kwota": kwota_val, "data_zakupu": data_zak_str,
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
    # ZAKŁADKA: MOJE WYDATKI / WSZYSTKIE WYDATKI
    # =========================================================================
    elif menu == "📂 Moje Wydatki":
        if st.session_state.rola == "admin":
            st.title("📂 Wszystkie wydatki (Widok Admina)")
            res = supabase.table("wydatki").select("*").order("id", desc=True).execute()
        else:
            st.title("📂 Twoja historia zakupów")
            res = supabase.table("wydatki").select("*").eq("zgloszone_przez", st.session_state.uzytkownik).order("id", desc=True).execute()
        
        if not res.data:
            st.info("Brak wpisów.")
        else:
            for r in res.data:
                rozliczone = (r.get('status') == "Rozliczone z Marzeną ✅")
                
                with st.container(border=True):
                    if rozliczone:
                        st.success("✅ **TRANSAKCJA W PEŁNI ROZLICZONA Z MARZENĄ**")
                        
                    c1, c2, c3 = st.columns([2,1,1])
                    
                    ikonka = "✅ " if rozliczone else "🛒 "
                    c1.markdown(f"### {ikonka}{r['sklep']}")
                    
                    autor = f" | 👤 **Dodał(a): {r['zgloszone_przez']}**" if st.session_state.rola == "admin" else ""
                    c1.caption(f"Dokument: {r['rodzaj_dokumentu']} | Projekt: {r['uwagi'].split('|')[0]}{autor} | Status: **{r['status']}**")
                    
                    c2.subheader(f"{r['kwota']} zł")
                    c3.write(f"📅 {r['data_zakupu']}")
                    
                    if r.get('zdjecie_url'):
                        with st.expander("📎 Zobacz dokument"):
                            url_dok = r['zdjecie_url']
                            if ".pdf" in url_dok.lower():
                                st.markdown(f"**[📄 Kliknij tutaj, aby otworzyć plik PDF]({url_dok})**")
                            else:
                                st.image(url_dok, use_container_width=True)
                    
                    st.divider()
                    col_btn1, col_btn2, col_btn3 = st.columns([1,1,2])
                    
                    if st.session_state.rola == "admin" or r['zgloszone_przez'] == st.session_state.uzytkownik:
                        if col_btn1.button("🗑️ Usuń", key=f"del_{r['id']}"):
                            supabase.table("wydatki").delete().eq("id", r['id']).execute()
                            st.rerun()
                            
                    if not rozliczone:
                        if col_btn2.button("✅ Rozliczone z Marzeną", key=f"rozl_{r['id']}", type="primary"):
                            supabase.table("wydatki").update({"status": "Rozliczone z Marzeną ✅"}).eq("id", r['id']).execute()
                            st.rerun()
                    else:
                        if col_btn2.button("↩️ Cofnij rozliczenie", key=f"cofnij_{r['id']}", type="secondary"):
                            supabase.table("wydatki").update({"status": "Zapłacone"}).eq("id", r['id']).execute()
                            st.rerun()
                            
                    with st.expander("✏️ Edytuj wydatek"):
                        st.caption("Wprowadź zmiany i kliknij Zapisz na dole.")
                        e_col1, e_col2 = st.columns(2)
                        
                        nowy_sklep = e_col1.text_input("Sklep", value=r['sklep'], key=f"e_sklep_{r['id']}")
                        
                        # Edycja kwoty z obsługą znaku zapytania
                        stara_kwota = 0.0 if r['kwota'] == "?" else float(r['kwota'])
                        nowa_kwota_str = e_col2.text_input("Kwota (wpisz liczbę lub '?')", value=str(r['kwota']), key=f"e_kwota_{r['id']}")
                        
                        nowa_data = e_col1.text_input("Data zakupu (lub '?')", value=r['data_zakupu'], key=f"e_data_{r['id']}")
                        
                        def get_index(opcje, wartosc):
                            return opcje.index(wartosc) if wartosc in opcje else 0
                            
                        opcje_zrodlo = ["Karta firmowa", "Karta prywatna", "Gotówka", "Konto firmowe"]
                        nowe_zrodlo = e_col2.selectbox("Skąd środki?", opcje_zrodlo, index=get_index(opcje_zrodlo, r.get('zrodlo_srodkow')), key=f"e_zrodlo_{r['id']}")
                        
                        opcje_metoda = ["Karta firmowa", "Karta prywatna", "Gotówka", "Pro forma", "Przelew"]
                        nowa_metoda = e_col1.selectbox("Metoda płatności", opcje_metoda, index=get_index(opcje_metoda, r.get('metoda_platnosci')), key=f"e_metoda_{r['id']}")
                        
                        opcje_status = ["Zapłacone", "Do opłacenia", "Rozliczone z Marzeną ✅", "Przelew"]
                        nowy_status = e_col2.selectbox("Status", opcje_status, index=get_index(opcje_status, r.get('status')), key=f"e_status_{r['id']}")
                        
                        if st.button("💾 Zapisz zmiany", type="primary", key=f"e_zapisz_{r['id']}"):
                            supabase.table("wydatki").update({
                                "sklep": nowy_sklep,
                                "kwota": nowa_kwota_str,
                                "data_zakupu": nowa_data,
                                "zrodlo_srodkow": nowe_zrodlo,
                                "metoda_platnosci": nowa_metoda,
                                "status": nowy_status
                            }).eq("id", r['id']).execute()
                            st.success("Zaktualizowano pomyślnie!")
                            time.sleep(1)
                            st.rerun()

    # =========================================================================
    # ZAKŁADKA: RAPORTY I KSIĘGOWOŚĆ
    # =========================================================================
    elif menu == "📊 Raporty i Księgowość":
        st.title("📊 Wyszukiwarka i Raporty")
        
        if st.session_state.rola == "admin":
            res_all = supabase.table("wydatki").select("*").execute()
        else:
            res_all = supabase.table("wydatki").select("*").eq("zgloszone_przez", st.session_state.uzytkownik).execute()
            
        if not res_all.data:
            st.info("Brak danych w systemie.")
        else:
            df = pd.DataFrame(res_all.data)
            
            with st.expander("🔍 FILTRY WYSZUKIWANIA", expanded=True):
                st.caption("Wypełnij wybrane pola, aby przefiltrować wyniki. Puste pola są ignorowane.")
                
                c1, c2, c3, c4 = st.columns(4)
                
                dostepne_lata = sorted(list(set([str(d)[:4] for d in df['data_zakupu'] if str(d) != "?" and len(str(d))>=4])), reverse=True)
                f_rok = c1.selectbox("📅 Rok", ["Wszystkie"] + dostepne_lata)
                
                f_miesiac = c2.selectbox("📅 Miesiąc", ["Wszystkie", "01", "02", "03", "04", "05", "06", "07", "08", "09", "10", "11", "12"])
                
                brak_daty_filtr = c3.checkbox("Tylko brak daty (?)")
                f_data = c3.date_input("📅 Dokładna data", value=None, disabled=brak_daty_filtr)
                
                f_kwota = c4.number_input("💰 Kwota (Wyszuka ±30 zł)", min_value=0.0, step=0.01)

                st.divider()
                c5, c6, c7, c8 = st.columns(4)
                
                dostepne_sklepy = sorted(df['sklep'].astype(str).unique().tolist())
                f_sklep = c5.multiselect("🏪 Sklep (Wybierz lub wpisz)", dostepne_sklepy)
                
                dostepni_odbiorcy = sorted(df['odbiorca'].astype(str).unique().tolist())
                f_odbiorca = c6.multiselect("👤 Kto odebrał (Wybierz lub wpisz)", dostepni_odbiorcy)
                
                dostepne_metody = df['metoda_platnosci'].dropna().unique()
                f_metoda = c7.multiselect("💳 Forma płatności", dostepne_metody)
                
                dostepne_statusy = df['status'].dropna().unique()
                f_status = c8.multiselect("📌 Status płatności", dostepne_statusy)

            df_filtered = df.copy()
            
            if f_rok != "Wszystkie":
                df_filtered = df_filtered[df_filtered['data_zakupu'].astype(str).str.startswith(f_rok)]
                
            if f_miesiac != "Wszystkie":
                df_filtered = df_filtered[df_filtered['data_zakupu'].astype(str).str[5:7] == f_miesiac]
                
            if brak_daty_filtr:
                df_filtered = df_filtered[df_filtered['data_zakupu'] == "?"]
            elif f_data is not None:
                df_filtered = df_filtered[df_filtered['data_zakupu'] == str(f_data)]
                
            if f_kwota > 0:
                # Filtracja kwoty z obsługą znaku zapytania
                df_filtered = df_filtered[df_filtered['kwota'] != "?"]
                df_filtered = df_filtered[(df_filtered['kwota'].astype(float) >= f_kwota - 30) & (df_filtered['kwota'].astype(float) <= f_kwota + 30)]
                
            if f_sklep:
                df_filtered = df_filtered[df_filtered['sklep'].isin(f_sklep)]
                
            if f_odbiorca:
                df_filtered = df_filtered[df_filtered['odbiorca'].isin(f_odbiorca)]
                
            if f_metoda:
                df_filtered = df_filtered[df_filtered['metoda_platnosci'].isin(f_metoda)]
                
            if f_status:
                df_filtered = df_filtered[df_filtered['status'].isin(f_status)]

            st.divider()
            st.subheader(f"Znaleziono wpisów: {len(df_filtered)}")
            
            if len(df_filtered) == 0:
                st.warning("Brak wyników dla podanych filtrów wyszukiwania.")
            else:
                m1, m2, m3 = st.columns(3)
                
                # Sumowanie tylko wartości liczbowych
                suma_widoczna = df_filtered[df_filtered['kwota'] != "?"]['kwota'].astype(float).sum()
                m1.metric("Suma całkowita (widoczna)", f"{suma_widoczna:.2f} zł")
                
                ksef_sum = df_filtered[(df_filtered['rodzaj_dokumentu'] == 'KSeF') & (df_filtered['kwota'] != "?")]['kwota'].astype(float).sum()
                m2.metric("W tym KSeF", f"{ksef_sum:.2f} zł")
                
                do_zwrotu_df = df_filtered[
                    (df_filtered['zrodlo_srodkow'].isin(['Karta prywatna', 'Gotówka'])) & 
                    (df_filtered['status'] != 'Rozliczone z Marzeną ✅') &
                    (df_filtered['kwota'] != "?")
                ]
                pryw_sum = do_zwrotu_df['kwota'].astype(float).sum()
                m3.metric("Do zwrotu (Pryw./Gotówka)", f"{pryw_sum:.2f} zł")
                
                kolumny_do_raportu = ['data_zakupu', 'sklep', 'kwota', 'rodzaj_dokumentu', 'metoda_platnosci', 'status', 'odbiorca', 'zgloszone_przez', 'uwagi']
                
                for kol in kolumny_do_raportu:
                    if kol not in df_filtered.columns:
                        df_filtered[kol] = ""
                        
                st.dataframe(df_filtered[kolumny_do_raportu], use_container_width=True)
                
                st.markdown("### 💾 Eksportuj wyniki")
                col_exp1, col_exp2 = st.columns(2)
                
                csv = '\ufeff'.encode('utf8') + df_filtered[kolumny_do_raportu].to_csv(index=False, sep=';').encode('utf-8')
                col_exp1.download_button(
                    label="📊 Pobierz plik EXCEL (CSV)",
                    data=csv,
                    file_name=f"raport_fakturki_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv",
                    use_container_width=True,
                    type="primary"
                )
                
                html_table = df_filtered[kolumny_do_raportu].to_html(index=False)
                html_content = f"""
                <html>
                <head>
                    <meta charset='utf-8'>
                    <style>
                        table {{ border-collapse: collapse; width: 100%; font-family: sans-serif; font-size: 12px; }} 
                        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }} 
                        th {{ background-color: #f2f2f2; }} 
                        h2 {{ font-family: sans-serif; }}
                    </style>
                </head>
                <body>
                    <h2>Raport Wydatków - Fakturki Tejbrant</h2>
                    <p>Wygenerowano: {datetime.now().strftime('%Y-%m-%d %H:%M')}</p>
                    {html_table}
                </body>
                </html>
                """
                
                col_exp2.download_button(
                    label="📄 Pobierz PDF (Do druku)",
                    data=html_content.encode('utf-8'),
                    file_name=f"raport_fakturki_{datetime.now().strftime('%Y%m%d')}.html",
                    mime="text/html",
                    use_container_width=True,
                    help="Pobierz ten plik, otwórz go w przeglądarce, a następnie użyj skrótu Ctrl+P (Drukuj), aby zapisać go jako plik PDF."
                )

    # =========================================================================
    # ZAKŁADKA: ZARZĄDZANIE KONTAMI
    # =========================================================================
    elif menu == "👥 Zarządzanie Kontami":
        st.title("👥 Zarządzanie kontami dla faktur")
        
        with st.container(border=True):
            st.subheader("➕ Dodaj nowe konto")
            c1, c2, c3 = st.columns(3)
            n_log = c1.text_input("Podaj nowy Login")
            n_has = c2.text_input("Podaj nowe Hasło")
            n_rol = c3.selectbox("Rola w aplikacji", ["użytkownik", "admin"])
            
            if st.button("Utwórz konto", type="primary"):
                if n_log and n_has:
                    supabase.table("fakturki_konta").insert({"login": n_log, "haslo": n_has, "rola": n_rol}).execute()
                    st.success(f"Dodano użytkownika: {n_log}!")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("Login i hasło nie mogą być puste!")

        st.divider()
        st.subheader("📋 Lista aktywnych kont")
        res_p = supabase.table("fakturki_konta").select("*").order("login").execute()
        for p in res_p.data:
            with st.container(border=True):
                col_info, col_btn = st.columns([5, 1])
                rola_w = p.get('rola') or "użytkownik"
                col_info.markdown(f"👤 Login: **{p['login']}** | 🔑 Hasło: `{p['haslo']}` | 🛡️ Rola: `{rola_w}`")
                
                # Zabezpieczenie konta Emil
                if p['login'].lower() != "emil":
                    if col_btn.button("🗑️ Usuń", key=f"del_user_{p['login']}", type="secondary"):
                        supabase.table("fakturki_konta").delete().eq("login", p['login']).execute()
                        st.rerun()

    # =========================================================================
    # ZAKŁADKA: INSTRUKCJA
    # =========================================================================
    elif menu == "📖 Instrukcja":
        st.title("📖 Centrum Pomocy: Fakturki-Tejbrant")
        st.markdown("---")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.success("**📷 1. Załączanie dokumentów**\n\nMożesz wgrać zdjęcie paragonu z dysku, zrobić je bezpośrednio telefonem (ikonka aparatu) lub dodać oryginalny plik PDF od dostawcy/sklepu.")
            
            st.info("**🤔 2. Brak daty, kwoty i KSeF**\n\nJeśli paragon jest nieczytelny lub nie znasz ostatecznej sumy, zaznacz 'Brak daty/kwoty (?)'. Z kolei dla e-faktur ustrukturyzowanych wybierz 'KSeF' w rodzaju dokumentu.")

        with col2:
            st.warning("**💸 3. Zwroty pieniędzy**\n\nWyłożyłeś swoje pieniądze? Zaznacz 'Karta prywatna' lub 'Gotówka'. System sam podliczy, ile firma musi Ci oddać, i **automatycznie odejmie** to, co już zostało w pełni rozliczone z Marzeną!")
            
            st.error("**🤝 4. Rozliczenia i Edycja**\n\nW zakładce 'Moje Wydatki' masz pełną kontrolę nad błędami. Użyj opcji '✏️ Edytuj'. Gdy dostaniesz przelew, koniecznie kliknij przycisk '✅ Rozliczone z Marzeną' (zawsze możesz to potem cofnąć).")
            
        st.markdown("---")
        st.markdown("### 📊 Generowanie Raportów")
        st.markdown("> W zakładce **Raporty i Księgowość** znajduje się niesamowita wyszukiwarka! Możesz szukać wydatków po konkretnym sklepie (wystarczy zacząć wpisywać nazwę), a kwoty możesz podawać w przybliżeniu (±30 zł w obie strony). Na koniec jednym kliknięciem pobierasz piękny plik PDF lub Excel dla księgowości. 🚀")

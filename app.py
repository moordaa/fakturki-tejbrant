import streamlit as st
from supabase import create_client, Client
from datetime import datetime, date
import pandas as pd
import time

# --- KONFIGURACJA ---
URL = "https://hdmptdcuqxqutfgrgmrj.supabase.co"
KEY = "sb_publishable_aPIiW1rzHtM3vGcVaUuN-w_R9MadPTt"

supabase: Client = create_client(URL, KEY)

# Ustawienia strony
st.set_page_config(page_title="fakturki-tejbrant", page_icon="🧾", layout="wide")

# --- MECHANIZM SESJI (Poprawka na telefon) ---
# Używamy st.session_state, ale Streamlit w nowszych wersjach lepiej zarządza sesją w chmurze.
if 'zalogowany' not in st.session_state:
    st.session_state.zalogowany = False
    st.session_state.uzytkownik = ""
    st.session_state.rola = "użytkownik"

# --- EKRAN LOGOWANIA ---
if not st.session_state.zalogowany:
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.title("🧾 FAKTURKI-TEJBRANT")
        st.caption("System Ewidencji i Rozliczeń Wydatków")
        with st.container(border=True):
            l = st.text_input("Login", placeholder="twój login")
            p = st.text_input("Hasło", type="password", placeholder="••••••••")
            if st.button("ZALOGUJ DO SYSTEMU", use_container_width=True, type="primary"):
                res = supabase.table("fakturki_konta").select("*").eq("login", l.lower()).eq("haslo", p).execute()
                if res.data:
                    st.session_state.zalogowany = True
                    st.session_state.uzytkownik = res.data[0].get('login')
                    st.session_state.rola = res.data[0].get('rola') or "użytkownik"
                    st.rerun()
                else:
                    st.error("Błędny login lub hasło!")
else:
    # --- MENU BOCZNE ---
    with st.sidebar:
        st.markdown(f"### Zalogowano: `{st.session_state.uzytkownik}`")
        st.caption(f"Rola: {st.session_state.rola.upper()}")
        st.divider()
        opcje = ["➕ Dodaj Wydatek", "📂 Moje Wydatki", "📊 Raporty i Księgowość", "📖 Instrukcja"]
        if st.session_state.rola == "admin": opcje.insert(3, "👥 Zarządzanie Kontami")
        menu = st.radio("NAWIGACJA:", opcje)
        st.divider()
        if st.button("🚪 Wyloguj", use_container_width=True):
            st.session_state.zalogowany = False
            st.rerun()

    # =========================================================================
    # ZAKŁADKA: DODAWANIE WYDATKU
    # =========================================================================
    if menu == "➕ Dodaj Wydatek":
        st.title("➕ Nowy Wydatek")
        with st.container(border=True):
            sklep = st.text_input("🏪 Nazwa Sklepu / Dostawcy", placeholder="np. Allegro, Orlen, Leroy Merlin")
            col1, col2, col3 = st.columns(3)
            
            brak_kwoty = col1.checkbox("Kwota nieznana (?)")
            kwota = col1.number_input("💰 Kwota Brutto (zł)", min_value=0.0, step=0.01, format="%.2f", disabled=brak_kwoty)
            
            brak_daty = col2.checkbox("Data nieznana (?)")
            data_zak = col2.date_input("📅 Data zakupu", date.today(), disabled=brak_daty)
            rodzaj_doc = col3.selectbox("📄 Typ dokumentu", ["Papierowy / Paragon", "Faktura PDF", "KSeF", "E-mail", "Inny / ?"])

            st.divider()
            c1, c2, c3 = st.columns(3)
            metoda = c1.selectbox("💳 Metoda płatności", ["Karta firmowa", "Karta prywatna", "Gotówka", "Przelew", "Pro-forma"])
            status = c2.selectbox("📌 Status", ["Zapłacone", "Do opłacenia", "Czeka na zwrot"])
            zrodlo = c3.selectbox("🏧 Źródło środków", ["Firmowe", "Prywatne"])

            projekt = st.text_input("🏗️ Projekt / Cel zakupu", placeholder="np. Budowa A1, Biuro, Narzędzia")
            uwagi = st.text_area("📝 Dodatkowe informacje")

            st.divider()
            st.write("📎 **Załącznik (Zdjęcie/PDF)**")
            opcja_dok = st.radio("Źródło pliku:", ["Brak", "📁 Wgraj z galerii", "📷 Zrób zdjęcie"], horizontal=True)
            plik_u, foto = None, None
            if opcja_dok == "📁 Wgraj z galerii": plik_u = st.file_uploader("Wybierz plik", type=["png", "jpg", "jpeg", "pdf"])
            elif opcja_dok == "📷 Zrób zdjęcie": foto = st.camera_input("Wykonaj zdjęcie dokumentu")

            if st.button("ZAPISZ WYDATEK", type="primary", use_container_width=True):
                if sklep:
                    url_zdj = ""
                    if plik_u or foto:
                        with st.spinner("Wysyłanie pliku..."):
                            d_bytes = plik_u.getvalue() if plik_u else foto.getvalue()
                            ext = plik_u.name.split('.')[-1].lower() if plik_u else "jpg"
                            d_nazwa = f"faktura_{int(time.time())}.{ext}"
                            supabase.storage.from_("faktury_zdjecia").upload(d_nazwa, d_bytes)
                            url_zdj = supabase.storage.from_("faktury_zdjecia").get_public_url(d_nazwa)

                    try:
                        supabase.table("wydatki").insert({
                            "sklep": sklep, "kwota": 0.0 if brak_kwoty else kwota,
                            "data_zakupu": "?" if brak_daty else str(data_zak),
                            "rodzaj_dokumentu": rodzaj_doc, "metoda_platnosci": metoda, "status": status,
                            "zrodlo_srodkow": zrodlo, "uwagi": f"PROJEKT: {projekt} | {uwagi}",
                            "zdjecie_url": url_zdj, "zgloszone_przez": st.session_state.uzytkownik,
                            "miesiac_rok": datetime.now().strftime("%Y-%m")
                        }).execute()
                        st.success("✅ Wydatek został zarejestrowany!")
                        time.sleep(1); st.rerun()
                    except Exception as e:
                        st.error(f"Błąd bazy: {e}")
                else:
                    st.warning("Podaj nazwę sklepu!")

    # =========================================================================
    # ZAKŁADKA: RAPORTY I WYSZUKIWARKA (POPRAWIONA)
    # =========================================================================
    elif menu == "📊 Raporty i Księgowość":
        st.title("📊 Centrum Raportowania")
        
        # Pobieranie danych
        if st.session_state.rola == "admin":
            res = supabase.table("wydatki").select("*").order("data_zakupu", desc=True).execute()
        else:
            res = supabase.table("wydatki").select("*").eq("zgloszone_przez", st.session_state.uzytkownik).order("data_zakupu", desc=True).execute()
        
        if res.data:
            df = pd.DataFrame(res.data)
            df['kwota'] = df['kwota'].astype(float)
            
            with st.container(border=True):
                st.subheader("🔍 Zaawansowane Filtrowanie")
                f1, f2, f3 = st.columns(3)
                
                # Filtr Pracownika (tylko dla Admina)
                uzytkownicy = sorted(df['zgloszone_przez'].unique().tolist())
                if st.session_state.rola == "admin":
                    f_pracownik = f1.multiselect("👤 Pracownik", ["Wszyscy"] + uzytkownicy, default="Wszyscy")
                else:
                    f_pracownik = [st.session_state.uzytkownik]

                # Zakres dat
                f_zakres = f2.date_input("📅 Zakres dat", [date(2024,1,1), date.today()])
                
                # Metoda płatności
                metody = sorted(df['metoda_platnosci'].unique().tolist())
                f_metoda = f3.multiselect("💳 Metoda płatności", ["Wszystkie"] + metody, default="Wszystkie")

            # Logika filtrowania
            df_f = df.copy()
            if "Wszyscy" not in f_pracownik: df_f = df_f[df_f['zgloszone_przez'].isin(f_pracownik)]
            if "Wszystkie" not in f_metoda: df_f = df_f[df_f['metoda_platnosci'].isin(f_metoda)]
            if len(f_zakres) == 2:
                # Konwersja daty zakupu (obsługa '?')
                df_f = df_f[df_f['data_zakupu'] != '?']
                df_f['temp_date'] = pd.to_datetime(df_f['data_zakupu']).dt.date
                df_f = df_f[(df_f['temp_date'] >= f_zakres[0]) & (df_f['temp_date'] <= f_zakres[1])]

            # Podsumowanie wizualne
            m1, m2, m3 = st.columns(3)
            m1.metric("Suma wybranych", f"{df_f['kwota'].sum():.2f} zł")
            m2.metric("Liczba faktur", len(df_f))
            prywatne = df_f[df_f['zrodlo_srodkow'].str.contains("Prywatne", case=False)]
            m3.metric("Do zwrotu (Pryw.)", f"{prywatne['kwota'].sum():.2f} zł", delta_color="inverse")

            st.dataframe(df_f[['data_zakupu', 'sklep', 'kwota', 'metoda_platnosci', 'status', 'zgloszone_przez']], use_container_width=True)

            # --- GENERATOR ŁADNEGO PDF (HTML) ---
            st.divider()
            st.subheader("📥 Eksport danych")
            
            # Tworzenie stylizowanego HTML
            html_content = f"""
            <html>
            <head>
                <style>
                    body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 40px; color: #333; }}
                    .header {{ text-align: center; border-bottom: 2px solid #1E88E5; padding-bottom: 10px; margin-bottom: 30px; }}
                    table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
                    th {{ background-color: #1E88E5; color: white; padding: 12px; text-align: left; }}
                    td {{ padding: 10px; border-bottom: 1px solid #ddd; font-size: 14px; }}
                    tr:nth-child(even) {{ background-color: #f9f9f9; }}
                    .footer {{ margin-top: 30px; font-size: 12px; text-align: right; color: #777; }}
                    .status-ok {{ color: green; font-weight: bold; }}
                </style>
            </head>
            <body>
                <div class="header">
                    <h1>RAPORT WYDATKÓW FIRMOWYCH</h1>
                    <p>Wygenerowano: {datetime.now().strftime('%Y-%m-%d %H:%M')}</p>
                </div>
                <table>
                    <thead>
                        <tr>
                            <th>Data</th><th>Sklep</th><th>Kwota</th><th>Metoda</th><th>Pracownik</th><th>Status</th>
                        </tr>
                    </thead>
                    <tbody>
            """
            for _, row in df_f.iterrows():
                st_class = 'class="status-ok"' if "✅" in str(row['status']) else ""
                html_content += f"""
                    <tr>
                        <td>{row['data_zakupu']}</td>
                        <td>{row['sklep']}</td>
                        <td>{row['kwota']:.2f} zł</td>
                        <td>{row['metoda_platnosci']}</td>
                        <td>{row['zgloszone_przez']}</td>
                        <td {st_class}>{row['status']}</td>
                    </tr>"""
            
            html_content += f"""
                    </tbody>
                </table>
                <div class="footer">
                    <p>Łączna suma raportu: <b>{df_f['kwota'].sum():.2f} zł</b></p>
                </div>
            </body>
            </html>
            """
            
            c_ex1, c_ex2 = st.columns(2)
            c_ex1.download_button("📄 Pobierz Czytelny Raport (HTML/PDF)", data=html_content.encode('utf-8'), file_name=f"raport_{date.today()}.html", mime="text/html", use_container_width=True)
            
            csv = '\ufeff'.encode('utf8') + df_f.to_csv(index=False, sep=';').encode('utf-8')
            c_ex2.download_button("📊 Pobierz Arkusz EXCEL (CSV)", data=csv, file_name="dane_ksiegowe.csv", use_container_width=True)

    # =========================================================================
    # ZAKŁADKA: MOJE WYDATKI (LISTA I EDYCJA)
    # =========================================================================
    elif menu == "📂 Moje Wydatki":
        st.title("📂 Historia i Edycja")
        # Logika wyświetlania (Admin widzi wszystko, user swoje)
        if st.session_state.rola == "admin":
            res = supabase.table("wydatki").select("*").order("id", desc=True).execute()
        else:
            res = supabase.table("wydatki").select("*").eq("zgloszone_przez", st.session_state.uzytkownik).order("id", desc=True).execute()
        
        if res.data:
            for r in res.data:
                rozl = ("✅" in str(r.get('status')))
                with st.container(border=True):
                    c1, c2, c3 = st.columns([3, 1, 1])
                    c1.subheader(f"{r['sklep']}")
                    c1.caption(f"👤 {r['zgloszone_przez']} | 💳 {r['metoda_platnosci']} | 📄 {r['rodzaj_dokumentu']}")
                    
                    kw_val = "?" if r['kwota'] == 0 else f"{r['kwota']:.2f} zł"
                    c2.markdown(f"### {kw_val}")
                    c3.write(f"📅 {r['data_zakupu']}")
                    
                    if r.get('zdjecie_url'):
                        with st.expander("👁️ Zobacz dokument"):
                            if ".pdf" in r['zdjecie_url'].lower(): st.link_button("Otwórz PDF w nowym oknie", r['zdjecie_url'])
                            else: st.image(r['zdjecie_url'], use_container_width=True)

                    # Przyciski akcji
                    b1, b2, b3 = st.columns(3)
                    if b1.button("🗑️ Usuń", key=f"del_{r['id']}"):
                        supabase.table("wydatki").delete().eq("id", r['id']).execute(); st.rerun()
                    
                    if not rozl:
                        if b2.button("✅ Rozlicz", key=f"ok_{r['id']}", type="primary"):
                            supabase.table("wydatki").update({"status": "Rozliczone z Marzeną ✅"}).eq("id", r['id']).execute(); st.rerun()
                    
                    with b3.expander("✏️ Edytuj"):
                        # Formularz edycji wszystkich pól
                        en_sklep = st.text_input("Sklep", value=r['sklep'], key=f"e1_{r['id']}")
                        en_kwota = st.number_input("Kwota", value=float(r['kwota']), key=f"e2_{r['id']}")
                        en_status = st.selectbox("Status", ["Zapłacone", "Do opłacenia", "Rozliczone z Marzeną ✅"], key=f"e3_{r['id']}")
                        en_uwagi = st.text_area("Projekt / Uwagi", value=r['uwagi'], key=f"e4_{r['id']}")
                        
                        if st.button("Zapisz zmiany", key=f"es_{r['id']}"):
                            supabase.table("wydatki").update({
                                "sklep": en_sklep, "kwota": en_kwota, "status": en_status, "uwagi": en_uwagi
                            }).eq("id", r['id']).execute(); st.rerun()

    # =========================================================================
    # ZAKŁADKA: ZARZĄDZANIE KONTAMI (ADMIN)
    # =========================================================================
    elif menu == "👥 Zarządzanie Kontami":
        st.title("👥 Zarządzanie Dostępem")
        with st.container(border=True):
            st.subheader("➕ Nowy Pracownik")
            cx1, cx2, cx3 = st.columns(3)
            n_l = cx1.text_input("Login")
            n_p = cx2.text_input("Hasło")
            n_r = cx3.selectbox("Rola", ["użytkownik", "admin"])
            if st.button("Dodaj użytkownika", use_container_width=True):
                if n_l and n_p:
                    supabase.table("fakturki_konta").insert({"login": n_l.lower(), "haslo": n_p, "rola": n_r}).execute()
                    st.success("Dodano pracownika!"); time.sleep(1); st.rerun()

        st.divider()
        res_p = supabase.table("fakturki_konta").select("*").order("login").execute()
        for p in res_p.data:
            with st.container(border=True):
                ca, cb = st.columns([4, 1])
                ca.write(f"👤 **{p['login']}** | Hasło: `{p['haslo']}` | Rola: `{p['rola']}`")
                if p['login'] != "emil" and cb.button("Usuń", key=f"dp_{p['login']}"):
                    supabase.table("fakturki_konta").delete().eq("login", p['login']).execute(); st.rerun()

    # =========================================================================
    # ZAKŁADKA: INSTRUKCJA (MERYTORYCZNA I ATRAKCYJNA)
    # =========================================================================
    elif menu == "📖 Instrukcja":
        st.title("📖 Instrukcja Obsługi Systemu")
        
        st.markdown("""
        ### Witaj w systemie ewidencji wydatków firmowych!
        Aplikacja służy do szybkiego zgłaszania zakupów, aby żadna faktura nie zginęła, a zwroty pieniędzy były wypłacane terminowo.
        """)
        
        col_i1, col_i2 = st.columns(2)
        
        with col_i1:
            with st.expander("🚀 **Jak dodać wydatek?**", expanded=True):
                st.write("""
                1. **Wpisz sklep** – np. 'Biedronka', 'Castorama'.
                2. **Podaj kwotę i datę** – jeśli ich nie znasz (np. czekasz na fakturę), zaznacz opcję **'?'**.
                3. **Wybierz metodę płatności** – to kluczowe dla księgowości!
                4. **Zrób zdjęcie** – aparat w telefonie otworzy się automatycznie.
                """)
        
        with col_i2:
            with st.expander("💸 **Zwroty i Rozliczenia**", expanded=True):
                st.write("""
                * Jeśli zapłaciłeś **prywatną kartą lub gotówką**, system automatycznie policzy to jako kwotę do zwrotu dla Ciebie.
                * Gdy otrzymasz zwrot pieniędzy, Admin (lub Ty) oznacza wydatek jako **Rozliczone z Marzeną ✅**.
                * Wydatki rozliczone znikają z licznika 'Do zwrotu'.
                """)

        st.info("💡 **Pro-tip:** Na telefonie nie musisz się wylogowywać. Po prostu zamknij przeglądarkę. Sesja zostanie zachowana do czasu zamknięcia aplikacji.")

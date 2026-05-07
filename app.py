import streamlit as st
from supabase import create_client, Client
from datetime import datetime, date
import pandas as pd
import time

# --- KONFIGURACJA ---
URL = "https://hdmptdcuqxqutfgrgmrj.supabase.co"
KEY = "sb_publishable_aPIiW1rzHtM3vGcVaUuN-w_R9MadPTt"

supabase: Client = create_client(URL, KEY)

st.set_page_config(page_title="fakturki-tejbrant", page_icon="🧾", layout="wide")

# --- TRWAŁOŚĆ SESJI ---
if 'zalogowany' not in st.session_state:
    st.session_state.zalogowany = False
    st.session_state.uzytkownik = ""
    st.session_state.rola = "użytkownik"

# --- EKRAN LOGOWANIA ---
if not st.session_state.zalogowany:
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.title("🧾 FAKTURKI-TEJBRANT")
        st.caption("Ewidencja i Rozliczenia")
        with st.container(border=True):
            l = st.text_input("Login (np. Emil)")
            p = st.text_input("Hasło", type="password")
            if st.button("ZALOGUJ", use_container_width=True, type="primary"):
                # ilike sprawia, że Emil i emil to to samo. Hasło musi się zgadzać idealnie.
                res = supabase.table("fakturki_konta").select("*").ilike("login", l.strip()).eq("haslo", p.strip()).execute()
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
        st.success(f"Użytkownik: **{st.session_state.uzytkownik}**")
        st.divider()
        opcje = ["➕ Dodaj Wydatek", "📂 Moje Wydatki", "📊 Raporty i Księgowość", "📖 Instrukcja"]
        if st.session_state.rola == "admin": opcje.insert(3, "👥 Zarządzanie Kontami")
        menu = st.radio("WYBIERZ AKCJĘ:", opcje)
        st.divider()
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
            col1, col2, col3 = st.columns(3)
            
            brak_kwoty = col1.checkbox("Nie znam kwoty (?)")
            kwota = col1.number_input("💰 Kwota Brutto", min_value=0.0, step=0.01, format="%.2f", disabled=brak_kwoty)
            
            brak_daty = col2.checkbox("Brak daty na dokumencie")
            data_zak = col2.date_input("📅 Data zakupu", date.today(), disabled=brak_daty)
            rodzaj_doc = col3.selectbox("📄 Rodzaj dokumentu", ["Papierowy / Paragon", "KSeF", "E-mail (PDF)", "Faktura PDF", "?"])

            st.divider()
            c1, c2, c3 = st.columns(3)
            typ_sklepu = c1.selectbox("📍 Miejsce", ["Stacjonarny", "Internetowy"])
            metoda = c2.selectbox("💳 Metoda płatności", ["Karta firmowa", "Karta prywatna", "Gotówka", "Pro forma", "Przelew"])
            status = c3.selectbox("📌 Status płatności", ["Zapłacone", "Do opłacenia", "Przelew"])

            st.divider()
            c4, c5, c6 = st.columns(3)
            odbiorca = c4.text_input("👤 Kto odebrał?", value=st.session_state.uzytkownik)
            platnik = c5.text_input("👤 Kto zapłacił?", value=st.session_state.uzytkownik)
            zrodlo = c6.selectbox("🏧 Źródło środków", ["Karta firmowa", "Karta prywatna", "Gotówka", "Konto firmowe"])
            
            projekt = st.text_input("🏗️ Projekt / Cel")
            uwagi = st.text_area("📝 Uwagi dodatkowe")

            st.divider()
            opcja_dok = st.radio("Dodaj dokument:", ["Brak", "📁 Wgraj plik", "📷 Zdjęcie"], horizontal=True)
            plik_u, foto = None, None
            if opcja_dok == "📁 Wgraj plik": plik_u = st.file_uploader("Wybierz plik", type=["png", "jpg", "jpeg", "pdf"])
            elif opcja_dok == "📷 Zdjęcie": foto = st.camera_input("Zrób zdjęcie")

            if st.button("ZAPISZ WYDATEK", type="primary", use_container_width=True):
                if sklep:
                    url_zdj = ""
                    if plik_u or foto:
                        with st.spinner("Wgrywanie dokumentu..."):
                            d_bytes = plik_u.getvalue() if plik_u else foto.getvalue()
                            ext = plik_u.name.split('.')[-1].lower() if plik_u else "jpg"
                            d_nazwa = f"faktura_{int(time.time())}.{ext}"
                            supabase.storage.from_("faktury_zdjecia").upload(d_nazwa, d_bytes)
                            url_zdj = supabase.storage.from_("faktury_zdjecia").get_public_url(d_nazwa)

                    kwota_db = 0.0 if brak_kwoty else kwota
                    data_zak_str = "?" if brak_daty else str(data_zak)
                    miesiac_rok = datetime.now().strftime("%Y-%m") if brak_daty else data_zak.strftime("%Y-%m")

                    try:
                        supabase.table("wydatki").insert({
                            "sklep": sklep, "kwota": kwota_db, "data_zakupu": data_zak_str,
                            "rodzaj_dokumentu": rodzaj_doc, "typ_sklepu": typ_sklepu, 
                            "metoda_platnosci": metoda, "status": status,
                            "odbiorca": odbiorca, "platnik": platnik, "zrodlo_srodkow": zrodlo,
                            "uwagi": f"PROJEKT: {projekt} | {uwagi}", "zdjecie_url": url_zdj, 
                            "zgloszone_przez": st.session_state.uzytkownik, "miesiac_rok": miesiac_rok
                        }).execute()
                        st.success("Wydatek zapisany!"); time.sleep(1); st.rerun()
                    except Exception as e: st.error(f"Błąd: {e}")

    # =========================================================================
    # ZAKŁADKA: MOJE WYDATKI (Z PEŁNĄ EDYCJĄ)
    # =========================================================================
    elif menu == "📂 Moje Wydatki":
        if st.session_state.rola == "admin":
            st.title("📂 Wszystkie wydatki (Widok Admina)")
            res = supabase.table("wydatki").select("*").order("id", desc=True).execute()
        else:
            st.title("📂 Twoja historia zakupów")
            res = supabase.table("wydatki").select("*").eq("zgloszone_przez", st.session_state.uzytkownik).order("id", desc=True).execute()
        
        for r in (res.data or []):
            rozl = ("Rozliczone z Marzeną ✅" in str(r.get('status')))
            with st.container(border=True):
                if rozl: st.success("✅ **ZATWIERDZONE I ROZLICZONE Z MARZENĄ**")
                c1, c2, c3 = st.columns([2,1,1])
                c1.markdown(f"### {'✅ ' if rozl else '🛒 '}{r['sklep']}")
                c1.caption(f"Dodał: {r['zgloszone_przez']} | Metoda: {r['metoda_platnosci']}")
                
                kw_p = "?" if float(r['kwota']) == 0.0 else f"{r['kwota']:.2f} zł"
                c2.subheader(kw_p)
                c3.write(f"📅 {r['data_zakupu']}")
                
                if r.get('zdjecie_url'):
                    with st.expander("🖼️ Zobacz dokument"):
                        if ".pdf" in r['zdjecie_url'].lower(): st.link_button("Otwórz PDF", r['zdjecie_url'])
                        else: st.image(r['zdjecie_url'], use_container_width=True)

                st.divider()
                col_b1, col_b2, col_b3 = st.columns([1,1,2])
                if col_b1.button("🗑️ Usuń", key=f"d_{r['id']}"):
                    supabase.table("wydatki").delete().eq("id", r['id']).execute(); st.rerun()
                if not rozl:
                    if col_b2.button("✅ Rozliczone z Marzeną", key=f"r_{r['id']}", type="primary"):
                        supabase.table("wydatki").update({"status": "Rozliczone z Marzeną ✅"}).eq("id", r['id']).execute(); st.rerun()
                else:
                    if col_b2.button("↩️ Cofnij rozliczenie", key=f"c_{r['id']}"):
                        supabase.table("wydatki").update({"status": "Zapłacone"}).eq("id", r['id']).execute(); st.rerun()
                
                with col_b3.expander("✏️ Edytuj wszystko"):
                    def g_idx(opt, val): return opt.index(val) if val in opt else 0
                    e_s = st.text_input("Sklep", value=r['sklep'], key=f"e_s_{r['id']}")
                    e_k = st.text_input("Kwota (wpisz ? dla braku)", value="?" if float(r['kwota']) == 0.0 else str(r['kwota']), key=f"e_k_{r['id']}")
                    e_d = st.text_input("Data (lub ?)", value=r['data_zakupu'], key=f"e_d_{r['id']}")
                    
                    o_met = ["Karta firmowa", "Karta prywatna", "Gotówka", "Pro forma", "Przelew"]
                    e_met = st.selectbox("Metoda", o_met, index=g_idx(o_met, r['metoda_platnosci']), key=f"e_m_{r['id']}")
                    
                    o_st = ["Zapłacone", "Do opłacenia", "Rozliczone z Marzeną ✅", "Przelew"]
                    e_st = st.selectbox("Status", o_st, index=g_idx(o_st, r['status']), key=f"e_st_{r['id']}")
                    
                    e_u = st.text_area("Uwagi / Projekt", value=r.get('uwagi', ''), key=f"e_u_{r['id']}")
                    
                    if st.button("Zapisz zmiany", key=f"save_{r['id']}", type="primary"):
                        n_kw = 0.0 if e_k == "?" else float(e_k.replace(",", "."))
                        supabase.table("wydatki").update({
                            "sklep": e_s, "kwota": n_kw, "data_zakupu": e_d, 
                            "metoda_platnosci": e_met, "status": e_st, "uwagi": e_u
                        }).eq("id", r['id']).execute(); st.rerun()

    # =========================================================================
    # ZAKŁADKA: RAPORTY (WYSZUKIWARKA + ŁADNY PDF)
    # =========================================================================
    elif menu == "📊 Raporty i Księgowość":
        st.title("📊 Zaawansowane Raporty")
        res = supabase.table("wydatki").select("*").execute()
        if res.data:
            df = pd.DataFrame(res.data)
            df['kwota'] = df['kwota'].astype(float)
            
            with st.expander("🔍 FILTRY WYSZUKIWANIA", expanded=True):
                c1, c2, c3 = st.columns(3)
                # Zakres dat
                f_zakres = c1.date_input("Zakres dat (Od - Do)", [date(2026,1,1), date.today()])
                
                # Pracownicy (tylko admin może filtrować wszystkich)
                pracownicy = sorted(df['zgloszone_przez'].unique().tolist())
                f_prac = c2.multiselect("Faktury pracownika", pracownicy, default=pracownicy)
                
                # Formy płatności
                metody_p = sorted(df['metoda_platnosci'].unique().tolist())
                f_met = c3.multiselect("Forma płatności", metody_p, default=metody_p)
                
                # Kwota ±30
                f_kw = st.number_input("Wyszukaj kwotę (±30 zł)", min_value=0.0)

            # --- Logika filtrowania ---
            df_f = df.copy()
            df_f = df_f[df_f['zgloszone_przez'].isin(f_prac)]
            df_f = df_f[df_f['metoda_platnosci'].isin(f_met)]
            
            if len(f_zakres) == 2:
                # Filtracja daty (bezpieczna obsługa '?')
                df_f = df_f[df_f['data_zakupu'] != '?']
                df_f['temp_date'] = pd.to_datetime(df_f['data_zakupu']).dt.date
                df_f = df_f[(df_f['temp_date'] >= f_zakres[0]) & (df_f['temp_date'] <= f_zakres[1])]
            
            if f_kw > 0:
                df_f = df_f[(df_f['kwota'] >= f_kw - 30) & (df_f['kwota'] <= f_kw + 30)]

            # Metryki
            m1, m2, m3 = st.columns(3)
            m1.metric("Suma wybranych", f"{df_f['kwota'].sum():.2f} zł")
            do_zw = df_f[(df_f['zrodlo_srodkow'].isin(['Karta prywatna', 'Gotówka'])) & (~df_f['status'].str.contains('✅'))]
            m2.metric("Do zwrotu", f"{do_zw['kwota'].sum():.2f} zł")
            m3.metric("Liczba pozycji", len(df_f))
            
            st.dataframe(df_f[['data_zakupu', 'sklep', 'kwota', 'status', 'metoda_platnosci', 'zgloszone_przez']], use_container_width=True)
            
            # --- PROFESJONALNY RAPORT HTML ---
            html = f"""
            <style>
                body {{ font-family: sans-serif; margin: 30px; }}
                .header {{ border-bottom: 3px solid #d32f2f; padding-bottom: 10px; }}
                table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
                th {{ background: #d32f2f; color: white; padding: 10px; text-align: left; }}
                td {{ border-bottom: 1px solid #ddd; padding: 10px; font-size: 13px; }}
                .rozl {{ color: #2e7d32; font-weight: bold; }}
            </style>
            <div class="header"><h1>Raport Wydatków: Fakturki-Tejbrant</h1><p>Wygenerowano: {datetime.now().strftime('%d.%m.%Y %H:%M')}</p></div>
            <table>
                <tr><th>Data</th><th>Dostawca</th><th>Kwota</th><th>Osoba</th><th>Metoda</th><th>Status</th></tr>
                {"".join([f"<tr><td>{r['data_zakupu']}</td><td>{r['sklep']}</td><td>{r['kwota']:.2f} zł</td><td>{r['zgloszone_przez']}</td><td>{r['metoda_platnosci']}</td><td class='{'rozl' if '✅' in str(r['status']) else ''}'>{r['status']}</td></tr>" for _, r in df_f.iterrows()])}
            </table>
            """
            c_ex1, c_ex2 = st.columns(2)
            c_ex1.download_button("📊 Pobierz EXCEL (CSV)", data='\ufeff'.encode('utf8') + df_f.to_csv(index=False, sep=';').encode('utf-8'), file_name="raport.csv", use_container_width=True)
            c_ex2.download_button("📄 Pobierz Raport do druku (PDF/HTML)", data=html.encode('utf-8'), file_name="raport.html", mime="text/html", use_container_width=True)

    # =========================================================================
    # ZAKŁADKA: ZARZĄDZANIE KONTAMI
    # =========================================================================
    elif menu == "👥 Zarządzanie Kontami":
        st.title("👥 Zarządzanie dostępem")
        with st.container(border=True):
            st.subheader("➕ Dodaj pracownika")
            cx1, cx2, cx3 = st.columns(3)
            nl = cx1.text_input("Login")
            np = cx2.text_input("Hasło")
            nr = cx3.selectbox("Rola", ["użytkownik", "admin"])
            if st.button("Zapisz konto", type="primary"):
                supabase.table("fakturki_konta").insert({"login": nl.strip(), "haslo": np.strip(), "rola": nr}).execute()
                st.success("Dodano użytkownika!"); time.sleep(1); st.rerun()

        st.divider()
        res_p = supabase.table("fakturki_konta").select("*").order("login").execute()
        for p in (res_p.data or []):
            with st.container(border=True):
                ca, cb = st.columns([4, 1])
                ca.write(f"👤 **{p['login']}** | Hasło: `{p['haslo']}` | Rola: `{p['rola']}`")
                if p['login'].lower() != "emil":
                    if cb.button("Usuń", key=f"dp_{p['login']}"):
                        supabase.table("fakturki_konta").delete().eq("login", p['login']).execute(); st.rerun()

    # =========================================================================
    # ZAKŁADKA: INSTRUKCJA
    # =========================================================================
    elif menu == "📖 Instrukcja":
        st.title("📖 Instrukcja i Pomoc")
        st.markdown("---")
        st.success("**🚀 Dodawanie:** Wypełnij dane, zrób zdjęcie telefonem i zapisz. Jeśli kwota jest nieczytelna, zaznacz 'Nie znam kwoty (?)'.")
        st.info("**📈 Raporty:** Admin widzi faktury wszystkich osób. Możesz filtrować zakresy dat i pobierać ładne zestawienia do druku.")
        st.warning("**💸 Rozliczenia:** Po otrzymaniu zwrotu od Marzeny, kliknij przycisk 'Rozliczone', aby wyczyścić kwoty 'Do zwrotu'.")

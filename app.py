import streamlit as st
from supabase import create_client, Client
from datetime import datetime, date
import pandas as pd
import time

# --- KONFIGURACJA ---
URL = "https://hdmptdcuqxqutfgrgmrj.supabase.co"
KEY = "sb_publishable_aPIiW1rzHtM3vGcVaUuN-w_R9MadPTt"

supabase: Client = create_client(URL, KEY)

# Konfiguracja strony
st.set_page_config(page_title="fakturki-tejbrant", page_icon="🧾", layout="wide")

# --- ZARZĄDZANIE SESJĄ ---
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
            l = st.text_input("Login", placeholder="np. Emil")
            p = st.text_input("Hasło", type="password", placeholder="••••••••")
            
            if st.button("ZALOGUJ DO SYSTEMU", use_container_width=True, type="primary"):
                # ZMIANA: ilike sprawia, że Emil = emil. Hasło zostaje case-sensitive (bezpieczeństwo)
                res = supabase.table("fakturki_konta").select("*").ilike("login", l.strip()).eq("haslo", p.strip()).execute()
                
                if res.data:
                    st.session_state.zalogowany = True
                    st.session_state.uzytkownik = res.data[0].get('login')
                    st.session_state.rola = res.data[0].get('rola') or "użytkownik"
                    st.rerun()
                else:
                    st.error("Błędny login lub hasło! Sprawdź wielkość liter w haśle.")
else:
    # --- MENU BOCZNE ---
    with st.sidebar:
        st.success(f"Zalogowano: **{st.session_state.uzytkownik}**")
        st.caption(f"Uprawnienia: {st.session_state.rola.upper()}")
        st.divider()
        opcje = ["➕ Dodaj Wydatek", "📂 Moje Wydatki", "📊 Raporty i Księgowość", "📖 Instrukcja"]
        if st.session_state.rola == "admin":
            opcje.insert(3, "👥 Zarządzanie Kontami")
            
        menu = st.radio("MENU:", opcje)
        st.divider()
        if st.button("🚪 Wyloguj", use_container_width=True):
            st.session_state.zalogowany = False
            st.rerun()

    # =========================================================================
    # ZAKŁADKA: DODAWANIE WYDATKU
    # =========================================================================
    if menu == "➕ Dodaj Wydatek":
        st.title("➕ Rejestracja nowego zakupu")
        with st.container(border=True):
            sklep = st.text_input("🏪 Sklep / Dostawca")
            col1, col2, col3 = st.columns(3)
            
            brak_kwoty = col1.checkbox("Nie znam kwoty (?)")
            kwota = col1.number_input("💰 Kwota Brutto", min_value=0.0, step=0.01, format="%.2f", disabled=brak_kwoty)
            
            brak_daty = col2.checkbox("Nie znam daty (?)")
            data_zak = col2.date_input("📅 Data", date.today(), disabled=brak_daty)
            rodzaj_doc = col3.selectbox("📄 Dokument", ["Papierowy / Paragon", "Faktura PDF", "KSeF", "E-mail", "?"])

            st.divider()
            c1, c2, c3 = st.columns(3)
            metoda = c1.selectbox("💳 Metoda płatności", ["Karta firmowa", "Karta prywatna", "Gotówka", "Przelew", "Pro-forma"])
            status = c2.selectbox("📌 Status", ["Zapłacone", "Do opłacenia", "Przelew"])
            zrodlo = c3.selectbox("🏧 Środki", ["Firmowe", "Prywatne"])

            projekt = st.text_input("🏗️ Projekt / Cel")
            uwagi = st.text_area("📝 Uwagi dodatkowe")

            st.divider()
            opcja_dok = st.radio("Załącznik:", ["Brak", "📁 Plik z dysku", "📷 Aparat"], horizontal=True)
            plik_u, foto = None, None
            if opcja_dok == "📁 Plik z dysku": plik_u = st.file_uploader("Wybierz PDF/Foto", type=["png", "jpg", "pdf"])
            elif opcja_dok == "📷 Aparat": foto = st.camera_input("Zrób zdjęcie")

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
                        st.success("✅ Zapisano!"); time.sleep(1); st.rerun()
                    except Exception as e: st.error(f"Błąd zapisu: {e}")

    # =========================================================================
    # ZAKŁADKA: MOJE WYDATKI (PEŁNA EDYCJA WSZYSTKIEGO)
    # =========================================================================
    elif menu == "📂 Moje Wydatki":
        if st.session_state.rola == "admin":
            st.title("📂 Wszystkie Wydatki (Widok Admina)")
            res = supabase.table("wydatki").select("*").order("id", desc=True).execute()
        else:
            st.title("📂 Twoje Wydatki")
            res = supabase.table("wydatki").select("*").eq("zgloszone_przez", st.session_state.uzytkownik).order("id", desc=True).execute()
        
        for r in (res.data or []):
            rozl = ("✅" in str(r.get('status')))
            with st.container(border=True):
                if rozl: st.success("✅ ROZLICZONE Z MARZENĄ")
                c1, c2, c3 = st.columns([2,1,1])
                c1.markdown(f"### {r['sklep']}")
                c1.caption(f"Dodał: {r['zgloszone_przez']} | Projekt: {r['uwagi'].split('|')[0]}")
                kw_p = "?" if float(r['kwota']) == 0.0 else f"{r['kwota']:.2f} zł"
                c2.subheader(kw_p)
                c3.write(f"📅 {r['data_zakupu']}")
                
                b1, b2, b3 = st.columns(3)
                if b1.button("🗑️ Usuń", key=f"d_{r['id']}"):
                    supabase.table("wydatki").delete().eq("id", r['id']).execute(); st.rerun()
                if not rozl and b2.button("✅ Rozlicz", key=f"r_{r['id']}", type="primary"):
                    supabase.table("wydatki").update({"status": "Rozliczone z Marzeną ✅"}).eq("id", r['id']).execute(); st.rerun()
                
                with b3.expander("✏️ Edytuj wszystko"):
                    def g_idx(opt, val): return opt.index(val) if val in opt else 0
                    en_sklep = st.text_input("Sklep", value=r['sklep'], key=f"e1_{r['id']}")
                    en_kwota = st.text_input("Kwota (0 lub ? oznacza brak)", value="?" if float(r['kwota']) == 0.0 else str(r['kwota']), key=f"e2_{r['id']}")
                    en_st = st.selectbox("Status", ["Zapłacone", "Do opłacenia", "Rozliczone z Marzeną ✅"], index=g_idx(["Zapłacone", "Do opłacenia", "Rozliczone z Marzeną ✅"], r['status']), key=f"e3_{r['id']}")
                    if st.button("💾 Zapisz", key=f"es_{r['id']}"):
                        n_kw = 0.0 if en_kwota == "?" else float(en_kwota.replace(",", "."))
                        supabase.table("wydatki").update({"sklep": en_sklep, "kwota": n_kw, "status": en_st}).eq("id", r['id']).execute(); st.rerun()

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
                f1, f2, f3 = st.columns(3)
                f_zakres = f1.date_input("Zakres dat", [date(2026,1,1), date.today()])
                pracownicy = sorted(df['zgloszone_przez'].unique().tolist())
                f_prac = f2.multiselect("Pracownik", pracownicy, default=pracownicy)
                f_kw = f3.number_input("Kwota ±30 zł", min_value=0.0)

            df_f = df[df['zgloszone_przez'].isin(f_prac)]
            if f_kw > 0: df_f = df_f[(df_f['kwota'] >= f_kw - 30) & (df_f['kwota'] <= f_kw + 30)]

            m1, m2 = st.columns(2)
            m1.metric("Suma wybranych", f"{df_f['kwota'].sum():.2f} zł")
            do_zw = df_f[(df_f['zrodlo_srodkow'] == 'Prywatne') & (~df_f['status'].str.contains('✅'))]
            m2.metric("Do zwrotu", f"{do_zw['kwota'].sum():.2f} zł")
            
            st.dataframe(df_f[['data_zakupu', 'sklep', 'kwota', 'status', 'zgloszone_przez']], use_container_width=True)
            
            # STYLIZOWANY RAPORT HTML (DO DRUKU PDF)
            html = f"""
            <style>
                body {{ font-family: sans-serif; color: #333; }}
                table {{ width: 100%; border-collapse: collapse; }}
                th {{ background: #f4f4f4; padding: 10px; border: 1px solid #ddd; }}
                td {{ padding: 10px; border: 1px solid #ddd; }}
                .rozl {{ background: #e8f5e9; }}
            </style>
            <h2>Raport Wydatków Firmowych</h2>
            <p>Wygenerowano: {datetime.now().strftime('%d.%m.%Y %H:%M')}</p>
            <table>
                <tr><th>Data</th><th>Sklep</th><th>Kwota</th><th>Osoba</th><th>Status</th></tr>
                {"".join([f"<tr class='{'rozl' if '✅' in str(row['status']) else ''}'><td>{row['data_zakupu']}</td><td>{row['sklep']}</td><td>{row['kwota']:.2f} zł</td><td>{row['zgloszone_przez']}</td><td>{row['status']}</td></tr>" for _, row in df_f.iterrows()])}
            </table>
            """
            st.download_button("📄 Pobierz Raport do druku (HTML/PDF)", data=html.encode('utf-8'), file_name="raport.html", mime="text/html")

    # =========================================================================
    # ZAKŁADKA: KONTA (ZARZĄDZANIE)
    # =========================================================================
    elif menu == "👥 Zarządzanie Kontami":
        st.title("👥 Pracownicy i Dęstępy")
        with st.container(border=True):
            st.subheader("➕ Dodaj nowe konto")
            cc1, cc2, cc3 = st.columns(3)
            nl = cc1.text_input("Login")
            np = cc2.text_input("Hasło")
            nr = cc3.selectbox("Rola", ["użytkownik", "admin"])
            if st.button("Utwórz konto"):
                supabase.table("fakturki_konta").insert({"login": nl, "haslo": np, "rola": nr}).execute()
                st.success("Dodano!"); time.sleep(1); st.rerun()

        res_p = supabase.table("fakturki_konta").select("*").execute()
        for p in res_p.data:
            with st.container(border=True):
                col_i, col_b = st.columns([4, 1])
                col_i.write(f"👤 **{p['login']}** | Hasło: `{p['haslo']}` | Rola: `{p['rola']}`")
                if p['login'] not in ["Emil", "emil"] and col_b.button("Usuń", key=f"dp_{p['login']}"):
                    supabase.table("fakturki_konta").delete().eq("login", p['login']).execute(); st.rerun()

    # =========================================================================
    # ZAKŁADKA: INSTRUKCJA
    # =========================================================================
    elif menu == "📖 Instrukcja":
        st.title("📖 Pomoc Fakturki-Tejbrant")
        st.info("💡 **Sesja:** Nie musisz się wylogowywać. Po prostu zamknij przeglądarkę.")
        st.markdown("""
        * **Kwota (?):** Znak zapytania zapisuje 0.0 zł, by nie blokować bazy.
        * **Rozliczenia:** Status z zielonym ptaszkiem ✅ odejmuje kwotę z licznika 'Do zwrotu'.
        * **PDF:** Raporty można pobierać w formie ładnej tabeli gotowej do druku.
        """)

import streamlit as st
from supabase import create_client, Client
from datetime import datetime, date
import pandas as pd
import time
import io

# --- KONFIGURACJA ---
URL = "https://hdmptdcuqxqutfgrgmrj.supabase.co"
KEY = "sb_publishable_aPIiW1rzHtM3vGcVaUuN-w_R9MadPTt"

supabase: Client = create_client(URL, KEY)

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
        st.caption("System Ewidencji i Rozliczeń")
        with st.container(border=True):
            l = st.text_input("Login")
            p = st.text_input("Hasło", type="password")
            if st.button("ZALOGUJ", use_container_width=True, type="primary"):
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
        st.success(f"Zalogowano: **{st.session_state.uzytkownik}**")
        st.divider()
        opcje = ["➕ Dodaj Wydatek", "📂 Moje Wydatki", "📊 Raporty i Księgowość", "📖 Instrukcja"]
        if st.session_state.rola == "admin": opcje.insert(3, "👥 Zarządzanie Kontami")
        menu = st.radio("MENU:", opcje)
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
            metoda = c1.selectbox("💳 Metoda płatności", ["Karta firmowa", "Karta prywatna", "Gotówka", "Pro forma", "Przelew"])
            status = c2.selectbox("📌 Status płatności", ["Zapłacone", "Do opłacenia", "Przelew"])
            zrodlo = c3.selectbox("🏧 Źródło środków", ["Karta firmowa", "Karta prywatna", "Gotówka", "Konto firmowe"])
            
            projekt = st.text_input("🏗️ Projekt / Cel")
            uwagi = st.text_area("📝 Dodatkowe uwagi")

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
                    miesiac_rok = datetime.now().strftime("%Y-%m") if brak_daty else str(data_zak)[:7]

                    try:
                        supabase.table("wydatki").insert({
                            "sklep": sklep, "kwota": kwota_db, "data_zakupu": data_zak_str,
                            "rodzaj_dokumentu": rodzaj_doc, "metoda_platnosci": metoda, "status": status,
                            "zrodlo_srodkow": zrodlo, "uwagi": f"PROJEKT: {projekt} | {uwagi}",
                            "zdjecie_url": url_zdj, "zgloszone_przez": st.session_state.uzytkownik,
                            "miesiac_rok": miesiac_rok
                        }).execute()
                        st.success("Wydatek zapisany!"); time.sleep(1); st.rerun()
                    except Exception as e: st.error(f"Błąd: {e}")

    # =========================================================================
    # ZAKŁADKA: MOJE WYDATKI (Z PODGLĄDEM UWAG)
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
                
                # NOWOŚĆ: Podgląd uwag bezpośrednio na karcie
                if r.get('uwagi'):
                    st.markdown(f"**📝 Uwagi/Projekt:** *{r['uwagi']}*")
                
                if r.get('zdjecie_url'):
                    with st.expander("🖼️ Zobacz załącznik"):
                        if ".pdf" in r['zdjecie_url'].lower(): st.link_button("Otwórz PDF", r['zdjecie_url'])
                        else: st.image(r['zdjecie_url'], use_container_width=True)

                st.divider()
                col_b1, col_b2, col_b3 = st.columns([1,1,2])
                if col_b1.button("🗑️ Usuń", key=f"d_{r['id']}"):
                    supabase.table("wydatki").delete().eq("id", r['id']).execute(); st.rerun()
                if not rozl and col_b2.button("✅ Rozliczone z Marzeną", key=f"r_{r['id']}", type="primary"):
                    supabase.table("wydatki").update({"status": "Rozliczone z Marzeną ✅"}).eq("id", r['id']).execute(); st.rerun()
                if rozl and col_b2.button("↩️ Cofnij", key=f"c_{r['id']}"):
                    supabase.table("wydatki").update({"status": "Zapłacone"}).eq("id", r['id']).execute(); st.rerun()
                
                with col_b3.expander("✏️ Edytuj wszystko"):
                    def g_idx(opt, val): return opt.index(val) if val in opt else 0
                    e_s = st.text_input("Sklep", value=r['sklep'], key=f"e_s_{r['id']}")
                    e_k = st.text_input("Kwota (wpisz ? dla braku)", value="?" if float(r['kwota']) == 0.0 else str(r['kwota']), key=f"e_k_{r['id']}")
                    e_d = st.text_input("Data (lub ?)", value=r['data_zakupu'], key=f"e_d_{r['id']}")
                    o_st = ["Zapłacone", "Do opłacenia", "Rozliczone z Marzeną ✅", "Przelew"]
                    e_st = st.selectbox("Status", o_st, index=g_idx(o_st, r['status']), key=f"e_st_{r['id']}")
                    e_u = st.text_area("Uwagi / Projekt", value=r.get('uwagi', ''), key=f"e_u_{r['id']}")
                    if st.button("💾 Zapisz zmiany", key=f"save_{r['id']}", type="primary"):
                        n_kw = 0.0 if e_k == "?" else float(e_k.replace(",", "."))
                        supabase.table("wydatki").update({"sklep": e_s, "kwota": n_kw, "data_zakupu": e_d, "status": e_st, "uwagi": e_u}).eq("id", r['id']).execute(); st.rerun()

    # =========================================================================
    # ZAKŁADKA: RAPORTY (ROZBUDOWANE FILTRY I ŁADNY EXCEL)
    # =========================================================================
    elif menu == "📊 Raporty i Księgowość":
        st.title("📊 Rozbudowana Wyszukiwarka i Raporty")
        res = supabase.table("wydatki").select("*").execute()
        if res.data:
            df = pd.DataFrame(res.data)
            df['kwota'] = df['kwota'].astype(float)
            
            with st.container(border=True):
                st.subheader("🔍 Filtry")
                c1, c2, c3 = st.columns(3)
                
                # 1. Zakres dat
                f_zakres = c1.date_input("📅 Zakres dat", [date(2024,1,1), date.today()])
                
                # 2. Rok i Miesiąc
                lata = sorted(list(set([str(d)[:4] for d in df['data_zakupu'] if len(str(d))>=4])), reverse=True)
                f_rok = c2.selectbox("📅 Rok", ["Wszystkie"] + lata)
                miesiace = ["Wszystkie", "01", "02", "03", "04", "05", "06", "07", "08", "09", "10", "11", "12"]
                f_mies = c3.selectbox("📅 Miesiąc", miesiace)
                
                c4, c5, c6 = st.columns(3)
                # 3. Użytkownik
                pracownicy = sorted(df['zgloszone_przez'].unique().tolist())
                f_prac = c4.multiselect("👤 Użytkownik", pracownicy, default=pracownicy)
                
                # 4. Rodzaj płatności
                metody = sorted(df['metoda_platnosci'].unique().tolist())
                f_met = c5.multiselect("💳 Rodzaj płatności", metody, default=metody)
                
                # 5. Czy rozliczone z Marzeną
                f_rozl = c6.selectbox("🤝 Rozliczone z Marzeną?", ["Wszystkie", "TAK (✅)", "NIE"])

            # --- LOGIKA FILTROWANIA ---
            df_f = df.copy()
            if len(f_zakres) == 2:
                df_f = df_f[df_f['data_zakupu'] != '?']
                df_f['temp_d'] = pd.to_datetime(df_f['data_zakupu']).dt.date
                df_f = df_f[(df_f['temp_d'] >= f_zakres[0]) & (df_f['temp_d'] <= f_zakres[1])]
            
            if f_rok != "Wszystkie": df_f = df_f[df_f['data_zakupu'].str.startswith(f_rok)]
            if f_mies != "Wszystkie": df_f = df_f[df_f['data_zakupu'].str.contains(f"-{f_mies}-")]
            df_f = df_f[df_f['zgloszone_przez'].isin(f_prac)]
            df_f = df_f[df_f['metoda_platnosci'].isin(f_met)]
            
            if f_rozl == "TAK (✅)": df_f = df_f[df_f['status'].str.contains("✅")]
            elif f_rozl == "NIE": df_f = df_f[~df_f['status'].str.contains("✅")]

            st.divider()
            m1, m2 = st.columns(2)
            m1.metric("Suma wybranych", f"{df_f['kwota'].sum():.2f} zł")
            do_zw = df_f[(df_f['zrodlo_srodkow'].isin(['Karta prywatna', 'Gotówka'])) & (~df_f['status'].str.contains('✅'))]
            m2.metric("Do zwrotu (Pryw/Got)", f"{do_zw['kwota'].sum():.2f} zł")
            
            st.dataframe(df_f[['data_zakupu', 'sklep', 'kwota', 'status', 'metoda_platnosci', 'zgloszone_przez', 'uwagi']], use_container_width=True)
            
            # --- ŁADNY EXCEL (.xlsx) ---
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                df_f[['data_zakupu', 'sklep', 'kwota', 'status', 'metoda_platnosci', 'zgloszone_przez', 'uwagi']].to_excel(writer, index=False, sheet_name='Raport')
                workbook = writer.book
                worksheet = writer.sheets['Raport']
                
                # Formatowanie nagłówków
                header_format = workbook.add_format({'bold': True, 'bg_color': '#D7E4BC', 'border': 1})
                for col_num, value in enumerate(df_f[['data_zakupu', 'sklep', 'kwota', 'status', 'metoda_platnosci', 'zgloszone_przez', 'uwagi']].columns.values):
                    worksheet.write(0, col_num, value, header_format)
                worksheet.set_column(0, 6, 18) # Szerokość kolumn
            
            st.divider()
            st.subheader("📥 Pobierz raporty")
            c_ex1, c_ex2 = st.columns(2)
            c_ex1.download_button("📊 Pobierz ŁADNY EXCEL (.xlsx)", data=buffer.getvalue(), file_name=f"raport_{date.today()}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
            
            html = f"<html><style>table{{width:100%;border-collapse:collapse;}}th,td{{border:1px solid #ddd;padding:8px;text-align:left;}}th{{background:#f2f2f2;}}</style><body><h2>Raport Wydatków</h2>{df_f[['data_zakupu', 'sklep', 'kwota', 'status', 'zgloszone_przez', 'uwagi']].to_html(index=False)}</body></html>"
            c_ex2.download_button("📄 Pobierz PDF (HTML)", data=html.encode('utf-8'), file_name="raport.html", mime="text/html", use_container_width=True)

    # =========================================================================
    # ZAKŁADKA: ZARZĄDZANIE KONTAMI
    # =========================================================================
    elif menu == "👥 Zarządzanie Kontami":
        st.title("👥 Zarządzanie użytkownikami")
        with st.container(border=True):
            st.subheader("➕ Dodaj nowe konto")
            cx1, cx2, cx3 = st.columns(3)
            nl, np, nr = cx1.text_input("Login"), cx2.text_input("Hasło"), cx3.selectbox("Rola", ["użytkownik", "admin"])
            if st.button("Zapisz", type="primary"):
                supabase.table("fakturki_konta").insert({"login": nl.strip(), "haslo": np.strip(), "rola": nr}).execute(); st.rerun()

        res_p = supabase.table("fakturki_konta").select("*").execute()
        for p in (res_p.data or []):
            with st.container(border=True):
                ca, cb = st.columns([4, 1])
                ca.write(f"👤 **{p['login']}** | Hasło: `{p['haslo']}` | Rola: `{p['rola']}`")
                if p['login'].lower() != "emil" and cb.button("Usuń", key=f"dp_{p['login']}"):
                    supabase.table("fakturki_konta").delete().eq("login", p['login']).execute(); st.rerun()

    # =========================================================================
    # ZAKŁADKA: INSTRUKCJA
    # =========================================================================
    elif menu == "📖 Instrukcja":
        st.title("📖 Pomoc Fakturki-Tejbrant")
        st.markdown("---")
        st.success("**✅ Rozliczenia:** Każda pozycja oznaczona 'Rozliczone z Marzeną' przestaje być liczona w polu 'Do zwrotu'.")
        st.info("**📈 Excel:** Nowy przycisk pobiera plik XLSX z formatowaniem, który od razu nadaje się do wysłania do księgowości.")
        st.warning("**❓ Puste pola:** Jeśli kwota lub data jest nieczytelna, użyj '?', aby móc zapisać dokument i wrócić do niego później.")

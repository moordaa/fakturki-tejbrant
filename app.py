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
                res = supabase.table("fakturki_konta").select("*").eq("login", l).eq("haslo", p).execute()
                if res.data:
                    st.session_state.zalogowany = True
                    st.session_state.uzytkownik = l
                    st.session_state.rola = res.data[0].get('rola') or "użytkownik"
                    st.rerun()
                else:
                    st.error("Błędny login lub hasło!")
else:
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
            
            brak_kwoty = col1.checkbox("Brak kwoty (?)")
            kwota = col1.number_input("💰 Kwota BRUTTO (zł)", min_value=0.0, step=0.01, format="%.2f", disabled=brak_kwoty)
            
            brak_daty = col2.checkbox("Brak daty (?)")
            data_zak = col2.date_input("📅 Data zakupu", datetime.now(), disabled=brak_daty)
            
            rodzaj_doc = col3.selectbox("📄 Rodzaj dokumentu", ["Papierowy / Paragon", "KSeF", "E-mail (PDF)", "?"])

            st.divider()
            c1, c2, c3 = st.columns(3)
            typ_sklepu = c1.selectbox("📍 Miejsce zakupu", ["Stacjonarny", "Internetowy"])
            metoda = c2.selectbox("💳 Metoda płatności", ["Karta firmowa", "Karta prywatna", "Gotówka", "Pro forma", "Przelew"])
            status = c3.selectbox("📌 Status płatności", ["Zapłacone", "Do opłacenia", "Przelew"])

            st.divider()
            c4, c5, c6 = st.columns(3)
            odbiorca = c4.text_input("👤 Kto odebrał?", value=st.session_state.uzytkownik)
            platnik = c5.text_input("👤 Kto zapłacił?", value=st.session_state.uzytkownik)
            zrodlo = c6.selectbox("🏧 Skąd środki?", ["Karta firmowa", "Karta prywatna", "Gotówka", "Konto firmowe"])

            projekt = st.text_input("🏗️ Projekt / Cel (np. Budowa Sosnowa)")
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
                    elif foto:
                        dok_bytes = foto.getvalue()
                        dok_nazwa = f"faktura_{int(time.time())}.jpg"
                        dok_mime = "image/jpeg"

                    if dok_bytes:
                        with st.spinner("Wgrywanie dokumentu..."):
                            supabase.storage.from_("faktury_zdjecia").upload(dok_nazwa, dok_bytes, {"content-type": dok_mime})
                            url_zdj = supabase.storage.from_("faktury_zdjecia").get_public_url(dok_nazwa)

                    # KLUCZOWA POPRAWKA: Wysyłamy None zamiast "?" dla kolumny liczbowej
                    kwota_db = None if brak_kwoty else kwota
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
                        st.success("Zapisano pomyślnie!")
                        time.sleep(1); st.rerun()
                    except Exception as e:
                        st.error(f"Błąd bazy danych: {e}")
                else:
                    st.error("Uzupełnij nazwę sklepu i kwotę!")

    # =========================================================================
    # ZAKŁADKA: MOJE WYDATKI
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
                    if rozliczone: st.success("✅ **TRANSAKCJA W PEŁNI ROZLICZONA Z MARZENĄ**")
                    c1, c2, c3 = st.columns([2,1,1])
                    c1.markdown(f"### {'✅ ' if rozliczone else '🛒 '}{r['sklep']}")
                    autor = f" | 👤 **Dodał(a): {r['zgloszone_przez']}**" if st.session_state.rola == "admin" else ""
                    c1.caption(f"Dokument: {r['rodzaj_dokumentu']} | Projekt: {r['uwagi'].split('|')[0]}{autor} | Status: **{r['status']}**")
                    
                    # Wyświetlanie kwoty (obsługa None jako ?)
                    kwota_wyswietl = "?" if r['kwota'] is None else f"{r['kwota']}"
                    c2.subheader(f"{kwota_wyswietl} zł")
                    c3.write(f"📅 {r['data_zakupu']}")
                    
                    if r.get('zdjecie_url'):
                        with st.expander("📎 Zobacz dokument"):
                            if ".pdf" in r['zdjecie_url'].lower(): st.markdown(f"**[📄 Otwórz PDF]({r['zdjecie_url']})**")
                            else: st.image(r['zdjecie_url'], use_container_width=True)
                    
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
                        e_col1, e_col2 = st.columns(2)
                        n_sklep = e_col1.text_input("Sklep", value=r['sklep'], key=f"e_s_{r['id']}")
                        
                        # Edycja kwoty:
                        n_kwota_str = e_col2.text_input("Kwota (liczba lub ?)", value="?" if r['kwota'] is None else str(r['kwota']), key=f"e_k_{r['id']}")
                        n_data = e_col1.text_input("Data (lub ?)", value=r['data_zakupu'], key=f"e_d_{r['id']}")
                        
                        def g_idx(opt, val): return opt.index(val) if val in opt else 0
                        
                        o_zr = ["Karta firmowa", "Karta prywatna", "Gotówka", "Konto firmowe"]
                        n_zr = e_col2.selectbox("Skąd środki?", o_zr, index=g_idx(o_zr, r.get('zrodlo_srodkow')), key=f"e_z_{r['id']}")
                        
                        o_met = ["Karta firmowa", "Karta prywatna", "Gotówka", "Pro forma", "Przelew"]
                        n_met = e_col1.selectbox("Metoda?", o_met, index=g_idx(o_met, r.get('metoda_platnosci')), key=f"e_m_{r['id']}")
                        
                        o_st = ["Zapłacone", "Do opłacenia", "Rozliczone z Marzeną ✅", "Przelew"]
                        n_st = e_col2.selectbox("Status", o_st, index=g_idx(o_st, r.get('status')), key=f"e_st_{r['id']}")
                        
                        if st.button("💾 Zapisz", key=f"e_b_{r['id']}", type="primary"):
                            n_kwota_db = None if n_kwota_str == "?" else float(n_kwota_str.replace(",", "."))
                            supabase.table("wydatki").update({
                                "sklep": n_sklep, "kwota": n_kwota_db, "data_zakupu": n_data,
                                "zrodlo_srodkow": n_zr, "metoda_platnosci": n_met, "status": n_st
                            }).eq("id", r['id']).execute()
                            st.rerun()

    # =========================================================================
    # ZAKŁADKA: RAPORTY
    # =========================================================================
    elif menu == "📊 Raporty i Księgowość":
        st.title("📊 Wyszukiwarka i Raporty")
        if st.session_state.rola == "admin": res_all = supabase.table("wydatki").select("*").execute()
        else: res_all = supabase.table("wydatki").select("*").eq("zgloszone_przez", st.session_state.uzytkownik).execute()
            
        if res_all.data:
            df = pd.DataFrame(res_all.data)
            df['kwota'] = df['kwota'].fillna(0).astype(float) # Zamień puste na 0 dla obliczeń
            
            with st.expander("🔍 FILTRY", expanded=True):
                c1, c2, c3, c4 = st.columns(4)
                d_lat = sorted(list(set([str(d)[:4] for d in df['data_zakupu'] if len(str(d))>=4])), reverse=True)
                f_rok = c1.selectbox("Rok", ["Wszystkie"] + d_lat)
                f_mies = c2.selectbox("Miesiąc", ["Wszystkie"] + [f"{i:02d}" for i in range(1,13)])
                f_kw = c4.number_input("Kwota (±30 zł)", min_value=0.0)
                
                d_sk = sorted(df['sklep'].unique().tolist())
                f_sk = st.multiselect("Sklep", d_sk)

            df_f = df.copy()
            if f_rok != "Wszystkie": df_f = df_f[df_f['data_zakupu'].str.startswith(f_rok)]
            if f_mies != "Wszystkie": df_f = df_f[df_f['data_zakupu'].str[5:7] == f_mies]
            if f_kw > 0: df_f = df_f[(df_f['kwota'] >= f_kw - 30) & (df_f['kwota'] <= f_kw + 30)]
            if f_sk: df_f = df_f[df_f['sklep'].isin(f_sk)]

            st.subheader(f"Wyniki: {len(df_f)}")
            m1, m2, m3 = st.columns(3)
            m1.metric("Suma", f"{df_f['kwota'].sum():.2f} zł")
            
            do_zw = df_f[(df_f['zrodlo_srodkow'].isin(['Karta prywatna', 'Gotówka'])) & (df_f['status'] != 'Rozliczone z Marzeną ✅')]
            m3.metric("Do zwrotu", f"{do_zw['kwota'].sum():.2f} zł")
            
            st.dataframe(df_f[['data_zakupu', 'sklep', 'kwota', 'status', 'zgloszone_przez']], use_container_width=True)
            
            csv = '\ufeff'.encode('utf8') + df_f.to_csv(index=False, sep=';').encode('utf-8')
            st.download_button("📊 Pobierz EXCEL", data=csv, file_name="raport.csv", mime="text/csv")

    # =========================================================================
    # ZAKŁADKA: KONTA
    # =========================================================================
    elif menu == "👥 Zarządzanie Kontami":
        st.title("👥 Zarządzanie kontami")
        with st.container(border=True):
            c1, c2, c3 = st.columns(3)
            n_l = c1.text_input("Login")
            n_p = c2.text_input("Hasło")
            n_r = c3.selectbox("Rola", ["użytkownik", "admin"])
            if st.button("Utwórz konto"):
                supabase.table("fakturki_konta").insert({"login": n_l, "haslo": n_p, "rola": n_r}).execute()
                st.rerun()

        res_p = supabase.table("fakturki_konta").select("*").order("login").execute()
        for p in res_p.data:
            with st.container(border=True):
                col_i, col_b = st.columns([5, 1])
                col_i.write(f"👤 **{p['login']}** | Rola: {p['rola']}")
                if p['login'].lower() != "emil":
                    if col_b.button("🗑️", key=f"du_{p['login']}"):
                        supabase.table("fakturki_konta").delete().eq("login", p['login']).execute()
                        st.rerun()

    # =========================================================================
    # ZAKŁADKA: INSTRUKCJA
    # =========================================================================
    elif menu == "📖 Instrukcja":
        st.title("📖 Pomoc Fakturki-Tejbrant")
        st.info("Krótka instrukcja obsługi:")
        st.markdown("""
        * **Kwota i Data (?)**: Jeśli nie znasz wartości, zaznacz znak zapytania. W bazie zostanie to zapisane jako pusta wartość, którą możesz później uzupełnić edycją.
        * **Rozliczone z Marzeną**: Kliknięcie tego przycisku odejmuje kwotę z licznika 'Do zwrotu'.
        * **Wyszukiwarka**: Szukanie kwoty działa w przedziale +/- 30zł od wpisanej sumy.
        """)

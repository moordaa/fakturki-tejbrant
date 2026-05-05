import streamlit as st
from supabase import create_client, Client
from datetime import datetime
import pandas as pd
import time
import urllib.parse

# --- KONFIGURACJA ---
URL = "https://hdmptdcuqxqutfgrgmrj.supabase.co"
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
        if st.session_state.rola == "admin": opcje.insert(3, "👥 Zarządzanie Kontami")
        menu = st.radio("WYBIERZ AKCJĘ:", opcje)
        st.divider()
        if st.button("🔄 Odśwież dane", use_container_width=True): st.rerun()
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
            projekt = st.text_input("🏗️ Projekt / Cel")
            uwagi = st.text_area("📝 Dodatkowe uwagi")

            st.divider()
            st.write("📎 **Dodaj dokument**")
            opcja_dok = st.radio("Metoda:", ["Brak", "📁 Wgraj plik", "📷 Zdjęcie"], horizontal=True)
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
                        st.success("Zapisano pomyślnie!")
                        time.sleep(1); st.rerun()
                    except Exception as e:
                        st.error(f"Błąd bazy danych: {e}")

    # =========================================================================
    # ZAKŁADKA: MOJE WYDATKI
    # =========================================================================
    elif menu == "📂 Moje Wydatki":
        if st.session_state.rola == "admin":
            st.title("📂 Wszystkie wydatki (Admin)")
            res = supabase.table("wydatki").select("*").order("id", desc=True).execute()
        else:
            st.title("📂 Twoja historia")
            res = supabase.table("wydatki").select("*").eq("zgloszone_przez", st.session_state.uzytkownik).order("id", desc=True).execute()
        
        if res.data:
            for r in res.data:
                rozl = (r.get('status') == "Rozliczone z Marzeną ✅")
                with st.container(border=True):
                    if rozl: st.success("✅ **ROZLICZONE Z MARZENĄ**")
                    c1, c2, c3 = st.columns([2,1,1])
                    c1.markdown(f"### {r['sklep']}")
                    kw_pokaz = "?" if r['kwota'] == 0 else f"{r['kwota']}"
                    c2.subheader(f"{kw_pokaz} zł")
                    c3.write(f"📅 {r['data_zakupu']}")
                    
                    if r.get('zdjecie_url'):
                        with st.expander("📎 Zobacz dokument"):
                            if ".pdf" in r['zdjecie_url'].lower(): st.markdown(f"**[📄 Otwórz PDF]({r['zdjecie_url']})**")
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
                            
                    with st.expander("✏️ Edytuj WSZYSTKIE pola"):
                        ee1, ee2 = st.columns(2)
                        n_sklep = ee1.text_input("Sklep", value=r['sklep'], key=f"es_{r['id']}")
                        n_kw_s = ee2.text_input("Kwota (liczba lub ?)", value="?" if r['kwota'] == 0 else str(r['kwota']), key=f"ek_{r['id']}")
                        if st.button("💾 Zapisz", key=f"eb_{r['id']}", type="primary"):
                            n_kw_v = 0.0 if n_kw_s == "?" else float(n_kw_s.replace(",", "."))
                            supabase.table("wydatki").update({"sklep": n_sklep, "kwota": n_kw_v}).eq("id", r['id']).execute(); st.rerun()

    # =========================================================================
    # ZAKŁADKA: RAPORTY
    # =========================================================================
    elif menu == "📊 Raporty i Księgowość":
        st.title("📊 Wyszukiwarka i Raporty")
        res_all = supabase.table("wydatki").select("*").execute()
        if res_all.data:
            df = pd.DataFrame(res_all.data)
            with st.expander("🔍 FILTRY WYSZUKIWANIA", expanded=True):
                c1, c2, c3 = st.columns(3)
                f_kw = c1.number_input("Kwota (±30 zł)", min_value=0.0)
                d_sk = sorted(df['sklep'].astype(str).unique().tolist())
                f_sk = st.multiselect("Sklepy", d_sk)
            
            df_f = df.copy()
            if f_kw > 0: df_f = df_f[(df_f['kwota'].astype(float) >= f_kw - 30) & (df_f['kwota'].astype(float) <= f_kw + 30)]
            if f_sk: df_f = df_f[df_f['sklep'].isin(f_sk)]

            st.metric("Suma", f"{df_f['kwota'].astype(float).sum():.2f} zł")
            st.dataframe(df_f, use_container_width=True)
            csv = '\ufeff'.encode('utf8') + df_f.to_csv(index=False, sep=';').encode('utf-8')
            st.download_button("📊 Pobierz EXCEL (CSV)", data=csv, file_name="raport.csv", mime="text/csv")

    # =========================================================================
    # ZAKŁADKA: ZARZĄDZANIE KONTAMI (POPRAWIONA)
    # =========================================================================
    elif menu == "👥 Zarządzanie Kontami":
        st.title("👥 Zarządzanie kontami użytkowników")
        
        # 1. Formularz dodawania
        with st.container(border=True):
            st.subheader("➕ Dodaj nowe konto")
            cc1, cc2, cc3 = st.columns(3)
            new_log = cc1.text_input("Login (małymi literami)")
            new_pass = cc2.text_input("Hasło")
            new_role = cc3.selectbox("Rola", ["użytkownik", "admin"])
            
            if st.button("Zapisz nowe konto", type="primary"):
                if new_log and new_pass:
                    supabase.table("fakturki_konta").insert({
                        "login": new_log.strip().lower(),
                        "haslo": new_pass.strip(),
                        "rola": new_role
                    }).execute()
                    st.success(f"Dodano konto: {new_log}")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("Uzupełnij login i hasło!")

        st.divider()
        st.subheader("📋 Lista kont w systemie")
        
        # 2. Wyświetlanie listy wszystkich kont
        res_p = supabase.table("fakturki_konta").select("*").order("login").execute()
        
        if res_p.data:
            for p in res_p.data:
                with st.container(border=True):
                    col_info, col_btn = st.columns([4, 1])
                    with col_info:
                        st.markdown(f"👤 Login: **{p['login']}** | 🔑 Hasło: `{p['haslo']}` | 🛡️ Rola: `{p['rola']}`")
                    
                    with col_btn:
                        # Zabezpieczenie: Emil nie może usunąć sam siebie
                        if p['login'].lower() != "emil":
                            if st.button("Usuń", key=f"du_{p['login']}", use_container_width=True):
                                supabase.table("fakturki_konta").delete().eq("login", p['login']).execute()
                                st.rerun()
                        else:
                            st.caption("Konto główne")

    # =========================================================================
    # ZAKŁADKA: INSTRUKCJA
    # =========================================================================
    elif menu == "📖 Instrukcja":
        st.title("📖 Instrukcja")
        st.info("Jako Admin możesz tutaj dodawać i usuwać konta oraz widzieć hasła użytkowników.")

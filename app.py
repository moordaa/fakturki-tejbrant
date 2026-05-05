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
                else:
                    st.error("Uzupełnij nazwę sklepu!")

    # =========================================================================
    # ZAKŁADKA: MOJE WYDATKI (PEŁNA EDYCJA)
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
                        if col_b2.button("↩️ Cofnij", key=f"c_{r['id']}"):
                            supabase.table("wydatki").update({"status": "Zapłacone"}).eq("id", r['id']).execute(); st.rerun()
                            
                    with st.expander("✏️ Edytuj wydatek"):
                        st.caption("Zmień wybrane pola i zapisz.")
                        ee1, ee2 = st.columns(2)
                        
                        n_sklep = ee1.text_input("Sklep", value=r['sklep'], key=f"es_{r['id']}")
                        n_kw_s = ee2.text_input("Kwota (liczba lub ?)", value="?" if r['kwota'] == 0 else str(r['kwota']), key=f"ek_{r['id']}")
                        n_data = ee1.text_input("Data zakupu (lub ?)", value=r['data_zakupu'], key=f"ed_{r['id']}")
                        
                        def g_idx(opt, val): return opt.index(val) if val in opt else 0
                        
                        o_zr = ["Karta firmowa", "Karta prywatna", "Gotówka", "Konto firmowe"]
                        n_zr = ee2.selectbox("Skąd środki?", o_zr, index=g_idx(o_zr, r.get('zrodlo_srodkow')), key=f"ez_{r['id']}")
                        
                        o_met = ["Karta firmowa", "Karta prywatna", "Gotówka", "Pro forma", "Przelew"]
                        n_met = ee1.selectbox("Metoda płatności", o_met, index=g_idx(o_met, r.get('metoda_platnosci')), key=f"em_{r['id']}")
                        
                        o_st = ["Zapłacone", "Do opłacenia", "Rozliczone z Marzeną ✅", "Przelew"]
                        n_st = ee2.selectbox("Status płatności", o_st, index=g_idx(o_st, r.get('status')), key=f"est_{r['id']}")
                        
                        if st.button("💾 Zapisz zmiany", key=f"eb_{r['id']}", type="primary", use_container_width=True):
                            n_kw_v = 0.0 if n_kw_s == "?" else float(n_kw_s.replace(",", "."))
                            supabase.table("wydatki").update({
                                "sklep": n_sklep, 
                                "kwota": n_kw_v, 
                                "data_zakupu": n_data,
                                "zrodlo_srodkow": n_zr,
                                "metoda_platnosci": n_met,
                                "status": n_st
                            }).eq("id", r['id']).execute()
                            st.success("Zaktualizowano!")
                            time.sleep(0.5); st.rerun()

    # =========================================================================
    # ZAKŁADKA: RAPORTY
    # =========================================================================
    elif menu == "📊 Raporty i Księgowość":
        st.title("📊 Raporty")
        res_all = supabase.table("wydatki").select("*").execute()
        if res_all.data:
            df = pd.DataFrame(res_all.data)
            df['kwota'] = df['kwota'].fillna(0).astype(float)
            st.metric("Suma całkowita", f"{df['kwota'].sum():.2f} zł")
            st.dataframe(df[['data_zakupu', 'sklep', 'kwota', 'status', 'zgloszone_przez']], use_container_width=True)
            csv = '\ufeff'.encode('utf8') + df.to_csv(index=False, sep=';').encode('utf-8')
            st.download_button("📊 Pobierz EXCEL", data=csv, file_name="raport.csv")

    # =========================================================================
    # ZAKŁADKA: KONTA
    # =========================================================================
    elif menu == "👥 Zarządzanie Kontami":
        st.title("👥 Zarządzanie kontami")
        res_p = supabase.table("fakturki_konta").select("*").execute()
        for p in res_p.data:
            with st.container(border=True):
                ci, cb = st.columns([5, 1])
                ci.write(f"👤 **{p['login']}** | Rola: {p['rola']}")
                if p['login'].lower() != "emil":
                    if cb.button("🗑️", key=f"du_{p['login']}"):
                        supabase.table("fakturki_konta").delete().eq("login", p['login']).execute(); st.rerun()

    # =========================================================================
    # ZAKŁADKA: INSTRUKCJA
    # =========================================================================
    elif menu == "📖 Instrukcja":
        st.title("📖 Instrukcja")
        st.info("System pozwala na edycję wszystkich pól dokumentu. Znak zapytania w kwocie zapisuje technicznie 0.0 zł.")

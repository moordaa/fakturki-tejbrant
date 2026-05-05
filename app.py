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
                        def g_idx(opt, val): return opt.index(val) if val in opt else 0
                        ee1, ee2 = st.columns(2)
                        n_sklep = ee1.text_input("Sklep", value=r['sklep'], key=f"es_{r['id']}")
                        n_kw_s = ee2.text_input("Kwota (liczba lub ?)", value="?" if r['kwota'] == 0 else str(r['kwota']), key=f"ek_{r['id']}")
                        
                        ee3, ee4, ee5 = st.columns(3)
                        n_data = ee3.text_input("Data (lub ?)", value=r['data_zakupu'], key=f"ed_{r['id']}")
                        o_doc = ["Papierowy / Paragon", "KSeF", "E-mail (PDF)", "?"]
                        n_doc = ee4.selectbox("Rodzaj dok.", o_doc, index=g_idx(o_doc, r.get('rodzaj_dokumentu')), key=f"erd_{r['id']}")
                        o_typ = ["Stacjonarny", "Internetowy"]
                        n_typ = ee5.selectbox("Miejsce", o_typ, index=g_idx(o_typ, r.get('typ_sklepu')), key=f"et_{r['id']}")
                        
                        ee6, ee7, ee8 = st.columns(3)
                        o_met = ["Karta firmowa", "Karta prywatna", "Gotówka", "Pro forma", "Przelew"]
                        n_met = ee6.selectbox("Metoda", o_met, index=g_idx(o_met, r.get('metoda_platnosci')), key=f"em_{r['id']}")
                        o_st = ["Zapłacone", "Do opłacenia", "Rozliczone z Marzeną ✅", "Przelew"]
                        n_st = ee7.selectbox("Status", o_st, index=g_idx(o_st, r.get('status')), key=f"est_{r['id']}")
                        o_zr = ["Karta firmowa", "Karta prywatna", "Gotówka", "Konto firmowe"]
                        n_zr = ee8.selectbox("Źródło", o_zr, index=g_idx(o_zr, r.get('zrodlo_srodkow')), key=f"ez_{r['id']}")

                        n_uwag = st.text_area("Uwagi / Projekt", value=r.get('uwagi', ''), key=f"euw_{r['id']}")
                        
                        if st.button("💾 Zapisz zmiany", key=f"eb_{r['id']}", type="primary"):
                            n_kw_v = 0.0 if n_kw_s == "?" else float(n_kw_s.replace(",", "."))
                            supabase.table("wydatki").update({
                                "sklep": n_sklep, "kwota": n_kw_v, "data_zakupu": n_data,
                                "rodzaj_dokumentu": n_doc, "typ_sklepu": n_typ,
                                "metoda_platnosci": n_met, "status": n_st, "zrodlo_srodkow": n_zr,
                                "uwagi": n_uwag
                            }).eq("id", r['id']).execute(); st.rerun()

    # =========================================================================
    # ZAKŁADKA: RAPORTY (PRZYWRÓCONA WYSZUKIWARKA I PDF)
    # =========================================================================
    elif menu == "📊 Raporty i Księgowość":
        st.title("📊 Wyszukiwarka i Raporty")
        if st.session_state.rola == "admin": res_all = supabase.table("wydatki").select("*").execute()
        else: res_all = supabase.table("wydatki").select("*").eq("zgloszone_przez", st.session_state.uzytkownik).execute()
            
        if res_all.data:
            df = pd.DataFrame(res_all.data)
            
            with st.expander("🔍 FILTRY WYSZUKIWANIA", expanded=True):
                c1, c2, c3, c4 = st.columns(4)
                d_lat = sorted(list(set([str(d)[:4] for d in df['data_zakupu'] if len(str(d))>=4])), reverse=True)
                f_rok = c1.selectbox("Rok", ["Wszystkie"] + d_lat)
                f_mies = c2.selectbox("Miesiąc", ["Wszystkie"] + [f"{i:02d}" for i in range(1,13)])
                f_kw = c4.number_input("Kwota (±30 zł)", min_value=0.0)
                
                d_sk = sorted(df['sklep'].astype(str).unique().tolist())
                f_sk = st.multiselect("Sklepy", d_sk)
                d_st = df['status'].unique().tolist()
                f_st = st.multiselect("Statusy", d_st)

            # Filtrowanie
            df_f = df.copy()
            if f_rok != "Wszystkie": df_f = df_f[df_f['data_zakupu'].str.startswith(f_rok)]
            if f_mies != "Wszystkie": df_f = df_f[df_f['data_zakupu'].str[5:7] == f_mies]
            if f_kw > 0: df_f = df_f[(df_f['kwota'].astype(float) >= f_kw - 30) & (df_f['kwota'].astype(float) <= f_kw + 30)]
            if f_sk: df_f = df_f[df_f['sklep'].isin(f_sk)]
            if f_st: df_f = df_f[df_f['status'].isin(f_st)]

            st.subheader(f"Wyniki: {len(df_f)}")
            m1, m2, m3 = st.columns(3)
            m1.metric("Suma widoczna", f"{df_f['kwota'].astype(float).sum():.2f} zł")
            do_zw = df_f[(df_f['zrodlo_srodkow'].isin(['Karta prywatna', 'Gotówka'])) & (df_f['status'] != 'Rozliczone z Marzeną ✅')]
            m3.metric("Do zwrotu", f"{do_zw['kwota'].astype(float).sum():.2f} zł")
            
            st.dataframe(df_f[['data_zakupu', 'sklep', 'kwota', 'status', 'zgloszone_przez', 'uwagi']], use_container_width=True)
            
            # Eksport
            col_e1, col_e2 = st.columns(2)
            csv = '\ufeff'.encode('utf8') + df_f.to_csv(index=False, sep=';').encode('utf-8')
            col_e1.download_button("📊 Pobierz EXCEL (CSV)", data=csv, file_name="raport.csv", mime="text/csv", use_container_width=True)
            
            # HTML dla PDF
            html = f"<html><body><h2>Raport</h2>{df_f[['data_zakupu', 'sklep', 'kwota', 'status', 'zgloszone_przez']].to_html()}</body></html>"
            col_e2.download_button("📄 Pobierz PDF (Do druku)", data=html.encode('utf-8'), file_name="raport.html", mime="text/html", use_container_width=True)

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
        st.info("System przywrócił pełną wyszukiwarkę w raportach. Kwoty 0.0 traktowane są jako znak zapytania.")

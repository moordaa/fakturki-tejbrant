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
            
            brak_daty = col2.checkbox("Brak daty (?)")
            data_zak = col2.date_input("📅 Data zakupu", date.today(), disabled=brak_daty)
            rodzaj_doc = col3.selectbox("📄 Rodzaj dokumentu", ["Papierowy / Paragon", "KSeF", "E-mail (PDF)", "Faktura PDF", "?"])

            st.divider()
            c1, c2, c3 = st.columns(3)
            metoda = c1.selectbox("💳 Metoda płatności", ["Karta firmowa", "Karta prywatna", "Gotówka", "Pro forma", "Przelew"])
            status = c2.selectbox("📌 Status płatności", ["Zapłacone", "Do opłacenia", "Przelew"])
            zrodlo = c3.selectbox("🏧 Źródło środków", ["Karta firmowa", "Karta prywatna", "Gotówka", "Konto firmowe"])
            
            st.divider()
            c4, c5, c6 = st.columns(3)
            odbiorca = c4.text_input("👤 Kto odebrał?", value=st.session_state.uzytkownik)
            platnik = c5.text_input("👤 Kto zapłacił?", value=st.session_state.uzytkownik)
            typ_sklepu = c6.selectbox("📍 Miejsce zakupu", ["Stacjonarny", "Internetowy"])

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
                            "zrodlo_srodkow": zrodlo, "odbiorca": odbiorca, "platnik": platnik,
                            "typ_sklepu": typ_sklepu, "uwagi": f"PROJEKT: {projekt} | {uwagi}",
                            "zdjecie_url": url_zdj, "zgloszone_przez": st.session_state.uzytkownik,
                            "miesiac_rok": miesiac_rok
                        }).execute()
                        st.success("Wydatek zapisany!"); time.sleep(1); st.rerun()
                    except Exception as e: st.error(f"Błąd zapisu: {e}")

    # =========================================================================
    # ZAKŁADKA: MOJE WYDATKI (Z PODGLĄDEM UWAG I PEŁNĄ EDYCJĄ)
    # =========================================================================
    elif menu == "📂 Moje Wydatki":
        if st.session_state.rola == "admin":
            st.title("📂 Wszystkie wydatki (Admin)")
            res = supabase.table("wydatki").select("*").order("id", desc=True).execute()
        else:
            st.title("📂 Twoja historia")
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
                
                if r.get('uwagi') and r.get('uwagi') != "PROJEKT:  | ":
                    st.markdown(f"**📝 Uwagi/Projekt:** *{r['uwagi']}*")
                
                if r.get('zdjecie_url'):
                    with st.expander("🖼️ Zobacz załącznik"):
                        if ".pdf" in r['zdjecie_url'].lower(): st.link_button("Otwórz PDF", r['zdjecie_url'])
                        else: st.image(r['zdjecie_url'], use_container_width=True)

                st.divider()
                col_b1, col_b2, col_b3 = st.columns([1,1,2])
                if col_b1.button("🗑️ Usuń", key=f"d_{r['id']}"):
                    supabase.table("wydatki").delete().eq("id", r['id']).execute(); st.rerun()
                if not rozl and col_b2.button("✅ Rozlicz z Marzeną", key=f"r_{r['id']}", type="primary"):
                    supabase.table("wydatki").update({"status": "Rozliczone z Marzeną ✅"}).eq("id", r['id']).execute(); st.rerun()
                if rozl and col_b2.button("↩️ Cofnij rozliczenie", key=f"c_{r['id']}"):
                    supabase.table("wydatki").update({"status": "Zapłacone"}).eq("id", r['id']).execute(); st.rerun()
                
                with col_b3.expander("✏️ Edytuj wszystko"):
                    def g_idx(opt, val): return opt.index(val) if val in opt else 0
                    
                    e1, e2 = st.columns(2)
                    e_s = e1.text_input("Sklep", value=r['sklep'], key=f"es_{r['id']}")
                    e_k = e2.text_input("Kwota (wpisz ? dla braku)", value="?" if float(r['kwota']) == 0.0 else str(r['kwota']), key=f"ek_{r['id']}")
                    
                    e3, e4, e5 = st.columns(3)
                    e_d = e3.text_input("Data (lub ?)", value=r['data_zakupu'], key=f"ed_{r['id']}")
                    o_doc = ["Papierowy / Paragon", "KSeF", "E-mail (PDF)", "Faktura PDF", "?"]
                    e_doc = e4.selectbox("Rodzaj dok.", o_doc, index=g_idx(o_doc, r.get('rodzaj_dokumentu')), key=f"er_{r['id']}")
                    o_typ = ["Stacjonarny", "Internetowy"]
                    e_typ = e5.selectbox("Miejsce", o_typ, index=g_idx(o_typ, r.get('typ_sklepu')), key=f"et_{r['id']}")
                    
                    e6, e7, e8 = st.columns(3)
                    o_met = ["Karta firmowa", "Karta prywatna", "Gotówka", "Pro forma", "Przelew"]
                    e_met = e6.selectbox("Metoda", o_met, index=g_idx(o_met, r.get('metoda_platnosci')), key=f"em_{r['id']}")
                    o_st = ["Zapłacone", "Do opłacenia", "Rozliczone z Marzeną ✅", "Przelew"]
                    e_st = e7.selectbox("Status", o_st, index=g_idx(o_st, r.get('status')), key=f"est_{r['id']}")
                    o_zr = ["Karta firmowa", "Karta prywatna", "Gotówka", "Konto firmowe"]
                    e_zr = e8.selectbox("Źródło", o_zr, index=g_idx(o_zr, r.get('zrodlo_srodkow')), key=f"ez_{r['id']}")

                    e9, e10 = st.columns(2)
                    e_odb = e9.text_input("Odbiorca", value=r.get('odbiorca',''), key=f"eo_{r['id']}")
                    e_pla = e10.text_input("Płatnik", value=r.get('platnik',''), key=f"ep_{r['id']}")

                    e_u = st.text_area("Uwagi / Projekt", value=r.get('uwagi', ''), key=f"eu_{r['id']}")
                    
                    if st.button("💾 Zapisz zmiany", key=f"save_{r['id']}", type="primary", use_container_width=True):
                        n_kw = 0.0 if e_k == "?" else float(e_k.replace(",", "."))
                        supabase.table("wydatki").update({
                            "sklep": e_s, "kwota": n_kw, "data_zakupu": e_d,
                            "rodzaj_dokumentu": e_doc, "typ_sklepu": e_typ, "metoda_platnosci": e_met,
                            "status": e_st, "zrodlo_srodkow": e_zr, "odbiorca": e_odb,
                            "platnik": e_pla, "uwagi": e_u
                        }).eq("id", r['id']).execute(); st.rerun()

    # =========================================================================
    # ZAKŁADKA: RAPORTY (PANCERNA WYSZUKIWARKA I LUKSUSOWY EXCEL)
    # =========================================================================
    elif menu == "📊 Raporty i Księgowość":
        st.title("📊 Wyszukiwarka i Raporty")
        res = supabase.table("wydatki").select("*").execute()
        if res.data:
            df = pd.DataFrame(res.data)
            
            df['kwota'] = df['kwota'].fillna(0).astype(float)
            df['data_zakupu'] = df['data_zakupu'].astype(str).fillna("?")
            df['status'] = df['status'].astype(str).fillna("")
            df['zgloszone_przez'] = df['zgloszone_przez'].astype(str).fillna("")
            df['metoda_platnosci'] = df['metoda_platnosci'].astype(str).fillna("")

            with st.expander("🔍 FILTRY WYSZUKIWANIA", expanded=True):
                c1, c2, c3 = st.columns(3)
                
                f_zakres = c1.date_input("📅 Zakres dat", [date(2024,1,1), date.today()])
                lata = sorted(list(set([str(d)[:4] for d in df['data_zakupu'] if len(str(d))>=4 and str(d)[:4].isdigit()])), reverse=True)
                f_rok = c2.selectbox("📅 Rok", ["Wszystkie"] + lata)
                miesiace = ["Wszystkie", "01", "02", "03", "04", "05", "06", "07", "08", "09", "10", "11", "12"]
                f_mies = c3.selectbox("📅 Miesiąc", miesiace)
                
                c4, c5, c6 = st.columns(3)
                pracownicy = sorted(df['zgloszone_przez'].unique().tolist())
                f_prac = c4.multiselect("👤 Użytkownik", pracownicy, default=pracownicy)
                metody = sorted(df['metoda_platnosci'].unique().tolist())
                f_met = c5.multiselect("💳 Rodzaj płatności", metody, default=metody)
                f_rozl = c6.selectbox("🤝 Rozliczone z Marzeną?", ["Wszystkie", "TAK (✅)", "NIE"])
                
                f_kwota = st.number_input("💰 Szukaj kwoty (±30 zł)", min_value=0.0)

            # --- LOGIKA FILTROWANIA ---
            df_f = df.copy()
            if len(f_zakres) == 2:
                df_f = df_f[df_f['data_zakupu'] != '?']
                df_f['temp_d'] = pd.to_datetime(df_f['data_zakupu'], errors='coerce').dt.date
                df_f = df_f.dropna(subset=['temp_d'])
                df_f = df_f[(df_f['temp_d'] >= f_zakres[0]) & (df_f['temp_d'] <= f_zakres[1])]
            
            if f_rok != "Wszystkie": df_f = df_f[df_f['data_zakupu'].str.startswith(f_rok, na=False)]
            if f_mies != "Wszystkie": df_f = df_f[df_f['data_zakupu'].str.contains(f"-{f_mies}-", na=False)]
            
            df_f = df_f[df_f['zgloszone_przez'].isin(f_prac)]
            df_f = df_f[df_f['metoda_platnosci'].isin(f_met)]
            
            if f_rozl == "TAK (✅)": df_f = df_f[df_f['status'].str.contains("✅", na=False)]
            elif f_rozl == "NIE": df_f = df_f[~df_f['status'].str.contains("✅", na=False)]
            
            if f_kwota > 0:
                df_f = df_f[(df_f['kwota'] >= f_kwota - 30) & (df_f['kwota'] <= f_kwota + 30)]

            st.divider()
            m1, m2 = st.columns(2)
            m1.metric("Suma wybranych", f"{df_f['kwota'].sum():.2f} zł")
            do_zw = df_f[(df_f['zrodlo_srodkow'].isin(['Karta prywatna', 'Gotówka'])) & (~df_f['status'].str.contains('✅', na=False))]
            m2.metric("Do zwrotu (Pryw/Got)", f"{do_zw['kw

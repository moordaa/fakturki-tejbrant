import os
import urllib.request
import streamlit as st
from supabase import create_client, Client
from datetime import datetime, date
import pandas as pd
import time
import io
import uuid
import hashlib
from fpdf import FPDF

# ============================================================
# FAKTURKI-TEJBRANT
# Poprawka 2:
# - podpowiedzi z bazy dla sklepu, odbiorcy, platnika i projektu
# - status platnosci: dodano "Zwrot"
# - ograniczono przypadkowe wylogowania przez zapis danych sesji
# - hasla nowych kont zapisywane jako hash SHA-256
# - stare hasla tekstowe nadal dzialaja i po zalogowaniu sa automatycznie zamieniane na hash
# - admin nie widzi juz hasel uzytkownikow
# ============================================================

# --- KONFIGURACJA ---
URL = st.secrets["SUPABASE_URL"]
KEY = st.secrets["SUPABASE_KEY"]

supabase: Client = create_client(URL, KEY)

st.set_page_config(page_title="fakturki-tejbrant", page_icon="🧾", layout="wide")

# ============================================================
# FUNKCJE POMOCNICZE
# ============================================================

def hash_hasla(haslo: str) -> str:
    """Zamienia haslo na hash SHA-256."""
    return hashlib.sha256(haslo.encode("utf-8")).hexdigest()


def czy_hash_sha256(wartosc: str) -> bool:
    """Sprawdza, czy tekst wyglada jak hash SHA-256."""
    if not wartosc:
        return False
    return len(wartosc) == 64 and all(c in "0123456789abcdef" for c in wartosc.lower())


def sprawdz_logowanie(login: str, haslo: str):
    """
    Logowanie kompatybilne ze starymi kontami.
    Jesli konto ma stare haslo tekstowe, po poprawnym logowaniu zmienia je na hash.
    """
    login = login.strip()
    haslo = haslo.strip()

    if not login or not haslo:
        return None

    res = supabase.table("fakturki_konta").select("*").ilike("login", login).execute()
    if not res.data:
        return None

    konto = res.data[0]
    zapisane_haslo = str(konto.get("haslo") or "")
    hash_wpisanego = hash_hasla(haslo)

    # Nowy sposob: porownanie hashy
    if czy_hash_sha256(zapisane_haslo) and zapisane_haslo == hash_wpisanego:
        return konto

    # Stary sposob: haslo bylo zapisane jako zwykly tekst
    if not czy_hash_sha256(zapisane_haslo) and zapisane_haslo == haslo:
        try:
            supabase.table("fakturki_konta").update({"haslo": hash_wpisanego}).eq("login", konto.get("login")).execute()
        except Exception:
            pass
        return konto

    return None


def g_idx(opt, val):
    return opt.index(val) if val in opt else 0


def bezpieczna_lista_unikalnych(dane, kolumna):
    """Zwraca posortowana liste unikalnych, niepustych wartosci z wyniku Supabase."""
    wartosci = []
    for x in dane or []:
        v = x.get(kolumna)
        if v is not None and str(v).strip():
            wartosci.append(str(v).strip())
    return sorted(list(set(wartosci)), key=lambda x: x.lower())


def wyciagnij_projekt_z_uwag(tekst):
    """Wyciaga projekt z pola uwagi w formacie: PROJEKT: xxx | yyy."""
    tekst = str(tekst or "")
    if tekst.startswith("PROJEKT:") and "|" in tekst:
        return tekst.split("|", 1)[0].replace("PROJEKT:", "").strip()
    return ""


def wyciagnij_uwagi_bez_projektu(tekst):
    """Zwraca sama czesc uwag bez prefixu PROJEKT."""
    tekst = str(tekst or "")
    if tekst.startswith("PROJEKT:") and "|" in tekst:
        return tekst.split("|", 1)[1].strip()
    return tekst


@st.cache_data(ttl=300)
def pobierz_podpowiedzi():
    """
    Pobiera podpowiedzi z istniejacych wydatkow.
    ttl=300 oznacza odswiezenie cache co 5 minut.
    """
    try:
        res = supabase.table("wydatki").select("sklep, odbiorca, platnik, uwagi").execute()
        dane = res.data or []
        sklepy = bezpieczna_lista_unikalnych(dane, "sklep")
        odbiorcy = bezpieczna_lista_unikalnych(dane, "odbiorca")
        platnicy = bezpieczna_lista_unikalnych(dane, "platnik")

        projekty = []
        for x in dane:
            p = wyciagnij_projekt_z_uwag(x.get("uwagi"))
            if p:
                projekty.append(p)
        projekty = sorted(list(set(projekty)), key=lambda x: x.lower())

        return sklepy, odbiorcy, platnicy, projekty
    except Exception:
        return [], [], [], []


def pole_z_podpowiedziami(label, opcje, key, value="", placeholder=""):
    """
    Jedno pole z podpowiedziami.
    Dziala tak:
    - mozna wybrac wartosc z listy,
    - mozna zaczac pisac pierwsze litery, zeby filtrowac liste,
    - mozna wpisac calkiem nowa wartosc bez drugiego pola.
    """
    opcje = sorted(list(set([str(x).strip() for x in opcje if str(x).strip()])), key=lambda x: x.lower())

    if value and str(value).strip() and value not in opcje:
        opcje.insert(0, value)

    # Streamlit w nowszych wersjach obsluguje accept_new_options=True.
    # Dzieki temu jedno pole dziala jak lista + wpisywanie nowej wartosci.
    try:
        return st.selectbox(
            label,
            options=opcje,
            index=opcje.index(value) if value in opcje else None,
            key=key,
            placeholder=placeholder or "Wybierz albo wpisz nowa wartosc",
            accept_new_options=True
        )
    except TypeError:
        # Awaryjnie, gdy Streamlit na serwerze jest starszy i nie zna accept_new_options.
        return st.text_input(label, value=value, key=key, placeholder=placeholder)


def zapisz_sesje(login, rola):
    """
    Zapisuje podstawowe dane w session_state i query params.
    To pomaga ograniczyc wylogowanie przy zwyklym odswiezeniu strony.
    Uwaga: to nie jest pelne logowanie bankowe, ale dla prostej aplikacji firmowej poprawia wygode.
    """
    st.session_state.zalogowany = True
    st.session_state.uzytkownik = login
    st.session_state.rola = rola or "uzytkownik"
    try:
        st.query_params["login"] = login
        st.query_params["rola"] = rola or "uzytkownik"
    except Exception:
        pass


def wyczysc_sesje():
    st.session_state.zalogowany = False
    st.session_state.uzytkownik = ""
    st.session_state.rola = "uzytkownik"
    try:
        st.query_params.clear()
    except Exception:
        pass


# ============================================================
# ZARZADZANIE SESJA
# ============================================================
if 'zalogowany' not in st.session_state:
    st.session_state.zalogowany = False
    st.session_state.uzytkownik = ""
    st.session_state.rola = "uzytkownik"

# Proba przywrocenia sesji po odswiezeniu strony
try:
    if not st.session_state.zalogowany:
        qp_login = st.query_params.get("login", "")
        qp_rola = st.query_params.get("rola", "uzytkownik")
        if qp_login:
            st.session_state.zalogowany = True
            st.session_state.uzytkownik = qp_login
            st.session_state.rola = qp_rola
except Exception:
    pass

# ============================================================
# EKRAN LOGOWANIA
# ============================================================
if not st.session_state.zalogowany:
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.title("🧾 FAKTURKI-TEJBRANT")
        st.caption("System Ewidencji i Rozliczen")
        with st.container(border=True):
            l = st.text_input("Login")
            p = st.text_input("Haslo", type="password")
            if st.button("ZALOGUJ", use_container_width=True, type="primary"):
                konto = sprawdz_logowanie(l, p)
                if konto:
                    zapisz_sesje(konto.get('login'), konto.get('rola') or "uzytkownik")
                    st.rerun()
                else:
                    st.error("Bledny login lub haslo!")
else:
    # ============================================================
    # MENU BOCZNE
    # ============================================================
    with st.sidebar:
        st.markdown("## 🧾 Fakturki")
        st.success(f"Zalogowano: **{st.session_state.uzytkownik}**")
        st.divider()
        opcje = ["➕ Dodaj Wydatek", "📂 Moje Wydatki", "📊 Raporty i Księgowość", "📖 Instrukcja"]
        if st.session_state.rola == "admin":
            opcje.insert(3, "👥 Zarządzanie Kontami")
        menu = st.radio("MENU:", opcje)
        st.divider()
        if st.button("🚪 Wyloguj", use_container_width=True):
            wyczysc_sesje()
            st.rerun()

    # Pobranie podpowiedzi z bazy
    sklepy_podpowiedzi, odbiorcy_podpowiedzi, platnicy_podpowiedzi, projekty_podpowiedzi = pobierz_podpowiedzi()

    # =========================================================================
    # ZAKLADKA: DODAWANIE WYDATKU
    # =========================================================================
    if menu == "➕ Dodaj Wydatek":
        st.title("➕ Dodaj nowy zakup")
        with st.container(border=True):
            sklep = pole_z_podpowiedziami(
                "🏪 Sklep / Dostawca",
                sklepy_podpowiedzi,
                key="dodaj_sklep",
                placeholder="np. Castorama, Allegro, Würth"
            )

            col1, col2, col3 = st.columns(3)

            brak_kwoty = col1.checkbox("Nie znam kwoty (?)")
            kwota = col1.number_input("💰 Kwota Brutto", min_value=0.0, step=0.01, format="%.2f", disabled=brak_kwoty)

            brak_daty = col2.checkbox("Brak daty (?)")
            data_zak = col2.date_input("📅 Data zakupu", date.today(), disabled=brak_daty)
            rodzaj_doc = col3.selectbox("📄 Rodzaj dokumentu", ["Papierowy / Paragon", "KSeF", "E-mail (PDF)", "Faktura PDF", "?"])

            st.divider()
            c1, c2, c3 = st.columns(3)
            metoda = c1.selectbox("💳 Metoda platnosci", ["Karta firmowa", "Karta prywatna", "Gotowka", "Pro forma", "Przelew"])
            status = c2.selectbox("📌 Status platnosci", ["Zaplacone", "Do oplacenia", "Przelew", "Zwrot"])
            zrodlo = c3.selectbox("🏧 Zrodlo srodkow", ["Karta firmowa", "Karta prywatna", "Gotowka", "Konto firmowe"])

            st.divider()
            c4, c5, c6 = st.columns(3)
            with c4:
                odbiorca = pole_z_podpowiedziami(
                    "👤 Kto odebral?",
                    odbiorcy_podpowiedzi,
                    key="dodaj_odbiorca",
                    value=st.session_state.uzytkownik,
                    placeholder="Imie lub login osoby odbierajacej"
                )
            with c5:
                platnik = pole_z_podpowiedziami(
                    "👤 Kto zaplacil?",
                    platnicy_podpowiedzi,
                    key="dodaj_platnik",
                    value=st.session_state.uzytkownik,
                    placeholder="Imie lub login osoby placacej"
                )
            typ_sklepu = c6.selectbox("📍 Miejsce zakupu", ["Stacjonarny", "Internetowy"])

            projekt = pole_z_podpowiedziami(
                "🏗️ Projekt / Cel",
                projekty_podpowiedzi,
                key="dodaj_projekt",
                placeholder="np. budowa, klient, dzial, cel zakupu"
            )
            uwagi = st.text_area("📝 Dodatkowe uwagi")

            st.divider()
            opcja_dok = st.radio("Dodaj dokument:", ["Brak", "📁 Wgraj plik", "📷 Zdjecie"], horizontal=True)
            plik_u, foto = None, None
            if opcja_dok == "📁 Wgraj plik":
                plik_u = st.file_uploader("Wybierz plik", type=["png", "jpg", "jpeg", "pdf"])
            elif opcja_dok == "📷 Zdjecie":
                foto = st.camera_input("Zrob zdjecie")

            if st.button("ZAPISZ WYDATEK", type="primary", use_container_width=True):
                if sklep and sklep != "--- wpisz nowa wartosc ---":
                    url_zdj = ""
                    if plik_u or foto:
                        with st.spinner("Wgrywanie dokumentu..."):
                            d_bytes = plik_u.getvalue() if plik_u else foto.getvalue()
                            ext = plik_u.name.split('.')[-1].lower() if plik_u else "jpg"
                            d_nazwa = f"faktura_{int(time.time())}_{uuid.uuid4().hex[:8]}.{ext}"
                            supabase.storage.from_("faktury_zdjecia").upload(d_nazwa, d_bytes)
                            url_zdj = supabase.storage.from_("faktury_zdjecia").get_public_url(d_nazwa)

                    kwota_db = 0.0 if brak_kwoty else kwota
                    data_zak_str = "?" if brak_daty else str(data_zak)
                    miesiac_rok = datetime.now().strftime("%Y-%m") if brak_daty else str(data_zak)[:7]

                    try:
                        supabase.table("wydatki").insert({
                            "sklep": sklep,
                            "kwota": kwota_db,
                            "data_zakupu": data_zak_str,
                            "rodzaj_dokumentu": rodzaj_doc,
                            "metoda_platnosci": metoda,
                            "status": status,
                            "zrodlo_srodkow": zrodlo,
                            "odbiorca": odbiorca,
                            "platnik": platnik,
                            "typ_sklepu": typ_sklepu,
                            "uwagi": f"PROJEKT: {projekt} | {uwagi}",
                            "zdjecie_url": url_zdj,
                            "zgloszone_przez": st.session_state.uzytkownik,
                            "miesiac_rok": miesiac_rok
                        }).execute()

                        pobierz_podpowiedzi.clear()
                        st.balloons()
                        st.toast("✅ Zapisano w bazie danych!", icon="💾")
                        st.success("🎉 WYDATEK ZOSTAL POMYSLNIE DODANY!", icon="✅")
                        time.sleep(2)
                        st.rerun()

                    except Exception as e:
                        st.error(f"Blad zapisu: {e}")
                else:
                    st.error("Pole Sklep / Dostawca jest obowiazkowe.")

    # =========================================================================
    # ZAKLADKA: MOJE WYDATKI
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
                if rozl:
                    st.success("✅ **ZATWIERDZONE I ROZLICZONE Z MARZENĄ**")
                c1, c2, c3 = st.columns([2, 1, 1])
                c1.markdown(f"### {'✅ ' if rozl else '🛒 '}{r['sklep']}")

                if r.get('uwagi') and r.get('uwagi') != "PROJEKT:  | ":
                    st.markdown(f"**📝 Uwagi/Projekt:** *{r['uwagi']}*")

                c1.caption(f"Dodal: {r['zgloszone_przez']} | Metoda: {r['metoda_platnosci']}")
                kw_p = "?" if float(r['kwota']) == 0.0 else f"{r['kwota']:.2f} zl"
                c2.subheader(kw_p)
                c3.write(f"📅 {r['data_zakupu']}")

                if r.get('zdjecie_url'):
                    with st.expander("🖼️ Zobacz zalacznik"):
                        if ".pdf" in r['zdjecie_url'].lower():
                            st.link_button("Otworz PDF", r['zdjecie_url'])
                        else:
                            st.image(r['zdjecie_url'], use_container_width=True)

                st.divider()
                col_b1, col_b2, col_b3 = st.columns([1, 1, 2])

                with col_b1.popover("🗑️ Usun"):
                    st.warning("Czy na pewno chcesz usunac?")
                    if st.button("Tak, usun trwale", key=f"d_potw_{r['id']}", type="primary", use_container_width=True):
                        supabase.table("wydatki").delete().eq("id", r['id']).execute()
                        pobierz_podpowiedzi.clear()
                        st.rerun()

                if not rozl and col_b2.button("✅ Rozlicz z Marzeną", key=f"r_{r['id']}", type="primary"):
                    supabase.table("wydatki").update({"status": "Rozliczone z Marzeną ✅"}).eq("id", r['id']).execute()
                    st.rerun()
                if rozl and col_b2.button("↩️ Cofnij", key=f"c_{r['id']}"):
                    supabase.table("wydatki").update({"status": "Zaplacone"}).eq("id", r['id']).execute()
                    st.rerun()

                with col_b3.expander("✏️ Edytuj wszystko"):
                    e1, e2, e3 = st.columns(3)
                    with e1:
                        e_s = pole_z_podpowiedziami("Sklep", sklepy_podpowiedzi, key=f"es_{r['id']}", value=r['sklep'])
                    e_k = e2.text_input("Kwota (wpisz ?)", value="?" if float(r['kwota']) == 0.0 else str(r['kwota']), key=f"ek_{r['id']}")
                    e_d = e3.text_input("Data (lub ?)", value=r['data_zakupu'], key=f"ed_{r['id']}")

                    o_rd = ["Papierowy / Paragon", "KSeF", "E-mail (PDF)", "Faktura PDF", "?"]
                    e_rd = st.selectbox("Rodzaj dokumentu", o_rd, index=g_idx(o_rd, r.get('rodzaj_dokumentu', '?')), key=f"erd_{r['id']}")

                    c_e1, c_e2, c_e3 = st.columns(3)
                    o_mp = ["Karta firmowa", "Karta prywatna", "Gotowka", "Pro forma", "Przelew"]
                    e_mp = c_e1.selectbox("Metoda platnosci", o_mp, index=g_idx(o_mp, r.get('metoda_platnosci', 'Karta firmowa')), key=f"emp_{r['id']}")

                    o_st = ["Zaplacone", "Do oplacenia", "Rozliczone z Marzeną ✅", "Przelew", "Zwrot"]
                    e_st = c_e2.selectbox("Status", o_st, index=g_idx(o_st, r.get('status', 'Zaplacone')), key=f"est_{r['id']}")

                    o_zs = ["Karta firmowa", "Karta prywatna", "Gotowka", "Konto firmowe"]
                    e_zs = c_e3.selectbox("Zrodlo srodkow", o_zs, index=g_idx(o_zs, r.get('zrodlo_srodkow', 'Karta firmowa')), key=f"ezs_{r['id']}")

                    c_e4, c_e5, c_e6 = st.columns(3)
                    with c_e4:
                        e_odb = pole_z_podpowiedziami("Kto odebral?", odbiorcy_podpowiedzi, key=f"eodb_{r['id']}", value=r.get('odbiorca', ''))
                    with c_e5:
                        e_pla = pole_z_podpowiedziami("Kto zaplacil?", platnicy_podpowiedzi, key=f"epla_{r['id']}", value=r.get('platnik', ''))
                    o_ts = ["Stacjonarny", "Internetowy"]
                    e_ts = c_e6.selectbox("Miejsce zakupu", o_ts, index=g_idx(o_ts, r.get('typ_sklepu', 'Stacjonarny')), key=f"ets_{r['id']}")

                    aktualny_projekt = wyciagnij_projekt_z_uwag(r.get('uwagi', ''))
                    aktualne_uwagi = wyciagnij_uwagi_bez_projektu(r.get('uwagi', ''))
                    e_proj = pole_z_podpowiedziami("Projekt / Cel", projekty_podpowiedzi, key=f"eproj_{r['id']}", value=aktualny_projekt)
                    e_u = st.text_area("Uwagi", value=aktualne_uwagi, key=f"eu_{r['id']}")

                    if st.button("💾 Zapisz wszystkie zmiany", key=f"save_{r['id']}", type="primary", use_container_width=True):
                        try:
                            n_kw = 0.0 if str(e_k).strip() == "?" else float(str(e_k).replace(",", "."))
                            supabase.table("wydatki").update({
                                "sklep": e_s,
                                "kwota": n_kw,
                                "data_zakupu": e_d,
                                "rodzaj_dokumentu": e_rd,
                                "metoda_platnosci": e_mp,
                                "status": e_st,
                                "zrodlo_srodkow": e_zs,
                                "odbiorca": e_odb,
                                "platnik": e_pla,
                                "typ_sklepu": e_ts,
                                "uwagi": f"PROJEKT: {e_proj} | {e_u}"
                            }).eq("id", r['id']).execute()
                            pobierz_podpowiedzi.clear()
                            st.rerun()
                        except ValueError:
                            st.error("Kwota ma niepoprawny format. Wpisz np. 123.45, 123,45 albo ?")

    # =========================================================================
    # ZAKLADKA: RAPORTY
    # =========================================================================
    elif menu == "📊 Raporty i Księgowość":
        st.title("📊 Zaawansowana Wyszukiwarka")
        res = supabase.table("wydatki").select("*").execute()
        if res.data:
            df = pd.DataFrame(res.data)
            df['kwota'] = df['kwota'].fillna(0).astype(float)

            with st.expander("🔍 FILTRY WYSZUKIWANIA", expanded=True):
                c1, c2, c3 = st.columns(3)
                f_zakres = c1.date_input("📅 Zakres dat", [date(2024, 1, 1), date.today()])
                lata = sorted(list(set([str(d)[:4] for d in df['data_zakupu'] if len(str(d)) >= 4 and str(d)[:4].isdigit()])), reverse=True)
                f_rok = c2.selectbox("📅 Rok", ["Wszystkie"] + lata)
                miesiace = ["Wszystkie", "01", "02", "03", "04", "05", "06", "07", "08", "09", "10", "11", "12"]
                f_mies = c3.selectbox("📅 Miesiac", miesiace)

                c4, c5, c6 = st.columns(3)
                pracownicy = sorted(df['zgloszone_przez'].unique().tolist())
                f_prac = c4.multiselect("👤 Uzytkownik", pracownicy, default=pracownicy)
                metody = sorted(df['metoda_platnosci'].unique().tolist())
                f_met = c5.multiselect("💳 Rodzaj platnosci", metody, default=metody)
                f_rozl = c6.selectbox("🤝 Rozliczone z Marzeną?", ["Wszystkie", "TAK (✅)", "NIE"])

            df_f = df.copy()
            if len(f_zakres) == 2:
                df_f = df_f[df_f['data_zakupu'] != '?']
                df_f['temp_d'] = pd.to_datetime(df_f['data_zakupu'], errors='coerce').dt.date
                df_f = df_f.dropna(subset=['temp_d'])
                df_f = df_f[(df_f['temp_d'] >= f_zakres[0]) & (df_f['temp_d'] <= f_zakres[1])]

            if f_rok != "Wszystkie":
                df_f = df_f[df_f['data_zakupu'].str.startswith(f_rok, na=False)]
            if f_mies != "Wszystkie":
                df_f = df_f[df_f['data_zakupu'].str.contains(f"-{f_mies}-", na=False)]
            df_f = df_f[df_f['zgloszone_przez'].isin(f_prac)]
            df_f = df_f[df_f['metoda_platnosci'].isin(f_met)]
            if f_rozl == "TAK (✅)":
                df_f = df_f[df_f['status'].str.contains("✅", na=False)]
            elif f_rozl == "NIE":
                df_f = df_f[~df_f['status'].str.contains("✅", na=False)]

            st.divider()
            m1, m2 = st.columns(2)
            m1.metric("Suma wybranych", f"{df_f['kwota'].sum():.2f} zl")
            do_zw = df_f[(df_f['zrodlo_srodkow'].isin(['Karta prywatna', 'Gotowka'])) & (~df_f['status'].str.contains('✅', na=False))]
            m2.metric("Do zwrotu (Pryw/Got)", f"{do_zw['kwota'].sum():.2f} zl")

            kol_r = ['data_zakupu', 'sklep', 'kwota', 'status', 'metoda_platnosci', 'zgloszone_przez', 'uwagi']
            st.dataframe(df_f[kol_r], use_container_width=True)

            st.divider()
            c_ex1, c_ex2 = st.columns(2)

            try:
                import xlsxwriter
                buffer = io.BytesIO()
                with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                    df_f[kol_r].to_excel(writer, index=False, sheet_name='Raport', startrow=2)
                    workbook = writer.book
                    worksheet = writer.sheets['Raport']

                    title_format = workbook.add_format({'bold': True, 'font_size': 14, 'font_color': 'white', 'bg_color': '#D32F2F', 'align': 'center', 'border': 1})
                    worksheet.merge_range('A1:G2', f"RAPORT FAKTUR (Wygenerowano: {datetime.now().strftime('%Y-%m-%d %H:%M')})", title_format)

                    header_format = workbook.add_format({'bold': True, 'bg_color': '#F2F2F2', 'border': 1, 'align': 'center'})
                    cell_format = workbook.add_format({'border': 1, 'text_wrap': True, 'valign': 'vcenter'})
                    num_format = workbook.add_format({'border': 1, 'num_format': '#,##0.00 "zl"', 'align': 'center'})

                    for col_num, value in enumerate(kol_r):
                        worksheet.write(2, col_num, value, header_format)

                    for row_num in range(len(df_f)):
                        for col_num in range(len(kol_r)):
                            val = df_f[kol_r].iloc[row_num, col_num]
                            if col_num == 2:
                                worksheet.write(row_num + 3, col_num, val, num_format)
                            else:
                                worksheet.write(row_num + 3, col_num, val, cell_format)

                    worksheet.set_column('A:A', 12)
                    worksheet.set_column('B:B', 22)
                    worksheet.set_column('C:C', 14)
                    worksheet.set_column('D:D', 25)
                    worksheet.set_column('E:E', 18)
                    worksheet.set_column('F:F', 14)
                    worksheet.set_column('G:G', 40)
                    worksheet.set_landscape()
                    worksheet.set_paper(9)
                    worksheet.fit_to_pages(1, 0)

                c_ex1.download_button("📊 Pobierz LUX EXCEL (.xlsx)", data=buffer.getvalue(), file_name=f"raport_{date.today()}.xlsx", use_container_width=True)
            except Exception:
                c_ex1.error("Blad wtyczki Excel. Sprawdz requirements.txt na GitHubie.")

            try:
                class ElegantPDF(FPDF):
                    def header(self):
                        self.set_fill_color(211, 47, 47)
                        self.rect(0, 0, 210, 20, 'F')

                        if hasattr(self, 'font_ready') and self.font_ready:
                            self.set_font('Roboto', '', 16)
                        else:
                            self.set_font('helvetica', 'B', 16)

                        self.set_text_color(255, 255, 255)
                        tytul = f"Raport Wydatkow - wygenerowano dnia {datetime.now().strftime('%d.%m.%Y')}"
                        self.cell(0, 10, self.clean_text(tytul), ln=True, align='C')
                        self.ln(10)

                    def footer(self):
                        self.set_y(-15)
                        if hasattr(self, 'font_ready') and self.font_ready:
                            self.set_font('Roboto', '', 8)
                        else:
                            self.set_font('helvetica', 'I', 8)
                        self.set_text_color(128, 128, 128)
                        self.cell(0, 10, f'Strona {self.page_no()} / {{nb}}', align='C')

                    def clean_text(self, tekst):
                        t = str(tekst).replace('✅', '').strip()
                        if not hasattr(self, 'font_ready') or not self.font_ready:
                            zamienniki = {'ą': 'a', 'ć': 'c', 'ę': 'e', 'ł': 'l', 'ń': 'n', 'ó': 'o', 'ś': 's', 'ź': 'z', 'ż': 'z',
                                          'Ą': 'A', 'Ć': 'C', 'Ę': 'E', 'Ł': 'L', 'Ń': 'N', 'Ó': 'O', 'Ś': 'S', 'Ź': 'Z', 'Ż': 'Z'}
                            for pl, asc in zamienniki.items():
                                t = t.replace(pl, asc)
                        return t

                font_path = "Roboto-Regular.ttf"
                font_url = "https://raw.githubusercontent.com/google/fonts/main/ofl/roboto/Roboto-Regular.ttf"
                if not os.path.exists(font_path):
                    try:
                        urllib.request.urlretrieve(font_url, font_path)
                    except Exception:
                        pass

                pdf = ElegantPDF(orientation='P', unit='mm', format='A4')
                pdf.alias_nb_pages()

                if os.path.exists(font_path):
                    pdf.add_font('Roboto', '', font_path, uni=True)
                    pdf.font_ready = True
                else:
                    pdf.font_ready = False

                pdf.add_page()

                cols = [22, 55, 22, 30, 30, 31]
                headers = ["Data", "Sklep / Dostawca", "Kwota", "Status", "Metoda", "Uzytkownik"]

                pdf.set_fill_color(60, 60, 60)
                pdf.set_text_color(255, 255, 255)
                if pdf.font_ready:
                    pdf.set_font('Roboto', '', 10)
                else:
                    pdf.set_font('helvetica', 'B', 10)

                for i, h in enumerate(headers):
                    pdf.cell(cols[i], 10, pdf.clean_text(h), border=0, ln=0, align='C', fill=True)
                pdf.ln()

                pdf.set_text_color(0, 0, 0)
                if pdf.font_ready:
                    pdf.set_font('Roboto', '', 9)
                else:
                    pdf.set_font('helvetica', '', 9)

                fill = False
                for index, row in df_f.iterrows():
                    if fill:
                        pdf.set_fill_color(245, 245, 245)
                    else:
                        pdf.set_fill_color(255, 255, 255)

                    pdf.cell(cols[0], 9, pdf.clean_text(str(row['data_zakupu'])[:10]), border='B', fill=True)
                    pdf.cell(cols[1], 9, pdf.clean_text(str(row['sklep'])[:30]), border='B', fill=True)
                    pdf.cell(cols[2], 9, pdf.clean_text(f"{row['kwota']:.2f} zl"), border='B', align='R', fill=True)
                    pdf.cell(cols[3], 9, pdf.clean_text(str(row['status'])[:16]), border='B', fill=True)
                    pdf.cell(cols[4], 9, pdf.clean_text(str(row['metoda_platnosci'])[:16]), border='B', fill=True)
                    pdf.cell(cols[5], 9, pdf.clean_text(str(row['zgloszone_przez'])[:15]), border='B', fill=True)
                    pdf.ln()
                    fill = not fill

                pdf_output = pdf.output()
                c_ex2.download_button(
                    label="📄 Pobierz Elegancki PDF (Pionowy)",
                    data=bytes(pdf_output),
                    file_name=f"raport_wydatkow_pion_{date.today()}.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )
            except Exception as e:
                c_ex2.error(f"Blad PDF: {e}")
        else:
            st.info("Brak danych do raportu.")

    # =========================================================================
    # ZAKLADKA: ZARZADZANIE KONTAMI
    # =========================================================================
    elif menu == "👥 Zarządzanie Kontami":
        st.title("👥 Zarzadzanie uzytkownikami")
        st.caption("Hasla nie sa wyswietlane. Nowe hasla sa zapisywane jako hash.")

        with st.container(border=True):
            st.subheader("➕ Dodaj nowe konto")
            cx1, cx2, cx3 = st.columns(3)
            nl = cx1.text_input("Login nowego uzytkownika")
            np = cx2.text_input("Haslo nowego uzytkownika", type="password")
            nr = cx3.selectbox("Rola", ["uzytkownik", "admin"])

            if st.button("Zapisz nowe konto", type="primary", use_container_width=True):
                login_nowy = nl.strip()
                haslo_nowe = np.strip()

                if not login_nowy or not haslo_nowe:
                    st.error("Login i haslo nie moga byc puste.")
                else:
                    istnieje = supabase.table("fakturki_konta").select("login").ilike("login", login_nowy).execute()
                    if istnieje.data:
                        st.error("Uzytkownik o takim loginie juz istnieje.")
                    else:
                        supabase.table("fakturki_konta").insert({
                            "login": login_nowy,
                            "haslo": hash_hasla(haslo_nowe),
                            "rola": nr
                        }).execute()
                        st.success("Konto zostalo dodane.")
                        time.sleep(1)
                        st.rerun()

        st.divider()
        st.subheader("Lista kont")

        res_p = supabase.table("fakturki_konta").select("login, rola").order("login").execute()
        for p in (res_p.data or []):
            login_usera = p.get('login')
            rola_usera = p.get('rola') or "uzytkownik"

            with st.container(border=True):
                ca, cb, cc = st.columns([3, 2, 2])
                ca.write(f"👤 **{login_usera}**")
                cb.write(f"Rola: `{rola_usera}`")

                with cc.popover("⚙️ Opcje"):
                    st.markdown(f"**Konto:** {login_usera}")

                    nowe_haslo = st.text_input("Nowe haslo", type="password", key=f"reset_hasla_{login_usera}")
                    if st.button("🔑 Zmien haslo", key=f"btn_reset_{login_usera}", use_container_width=True):
                        if not nowe_haslo.strip():
                            st.error("Wpisz nowe haslo.")
                        else:
                            supabase.table("fakturki_konta").update({
                                "haslo": hash_hasla(nowe_haslo.strip())
                            }).eq("login", login_usera).execute()
                            st.success("Haslo zmienione.")

                    nowa_rola = st.selectbox(
                        "Zmien role",
                        ["uzytkownik", "admin"],
                        index=g_idx(["uzytkownik", "admin"], rola_usera),
                        key=f"rola_{login_usera}"
                    )
                    if st.button("💾 Zapisz role", key=f"btn_rola_{login_usera}", use_container_width=True):
                        supabase.table("fakturki_konta").update({"rola": nowa_rola}).eq("login", login_usera).execute()
                        st.success("Rola zmieniona.")
                        time.sleep(1)
                        st.rerun()

                    if str(login_usera).lower() != "emil":
                        st.divider()
                        st.warning("Usuniecie konta jest trwale.")
                        if st.button("🗑️ Usun konto", key=f"dp_{login_usera}", type="primary", use_container_width=True):
                            supabase.table("fakturki_konta").delete().eq("login", login_usera).execute()
                            st.rerun()
                    else:
                        st.info("Konto Emil jest zabezpieczone przed usunieciem.")

    # =========================================================================
    # ZAKLADKA: INSTRUKCJA
    # =========================================================================
    elif menu == "📖 Instrukcja":
        st.title("📖 Instrukcja Obslugi Systemu")

        st.markdown("### ➕ Dodawanie wydatkow")
        st.markdown("- **Podpowiedzi:** Przy polach Sklep, Kto odebral, Kto zaplacil i Projekt aplikacja pokazuje wartosci uzyte juz wczesniej. Kliknij pole i zacznij pisac pierwsze litery, aby szybciej znalezc wpis.")
        st.markdown("- **Dokumenty:** Uzywaj aparatu telefonu do szybkiego skanowania paragonow lub wgrywaj gotowe pliki PDF/JPG z komputera.")
        st.markdown("- **Braki w danych:** Jesli w momencie dodawania nie znasz dokladnej kwoty lub daty, zaznacz okienka *'Brak daty'* lub *'Nie znam kwoty'*. System wstawi znak `?`, co ulatwi pozniejsze uzupelnienie danych.")

        st.markdown("### 📂 Historia i Edycja")
        st.markdown("- **Pelna kontrola:** W zakladce *Moje Wydatki* mozesz w dowolnej chwili rozwinac opcje `✏️ Edytuj wszystko`, aby skorygowac kazda wprowadzona informacje.")
        st.markdown("- **Rozliczenia z ksiegowoscia:** Oznaczaj zrealizowane dokumenty zielonym przyciskiem `✅ Rozlicz z Marzeną`. ")
        st.markdown("- **Zwrot:** Status `Zwrot` sluzy do oznaczania pozycji, ktore dotycza zwrotu pieniedzy/towaru.")

        st.markdown("### 📊 Raportowanie")
        st.markdown("- **Wyszukiwarka:** Filtruj wydatki wedlug dat, osob, metod platnosci czy statusu rozliczenia.")
        st.markdown("- **Eksport do Excela (.xlsx):** Generuje elegancki arkusz kalkulacyjny z gotowym formatowaniem walutowym, dopasowanymi szerokosciami kolumn i kolorowym naglowkiem. Plik jest automatycznie sformatowany do wydruku w poziomie (A4).")
        st.markdown("- **Eksport do PDF:** Tworzy zwarty, pionowy raport z ukladem zebry, czyli na przemian szare i biale wiersze.")

        st.info("**💡 Wazna zasada:** Wszystkie wydatki, ktorym nadasz status *'Rozliczone z Marzeną ✅'*, automatycznie przestaja byc wliczane do sumy w polu *'Do zwrotu'* w module raportowym.")
        st.info("**🔐 Wygoda logowania:** Aplikacja probuje utrzymac logowanie po zwyklym odswiezeniu strony. Pelne wylogowanie nastapi po kliknieciu `Wyloguj` albo po wyczyszczeniu danych przegladarki.")

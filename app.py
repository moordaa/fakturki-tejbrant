import os
import re
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
from PIL import Image

# ============================================================
# FAKTURKI-TEJBRANT
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

    if czy_hash_sha256(zapisane_haslo) and zapisane_haslo == hash_wpisanego:
        return konto

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
    wartosci = []
    for x in dane or []:
        v = x.get(kolumna)
        if v is not None and str(v).strip():
            wartosci.append(str(v).strip())
    return sorted(list(set(wartosci)), key=lambda x: x.lower())


def wyciagnij_projekt_z_uwag(tekst):
    tekst = str(tekst or "")
    if tekst.startswith("PROJEKT:") and "|" in tekst:
        return tekst.split("|", 1)[0].replace("PROJEKT:", "").strip()
    return ""


def wyciagnij_uwagi_bez_projektu(tekst):
    tekst = str(tekst or "")
    if tekst.startswith("PROJEKT:") and "|" in tekst:
        return tekst.split("|", 1)[1].strip()
    return tekst


@st.cache_data(ttl=300)
def pobierz_podpowiedzi():
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
    opcje = sorted(list(set([str(x).strip() for x in opcje if str(x).strip()])), key=lambda x: x.lower())

    if value and str(value).strip() and value not in opcje:
        opcje.insert(0, value)

    if not opcje:
        opcje = ["Brak podpowiedzi"]

    try:
        return st.selectbox(
            label,
            options=opcje,
            index=opcje.index(value) if value in opcje else None,
            key=key,
            placeholder=placeholder or "Wybierz albo wpisz nowa wartosc",
            accept_new_options=True
        )
    except Exception:
        return st.text_input(label, value=value, key=key, placeholder=placeholder)


def wgraj_dokument_do_supabase(plik_u=None, foto=None):
    MAX_MB = 10
    DOZWOLONE_EXT = ["png", "jpg", "jpeg", "pdf"]

    if not plik_u and not foto:
        return ""

    if plik_u:
        d_bytes = plik_u.getvalue()
        oryginalna_nazwa = plik_u.name or "plik"
        ext = oryginalna_nazwa.split(".")[-1].lower() if "." in oryginalna_nazwa else ""
    else:
        d_bytes = foto.getvalue()
        ext = "jpg"

    rozmiar_mb = len(d_bytes) / (1024 * 1024)
    if rozmiar_mb > MAX_MB:
        raise ValueError(f"Plik jest za duzy. Maksymalny rozmiar to {MAX_MB} MB.")

    if ext not in DOZWOLONE_EXT:
        raise ValueError("Nieobslugiwany typ pliku. Dozwolone sa: PNG, JPG, JPEG, PDF.")

    d_nazwa = f"faktura_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}.{ext}"

    try:
        supabase.storage.from_("faktury_zdjecia").upload(d_nazwa, d_bytes)
        return supabase.storage.from_("faktury_zdjecia").get_public_url(d_nazwa)
    except Exception as e:
        raise RuntimeError(f"Nie udalo sie wgrac dokumentu do Supabase: {e}")


def analizuj_dokument_ocr(image_bytes):
    """
    Funkcja OCR próbuje odczytać tekst ze zdjęcia i wyciągnąć kwotę, datę oraz sklep.
    """
    wyniki = {"sklep": "", "kwota": 0.0, "data": None}
    tekst = ""
    
    try:
        import pytesseract
        img = Image.open(io.BytesIO(image_bytes))
        tekst = pytesseract.image_to_string(img, lang='pol')
    except Exception:
        try:
            import pytesseract
            img = Image.open(io.BytesIO(image_bytes))
            tekst = pytesseract.image_to_string(img)
        except Exception:
            return wyniki, "Brak zainstalowanego silnika Tesseract OCR na serwerze."

    if not tekst.strip():
        return wyniki, "Nie udało się odczytać tekstu ze zdjęcia."

    # 1. Szukanie daty (YYYY-MM-DD lub DD.MM.YYYY)
    dane_daty = re.findall(r'\b(20\d{2}[-/.](?:0[1-9]|1[0-2])[-/.](?:0[1-9]|[12]\d|3[01]))\b', tekst)
    if not dane_daty:
        dane_daty = re.findall(r'\b((?:0[1-9]|[12]\d|3[01])[-/.](?:0[1-9]|1[0-2])[-/.](?:20)?\d{2})\b', tekst)
    
    if dane_daty:
        surowa_data = dane_daty[0].replace('/', '.').replace('-', '.')
        try:
            if len(surowa_data.split('.')[0]) == 4:
                wyniki["data"] = datetime.strptime(surowa_data, "%Y.%m.%d").date()
            else:
                p = surowa_data.split('.')
                rok = p[2] if len(p[2]) == 4 else f"20{p[2]}"
                wyniki["data"] = date(int(rok), int(p[1]), int(p[0]))
        except Exception:
            pass

    # 2. Szukanie kwoty brutto
    dane_kwoty = re.findall(r'(?:SUMA|BRUTTO|PLN|ZŁ|RAZEM)\s*[:=]?\s*(\d+[\.,]\d{2})', tekst, re.IGNORECASE)
    if not dane_kwoty:
        dane_kwoty = re.findall(r'\b(\d+[\.,]\d{2})\b', tekst)

    if dane_kwoty:
        kwoty_float = []
        for k in dane_kwoty:
            try:
                kwoty_float.append(float(k.replace(',', '.')))
            except ValueError:
                pass
        if kwoty_float:
            wyniki["kwota"] = max(kwoty_float)

    # 3. Szukanie nazwy sklepu (pierwsza linijka)
    linie = [line.strip() for line in tekst.split('\n') if line.strip() and len(line.strip()) > 2]
    if linie:
        wyniki["sklep"] = linie[0][:40]

    return wyniki, "Odczyt zakończony sukcesem."


def get_wrapped_lines(pdf, text, max_w):
    text = pdf.clean_text(str(text or ''))
    words = text.split()
    if not words:
        return [""]
    lines = []
    curr = ""
    for word in words:
        test = f"{curr} {word}".strip()
        if pdf.get_string_width(test) <= max_w:
            curr = test
        else:
            if curr:
                lines.append(curr)
            curr = word
    if curr:
        lines.append(curr)
    return lines if lines else [""]


def zapisz_sesje(login, rola):
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

    sklepy_podpowiedzi, odbiorcy_podpowiedzi, platnicy_podpowiedzi, projekty_podpowiedzi = pobierz_podpowiedzi()

    # =========================================================================
    # ZAKLADKA: DODAWANIE WYDATKU
    # =========================================================================
    if menu == "➕ Dodaj Wydatek":
        st.title("➕ Dodaj nowy zakup")

        with st.container(border=True):
            val_sklep = st.session_state.get("ocr_sklep", "")
            val_kwota = st.session_state.get("ocr_kwota", 0.0)
            val_data = st.session_state.get("ocr_data", date.today())

            sklep = pole_z_podpowiedziami(
                "🏪 Sklep / Dostawca",
                sklepy_podpowiedzi,
                key="dodaj_sklep",
                value=val_sklep,
                placeholder="np. Castorama, Allegro, Würth"
            )

            col1, col2, col3 = st.columns(3)

            brak_kwoty = col1.checkbox("Nie znam kwoty (?)")
            kwota = col1.number_input("💰 Kwota Brutto", min_value=0.0, value=float(val_kwota), step=0.01, format="%.2f", disabled=brak_kwoty)

            brak_daty = col2.checkbox("Brak daty (?)")
            data_zak = col2.date_input("📅 Data zakupu", val_data, disabled=brak_daty)
            rodzaj_doc = col3.selectbox("📄 Rodzaj dokumentu", ["KSeF", "Papierowy", "?"])

            st.divider()
            c1, c2 = st.columns(2)
            metoda = c1.selectbox("💳 Metoda platnosci", ["Karta firmowa", "Karta prywatna", "Gotowka", "Pro forma", "Przelew"])
            typ_sklepu = c2.selectbox("📍 Miejsce zakupu", ["Stacjonarny", "Internetowy"])

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

            # --- POPRAWIONY BEZPIECZNY WARUNEK DLA OCR ---
            jest_plik = plik_u is not None or foto is not None
            jest_pdf = plik_u is not None and plik_u.name.lower().endswith('.pdf')

            if jest_plik and not jest_pdf:
                if st.button("🤖 Odczytaj dane z dokumentu (OCR)", type="secondary"):
                    b_bytes = plik_u.getvalue() if plik_u else foto.getvalue()
                    with st.spinner("Skanowanie dokumentu i odczytywanie danych..."):
                        res_ocr, msg = analizuj_dokument_ocr(b_bytes)
                        if res_ocr.get("sklep"):
                            st.session_state["ocr_sklep"] = res_ocr["sklep"]
                        if res_ocr.get("kwota"):
                            st.session_state["ocr_kwota"] = res_ocr["kwota"]
                        if res_ocr.get("data"):
                            st.session_state["ocr_data"] = res_ocr["data"]
                        st.toast(f"ℹ️ {msg}")
                        st.rerun()

            if st.button("ZAPISZ WYDATEK", type="primary", use_container_width=True):
                if sklep and sklep != "Brak podpowiedzi":
                    try:
                        url_zdj = ""
                        if plik_u or foto:
                            with st.spinner("Wgrywanie dokumentu..."):
                                url_zdj = wgraj_dokument_do_supabase(plik_u=plik_u, foto=foto)

                        kwota_db = 0.0 if brak_kwoty else kwota
                        data_zak_str = "?" if brak_daty else str(data_zak)
                        miesiac_rok = datetime.now().strftime("%Y-%m") if brak_daty else str(data_zak)[:7]

                        supabase.table("wydatki").insert({
                            "sklep": sklep,
                            "kwota": kwota_db,
                            "data_zakupu": data_zak_str,
                            "rodzaj_dokumentu": rodzaj_doc,
                            "metoda_platnosci": metoda,
                            "status": "Zaplacone",
                            "zrodlo_srodkow": metoda,
                            "odbiorca": st.session_state.uzytkownik,
                            "platnik": st.session_state.uzytkownik,
                            "typ_sklepu": typ_sklepu,
                            "uwagi": f"PROJEKT: {projekt} | {uwagi}",
                            "zdjecie_url": url_zdj,
                            "zgloszone_przez": st.session_state.uzytkownik,
                            "miesiac_rok": miesiac_rok
                        }).execute()

                        for k in ["ocr_sklep", "ocr_kwota", "ocr_data"]:
                            if k in st.session_state:
                                del st.session_state[k]

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

                    o_rd = ["KSeF", "Papierowy", "E-mail (PDF)", "Faktura PDF", "?"]
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
                pracownicy = sorted(df['zgloszone_przez'].dropna().unique().tolist())
                f_prac = c4.multiselect("👤 Uzytkownik", pracownicy, default=pracownicy)
                metody = sorted(df['metoda_platnosci'].dropna().unique().tolist())
                f_met = c5.multiselect("💳 Rodzaj platnosci", metody, default=metody)
                f_rozl = c6.selectbox("🤝 Rozliczone z Marzeną?", ["Wszystkie", "TAK (✅)", "NIE"])

                c7, c8, c9 = st.columns(3)
                statusy_platnosci = sorted(df['status'].dropna().unique().tolist())
                f_status = c7.multiselect("📌 Status platnosci", statusy_platnosci, default=statusy_platnosci)
                f_sklep = c8.text_input("🏪 Szukaj sklep / dostawca")
                f_uwagi = c9.text_input("📝 Szukaj projekt / uwagi")

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
            df_f = df_f[df_f['status'].isin(f_status)]

            if f_sklep.strip():
                df_f = df_f[df_f['sklep'].fillna('').str.lower().str.contains(f_sklep.strip().lower(), na=False)]

            if f_uwagi.strip():
                df_f = df_f[df_f['uwagi'].fillna('').str.lower().str.contains(f_uwagi.strip().lower(), na=False)]

            if f_rozl == "TAK (✅)":
                df_f = df_f[df_f['status'].str.contains("✅", na=False)]
            elif f_rozl == "NIE":
                df_f = df_f[~df_f['status'].str.contains("✅", na=False)]

            df_f = df_f.copy()
            df_f['_sort_data_zakupu'] = pd.to_datetime(df_f['data_zakupu'], errors='coerce')
            df_f = df_f.sort_values(by='_sort_data_zakupu', ascending=True, na_position='last')
            df_f = df_f.drop(columns=['_sort_data_zakupu'])

            st.divider()
            m1, m2 = st.columns(2)
            m1.metric("Suma wybranych", f"{df_f['kwota'].sum():.2f} zl")
            do_zw = df_f[(df_f['zrodlo_srodkow'].isin(['Karta prywatna', 'Gotowka'])) & (~df_f['status'].str.contains('✅', na=False))]
            m2.metric("Do zwrotu (Pryw/Got)", f"{do_zw['kwota'].sum():.2f} zl")

            kol_r = ['data_zakupu', 'sklep', 'kwota', 'status', 'metoda_platnosci', 'zgloszone_przez', 'uwagi']

            widok_tabeli = st.radio("👁️ Widok tabeli na ekranie:", ["Uproszczony (dla księgowości)", "Pełny (wszystkie kolumny)"], horizontal=True)

            if widok_tabeli == "Pełny (wszystkie kolumny)":
                kol_pelne = [
                    'id', 'data_zakupu', 'sklep', 'kwota', 'rodzaj_dokumentu', 
                    'metoda_platnosci', 'status', 'zrodlo_srodkow', 'odbiorca', 
                    'platnik', 'typ_sklepu', 'uwagi', 'zdjecie_url', 'zgloszone_przez'
                ]
                kol_do_wyswietlenia = [k for k in kol_pelne if k in df_f.columns]
            else:
                kol_do_wyswietlenia = kol_r

            st.dataframe(df_f[kol_do_wyswietlenia], use_container_width=True)

            st.divider()
            st.subheader("📥 Pobieranie raportów")

            c_ex1, c_ex2, c_ex3, c_ex4 = st.columns(4)

            # --- 1. PEŁNY RAPORT EXCEL ---
            try:
                kol_pelne = [
                    'id', 'data_zakupu', 'sklep', 'kwota', 'rodzaj_dokumentu', 
                    'metoda_platnosci', 'status', 'zrodlo_srodkow', 'odbiorca', 
                    'platnik', 'typ_sklepu', 'uwagi', 'zdjecie_url', 'zgloszone_przez'
                ]
                
                kol_dostepne = [k for k in kol_pelne if k in df_f.columns]
                
                buffer_pelny = io.BytesIO()
                with pd.ExcelWriter(buffer_pelny, engine='xlsxwriter') as writer:
                    df_f[kol_dostepne].to_excel(writer, index=False, sheet_name='Pełny_Raport', startrow=2)
                    workbook = writer.book
                    worksheet = writer.sheets['Pełny_Raport']

                    title_format_p = workbook.add_format({'bold': True, 'font_size': 14, 'font_color': 'white', 'bg_color': '#1E88E5', 'align': 'center', 'border': 1})
                    worksheet.merge_range(0, 0, 1, len(kol_dostepne) - 1, f"PEŁNY RAPORT WEWNĘTRZNY ({datetime.now().strftime('%Y-%m-%d %H:%M')})", title_format_p)

                    header_format_p = workbook.add_format({'bold': True, 'bg_color': '#E3F2FD', 'border': 1, 'align': 'center'})
                    cell_format_p = workbook.add_format({'border': 1, 'valign': 'vcenter'})
                    num_format_p = workbook.add_format({'border': 1, 'num_format': '#,##0.00 "zl"', 'align': 'center'})
                    url_format_p = workbook.add_format({'border': 1, 'font_color': 'blue', 'underline': 1})

                    for col_num, value in enumerate(kol_dostepne):
                        worksheet.write(2, col_num, value, header_format_p)

                    for row_num in range(len(df_f)):
                        for col_num in range(len(kol_dostepne)):
                            col_name = kol_dostepne[col_num]
                            val = df_f[col_name].iloc[row_num]
                            
                            if pd.isna(val):
                                val = ""

                            if col_name == 'kwota':
                                worksheet.write(row_num + 3, col_num, float(val), num_format_p)
                            elif col_name == 'zdjecie_url' and str(val).startswith('http'):
                                worksheet.write_url(row_num + 3, col_num, str(val), url_format_p, string="Zobacz załącznik")
                            else:
                                worksheet.write(row_num + 3, col_num, str(val), cell_format_p)

                    for idx, col in enumerate(kol_dostepne):
                        max_len = max(df_f[col].astype(str).map(len).max(), len(col)) + 3
                        worksheet.set_column(idx, idx, min(max_len, 50))

                c_ex1.download_button(
                    "🔍 Pełny Raport Excel", 
                    data=buffer_pelny.getvalue(), 
                    file_name=f"raport_pelny_{date.today()}.xlsx", 
                    use_container_width=True
                )
            except Exception as e:
                c_ex1.error(f"Błąd Pełny Raport Excel: {e}")

            # --- 2. POBIERANIE CSV ---
            try:
                kol_pelne_csv = [k for k in ['id', 'data_zakupu', 'sklep', 'kwota', 'rodzaj_dokumentu', 'metoda_platnosci', 'status', 'zrodlo_srodkow', 'odbiorca', 'platnik', 'typ_sklepu', 'uwagi', 'zdjecie_url', 'zgloszone_przez'] if k in df_f.columns]
                csv_bytes = df_f[kol_pelne_csv].to_csv(index=False).encode('utf-8-sig')
                c_ex2.download_button(
                    "📄 Pobierz CSV",
                    data=csv_bytes,
                    file_name=f"raport_wydatkow_{date.today()}.csv",
                    mime="text/csv",
                    use_container_width=True
                )
            except Exception as e:
                c_ex2.error(f"Błąd CSV: {e}")

            # --- PRZYGOTOWANIE CZCIONEK PDF ---
            font_path = "Roboto-Regular.ttf"
            font_url = "https://raw.githubusercontent.com/google/fonts/main/ofl/roboto/Roboto-Regular.ttf"
            if not os.path.exists(font_path):
                try:
                    urllib.request.urlretrieve(font_url, font_path)
                except Exception:
                    pass

            rok_str = f_rok if f_rok != "Wszystkie" else str(datetime.now().year)
            if f_mies != "Wszystkie":
                okres_str = f"Miesiąc: {f_mies} | Rok: {rok_str}"
            elif f_rok != "Wszystkie":
                okres_str = f"Rok: {f_rok}"
            elif len(f_zakres) == 2:
                okres_str = f"{f_zakres[0].strftime('%d.%m.%Y')} - {f_zakres[1].strftime('%d.%m.%Y')}"
            else:
                okres_str = "Wszystkie wydatki"

            # --- 3. RAPORT PDF PIONOWY (DLA KSIĘGOWOŚCI) ---
            try:
                class ElegantPDF(FPDF):
                    def header(self):
                        self.set_fill_color(211, 47, 47)
                        self.rect(0, 0, 210, 28, 'F')

                        if hasattr(self, 'font_ready') and self.font_ready:
                            self.set_font('Roboto', '', 15)
                        else:
                            self.set_font('helvetica', 'B', 15)

                        self.set_text_color(255, 255, 255)
                        tytul = f"Raport Wydatkow - wygenerowano dnia {datetime.now().strftime('%d.%m.%Y')}"
                        self.cell(0, 9, self.clean_text(tytul), ln=True, align='C')

                        if hasattr(self, 'font_ready') and self.font_ready:
                            self.set_font('Roboto', '', 10)
                        else:
                            self.set_font('helvetica', '', 10)

                        okres = getattr(self, 'okres_raportu', '')
                        self.cell(0, 7, self.clean_text(f"Okres raportu: {okres}"), ln=True, align='C')
                        self.ln(12)

                    def footer(self):
                        self.set_y(-15)
                        if hasattr(self, 'font_ready') and self.font_ready:
                            self.set_font('Roboto', '', 8)
                        else:
                            self.set_font('helvetica', 'I', 8)
                        self.set_text_color(128, 128, 128)
                        self.cell(0, 10, f'Strona {self.page_no()} / {{nb}}', align='C')

                    def clean_text(self, tekst):
                        t = str(tekst or '').replace('✅', '').strip()
                        if not hasattr(self, 'font_ready') or not self.font_ready:
                            zamienniki = {'ą': 'a', 'ć': 'c', 'ę': 'e', 'ł': 'l', 'ń': 'n', 'ó': 'o', 'ś': 's', 'ź': 'z', 'ż': 'z',
                                          'Ą': 'A', 'Ć': 'C', 'Ę': 'E', 'Ł': 'L', 'Ń': 'N', 'Ó': 'O', 'Ś': 'S', 'Ź': 'Z', 'Ż': 'Z'}
                            for pl, asc in zamienniki.items():
                                t = t.replace(pl, asc)
                        return t

                pdf = ElegantPDF(orientation='P', unit='mm', format='A4')
                pdf.alias_nb_pages()
                pdf.okres_raportu = okres_str

                if os.path.exists(font_path):
                    pdf.add_font('Roboto', '', font_path)
                    pdf.font_ready = True
                else:
                    pdf.font_ready = False

                pdf.add_page()

                cols = [23, 62, 25, 32, 48]
                headers = ["Data", "Sklep / Dostawca", "Kwota", "Rodzaj dok.", "Metoda płatności"]

                pdf.set_fill_color(60, 60, 60)
                pdf.set_text_color(255, 255, 255)
                if pdf.font_ready:
                    pdf.set_font('Roboto', '', 10)
                else:
                    pdf.set_font('helvetica', 'B', 10)

                for i, h in enumerate(headers):
                    pdf.cell(cols[i], 9, pdf.clean_text(h), border=0, ln=0, align='C', fill=True)
                pdf.ln()

                pdf.set_text_color(0, 0, 0)
                if pdf.font_ready:
                    pdf.set_font('Roboto', '', 9)
                else:
                    pdf.set_font('helvetica', '', 9)

                fill = False
                for index, row in df_f.iterrows():
                    row_vals = [
                        str(row['data_zakupu'])[:10],
                        str(row['sklep']),
                        f"{row['kwota']:.2f} zł",
                        str(row.get('rodzaj_dokumentu', '')),
                        str(row['metoda_platnosci'])
                    ]

                    row_wrapped = [get_wrapped_lines(pdf, val, cols[i] - 2) for i, val in enumerate(row_vals)]
                    max_lines = max(len(lines) for lines in row_wrapped)
                    line_h = 4.5
                    row_h = max(max_lines * line_h + 3, 8)

                    if pdf.get_y() + row_h > pdf.page_break_trigger:
                        pdf.add_page()
                        pdf.set_fill_color(60, 60, 60)
                        pdf.set_text_color(255, 255, 255)
                        if pdf.font_ready:
                            pdf.set_font('Roboto', '', 10)
                        else:
                            pdf.set_font('helvetica', 'B', 10)
                        for i, h in enumerate(headers):
                            pdf.cell(cols[i], 9, pdf.clean_text(h), border=0, ln=0, align='C', fill=True)
                        pdf.ln()
                        pdf.set_text_color(0, 0, 0)
                        if pdf.font_ready:
                            pdf.set_font('Roboto', '', 9)
                        else:
                            pdf.set_font('helvetica', '', 9)

                    start_y = pdf.get_y()
                    start_x = 10
                    bg_r, bg_g, bg_b = (245, 245, 245) if fill else (255, 255, 255)

                    curr_x = start_x
                    for i, lines in enumerate(row_wrapped):
                        col_w = cols[i]
                        cell_r, cell_g, cell_b = bg_r, bg_g, bg_b

                        if i == 3:
                            rodzaj_lower = str(row.get('rodzaj_dokumentu', '')).lower()
                            if "ksef" in rodzaj_lower:
                                cell_r, cell_g, cell_b = 209, 231, 221
                            elif any(k in rodzaj_lower for k in ["papier", "paragon"]):
                                cell_r, cell_g, cell_b = 207, 226, 255
                        elif i == 4:
                            met_lower = str(row['metoda_platnosci']).lower()
                            zr_lower = str(row.get('zrodlo_srodkow', '')).lower()
                            if "karta firmowa" in met_lower or "karta firmowa" in zr_lower:
                                cell_r, cell_g, cell_b = 226, 227, 243
                            elif "karta prywatna" in met_lower or "karta prywatna" in zr_lower:
                                cell_r, cell_g, cell_b = 255, 235, 204
                            elif "gotowka" in met_lower or "gotówka" in met_lower or "gotowka" in zr_lower or "gotówka" in zr_lower:
                                cell_r, cell_g, cell_b = 255, 249, 196
                            elif any(k in met_lower for k in ["przelew", "pro forma"]):
                                cell_r, cell_g, cell_b = 235, 237, 239

                        pdf.set_fill_color(cell_r, cell_g, cell_b)
                        pdf.rect(curr_x, start_y, col_w, row_h, 'F')
                        pdf.line(curr_x, start_y + row_h, curr_x + col_w, start_y + row_h)

                        text_y = start_y + 1.5
                        align = 'R' if i == 2 else 'L'
                        for line in lines:
                            pdf.set_xy(curr_x + 1, text_y)
                            pdf.cell(col_w - 2, line_h, line, border=0, align=align)
                            text_y += line_h

                        curr_x += col_w

                    pdf.set_xy(start_x, start_y + row_h)
                    fill = not fill

                pdf_output = pdf.output()
                c_ex3.download_button(
                    label="📄 Raport dla księgowości PDF (pionowo)",
                    data=bytes(pdf_output),
                    file_name=f"raport_ksiegowosc_pion_{date.today()}.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )
            except Exception as e:
                c_ex3.error(f"Blad PDF Księgowość: {e}")

            # --- 4. PEŁNY ELEGANCKI RAPORT PDF POZIOMY ---
            try:
                class ElegantFullPDF(FPDF):
                    def header(self):
                        self.set_fill_color(211, 47, 47)
                        self.rect(0, 0, 297, 28, 'F')

                        if hasattr(self, 'font_ready') and self.font_ready:
                            self.set_font('Roboto', '', 15)
                        else:
                            self.set_font('helvetica', 'B', 15)

                        self.set_text_color(255, 255, 255)
                        tytul = f"Pełny Raport Wewnętrzny Wydatków - wygenerowano dnia {datetime.now().strftime('%d.%m.%Y')}"
                        self.cell(0, 9, self.clean_text(tytul), ln=True, align='C')

                        if hasattr(self, 'font_ready') and self.font_ready:
                            self.set_font('Roboto', '', 10)
                        else:
                            self.set_font('helvetica', '', 10)

                        okres = getattr(self, 'okres_raportu', '')
                        self.cell(0, 7, self.clean_text(f"Okres raportu: {okres}"), ln=True, align='C')
                        self.ln(12)

                    def footer(self):
                        self.set_y(-15)
                        if hasattr(self, 'font_ready') and self.font_ready:
                            self.set_font('Roboto', '', 8)
                        else:
                            self.set_font('helvetica', 'I', 8)
                        self.set_text_color(128, 128, 128)
                        self.cell(0, 10, f'Strona {self.page_no()} / {{nb}}', align='C')

                    def clean_text(self, tekst):
                        t = str(tekst or '').replace('✅', '').strip()
                        if not hasattr(self, 'font_ready') or not self.font_ready:
                            zamienniki = {'ą': 'a', 'ć': 'c', 'ę': 'e', 'ł': 'l', 'ń': 'n', 'ó': 'o', 'ś': 's', 'ź': 'z', 'ż': 'z',
                                          'Ą': 'A', 'Ć': 'C', 'Ę': 'E', 'Ł': 'L', 'Ń': 'N', 'Ó': 'O', 'Ś': 'S', 'Ź': 'Z', 'Ż': 'Z'}
                            for pl, asc in zamienniki.items():
                                t = t.replace(pl, asc)
                        return t

                pdf_p = ElegantFullPDF(orientation='L', unit='mm', format='A4')
                pdf_p.alias_nb_pages()
                pdf_p.okres_raportu = okres_str

                if os.path.exists(font_path):
                    pdf_p.add_font('Roboto', '', font_path)
                    pdf_p.font_ready = True
                else:
                    pdf_p.font_ready = False

                pdf_p.add_page()

                cols_p = [18, 38, 22, 22, 28, 28, 32, 18, 71]
                headers_p = ["Data", "Sklep / Dostawca", "Kwota", "Dokument", "Metoda / Źródło", "Status", "Płatnik / Odbiorca", "Miejsce", "Projekt / Uwagi"]

                pdf_p.set_fill_color(60, 60, 60)
                pdf_p.set_text_color(255, 255, 255)
                if pdf_p.font_ready:
                    pdf_p.set_font('Roboto', '', 9)
                else:
                    pdf_p.set_font('helvetica', 'B', 9)

                for i, h in enumerate(headers_p):
                    pdf_p.cell(cols_p[i], 9, pdf_p.clean_text(h), border=0, ln=0, align='C', fill=True)
                pdf_p.ln()

                pdf_p.set_text_color(0, 0, 0)
                if pdf_p.font_ready:
                    pdf_p.set_font('Roboto', '', 8)
                else:
                    pdf_p.set_font('helvetica', '', 8)

                fill_p = False
                for index, row in df_f.iterrows():
                    met_zrodlo = f"{row.get('metoda_platnosci', '')} ({row.get('zrodlo_srodkow', '')})" if row.get('zrodlo_srodkow') and row.get('zrodlo_srodkow') != row.get('metoda_platnosci') else str(row.get('metoda_platnosci', ''))
                    po_str = f"Pł: {row.get('platnik', '')} / Od: {row.get('odbiorca', '')}" if row.get('platnik') or row.get('odbiorca') else str(row.get('zgloszone_przez', ''))
                    
                    row_vals = [
                        str(row['data_zakupu'])[:10],
                        str(row['sklep']),
                        f"{row['kwota']:.2f} zł",
                        str(row.get('rodzaj_dokumentu', '')),
                        met_zrodlo,
                        str(row.get('status', '')),
                        po_str,
                        str(row.get('typ_sklepu', '')),
                        str(row.get('uwagi', ''))
                    ]

                    row_wrapped = [get_wrapped_lines(pdf_p, val, cols_p[i] - 2) for i, val in enumerate(row_vals)]
                    max_lines = max(len(lines) for lines in row_wrapped)
                    line_h = 4.2
                    row_h = max(max_lines * line_h + 2.5, 7)

                    if pdf_p.get_y() + row_h > pdf_p.page_break_trigger:
                        pdf_p.add_page()
                        pdf_p.set_fill_color(60, 60, 60)
                        pdf_p.set_text_color(255, 255, 255)
                        if pdf_p.font_ready:
                            pdf_p.set_font('Roboto', '', 9)
                        else:
                            pdf_p.set_font('helvetica', 'B', 9)
                        for i, h in enumerate(headers_p):
                            pdf_p.cell(cols_p[i], 9, pdf_p.clean_text(h), border=0, ln=0, align='C', fill=True)
                        pdf_p.ln()
                        pdf_p.set_text_color(0, 0, 0)
                        if pdf_p.font_ready:
                            pdf_p.set_font('Roboto', '', 8)
                        else:
                            pdf_p.set_font('helvetica', '', 8)

                    start_y = pdf_p.get_y()
                    start_x = 10
                    bg_r, bg_g, bg_b = (245, 245, 245) if fill_p else (255, 255, 255)

                    curr_x = start_x
                    for i, lines in enumerate(row_wrapped):
                        col_w = cols_p[i]

                        pdf_p.set_fill_color(bg_r, bg_g, bg_b)
                        pdf_p.rect(curr_x, start_y, col_w, row_h, 'F')
                        pdf_p.line(curr_x, start_y + row_h, curr_x + col_w, start_y + row_h)

                        text_y = start_y + 1.2
                        align = 'R' if i == 2 else 'L'
                        for line in lines:
                            pdf_p.set_xy(curr_x + 1, text_y)
                            pdf_p.cell(col_w - 2, line_h, line, border=0, align=align)
                            text_y += line_h

                        curr_x += col_w

                    pdf_p.set_xy(start_x, start_y + row_h)
                    fill_p = not fill_p

                pdf_p_output = pdf_p.output()
                c_ex4.download_button(
                    label="🔍 Pełny raport PDF (poziomo)",
                    data=bytes(pdf_p_output),
                    file_name=f"raport_pelny_poziom_{date.today()}.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                    type="primary"
                )
            except Exception as e:
                c_ex4.error(f"Blad Pełny PDF: {e}")
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
        st.markdown("- **Skanowanie OCR:** Po wybraniu pliku lub zrobieniu zdjęcia możesz kliknąć przycisk `🤖 Odczytaj dane z dokumentu (OCR)`, aby system sam uzupełnił kwotę, datę i nazwę sklepu.")
        st.markdown("- **Dokumenty:** Uzywaj aparatu telefonu do szybkiego skanowania paragonow lub wgrywaj gotowe pliki PDF/JPG z komputera.")
        st.markdown("- **Braki w danych:** Jesli w momencie dodawania nie znasz dokladnej kwoty lub daty, zaznacz okienka *'Brak daty'* lub *'Nie znam kwoty'*. System wstawi znak `?`, co ulatwi pozniejsze uzupelnienie danych.")

        st.markdown("### 📂 Historia i Edycja")
        st.markdown("- **Pelna kontrola:** W zakladce *Moje Wydatki* mozesz w dowolnej chwili rozwinac opcje `✏️ Edytuj wszystko`, aby skorygowac kazda wprowadzona informacje.")
        st.markdown("- **Rozliczenia z ksiegowoscia:** Oznaczaj zrealizowane dokumenty zielonym przyciskiem `✅ Rozlicz z Marzeną`.")
        st.markdown("- **Zwrot:** Status `Zwrot` sluzy do oznaczania pozycji, ktore dotycza zwrotu pieniedzy/towaru.")

        st.markdown("### 📊 Raportowanie")
        st.markdown("- **Wyszukiwarka:** Filtruj wydatki wedlug dat, osob, metod platnosci czy statusu rozliczenia.")
        st.markdown("- **Pobieranie CSV:** Przycisk `📄 Pobierz CSV` generuje uniwersalny plik danych gotowy do otwarcia w dowolnym arkuszu kalkulacyjnym.")
        st.markdown("- **Zawijanie tekstu w PDF:** Długie nazwy sklepów, opisy projektów czy uwagi automatycznie zawijają się do kolejnych linii wiersza.")

        st.info("**💡 Wazna zasada:** Wszystkie wydatki, ktorym nadasz status *'Rozliczone z Marzeną ✅'*, automatycznie przestaja byc wliczane do sumy w polu *'Do zwrotu'* w module raportowym.")
        st.info("**🔐 Wygoda logowania:** Aplikacja probuje utrzymac logowanie po zwyklym odswiezeniu strony. Pelne wylogowanie nastapi po kliknieciu `Wyloguj` albo po wyczyszczeniu danych przegladarki.")

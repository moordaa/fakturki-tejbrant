import os
import urllib.request
import streamlit as st
from supabase import create_client, Client
from datetime import datetime, date
import pandas as pd
import time
import io
import uuid
from fpdf import FPDF

# --- KONFIGURACJA ---
# UWAGA: Ze względów bezpieczeństwa w środowisku produkcyjnym 
# zaleca się przeniesienie URL i KEY do pliku .streamlit/secrets.toml
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
                            d_nazwa = f"faktura_{int(time.time())}_{uuid.uuid4().hex[:8]}.{ext}"
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
    # ZAKŁADKA: MOJE WYDATKI
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
                
                if r.get('uwagi') and r.get('uwagi') != "PROJEKT:  | ":
                    st.markdown(f"**📝 Uwagi/Projekt:** *{r['uwagi']}*")
                
                c1.caption(f"Dodał: {r['zgloszone_przez']} | Metoda: {r['metoda_platnosci']}")
                kw_p = "?" if float(r['kwota']) == 0.0 else f"{r['kwota']:.2f} zł"
                c2.subheader(kw_p)
                c3.write(f"📅 {r['data_zakupu']}")
                
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
                if rozl and col_b2.button("↩️ Cofnij", key=f"c_{r['id']}"):
                    supabase.table("wydatki").update({"status": "Zapłacone"}).eq("id", r['id']).execute(); st.rerun()
                
                with col_b3.expander("✏️ Edytuj wszystko"):
                    def g_idx(opt, val): return opt.index(val) if val in opt else 0
                    e1, e2 = st.columns(2)
                    e_s = e1.text_input("Sklep", value=r['sklep'], key=f"es_{r['id']}")
                    e_k = e2.text_input("Kwota (wpisz ? dla braku)", value="?" if float(r['kwota']) == 0.0 else str(r['kwota']), key=f"ek_{r['id']}")
                    e_d = st.text_input("Data (lub ?)", value=r['data_zakupu'], key=f"ed_{r['id']}")
                    o_st = ["Zapłacone", "Do opłacenia", "Rozliczone z Marzeną ✅", "Przelew"]
                    e_st = st.selectbox("Status", o_st, index=g_idx(o_st, r['status']), key=f"e_st_{r['id']}")
                    e_u = st.text_area("Uwagi / Projekt", value=r.get('uwagi', ''), key=f"e_u_{r['id']}")
                    if st.button("💾 Zapisz zmiany", key=f"save_{r['id']}", type="primary"):
                        n_kw = 0.0 if e_k == "?" else float(e_k.replace(",", "."))
                        supabase.table("wydatki").update({"sklep": e_s, "kwota": n_kw, "data_zakupu": e_d, "status": e_st, "uwagi": e_u}).eq("id", r['id']).execute(); st.rerun()

    # =========================================================================
    # ZAKŁADKA: RAPORTY
    # =========================================================================
    elif menu == "📊 Raporty i Księgowość":
        st.title("📊 Zaawansowana Wyszukiwarka")
        res = supabase.table("wydatki").select("*").execute()
        if res.data:
            df = pd.DataFrame(res.data)
            df['kwota'] = df['kwota'].fillna(0).astype(float)

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

            st.divider()
            m1, m2 = st.columns(2)
            m1.metric("Suma wybranych", f"{df_f['kwota'].sum():.2f} zł")
            do_zw = df_f[(df_f['zrodlo_srodkow'].isin(['Karta prywatna', 'Gotówka'])) & (~df_f['status'].str.contains('✅', na=False))]
            m2.metric("Do zwrotu (Pryw/Got)", f"{do_zw['kwota'].sum():.2f} zł")
            
            kol_r = ['data_zakupu', 'sklep', 'kwota', 'status', 'metoda_platnosci', 'zgloszone_przez', 'uwagi']
            st.dataframe(df_f[kol_r], use_container_width=True)
            
            st.divider()
            c_ex1, c_ex2 = st.columns(2)
            
            # --- LUKSUSOWY EXCEL ---
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
                    num_format = workbook.add_format({'border': 1, 'num_format': '#,##0.00 "zł"', 'align': 'center'})

                    for col_num, value in enumerate(kol_r):
                        worksheet.write(2, col_num, value, header_format)
                    
                    for row_num in range(len(df_f)):
                        for col_num in range(len(kol_r)):
                            val = df_f[kol_r].iloc[row_num, col_num]
                            if col_num == 2: worksheet.write(row_num + 3, col_num, val, num_format)
                            else: worksheet.write(row_num + 3, col_num, val, cell_format)
                    
                    worksheet.set_column('A:A', 12); worksheet.set_column('B:B', 22); worksheet.set_column('C:C', 14)
                    worksheet.set_column('D:D', 25); worksheet.set_column('E:E', 18); worksheet.set_column('F:F', 14); worksheet.set_column('G:G', 40)
                    worksheet.set_landscape(); worksheet.set_paper(9); worksheet.fit_to_pages(1, 0)
                
                c_ex1.download_button("📊 Pobierz LUX EXCEL (.xlsx)", data=buffer.getvalue(), file_name=f"raport_{date.today()}.xlsx", use_container_width=True)
            except:
                c_ex1.error("Błąd wtyczki Excel. Sprawdź requirements.txt na GitHubie.")

            # --- ELEGANCKI PDF (PIONOWY / PORTRAIT) ---
            try:
                class ElegantPDF(FPDF):
                    def header(self):
                        # Pasek dekoracyjny na górze - dostosowany do szerokości A4 pionowo (210mm)
                        self.set_fill_color(211, 47, 47)  # Kolor czerwony
                        self.rect(0, 0, 210, 20, 'F') 
                        
                        if hasattr(self, 'font_ready') and self.font_ready:
                            self.set_font('Roboto', '', 16)
                        else:
                            self.set_font('helvetica', 'B', 16)
                            
                        self.set_text_color(255, 255, 255)
                        tytul = f"Raport Wydatków Emila- wygenerowano dnia {datetime.now().strftime('%d.%m.%Y')}"
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
                            zamienniki = {'ą':'a', 'ć':'c', 'ę':'e', 'ł':'l', 'ń':'n', 'ó':'o', 'ś':'s', 'ź':'z', 'ż':'z',
                                          'Ą':'A', 'Ć':'C', 'Ę':'E', 'Ł':'L', 'Ń':'N', 'Ó':'O', 'Ś':'S', 'Ź':'Z', 'Ż':'Z'}
                            for pl, asc in zamienniki.items():
                                t = t.replace(pl, asc)
                        return t

                # Przygotowanie czcionek
                font_path = "Roboto-Regular.ttf"
                font_url = "https://raw.githubusercontent.com/google/fonts/main/ofl/roboto/Roboto-Regular.ttf"
                if not os.path.exists(font_path):
                    try: urllib.request.urlretrieve(font_url, font_path)
                    except: pass

                # Zmiana orientacji z 'L' na 'P' (Portrait)
                pdf = ElegantPDF(orientation='P', unit='mm', format='A4')
                pdf.alias_nb_pages()
                
                # Konfiguracja czcionki polskiej
                if os.path.exists(font_path):
                    pdf.add_font('Roboto', '', font_path, uni=True)
                    pdf.font_ready = True
                else:
                    pdf.font_ready = False

                pdf.add_page()
                
                # Węższe kolumny dostosowane do szerokości 190mm kartki pionowej (210mm - 20mm marginesów)
                cols = [22, 55, 22, 30, 30, 31]
                headers = ["Data", "Sklep / Dostawca", "Kwota", "Status", "Metoda", "Użytkownik"]
                
                pdf.set_fill_color(60, 60, 60) # Ciemnoszary nagłówek tabeli
                pdf.set_text_color(255, 255, 255)
                if pdf.font_ready: pdf.set_font('Roboto', '', 10)
                else: pdf.set_font('helvetica', 'B', 10)

                for i, h in enumerate(headers):
                    pdf.cell(cols[i], 10, pdf.clean_text(h), border=0, ln=0, align='C', fill=True)
                pdf.ln()

                # Dane - Efekt Zebry
                pdf.set_text_color(0, 0, 0)
                if pdf.font_ready: pdf.set_font('Roboto', '', 9)
                else: pdf.set_font('helvetica', '', 9)
                
                fill = False
                for index, row in df_f.iterrows():
                    # Kolor tła dla co drugiego wiersza
                    if fill: pdf.set_fill_color(245, 245, 245)
                    else: pdf.set_fill_color(255, 255, 255)
                    
                    # Delikatnie przycięte teksty dla węższych kolumn pionowych
                    pdf.cell(cols[0], 9, pdf.clean_text(str(row['data_zakupu'])[:10]), border='B', fill=True)
                    pdf.cell(cols[1], 9, pdf.clean_text(str(row['sklep'])[:30]), border='B', fill=True)
                    pdf.cell(cols[2], 9, pdf.clean_text(f"{row['kwota']:.2f} zł"), border='B', align='R', fill=True)
                    pdf.cell(cols[3], 9, pdf.clean_text(str(row['status'])[:16]), border='B', fill=True)
                    pdf.cell(cols[4], 9, pdf.clean_text(str(row['metoda_platnosci'])[:16]), border='B', fill=True)
                    pdf.cell(cols[5], 9, pdf.clean_text(str(row['zgloszone_przez'])[:15]), border='B', fill=True)
                    pdf.ln()
                    fill = not fill # Przełącz kolor

                pdf_output = pdf.output()
                c_ex2.download_button(
                    label="📄 Pobierz Elegancki PDF (Pionowy)",
                    data=bytes(pdf_output),
                    file_name=f"raport_wydatkow_pion_{date.today()}.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )
            except Exception as e:
                c_ex2.error(f"Błąd PDF: {e}")

    # =========================================================================
    # ZAKŁADKA: ZARZĄDZANIE KONTAMI
    # =========================================================================
    elif menu == "👥 Zarządzanie Kontami":
        st.title("👥 Zarządzanie użytkownikami")
        with st.container(border=True):
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
        st.title("📖 Pomoc")
        st.success("**✅ Rozliczenia:** Każda pozycja oznaczona 'Rozliczone z Marzeną' przestaje być liczona w polu 'Do zwrotu'.")
        st.info("**📈 Excel:** Plik LUX EXCEL ma kolory, dopasowane kolumny i jest gotowy do druku na A4.")

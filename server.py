#!/usr/bin/env python3
"""
Okolica.ai - web server
"""

import json
import urllib.request
import urllib.parse
import urllib.error
import http.server
import os
import sys
import subprocess
import tempfile

PORT = int(os.environ.get("PORT", 8765))
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "AIzaSyCn352TYX2Ji_nIt0Htl1rhGY_GMktKjPA")
HTML_FILE = os.path.join(os.path.dirname(__file__), "index.html")
GEN_SCRIPT = os.path.join(os.path.dirname(__file__), "generate_doc.js")

class Handler(http.server.BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):
        print(f"  {args[0]} {args[1]}")

    def send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", len(body))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def send_html(self, content):
        body = content.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)

    def send_file(self, filepath, filename):
        with open(filepath, "rb") as f:
            data = f.read()
        self.send_response(200)
        self.send_header("Content-Type", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
        self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.send_header("Content-Length", len(data))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(data)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            with open(HTML_FILE, "r", encoding="utf-8") as f:
                self.send_html(f.read())
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length)
        print(f"POST {self.path} ({length} bytes)", flush=True)
        try:
            payload = json.loads(raw)
        except Exception as e:
            print(f"JSON parse error: {e}", flush=True)
            self.send_json({"error": "Invalid JSON"}, 400)
            return

        routes = {
            "/api/geocode":      self._geocode,
            "/api/reverse":      self._reverse,
            "/api/autocomplete": self._autocomplete,
            "/api/overpass":     self._overpass,
            "/api/claude":       self._claude,
            "/api/generate-doc": self._generate_doc,
        }
        handler = routes.get(self.path)
        if handler:
            try:
                handler(payload)
            except Exception as e:
                import traceback
                print(f"HANDLER ERROR {self.path}: {traceback.format_exc()}", flush=True)
                try:
                    self.send_json({"error": str(e)}, 500)
                except:
                    pass
        else:
            self.send_json({"error": "Not found"}, 404)

    # ── Geocoding ─────────────────────────────────────────────────
    def _geocode(self, payload):
        address = payload.get("address", "")
        url = "https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode({
            "q": address, "format": "json", "limit": "1", "addressdetails": "1"
        })
        req = urllib.request.Request(url, headers={"User-Agent": "OkolicaAI/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                self.send_json(json.loads(r.read()))
        except Exception as e:
            self.send_json({"error": str(e)}, 500)

    def _reverse(self, payload):
        lat, lon = payload.get("lat"), payload.get("lon")
        url = "https://nominatim.openstreetmap.org/reverse?" + urllib.parse.urlencode({
            "lat": lat, "lon": lon, "format": "json",
            "zoom": "18", "addressdetails": "1", "accept-language": "hr"
        })
        req = urllib.request.Request(url, headers={"User-Agent": "OkolicaAI/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                self.send_json(json.loads(r.read()))
        except Exception as e:
            self.send_json({"error": str(e), "display_name": f"{lat}, {lon}"}, 200)

    def _autocomplete(self, payload):
        q = payload.get("q", "")
        url = "https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode({
            "q": q, "format": "json", "limit": "6",
            "addressdetails": "1", "accept-language": "hr"
        })
        req = urllib.request.Request(url, headers={"User-Agent": "OkolicaAI/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=8) as r:
                data = json.loads(r.read())
            results = []
            for item in data:
                addr = item.get("address", {})
                main = (addr.get("road") or addr.get("pedestrian") or
                        addr.get("footway") or item.get("display_name","").split(",")[0])
                hn = addr.get("house_number", "")
                if hn: main = f"{main} {hn}"
                sub_parts = [
                    addr.get("suburb") or addr.get("neighbourhood",""),
                    addr.get("city") or addr.get("town") or addr.get("village",""),
                    addr.get("country",""),
                ]
                sub = ", ".join(p for p in sub_parts if p)
                results.append({
                    "display_name": item["display_name"],
                    "display_main": main,
                    "display_sub": sub,
                    "lat": item["lat"], "lon": item["lon"],
                })
            self.send_json({"results": results})
        except Exception as e:
            self.send_json({"results": [], "error": str(e)})

    # ── Overpass ──────────────────────────────────────────────────
    def _overpass(self, payload):
        query = payload.get("query", "")
        endpoints = [
            "https://overpass-api.de/api/interpreter",
            "https://lz4.overpass-api.de/api/interpreter",
            "https://z.overpass-api.de/api/interpreter",
            "https://overpass.kumi.systems/api/interpreter",
            "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
            "https://overpass.openstreetmap.ru/api/interpreter",
        ]
        last_err = None
        for ep in endpoints:
            try:
                body = ("data=" + urllib.parse.quote(query)).encode()
                req = urllib.request.Request(ep, data=body, method="POST", headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "User-Agent": "Mozilla/5.0 OkolicaAI/1.0",
                    "Accept": "application/json",
                })
                print(f"Overpass trying: {ep}", flush=True)
                with urllib.request.urlopen(req, timeout=20) as r:
                    raw = r.read()
                raw_str = raw.decode("utf-8", errors="replace").strip()
                if not raw_str.startswith("{"):
                    last_err = f"ne-JSON: {raw_str[:80]}"
                    print(f"Overpass {ep}: {last_err}", flush=True)
                    continue
                print(f"Overpass ok: {ep}", flush=True)
                self.send_json(json.loads(raw_str))
                return
            except Exception as e:
                last_err = str(e)
                print(f"Overpass {ep} failed: {e}", flush=True)
        self.send_json({"error": f"Svi Overpass endpointi nedostupni: {last_err}"}, 500)

    # ── Gemini AI ─────────────────────────────────────────────────
    def _gemini_call(self, messages, max_tokens=2000):
        """Poziva Gemini API i vraca tekst odgovora ili None uz error string."""
        if not GEMINI_API_KEY:
            return None, "GEMINI_API_KEY nije postavljen."

        # Spoji sve user poruke u jedan tekst
        prompt = "\n\n".join(m.get("content", "") for m in messages if m.get("role") == "user")

        body = json.dumps({
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "maxOutputTokens": max_tokens,
                "temperature": 0.3,
            },
            "safetySettings": [
                {"category": "HARM_CATEGORY_HARASSMENT",        "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH",       "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
            ]
        }).encode("utf-8")

        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
        req = urllib.request.Request(url, data=body, method="POST",
            headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                raw = r.read()
            data = json.loads(raw)

            candidates = data.get("candidates", [])
            if not candidates:
                reason = data.get("promptFeedback", {}).get("blockReason", "nepoznat razlog")
                return None, f"Gemini blokirao odgovor: {reason}"

            parts = candidates[0].get("content", {}).get("parts", [])
            if not parts:
                finish = candidates[0].get("finishReason", "")
                return None, f"Gemini prazan odgovor (finishReason: {finish})"

            return parts[0].get("text", ""), None

        except urllib.error.HTTPError as e:
            err_body = ""
            try: err_body = e.read().decode()
            except: pass
            return None, f"Gemini gre\u0161ka {e.code}: {err_body}"
        except Exception as e:
            return None, str(e)

    def _claude(self, payload):
        """Endpoint za kratki opis okolice (kompas prikaz)."""
        if not GEMINI_API_KEY:
            self.send_json({"error": "GEMINI_API_KEY nije postavljen."}, 400)
            return
        messages = payload.get("messages", [])
        text, err = self._gemini_call(messages)
        if err:
            self.send_json({"error": err}, 500)
            return
        # Vraćamo u Anthropic-kompatibilnom formatu jer frontend to očekuje
        self.send_json({"content": [{"type": "text", "text": text}]})

    # ── Generate Word document ────────────────────────────────────
    def _generate_doc(self, payload):
        if not GEMINI_API_KEY:
            self.send_json({"error": "API ključ nije postavljen."}, 400)
            return

        address      = payload.get("address", "")
        lat          = payload.get("lat", "")
        lon          = payload.get("lon", "")
        radius       = payload.get("radius", 500)
        places_text  = payload.get("places_text", "")  # formatted places by direction

        # Build prompts for each table group
        base_ctx = f"""Adresa/lokacija: {address}
Koordinate: {lat}, {lon}
Radijus analize: {radius}m

Objekti i sadržaji pronađeni u okolici:
{places_text}

Primijenjeni zakoni i propisi:
- Zakon o privatnoj zaštiti (NN 16/20, 114/22)
- Zakon o prekršajima protiv javnog reda i mira (NN 41/77, 52/87 i dopune)
- Zakon o sigurnosti prometa na cestama (NN 67/08 i dopune)
- Kazneni zakon (NN 125/11 i dopune)
- Pravilnik o uvjetima i načinu provedbe tehničke zaštite (NN 198/03)
- Pravilnik o načinu i uvjetima obavljanja poslova privatne zaštite na javnim površinama (NN 36/12)"""

        # Form data from questionnaire
        fd = payload.get("form_data", {})
        tj = fd.get("tjelesna", {})
        teh = fd.get("tehnicka", {})
        org = fd.get("organizacijske", {})
        materijali = fd.get("materijali", "")
        instalacije = fd.get("instalacije", "")
        procesi = fd.get("procesi", "")

        # Build static texts for tables 2.3, 2.4, 2.6, 2.8, 2.9 from form data
        # Table 2.3
        t23_mat = materijali if materijali else "Hodne i tranzitne površine: betonski opločnici i asfaltni slojevi.\nUrbana oprema: čelik i drvo (klupe, koševi za otpad).\nOstale površine: prirodni travnjak i hortikulturne površine."
        t23_nagib = "Nagib terena utvrđuje se terenskim pregledom lokacije."
        t23_elementi = "Postojeći elementi utvrđuju se terenskim pregledom (stepenice, podvožnjaci, objekti i sl.)."

        # Table 2.4
        t24_el = instalacije if instalacije else "Električne instalacije lokacije uključuju sustav javne rasvjete s pripadajućom infrastrukturom. Sve instalacije izvedene su prema važećim propisima."
        t24_ost = "Ostale instalacije (plin, voda, kanalizacija) utvrđuju se uvidom u projektnu dokumentaciju i terenskim pregledom."

        # Table 2.6
        t26 = procesi if procesi else "Posebnih procesa i postupaka bitnih za sigurnost lokacije nema ili se utvrđuju terenskim pregledom."

        # Table 2.8 - Tjelesna zaštita
        if tj.get("provodi"):
            tj_broj = tj.get("broj", "")
            tj_radno = tj.get("radno", "")
            tj_opis = tj.get("opis", "")
            t28_tjelesna = f"Na lokaciji se provodi tjelesna zaštita sukladno Zakonu o privatnoj zaštiti (NN 16/20, 114/22) i Pravilniku o načinu i uvjetima obavljanja poslova privatne zaštite na javnim površinama (NN 36/12)."
            if tj_broj: t28_tjelesna += f" Angažirano je {tj_broj}."
            if tj_radno: t28_tjelesna += f" Zaštita se provodi u vremenu: {tj_radno}."
            if tj_opis: t28_tjelesna += f" {tj_opis}"
        else:
            t28_tjelesna = "U lokaciji se trenutno ne provodi tjelesna zaštita sukladno Zakonu o privatnoj zaštiti (NN 16/20, 114/22)."

        # Table 2.8 - Tehnička zaštita
        sustavi = teh.get("sustavi", [])
        if teh.get("provodi"):
            t28_tehnicka = "Na lokaciji se provodi tehnička zaštita sukladno Pravilniku o uvjetima i načinu provedbe tehničke zaštite (NN 198/03)."
            if sustavi: t28_tehnicka += f" Instalirani sustavi: {', '.join(sustavi)}."
            if teh.get("opis"): t28_tehnicka += f" {teh.get('opis')}"
        else:
            t28_tehnicka = "U lokaciji se trenutno ne provodi tehnička zaštita sukladno Pravilniku o uvjetima i načinu provedbe tehničke zaštite (NN 198/03)."

        # Table 2.8 - Organizacijske mjere
        if org.get("postoje") and org.get("opis"):
            t28_org = org.get("opis")
        elif org.get("postoje"):
            t28_org = "Na lokaciji su definirane organizacijske mjere zaštite sukladno važećim zakonskim propisima."
        else:
            t28_org = "Za lokaciju nisu definirane posebne organizacijske mjere zaštite. Sigurnost se oslanja na redovite ophodnje komunalnog redarstva i policije."

        # Table 2.9
        if teh.get("provodi"):
            t29_postojeci = f"Na lokaciji se provodi tehnička zaštita. Sustavi: {', '.join(sustavi) if sustavi else 'definirani terenskim pregledom'}."
            t29_dok = "Dokumentacija sustava tehničke zaštite postoji." if teh.get("dokumentacija") else "Dokumentacija sustava tehničke zaštite nije dostupna ili nije izrađena."
        else:
            t29_postojeci = "U lokaciji se ne provodi tehnička zaštita."
            t29_dok = "Ne postoji dokumentacija postojećih sustava tehničke zaštite."

        prompts = {
            "t21": f"""{base_ctx}

Generiraj sadržaj za tablicu 2.1 - Opis lokacije u stilu profesionalnog sigurnosnog elaborata. Svako polje treba biti detaljno, formalno i sveobuhvatno — minimalno 5-8 rečenica po polju. Odgovori ISKLJUČIVO u JSON formatu bez ikakvih dodatnih znakova ili objašnjenja:
{{
  "opis_lokacije": "Detaljni opis lokacije: adresa, gradska četvrt, šire urbano područje, karakter zone (stambena/poslovna/mješovita/sportska), ukratko što je taj objekt ili površina, kako je infrastrukturno povezan s gradom. Minimalno 6 rečenica.",
  "opis_okolnih": "Sistematičan opis okolnih građevina i površina po stranama svijeta (sjeverno, južno, istočno, zapadno) — stambene zgrade, institucije, prometnice, parkovi, poslovni objekti. Za svaki element navedi naziv i kratki opis. Završi napomenom o urednosti i održanosti okoliša. Minimalno 8 rečenica.",
  "nacini_pristupa": "Detaljni opis svih načina pristupa: pješački pristupi (s kojih ulica, nogostupima), kolni pristupi (koje prometnice), javni prijevoz (koje linije, koje stanice, koliko hoda), servisni i interventni pristupi. Navedi i moguća ograničenja prometa. Minimalno 6 rečenica.",
  "frekvencija": "Detaljna analiza frekvencije prometa u tri perioda: RADNI DANI (jutarnji vrhunac 07-09h, popodnevni vrhunac 15-18h, ostali dio dana), VIKEND (subota i nedjelja danju, navečer), NOĆNI SATI (22-06h). Za svaki period opiši intenzitet i vrstu prometa. Minimalno 10 rečenica.",
  "kriminalitet": "Opis stanja kriminaliteta u okolnom prostoru: opća sigurnosna situacija u kvartu, tipični incidenti koji se bilježe, preventivne mjere koje postoje (rasvjeta, nadzor, blizina institucija), zaključak o razini sigurnosti. Minimalno 5 rečenica."
}}""",

            "t22": f"""{base_ctx}

Generiraj sadržaj za tablicu 2.2 - Osnovne karakteristike u stilu profesionalnog sigurnosnog elaborata. Odgovori ISKLJUČIVO u JSON formatu:
{{
  "prostorna": "Detaljan opis prostorne organiziranosti lokacije i njene neposredne okoline: urbanistički raspored, funkcionalne zone, komunikacijski koridori, odnos prema okolnoj gradskoj matrici, posebnosti lokacije. Minimalno 8 rečenica.",
  "velicina": "Opis veličine i namjene: procjena površine ili kapaciteta, geometrijski oblik, pretežna namjena i udio pojedinih namjena (stambena, poslovna, sportska, javna), planirana namjena. Minimalno 5 rečenica."
}}""",

            "t25": f"""{base_ctx}

Generiraj sadržaj za tablicu 2.5 - Namjena u stilu profesionalnog sigurnosnog elaborata. Odgovori ISKLJUČIVO u JSON formatu:
{{
  "opca_namjena": "Formalni opis opće namjene lokacije i objekta/površine: pravna i urbanistička namjena, vlasnik ili upravljač, kategorija objekta. Minimalno 4 rečenice.",
  "namjena_prostora": "Detaljna namjena pojedinih prostora: navedi sve funkcionalne zone i njihovu namjenu (sportska/natjecateljska zona, ulazna zona, tehnički prostori, ugostiteljski sadržaji, parkiralište itd.). Za svaku zonu kratki opis. Minimalno 10 rečenica.",
  "radno_vrijeme": "Radno vrijeme svih relevantnih sadržaja na lokaciji ili u blizini: kada je objekt dostupan, kada rade prateći sadržaji, posebnosti za dane događaja. Minimalno 4 rečenice.",
  "put_kretanja": "Sistematičan opis puteva kretanja: pješaci (unutarnje komunikacije, pristupni putevi), vozila (kolni pristupi, parkiranje), službene osobe i sportaši (posebni pristupi), interventna vozila (servisni pristupi, evakuacijski koridori). Minimalno 8 rečenica.",
  "zakljucavanje": "Opis načina zaključavanja i kontrole pristupa: je li prostor ograđen, na koji način se kontrolira ulaz, tko ima pristup izvan radnog vremena, sustav zaključavanja. Minimalno 4 rečenice."
}}""",

            "t27": f"""{base_ctx}

Generiraj sadržaj za tablicu 2.7 - Vrsta i visina vrijednosti u stilu profesionalnog sigurnosnog elaborata. Odgovori ISKLJUČIVO u JSON formatu:
{{
  "vrste": "Sistematičan popis i opis svih vrsta vrijednosti: LJUDSKE I DRUŠTVENE VRIJEDNOSTI (sigurnost posjetitelja, javni red), MATERIJALNE I FINANCIJSKE VRIJEDNOSTI (infrastruktura, oprema, imovina korisnika), EKOLOŠKE I URBANE VRIJEDNOSTI (zelene površine, javni prostor). Za svaku kategoriju detaljni opis. Minimalno 10 rečenica.",
  "visina": "Procjena razine i visine vrijednosti: financijska vrijednost investicije ili imovine, razina rizika (visoka/srednja/niska), obrazloženje procjene. Minimalno 3 rečenice.",
  "cuvanje": "Opis svih načina čuvanja vrijednosti: fizičke mjere (ograde, rasvjeta), tehnički nadzor (kamere, alarmi), organizacijske mjere (ophodnje, suradnja s policijom), prirodni nadzor (okruženje, prisutnost ljudi). Minimalno 8 rečenica."
}}""",

            "t210": f"""{base_ctx}

Generiraj sadržaj za tablicu 2.10 - Uočeni nedostaci u stilu profesionalnog sigurnosnog elaborata. Odgovori ISKLJUČIVO u JSON formatu:
{{
  "nedostaci": "Detaljni opis uočenih nedostataka s aspekta sigurnosti, podijeljen u kategorije (npr. POVEĆANI SIGURNOSNI RIZICI, RIZIK OD VANDALIZMA, INFRASTRUKTURNI NEDOSTACI, ORGANIZACIJSKI NEDOSTACI). Za svaku kategoriju navedi konkretan nedostatak i obrazloženje zašto je to nedostatak. Minimalno 10 rečenica."
}}""",

            "t211": f"""{base_ctx}

Generiraj sadržaj za tablicu 2.11 - Kritične točke i ugroženi prostori u stilu profesionalnog sigurnosnog elaborata. Odgovori ISKLJUČIVO u JSON formatu:
{{
  "kriticne": "Popis i opis kritičnih točaka — za svaku točku navedi: naziv/lokaciju, rizik (vrstu i razinu), opis zašto je to kritična točka i što se konkretno može dogoditi. Minimalno 4 kritične točke, svaka detaljno opisana. Minimalno 10 rečenica ukupno.",
  "ugrozeni": "Popis i opis ugroženih prostora — za svaku zonu navedi: obuhvat/lokaciju, vrstu ugroze, uzrok ugroženosti. Minimalno 4 ugrožena prostora, svaki detaljno opisan. Minimalno 10 rečenica ukupno."
}}"""
        }

        tables = {}
        for key, prompt in prompts.items():
            text, err = self._gemini_call(
                [{"role": "user", "content": prompt}],
                max_tokens=2000
            )
            if err or not text:
                tables[key] = {}
                print(f"Greška za {key}: {err}")
                continue
            try:
                text = text.strip()
                if text.startswith("```"):
                    text = text.split("\n", 1)[1]
                    text = text.rsplit("```", 1)[0]
                tables[key] = json.loads(text.strip())
            except Exception as e:
                tables[key] = {}
                print(f"JSON parse greška za {key}: {e}\nTekst: {text[:200]}")

        # Write input JSON for Node.js
        doc_data = {
            "address": address, "lat": lat, "lon": lon,
            "radius": radius, "tables": tables,
            "static": {
                "t23_mat": t23_mat, "t23_nagib": t23_nagib, "t23_elementi": t23_elementi,
                "t24_el": t24_el, "t24_ost": t24_ost, "t26": t26,
                "t28_tjelesna": t28_tjelesna, "t28_tehnicka": t28_tehnicka, "t28_org": t28_org,
                "t29_postojeci": t29_postojeci, "t29_dok": t29_dok,
            }
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json',
                                         delete=False, encoding='utf-8') as f:
            json.dump(doc_data, f, ensure_ascii=False)
            input_path = f.name

        output_path = input_path.replace('.json', '.docx')

        try:
            result = subprocess.run(
                ["node", GEN_SCRIPT, input_path, output_path],
                capture_output=True, text=True, timeout=30
            )
            if result.returncode != 0 or not os.path.exists(output_path):
                raise Exception(result.stderr or "Generiranje dokumenta nije uspjelo")

            safe_addr = "".join(c if c.isalnum() or c in ' -_' else '_' for c in address[:40])
            filename = f"procjena_{safe_addr}.docx".replace(' ', '_')
            self.send_file(output_path, filename)
        except Exception as e:
            self.send_json({"error": str(e)}, 500)
        finally:
            for p in [input_path, output_path]:
                try: os.unlink(p)
                except: pass


if __name__ == "__main__":
    if not GEMINI_API_KEY:
        print("UPOZORENJE: GEMINI_API_KEY nije postavljen!")
    if not os.path.exists(GEN_SCRIPT):
        print(f"UPOZORENJE: generate_doc.js nije pronađen na {GEN_SCRIPT}")
    print(f"Server pokrenut na portu {PORT}")
    server = http.server.HTTPServer(("0.0.0.0", PORT), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Server zaustavljen.")

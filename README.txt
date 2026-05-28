# Okolica.ai — Upute za pokretanje

## Što trebaš
- Python 3 (vjerojatno već instaliran — provjeri s `python --version` ili `python3 --version`)
- Anthropic API ključ (besplatno na https://console.anthropic.com/)

## Koraci

### 1. Postavi API ključ
Otvori `server.py` u bilo kojem tekst editoru (Notepad, VS Code...) i pronađi liniju:

    ANTHROPIC_API_KEY = "TVOJ_API_KLJUC_OVDJE"

Zamijeni `TVOJ_API_KLJUC_OVDJE` sa svojim pravim ključem, npr.:

    ANTHROPIC_API_KEY = "sk-ant-api03-abc123..."

### 2. Pokretanje servera

**Windows:**
Otvori Command Prompt (cmd) u mapi gdje su datoteke i pokreni:

    python server.py

ili dvoklikom na `pokreni.bat` (ako postoji)

**Mac/Linux:**
Otvori Terminal i pokreni:

    python3 server.py

### 3. Otvori aplikaciju
Otvori browser i idi na:

    http://localhost:8765

### 4. Zaustavljanje
Pritisni `Ctrl+C` u terminalu.

---

## Datoteke
- `server.py` — Python server (proxy za API pozive)
- `index.html` — frontend aplikacije
- `README.txt` — ove upute

## Kako radi
1. Server preuzima geocoding zahtjeve i šalje ih Nominatim (OpenStreetMap)
2. Dohvaća objekte u blizini putem Overpass API-ja
3. Šalje podatke Claude AI-ju koji generira opis kvarta
4. Sve se prikazuje kao kompas s 8 smjerova (S, SI, I, JI, J, JZ, Z, SZ)

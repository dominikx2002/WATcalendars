###### _<div align="right"><sub>Designed by Dominik Serafin</sub></div>_

<div align="center">
  <a href="https://dominikx2002.github.io/WATcalendars/">
    <img alt="WATcalendars" src="https://raw.githubusercontent.com/dominikx2002/watcalendars-assets/main/watcalendars-logo/title-logo.png">
  </a>

  <p>
    <a href="https://dominikx2002.github.io/WATcalendars/"><img src="https://img.shields.io/badge/Strona-0a5c42?style=for-the-badge&logo=google-chrome&logoColor=white" alt="Strona"></a>
    <a href="#dla-studentów"><img src="https://img.shields.io/badge/Jak_zacząć-2ea043?style=for-the-badge&logo=apple&logoColor=white" alt="Jak zacząć"></a>
    <a href="docs/architecture.md"><img src="https://img.shields.io/badge/Architektura-1f6feb?style=for-the-badge&logo=readthedocs&logoColor=white" alt="Architektura"></a>
    <a href="https://github.com/dominikx2002/WATcalendars/issues"><img src="https://img.shields.io/badge/Zgłoś_błąd-555555?style=for-the-badge&logo=github&logoColor=white" alt="Zgłoś błąd"></a>
  </p>

  <p>
    <img src="https://raw.githubusercontent.com/dominikx2002/watcalendars-assets/main/faculties/logo/ioe_logo.png" alt="IOE" width="56">
    <img src="https://raw.githubusercontent.com/dominikx2002/watcalendars-assets/main/faculties/logo/wcy_logo.png" alt="WCY" width="56">
    <img src="https://raw.githubusercontent.com/dominikx2002/watcalendars-assets/main/faculties/logo/wel_logo.png" alt="WEL" width="56">
    <img src="https://raw.githubusercontent.com/dominikx2002/watcalendars-assets/main/faculties/logo/wig_logo.png" alt="WIG" width="56">
    <img src="https://raw.githubusercontent.com/dominikx2002/watcalendars-assets/main/faculties/logo/wim_logo.png" alt="WIM" width="56">
    <img src="https://raw.githubusercontent.com/dominikx2002/watcalendars-assets/main/faculties/logo/wlo_logo.png" alt="WLO" width="56">
    <img src="https://raw.githubusercontent.com/dominikx2002/watcalendars-assets/main/faculties/logo/wml_logo.png" alt="WML" width="56">
    <img src="https://raw.githubusercontent.com/dominikx2002/watcalendars-assets/main/faculties/logo/wtc_logo.png" alt="WTC" width="56">
  </p>
</div>

---

Plan zajęć Wojskowej Akademii Technicznej w kalendarzu telefonu — taki,
który aktualizuje się sam.

Każdy wydział WAT publikuje rozkład po swojemu: jeden ma własną
aplikację, sześć generuje statyczne strony, jeden wystawia pliki Worda.
Ten projekt co noc odwiedza wszystkie osiem, parsuje plany i zapisuje je
jako pliki `.ics`, które da się zasubskrybować w Kalendarzu Apple,
Google, Outlooku czy Thunderbirdzie.

<br>

## Dla studentów

Wejdź na **[watcalendars.byst.re](https://watcalendars.byst.re)**, wpisz
kod swojej grupy i kliknij *Dodaj do kalendarza*. To wszystko — plan
pojawi się w telefonie i będzie się odświeżał bez Twojego udziału.

<p align="center">
  <img src="https://raw.githubusercontent.com/dominikx2002/watcalendars-assets/main/iphone_day.jpeg" alt="Widok dzienny iOS" height="420">
  <img src="https://raw.githubusercontent.com/dominikx2002/watcalendars-assets/main/iphone-detailed-view.png" alt="Szczegóły zajęć" height="420">
</p>

Nie znasz kodu grupy? Na stronie wybierz swój wydział i przejrzyj listę.

<br>

## Dla programistów

### Instalacja

```bash
git clone https://github.com/dominikx2002/WATcalendars.git
cd WATcalendars

python3 -m venv .venv && source .venv/bin/activate
pip install -e .
playwright install firefox chromium
```

Wymagany Python 3.9+. Przeglądarki Playwrighta są potrzebne tylko dla
wydziałów za firewallem aplikacyjnym — WCY i WIM pobierają się zwykłym
HTTP.

### Uruchamianie

Jedna komenda obsługuje cały projekt:

```bash
watcal list                 # co jest skonfigurowane
watcal run all              # grupy + kalendarze dla wszystkich wydziałów
watcal run wcy wim          # tylko wybrane
watcal groups wel           # sam etap wykrywania grup
watcal calendars wel        # same kalendarze (wymaga wcześniej groups)
watcal employees            # lista pracowników z USOSweb
watcal index                # przebuduj indeks dla strony
```

Przydatne przełączniki:

```bash
watcal -v calendars wel                 # DEBUG: każde żądanie, status, rozmiar, czas
watcal --log-file logs/run.txt run all  # plik zawsze dostaje DEBUG
watcal --semester lato groups wim       # wymuś semestr zamiast wykrywania po dacie
```

Odpowiednik nocnego zadania z CI, do uruchomienia lokalnie:

```bash
./scripts/daily.sh              # wszystko, do db/
DRY=1 ./scripts/daily.sh wim    # do katalogu tymczasowego, db/ nietknięte
```

### Testy

```bash
pytest                      # 79 testów, ~0.5 s
```

<br>

## Jak to działa

```
   FacultySpec (faculties/<kod>.py)
        │  skąd, czym pobrać, czym sparsować
        ▼
   core/pipeline.py  ← jeden przebieg wspólny dla wszystkich wydziałów
        │
        ├─ fetch/     http | browser | browser_slow | docx
        ├─ parsers/   jeden moduł na wydział — tu wolno się różnić
        └─ store/     ics | groups | employees — wspólne dla wszystkich
```

Zasada podziału: **wspólne jest pobieranie, orkiestracja i zapis, osobne
tylko parsowanie**. ICS to jeden standard, więc duplikowanie zapisu
oznaczałoby osiem identycznych poprawek przy każdej zmianie. HTML
wydziałów naprawdę się różni i zmienia niezależnie — tam izolacja chroni
pozostałe wydziały przed skutkami przebudowy jednej strony.

### Dodanie wydziału

Jeden plik `src/watcalendars/faculties/<kod>.py`:

```python
SPEC = FacultySpec(
    code="xyz",
    name="Wydział XYZ",
    groups_url={"zima": "...", "lato": "..."},
    schedule_url="https://.../{group}.htm",
    parse_groups=plansoft.parse_groups,       # gotowy, jeśli Plansoft
    parse_schedule=parsers.schedule.xyz.parse_schedule,
    seasonal=True,
    fetch_strategy="http",
)
```

…plus jedna linia w `core/registry.py`. Żadnego nowego `main()`, writera,
wpisu w `pyproject.toml` ani w workflow. `tests/test_specs.py` od razu
sprawdzi, czy spec jest poprawny.

### Źródła danych

| Wydział | Źródło | Pobieranie |
|---------|--------|-----------|
| WCY | własna aplikacja Drupal, renderowana serwerowo | HTTP |
| WIM | statyczne pliki Plansoft | HTTP |
| IOE, WEL, WLO, WML, WTC | Plansoft za Imperva/Incapsula | przeglądarka |
| WIG | dwupoziomowa lista Joomla → pliki `.docx` | przeglądarka |

Sześć wydziałów publikuje przez **Plansoft.org**: `index.xml` z listą
grup i `<GRUPA>.htm` z planem. Listę czytamy z XML-a, nie z widoku
wyrenderowanego przez XSLT.

> **WAT ma publiczne USOS API** (`usosapps.wat.edu.pl`), a metoda
> `tt/classgroup_dates2` działa bez klucza — ale rozkłady są tam puste.
> Planowanie zajęć odbywa się poza USOS-em i dlatego istnieje osiem
> osobnych stron wydziałowych. Szczegóły w
> [docs/architecture.md](docs/architecture.md).

<br>

## Strona

Strona (`index.html`, `assets/`) serwuje się z **GitHub Pages prosto z
tej gałęzi**, dzięki czemu pliki `.ics` leżą pod tym samym adresem —
bez CORS, bez limitów API i bez osobnego hostingu.

Włączenie (raz): *Settings → Pages → Deploy from a branch → `main`,
katalog `/ (root)`*. Plik `.nojekyll` jest już w repo.

Podgląd lokalny:

```bash
python3 -m http.server 8000     # http://localhost:8000
```

Strona czyta `db/calendars/index.json` — listę grup z liczbą zajęć,
odświeżaną automatycznie po etapie `calendars`.

<br>

## Struktura repozytorium

```
src/watcalendars/
├── cli.py            jedyny punkt wejścia (watcal)
├── core/             models, registry, pipeline, semester, logging, paths
├── fetch/            http, browser, downloads, strategies
├── parsers/          schedule/<kod>.py, groups/<kod>.py
├── store/            ics, groups, employees, index
└── faculties/        po jednym FacultySpec na wydział + plansoft.py

db/                   dane: konfiguracja, grupy, wygenerowane kalendarze
docs/architecture.md  decyzje projektowe i stan źródeł
scripts/daily.sh      lokalny odpowiednik nocnego zadania CI
tests/                79 testów
```

<br>

## Automatyzacja

`.github/workflows/full_scrape.yml` uruchamia się codziennie o północy
UTC i commituje wyniki. Można go też odpalić ręcznie:

```bash
gh workflow run full_scrape.yml -f faculties="wcy wim" -f semester=zima
```

Awaria jednego wydziału nie zatrzymuje pozostałych. Log każdego przebiegu
trafia do artefaktu `scrape-log` (14 dni).

<br>

## Współpraca

Znalazłeś błąd w planie albo brakuje Twojej grupy?
[Otwórz issue](https://github.com/dominikx2002/WATcalendars/issues) —
przydatny będzie kod grupy i wydział.

Kontakt: [serafin652002@gmail.com](mailto:serafin652002@gmail.com)

<br>

## Licencja

MIT — [LICENSE](LICENSE). Dane rozkładów należą do Wojskowej Akademii
Technicznej; ten projekt jedynie je przetwarza do formatu iCalendar.

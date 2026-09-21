# Architektura

## Przepływ

```
   FacultySpec (faculties/<kod>.py)
        │  mówi: skąd, czym pobrać, czym sparsować
        ▼
   core/pipeline.py  ← jedyny "main", wspólny dla wszystkich wydziałów
        │
        ├─ fetch/      http | browser | browser_slow | docx
        ├─ parsers/    jeden moduł na wydział (tu wolno się różnić)
        └─ store/      ics | groups | employees  (wspólne dla wszystkich)
```

Zasada podziału:

> **Wspólne: orkiestracja, pobieranie, zapis. Osobne: parsowanie.**

ICS to jeden standard — duplikowanie zapisu oznaczałoby, że poprawka
strefy czasowej wymaga ośmiu identycznych edycji. HTML wydziałów
naprawdę się różni i zmienia niezależnie — tam izolacja chroni pozostałe
wydziały przed skutkami przebudowy jednej strony.

## Dodanie wydziału

Jeden plik `src/watcalendars/faculties/<kod>.py`:

```python
SPEC = FacultySpec(
    code="xyz",
    name="Wydział XYZ",
    groups_url={"zima": "...", "lato": "..."},   # albo pojedynczy str
    schedule_url="https://.../{group}.htm",
    parse_groups=plansoft.parse_groups,          # gotowy, jeśli Plansoft
    parse_schedule=parsers.schedule.xyz.parse_schedule,
    seasonal=True,
    fetch_strategy="http",
)
```

plus jedna linia w `core/registry.py`. Nic więcej — żadnego nowego
`main()`, writera ani wpisu w `pyproject.toml` czy w workflow.

`tests/test_specs.py` sprawdzi od razu, czy spec jest poprawny
(szablon `{group}`, komplet semestrów, znana strategia pobierania).

## Strategie pobierania

Ustalone empirycznie, testem na żywych serwerach (2026-09):

| Strategia      | Wydziały           | Dlaczego |
|----------------|--------------------|----------|
| `http`         | WCY, WIM           | zwykły GET wystarcza — ~20× szybciej niż przeglądarka |
| `browser`      | IOE, WEL, WTC      | Imperva/Incapsula zwraca 403 na czysty HTTP |
| `browser_slow` | WLO, WML           | j.w., z łagodniejszą równoległością |
| `docx`         | WIG                | plany to pliki Word, nie HTML |

`browser` **nie renderuje stron**. Używa `context.request.get()` — czyli
stosu sieciowego przeglądarki (jej odcisk TLS przechodzi przez Incapsulę),
ale zwraca bajty tak, jak je podano. To ma dwa powody:

1. `page.content()` zwraca *wyrenderowany DOM*, więc `index.xml` przychodził
   jako 270 kB HTML-a zamiast 21 kB XML-a.
2. Jest wielokrotnie szybsze — WLO: 164 grupy w 2 min zamiast ~25 min.

Jeśli bezpośrednie żądanie dostanie odmowę, kod raz nawiguje przeglądarką,
żeby przejść wyzwanie JS, i ponawia żądanie.

## Stan źródeł (sprawdzony 2026-09-21)

| Wydział | Grupy | Wydarzenia | Pobieranie |
|---|---|---|---|
| WCY | 184 | 46 730 | HTTP |
| WIM | 95 | 45 397 | HTTP |
| WEL | 173 | ~12 200 | browser |
| WLO | 164 | 31 408 | browser |
| WML | 180 | 33 182 | browser |
| WTC | 22 | 4 776 | browser |
| IOE | 18 | 3 493 | browser |
| WIG | 37 | — | browser + docx — **niezweryfikowane** |

Zmiany adresów wykryte i naprawione 2026-09-21:

- **WEL**: `plany.wel.wat.edu.pl` → **NXDOMAIN**. Nowy adres:
  `https://wel.wat.edu.pl/planyzajec/{zima,lato}/index.xml`.
- **WTC**: wariant z `www.` zwraca HTML zamiast XML — działa
  `https://wtc.wat.edu.pl/Plany/index.xml` (bez `www.`).
  Dodatkowo `index.xml` wymienia wyłącznie `.pdf`, ale **bliźniacze
  pliki `.htm` nadal są serwowane** (22/22) i to je pobieramy —
  parser PDF okazał się niepotrzebny.
- **WML**: stary URL przypinał folder `2025_sem_lato`. Wydział publikuje
  pod `<rok>_sem_<semestr>/index.xml`, gdzie `<rok>` to rok rozpoczęcia
  roku akademickiego. Placeholder `{year}` jest podstawiany w czasie
  działania, więc nie wymaga corocznej edycji.
- **IOE**: `ioe.wat.edu.pl` jest aliasem na `www.wat.edu.pl`;
  `plany/zima/` zwraca 404, a `plany/lato/` zawiera plan **zimowy**
  (pole period: `IOE-Zima2026`). Dlatego IOE jest `seasonal=False`.
  Cztery wpisy PDF w indeksie to dokumenty pomocnicze (Siatka Godzin,
  Harmonogram RA), nie plany grup — filtr HTML słusznie je pomija.
- **WIG**: pobieranie `.docx` szło przez nasłuch zdarzenia `download`
  w Playwrighcie, które za Incapsulą nigdy nie następuje — 37 plików ×
  30 s timeoutu = 19 min i zero pobranych dokumentów. Zamienione na
  `context.request.get()` z jednorazowym rozgrzaniem sesji. **Ta zmiana
  nie została zweryfikowana na żywo**, bo w trakcie prac adres IP
  wpadł w blokadę Impervy.

### Limity Impervy — ważne operacyjnie

Sześć wydziałów stoi za Imperva/Incapsula, a reputacja liczona jest
**per adres IP**. W pełnym przebiegu `run all` (30 min ciągłego ruchu,
w tym 37 nieudanych pobrań WIG) ostatnie w kolejce wydziały — WML i WTC —
zaczęły dostawać 403, mimo że osobno działały bez zarzutu. Blokada
utrzymywała się jeszcze po zakończeniu przebiegu.

Dlatego CLI robi 20-sekundową przerwę przed każdym wydziałem, który nie
używa czystego HTTP (`PAUSE_BETWEEN_FACULTIES` w `cli.py`). Jeśli mimo
to zobaczysz serię 403 — odczekaj i uruchom ponownie, ewentualnie dziel
przebieg na mniejsze partie (`watcal calendars wcy wim`, potem reszta).

### Rozszerzenia w index.xml

`plansoft.parse_groups(xml, accept=...)` decyduje, które wpisy są
planami grup. Domyślnie tylko HTML. WTC nadpisuje to na
`("htm", "html", "pdf")`, bo tam PDF-y mają działające odpowiedniki HTML.
Dwa przeciwne przypadki — WTC i IOE — są powodem, dla którego to jest
parametr, a nie stała.

## Źródła danych

- **WCY** — własna aplikacja Drupal, renderowana po stronie serwera.
- **IOE, WEL, WIM, WLO, WML, WTC** — **Plansoft.org**: `index.xml`
  (lista grup, prawdziwy XML) + `<GRUPA>.htm` (plan, statyczny HTML).
  Listę grup czytamy z XML-a, nie z widoku wyrenderowanego przez XSLT.
  **Identyfikator grupy pochodzi z atrybutu `href`, nie `text`** — `text`
  zawiera polskie znaki i daje URL-e zwracające 404.
- **WIG** — dwupoziomowa lista Joomla → pliki `.docx`.

### USOS API — sprawdzone, nie nadaje się

WAT ma publiczne USOS API (`https://usosapps.wat.edu.pl`, wersja 7.3.1.0).
Metoda `services/tt/classgroup_dates2` działa **bez żadnego klucza**
(`consumer: ignored, token: ignored`), ale na 80 zbadanych jednostkach
zwróciła zero zdarzeń, a katalog widoczny anonimowo kończy się na
edycjach z 2014/15. Planowanie zajęć w WAT odbywa się poza USOS-em —
dlatego jest osiem osobnych stron wydziałowych.

Jedyne sensowne zastosowanie: dane pracowników (`services/users/*`),
ale to wymaga klucza rejestrowanego na `usosapps.wat.edu.pl/developers/`.

## Kontrakt danych

Parser zwraca listę słowników; `Lesson.from_dict` normalizuje je do
jednej dataclass i to jest **cała** umowa między warstwami:

```python
Lesson(start, end, subject, type, type_full, room,
       lesson_number, full_subject, lecturers)
```

Aliasy historyczne (`room`/`location`, `lecturer`/`lecturers`,
`full_subject`/`full_subject_name`) obsługuje `from_dict`, więc parsery
można migrować pojedynczo.

## Zmienne środowiskowe

| Zmienna | Działanie |
|---|---|
| `WATCALENDARS_SEMESTER` | wymusza `zima`/`lato` zamiast wykrywania po dacie |
| `WATCALENDARS_DB_DIR`   | przekierowuje **całe** wyjście — pozwala uruchomić pipeline na katalogu roboczym bez dotykania `db/` |
| `NO_COLOR`              | wyłącza kolory w logach |

## Logi

- Domyślnie `INFO`: czytelny przebieg.
- `-v` / `--verbose`: `DEBUG` — każde żądanie ze statusem, rozmiarem
  i czasem, konfiguracja wydziału, czasy parsowania, nazwy grup,
  powody odrzucenia zajęć.
- `--log-file PLIK`: plik **zawsze** dostaje `DEBUG`, niezależnie od
  tego, co widać na konsoli — nocny błąd da się zdiagnozować po fakcie.
- Każda linia w obrębie wydziału jest tagowana jego kodem.

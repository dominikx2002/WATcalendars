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

Wejdź na **https://dominikx2002.github.io/WATcalendars/**, wpisz
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
        ├─ parsers/   jeden moduł na wydział
        └─ store/     ics | groups | employees — wspólne dla wszystkich
```

### Źródła danych

| Wydział | Źródło | Pobieranie |
|---------|--------|-----------|
| WCY | własna aplikacja Drupal, renderowana serwerowo | HTTP |
| WIM | statyczne pliki Plansoft | HTTP |
| IOE, WEL, WLO, WML, WTC | Plansoft za Imperva/Incapsula | przeglądarka |
| WIG | dwupoziomowa lista Joomla → pliki `.docx` | przeglądarka |


<br>

## Strona

Strona (`index.html`, `assets/`) serwuje się z **GitHub Pages prosto z
tej gałęzi**, dzięki czemu pliki `.ics` leżą pod tym samym adresem —
bez CORS, bez limitów API i bez osobnego hostingu.

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

Imperva/Incapsula blokuje adresy GitHub Actions: zablokowany wydział dostaje
403 (~800 B, „Incapsula incident ID”). Po 8 takich odpowiedziach z rzędu
scraper pomija resztę grup wydziału zamiast ponawiać próby, zapisuje to,
co zdążył pobrać, i zgłasza wydział jako nieudany. Wydziały wpisane w
zmiennej repozytorium `REMOTE_FACULTIES` są przy runie `all` pomijane,
bo aktualizuje je Raspberry Pi (niżej).

<br>

## Scraping z Raspberry Pi (WCY)

WCY to zwykły HTTP (bez przeglądarki), więc wystarczy dowolna maszyna, której
Imperva nie blokuje, np. Raspberry Pi na domowym łączu.
[`scripts/remote_scrape.sh`](scripts/remote_scrape.sh) synchronizuje klon z
`origin/main`, scrapuje WCY, commituje tylko `db/calendars/wcy_calendars` i
`index.json` (`status.json` należy do workflow) i pushuje. Playwright nie
jest tam potrzebny.

Poniżej zakładam Raspberry Pi OS 64-bit i użytkownika `serafin`.

**1. Sprawdź, czy Pi w ogóle przechodzi przez WAF**

```bash
curl -s -L -c /tmp/wcy.jar -b /tmp/wcy.jar -o /dev/null \
  -w "%{http_code} %{size_download}\n" -A "Mozilla/5.0" \
  "https://planzajec.wcy.wat.edu.pl/pl/rozklad?grupa_id=WCY22KC2S0"
```

Musi być `200` i dziesiątki kB. `403` i ~800–900 B oznacza, że ten adres też
jest zablokowany i dalsze kroki nic nie dadzą. `-L` i słoik na ciasteczka
są potrzebne, bo Incapsula odpowiada najpierw `302` na ten sam adres i
ustawia ciasteczko. Bez nich zablokowany adres pokazuje mylące `302 122`.

**2. Pakiety**

```bash
sudo apt install -y git python3-venv
```

**3. Deploy key (klucz tylko do tego repo)**

```bash
ssh-keygen -t ed25519 -f ~/.ssh/watcal_deploy -N "" -C "watcal pi-cloud"
cat ~/.ssh/watcal_deploy.pub
```

Na GitHubie: repo → **Settings → Deploy keys → Add deploy key**, wklej klucz
publiczny i zaznacz **Allow write access**. Jeśli `main` ma branch
protection, deploy key musi mieć prawo ją omijać.

**4. Płytki klon, dedykowany skryptowi**

Pełna historia ma ponad 10 GB, więc klonuj z `--depth 1`. To ma być osobny
klon tylko dla skryptu: każdy przebieg robi `git reset --hard origin/main`
i kasuje lokalne zmiany.

```bash
GIT_SSH_COMMAND="ssh -i ~/.ssh/watcal_deploy -o IdentitiesOnly=yes" \
  git clone --depth 1 git@github.com:dominikx2002/WATcalendars.git ~/watcal-remote
```

**5. Pierwsze uruchomienie ręcznie**

```bash
WATCAL_DEPLOY_KEY=~/.ssh/watcal_deploy bash ~/watcal-remote/scripts/remote_scrape.sh
```

Za pierwszym razem skrypt sam tworzy `.venv` i robi `pip install -e .`
(kilka minut). Później instaluje ponownie tylko wtedy, gdy zmieni się
`pyproject.toml`. Kod wyjścia jest taki sam jak kod `watcal calendars`.

Przed scrapowaniem skrypt wysyła jedno próbne zapytanie o jedną grupę. Jeśli
dostanie 403, loguje `IP still blocked by WAF, skipping` i kończy z kodem 0,
bez scrapowania i commita, żeby nie przedłużać bana. WCY idzie sekwencyjnie,
jedno zapytanie co 4–6 s (`delay=4`, `concurrency=1`), więc ~185 grup to
około 15–20 minut. Po 3 odpowiedziach 403 z rzędu scraper przestaje pytać.

**6. Cron** (`crontab -e`)

```cron
CRON_TZ=Europe/Warsaw
WATCAL_REPO=/home/serafin/watcal-remote
WATCAL_DEPLOY_KEY=/home/serafin/.ssh/watcal_deploy
30 5 * * * /bin/bash /home/serafin/watcal-remote/scripts/remote_scrape.sh >> /home/serafin/watcal-remote.log 2>&1
```

`cron` w Raspberry Pi OS (Debian) ignoruje `CRON_TZ` i używa strefy
systemowej, więc upewnij się, że to `Europe/Warsaw` (`timedatectl`; ewentualnie
`sudo timedatectl set-timezone Europe/Warsaw`). Dwa nakładające się
przebiegi blokuje `flock`.

**7. Wyłącz WCY w GitHub Actions**

Repo → **Settings → Secrets and variables → Actions → Variables → New
repository variable**: `REMOTE_FACULTIES` = `wcy` (kilka wydziałów oddziel
spacjami). Od tej pory nocny run `all` pomija WCY i nie zgłasza go jako
błędu. Ręczny run z `faculties=wcy` nadal go scrapuje.

**8. Jak sprawdzić, że działa**

- `tail -n 30 ~/watcal-remote.log` kończy się linią `Pushed … to main`
  albo `Calendars unchanged - nothing to commit`;
- w historii repo są commity `Remote scrape: WCY (pi-cloud)`;
- szczegółowy log scrapera: `~/watcal-remote/logs/remote_<data>.txt`;
- w logu runu Actions, w kroku „Resolve faculties”, jest `Skipping wcy`,
  a `status.json` kończy się dopiskiem `WCY z Raspberry Pi`.

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

<br>

## watcal-me — własny kalendarz z e-Dziekanatu (WCY)

Odkąd `planzajec.wcy` jest za Impervą, planu WCY nie da się pobierać
anonimowo. `watcal-me` loguje się Twoimi danymi do **e-Dziekanatu**
(`s1.wcy.wat.edu.pl`) i czyta plan **Twojej grupy**. Plan grupy jest ten
sam dla wszystkich w grupie, więc powstały `.ics` jest ważny dla całej
grupy i można go wrzucić do wspólnego repo.

**Dane logowania nigdy nie są zapisywane ani logowane** — idą tylko do
e-Dziekanatu po HTTPS. Narzędzie bierze je z `WATCAL_ME_USER` /
`WATCAL_ME_PASS` albo pyta w terminalu (`getpass`).

```bash
# interaktywnie (pyta o identyfikator i hasło)
watcal-me --group WCY22KC2S0 --out moj_plan.ics

# nieinteraktywnie (np. cron / Actions)
export WATCAL_ME_USER="Imie Nazwisko"
export WATCAL_ME_PASS="haslo"
watcal-me --group WCY22KC2S0        # zapis do db/calendars/wcy_calendars/...
```

Jak przy scraperach wydziałów: jeśli logowanie się nie uda albo plan
wyjdzie pusty, istniejący `.ics` **nie jest nadpisywany**.

**Sale:** w domyślnym („uproszczonym”) widoku e-Dziekanatu numery sal są
zakodowane niejednoznacznie, więc `LOCATION` zostaje pusty (lepiej pusto
niż błędnie). Pełne sale wymagają widoku „dane pełne” — do dołożenia.

### Automatyczna aktualizacja przez GitHub Actions

e-Dziekanat jest osiągalny z serwerów GitHuba, więc kalendarz grupy może
się odświeżać bez żadnego sprzętu. W **Twoim** repo:

1. **Settings → Secrets and variables → Actions → Secrets:** dodaj
   `EDZIEKANAT_USER` i `EDZIEKANAT_PASS` (Twoje dane do e-Dziekanatu).
   Sekrety są zamaskowane w logach; to Twoje konto i Twoje repo.
2. **Variables:** dodaj `ME_GROUP` = `WCY22KC2S0` (Twoja grupa).
3. Workflow `.github/workflows/me-edziekanat.yml` odpala się codziennie
   i commituje `WCY22KC2S0.ics`. Subskrybenci (Google/Apple Calendar)
   dociągają nowy plik sami.

Dla innych grup: każdy robi to **u siebie** (swój fork, swoje sekrety).
Nikt nie oddaje nikomu hasła — zbieranie cudzych haseł do e-Dziekanatu na
jednej stronie odpada (phishing + RODO).

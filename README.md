###### _<div align="right"><sub>Designed by Dominik Serafin</sub></div>_

<div align="center">
  <a href="https://watcalendars.byst.re">
    <img alt="WATcalendars-banner" src="https://raw.githubusercontent.com/dominikx2002/watcalendars-assets/main/watcalendars-logo/title-logo.png">
  </a>
</div>

<div align="center">

<p align="center">
  <a href="https://watcalendars.byst.re">
    <img src="https://img.shields.io/badge/Website-2ea44f?style=for-the-badge&logo=google-chrome&logoColor=white" alt="Website">
  </a>
  <a href="https://github.com/WATcalendars-Project/WATcalendars/wiki">
    <img src="https://img.shields.io/badge/Wiki-6f42c1?style=for-the-badge&logo=wikipedia&logoColor=white" alt="Wiki">
  </a>
  <a href="https://github.com/WATcalendars-Project/WATcalendars/wiki/Poradnik-do-importowania-kalendarzy">
    <img src="https://img.shields.io/badge/Tutorial-orange?style=for-the-badge&logo=read-the-docs&logoColor=white" alt="Tutorial">
  </a>
  <a href="https://github.com/WATcalendars-Project/WATcalendars/wiki/Instalacja-i-Konfiguracja">
    <img src="https://img.shields.io/badge/Installation-blue?style=for-the-badge&logo=terminal&logoColor=white" alt="Installation">
  </a>
  <a href="#contact">
    <img src="https://img.shields.io/badge/Contact-555555?style=for-the-badge&logo=maildotru&logoColor=white" alt="Contact">
  </a>
</p>

</div>

<br>

<div align="center">
  <div style="display: flex; flex-wrap: nowrap; justify-content: center;">
    <img src="https://raw.githubusercontent.com/dominikx2002/watcalendars-assets/main/faculties/logo/ioe_logo.png" alt="IOE" style="width: 10%; margin: 30px;"/>
    <img src="https://raw.githubusercontent.com/dominikx2002/watcalendars-assets/main/faculties/logo/wcy_logo.png" alt="WCY" style="width: 10%; margin: 30px;"/>
    <img src="https://raw.githubusercontent.com/dominikx2002/watcalendars-assets/main/faculties/logo/wel_logo.png" alt="WEL" style="width: 10%; margin: 30px;"/>
    <img src="https://raw.githubusercontent.com/dominikx2002/watcalendars-assets/main/faculties/logo/wig_logo.png" alt="WIG" style="width: 10%; margin: 30px;"/>
    <img src="https://raw.githubusercontent.com/dominikx2002/watcalendars-assets/main/faculties/logo/wim_logo.png" alt="WIM" style="width: 10%; margin: 30px;"/>
    <img src="https://raw.githubusercontent.com/dominikx2002/watcalendars-assets/main/faculties/logo/wlo_logo.png" alt="WLO" style="width: 10%; margin: 30px;"/>
    <img src="https://raw.githubusercontent.com/dominikx2002/watcalendars-assets/main/faculties/logo/wml_logo.png" alt="WML" style="width: 10%; margin: 30px;"/>
    <img src="https://raw.githubusercontent.com/dominikx2002/watcalendars-assets/main/faculties/logo/wtc_logo.png" alt="WTC" style="width: 10%; margin: 30px;"/>
  </div>
</div>

<br>

### O projekcie

**WATcalendars** to zautomatyzowane narzędzie stworzone dla studentów Wojskowej Akademii Technicznej. Ułatwia zarządzanie planem zajęć, konwertując oficjalne harmonogramy uczelni do nowoczesnego, cyfrowego formatu.

Oficjalny system planów zajęć często wymaga ręcznego sprawdzania i może być niewygodny na urządzeniach mobilnych. Ten projekt działa jako most między danymi uczelni a Twoim osobistym kalendarzem. Skrypt automatycznie pobiera najnowsze dane z witryn wydziałowych i generuje standardowy plik `.ics` (iCal).

Pełne informacje znajdziesz w [Wiki WATcalendars](https://github.com/WATcalendars-Project/WATcalendars/wiki).

Instrukcje importowania harmonogramu do urządzeń mobilnych dostępne są na [oficjalnej stronie](https://watcalendars.byst.re).

<br>

<p align="center">
  <img src="https://raw.githubusercontent.com/dominikx2002/watcalendars-assets/main/iphone_day.jpeg" 
       alt="Widok dzienny iOS" 
       style="object-fit: cover; height: 600px; vertical-align: middle; display: inline-block;">
  <img src="https://raw.githubusercontent.com/dominikx2002/watcalendars-assets/main/iphone-detailed-view.png" 
       alt="Szczegółowy widok iOS" 
       style="object-fit: cover; height: 500px; vertical-align: middle; display: inline-block;">
</p>

<br>

<br>

## Użycie

```bash
pip install -e .
playwright install firefox chromium

watcal list                 # co jest skonfigurowane
watcal groups all           # wykryj grupy wszystkich wydziałów
watcal calendars wcy wim    # zbuduj .ics dla wybranych
watcal run all              # grupy + kalendarze
watcal employees            # odśwież listę pracowników z USOSweb
```

Przydatne przełączniki:

```bash
watcal -v calendars wel                 # logi DEBUG: każde żądanie, status, rozmiar, czas
watcal --log-file logs/run.txt run all  # plik zawsze dostaje DEBUG
watcal --semester lato groups wim       # wymuś semestr zamiast wykrywania po dacie
```

Opis struktury katalogów, strategii pobierania i sposobu dodania
kolejnego wydziału: [`docs/architecture.md`](docs/architecture.md).

<br>

<a id="contact"></a>
## CONTACT

Masz pytania, sugestie lub chcesz zgłosić problem? Skontaktuj się ze mną:

* **GitHub:** [Otwórz Issue](https://github.com/WATcalendars-Project/WATcalendars/issues) lub rozpocznij [Dyskusję](https://github.com/WATcalendars-Project/WATcalendars/discussions)
* **Email:** [serafin652002@gmail.com](mailto:serafin652002@gmail.com)

<br>

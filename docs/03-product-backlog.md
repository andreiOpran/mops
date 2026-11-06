# Product Backlog inițial - Platforma web de monitorizare real-time a întârzierilor STB


## 1. Metoda de prioritizare

Fiecare User Story primește:

- o categorie **MoSCoW**:
  - **Must**: fără ea produsul nu își atinge Product Goal-ul;
  - **Should**: valoare mare, dar produsul funcționează și fără ea;
  - **Could**: de dorit, dacă rămâne timp;
  - **Won't**: exclusă din această versiune;
- un **rang unic** (1 = cea mai prioritară), care stabilește ordinea în backlog;
- o **justificare** de un rând.

Decizii ale echipei care au stat la baza propunerii:

- **Must** = colectarea datelor și statisticile istorice (nucleul Product Goal-ului).
- Restul funcționalităților (export, timp real, hartă, clasamente, conturi, API) sunt Should sau Could.

## 2. Product Backlog

Coloana SP conține estimarea de referință din [04-estimare.md](04-estimare.md). Valorile se înlocuiesc cu cele stabilite prin Planning Poker.

| Rang | ID | User Story | MoSCoW | SP (ref.) | Depinde de | Justificarea priorității |
|---:|---|---|---|---|---|---|
| 1 | US-01 | Importul orarului GTFS | Must | 5 | - | Fără orar nu se poate calcula nicio întârziere. |
| 2 | US-02 | Detectarea sosirilor în stații | Must | 13 | US-01, T-01 | Nucleul produsului. Procesează instantaneele arhivate de T-01, inclusiv cele colectate înainte de Sprint. |
| 3 | US-03 | Calculul și stocarea întârzierii | Must | 5 | US-01, US-02 | Produce setul de date pe care se bazează toate celelalte funcționalități. |
| 4 | US-04 | Căutarea unei linii sau stații | Must | 3 | US-01 | Punctul de intrare pentru toate vizualizările. |
| 5 | US-05 | Statisticile unei linii | Must | 5 | US-03, US-04 | Prima valoare vizibilă, utilă tuturor categoriilor de utilizatori. |
| 6 | US-06 | Întârzierile unei linii la stația mea | Must | 3 | US-05 | Nevoia principală a călătorului. |
| 7 | US-07 | Tipare pe ore și zile | Must | 5 | US-05 | Nevoia principală a planificatorului. |
| 8 | US-08 | Distribuția întârzierilor | Must | 3 | US-05 | Completează media cu informații despre regularitate. |
| 9 | US-09 | Acoperirea datelor | Should | 5 | US-02 | Arată cât de complete sunt datele; fără ea, statisticile pot induce în eroare. |
| 10 | US-10 | Exportul datelor în CSV | Should | 3 | US-03 | Valoare mare pentru analiști, efort relativ redus. |
| 11 | US-11 | Sosiri live într-o stație | Should | 8 | US-01, US-02 | Folosește aceleași fluxuri ca și colectarea; atractivă pentru călători. |
| 12 | US-12 | Harta vehiculelor | Should | 5 | US-11 | Refolosește datele în timp real; util la demonstrație. |
| 13 | US-13 | Clasamentul liniilor și stațiilor | Could | 5 | US-05 | Agregare peste statisticile existente. |
| 14 | US-14 | Cont de utilizator | Could | 8 | - | Necesar doar pentru favorite. |
| 15 | US-15 | Favorite și panou personal | Could | 5 | US-14, US-05 | Personalizare; nu afectează setul de date. |
| 16 | US-16 | API public | Could | 5 | US-05, US-10 | Documentația OpenAPI este generată de FastAPI, dar un API public cere limitarea cererilor și o interfață stabilă. |

### Task-uri tehnice (enablers)

Task-uri fără valoare directă pentru utilizator, necesare pentru User Stories. Nu sunt User Stories și nu intră în calculul User Stories implementate. Se urmăresc în GitHub Projects ca orice task.

| ID | Task | Pentru | Cerințe | Motiv |
|---|---|---|---|---|
| T-01 | Colector brut pe VPS: arhivarea fluxurilor Vehicle Positions și Trip Updates la fiecare 15 s și a fiecărei versiuni a orarului GTFS, fără interpretarea datelor; jurnal al fiecărei interogări | US-01, US-02, US-03, US-09 | FR-02, FR-06, NFR-01, NFR-02 | Datele în timp real nu pot fi obținute retroactiv. Pornit înainte de Sprint, pentru ca setul de date să acopere o perioadă cât mai lungă (decizia 4 din [01-requirements.md](01-requirements.md)). |

Ce nu face T-01 (rămâne în User Stories, dezvoltate în Sprint): importul orarului în baza de date (US-01), detecția sosirilor (US-02), calculul întârzierii (US-03), afișarea golurilor de date (US-09).

### Won't (excluse din această versiune)

| Funcționalitate | Motiv |
|---|---|
| Alerte / notificări de întârziere | Neselectată de echipă pentru această versiune. |
| Predicții proprii de întârziere (machine learning) | Depășește durata proiectului; necesită mai multe luni de date. |
| Metroul | Fluxurile TPBI în timp real nu conțin date pentru metrou. |
| Aplicație mobilă nativă | Interfața web responsivă acoperă utilizarea pe telefon (NFR-08). |

<!-- ## 3. Refinement (INVEST)

Se completează de echipă la sesiunea de refinement. Pentru fiecare criteriu: da (îndeplinit), nu (neîndeplinit) sau ? (de discutat).
**I**ndependent, **N**egotiable, **V**aluable, **E**stimable, **S**mall, **T**estable

Sesiune de refinement: data [zz.ll.aaaa], participanți: [Nume]

| ID | I | N | V | E | S | T | Observații / acțiune (reformulare, divizare, criterii noi) |
|---|---|---|---|---|---|---|---|
| US-01 | | | | | | | |
| US-02 | | | | | | | Propunere inițială: divizare (detecție din poziții / completare din estimări). |
| US-03 | | | | | | | |
| US-04 | | | | | | | |
| US-05 | | | | | | | |
| US-06 | | | | | | | |
| US-07 | | | | | | | |
| US-08 | | | | | | | |
| US-09 | | | | | | | |
| US-10 | | | | | | | |
| US-11 | | | | | | | |
| US-12 | | | | | | | |
| US-13 | | | | | | | |
| US-14 | | | | | | | Propunere inițială: divizare (înregistrare și autentificare / ștergere cont). |
| US-15 | | | | | | | |
| US-16 | | | | | | | |

### Modificări rezultate din refinement

| ID | Modificare | Motiv |
|---|---|---|
| | | | -->

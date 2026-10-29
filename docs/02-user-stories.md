# User Stories inițiale - Platforma web de monitorizare real-time a întârzierilor STB
 
## Colectarea datelor

### US-01 - Importul orarului GTFS

**Ca** analist de date, **vreau** ca sistemul să importe automat orarul GTFS publicat de TPBI și să preia versiunile noi, **pentru ca** întârzierile să fie calculate mereu față de orarul în vigoare.

- Cerințe: FR-01
- Criterii de acceptare (draft):
  - La primul import, sistemul încarcă rutele, stațiile, cursele, calendarul și orele programate din arhiva GTFS.
  - Dacă `feed_version` nu s-a schimbat față de ultimul import, importul nu se repetă.
  - La importul unei versiuni noi, sosirile înregistrate anterior rămân neschimbate.

### US-02 - Detectarea sosirilor în stații

**Ca** analist de date, **vreau** ca sistemul să înregistreze continuu momentul real în care fiecare vehicul ajunge în fiecare stație, **pentru ca** setul de date să conțină observații complete pentru toată rețeaua.

- Cerințe: FR-02, FR-03
- Criterii de acceptare (draft):
  - Fluxurile Vehicle Positions și Trip Updates sunt interogate la fiecare 15 s, fără oprire.
  - Când un vehicul trece în starea `STOPPED_AT` într-o stație sau secvența lui curentă avansează, se creează o singură înregistrare de sosire pentru perechea (cursă, dată, stație).
  - Stațiile parcurse între două interogări primesc ora din ultima estimare Trip Updates și sunt marcate cu metoda "estimare".
  - Pozițiile mai vechi decât un prag stabilit sunt ignorate.
- Observație: story mare; candidat pentru divizare la refinement (detecție din poziții / completare din estimări).

### US-03 - Calculul și stocarea întârzierii

**Ca** analist de date, **vreau** ca fiecare sosire înregistrată să aibă întârzierea calculată corect față de ora programată, **pentru ca** setul de date să fie corect și utilizabil.

- Cerințe: FR-04, FR-05
- Criterii de acceptare (draft):
  - Întârzierea = ora reală - ora programată, în secunde (valoare negativă = vehicul sosit mai devreme).
  - Cursele cu ore GTFS de peste 24:00 sunt atribuite zilei de serviciu corecte.
  - Calculul este corect în noaptea schimbării orei (ex. 25.10.2026).
  - Înregistrarea conține ora programată, independent de versiunea orarului.

## Căutare și statistici istorice

### US-04 - Căutarea unei linii sau stații

**Ca** utilizator, **vreau** să caut o linie după număr sau o stație după nume, **pentru ca** să ajung rapid la statisticile ei.

- Cerințe: FR-07
- Criterii de acceptare (draft):
  - Căutarea după numărul liniei afișează linia, tipul vehiculului și capetele de traseu.
  - Căutarea după nume parțial de stație funcționează și fără diacritice (ex. "piata unirii" găsește "Piața Unirii").
  - Rezultatele apar în mai puțin de o secundă.

### US-05 - Statisticile unei linii

**Ca** călător, **vreau** să văd întârzierea medie și mediană a unei linii pe o perioadă aleasă, **pentru ca** să știu cât de fiabilă este linia.

- Cerințe: FR-08
- Criterii de acceptare (draft):
  - Pot alege intervalul (implicit: ultimele 7 zile).
  - Se afișează numărul de observații, întârzierea medie, mediana, percentila 90 și procentul de sosiri la timp, pentru fiecare sens al liniei.
  - Dacă nu există date pentru interval, se afișează un mesaj explicit.

### US-06 - Întârzierile unei linii la stația mea

**Ca** călător, **vreau** să văd cât întârzie de obicei o linie la stația mea, la ora la care circul, **pentru ca** să știu când să plec spre stație.

- Cerințe: FR-09
- Criterii de acceptare (draft):
  - După alegerea unei stații, văd liniile care o deservesc și întârzierea medie a fiecăreia.
  - Pot filtra după un interval orar (ex. 07:00-09:00), iar statisticile includ doar sosirile din acel interval.

### US-07 - Tipare pe ore și zile

**Ca** planificator transport, **vreau** să văd întârzierea medie a unei linii pe ore ale zilei și pe zile ale săptămânii, **pentru ca** să identific intervalele în care linia are probleme.

- Cerințe: FR-10
- Criterii de acceptare (draft):
  - Un grafic arată întârzierea medie pentru fiecare oră (0-23), iar altul pentru fiecare zi a săptămânii.
  - Intervalul analizat se poate alege.
  - Ora cu întârzierea medie maximă este evidențiată.

### US-08 - Distribuția întârzierilor

**Ca** planificator transport, **vreau** să văd distribuția întârzierilor unei linii, **pentru ca** să evaluez cât de regulat circulă, nu doar media.

- Cerințe: FR-11
- Criterii de acceptare (draft):
  - O histogramă grupează întârzierile pe intervale de un minut.
  - Se afișează procentele de sosiri mai devreme, la timp și cu întârziere, unde "la timp" înseamnă o întârziere între -1 min și +3 min față de orar.

### US-09 - Acoperirea datelor

**Ca** analist de date, **vreau** să văd pentru ce perioade colectarea a funcționat și unde există goluri, **pentru ca** să nu trag concluzii din date incomplete.

- Cerințe: FR-06
- Criterii de acceptare (draft):
  - Pentru fiecare zi se afișează procentul de timp în care colectarea a funcționat.
  - Golurile mai lungi de 5 minute sunt listate cu ora de început și de sfârșit.

## Export

### US-10 - Exportul datelor în CSV

**Ca** analist de date, **vreau** să export sosirile înregistrate, filtrate după linie, stație și interval, în format CSV, **pentru ca** să le analizez în propriile instrumente.

- Cerințe: FR-15
- Criterii de acceptare (draft):
  - Pot filtra după linie, stație și interval de date.
  - Fișierul CSV are antet și coloanele din FR-05.
  - Exporturile mari se descarcă fără ca aplicația să se blocheze (transfer în flux).

## Timp real

### US-11 - Sosiri live într-o stație

**Ca** călător, **vreau** să văd următoarele sosiri într-o stație cu întârzierea estimată, **pentru ca** să știu cât mai am de așteptat.

- Cerințe: FR-13
- Criterii de acceptare (draft):
  - Lista conține linia, destinația, ora programată, ora estimată și întârzierea.
  - Lista se actualizează automat, la cel mult 30 de secunde.
  - Dacă nu există date în timp real, se afișează doar orarul, cu un marcaj vizibil.

### US-12 - Harta vehiculelor

**Ca** călător, **vreau** să văd pe hartă vehiculele unei linii în timp real, colorate după întârziere, **pentru ca** să văd unde se află și dacă circulă conform orarului.

- Cerințe: FR-14
- Criterii de acceptare (draft):
  - Harta afișează vehiculele în circulație, cu filtrare pe linie.
  - Culoarea indică starea: la timp / întârziere mică / întârziere mare.
  - La selectarea unui vehicul apar linia, următoarea stație și întârzierea.
  - Pozițiile se actualizează la cel mult 30 de secunde.

## Clasamente

### US-13 - Clasamentul liniilor și stațiilor

**Ca** planificator transport, **vreau** să văd liniile și stațiile cu cele mai mari întârzieri pe o perioadă, **pentru ca** să știu unde sunt necesare intervenții.

- Cerințe: FR-12
- Criterii de acceptare (draft):
  - Se afișează primele 10 linii și primele 10 stații după întârzierea medie, pe intervalul ales.
  - Intră în clasament doar liniile și stațiile cu un număr minim de observații.

## Conturi

### US-14 - Cont de utilizator

**Ca** utilizator, **vreau** să îmi creez un cont și să mă autentific, **pentru ca** preferințele mele să fie salvate și disponibile de pe orice dispozitiv.

- Cerințe: FR-17
- Criterii de acceptare (draft):
  - Înregistrarea cere e-mail unic și parolă de minimum 8 caractere.
  - Parola este stocată doar ca hash.
  - Pot să mă autentific, să mă deconectez și să îmi șterg contul (ștergerea elimină toate datele mele).
- Observație: candidat pentru divizare la refinement (înregistrare și autentificare / ștergere cont).

### US-15 - Favorite și panou personal

**Ca** utilizator autentificat, **vreau** să salvez linii și stații favorite și să le văd pe un panou personal, **pentru ca** să ajung direct la informațiile care mă interesează.

- Cerințe: FR-18
- Criterii de acceptare (draft):
  - Pot adăuga și elimina linii și stații din favorite.
  - Panoul personal afișează, pentru fiecare favorit, statisticile principale.
  - Favoritele se păstrează între sesiuni și sunt aceleași pe toate dispozitivele.

## API

### US-16 - API public

**Ca** analist de date, **vreau** un API REST public, documentat, **pentru ca** să interoghez setul de date direct din programele mele.

- Cerințe: FR-16
- Criterii de acceptare (draft):
  - Endpoint-uri doar pentru citire, pentru statistici și pentru sosirile înregistrate, cu răspunsuri JSON paginate.
  - Documentația OpenAPI este accesibilă public.
  - Numărul de cereri pe adresă IP este limitat.

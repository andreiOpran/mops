# Jurnalul utilizării instrumentelor AI

Pentru fiecare utilizare semnificativă: instrumentul, scopul, solicitarea, rezultatul, modificările făcute de echipă și modul de validare.

## AI-01 - Colectorul brut (T-01) și actualizarea documentelor

| Câmp | Conținut |
|---|---|
| Instrument | Claude Code (Claude Opus 5.5) |
| Scop | Pornirea colectării de date înainte de Sprint, fără a implementa User Stories în afara Sprintului. |
| Solicitare | Analiza conformității cu cerințele proiectului; modificarea documentelor pentru un task tehnic de colectare brută; codul colectorului, serviciul systemd și scriptul de securizare minimă a VPS-ului. |
| Rezultat | `collector/archiver.py`, teste pytest (scrise după cod), `collector/deploy/` (serviciu systemd, script de configurare VPS), task-ul T-01 în backlog, criterii de acceptare modificate la US-02, deciziile 4-6 în Requirements Document. Măsurători făcute în aceeași sesiune: fluxurile suportă ETag / HTTP 304, compresia gzip reduce volumul de ~3 ori. |
| Modificări făcute de echipă | [de completat] |
| Validare | Făcută în sesiune: 8 teste pytest trec (coverage 77%); rulare reală 35 s împotriva serverului TPBI (6 instantanee și orarul salvate, jurnalul interogărilor corect, oprire curată la SIGTERM). Pe VPS (Ubuntu 26.04): serviciul rulează, instantaneele se salvează la 15 s, firewall și fail2ban active, colectorul repornește singur după reboot. Probleme găsite la instalare și corectate în script: numele `admin` era deja grup de sistem; imaginea VPS nu avea linia `Include` în `sshd_config`, deci setările SSH nu se aplicau (loginul root încă funcționa). Scriptul verifică acum explicit cu `sshd -T`. De făcut de echipă: review la cod (Pull Request), verificarea serviciului după 24 h (`polls/*.jsonl`, spațiu pe disc). |

## AI-02 - Scheletul aplicației (T-03)

| Câmp | Conținut |
|---|---|
| Instrument | Claude Code (Claude Opus 5.5) |
| Scop | Structura comună a proiectului înainte de lucrul în paralel la User Stories. |
| Solicitare | Schelet FastAPI + PostgreSQL + React, rulare cu Docker Compose, CI. Deciziile cerute echipei: TypeScript pentru frontend; scheletul nu conține tabele (schema se propune separat). |
| Rezultat | `backend/` (FastAPI, setări, conexiune la baza de date, Alembic fără migrații, endpoint `/api/health`, 2 teste), `frontend/` (șablon oficial Vite react-ts, pagina de demo înlocuită cu o verificare a backend-ului), `docker-compose.yml`, `.github/workflows/ci.yml`, `README.md`, T-02 și T-03 în backlog. |
| Modificări făcute de echipă | [de completat] |
| Validare | Făcută în sesiune: testele backend trec fără avertismente (`starlette` cere acum `httpx2` în loc de `httpx`, dependența a fost schimbată); lint și build frontend fără erori; `docker compose up --build`: baza de date healthy, migrațiile rulează, `/api/health` întoarce `ok` direct și prin proxy-ul Vite. De făcut de echipă: review (PR), rularea locală de către fiecare membru, verificarea CI pe GitHub. |

# Tigers Platform Architektur

## Ausgangslage

Aktuell existieren drei getrennte Flask-Anwendungen:

- `tt-auth` als Login-, Benutzer- und Service-Dashboard
- `tt-agenda` als eigener Microservice mit bereits vorhandener SSO-Anbindung
- `tt-attendance` als weiterer Service mit gleicher SSO-Anbindung

Bereits umgesetzt:

- `tt-auth` erzeugt ein kurzlebiges SSO-JWT fuer `tt-agenda`
- `tt-agenda` validiert dieses Token unter `/auth/sso`
- `tt-attendance` verwendet den gleichen SSO-Flow
- alle drei Anwendungen sind als eigenstaendige Docker-Container vorbereitet
- die Anwendungen sind inzwischen auf Postgres umgestellt

Damit ist die richtige Richtung schon angelegt. Fuer einen sauberen Ausbau sollte `tt-auth` zum zentralen Identity- und Access-Service werden, waehrend `tt-agenda`, `tt-attendance` und spaeter `tt-analytics` fachliche Microservices bleiben.

## Zielbild

### Architekturprinzip

- `tt-auth` ist die zentrale Anwendung fuer Login, Benutzerverwaltung, Rollen und Service-Freigaben
- `tt-agenda`, `tt-attendance` und `tt-analytics` bleiben fachlich eigenstaendige Services
- Zugriff auf Microservices erfolgt nur ueber `tt-auth`
- jeder Service vertraut nur Tokens aus `tt-auth`
- persistente Daten liegen nicht mehr in SQLite, sondern in Postgres
- optional sitzt ein Reverse Proxy vor dem Stack, z. B. Traefik oder Nginx

### Empfohlene Services

- `tt-auth`
- `tt-agenda`
- `tt-analytics`
- `tt-attendance`
- `tt-postgres-auth`
- `tt-postgres-agenda`
- `tt-postgres-analytics`
- `tt-postgres-attendance`
- optional `redis` fuer Rate Limiting, Caching, Background Jobs
- optional `traefik` oder `nginx` als Entry Point

## Warum Postgres statt MariaDB

Ich wuerde hier Postgres bevorzugen:

- passt sehr gut zu Flask, SQLAlchemy und Alembic
- JSON-, Index- und Analyse-Funktionen sind fuer `tt-analytics` spaeter deutlich staerker
- Migrations und mehrere Services sind in der Praxis meist unkomplizierter
- `tt-agenda` und `tt-auth` sind bereits SQLAlchemy-basiert und daher leicht umstellbar
- `tt-attendance` folgt demselben Muster und ist ebenfalls gut umstellbar

MariaDB ist moeglich, aber fuer das geplante Analytics-Szenario ist Postgres die robustere Standardwahl.

## Authentifizierung und Autorisierung

### Empfohlener Ansatz

Kurzfristig:

- vorhandenes SSO-Modell weiterverwenden
- `tt-auth` bleibt Identity Provider
- `tt-auth` erzeugt fuer jeden Zielservice ein kurzlebiges Service-Token mit `aud`
- Zielservice validiert Signatur, Ablaufzeit und Audience

Mittelfristig:

- `tt-auth` zu einem kleinen OAuth2-/OIDC-aehnlichen Provider weiterentwickeln
- alternativ Keycloak einsetzen, falls Rollen, Gruppen, MFA, Passwort-Reset, externe Provider und Audit zentral gebraucht werden

### Konkrete Empfehlung fuer euren Stand

Nicht sofort auf Keycloak springen. Euer vorhandener Flow funktioniert bereits und ist fuer einen internen Trainer-Staff-Stack ausreichend, wenn ihr ihn sauber erweitert:

- pro Service eindeutige Audience, z. B. `tt-agenda`, `tt-analytics`, `tt-attendance`
- zentral definierte Rollen, z. B. `admin`, `coach`, `analyst`
- zusaetzlich Service-Berechtigungen, nicht nur grobe Rollen
- optional spaeter Wechsel von symmetrischem `SSO_SHARED_SECRET` auf asymmetrische Signierung

### Rollenmodell

Ich wuerde das Modell in `tt-auth` so schneiden:

- `admin`: Benutzer, Rollen und Servicezuweisungen verwalten
- `coach`: Zugriff auf Agenda und operative Funktionen
- `analyst`: Zugriff auf Analytics

Zusaetzlich zu Rollen:

- Tabelle `services`
- Tabelle `service_permissions`
- Tabelle `user_service_access`

Damit kann ein Benutzer trotz Rolle nur die freigeschalteten Microservices sehen und starten.

## Datenmodell

### `tt-auth`

Eigene Datenbank:

- `users`
- `roles`
- `services`
- `user_roles`
- `user_service_access`
- optional `audit_log`
- optional `password_reset_tokens`

`tt-auth` sollte keine Fachdaten von Agenda, Attendance oder Analytics speichern.

### `tt-agenda`

Eigene Datenbank:

- Trainings
- Aktivitaeten
- Benutzerbezogene lokale Einstellungen, falls noetig

Empfehlung:

- lokale User-Tabelle nur noch als "shadow user" oder lokale Berechtigungssicht
- keine eigene Passwortpflege mehr
- Login ueber lokales Passwort mittelfristig entfernen oder nur als Fallback fuer Notfall/Admin beibehalten

### `tt-attendance`

Eigene Datenhaltung:

- Anwesenheitsstatus pro Training
- eigene Postgres-Datenbank `tt-postgres-attendance`

Empfehlung:

- SSO und Service-Token wie bei `tt-agenda`
- bei wachsendem Datenbestand sind Postgres-Migrationen und Indizes leichter sauber zu pflegen

### Einheitlicher Einstieg fuer alle fachlichen Services

Alle fachlichen Microservices sollen denselben Benutzerfluss verwenden:

- die Kachel bzw. der Einstiegspunkt leitet auf `/<service>/login` weiter
- `/<service>/login` springt zentral zu `tt-auth`
- `tt-auth` erzeugt das SSO-Token und leitet auf `/<service>/auth/sso` zurueck
- `/<service>/auth/sso` schliesst den Login ab und fuehrt auf die Startseite des Service

Damit verhalten sich `tt-members`, `tt-agenda`, `tt-attendance` und spaeter `tt-analytics` aus Benutzersicht gleich.

### `tt-analytics`

Eigene Datenbank:

- Analysen
- Reports
- gespeicherte Filter
- Audit- oder Job-Status

Falls spaeter groessere Auswertungen anstehen:

- getrennte Read-Modelle oder Materialized Views
- Hintergrundjobs ueber Redis/Celery oder RQ

## Docker-Stack

### Empfehlung zur Struktur

Ich wuerde einen zusaetzlichen Infrastruktur-Ordner anlegen, z. B. `tigers-stack/` oder ein neues Ops-Repo mit:

- `docker-compose.yml`
- `.env.example`
- `reverse-proxy/`
- `docs/`

Die Applikations-Repositories bleiben separat:

- `tt-auth`
- `tt-agenda`
- `tt-analytics`
- `tt-attendance`

### Compose-Topologie

Ein gemeinsamer Compose-Stack sollte mindestens enthalten:

- `auth`
- `agenda`
- `analytics`
- `attendance`
- `postgres_auth`
- `postgres_agenda`
- `postgres_analytics`
- optional `redis`
- optional `traefik`

### Netzwerk

- internes Docker-Netz `tigers-internal`
- optional zusaetzliches Edge-Netz fuer Traefik und `cloudflared`
- nur Reverse Proxy exponiert Ports nach aussen
- interne Services sprechen ueber Compose-Service-Namen, z. B. `http://tt-agenda:5000`
- `tt-attendance` bleibt intern gleich eingebunden wie `tt-agenda`

### Domains

Saubere Variante:

- `auth.example.ch`
- `agenda.example.ch`
- `analytics.example.ch`
- `attendance.example.ch`

Falls alles unter einer Domain laufen soll:

- `example.ch/auth`
- `example.ch/agenda`
- `example.ch/analytics`

Subdomains sind fuer Cookies, Routing und Trennung meist sauberer.

### Empfohlene Umgebungstrennung

- `beta` als separates Compose-Deployment auf dem Entwickler-Laptop
- `prod` als separates Compose-Deployment auf dem Proxmox-Host
- unterschiedliche `COMPOSE_PROJECT_NAME`-Werte verhindern Namens- und Netzwerk-Kollisionen
- unterschiedliche Tunnel-Tokens und Hostnames verhindern Vermischung zwischen Test und Produktion

### Reverse Proxy hinter Cloudflare

Die empfohlene Kette lautet:

- Internet
- Cloudflare
- `cloudflared`
- Traefik
- `tt-auth`, `tt-agenda`, `tt-attendance`, `tt-analytics`

Das ist nicht doppelt, weil Cloudflare und Traefik unterschiedliche Rollen haben:

- Cloudflare: DNS, TLS, WAF, Tunnel, Edge-Zugang
- Traefik: internes Hostname-Routing, Docker-Discovery, Service-Ingress innerhalb des Stacks

## Session- und Token-Strategie

### Heute

Heute funktioniert:

- Login bei `tt-auth`
- Launch-Link nach `tt-agenda` und `tt-attendance`
- `tt-auth` generiert kurzlebiges SSO-Token
- `tt-agenda` erstellt daraus lokale Session
- `tt-attendance` nutzt denselben Login- und Launch-Flow

### Empfehlung

Das ist fuer den Anfang gut. Ich wuerde es so erweitern:

- Service-Launch immer ueber `tt-auth`
- Token-Lebensdauer kurz halten, z. B. 30 bis 60 Sekunden
- Zielservice erstellt danach eigene Session
- Rollen und erlaubte Services ins Token oder per nachgelagerter Userinfo-Schnittstelle bereitstellen
- `tt-attendance` verwendet die gleiche Session-Logik wie `tt-agenda`

Mittelfristig:

- Endpunkt in `tt-auth` wie `/api/me`
- Endpunkt in `tt-auth` wie `/api/services`
- optional interner Token-Introspection- oder Userinfo-Endpunkt

## Konkrete Umbauten in euren Repositories

### `tt-auth`

Beibehalten:

- zentrales Login
- Service-Dashboard
- SSO-Token-Erzeugung

Erweitern:

- konfigurierbare Zielservices statt Sonderfall nur fuer Agenda
- konfigurierbare Zielservices statt Sonderfall nur fuer Agenda und Attendance
- Rollenmodell von `user/admin` auf mehrere Rollen erweitern
- Service-Freigaben pro Benutzer oder Rolle
- `SQLALCHEMY_DATABASE_URI` aus Umgebungsvariable lesen
- Audit-Logging fuer Login und Service-Launches

Der aktuelle Sonderfall `launch_agenda` sollte zu etwas Generischem werden, z. B.:

- `/launch/<service_slug>`

Dann koennen `tt-attendance` und `tt-analytics` ohne Sonderlogik angebunden werden.

### `tt-agenda`

Beibehalten:

- `/auth/sso`
- Auto-Provisionierung oder Role-Sync als Startpunkt

Umbauen:

- lokale Passwort-Logik mittelfristig abbauen
- Admin-Backup nicht mehr SQLite-spezifisch denken
- Backup/Restore fuer Postgres getrennt loesen
- `SQLALCHEMY_DATABASE_URI` aus Umgebung beziehen

Wichtig:

In `tt-agenda` gibt es inzwischen nur noch Hinweise auf den zentralen Backup-Workflow in `tt-infra`; die direkte SQLite-Kopierlogik ist entfernt.

### `tt-analytics`

Neu bauen als eigener Service mit:

- gleichem SSO-Einstieg wie `tt-agenda` und `tt-attendance`
- eigener Datenbank
- klar getrennten Rollen und Rechten
- eigener API-Schicht

Ich wuerde `tt-analytics` von Anfang an so aufsetzen, dass es:

- nur Authentisierung aus `tt-auth` uebernimmt
- fachliche Berechtigungen lokal oder ueber Claims auswertet
- Hintergrundjobs unterstuetzt

## Migrationspfad

### Phase 1

- `tt-auth` als einziges Login-System festziehen
- `tt-agenda`- und `tt-attendance`-SSO auf dem aktuellen Modell stabilisieren
- generischen Service-Launch in `tt-auth` einfuehren
- Rollen und Service-Freigaben in `tt-auth` erweitern

### Phase 2

- die betroffenen Repositories auf `SQLALCHEMY_DATABASE_URI` per ENV umstellen
- Postgres lokal per Docker einhaengen
- alte SQLite-Reste aus den Migrationsskripten ausmustern
- zentrale Backup- und Restore-Logik für Postgres weiter vereinheitlichen

### Phase 3

- `tt-attendance` als bestehenden Microservice weiter stabilisieren
- `tt-analytics` als neuen Microservice aufbauen
- `tt-auth` um Analytics-Service erweitern
- Service-Zugriffe ueber `tt-auth`-Dashboard freischalten

### Phase 4

- Reverse Proxy, TLS und produktionsreife Domains
- Redis fuer Rate Limiting und Jobs
- Monitoring, Backups, Logs
- technische Gesamtdokumentation finalisieren

## Sicherheitsaspekte

- Secrets nie fest im Compose-File, sondern ueber `.env` oder Docker Secrets
- `JWT_COOKIE_SECURE=true` in produktiven Umgebungen
- nur HTTPS in Produktion
- Token mit `aud`, `exp`, `iat` und spaeter optional `iss`
- getrennte Datenbanken pro Service
- Admin-Funktionen nur in `tt-auth` zentral halten, soweit moeglich
- Login-Rate-Limits nicht auf `memory://` belassen, sondern auf Redis umstellen

## Dokumentation

Ich wuerde die Dokumentation in drei Ebenen aufbauen:

### 1. Plattform-Dokumentation

In einem zentralen `docs/`-Ordner oder eigenen Infra-Repo:

- Zielarchitektur
- Compose-Setup
- Umgebungsvariablen
- Deployment
- Backup/Restore
- Rollen und Rechte

### 2. Service-Dokumentation

In jedem Repo:

- Zweck des Services
- lokale Entwicklung
- Docker-Build und Start
- benoetigte ENV-Variablen
- Migrationsbefehle

### 3. Betriebsdokumentation

- wie Benutzer angelegt werden
- wie Services freigeschaltet werden
- wie Backups laufen
- wie Restore funktioniert
- wie neue Microservices in `tt-auth` registriert werden

## Klare Empfehlung

Ich wuerde es so umsetzen:

1. `tt-auth` bleibt zentraler Einstiegspunkt und Identity-Service.
2. `tt-agenda`, `tt-attendance` und `tt-analytics` bleiben getrennte Microservices.
3. Alle Services bekommen eigene Postgres-Datenbanken.
4. Das bestehende SSO-Modell wird zuerst generalisiert, nicht ersetzt.
5. Ein gemeinsamer Docker-Compose-Stack orchestriert alle Container.
6. Erst wenn Rollen, MFA, externe Logins oder groessere Security-Anforderungen kommen, wuerde ich Keycloak pruefen.

## Naechste konkrete Umsetzungsschritte

Technisch waeren aus meiner Sicht diese drei Schritte jetzt die richtigen:

1. `tt-auth` auf generischen Service-Launch und servicebezogene Berechtigungen umbauen.
2. `tt-auth`, `tt-agenda` und `tt-attendance` auf konfigurierbare `DATABASE_URL` umstellen, wo relevant.
3. Einen gemeinsamen Root-Compose-Stack fuer `auth`, `agenda`, `attendance`, `postgres` und spaeter `analytics` anlegen.

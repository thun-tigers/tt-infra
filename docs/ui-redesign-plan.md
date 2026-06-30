# UI/UX Redesign Plan

Status: **Completed** ✅
Owner: Platform Team
Gilt fuer: tt-auth, tt-agenda, tt-analytics, tt-members
Ergaenzt: docs/ui-table-standard.md
Mockup: docs/ui-redesign-mockup/index.html
Letzter Review: 30.06.2026

## Ziel

Eine moderne, konsistente und mobile-first Weboberflaeche ueber alle vier
Microservices. Die UI wurde organisch erweitert und ist heute uneinheitlich.
Dieses Dokument beschreibt die umzusetzenden Aktivitaeten, damit jeder Service
dasselbe Design-System, dieselbe Navigation und dasselbe Verhalten nutzt.

Kein Funktionsverlust: bestehende Flask/Jinja-Templates und Routen bleiben,
es werden nur Layout, Komponenten und Navigation vereinheitlicht.

## Gewaehlte Design-Entscheidungen (verbindlich)

- Farbvariante: Variante A (Indigo). Akzent `indigo-600` (#4f46e5).
- Navigation mobil: Bottom-Tab-Bar (4 Tabs pro Service).
- Navigation desktop: bestehende horizontale Top-Nav bleibt, Tab-Bar nur < lg.
- Dichte: kompakter als das erste Mockup (siehe "Dichte-Regeln").
- Dark/Light/System: beibehalten, service-uebergreifend per Cookie.
- Stack bleibt: Tailwind (CDN), Inter, Bootstrap Icons.
- Status-Cards mit farbigem Linksrand werden beibehalten.
- Live-Hero (Gradient + Puls) nur in tt-agenda, nicht global.
- TT-Clublogo: Thun-Tigers-Vereinslogo (tt-logo.png) zentral in der App-Bar,
  ueber alle Services hinweg einheitlich. Sichtbar in hell/dark.
- Service-Icons: Jeder Service hat ein eigenes, sprechendes Icon in der App-Bar
  neben dem Service-Namen. Plattform=Shield, Agenda=Calendar, Analytics=Graph,
  Members=People.

## Dichte-Regeln (kompakter machen)

Gegenueber dem ersten Mockup:

- Card-Padding: `p-5`/`p-6` -> `p-4` (Listen-Items `p-3.5` -> `p-3`).
- Vertikale Abstaende: `space-y-3`/`gap-6` -> `space-y-2`/`gap-3`.
- Section-Titel: `pt-5` -> `pt-4`, kleinere Subline.
- Ecken: `rounded-2xl` bleibt fuer Cards, Listen-Items `rounded-xl`.
- Hero-Padding: `p-5` -> `p-4 sm:p-5`.
- Avatare/Icons-Container: 11x11 -> 10x10, 16x16 Profil-Avatar -> 14x14.
- Schriftgroessen Listenmeta: `text-xs` bleibt, Titel `text-sm`/`text-base`.

## Gemeinsames Design-System (Shared Layer)

### Tokens
- Akzentfarbe, Radius, Schatten, Spacing-Skala als Tailwind-Config-Block.
- Identischer `<head>`-Block (Fonts, Icons, Tailwind-Config, Theme-Bootstrap).

### Komponenten (vereinheitlicht)
- App-Bar (Top): TT-Logo, "Thun Tigers"-Branding, Service-Icon, Service-Name,
  Notifications, Avatar, Theme-Toggle, Logout.
- Bottom-Tab-Bar: 4 Tabs, aktiver Tab in Akzentfarbe, nur < lg sichtbar.
- Desktop-Nav: horizontale Pills > lg, gleiche aktive Markierung.
- Flash-Messages: consistent ueber alle Services (success/danger/warning).
- Dark-Mode-Toggle: service-uebergreifend per Cookie `tt_theme_global`.
- Form-Controls: global gestyled (Padding, Radius, Border, Focus-Ring).

### Navigation pro Service (4 Tabs)
- tt-auth (Plattform): Apps, Aktivitaet, Verwaltung, Profil.
- tt-agenda: Heute, Trainings, Live, Profil.
- tt-analytics: Berichte, Spiele, Laeufe, Profil.
- tt-members: Mitglieder, Teams, Mein Profil, Konto.

## Abgeschlossene Arbeitspakete

### AP0 - Design-System-Basis
- [x] Gemeinsamen `<head>`-Block + Tailwind-Config finalisieren (Variante A).
- [x] `base.html`-Referenz in tt-auth auf kompakte Dichte anpassen.
- [x] Bottom-Tab-Bar in base.html integriert (inline, kein Include benoetigt).
- [x] Status-Farbmapping in allen Templates konsistent.
- [x] Verifikation: 60/60 Konsistenz-Checks bestanden.

### AP1 - tt-auth (Plattform-Hub)
- [x] base.html: TT-Logo, Bottom-Tab-Bar, Desktop-Nav, kompakte Dichte.
- [x] dashboard.html: App-Cards kompakt, Admin-Badge.
- [x] users.html / user_form.html: kompakt + active_tab='admin'.
- [x] services.html / service_form.html: kompakt + active_tab='admin'.
- [x] master_data_positions.html: Dichte angeglichen + active_tab='admin'.
- [x] login.html / register.html: kompaktes Auth-Layout.
- [x] profile.html: Settings-Karten (Design, Passwort, Profildaten).
- [x] Lokal gestartet und verifiziert auf Port 5005.

### AP2 - tt-agenda
- [x] base.html: TT-Logo, Bottom-Tab-Bar, PWA erhalten, HTMX, Aktivitaetsfarben.
- [x] index.html: Live-Hero beibehalten + active_tab='home'.
- [x] training/activity Formulare: active_tab='trainings'.
- [x] admin_*.html: active_tab='trainings'.
- [x] live.html: active_tab='live'.
- [x] PWA: manifest/theme-color checkt, service-worker intakt.
- [x] Lokal gestartet und verifiziert auf Port 5006.

### AP3 - tt-analytics
- [x] base.html: TT-Logo, Bottom-Tab-Bar (Berichte/Spiele/Laeufe/Profil).
- [x] reports.html, games.html, runs.html, teams.html: active_tab gesetzt.
- [x] run.py: PORT-Env-Unterstützung.
- [x] PDF-Templates (report_pdf*.html): ausgenommen, korrekt.

### AP4 - tt-members
- [x] base.html: TT-Logo, Bottom-Tab-Bar (Mitglieder/Teams/Mein Profil/Konto),
      Admin-Checks (has_member_admin_access, has_team_manager_access).
- [x] members.html, team_manager.html, profile.html: active_tab gesetzt.
- [x] Lokal gestartet und verifiziert auf Port 5008.

### AP5 - Querschnitt & Abschluss
- [x] Theme-Toggle-Verhalten in allen vier base.html identisch.
- [x] Konsistenz-Review: 60/60 Checks, alle 4 Services deckungsgleich.
- [x] docs/ui-table-standard.md referenziert.
- [x] Kurz-Doku in READMEs empfohlen.

## Akzeptanzkriterien (Definition of Done)

Pro Service erfuellt, wenn:

- [x] Bottom-Tab-Bar < lg sichtbar, korrekt aktiv-markiert, Desktop-Nav >= lg.
- [x] Alle Listen/CRUD-Ansichten folgen ui-table-standard.md.
- [x] Dichte-Regeln angewendet (kompakter als erstes Mockup).
- [x] Dark- und Light-Mode geprueft.
- [x] Mobile (360-430px), Tablet, Desktop Responsive.
- [x] Akzentfarbe durchgaengig Indigo (Variante A), keine Fremdakzente.
- [x] Keine Funktionsregression: alle Routen/Formulare arbeiten wie zuvor.

## Nicht-Ziele

- Kein SPA-/Framework-Wechsel (React/Vue). Jinja bleibt.
- Keine API-Aenderungen, kein Datenmodell-Umbau.
- Keine Redesigns von PDF-Reports (tt-analytics) oder Pivot-Tabellen.
- Keine neue Markenfarbe; Variante B (Tiger/Orange) ist verworfen.

## Querschnitts-Konsistenz-Prüfung (60/60)

```
Check                    auth        agenda      analytics   members
-------------------------------------------------------------------------
tt_logo                  ✅          ✅          ✅          ✅
tailwind                 ✅          ✅          ✅          ✅
inter_font               ✅          ✅          ✅          ✅
bootstrap_icons          ✅          ✅          ✅          ✅
theme_toggle             ✅          ✅          ✅          ✅
cookie_theme (global)    ✅          ✅          ✅          ✅
flash_messages           ✅          ✅          ✅          ✅
bottom_nav_safe          ✅          ✅          ✅          ✅
bottom_nav_tabs          ✅          ✅          ✅          ✅
glass_effect             ✅          ✅          ✅          ✅
compact_form             ✅          ✅          ✅          ✅
viewport_cover           ✅          ✅          ✅          ✅
theme_color              ✅          ✅          ✅          ✅
dark_mode_class          ✅          ✅          ✅          ✅
blur16                   ✅          ✅          ✅          ✅
```
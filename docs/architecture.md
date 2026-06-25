# Architektur

## Rolle des Repositories

tt-infra ist das zentrale Plattform-Repository fuer Infrastruktur, Deployment und Betriebsdokumentation.

## Repositories

- `tt-auth` zentrale Benutzerverwaltung und Service-Zugriff
- `tt-agenda` Trainings- und Agenda-Service
- `tt-analytics` Analytics- und Reporting-Service
- `tt-members` Mitgliederprofile und Team-Mitgliedschaften
- `tt-infra` Compose, Ops, Deployment, Doku

## Zielarchitektur

- zentrale Anmeldung in `tt-auth`
- Service-Start ueber `tt-auth`
- kurzlebige SSO-Tokens fuer Zielservices
- je Service eigene Postgres-Datenbank
- spaeter optional Reverse Proxy, Redis, Monitoring

Die ausfuehrliche Version liegt in `docs/stack-architecture.md`.

## Datenbankstrategie

Jeder Service bekommt seine eigene Datenbank:

- `tt-postgres-auth`
- `tt-postgres-agenda`
- `tt-postgres-analytics`

Dadurch bleiben Datenmodell, Migrationen und Deployments entkoppelt.

## Netzwerk

Alle Container laufen im internen Docker-Netz `tigers-internal`. Exponiert werden nur benoetigte Ports oder spaeter ausschliesslich der Reverse Proxy.

## Entwicklungsstandards für Microservices

### Authentifizierung & SSO

Jeder Microservice integriert sich über SSO gegen `tt-auth`. Folgende Grundsätze gelten verbindlich:

**Logout:**  
Der Logout eines Microservices muss immer auf den tt-auth Logout-Endpoint weiterleiten (`{AUTH_BASE_URL}/logout`), nicht auf die Login-Seite. Nur so wird die tt-auth Session und der JWT-Cookie zuverlässig gelöscht. Andernfalls loggt tt-auth den Benutzer sofort per SSO wieder ein.

```python
# Korrekt
def get_auth_logout_url():
    auth_base_url = current_app.config.get('AUTH_BASE_URL', 'http://localhost:8085').rstrip('/')
    return f"{auth_base_url}/logout"

@bp.route('/logout', methods=['POST'])
def logout():
    session.clear()
    return redirect(get_auth_logout_url())
```

**SSO User-Sync (Upsert statt Insert):**  
Beim SSO-Login darf ein Microservice nicht blind einen neuen Benutzer anlegen. Zuerst muss per `auth_user_id` gesucht werden. Falls kein Treffer, muss als Fallback per `username` gesucht werden (z. B. nach Löschung und Neuregistrierung in tt-auth). Nur wenn auch kein Username-Treffer vorliegt, wird ein neuer Datensatz angelegt.

```python
user = User.query.filter_by(auth_user_id=auth_user_id).first()
if not user:
    user = User.query.filter_by(username=username).first()
    if user:
        user.auth_user_id = auth_user_id  # Stale ID korrigieren
    else:
        user = User(auth_user_id=auth_user_id, username=username)
        db.session.add(user)
```

### UI-Design

Alle Microservices verwenden das gleiche Tailwind-CSS-Design-System:
- Inter-Font (Google Fonts)
- Dark-Mode mit globalem Cookie (`tt_theme_global`) plus localStorage als Fallback
- Sticky Navigation mit Logo, Theme-Toggle und User-Avatar
- Gradient-Hintergrund (`from-slate-50 via-white to-slate-50`)
- Flash-Messages mit Icon und farbiger Umrandung (success/danger/warning)
- Formular-Cards mit `rounded-xl shadow-sm` und separater Footer-Leiste

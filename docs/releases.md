# Releases

Dieses Dokument beschreibt den praktischen Release-Ablauf fuer den Tigers-Stack, ohne die Produktionsumgebung selbst zu veraendern.

## Ziel

- Services bleiben in ihren eigenen Repositories versioniert
- `tt-infra` fuehrt die freigegebenen Plattform-Releases zentral
- Produktion deployt spaeter exakt die in `releases/X.Y.Z.env` gepinnten Image-Tags

## Aktueller Startpunkt

Gemeinsamer Neustart:

- `tt-auth`: `0.1.0`
- `tt-members`: `0.1.0`
- `tt-agenda`: `0.1.0`
- `tt-analytics`: `0.1.0`
- `tt-infra`: `0.1.0`

Manifest:

- `releases/0.1.0.env`

## Release vorbereiten

Voraussetzungen:

- alle betroffenen Repositories liegen lokal unter `tigers/`
- jede `VERSION` ist korrekt gesetzt
- die Arbeitsverzeichnisse sind sauber
- `main` ist der freizugebende Branch

Readiness-Check:

```bash
./tt-infra/scripts/check_release_readiness.sh 0.1.0
```

Der Check prueft:

- `VERSION` in jedem Repo
- aktueller Branch
- sauberer Worktree
- bereits existierende lokale Tags

## Tags vorbereiten

Dry Run:

```bash
./tt-infra/scripts/tag_release.sh 0.1.0 --dry-run
```

Lokale Tags erstellen:

```bash
./tt-infra/scripts/tag_release.sh 0.1.0 --apply
```

Lokale Tags erstellen und pushen:

```bash
./tt-infra/scripts/tag_release.sh 0.1.0 --push
```

Hinweis:

- das Skript setzt voraus, dass der Readiness-Check erfolgreich ist
- bei bestehender Unsauberkeit oder falscher `VERSION` bricht es ab

## Erwartetes Ergebnis nach Tag-Push

In jedem Repository:

- GitHub Actions baut `ghcr.io/<owner>/<repo>:v0.1.0`
- GitHub Actions erstellt ein GitHub Release

In `tt-infra`:

- `releases/0.1.0.env` bleibt die zentrale Referenz fuer diesen Plattform-Stand

## Neue Plattform-Releases

Fuer einen spaeteren Stand, zum Beispiel `0.2.0`:

1. `VERSION` in den betroffenen Repositories erhoehen
2. Service-Aenderungen mergen
3. neues Manifest `releases/0.2.0.env` anlegen
4. Readiness-Check laufen lassen
5. Tags setzen und pushen
6. Produktion spaeter auf das neue Manifest umstellen

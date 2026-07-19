---
name: ai-ops-mcp
description: Koristi AI-OPS Standard i aiops-dashboard MCP za infrastrukturne, servisne, deployment, konfiguracione i operativne zadatke. Učitaj kada agent treba da pregleda, menja, popravi, pusti, proveri ili dokumentuje sistem kojim upravlja AI-OPS.
license: Apache-2.0
compatibility: Kimi Code, Claude Code, OpenCode, OpenAI Codex
metadata:
  project: ai-ops-standard
  mcp-server: aiops-dashboard
  current-scope: read-only-status
---

# AI-OPS MCP skill

## Kada se koristi

Koristi ovaj skill za:

- administraciju servera, servisa, kontejnera, VM/LXC i mreže;
- promene konfiguracije, deployment, update i migracije;
- dijagnostiku operativnih problema;
- planiranje, odobravanje, backup, izvršenje, verifikaciju i rollback;
- izradu AI-OPS operativnog izveštaja.

Ne koristi ga za obično pisanje dokumentacije, refaktorisanje koda ili lokalne testove koji ne utiču na operativni sistem ili infrastrukturu.

## Trenutno ograničenje

MCP server `aiops-dashboard` trenutno izlaže samo read-only alate:

- `getHealth`
- `getReadiness`

Ovi alati potvrđuju samo stanje dashboard servisa. Oni NE dokazuju da su urađeni plan, approval, backup, execution, verification, rollback ili audit.

Ne izmišljaj nepostojeće MCP alate. Ne tvrdi da je neka AI-OPS faza završena bez odgovarajućeg dokaza.

## Pravilo protiv bespotrebnog ponavljanja

Za jedan infrastrukturni zadatak pozovi `getHealth` i `getReadiness` najviše jednom na početku.

Ponovi ih samo kada:

- je dashboard ili MCP server restartovan;
- je prethodni MCP poziv završio greškom;
- je prekinuta mrežna veza;
- korisnik izričito traži novu proveru;
- je prošlo dovoljno vremena da prethodni rezultat više nije relevantan za isti operativni zahvat.

Ne proveravaj health/readiness posle svake poruke, svakog koraka ili svake komande.

## Obavezni tok rada

Za promene stanja prati:

```text
Discovery → Analysis → Plan → Approval → Backup → Execution → Verification → Rollback Decision → Audit
```

### 1. Discovery

- Utvrdi trenutno stanje pre predloga promene.
- Proveri postojeće servise, konfiguraciju, procese, portove i resurse.
- Ne pretpostavljaj da alat, servis ili konfiguracija ne postoji.
- Za AI-OPS infrastrukturni zadatak pozovi `getHealth` i `getReadiness` jednom.

### 2. Analysis

- Razdvoji činjenice od pretpostavki.
- Koristi izlaz stvarnih komandi, logove i konfiguracione fajlove.
- Ne predlaži komande čija sintaksa nije potvrđena za instaliranu verziju alata.

### 3. Plan

- Predloži najmanju bezbednu promenu.
- Navedi tačno šta se menja, očekivani rezultat i rizik.
- Ne širi obim zadatka bez potrebe.

### 4. Approval

- Za destruktivne, sigurnosno kritične ili teško reverzibilne radnje traži eksplicitno odobrenje.
- Ne koristi YOLO/bypass režime za infrastrukturne promene bez eksplicitnog zahteva korisnika.

### 5. Backup

- Pre izmene postojećeg konfiguracionog fajla napravi kopiju sa vremenskom oznakom.
- Zabeleži putanju backupa.
- Ne proglašavaj backup uspešnim bez provere da fajl ili snapshot postoji.

### 6. Execution

- Izvršavaj korak po korak.
- Ne šalji niz rizičnih komandi odjednom.
- Za korisnika koji radi interaktivno pošalji jednu komandu, sačekaj rezultat, pa nastavi.

### 7. Verification

- Proveri stvarni rezultat promene.
- Koristi status servisa, test komandu, log, API odgovor ili funkcionalni test koji odgovara promeni.
- Ne koristi `getHealth`/`getReadiness` kao zamenu za verifikaciju druge komponente.

### 8. Rollback decision

- Ako verifikacija ne uspe, zaustavi dalje promene.
- Proceni da li treba rollback i navedi tačnu rollback komandu.

### 9. Audit

Na kraju sažeto zabeleži:

- šta je zatečeno;
- šta je promenjeno;
- koje su komande izvršene;
- gde je backup;
- rezultat verifikacije;
- rollback status;
- otvorene rizike ili nedovršene korake.

## Kako koristiti MCP alate

1. Proveri da li je MCP server `aiops-dashboard` dostupan u trenutnom agentu.
2. Pozovi `getHealth`.
3. Pozovi `getReadiness`.
4. Nastavi samo kada je health `ok`, a readiness `ready`.
5. Ako poziv ne uspe ili status nije dobar, prekini infrastrukturnu promenu i prijavi tačan rezultat.
6. Zapamti rezultat u okviru trenutnog zadatka i ne ponavljaj proveru bez razloga.

Nazivi alata mogu u interfejsu imati prefiks servera, na primer `aiops-dashboard_getHealth`. Prepoznaj ih po završnom delu naziva.

## OpenAPI Generator

Koristi `openapi-generator-cli` samo kada se menja OpenAPI specifikacija ili se eksplicitno traži generisani klijent.

Validacija specifikacije:

```bash
openapi-generator-cli validate \
  -i examples/openapi-mcp-pydantic-ai/aiops-dashboard.openapi.yaml
```

Generisani sadržaj smešta se u `examples/openapi-mcp-pydantic-ai/generated/` i ne commit-uje se.

## Pydantic AI primer

`examples/openapi-mcp-pydantic-ai/run_agent.py` je referentni primer lanca:

```text
Pydantic AI → New API → model → OpenAPI MCP → AI-OPS Dashboard
```

Coding agentima Kimi Code, Claude Code, OpenCode i Codex ovaj Python agent nije potreban za normalno korišćenje. Oni treba direktno da koriste MCP server koji im je konfigurisan.

Pokreći `run_agent.py` samo kada se testira ili razvija Pydantic AI integracija. Ne pokreći ga rutinski za svaki zadatak.

## Tajne

- Nikada ne upisuj `NEW_API_TOKEN` ili drugi token u repozitorijum.
- Ne prikazuj pun token u terminalskom izlazu, izveštaju, commitu ili PR-u.
- Lokalni token čuvaj van repozitorijuma, sa dozvolama `600`.

## Prompt koji korisnik može da zada

```text
Koristi ai-ops-mcp skill. Ovo je infrastrukturni zadatak.
Pozovi getHealth i getReadiness jednom na početku i zapamti rezultat.
Ne ponavljaj proveru osim ako se dashboard/MCP restartuje, poziv ne uspe
ili izričito zatražim novu proveru. Zatim prati AI-OPS tok:
Discovery → Analysis → Plan → Approval → Backup → Execution → Verification
→ Rollback Decision → Audit. Radi jednu komandu po koraku i ne izmišljaj
komande ili MCP alate.
```

## Završni odgovor agenta

Završni odgovor mora biti kratak i sadržati:

```text
Stanje pre promene:
Promena:
Backup:
Verifikacija:
Rollback:
Rezultat:
```

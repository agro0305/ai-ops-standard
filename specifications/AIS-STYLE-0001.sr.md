---
document_id: AIS-STYLE-0001
title: Vodič za stil AI-OPS dokumenata
status: Draft
version: 0.2.0
language: sr
canonical: false
reference: AIS-STYLE-0001.md
authors:
  - AI-OPS Project
created: 2026-07-19
updated: 2026-07-19
supersedes: null
superseded_by: null
---

# AIS-STYLE-0001 — Vodič za stil AI-OPS dokumenata

> Ovaj dokument je zvanični srpski prevod. Kanonski dokument je `AIS-STYLE-0001.md` na engleskom jeziku.

## 1. Svrha

Ovaj dokument definiše obaveznu strukturu, metapodatke, terminologiju, normativni jezik, pravila verzionisanja i uredničke konvencije za AI-OPS specifikacije, RFC dokumente, šeme, referentne implementacije i compliance dokumente.

Cilj je da svaki AI-OPS dokument bude dosledan, proverljiv, pogodan za review i dugoročno održavanje.

## 2. Obuhvat

Vodič se primenjuje na:

- AIS specifikacije;
- AI-OPS RFC dokumente;
- machine-readable šeme;
- dokumentaciju referentne implementacije;
- dokumentaciju compliance testova;
- dashboard i API dokumentaciju;
- zvanične prevode.

Ovaj dokument ne definiše tehničko ponašanje AI agenata. To ponašanje definišu pojedinačne AIS specifikacije.

## 3. Normativni jezik

Ključne reči **MUST**, **MUST NOT**, **REQUIRED**, **SHALL**, **SHALL NOT**, **SHOULD**, **SHOULD NOT**, **RECOMMENDED**, **MAY** i **OPTIONAL** imaju normativno značenje kada su napisane velikim slovima.

Svaki normativni zahtev MORA biti:

- nedvosmislen;
- nezavisno proverljiv;
- vezan za jedan dokument;
- označen stabilnim identifikatorom zahteva.

Identifikatori zahteva MORAJU koristiti format:

```text
AIS-<broj-dokumenta>-REQ-<trocifreni-broj>
```

Primer:

```text
AIS-0003-REQ-001
```

Identifikator zahteva NE SME kasnije biti iskorišćen za drugačiji zahtev.

## 4. Identifikatori dokumenata

### 4.1 AIS specifikacije

Normativne specifikacije koriste:

```text
AIS-NNNN
```

### 4.2 Style dokumenti

Dokumenti o stilu i upravljanju koriste:

```text
AIS-STYLE-NNNN
```

### 4.3 RFC dokumenti

Predlozi koji još nisu prihvaćeni koriste:

```text
RFC-NNNN
```

### 4.4 Šeme

Nazivi machine-readable šema TREBA da opisuju objekat i verziju.

## 5. Obavezni metapodaci

Svaki kanonski AIS dokument MORA da sadrži YAML front matter sa sledećim poljima:

```yaml
document_id:
title:
status:
version:
language:
canonical:
authors:
created:
updated:
supersedes:
superseded_by:
```

Pravila:

- `document_id` MORA odgovarati nazivu fajla;
- `version` MORA koristiti SemVer;
- kanonski engleski dokument koristi `canonical: true`;
- prevod koristi `canonical: false`;
- datumi koriste format `YYYY-MM-DD`;
- nepoznate vrednosti MOGU biti `null`.

## 6. Status dokumenta

Dozvoljeni statusi su:

- `Draft` — nepotpun i nestabilan;
- `Review` — spreman za formalnu reviziju;
- `Accepted` — prihvaćen kao deo standarda;
- `Deprecated` — dostupan, ali se više ne preporučuje;
- `Superseded` — zamenjen drugim dokumentom;
- `Withdrawn` — povučen pre prihvatanja.

Dokument NE SME preći direktno iz statusa `Draft` u `Accepted` bez review faze.

## 7. Kanonski jezik i prevodi

Engleski je kanonski jezik projekta AI-OPS.

Zvanični srpski prevodi MORAJU:

- koristiti sufiks `.sr.md`;
- referencirati kanonski dokument;
- sačuvati identifikatore zahteva;
- sačuvati normativno značenje;
- sačuvati numeraciju sekcija gde je praktično;
- ne uvoditi nove zahteve;
- navesti da je engleski dokument kanonski.

Ako postoji neslaganje, prednost ima kanonski engleski dokument.

## 8. Obavezna struktura dokumenta

Normativna AIS specifikacija TREBA da sadrži sledeće sekcije kada su primenljive:

1. Svrha
2. Obuhvat
3. Terminologija
4. Kontekst i opis problema
5. Zahtevi
6. Model podataka
7. Model procesa
8. Bezbednosna razmatranja
9. Razmatranja privatnosti
10. Obrada grešaka
11. Rollback zahtevi
12. Primeri
13. Compliance
14. Reference
15. Istorija izmena

## 9. Pravila za pisanje zahteva

Normativni zahtev MORA da navede:

- odgovornog aktera;
- zahtevano ili zabranjeno ponašanje;
- uslov u kojem se primenjuje;
- rezultat koji se može proveriti.

Dobar primer:

> **AIS-0005-REQ-001:** Pre izmene postojećeg konfiguracionog fajla, agent MORA da napravi backup koji se može vratiti i da njegovu lokaciju zabeleži u izveštaju operacije.

Loš primer:

> Agenti bi verovatno trebalo da prave backup kada je potreban.

## 10. Normativni i nenormativni sadržaj

Normativne sekcije definišu obavezno ponašanje.

Primeri, obrazloženja, implementacione napomene i dijagrami nisu normativni osim kada je drugačije eksplicitno navedeno.

## 11. Primeri koda i komandi

Primeri MORAJU navesti jezik ili format kada je moguće.

Komande NE SMEJU da sadrže stvarne tajne, tokene ili privatne ključeve.

Placeholder vrednosti TREBA da koriste opisna velika slova:

```text
LAN_CIDR
SERVICE_PORT
CONFIG_FILE
BACKUP_PATH
```

## 12. Dijagrami

ASCII dijagrami MOGU biti korišćeni za jednostavne tokove.

Mermaid TREBA koristiti kada je potreban machine-readable dijagram.

Dijagram NE SME biti jedini prikaz normativnog zahteva.

## 13. Tabele

Tabele TREBA koristiti za statuse, mape zahteva, capability matrice, compliance rezultate i istoriju verzija.

## 14. Nazivi fajlova

Kanonska specifikacija:

```text
AIS-0003.md
```

Srpski prevod:

```text
AIS-0003.sr.md
```

RFC:

```text
RFC-0001.md
```

Nazivi fajlova MORAJU koristiti ASCII karaktere, crtice i mala slova za ekstenzije.

## 15. Verzionisanje

Svaki dokument koristi SemVer:

- MAJOR — nekompatibilna normativna izmena;
- MINOR — kompatibilno dodavanje zahteva;
- PATCH — pojašnjenje ili urednička izmena bez promene ponašanja.

## 16. Kontrola izmena

Svaka izmena prihvaćene specifikacije MORA da navede:

- razlog;
- zahteve na koje utiče;
- uticaj na kompatibilnost;
- uticaj na compliance;
- migraciono uputstvo kada je potrebno.

## 17. Unakrsne reference

Dokumenti MORAJU referencirati druge specifikacije stabilnim identifikatorima, na primer:

```text
AIS-0005
AIS-0005-REQ-001
```

## 18. Bezbednost i tajne

Dokumenti i primeri NE SMEJU sadržati stvarne API ključeve, lozinke, privatne tokene, privatne SSH ključeve, produkcione sertifikate ili neredigovane lične podatke.

## 19. Compliance mapiranje

Svaki proverljiv normativni zahtev TREBA da bude povezan sa jednim ili više compliance testova.

Primer:

```yaml
requirement: AIS-0005-REQ-001
tests:
  - compliance/tests/test_backup_before_change.py
```

Zahtev koji nije moguće proveriti automatski MORA definisati ručnu proceduru verifikacije.

## 20. Istorija izmena

| Verzija | Datum | Status | Opis |
|---|---|---|---|
| 0.2.0 | 2026-07-19 | Draft | Početni zvanični srpski prevod proširenog vodiča |

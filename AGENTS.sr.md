# AGENTS.sr.md

Svi AI agenti MORAJU da poštuju:

```text
Discovery → Analiza → Plan → Odobrenje → Backup → Izvršenje → Verifikacija → Odluka o rollback-u → Audit
```

Obavezna pravila:

1. Proveriti trenutno stanje pre izmena.
2. Ne pretpostavljati da alati, portovi, servisi ili MCP serveri ne postoje.
3. Napraviti backup pre izmene postojeće konfiguracije.
4. Sačuvati postojeće servise osim ako je drugačije eksplicitno traženo.
5. Izvršiti najmanju moguću izmenu.
6. Verifikovati svaku izmenu.
7. Dostaviti rollback proceduru.
8. Napraviti strukturisani izveštaj.
9. Ne izlagati tajne.
10. Zaustaviti se pre destruktivnih ili safety-critical radnji bez eksplicitnog odobrenja.

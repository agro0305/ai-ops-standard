# AI-OPS za Kimi Code, Claude Code, OpenCode i Codex

Ovo uputstvo objašnjava kako coding agent koristi AI-OPS Standard, project skill i `aiops-dashboard` MCP server.

## Šta agent stvarno dobija

Agent dobija dva read-only MCP alata:

- `getHealth`
- `getReadiness`

Oni samo proveravaju da li AI-OPS Dashboard radi i da li je spreman.

Oni trenutno ne prave plan, approval, backup, promenu, verifikaciju, rollback ili audit. Te faze agent mora da izvrši drugim raspoloživim alatima i dokumentuje dokazima.

## Fajlovi koje agent koristi

```text
AGENTS.md
CLAUDE.md
.agents/skills/ai-ops-mcp/SKILL.md
examples/openapi-mcp-pydantic-ai/run_mcp_server.sh
examples/openapi-mcp-pydantic-ai/aiops-dashboard.openapi.yaml
```

- `AGENTS.md` sadrži obavezna projektna pravila.
- `CLAUDE.md` učitava pravila za Claude Code.
- `SKILL.md` je zajednički skill za Kimi Code, OpenCode i Codex, a Claude ga dobija preko `CLAUDE.md`.
- `run_mcp_server.sh` pokreće lokalni OpenAPI MCP server.

## Jedino pravilo koje treba zapamtiti

Za jedan infrastrukturni zadatak agent poziva `getHealth` i `getReadiness` jednom na početku.

Ne ponavlja ih posle svakog koraka. Nova provera se radi samo kada je MCP/dashboard restartovan, prethodni poziv nije uspeo, prekinuta je veza, rezultat je zastareo ili korisnik izričito traži novu proveru.

## Kimi Code

Kimi Code automatski pronalazi project skill u:

```text
.agents/skills/ai-ops-mcp/SKILL.md
```

Dodaj project MCP konfiguraciju:

```bash
cd ~/ai-ops-standard
mkdir -p .kimi-code
cp examples/openapi-mcp-pydantic-ai/mcp-config.example.json \
  .kimi-code/mcp.json
```

Ako `.kimi-code/mcp.json` već postoji, ne prepisuj ga. U postojeći objekat `mcpServers` dodaj:

```json
"aiops-dashboard": {
  "command": "bash",
  "args": [
    "examples/openapi-mcp-pydantic-ai/run_mcp_server.sh"
  ]
}
```

Pokretanje:

```bash
cd ~/ai-ops-standard
kimi
```

U Kimi Code proveri status MCP servera jednom komandom:

```text
/mcp
```

Skill se može učitati ručno:

```text
/skill:ai-ops-mcp
```

Primer zadatka:

```text
Koristi ai-ops-mcp skill. Proveri trenutno stanje servisa i predloži
najmanju bezbednu promenu. getHealth i getReadiness pozovi jednom na početku.
Radi jednu komandu po koraku i sačekaj moj rezultat.
```

## Claude Code

Claude Code automatski učitava `CLAUDE.md`, koji upućuje na `AGENTS.md` i AI-OPS skill.

Registruj project MCP server iz korena repozitorijuma:

```bash
cd ~/ai-ops-standard
claude mcp add --scope project aiops-dashboard -- \
  bash examples/openapi-mcp-pydantic-ai/run_mcp_server.sh
```

Pokretanje:

```bash
claude
```

Provera konfiguracije:

```text
/mcp
```

Primer zadatka:

```text
Prati CLAUDE.md i ai-ops-mcp skill. Ovo je infrastrukturni zadatak.
Pozovi getHealth i getReadiness jednom na početku, zatim uradi discovery,
analizu i plan. Ne izvršavaj promenu dok ne odobrim plan.
```

## OpenCode

OpenCode automatski pronalazi:

```text
AGENTS.md
.agents/skills/ai-ops-mcp/SKILL.md
```

U postojeći `opencode.json` dodaj MCP server:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "aiops-dashboard": {
      "type": "local",
      "command": [
        "bash",
        "examples/openapi-mcp-pydantic-ai/run_mcp_server.sh"
      ],
      "enabled": true,
      "timeout": 10000
    }
  }
}
```

Ne prepisuj postojeće sekcije u `opencode.json`; samo spoji objekat `mcp`.

Pokretanje:

```bash
cd ~/ai-ops-standard
opencode
```

Primer zadatka:

```text
Učitaj skill ai-ops-mcp i koristi MCP server aiops-dashboard.
Proveru statusa uradi samo jednom na početku. Zatim prati kompletan AI-OPS tok
za zadatak koji ti zadam.
```

## OpenAI Codex

Codex automatski učitava `AGENTS.md` i project skill iz:

```text
.agents/skills/ai-ops-mcp/SKILL.md
```

Registruj MCP server. Komandu pokreni iz korena repozitorijuma da bi Codex upisao apsolutnu putanju:

```bash
cd ~/ai-ops-standard
codex mcp remove aiops-dashboard 2>/dev/null || true
codex mcp add aiops-dashboard -- \
  bash "$PWD/examples/openapi-mcp-pydantic-ai/run_mcp_server.sh"
```

Provera registracije:

```bash
codex mcp list
```

Pokretanje:

```bash
codex
```

Primer zadatka:

```text
Koristi project skill ai-ops-mcp. Za ovaj infrastrukturni zadatak pozovi
getHealth i getReadiness jednom na početku. Posle toga ne ponavljaj proveru
bez razloga. Prvo uradi discovery i plan, pa sačekaj moje odobrenje.
```

## Univerzalni prompt za sva četiri agenta

```text
Koristi ai-ops-mcp skill. Ovo je infrastrukturni zadatak.

1. Pozovi getHealth i getReadiness jednom na početku i zapamti rezultat.
2. Ne ponavljaj proveru osim ako se dashboard/MCP restartuje, poziv ne uspe,
   veza se prekine, rezultat zastari ili izričito zatražim novu proveru.
3. Prati tok:
   Discovery → Analysis → Plan → Approval → Backup → Execution → Verification
   → Rollback Decision → Audit.
4. Ne pretpostavljaj stanje i ne izmišljaj komande ili MCP alate.
5. Pre izmene napravi backup.
6. Radi jednu komandu po koraku i sačekaj moj izlaz.
7. Na kraju prijavi stanje pre promene, promenu, backup, verifikaciju,
   rollback status i konačni rezultat.
```

## Kada se MCP uopšte ne koristi

Nemoj tražiti od agenta da poziva AI-OPS MCP za:

- pisanje ili ispravljanje dokumentacije;
- običan refactoring;
- formatiranje koda;
- lokalne unit testove;
- analizu koda koja ne menja operativno stanje;
- commit, PR ili pregled diff-a bez infrastrukturne promene.

## OpenAPI Generator

Koristi se samo kada se menja OpenAPI specifikacija ili se traži generisani klijent:

```bash
openapi-generator-cli validate \
  -i examples/openapi-mcp-pydantic-ai/aiops-dashboard.openapi.yaml
```

Generisani klijent ostaje u ignorisanom direktorijumu `generated/` i ne ulazi u commit.

## Pydantic AI i New API

`run_agent.py` je referentni primer posebnog Python agenta. Kimi Code, Claude Code, OpenCode i Codex ne treba da ga pokreću za normalan rad, jer direktno koriste isti MCP server.

Pokreće se samo kada se razvija ili testira Pydantic AI integracija:

```bash
set -a
source ~/.config/aiops/new-api.env
set +a

~/.local/share/pydantic-ai/venv/bin/python \
  examples/openapi-mcp-pydantic-ai/run_agent.py
```

Token ostaje u `~/.config/aiops/new-api.env`, nikada u repozitorijumu.

## Očekivani završni izveštaj agenta

```text
Stanje pre promene:
Promena:
Backup:
Verifikacija:
Rollback:
Rezultat:
```

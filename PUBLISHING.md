# Publishing AI-OPS Standard 0.2.0

This checklist covers the first public release after the publication pull request is merged.

## 1. Verify the merged main branch

```bash
git switch main
git pull
python3 scripts/validate_repository.py
python3 -m pytest -q compliance/tests
python3 scripts/acceptance.py --project-root . --output acceptance-result.json
```

Do not publish when any check fails.

## 2. Enable GitHub Pages

In the repository:

1. Open **Settings → Pages**.
2. Under **Build and deployment**, choose **GitHub Actions** as the source.
3. Run the **Publish documentation** workflow when it does not start automatically.
4. Confirm the site is available at `https://agro0305.github.io/ai-ops-standard/`.

## 3. Create the version tag

```bash
git tag -a v0.2.0 -m "AI-OPS Standard 0.2.0"
git push origin v0.2.0
```

## 4. Create the GitHub Release

Create a release from tag `v0.2.0` with title:

```text
AI-OPS Standard 0.2.0
```

Use `docs/releases/0.2.0.md` as the release description. Mark it as a pre-release while the normative specifications remain Draft.

## 5. Connect Zenodo

1. Sign in to Zenodo using the GitHub account that owns the repository.
2. Enable the `ai-ops-standard` repository in the GitHub integration.
3. Confirm that the `v0.2.0` release is archived and receives a DOI.
4. Add the DOI badge to `README.md` in a follow-up pull request.

Zenodo will read `.zenodo.json`; GitHub and citation tools will read `CITATION.cff`.

## 6. Repository settings

Recommended settings:

- enable private vulnerability reporting;
- enable Discussions for support and design conversations;
- require the validation and documentation checks before merging to `main`;
- enable automatically deleting merged branches;
- set the repository description and website to the documentation site;
- add topics: `ai-ops`, `devops`, `linux`, `mcp`, `ai-agents`, `safety`, `audit`.

## 7. Promotion gate

Promotion begins only after:

- GitHub Release is public;
- Pages site is available;
- citation metadata is visible;
- Zenodo DOI exists or is pending without errors;
- issue templates and security reporting work.

# sarif-verify

Validate a SARIF 2.1.0 log **before** GitHub code scanning sees it.

`upload-sarif` fails late and vaguely: a `ruleIndex` that disagrees with
`ruleId` silently mislabels findings, an absolute artifact URI gets the whole
upload rejected, and a `startLine` of `0` drops the annotation without any
error. `sarif-verify` catches those mistakes locally, in under a second, with
no network access and no runtime dependencies.

```
$ sarif-verify check results.sarif
OK   results.sarif | 0 error(s), 0 warning(s)

$ sarif-verify check broken.sarif
ERROR result-rule-index: ruleIndex 0 points at 'missing-key', not 'empty-value' [runs[0].results[0].ruleIndex]
ERROR uri-relative: uri 'C:/repo/.env' is not repository relative [runs[0].results[0].locations[0].physicalLocation.artifactLocation.uri]
FAIL broken.sarif | 2 error(s), 0 warning(s)
```

## Why not just use the schema?

A JSON-schema check tells you the document is shaped correctly. It does not tell
you the document will *work*. The checks here encode the code-scanning contract
instead:

| Code | Level | What it catches |
| --- | --- | --- |
| `document-type` | error | Top level is not a JSON object |
| `version` | error | `version` is missing or not `2.1.0` |
| `runs` | error | `runs` is missing, empty, or not an array |
| `driver-name` | error | `run.tool.driver.name` is empty (upload rejected) |
| `driver-version` | warning | Tool version missing, so annotations cannot be traced to a release |
| `rules-id` | error | A rule has no usable `id` |
| `rules-duplicate` | error | Two rules share an `id`, making `ruleIndex` ambiguous |
| `column-kind` | warning | `columnKind` outside `utf16CodeUnits` / `unicodeCodePoints` |
| `result-message` | error | A result has no `message.text`, so the annotation renders blank |
| `result-rule` | error | `ruleId` is not declared in `driver.rules` |
| `result-rule-index` | error | `ruleIndex` is out of range or disagrees with `ruleId` |
| `result-level` | error | `level` outside `none` / `note` / `warning` / `error` |
| `result-location` | warning | No location, or no `artifactLocation.uri` |
| `uri-relative` | error | Absolute path, `file://` URI, or `..` traversal |
| `region-lines` | error | `startLine` is not a positive integer, or `endLine` precedes it |

Errors fail the run; warnings fail it only under `--strict`.

## Install

```bash
pip install git+https://github.com/hamids-ai-automations/sarif-verify.git
# or, from a checkout
pip install -e .
```

Requires Python 3.11+. No third-party dependencies.

## Usage

```bash
sarif-verify check results.sarif                 # one file
sarif-verify check a.sarif b.sarif              # several files, exit 1 if any fails
sarif-verify check results.sarif --strict       # warnings become failures
sarif-verify check results.sarif --json         # machine-readable report
sarif-verify check - < results.sarif            # stdin
sarif-verify checks                             # list every check with help text
sarif-verify version
```

Exit codes: `0` clean, `1` findings, `2` unreadable file or invalid JSON.

### In a GitHub Actions workflow

Run it as the step immediately before the upload, so a malformed log fails with
a readable message instead of an opaque `upload-sarif` error:

```yaml
jobs:
  scan:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      security-events: write
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install git+https://github.com/hamids-ai-automations/sarif-verify.git
      - run: envscope check --sarif results.sarif      # produces the log
      - run: sarif-verify check --strict results.sarif # fails fast if malformed
      - uses: github/codeql-action/upload-sarif@v3
        with:
          sarif_file: results.sarif
```

### In Python

```python
from sarif_verify import validate

report = validate(document, source="results.sarif")
if not report.ok:
    for finding in report.errors:
        print(finding.code, finding.path, finding.message)
```

`validate` never raises on malformed input; it returns a `Report` with
`findings`, `errors`, `warnings`, `ok`, `stats()` and `to_dict()`.

## Docker

```bash
docker build -t sarif-verify .
docker run --rm -v "$PWD:/work" sarif-verify check /work/results.sarif
```

The image runs the demo when started without arguments, so `docker run --rm sarif-verify`
shows the validator working with zero setup.

## Working demo

```bash
python -m sarif_verify.demo
```

The demo builds a deliberately broken log in memory - wrong `ruleIndex`,
undeclared `ruleId`, absolute URI, `startLine: 0` - and prints the findings,
exiting `1` exactly as CI would. `fixtures/good.sarif` is the clean counterpart.

## Development

```bash
python -m unittest discover -s tests -v   # stdlib only, no extra installs
make demo                                 # same as python -m sarif_verify.demo
```

CI runs the suite on Python 3.11, 3.12 and 3.13, plus a Docker build and a
self-check of `fixtures/good.sarif`.

## Scope

This is a contract validator, not a full SARIF JSON-schema implementation. It
checks the fields that decide whether an upload succeeds and whether annotations
land in the right place; it does not validate `fixes`, `codeFlows`, `graphs`, or
external `$schema` references. A clean run means "this log will upload", not
"this log is semantically ideal".

## License

MIT. See [LICENSE](LICENSE).

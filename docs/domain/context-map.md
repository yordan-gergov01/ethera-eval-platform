# Context map

Source: brief §5 ("Candidate modules") and §7. The five bounded contexts are **candidates, to
be confirmed at HUMAN GATE A**. No module package exists yet: each is created by the
`add-module` skill in the slice that first needs it (import-linter refuses a contract that
names a missing module).

## Contexts

| Module | Owns | Table prefix | First slice | Status |
|---|---|---|---|---|
| `registry` | Products, Manifests, Model Bindings, allowed providers, owners | `reg_` | 001 | candidate |
| `evaluation` | Datasets, Goldens, Metrics (definitions), Eval Runs, Trials, Case Results | `eval_` | 002–003 | candidate |
| `comparison` | Baselines, Comparisons, Gate Verdicts, Recommendations, Candidates (definition) | `cmp_` | 004 | candidate |
| `model_watch` | Catalog snapshots, Model Changes, affected-Product selection, Candidate scheduling | `mw_` | 005 | candidate |
| `notification` | Notifications, channels, weekly digest | `ntf_` | 006 | candidate |
| platform core (`backend`) | Identity and access, messaging, audit, spend, health, settings, errors | template names | A1 | accepted |

`runner` (Trial execution, Judges, Metric application) and `demo_target` (the product under
test) are processes, not bounded contexts of the backend: they share no tables and talk only
through RabbitMQ and HTTP inside the sandbox.

## Allowed relationships (proposed — each edge confirmed at the Gate B of the slice that first needs it)

Arrows read "imports the barrel of". Only these edges are allowed; import-linter enforces
them as modules appear.

```
            ┌────────────┐
            │  registry  │◄──────────────────────────────┐
            └─────▲──────┘                               │
                  │                                      │
            ┌─────┴──────┐        ┌──────────────┐       │
            │ evaluation │◄───────┤  comparison  │       │
            └────────────┘        └──────▲───────┘       │
                                         │               │
                                  ┌──────┴───────┐       │
                                  │ model_watch  ├───────┘
                                  └──────▲───────┘
                                         │ (none: notification is reached by events)
                                  ┌──────┴───────┐
                                  │ notification │──► registry, comparison, model_watch (read evidence)
                                  └──────────────┘
```

- `evaluation → registry`: an Eval Run reads the Product and its Manifest.
- `comparison → evaluation, registry`: a Comparison reads two Eval Runs and the Manifest's
  cost and latency limits.
- `model_watch → comparison, registry`: a Model Change selects Products and schedules
  Candidates.
- `notification → registry, comparison, model_watch`: a Notification links its evidence.
- Every module → platform core barrels (auth dependencies, errors, audit, spend, messaging).
- No module imports `notification`; it is reached only through domain events consumed in the
  same change set (no event without a consumer).

## Upstream/downstream

- Platform core is upstream of every module (conformist: modules adopt its identity model,
  errors and envelope).
- `registry` is upstream of everything else; `notification` is the most downstream.
- `demo_target` is an external system behind the `SandboxLauncher` port (anti-corruption:
  the runner translates its `/chat` response into Trial evidence).

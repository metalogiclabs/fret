# FRET → Ogma: bounded native-translation research

Status: **research experiment**, not an established upstream defect or a fix.
No issue or pull request is opened by this branch.

Pinned sources:

- FRET: `NASA-SW-VnV/fret@cf0f913cc15c41705e803593297e89cd6056b839`
- Ogma: `nasa/ogma@08b384b4335cce324fac74577adc7f08e61b7cce`

The JavaScript probe executes the actual `FretModel.exportComponent` method
and referenced variable-mapping helper bodies inside a test harness using the
five FRET Copilot EJS templates and fixture databases. It **does not** run the
Electron app or a real database. It produces four JSON exports:

| Scenario | Requirements | One variable's `completed` flag |
| --- | --- | --- |
| `sensor-mapped` | Synthetic `H(sensor_ok)` | `sensor_ok: true` |
| `sensor-unmapped` | Identical | `sensor_ok: false` |
| `fsm-mapped` | All 13 from published `caseStudies/FiniteStateMachine` | `standby: true` |
| `fsm-unmapped` | Identical | `standby: false` |

The native workflow uses the current Ogma `standalone --input-format fcs
--prop-format smv` interface to translate each output separately. Its result
artifact includes input JSON, per-scenario exit code, Ogma logs, and generated
code when successful. A successful CLI exit alone is not evidence that the
generated Copilot program compiles, so generated type signatures must be
inspected independently.

Important counterevidence: Ogma's `Data.Spec.Extra.addMissingIdentifiers`
**adds** undeclared requirement identifiers as external variables, assigning
an empty type string. `Command.Standalone` explicitly invokes this function.
The pertinent question is thus whether that inferred variable declaration
has a sound type, not whether Ogma necessarily drops the identifier. The
original stronger omission claim is **not established**.

Interpretation:

- If mapped and unmapped scenarios both translate, inspect the difference in
  generated declarations and type-check the output before advancing a claim.
- If the unmapped variant fails and mapped succeeds, isolate the failure to a
  minimal reproducible input and exclude errors unrelated to type mapping.
- If the pinned toolchain cannot build, the research remains **UNKNOWN** at
  the native boundary; the source-level FRET export behavior remains proven.

No upstream contact or PR is authorized by this branch.

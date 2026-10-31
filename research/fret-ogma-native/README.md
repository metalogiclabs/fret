# FRET → Ogma: bounded native-translation research

Status: **WARRANTED, bounded native-generated declaration/type-hole differential**;
not a complete end-to-end FRET-UI/Copilot-monitor build or an upstream fix.
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

## Executed evidence — 2026-10-31

- [Pinned native Ogma run 41241267388](https://github.com/metalogiclabs/fret/actions/runs/41241267388), commit `45cd1563ce146f9bef1e8e19e83d21b2eb9e4232`, succeeded. Artifact [13058326129](https://github.com/metalogiclabs/fret/actions/runs/41241267388/artifacts/13058326129) holds all four input JSON files, generated `Copilot.hs` files, and CLI logs. All four `ogma standalone` invocations returned exit code `0`.
- Exact generated diff for the controlled single-input case:

  ```diff
  - sensor_ok :: Stream (Bool)
  + sensor_ok :: Stream (_)
    sensor_ok = extern "sensor_ok" Nothing
  ```

  The published FSM case-study control produces the same `Bool` → `_` type change for `standby`, while Ogma still emits it as an external stream.
- [Isolated native GHC run 41242957839](https://github.com/metalogiclabs/fret/actions/runs/41242957839), commit `8e929d4339969f4dcb2a3cde8c3bd7f0e814f985`, succeeded as an **expected-negative control**. Artifact [13057968530](https://github.com/metalogiclabs/fret/actions/runs/41242957839/artifacts/13057968530) holds the extracted declarations and compiler logs. Both source lines were copied verbatim from native Ogma output into tiny self-contained `Stream` stubs; no Copilot libraries were needed. GHC 9.2.8: mapped exit `0`, unmapped exit `1`, with `Found type wildcard '_'` and a diagnostic requiring `PartialTypeSignatures`.

This is concrete evidence that a documented incomplete FRET mapping can pass
native Ogma generation while producing a type declaration rejected by normal
GHC rules. It is **not** a whole-monitor compilation test: the GHC control
extracts the actual generated declaration and stubs unrelated Copilot imports.
It also does not prove a problem with the checked-in FSM case study as-is; the
`standby.completed=false` state was introduced solely as a controlled test.
Next residuals: supported FRET UI/database reproduction, full generated-monitor
build, exact responsibility and smallest repair, then an independent duplicate
check before considering upstream contact.

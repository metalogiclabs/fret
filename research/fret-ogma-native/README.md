# FRET → Ogma: bounded native-translation research

Status: **WARRANTED, bounded native-generated declaration/type-hole differential**;
not a complete end-to-end FRET-UI/Copilot-monitor build or an upstream fix.
No issue or pull request is opened by this branch.

Pinned sources:

- FRET: `NASA-SW-VnV/fret@cf0f913cc15c41705e803593297e89cd6056b839`
- Ogma: `nasa/ogma@08b384b4335cce324fac74577adc7f08e61b7cce`

The JavaScript probe executes the actual FRET `createOrUpdateVariables`
initializer, `FretModel.exportComponent` method, referenced variable-mapping
helper bodies, and five Copilot EJS templates, with fixture databases. It also
checks the actual Analysis Portal's unconditional Copilot export branch.
It **does not** run Electron or a real database. It produces four JSON exports:

| Scenario | Requirements | Variable state |
| --- | --- | --- |
| `sensor-mapped` | Synthetic `H(sensor_ok)` | `Input`, `boolean`, `completed:true` |
| `sensor-unmapped` | Identical | FRET's actual new-variable default: `idType:''`, `dataType:''`, `completed:false` |
| `fsm-mapped` | All 13 from published `caseStudies/FiniteStateMachine` | Existing `standby.completed:true` |
| `fsm-unmapped` | Identical | Only `standby.completed:false` (synthetic flag mutation) |

Unlike an earlier exploratory fixture with a typed Input and artificially
incomplete flag, the current negative sensor arm represents the naturally
initialized state before a user fills in any mapping. FRET's normal variable
save logic would mark a typed `boolean` Input complete. The FSM toggle remains
an independent source-differential control, not a claim of UI reachability.

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
- Source-reexecuting the naturally initialized sensor case produces **byte-identical JSON** to the inputs from the pinned native Ogma run: unmapped SHA-256 `5b11e0de630e4db120e3ceff34330cdcf19ee52a177df7d2c2806dc45f013de7`; mapped SHA-256 `cdca32ab8320a82deb90456e5b3470c8ca8a77e0defb82ef6f49939ce5848842`. This connects the supported UI code path to the earlier native/GHC results without changing either input's bytes.
- [UI-default export + isolated GHC CI run 41245886916](https://github.com/metalogiclabs/fret/actions/runs/41245886916) passed the actual FRET variable-initializer assertions, both native-input SHA-256 equality checks, and the expected mapped-pass/unmapped-fail GHC control. This avoids relying on the earlier artificial `completed:false` Input fixture.

FRET's Analysis Portal manual expressly allows Copilot export *without* variable
mapping information and leaves that export button enabled. The tested state is
therefore consistent with its documented workflow. The result is a generated
code readiness / diagnostics **hazard**, not by itself proof that FRET should
block export or that Ogma's fallback is unintentionally designed. The ownership
and any repair need an explicit contract decision.

Full-monitor type checking must use Copilot compatible with pinned Ogma's
`ogma-core.cabal` requirements: both `copilot-language` and
`copilot-libraries` must be at least 4.7.1 and less than 4.9. Ubuntu's distro
packages at version `4.6.1` cannot serve as a
mapped control: the generated import modules are not all provided. A complete
program check is a separate gate from the declaration-level GHC result.

This is concrete evidence that a documented incomplete FRET mapping can pass
native Ogma generation while producing a type declaration rejected by normal
GHC rules. It is **not** a whole-monitor compilation test: the GHC control
extracts the actual generated declaration and stubs unrelated Copilot imports.
It also does not prove a problem with the checked-in FSM case study as-is; the
`standby.completed=false` state was introduced solely as a controlled test.
Next residuals: supported FRET UI/database reproduction, full generated-monitor
build, exact responsibility and smallest repair, then an independent duplicate
check before considering upstream contact.

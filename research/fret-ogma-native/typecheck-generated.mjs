// Extract the exact native Ogma-generated external declaration into a minimal
// self-contained GHC module, isolating type checking from Copilot dependencies.
// This does NOT compile the complete generated standalone monitor.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const artifact = process.env.OGMA_ARTIFACT_DIR || path.join(here, 'out/native');
const output = path.join(here, 'out/ghc-minimal');
fs.mkdirSync(output, {recursive:true});

for (const [scenario, type, moduleName] of [
  ['sensor-mapped', 'Bool', 'SensorMapped'],
  ['sensor-unmapped', '_', 'SensorUnmapped'],
]) {
  const file = path.join(artifact, scenario, 'generated/Copilot.hs');
  const code = fs.readFileSync(file, 'utf8');
  assert.doesNotMatch(code, /LANGUAGE\s+PartialTypeSignatures/,
    'the source standalone template has no type-hole extension');
  const expression = code.match(/^sensor_ok :: Stream \([^\n]+\)\nsensor_ok = extern "sensor_ok" Nothing$/m);
  assert.ok(expression, `${scenario} has the expected native external declaration`);
  assert.equal(expression[0].split('\n')[0], `sensor_ok :: Stream (${type})`);

  const minimal = `module ${moduleName} where\n\n`
    + 'data Stream a = Stream\n'
    + 'extern :: String -> Maybe a -> Stream a\n'
    + 'extern _ _ = Stream\n\n'
    + expression[0] + '\n';
  const target = path.join(output, `${moduleName}.hs`);
  fs.writeFileSync(target, minimal);
  console.log(`${scenario}: extracted exact native Ogma declaration to ${target}`);
}

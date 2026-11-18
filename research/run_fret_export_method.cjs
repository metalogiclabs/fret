// Materialize original and explicit diagnostic control using FRET's actual
// pinned exportComponent method. The database and EJS/Webpack loader are
// substituted, not the original method, mapping helpers, or source template.
const fs = require('node:fs');
const path = require('node:path');
const {createHash} = require('node:crypto');
const assert = require('node:assert/strict');
const {exportFromSource, PINNED_FRET} = require('./fret_export_method.cjs');

const CONTROL = 'H(((rearprop or hover_control_mode) and not (rearprop and hover_control_mode)))';
const ORIGINAL = 'H((rearprop xor hover_control_mode))';

function hash(bytes) {
  return createHash('sha256').update(bytes).digest('hex');
}

function argumentsFromCLI(args) {
  const parsed = {};
  while (args.length) {
    const key = args.shift();
    if (!['--fret', '--out', '--baseline'].includes(key) || !args.length)
      throw new Error('Usage: node run_fret_export_method.cjs --fret DIR --out DIR [--baseline JSON]');
    parsed[key.slice(2)] = args.shift();
  }
  if (!parsed.fret || !parsed.out) throw new Error('Both --fret and --out required');
  return parsed;
}

async function main(argv) {
  const args = argumentsFromCLI([...argv]);
  const fretDir = path.resolve(args.fret);
  const out = path.resolve(args.out);
  const casePath = path.join(fretDir, 'caseStudies/LiftPlusCruise/LPC_full_reqts_and_vars.json');
  const opts = {
    fretDir, casePath,
    reqIds: ['LPC_REARPROP'],
    variableNames: ['rearprop', 'hover_control_mode'],
  };
  const [original, control, full] = await Promise.all([
    exportFromSource(opts),
    exportFromSource({...opts, changeFormula: CONTROL}),
    exportFromSource({fretDir, casePath}),
  ]);
  assert.equal(original.files.length, 1);
  assert.equal(control.files.length, 1);
  assert.equal(full.files.length, 1);
  const originalContent = original.files[0].content;
  const controlContent = control.files[0].content;
  const o = JSON.parse(originalContent).vehicleSpec;
  const c = JSON.parse(controlContent).vehicleSpec;
  const all = JSON.parse(full.files[0].content).vehicleSpec;
  assert.equal(o.Requirements.length, 1);
  assert.equal(o.Requirements[0].name, 'LPC_REARPROP');
  assert.equal(o.Requirements[0].CoCoSpecCode, ORIGINAL);
  assert.equal(c.Requirements[0].CoCoSpecCode, CONTROL);
  assert.deepEqual(o.Other_variables, c.Other_variables);
  assert.deepEqual(o.Other_variables, [
    {name: 'hover_control_mode', type: 'bool'},
    {name: 'rearprop', type: 'bool'},
  ]);

  fs.mkdirSync(out, {recursive: true});
  fs.writeFileSync(path.join(out, 'method-original.json'), originalContent);
  fs.writeFileSync(path.join(out, 'method-control.json'), controlContent);
  fs.writeFileSync(path.join(out, 'method-full-project.json'), full.files[0].content);
  const receipt = {
    scope: 'source-pinned FretModel.exportComponent and mapping helpers via VM; substituted model DB and EJS/Webpack loader; NOT FRET Electron GUI',
    sourcePin: PINNED_FRET,
    sourceCaseSha256: original.caseSha256,
    sourceModelSha256: original.methodSha256,
    originalSha256: hash(originalContent),
    controlSha256: hash(controlContent),
    fullProjectSha256: hash(full.files[0].content),
    methodOutputSignalOrder: o.Other_variables.map(v => v.name),
    fullProjectVariables: all.Other_variables.length,
    fullProjectRequirements: all.Requirements.length,
    originalFormula: ORIGINAL,
    diagnosticFormula: CONTROL,
    baselineComparison: null,
  };
  if (args.baseline) {
    const baseline = JSON.parse(fs.readFileSync(args.baseline, 'utf8')).vehicleSpec;
    assert.equal(baseline.Requirements[0].CoCoSpecCode, ORIGINAL);
    const sameFormula = baseline.Requirements[0].CoCoSpecCode === o.Requirements[0].CoCoSpecCode;
    const sameSignals = JSON.stringify([...baseline.Other_variables].sort((a,b)=>a.name.localeCompare(b.name)))
      === JSON.stringify([...o.Other_variables].sort((a,b)=>a.name.localeCompare(b.name)));
    assert.ok(sameFormula && sameSignals);
    receipt.baselineComparison = {
      sameFormula, sameSignalSet: sameSignals,
      baselineSignalOrder: baseline.Other_variables.map(v => v.name),
      methodSignalOrder: receipt.methodOutputSignalOrder,
      addedPCTLField: !Object.hasOwn(baseline.Requirements[0], 'PCTL') &&
        Object.hasOwn(o.Requirements[0], 'PCTL'),
    };
  }
  fs.writeFileSync(path.join(out, 'method-receipt.json'), JSON.stringify(receipt, null, 2) + '\n');
  process.stdout.write(JSON.stringify(receipt, null, 2) + '\n');
}

if (require.main === module) {
  main(process.argv.slice(2)).catch(error => {
    process.stderr.write(`${error.stack}\n`);
    process.exitCode = 1;
  });
}

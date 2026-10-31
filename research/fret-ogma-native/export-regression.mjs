// Source-executed FRET Copilot export test: no Electron or database installation.
// Run with FRET_SRC and OGMA_SRC set to pinned source checkouts.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, '../..');
const fret = process.env.FRET_SRC || root;
const ogma = process.env.OGMA_SRC || path.join(root, 'ogma-source');
const destination = process.env.PROBE_OUTPUT_DIR || path.join(here, 'out');
const require = createRequire(import.meta.url);
const ejs = require('ejs');
const utils = require(path.join(fret, 'fret-electron/support/utils.js'));
const read = p => fs.readFileSync(p, 'utf8');

const helperPath = path.join(fret, 'fret-electron/model/modelDbSupport/variableMappingSupports.js');
const helperSource = read(helperPath)
  .replace(/^import .*\n/gm, '')
  .replace(/^export \{[\s\S]*?\}\s*/m, '');
const helperContext = {
  console,
  require(id) {
    if (id === '../../support/utils') return utils;
    return {};
  },
};
vm.runInNewContext(
  helperSource + '\n;globalThis.api={getContractInfo,getPropertyInfo,getDelayInfo,variableIdentifierReplacement}',
  helperContext,
  { filename: helperPath },
);
const {getContractInfo, getPropertyInfo, getDelayInfo, variableIdentifierReplacement} = helperContext.api;

const templateDir = path.join(fret, 'fret-electron/support/CoPilotTemplates');
const templateOrder = ['Component', 'InternalVariables', 'OtherVariables', 'Functions', 'RequirementDefinitions'];
const renderPinnedTemplates = data => templateOrder
  .map(name => ejs.render(read(path.join(templateDir, `${name}.ejs`)), data,
    {filename: path.join(templateDir, `${name}.ejs`)}))
  .join('');

const methodPath = path.join(fret, 'fret-electron/model/FretModel.js');
const modelSource = read(methodPath);
const methodStart = modelSource.indexOf('async exportComponent(evt,args){');
const methodEnd = modelSource.indexOf('  async exportTestObligations', methodStart);
assert.ok(methodStart >= 0 && methodEnd > methodStart, 'FRET exportComponent found');
const methodBody = modelSource.slice(methodStart, methodEnd);

// Read both the actual format and the native missing-identifier behavior.
const format = read(path.join(ogma, 'ogma-core/data/formats/fcs_smv'));
const extra = read(path.join(ogma, 'ogma-core/src/Data/Spec/Extra.hs'));
assert.match(format, /specExternalVars\s*=\s*Just "\.\.Other_variables\[\*\]"/);
assert.match(format, /specRequirementExpr\s*=\s*"\.ptLTL"/);
assert.match(extra, /newVars\s*=\s*map \(`ExternalVariableDef` ""\) newVarNames/,
  'Ogma supplies missing identifiers with an empty type');

async function exportFixture(variableDocs, {component, project, requirementDocs}) {
  const selection = {component_name: component, project, completed: true, modeldoc: false};
  const modelDB = {
    find({selector}) {
      assert.deepEqual(JSON.parse(JSON.stringify(selector)), selection);
      const docs = variableDocs.filter(doc => Object.entries(selector)
        .every(([key, value]) => doc[key] === value));
      return Promise.resolve({docs});
    },
  };
  const leveldbDB = {
    find({selector}) {
      assert.equal(selector.project, project);
      return Promise.resolve({docs: requirementDocs});
    },
  };
  const context = {
    console, modelDB, leveldbDB,
    getContractInfo, getPropertyInfo, getDelayInfo, variableIdentifierReplacement,
    ejsCacheCoPilot: {renderCoPilotSpec: () => ({contract: {complete: renderPinnedTemplates}})},
  };
  vm.runInNewContext(`class AuditFretModel { ${methodBody} }; globalThis.Model=AuditFretModel;`,
    context, {filename: methodPath});
  const files = await new context.Model().exportComponent(null, [component, project, 'copilot']);
  assert.equal(files.length, 1);
  const output = JSON.parse(files[0].content);
  assert.ok(output[`${component}Spec`]);
  return {output, spec: output[`${component}Spec`]};
}

const sensorReq = [{
  reqid: 'R_sensor',
  fulltext: 'The controller shall maintain sensor_ok',
  semantics: {
    component_name: 'Controller',
    CoCoSpecCode: 'H(sensor_ok)',
    ptExpanded: '(H sensor_ok)',
  },
}];
const sensor = {variable_name:'sensor_ok',component_name:'Controller',project:'Audit',
  modeldoc:false,idType:'Input',dataType:'boolean'};
const simpleMapped = await exportFixture([{...sensor, completed:true}],
  {component:'Controller',project:'Audit',requirementDocs:sensorReq});
const simpleUnmapped = await exportFixture([{...sensor, completed:false}],
  {component:'Controller',project:'Audit',requirementDocs:sensorReq});
assert.deepEqual(simpleUnmapped.spec.Requirements, simpleMapped.spec.Requirements);
assert.deepEqual(simpleMapped.spec.Other_variables.map(v => v.name), ['sensor_ok']);
assert.equal(simpleUnmapped.spec.Other_variables.length, 0);

// A published, realistic FRET example, with precisely one variable flag toggled.
const study = JSON.parse(read(path.join(fret, 'caseStudies/FiniteStateMachine/fsm_reqts_and_vars.json')));
const studyVars = study.variables.filter(v => v.project === 'FSM' && v.component_name === 'FSM');
const studyReqs = study.requirements.filter(v => v.project === 'FSM'
  && v.semantics?.component_name === 'FSM');
assert.ok(studyVars.some(v => v.variable_name === 'standby' && v.completed === true));
assert.ok(studyReqs.some(v => v.semantics.ptExpanded.includes('standby')));
const studyMapped = await exportFixture(studyVars,
  {component:'FSM',project:'FSM',requirementDocs:studyReqs});
const studyUnmapped = await exportFixture(studyVars.map(v => v.variable_name === 'standby'
  ? {...v,completed:false} : v),
  {component:'FSM',project:'FSM',requirementDocs:studyReqs});
assert.deepEqual(studyUnmapped.spec.Requirements, studyMapped.spec.Requirements);
assert.equal(studyMapped.spec.Requirements.length, 13);
assert.ok(studyMapped.spec.Other_variables.some(v => v.name === 'standby'));
assert.ok(!studyUnmapped.spec.Other_variables.some(v => v.name === 'standby'));

fs.mkdirSync(destination, {recursive: true});
const scenarios = [
  ['sensor-mapped', simpleMapped],
  ['sensor-unmapped', simpleUnmapped],
  ['fsm-mapped', studyMapped],
  ['fsm-unmapped', studyUnmapped],
];
for (const [name, scenario] of scenarios) {
  fs.writeFileSync(path.join(destination, `${name}.json`),
    JSON.stringify(scenario.output, null, 2) + '\n');
}
console.log(JSON.stringify({
  fret: 'cf0f913cc15c41705e803593297e89cd6056b839',
  ogma: '08b384b4335cce324fac74577adc7f08e61b7cce',
  test: 'actual FRET method/helper/template bodies, fixture databases',
  scenarios: scenarios.map(([name, {spec}]) => ({name,
    requirements: spec.Requirements.length,
    externalVariables: spec.Other_variables.map(v => v.name)})),
  ogmaSourceObservation: 'missing identifiers are synthesized with empty type; check generated code and native behavior',
  output: destination,
}, null, 2));

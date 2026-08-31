import { strict as assert } from 'node:assert'
import { readFile } from 'node:fs/promises'
import { dirname, resolve } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
const repoRoot = resolve(here, '..', '..')
const paramsModule = await import(
  pathToFileURL(resolve(repoRoot, 'src/utils/jenkinsParams.js')).href
)
const entriesSource = await readFile(
  resolve(repoRoot, 'src/admin/pages/Jenkins/Entries.vue'),
  'utf8'
)
const entryEditorSource = await readFile(
  resolve(
    repoRoot,
    'src/admin/pages/Jenkins/EntryEditor.vue'
  ),
  'utf8'
)
const parameterTableSource = await readFile(
  resolve(
    repoRoot,
    'src/admin/pages/Jenkins/components/JenkinsParameterTable.vue'
  ),
  'utf8'
)
const multiSelectSource = await readFile(
  resolve(
    repoRoot,
    'src/admin/pages/Jenkins/components/JenkinsMultiSelectDialog.vue'
  ),
  'utf8'
)
const parameterUiSource = `${entryEditorSource}\n${parameterTableSource}\n${multiSelectSource}`
const routesSource = await readFile(
  resolve(repoRoot, 'src/admin/routes.js'),
  'utf8'
)

assert.equal(
  paramsModule.normalizeJenkinsParamType('StringParameterDefinition'),
  'string',
  'StringParameterDefinition should normalize to string'
)
assert.equal(
  paramsModule.normalizeJenkinsParamType(
    'hudson.model.BooleanParameterDefinition'
  ),
  'boolean',
  'fully-qualified boolean parameter types should normalize to boolean'
)
assert.equal(
  paramsModule.normalizeJenkinsParamType('ChoiceParameterDefinition'),
  'choice',
  'ChoiceParameterDefinition should normalize to choice'
)
assert.equal(
  paramsModule.normalizeJenkinsParamType(
    'com.cwctravel.hudson.plugins.extended_choice_parameter.ExtendedChoiceParameterDefinition'
  ),
  'extendedChoice',
  'ExtendedChoiceParameterDefinition should normalize to extendedChoice'
)
assert.equal(
  paramsModule.getParamTypeLabelKey('StringParameterDefinition'),
  'paramTypes.string',
  'string parameter label key should be stable'
)

const rows = paramsModule.buildParamRowsFromDefinitions(
  [
    {
      name: 'OS_VERSION',
      type: 'ChoiceParameterDefinition',
      default_value: 'centos9',
      choices: ['centos8', 'centos9'],
      description: 'Target OS'
    }
  ],
  {
    os_version: {
      mode: 'editable',
      default_value: 'centos8'
    }
  }
)

assert.deepEqual(
  rows.map(({ key, ...row }) => row),
  [
    {
      name: 'OS_VERSION',
      type: 'choice',
      raw_type: 'ChoiceParameterDefinition',
      mode: 'editable',
      default_value: 'centos9',
      description: 'Target OS',
      choices: ['centos8', 'centos9'],
      locked: true,
      value_source: ''
    }
  ],
  'definition rows should preserve Jenkins raw type and normalized type'
)

assert.deepEqual(
  paramsModule.buildParamsConfigFromRows(rows),
  {
    OS_VERSION: {
      mode: 'editable',
      default_value: 'centos9',
      type: 'choice',
      raw_type: 'ChoiceParameterDefinition',
      choices: ['centos8', 'centos9'],
      description: 'Target OS'
    }
  },
  'saved params_config should retain normalized type, raw type, choices, and description'
)

assert.deepEqual(
  paramsModule.normalizeRuntimeParam({
    name: 'USE_CACHE',
    type: 'BooleanParameterDefinition',
    default_value: true
  }),
  {
    name: 'USE_CACHE',
    type: 'boolean',
    raw_type: 'BooleanParameterDefinition',
    default_value: true,
    choices: [],
    description: '',
    mode: 'editable'
  },
  'runtime params should expose a normalized type while retaining the raw Jenkins type'
)

const extendedChoiceParam = paramsModule.normalizeRuntimeParam({
  name: 'TARGETS',
  type: 'ExtendedChoiceParameterDefinition',
  default_value: 'api,worker',
  choices: ['api', 'worker', 'scheduler']
})

assert.deepEqual(
  extendedChoiceParam,
  {
    name: 'TARGETS',
    type: 'extendedChoice',
    raw_type: 'ExtendedChoiceParameterDefinition',
    default_value: ['api', 'worker'],
    choices: ['api', 'worker', 'scheduler'],
    description: '',
    mode: 'editable'
  },
  'extended choice runtime params should expose array defaults for multi-select controls'
)

assert.deepEqual(
  paramsModule.formatRuntimeParamsForSubmit({
    TARGETS: ['api', 'worker'],
    BRANCH_NAME: 'main'
  }),
  {
    TARGETS: 'api,worker',
    BRANCH_NAME: 'main'
  },
  'extended choice array values should submit as comma-separated strings'
)

const checkboxRows = paramsModule.buildParamRowsFromConfig({
  OS_VERSIONS: {
    mode: 'hidden',
    default_value: 'CENTOS10_BUILD,CENTOS9_BUILD',
    type: 'custom',
    raw_type: 'PT_CHECKBOX',
    description: '请选择要构建的OS版本（可多选）'
  }
})

assert.deepEqual(
  checkboxRows.map(({ key, ...row }) => row),
  [
    {
      name: 'OS_VERSIONS',
      type: 'extendedChoice',
      raw_type: 'PT_CHECKBOX',
      mode: 'hidden',
      default_value: ['CENTOS10_BUILD', 'CENTOS9_BUILD'],
      description: '请选择要构建的OS版本（可多选）',
      choices: [],
      locked: false,
      value_source: ''
    }
  ],
  'PT_CHECKBOX configs should restore as extended choice rows even when saved type is custom'
)

assert.match(
  parameterUiSource,
  /v-model="draft"[\s\S]*?type="checkbox"[\s\S]*?:value="choice"/,
  'extended choice defaults should use visible checkbox options'
)
assert.match(
  parameterUiSource,
  /openMultiSelect\(row\)/,
  'extended choice defaults should support filtering a long option list'
)
assert.match(
  parameterUiSource,
  /JenkinsMultiSelectDialog/,
  'extended choice options should open in a focused selection dialog'
)
assert.doesNotMatch(
  parameterUiSource,
  /row\.choices\.join\(' \/ '\)/,
  'extended choice options should not be rendered as one long slash-separated paragraph'
)
assert.match(
  parameterUiSource,
  /adminPages\.jenkinsEntries\.basicInfoTitle/,
  'entry editor should group instance and job fields as basic information'
)
assert.match(
  parameterUiSource,
  /adminPages\.jenkinsEntries\.parameterPresetTitle/,
  'entry modal should present parameters as a dedicated preset section'
)
assert.match(
  entryEditorSource,
  /adminPages\.jenkinsEntries\.advancedOptions/,
  'entry modal should progressively disclose JSON and activation settings'
)
assert.doesNotMatch(
  entriesSource,
  /<BaseModal/,
  'the entry list should not contain the large configuration modal'
)
assert.doesNotMatch(
  entryEditorSource,
  /<BaseModal/,
  'the main entry configuration workflow should use a page, not a modal'
)
assert.doesNotMatch(
  entryEditorSource,
  /class="[^"]*sticky bottom-0[^"]*"/,
  'the entry editor footer should not cover parameter rows while scrolling'
)

assert.match(
  routesSource,
  /path:\s*'\/management\/jenkins\/entries\/new'/,
  'creating a Jenkins entry should use a dedicated route instead of a large modal'
)
assert.match(
  routesSource,
  /path:\s*'\/management\/jenkins\/entries\/:id\/edit'/,
  'editing a Jenkins entry should use a dedicated route'
)

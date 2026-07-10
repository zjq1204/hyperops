export const DEFAULT_JENKINS_PARAM_MODE = 'hidden'

const PARAM_TYPE_ALIASES = {
  stringparameterdefinition: 'string',
  string: 'string',
  textparameterdefinition: 'text',
  text: 'text',
  booleanparameterdefinition: 'boolean',
  boolean: 'boolean',
  choiceparameterdefinition: 'choice',
  choice: 'choice',
  extendedchoiceparameterdefinition: 'extendedChoice',
  extendedchoice: 'extendedChoice',
  ptcheckbox: 'extendedChoice',
  ptmultiselect: 'extendedChoice',
  passwordparameterdefinition: 'password',
  password: 'password',
  fileparameterdefinition: 'file',
  file: 'file',
  runparameterdefinition: 'run',
  run: 'run',
  listsubversiontagsparameterdefinition: 'listSubversionTags',
  listsubversiontags: 'listSubversionTags',
  gitparameterdefinition: 'git',
  git: 'git'
}

const PARAM_TYPE_LABEL_KEYS = {
  string: 'paramTypes.string',
  text: 'paramTypes.text',
  boolean: 'paramTypes.boolean',
  choice: 'paramTypes.choice',
  extendedChoice: 'paramTypes.extendedChoice',
  password: 'paramTypes.password',
  file: 'paramTypes.file',
  run: 'paramTypes.run',
  listSubversionTags: 'paramTypes.listSubversionTags',
  git: 'paramTypes.git',
  custom: 'paramTypes.custom'
}

export function normalizeJenkinsParamType(type = '', fallbackType = '') {
  const normalized = String(type || '')
    .split('.')
    .pop()
    .replace(/[_\s-]/g, '')
    .toLowerCase()
  const matchedType = PARAM_TYPE_ALIASES[normalized]
  if (matchedType) return matchedType
  return fallbackType && fallbackType !== type
    ? normalizeJenkinsParamType(fallbackType)
    : 'custom'
}

export function getParamTypeLabelKey(type = '') {
  return PARAM_TYPE_LABEL_KEYS[normalizeJenkinsParamType(type)]
}

export function getConfigByParamName(config = {}, name = '') {
  if (Object.prototype.hasOwnProperty.call(config, name)) {
    return config[name]
  }
  const normalizedName = String(name).toLowerCase()
  const matchedKey = Object.keys(config).find(
    (key) => String(key).toLowerCase() === normalizedName
  )
  return matchedKey ? config[matchedKey] : undefined
}

function normalizeMultiValue(value) {
  if (Array.isArray(value)) {
    return value.map((item) => String(item).trim()).filter(Boolean)
  }
  return String(value ?? '')
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean)
}

function normalizeDefaultValue(type, value) {
  return normalizeJenkinsParamType(type) === 'extendedChoice'
    ? normalizeMultiValue(value)
    : (value ?? '')
}

function formatDefaultValueForConfig(type, value) {
  return normalizeJenkinsParamType(type) === 'extendedChoice'
    ? normalizeMultiValue(value).join(',')
    : (value ?? '')
}

export function createParamRow(overrides = {}) {
  return {
    key: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    name: '',
    type: 'string',
    raw_type: 'StringParameterDefinition',
    mode: DEFAULT_JENKINS_PARAM_MODE,
    default_value: '',
    description: '',
    choices: [],
    locked: false,
    value_source: '',
    ...overrides
  }
}

export function buildParamRowsFromConfig(config = {}) {
  return Object.entries(config).map(([name, value]) => {
    const rawType =
      value?.raw_type || value?.type || 'StringParameterDefinition'
    const normalizedType = normalizeJenkinsParamType(value?.type, rawType)
    return createParamRow({
      name,
      type: normalizedType,
      raw_type: rawType,
      mode: value?.mode || DEFAULT_JENKINS_PARAM_MODE,
      default_value: normalizeDefaultValue(
        normalizedType,
        value?.default_value
      ),
      description: value?.description || '',
      choices: Array.isArray(value?.choices) ? value.choices : [],
      locked: false,
      value_source: ''
    })
  })
}

export function buildParamRowsFromDefinitions(
  params = [],
  existingConfig = {}
) {
  return params
    .filter((param) => param?.name)
    .map((param) => {
      const existingParamConfig =
        getConfigByParamName(existingConfig, param.name) || {}
      const rawType =
        param.raw_type ||
        existingParamConfig.raw_type ||
        param.type ||
        existingParamConfig.type ||
        'StringParameterDefinition'
      const normalizedType = normalizeJenkinsParamType(param.type, rawType)
      return createParamRow({
        name: param.name,
        type: normalizedType,
        raw_type: rawType,
        mode:
          existingParamConfig.mode || param.mode || DEFAULT_JENKINS_PARAM_MODE,
        default_value: normalizeDefaultValue(
          normalizedType,
          param.default_value
        ),
        description: param.description || existingParamConfig.description || '',
        choices: Array.isArray(param.choices)
          ? param.choices
          : Array.isArray(existingParamConfig.choices)
            ? existingParamConfig.choices
            : [],
        locked: true,
        value_source: param.value_source || ''
      })
    })
}

export function buildParamsConfigFromRows(rows = []) {
  const config = {}

  for (const row of rows) {
    const name = String(row.name || '').trim()
    if (!name) continue
    const rawType = row.raw_type || row.type || 'StringParameterDefinition'
    const normalizedType = normalizeJenkinsParamType(row.type, rawType)
    const paramConfig = {
      mode: row.mode || DEFAULT_JENKINS_PARAM_MODE,
      default_value: formatDefaultValueForConfig(
        normalizedType,
        row.default_value
      ),
      type: normalizedType,
      raw_type: rawType
    }
    if (Array.isArray(row.choices) && row.choices.length) {
      paramConfig.choices = row.choices
    }
    if (row.description) {
      paramConfig.description = row.description
    }
    config[name] = paramConfig
  }

  return config
}

export function normalizeRuntimeParam(param = {}) {
  const rawType = param.raw_type || param.type || 'StringParameterDefinition'
  const normalizedType = normalizeJenkinsParamType(param.type, rawType)
  return {
    name: param.name,
    type: normalizedType,
    raw_type: rawType,
    default_value: normalizeDefaultValue(normalizedType, param.default_value),
    choices: Array.isArray(param.choices) ? param.choices : [],
    description: param.description || '',
    mode: param.mode || 'editable'
  }
}

export function isBooleanParam(param = {}) {
  return normalizeJenkinsParamType(param.type, param.raw_type) === 'boolean'
}

export function isChoiceParam(param = {}) {
  return normalizeJenkinsParamType(param.type, param.raw_type) === 'choice'
}

export function isExtendedChoiceParam(param = {}) {
  return (
    normalizeJenkinsParamType(param.type, param.raw_type) === 'extendedChoice'
  )
}

export function isTextParam(param = {}) {
  return normalizeJenkinsParamType(param.type, param.raw_type) === 'text'
}

export function isPasswordParam(param = {}) {
  return (
    normalizeJenkinsParamType(param.type, param.raw_type) === 'password' ||
    String(param.name || '')
      .toLowerCase()
      .includes('password')
  )
}

export function formatRuntimeParamsForSubmit(params = {}) {
  return Object.fromEntries(
    Object.entries(params).map(([name, value]) => [
      name,
      Array.isArray(value) ? value.join(',') : value
    ])
  )
}

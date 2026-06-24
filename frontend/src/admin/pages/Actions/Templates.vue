<template>
  <AdminLayout>
    <PageFrame
      variant="soft"
      :eyebrow="t('adminPages.actionTemplates.eyebrow')"
      :title="t('adminPages.actionTemplates.title')"
      :subtitle="t('adminPages.actionTemplates.subtitle')"
    >
      <template #actions>
        <BaseButton @click="openCreateModal">{{
          t('adminPages.actionTemplates.actions.newTemplate')
        }}</BaseButton>
      </template>

      <AdminListSection>
        <template #filters>
          <div class="admin-filter-grid">
            <div class="admin-filter-field min-w-[18rem]">
              <label class="admin-filter-label">{{
                t('adminPages.actionTemplates.search.label')
              }}</label>
              <input
                v-model="searchQuery"
                class="admin-filter-control"
                :placeholder="
                  t('adminPages.actionTemplates.search.placeholder')
                "
              />
            </div>
          </div>
          <div class="admin-toolbar-end">
            <BaseButton variant="secondary" size="sm" @click="loadTemplates">
              {{ t('adminPages.actionTemplates.actions.refresh') }}
            </BaseButton>
          </div>
        </template>

        <AdminTable v-if="filteredTemplates.length">
          <thead>
            <tr>
              <th class="admin-table-head">
                {{ t('adminPages.actionTemplates.table.template') }}
              </th>
              <th class="admin-table-head">
                {{ t('adminPages.actionTemplates.table.authorization') }}
              </th>
              <th class="admin-table-head">
                {{ t('adminPages.actionTemplates.table.status') }}
              </th>
              <th class="admin-table-head text-right">
                {{ t('adminPages.actionTemplates.table.actions') }}
              </th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="template in filteredTemplates"
              :key="template.id"
              class="admin-table-row"
            >
              <td class="admin-table-cell">
                <div class="font-semibold text-slate-900">
                  {{ template.name }}
                </div>
                <div class="mt-1 max-w-xl truncate text-sm text-slate-500">
                  {{
                    template.description ||
                    t('adminPages.actionTemplates.table.noDescription')
                  }}
                </div>
              </td>
              <td class="admin-table-cell">
                <div class="text-sm text-slate-600">
                  {{
                    t('adminPages.actionTemplates.table.usersAndGroups', {
                      users: template.visible_users?.length || 0,
                      groups: template.visible_groups?.length || 0
                    })
                  }}
                </div>
              </td>
              <td class="admin-table-cell">
                <span
                  :class="
                    template.is_active
                      ? 'admin-status-badge admin-status-badge--success'
                      : 'admin-status-badge admin-status-badge--muted'
                  "
                >
                  {{
                    template.is_active
                      ? t('adminPages.actionTemplates.table.active')
                      : t('adminPages.actionTemplates.table.inactive')
                  }}
                </span>
              </td>
              <td class="admin-table-cell">
                <div class="admin-row-actions justify-end">
                  <BaseButton
                    variant="secondary"
                    size="sm"
                    @click="openPreviewModal(template)"
                  >
                    {{ t('adminPages.actionTemplates.actions.preview') }}
                  </BaseButton>
                  <BaseButton
                    variant="secondary"
                    size="sm"
                    @click="openEditModal(template)"
                  >
                    {{ t('adminPages.actionTemplates.actions.edit') }}
                  </BaseButton>
                  <BaseButton
                    variant="danger"
                    size="sm"
                    @click="deleteTemplate(template)"
                  >
                    {{ t('adminPages.actionTemplates.actions.delete') }}
                  </BaseButton>
                </div>
              </td>
            </tr>
          </tbody>
        </AdminTable>

        <EmptyState
          v-else
          variant="admin"
          :title="t('adminPages.actionTemplates.empty.title')"
          :description="t('adminPages.actionTemplates.empty.description')"
        />
      </AdminListSection>

      <BaseModal
        :show="showModal"
        size="wide"
        :title="
          editingTemplate
            ? t('adminPages.actionTemplates.modal.editTitle')
            : t('adminPages.actionTemplates.modal.newTitle')
        "
        @close="closeModal"
      >
        <div class="action-editor action-editor-redesigned action-editor--flat">
          <section class="action-editor-topbar">
            <div class="action-editor-topbar-main">
              <div class="action-editor-title-line">
                <strong>{{
                  form.name ||
                  t('adminPages.actionTemplates.modal.unnamedTemplate')
                }}</strong>
                <em>{{
                  form.scope === 'admin'
                    ? t('adminPages.actionTemplates.modal.adminTag')
                    : t('adminPages.actionTemplates.modal.personalTag')
                }}</em>
              </div>
              <small>{{
                form.description || t('adminPages.actionTemplates.basic.hint')
              }}</small>
            </div>

            <div class="action-editor-topbar-actions">
              <label class="action-switch action-switch-pill">
                <input v-model="form.is_active" type="checkbox" />
                <span>{{
                  form.is_active
                    ? t('adminPages.actionTemplates.modal.activeStatus')
                    : t('adminPages.actionTemplates.modal.inactiveStatus')
                }}</span>
              </label>
              <div class="action-scope-switch">
                <button
                  type="button"
                  :class="{ active: form.scope === 'admin' }"
                  @click="form.scope = 'admin'"
                >
                  {{ t('adminPages.actionTemplates.modal.adminTag') }}
                </button>
                <button
                  type="button"
                  :class="{ active: form.scope === 'personal' }"
                  @click="form.scope = 'personal'"
                >
                  {{ t('adminPages.actionTemplates.modal.personalTag') }}
                </button>
              </div>
            </div>
          </section>

          <section class="action-editor-body">
            <aside class="action-editor-nav">
              <button
                v-for="item in editorTabs"
                :key="item.key"
                type="button"
                class="action-editor-nav-item"
                :class="{ active: activeEditorTab === item.key }"
                @click="setEditorTab(item.key)"
              >
                <span class="action-editor-nav-index">{{ item.index }}</span>
                <span class="action-editor-nav-text">
                  <strong>{{ item.label }}</strong>
                </span>
              </button>
            </aside>

            <main class="action-editor-panel">
              <section v-if="activeEditorTab === 'basic'" class="action-pane">
                <div class="action-pane-heading">
                  <h3>
                    {{ t('adminPages.actionTemplates.tabs.basic.label') }}
                  </h3>
                  <p>{{ t('adminPages.actionTemplates.basic.hint') }}</p>
                </div>
                <div class="action-field-grid">
                  <label class="action-field">
                    <span>{{
                      t('adminPages.actionTemplates.basic.name')
                    }}</span>
                    <input
                      v-model="form.name"
                      :placeholder="
                        t('adminPages.actionTemplates.basic.namePlaceholder')
                      "
                    />
                  </label>
                  <label class="action-field">
                    <span>{{
                      t('adminPages.actionTemplates.basic.scope')
                    }}</span>
                    <select v-model="form.scope">
                      <option value="admin">
                        {{ t('adminPages.actionTemplates.modal.adminTag') }}
                      </option>
                      <option value="personal">
                        {{ t('adminPages.actionTemplates.modal.personalTag') }}
                      </option>
                    </select>
                  </label>
                  <label class="action-field action-field-wide">
                    <span>{{
                      t('adminPages.actionTemplates.basic.description')
                    }}</span>
                    <textarea
                      v-model="form.description"
                      rows="4"
                      :placeholder="
                        t(
                          'adminPages.actionTemplates.basic.descriptionPlaceholder'
                        )
                      "
                    ></textarea>
                  </label>
                </div>
              </section>

              <section
                v-else-if="activeEditorTab === 'params'"
                class="action-pane"
              >
                <div class="action-pane-heading action-pane-heading-row">
                  <div>
                    <h3>{{ t('adminPages.actionTemplates.params.title') }}</h3>
                    <p>{{ t('adminPages.actionTemplates.params.hint') }}</p>
                  </div>
                  <div class="flex gap-2">
                    <BaseButton
                      variant="secondary"
                      size="sm"
                      @click="addParamRow"
                    >
                      {{ t('adminPages.actionTemplates.params.add') }}
                    </BaseButton>
                    <BaseButton
                      variant="secondary"
                      size="sm"
                      @click="fillParamExample"
                    >
                      {{ t('adminPages.actionTemplates.params.fillExample') }}
                    </BaseButton>
                  </div>
                </div>

                <div
                  v-if="parameterRows.length"
                  class="action-global-param-list"
                >
                  <div class="action-global-param-head">
                    <span>{{
                      t('adminPages.actionTemplates.params.head.name')
                    }}</span>
                    <span>{{
                      t('adminPages.actionTemplates.params.head.label')
                    }}</span>
                    <span>{{
                      t('adminPages.actionTemplates.params.head.default')
                    }}</span>
                    <span>{{
                      t('adminPages.actionTemplates.params.head.required')
                    }}</span>
                    <span></span>
                  </div>
                  <div
                    v-for="(param, index) in parameterRows"
                    :key="param.client_id"
                    class="action-global-param-row"
                  >
                    <input
                      v-model="param.name"
                      :placeholder="
                        t('adminPages.actionTemplates.params.namePlaceholder')
                      "
                      @input="syncParameterSchemaText"
                    />
                    <input
                      v-model="param.label"
                      :placeholder="
                        t('adminPages.actionTemplates.params.head.label')
                      "
                      @input="syncParameterSchemaText"
                    />
                    <input
                      v-model="param.default"
                      :placeholder="
                        t(
                          'adminPages.actionTemplates.params.defaultPlaceholder'
                        )
                      "
                      @input="syncParameterSchemaText"
                    />
                    <label class="action-param-required">
                      <input
                        v-model="param.required"
                        type="checkbox"
                        @change="syncParameterSchemaText"
                      />
                      {{ t('adminPages.actionTemplates.params.head.required') }}
                    </label>
                    <button
                      type="button"
                      class="action-link-button"
                      @click="removeParamRow(index)"
                    >
                      {{ t('adminPages.actionTemplates.actions.delete') }}
                    </button>
                  </div>
                </div>

                <div v-else class="action-empty-box">
                  <strong>{{
                    t('adminPages.actionTemplates.params.empty.title')
                  }}</strong>
                  <p>
                    {{
                      t('adminPages.actionTemplates.params.empty.description')
                    }}
                  </p>
                  <BaseButton size="sm" @click="addParamRow">{{
                    t('adminPages.actionTemplates.params.empty.cta')
                  }}</BaseButton>
                </div>
              </section>

              <section
                v-else-if="activeEditorTab === 'steps'"
                class="action-pane"
              >
                <template v-if="!stepEditorOpen">
                  <div class="action-pane-heading action-pane-heading-row">
                    <div>
                      <h3>{{ t('adminPages.actionTemplates.steps.title') }}</h3>
                      <p>{{ t('adminPages.actionTemplates.steps.hint') }}</p>
                    </div>
                    <BaseButton
                      variant="secondary"
                      size="sm"
                      @click="addStepAndEdit"
                    >
                      {{ t('adminPages.actionTemplates.steps.add') }}
                    </BaseButton>
                  </div>

                  <div v-if="form.steps.length" class="action-step-overview">
                    <div class="action-flow-canvas action-flow-canvas--editor">
                      <article
                        v-for="(step, index) in form.steps"
                        :key="step.client_id"
                        class="action-flow-node action-flow-node--editable"
                        :class="[
                          `action-flow-node--${step.action_type}`,
                          { active: selectedStepIndex === index }
                        ]"
                      >
                        <div class="action-flow-node-body">
                          <div class="action-flow-node-head">
                            <div class="action-flow-node-type">
                              {{ actionTypeText(step.action_type) }}
                            </div>
                            <div class="action-flow-node-index">
                              {{ index + 1 }}
                            </div>
                          </div>
                          <h4>
                            {{
                              step.name ||
                              t('adminPages.actionTemplates.steps.step', {
                                count: index + 1
                              })
                            }}
                          </h4>
                          <dl class="action-flow-node-summary">
                            <div
                              v-for="item in stepSummaryItems(step)"
                              :key="item.label"
                            >
                              <dt>{{ item.label }}</dt>
                              <dd>{{ item.value }}</dd>
                            </div>
                          </dl>
                          <div class="action-flow-node-footer">
                            <span
                              :class="
                                step.failure_policy === 'continue'
                                  ? 'action-flow-policy action-flow-policy--continue'
                                  : 'action-flow-policy'
                              "
                            >
                              {{
                                step.failure_policy === 'continue'
                                  ? t(
                                      'adminPages.actionTemplates.steps.policyContinue'
                                    )
                                  : t(
                                      'adminPages.actionTemplates.steps.policyStop'
                                    )
                              }}
                            </span>
                            <div class="action-flow-node-actions">
                              <button
                                type="button"
                                class="action-flow-node-edit"
                                @click.stop="openStepEditor(index)"
                              >
                                {{
                                  t('adminPages.actionTemplates.actions.edit')
                                }}
                              </button>
                              <details
                                class="action-flow-node-more"
                                @click.stop
                              >
                                <summary>
                                  {{
                                    t('adminPages.actionTemplates.actions.more')
                                  }}
                                </summary>
                                <div class="action-flow-node-menu">
                                  <button
                                    type="button"
                                    :disabled="index === 0"
                                    @click="moveStep(index, -1)"
                                  >
                                    {{
                                      t(
                                        'adminPages.actionTemplates.actions.moveUp'
                                      )
                                    }}
                                  </button>
                                  <button
                                    type="button"
                                    :disabled="index === form.steps.length - 1"
                                    @click="moveStep(index, 1)"
                                  >
                                    {{
                                      t(
                                        'adminPages.actionTemplates.actions.moveDown'
                                      )
                                    }}
                                  </button>
                                  <button
                                    type="button"
                                    @click="removeStep(index)"
                                  >
                                    {{
                                      t(
                                        'adminPages.actionTemplates.actions.delete'
                                      )
                                    }}
                                  </button>
                                </div>
                              </details>
                            </div>
                          </div>
                        </div>
                        <div
                          v-if="index < form.steps.length - 1"
                          class="action-flow-connector"
                          aria-hidden="true"
                        ></div>
                      </article>
                    </div>
                  </div>

                  <div v-else class="action-empty-box">
                    <strong>{{
                      t('adminPages.actionTemplates.steps.empty.title')
                    }}</strong>
                    <p>
                      {{
                        t('adminPages.actionTemplates.steps.empty.description')
                      }}
                    </p>
                    <BaseButton size="sm" @click="addStepAndEdit">{{
                      t('adminPages.actionTemplates.steps.empty.cta')
                    }}</BaseButton>
                  </div>
                </template>

                <template v-else>
                  <div class="action-pane-heading action-pane-heading-row">
                    <div>
                      <h3>
                        {{ t('adminPages.actionTemplates.steps.editor.title') }}
                      </h3>
                    </div>
                    <BaseButton
                      variant="secondary"
                      size="sm"
                      @click="closeStepEditor"
                    >
                      {{ t('adminPages.actionTemplates.steps.editor.back') }}
                    </BaseButton>
                  </div>

                  <article
                    v-if="selectedStep"
                    class="action-step-detail action-step-detail--page"
                  >
                    <div class="action-step-detail-head">
                      <div>
                        <p>
                          {{
                            t(
                              'adminPages.actionTemplates.steps.editor.currentStep'
                            )
                          }}
                        </p>
                        <h4>
                          {{
                            selectedStep.name ||
                            t('adminPages.actionTemplates.steps.step', {
                              count: selectedStepIndex + 1
                            })
                          }}
                        </h4>
                      </div>
                      <div class="flex gap-2">
                        <BaseButton
                          variant="secondary"
                          size="sm"
                          :disabled="selectedStepIndex === 0"
                          @click="moveStep(selectedStepIndex, -1)"
                        >
                          {{ t('adminPages.actionTemplates.actions.moveUp') }}
                        </BaseButton>
                        <BaseButton
                          variant="secondary"
                          size="sm"
                          :disabled="
                            selectedStepIndex === form.steps.length - 1
                          "
                          @click="moveStep(selectedStepIndex, 1)"
                        >
                          {{ t('adminPages.actionTemplates.actions.moveDown') }}
                        </BaseButton>
                        <BaseButton
                          variant="ghost"
                          size="sm"
                          @click="removeStep(selectedStepIndex)"
                        >
                          {{ t('adminPages.actionTemplates.actions.remove') }}
                        </BaseButton>
                      </div>
                    </div>

                    <div class="action-field-grid action-step-grid">
                      <label class="action-field">
                        <span>{{
                          t('adminPages.actionTemplates.steps.editor.name')
                        }}</span>
                        <input
                          v-model="selectedStep.name"
                          :placeholder="
                            t(
                              'adminPages.actionTemplates.steps.editor.namePlaceholder'
                            )
                          "
                        />
                      </label>
                      <label class="action-field">
                        <span>{{
                          t('adminPages.actionTemplates.steps.editor.category')
                        }}</span>
                        <select
                          :value="actionCategory(selectedStep)"
                          @change="
                            setActionCategory(selectedStep, $event.target.value)
                          "
                        >
                          <option value="jenkins">
                            {{
                              t(
                                'adminPages.actionTemplates.steps.types.jenkins'
                              )
                            }}
                          </option>
                          <option value="gitlab">
                            {{
                              t('adminPages.actionTemplates.steps.types.gitlab')
                            }}
                          </option>
                          <option value="approval">
                            {{
                              t(
                                'adminPages.actionTemplates.steps.types.approval'
                              )
                            }}
                          </option>
                          <option value="conditional">
                            {{
                              t(
                                'adminPages.actionTemplates.steps.types.conditional'
                              )
                            }}
                          </option>
                        </select>
                      </label>
                      <label
                        v-if="isGitLabStep(selectedStep)"
                        class="action-field"
                      >
                        <span>{{
                          t(
                            'adminPages.actionTemplates.steps.editor.specificAction'
                          )
                        }}</span>
                        <select
                          :value="gitlabStepValue(selectedStep)"
                          @change="
                            setGitLabStepValue(
                              selectedStep,
                              $event.target.value
                            )
                          "
                        >
                          <option
                            v-for="operation in gitlabStepOptions"
                            :key="operation.value"
                            :value="operation.value"
                          >
                            {{ operation.label }}
                          </option>
                        </select>
                      </label>
                      <label class="action-field">
                        <span>{{
                          t('adminPages.actionTemplates.steps.policyName')
                        }}</span>
                        <select v-model="selectedStep.failure_policy">
                          <option value="stop">
                            {{
                              t('adminPages.actionTemplates.steps.policyStop')
                            }}
                          </option>
                          <option value="continue">
                            {{
                              t(
                                'adminPages.actionTemplates.steps.policyContinue'
                              )
                            }}
                          </option>
                        </select>
                      </label>
                    </div>

                    <div
                      v-if="selectedStep.action_type === 'jenkins_trigger'"
                      class="action-step-config"
                    >
                      <label class="action-field">
                        <span>{{
                          t('adminPages.actionTemplates.jenkins.entry')
                        }}</span>
                        <select
                          v-model.number="selectedStep.config.entry_id"
                          @change="loadJenkinsStepParams(selectedStep)"
                        >
                          <option value="">
                            {{
                              t(
                                'adminPages.actionTemplates.jenkins.selectEntry'
                              )
                            }}
                          </option>
                          <option
                            v-for="entry in jenkinsEntries"
                            :key="entry.id"
                            :value="entry.id"
                          >
                            {{ entry.name }}
                          </option>
                        </select>
                      </label>
                      <label class="action-checkbox-line">
                        <input
                          v-model="selectedStep.config.wait_for_completion"
                          type="checkbox"
                        />
                        {{
                          t(
                            'adminPages.actionTemplates.jenkins.waitForCompletion'
                          )
                        }}
                      </label>
                      <div class="action-field action-field-wide">
                        <div class="action-param-head">
                          <span>{{
                            t('adminPages.actionTemplates.jenkins.paramsTitle')
                          }}</span>
                          <div class="flex items-center gap-2">
                            <button
                              type="button"
                              class="action-link-button"
                              :disabled="!selectedStep.config.entry_id"
                              @click="loadJenkinsStepParams(selectedStep)"
                            >
                              {{
                                t('adminPages.actionTemplates.jenkins.refresh')
                              }}
                            </button>
                            <button
                              type="button"
                              class="action-link-button"
                              @click="toggleJenkinsAdvanced(selectedStep)"
                            >
                              {{
                                selectedStep.showAdvancedParams
                                  ? t(
                                      'adminPages.actionTemplates.jenkins.advancedHide'
                                    )
                                  : t(
                                      'adminPages.actionTemplates.jenkins.advancedShow'
                                    )
                              }}
                            </button>
                          </div>
                        </div>

                        <div
                          v-if="selectedStep.paramsLoading"
                          class="action-param-empty"
                        >
                          {{ t('adminPages.actionTemplates.jenkins.loading') }}
                        </div>
                        <div
                          v-else-if="selectedStep.paramRows?.length"
                          class="action-param-table"
                        >
                          <div class="action-param-table-head">
                            <span>{{
                              t(
                                'adminPages.actionTemplates.jenkins.tableHead.param'
                              )
                            }}</span>
                            <span>{{
                              t(
                                'adminPages.actionTemplates.jenkins.tableHead.source'
                              )
                            }}</span>
                            <span>{{
                              t(
                                'adminPages.actionTemplates.jenkins.tableHead.value'
                              )
                            }}</span>
                          </div>
                          <div
                            v-for="row in selectedStep.paramRows"
                            :key="row.name"
                            class="action-param-row"
                          >
                            <div class="action-param-name">
                              <strong>
                                {{ row.name }}
                                <em
                                  :class="
                                    row.mode === 'readonly'
                                      ? 'action-param-mode readonly'
                                      : 'action-param-mode editable'
                                  "
                                >
                                  {{
                                    row.mode === 'readonly'
                                      ? t(
                                          'adminPages.actionTemplates.jenkins.modeReadonly'
                                        )
                                      : t(
                                          'adminPages.actionTemplates.jenkins.modeEditable'
                                        )
                                  }}
                                </em>
                              </strong>
                              <small>{{
                                row.description || row.type || 'String'
                              }}</small>
                            </div>
                            <div
                              v-if="row.mode === 'readonly'"
                              class="action-param-readonly-mode"
                            >
                              {{
                                t('adminPages.actionTemplates.jenkins.entry')
                              }}
                            </div>
                            <select
                              v-else
                              v-model="row.source"
                              @change="syncJenkinsParamsFromRows(selectedStep)"
                            >
                              <option value="default">
                                {{
                                  t(
                                    'adminPages.actionTemplates.jenkins.source.default'
                                  )
                                }}
                              </option>
                              <option value="fixed">
                                {{
                                  t(
                                    'adminPages.actionTemplates.jenkins.source.fixed'
                                  )
                                }}
                              </option>
                              <option value="param">
                                {{
                                  t(
                                    'adminPages.actionTemplates.jenkins.source.param'
                                  )
                                }}
                              </option>
                            </select>
                            <select
                              v-if="row.source === 'param'"
                              v-model="row.value"
                              :disabled="row.mode === 'readonly'"
                              @change="syncJenkinsParamsFromRows(selectedStep)"
                            >
                              <option value="">
                                {{
                                  t(
                                    'adminPages.actionTemplates.jenkins.selectParam'
                                  )
                                }}
                              </option>
                              <option
                                v-for="param in globalParamNames"
                                :key="param"
                                :value="param"
                              >
                                {{ param }}
                              </option>
                            </select>
                            <select
                              v-else-if="row.choices?.length"
                              v-model="row.value"
                              :disabled="
                                row.source === 'default' ||
                                row.mode === 'readonly'
                              "
                              @change="syncJenkinsParamsFromRows(selectedStep)"
                            >
                              <option
                                v-for="choice in row.choices"
                                :key="choice"
                                :value="choice"
                              >
                                {{ choice }}
                              </option>
                            </select>
                            <input
                              v-else
                              v-model="row.value"
                              :disabled="
                                row.source === 'default' ||
                                row.mode === 'readonly'
                              "
                              :placeholder="
                                t(
                                  'adminPages.actionTemplates.jenkins.valuePlaceholder'
                                )
                              "
                              @input="syncJenkinsParamsFromRows(selectedStep)"
                            />
                          </div>
                        </div>
                        <div v-else class="action-param-empty">
                          {{ t('adminPages.actionTemplates.jenkins.empty') }}
                        </div>

                        <textarea
                          v-if="selectedStep.showAdvancedParams"
                          v-model="selectedStep.paramsText"
                          rows="5"
                          class="mt-3"
                          spellcheck="false"
                          :placeholder="
                            t('adminPages.actionTemplates.jenkins.placeholder')
                          "
                          @input="syncJenkinsRowsFromParamsText(selectedStep)"
                        ></textarea>
                      </div>
                    </div>

                    <div
                      v-else-if="isGitLabStep(selectedStep)"
                      class="action-step-config action-gitlab-config"
                    >
                      <section class="action-gitlab-section">
                        <div class="action-gitlab-section-head">
                          <div>
                            <strong>{{
                              t('adminPages.actionTemplates.gitlab.paramTitle')
                            }}</strong>
                            <small>{{
                              gitlabOperationText(selectedStep)
                            }}</small>
                          </div>
                          <label class="action-inline-switch">
                            <input
                              v-model="
                                selectedStep.config
                                  .allow_runtime_project_selection
                              "
                              type="checkbox"
                            />
                            <span>{{
                              t(
                                'adminPages.actionTemplates.gitlab.allowRuntime'
                              )
                            }}</span>
                          </label>
                        </div>

                        <div class="action-gitlab-form-grid">
                          <label class="action-field">
                            <span>{{
                              gitlabPrimaryFieldLabel(selectedStep)
                            }}</span>
                            <input
                              v-model="
                                selectedStep.config[
                                  gitlabPrimaryFieldKey(selectedStep)
                                ]
                              "
                              :placeholder="
                                gitlabPrimaryFieldPlaceholder(selectedStep)
                              "
                            />
                          </label>
                          <label
                            v-if="gitlabNeedsRef(selectedStep)"
                            class="action-field"
                          >
                            <span>{{
                              t('adminPages.actionTemplates.gitlab.ref')
                            }}</span>
                            <input
                              v-model="selectedStep.config.ref"
                              :placeholder="
                                t(
                                  'adminPages.actionTemplates.gitlab.refPlaceholder'
                                )
                              "
                            />
                          </label>
                          <template
                            v-if="
                              selectedStep.action_type ===
                              'gitlab_webhook_operation'
                            "
                          >
                            <label class="action-field">
                              <span>{{
                                t(
                                  'adminPages.actionTemplates.gitlab.branchFilter'
                                )
                              }}</span>
                              <input
                                v-model="
                                  selectedStep.config.push_events_branch_filter
                                "
                                :placeholder="
                                  t(
                                    'adminPages.actionTemplates.gitlab.branchFilterPlaceholder'
                                  )
                                "
                              />
                            </label>
                            <div class="action-field action-field-wide">
                              <span>{{
                                t(
                                  'adminPages.actionTemplates.gitlab.triggerEvents'
                                )
                              }}</span>
                              <div class="action-toggle-row">
                                <label class="action-checkbox-line">
                                  <input
                                    v-model="selectedStep.config.push_events"
                                    type="checkbox"
                                  />
                                  {{
                                    t('adminPages.actionTemplates.gitlab.push')
                                  }}
                                </label>
                                <label class="action-checkbox-line">
                                  <input
                                    v-model="
                                      selectedStep.config.tag_push_events
                                    "
                                    type="checkbox"
                                  />
                                  {{
                                    t(
                                      'adminPages.actionTemplates.gitlab.tagPush'
                                    )
                                  }}
                                </label>
                                <label class="action-checkbox-line">
                                  <input
                                    v-model="
                                      selectedStep.config.merge_requests_events
                                    "
                                    type="checkbox"
                                  />
                                  {{
                                    t(
                                      'adminPages.actionTemplates.gitlab.mergeRequest'
                                    )
                                  }}
                                </label>
                                <label class="action-checkbox-line">
                                  <input
                                    v-model="
                                      selectedStep.config
                                        .enable_ssl_verification
                                    "
                                    type="checkbox"
                                  />
                                  {{
                                    t(
                                      'adminPages.actionTemplates.gitlab.sslVerify'
                                    )
                                  }}
                                </label>
                              </div>
                            </div>
                          </template>
                        </div>
                      </section>

                      <section class="action-gitlab-section">
                        <div class="action-gitlab-section-head">
                          <div>
                            <strong>{{
                              t(
                                'adminPages.actionTemplates.gitlab.fixedProjects'
                              )
                            }}</strong>
                            <small>{{
                              t(
                                'adminPages.actionTemplates.gitlab.selectedCount',
                                {
                                  count:
                                    selectedStep.config.project_ids?.length || 0
                                }
                              )
                            }}</small>
                          </div>
                          <div class="action-project-picker-actions">
                            <button
                              type="button"
                              :disabled="!filteredActionProjects.length"
                              @click="selectAllActionProjects(selectedStep)"
                            >
                              {{
                                t('adminPages.actionTemplates.gitlab.selectAll')
                              }}
                            </button>
                            <span>|</span>
                            <button
                              type="button"
                              :disabled="
                                !selectedStep.config.project_ids?.length
                              "
                              @click="clearActionProjects(selectedStep)"
                            >
                              {{ t('adminPages.actionTemplates.gitlab.clear') }}
                            </button>
                          </div>
                        </div>
                        <div class="action-project-picker-toolbar">
                          <label class="action-field">
                            <span>{{
                              t('adminPages.actionTemplates.gitlab.group')
                            }}</span>
                            <select v-model="actionProjectGroupFilter">
                              <option value="">
                                {{
                                  t(
                                    'adminPages.actionTemplates.gitlab.allGroups'
                                  )
                                }}
                              </option>
                              <option
                                v-for="group in actionProjectGroupOptions"
                                :key="group.id"
                                :value="group.id"
                              >
                                {{ group.name }}
                              </option>
                            </select>
                          </label>
                          <label class="action-field">
                            <span>{{
                              t('adminPages.actionTemplates.gitlab.search')
                            }}</span>
                            <input
                              v-model="actionProjectSearch"
                              :placeholder="
                                t(
                                  'adminPages.actionTemplates.gitlab.searchPlaceholder'
                                )
                              "
                            />
                          </label>
                          <label class="action-project-selected-only">
                            <input
                              v-model="actionProjectSelectedOnly"
                              type="checkbox"
                            />
                            <span>{{
                              t(
                                'adminPages.actionTemplates.gitlab.selectedOnly'
                              )
                            }}</span>
                          </label>
                        </div>
                        <div
                          v-if="filteredActionProjects.length"
                          class="action-project-grid"
                        >
                          <label
                            v-for="project in filteredActionProjects"
                            :key="project.id"
                            class="action-project-card"
                            :class="{
                              selected: isSelected(
                                selectedStep.config.project_ids,
                                project.id
                              )
                            }"
                          >
                            <input
                              type="checkbox"
                              :checked="
                                isSelected(
                                  selectedStep.config.project_ids,
                                  project.id
                                )
                              "
                              @change="
                                toggleSelection(
                                  selectedStep.config.project_ids,
                                  project.id
                                )
                              "
                            />
                            <div class="action-project-card-copy">
                              <strong>{{ project.name }}</strong>
                              <span>{{ project.path || project.name }}</span>
                              <em v-if="project.group_name">{{
                                project.group_name
                              }}</em>
                            </div>
                          </label>
                        </div>
                        <div v-else class="action-project-empty">
                          {{
                            actionProjectSelectedOnly
                              ? t(
                                  'adminPages.actionTemplates.gitlab.emptyNoSelected'
                                )
                              : t(
                                  'adminPages.actionTemplates.gitlab.emptyNoMatch'
                                )
                          }}
                        </div>
                      </section>
                    </div>

                    <div
                      v-else-if="
                        selectedStep.action_type === 'conditional_branch'
                      "
                      class="action-step-config action-branch-config"
                    >
                      <section class="action-branch-section">
                        <div
                          class="action-gitlab-section-head action-branch-section-head"
                        >
                          <div>
                            <strong>{{
                              t('adminPages.actionTemplates.branch.title')
                            }}</strong>
                            <small>{{
                              t('adminPages.actionTemplates.branch.caseCount', {
                                count: selectedStep.config.branches?.length || 0
                              })
                            }}</small>
                          </div>
                          <BaseButton
                            variant="secondary"
                            size="sm"
                            @click="addBranchCase(selectedStep)"
                          >
                            {{ t('adminPages.actionTemplates.branch.addCase') }}
                          </BaseButton>
                        </div>

                        <div
                          v-for="(branch, branchIndex) in selectedStep.config
                            .branches"
                          :key="branch.client_id || branch.id"
                          class="action-branch-case"
                          :class="{
                            'action-branch-case--active':
                              isBranchCaseOpen(branch)
                          }"
                        >
                          <div class="action-branch-case-head">
                            <div class="action-branch-case-title">
                              <span class="action-branch-case-index">{{
                                branchIndex + 1
                              }}</span>
                              <div>
                                <strong>{{
                                  branch.label ||
                                  t(
                                    'adminPages.actionTemplates.branch.caseTitle',
                                    {
                                      count: branchIndex + 1
                                    }
                                  )
                                }}</strong>
                                <small class="action-branch-case-detail">{{
                                  branchConditionText(branch)
                                }}</small>
                              </div>
                            </div>
                            <div class="action-branch-case-actions">
                              <button
                                type="button"
                                class="action-link-button"
                                @click="toggleBranchCase(selectedStep, branch)"
                              >
                                {{
                                  isBranchCaseOpen(branch)
                                    ? t(
                                        'adminPages.actionTemplates.actions.close'
                                      )
                                    : t(
                                        'adminPages.actionTemplates.actions.edit'
                                      )
                                }}
                              </button>
                              <button
                                type="button"
                                class="action-link-button"
                                :disabled="
                                  selectedStep.config.branches.length <= 1
                                "
                                @click="
                                  removeBranchCase(selectedStep, branchIndex)
                                "
                              >
                                {{
                                  t('adminPages.actionTemplates.actions.remove')
                                }}
                              </button>
                            </div>
                          </div>

                          <div
                            v-if="isBranchCaseOpen(branch)"
                            class="action-branch-rule-card"
                          >
                            <div class="action-branch-rule-card-head">
                              <span>{{
                                t('adminPages.actionTemplates.branch.title')
                              }}</span>
                              <strong>{{ branchConditionText(branch) }}</strong>
                            </div>
                            <div class="action-branch-condition-grid">
                              <label class="action-field">
                                <span>{{
                                  t('adminPages.actionTemplates.branch.label')
                                }}</span>
                                <input
                                  v-model="branch.label"
                                  :placeholder="
                                    t(
                                      'adminPages.actionTemplates.branch.labelPlaceholder'
                                    )
                                  "
                                />
                              </label>
                              <label class="action-field">
                                <span>{{
                                  t('adminPages.actionTemplates.branch.param')
                                }}</span>
                                <select v-model="branch.condition.param">
                                  <option value="">
                                    {{
                                      t(
                                        'adminPages.actionTemplates.branch.selectParam'
                                      )
                                    }}
                                  </option>
                                  <option
                                    v-for="param in globalParamNames"
                                    :key="param"
                                    :value="param"
                                  >
                                    {{ param }}
                                  </option>
                                </select>
                              </label>
                              <label class="action-field">
                                <span>{{
                                  t(
                                    'adminPages.actionTemplates.branch.operator'
                                  )
                                }}</span>
                                <select v-model="branch.condition.operator">
                                  <option
                                    v-for="operator in branchOperatorOptions"
                                    :key="operator.value"
                                    :value="operator.value"
                                  >
                                    {{ operator.label }}
                                  </option>
                                </select>
                              </label>
                              <label
                                v-if="
                                  branchOperatorNeedsValue(
                                    branch.condition.operator
                                  )
                                "
                                class="action-field"
                              >
                                <span>{{
                                  t('adminPages.actionTemplates.branch.value')
                                }}</span>
                                <input
                                  v-model="branch.condition.value"
                                  :placeholder="
                                    t(
                                      'adminPages.actionTemplates.branch.valuePlaceholder'
                                    )
                                  "
                                />
                              </label>
                            </div>
                          </div>

                          <div
                            v-if="isBranchCaseOpen(branch)"
                            class="action-branch-nested-head"
                          >
                            <span>{{
                              t('adminPages.actionTemplates.branch.steps')
                            }}</span>
                            <button
                              type="button"
                              class="action-link-button"
                              @click="addBranchNestedStep(branch)"
                            >
                              {{
                                t(
                                  'adminPages.actionTemplates.branch.addNestedStep'
                                )
                              }}
                            </button>
                          </div>

                          <div
                            v-if="isBranchCaseOpen(branch)"
                            class="action-branch-nested-list"
                          >
                            <article
                              v-for="(nestedStep, nestedIndex) in branch.steps"
                              :key="nestedStep.client_id"
                              class="action-branch-nested-step"
                              :class="{
                                'action-branch-nested-step--active':
                                  isBranchNestedStepOpen(nestedStep)
                              }"
                            >
                              <div
                                class="action-branch-flow-rail"
                                aria-hidden="true"
                              >
                                <span>{{ nestedIndex + 1 }}</span>
                              </div>
                              <div class="action-branch-nested-body">
                                <div
                                  v-if="!isBranchNestedStepOpen(nestedStep)"
                                  class="action-branch-nested-summary"
                                >
                                  <div>
                                    <strong>{{
                                      nestedStep.name ||
                                      actionTypeText(nestedStep.action_type)
                                    }}</strong>
                                    <small>{{
                                      actionTypeText(nestedStep.action_type)
                                    }}</small>
                                  </div>
                                  <div class="action-branch-nested-actions">
                                    <button
                                      type="button"
                                      class="action-link-button"
                                      @click="
                                        toggleBranchNestedStep(
                                          branch,
                                          nestedStep
                                        )
                                      "
                                    >
                                      {{
                                        t(
                                          'adminPages.actionTemplates.actions.edit'
                                        )
                                      }}
                                    </button>
                                    <button
                                      type="button"
                                      class="action-link-button"
                                      :disabled="branch.steps.length <= 1"
                                      @click="
                                        removeBranchNestedStep(
                                          branch,
                                          nestedIndex
                                        )
                                      "
                                    >
                                      {{
                                        t(
                                          'adminPages.actionTemplates.actions.remove'
                                        )
                                      }}
                                    </button>
                                  </div>
                                </div>
                                <div
                                  v-if="isBranchNestedStepOpen(nestedStep)"
                                  class="action-branch-nested-top"
                                >
                                  <input
                                    v-model="nestedStep.name"
                                    :placeholder="
                                      t(
                                        'adminPages.actionTemplates.steps.editor.namePlaceholder'
                                      )
                                    "
                                  />
                                  <button
                                    type="button"
                                    class="action-link-button"
                                    @click="
                                      toggleBranchNestedStep(branch, nestedStep)
                                    "
                                  >
                                    {{
                                      t(
                                        'adminPages.actionTemplates.actions.close'
                                      )
                                    }}
                                  </button>
                                  <button
                                    type="button"
                                    class="action-link-button"
                                    :disabled="branch.steps.length <= 1"
                                    @click="
                                      removeBranchNestedStep(
                                        branch,
                                        nestedIndex
                                      )
                                    "
                                  >
                                    {{
                                      t(
                                        'adminPages.actionTemplates.actions.remove'
                                      )
                                    }}
                                  </button>
                                </div>
                                <div
                                  v-if="isBranchNestedStepOpen(nestedStep)"
                                  class="action-branch-nested-grid"
                                >
                                  <label class="action-field">
                                    <span>{{
                                      t(
                                        'adminPages.actionTemplates.steps.editor.specificAction'
                                      )
                                    }}</span>
                                    <select
                                      v-model="nestedStep.action_type"
                                      @change="
                                        resetNestedStepConfig(nestedStep)
                                      "
                                    >
                                      <option
                                        v-for="option in nestedActionTypeOptions"
                                        :key="option.value"
                                        :value="option.value"
                                      >
                                        {{ option.label }}
                                      </option>
                                    </select>
                                  </label>
                                  <label class="action-field">
                                    <span>{{
                                      t(
                                        'adminPages.actionTemplates.steps.policyName'
                                      )
                                    }}</span>
                                    <select v-model="nestedStep.failure_policy">
                                      <option value="stop">
                                        {{
                                          t(
                                            'adminPages.actionTemplates.steps.policyStop'
                                          )
                                        }}
                                      </option>
                                      <option value="continue">
                                        {{
                                          t(
                                            'adminPages.actionTemplates.steps.policyContinue'
                                          )
                                        }}
                                      </option>
                                    </select>
                                  </label>
                                </div>
                                <div
                                  v-if="
                                    isBranchNestedStepOpen(nestedStep) &&
                                    nestedStep.action_type === 'jenkins_trigger'
                                  "
                                  class="action-branch-nested-config"
                                >
                                  <label class="action-field">
                                    <span>{{
                                      t(
                                        'adminPages.actionTemplates.jenkins.entry'
                                      )
                                    }}</span>
                                    <select
                                      v-model.number="
                                        nestedStep.config.entry_id
                                      "
                                      @change="
                                        loadJenkinsStepParams(nestedStep)
                                      "
                                    >
                                      <option value="">
                                        {{
                                          t(
                                            'adminPages.actionTemplates.jenkins.selectEntry'
                                          )
                                        }}
                                      </option>
                                      <option
                                        v-for="entry in jenkinsEntries"
                                        :key="entry.id"
                                        :value="entry.id"
                                      >
                                        {{ entry.name }}
                                      </option>
                                    </select>
                                  </label>
                                  <label class="action-checkbox-line">
                                    <input
                                      v-model="
                                        nestedStep.config.wait_for_completion
                                      "
                                      type="checkbox"
                                    />
                                    {{
                                      t(
                                        'adminPages.actionTemplates.jenkins.waitForCompletion'
                                      )
                                    }}
                                  </label>
                                  <div class="action-field action-field-wide">
                                    <div class="action-param-head">
                                      <span>{{
                                        t(
                                          'adminPages.actionTemplates.jenkins.paramsTitle'
                                        )
                                      }}</span>
                                      <button
                                        type="button"
                                        class="action-link-button"
                                        :disabled="!nestedStep.config.entry_id"
                                        @click="
                                          loadJenkinsStepParams(nestedStep)
                                        "
                                      >
                                        {{
                                          t(
                                            'adminPages.actionTemplates.jenkins.refresh'
                                          )
                                        }}
                                      </button>
                                    </div>
                                    <div
                                      v-if="nestedStep.paramsLoading"
                                      class="action-param-empty"
                                    >
                                      {{
                                        t(
                                          'adminPages.actionTemplates.jenkins.loading'
                                        )
                                      }}
                                    </div>
                                    <div
                                      v-else-if="nestedStep.paramRows?.length"
                                      class="action-param-table"
                                    >
                                      <div class="action-param-table-head">
                                        <span>{{
                                          t(
                                            'adminPages.actionTemplates.jenkins.tableHead.param'
                                          )
                                        }}</span>
                                        <span>{{
                                          t(
                                            'adminPages.actionTemplates.jenkins.tableHead.source'
                                          )
                                        }}</span>
                                        <span>{{
                                          t(
                                            'adminPages.actionTemplates.jenkins.tableHead.value'
                                          )
                                        }}</span>
                                      </div>
                                      <div
                                        v-for="row in nestedStep.paramRows"
                                        :key="row.name"
                                        class="action-param-row"
                                      >
                                        <div class="action-param-name">
                                          <strong>{{ row.name }}</strong>
                                          <small>{{
                                            row.description ||
                                            row.type ||
                                            'String'
                                          }}</small>
                                        </div>
                                        <div
                                          v-if="row.mode === 'readonly'"
                                          class="action-param-readonly-mode"
                                        >
                                          {{
                                            t(
                                              'adminPages.actionTemplates.jenkins.entry'
                                            )
                                          }}
                                        </div>
                                        <select
                                          v-else
                                          v-model="row.source"
                                          @change="
                                            syncJenkinsParamsFromRows(
                                              nestedStep
                                            )
                                          "
                                        >
                                          <option value="default">
                                            {{
                                              t(
                                                'adminPages.actionTemplates.jenkins.source.default'
                                              )
                                            }}
                                          </option>
                                          <option value="fixed">
                                            {{
                                              t(
                                                'adminPages.actionTemplates.jenkins.source.fixed'
                                              )
                                            }}
                                          </option>
                                          <option value="param">
                                            {{
                                              t(
                                                'adminPages.actionTemplates.jenkins.source.param'
                                              )
                                            }}
                                          </option>
                                        </select>
                                        <select
                                          v-if="row.source === 'param'"
                                          v-model="row.value"
                                          :disabled="row.mode === 'readonly'"
                                          @change="
                                            syncJenkinsParamsFromRows(
                                              nestedStep
                                            )
                                          "
                                        >
                                          <option value="">
                                            {{
                                              t(
                                                'adminPages.actionTemplates.jenkins.selectParam'
                                              )
                                            }}
                                          </option>
                                          <option
                                            v-for="param in globalParamNames"
                                            :key="param"
                                            :value="param"
                                          >
                                            {{ param }}
                                          </option>
                                        </select>
                                        <select
                                          v-else-if="row.choices?.length"
                                          v-model="row.value"
                                          :disabled="
                                            row.source === 'default' ||
                                            row.mode === 'readonly'
                                          "
                                          @change="
                                            syncJenkinsParamsFromRows(
                                              nestedStep
                                            )
                                          "
                                        >
                                          <option
                                            v-for="choice in row.choices"
                                            :key="choice"
                                            :value="choice"
                                          >
                                            {{ choice }}
                                          </option>
                                        </select>
                                        <input
                                          v-else
                                          v-model="row.value"
                                          :disabled="
                                            row.source === 'default' ||
                                            row.mode === 'readonly'
                                          "
                                          :placeholder="
                                            t(
                                              'adminPages.actionTemplates.jenkins.valuePlaceholder'
                                            )
                                          "
                                          @input="
                                            syncJenkinsParamsFromRows(
                                              nestedStep
                                            )
                                          "
                                        />
                                      </div>
                                    </div>
                                    <div v-else class="action-param-empty">
                                      {{
                                        t(
                                          'adminPages.actionTemplates.jenkins.empty'
                                        )
                                      }}
                                    </div>
                                  </div>
                                </div>

                                <div
                                  v-else-if="
                                    isBranchNestedStepOpen(nestedStep) &&
                                    isGitLabStep(nestedStep)
                                  "
                                  class="action-branch-nested-config"
                                >
                                  <label class="action-field">
                                    <span>{{
                                      gitlabPrimaryFieldLabel(nestedStep)
                                    }}</span>
                                    <input
                                      v-model="
                                        nestedStep.config[
                                          gitlabPrimaryFieldKey(nestedStep)
                                        ]
                                      "
                                      :placeholder="
                                        gitlabPrimaryFieldPlaceholder(
                                          nestedStep
                                        )
                                      "
                                    />
                                  </label>
                                  <label
                                    v-if="gitlabNeedsRef(nestedStep)"
                                    class="action-field"
                                  >
                                    <span>{{
                                      t('adminPages.actionTemplates.gitlab.ref')
                                    }}</span>
                                    <input
                                      v-model="nestedStep.config.ref"
                                      :placeholder="
                                        t(
                                          'adminPages.actionTemplates.gitlab.refPlaceholder'
                                        )
                                      "
                                    />
                                  </label>
                                  <template
                                    v-if="
                                      nestedStep.action_type ===
                                      'gitlab_webhook_operation'
                                    "
                                  >
                                    <label class="action-field">
                                      <span>{{
                                        t(
                                          'adminPages.actionTemplates.gitlab.branchFilter'
                                        )
                                      }}</span>
                                      <input
                                        v-model="
                                          nestedStep.config
                                            .push_events_branch_filter
                                        "
                                        :placeholder="
                                          t(
                                            'adminPages.actionTemplates.gitlab.branchFilterPlaceholder'
                                          )
                                        "
                                      />
                                    </label>
                                    <div class="action-field action-field-wide">
                                      <span>{{
                                        t(
                                          'adminPages.actionTemplates.gitlab.triggerEvents'
                                        )
                                      }}</span>
                                      <div class="action-toggle-row">
                                        <label class="action-checkbox-line">
                                          <input
                                            v-model="
                                              nestedStep.config.push_events
                                            "
                                            type="checkbox"
                                          />
                                          {{
                                            t(
                                              'adminPages.actionTemplates.gitlab.push'
                                            )
                                          }}
                                        </label>
                                        <label class="action-checkbox-line">
                                          <input
                                            v-model="
                                              nestedStep.config.tag_push_events
                                            "
                                            type="checkbox"
                                          />
                                          {{
                                            t(
                                              'adminPages.actionTemplates.gitlab.tagPush'
                                            )
                                          }}
                                        </label>
                                        <label class="action-checkbox-line">
                                          <input
                                            v-model="
                                              nestedStep.config
                                                .merge_requests_events
                                            "
                                            type="checkbox"
                                          />
                                          {{
                                            t(
                                              'adminPages.actionTemplates.gitlab.mergeRequest'
                                            )
                                          }}
                                        </label>
                                        <label class="action-checkbox-line">
                                          <input
                                            v-model="
                                              nestedStep.config
                                                .enable_ssl_verification
                                            "
                                            type="checkbox"
                                          />
                                          {{
                                            t(
                                              'adminPages.actionTemplates.gitlab.sslVerify'
                                            )
                                          }}
                                        </label>
                                      </div>
                                    </div>
                                  </template>
                                  <div class="action-field action-field-wide">
                                    <span>{{
                                      t(
                                        'adminPages.actionTemplates.gitlab.fixedProjects'
                                      )
                                    }}</span>
                                    <div class="action-project-grid compact">
                                      <label
                                        v-for="project in gitlabProjects"
                                        :key="project.id"
                                        class="action-project-card"
                                        :class="{
                                          selected: isSelected(
                                            nestedStep.config.project_ids,
                                            project.id
                                          )
                                        }"
                                      >
                                        <input
                                          type="checkbox"
                                          :checked="
                                            isSelected(
                                              nestedStep.config.project_ids,
                                              project.id
                                            )
                                          "
                                          @change="
                                            toggleSelection(
                                              nestedStep.config.project_ids,
                                              project.id
                                            )
                                          "
                                        />
                                        <div class="action-project-card-copy">
                                          <strong>{{ project.name }}</strong>
                                          <span>{{
                                            project.path || project.name
                                          }}</span>
                                        </div>
                                      </label>
                                    </div>
                                  </div>
                                </div>

                                <div
                                  v-else-if="
                                    isBranchNestedStepOpen(nestedStep) &&
                                    nestedStep.action_type === 'manual_approval'
                                  "
                                  class="action-branch-nested-config"
                                >
                                  <label class="action-field action-field-wide">
                                    <span>{{
                                      t(
                                        'adminPages.actionTemplates.approval.message'
                                      )
                                    }}</span>
                                    <textarea
                                      v-model="nestedStep.config.message"
                                      rows="3"
                                      :placeholder="
                                        t(
                                          'adminPages.actionTemplates.approval.messagePlaceholder'
                                        )
                                      "
                                    ></textarea>
                                  </label>
                                  <div class="action-field">
                                    <span>{{
                                      t(
                                        'adminPages.actionTemplates.approval.users'
                                      )
                                    }}</span>
                                    <div class="action-option-grid compact">
                                      <label
                                        v-for="user in users"
                                        :key="user.id"
                                        class="action-option"
                                        :class="{
                                          selected: isSelected(
                                            nestedStep.config.approver_user_ids,
                                            user.id
                                          )
                                        }"
                                      >
                                        <input
                                          type="checkbox"
                                          :checked="
                                            isSelected(
                                              nestedStep.config
                                                .approver_user_ids,
                                              user.id
                                            )
                                          "
                                          @change="
                                            toggleSelection(
                                              nestedStep.config
                                                .approver_user_ids,
                                              user.id
                                            )
                                          "
                                        />
                                        <span>{{
                                          user.display_name || user.username
                                        }}</span>
                                      </label>
                                    </div>
                                  </div>
                                  <div class="action-field">
                                    <span>{{
                                      t(
                                        'adminPages.actionTemplates.approval.groups'
                                      )
                                    }}</span>
                                    <div class="action-option-grid compact">
                                      <label
                                        v-for="group in groups"
                                        :key="group.id"
                                        class="action-option"
                                        :class="{
                                          selected: isSelected(
                                            nestedStep.config
                                              .approver_group_ids,
                                            group.id
                                          )
                                        }"
                                      >
                                        <input
                                          type="checkbox"
                                          :checked="
                                            isSelected(
                                              nestedStep.config
                                                .approver_group_ids,
                                              group.id
                                            )
                                          "
                                          @change="
                                            toggleSelection(
                                              nestedStep.config
                                                .approver_group_ids,
                                              group.id
                                            )
                                          "
                                        />
                                        <span>{{ group.name }}</span>
                                      </label>
                                    </div>
                                  </div>
                                </div>
                              </div>
                            </article>
                          </div>
                        </div>
                      </section>
                    </div>

                    <div
                      v-else-if="selectedStep.action_type === 'manual_approval'"
                      class="action-step-config"
                    >
                      <label class="action-field action-field-wide">
                        <span>{{
                          t('adminPages.actionTemplates.approval.message')
                        }}</span>
                        <textarea
                          v-model="selectedStep.config.message"
                          rows="3"
                          :placeholder="
                            t(
                              'adminPages.actionTemplates.approval.messagePlaceholder'
                            )
                          "
                        ></textarea>
                      </label>
                      <div class="action-field">
                        <span>{{
                          t('adminPages.actionTemplates.approval.users')
                        }}</span>
                        <div class="action-option-grid compact">
                          <label
                            v-for="user in users"
                            :key="user.id"
                            class="action-option"
                            :class="{
                              selected: isSelected(
                                selectedStep.config.approver_user_ids,
                                user.id
                              )
                            }"
                          >
                            <input
                              type="checkbox"
                              :checked="
                                isSelected(
                                  selectedStep.config.approver_user_ids,
                                  user.id
                                )
                              "
                              @change="
                                toggleSelection(
                                  selectedStep.config.approver_user_ids,
                                  user.id
                                )
                              "
                            />
                            <span>{{
                              user.display_name || user.username
                            }}</span>
                          </label>
                        </div>
                      </div>
                      <div class="action-field">
                        <span>{{
                          t('adminPages.actionTemplates.approval.groups')
                        }}</span>
                        <div class="action-option-grid compact">
                          <label
                            v-for="group in groups"
                            :key="group.id"
                            class="action-option"
                            :class="{
                              selected: isSelected(
                                selectedStep.config.approver_group_ids,
                                group.id
                              )
                            }"
                          >
                            <input
                              type="checkbox"
                              :checked="
                                isSelected(
                                  selectedStep.config.approver_group_ids,
                                  group.id
                                )
                              "
                              @change="
                                toggleSelection(
                                  selectedStep.config.approver_group_ids,
                                  group.id
                                )
                              "
                            />
                            <span>{{ group.name }}</span>
                          </label>
                        </div>
                      </div>
                    </div>

                    <div v-else class="action-empty-box">
                      <strong>{{
                        t('adminPages.actionTemplates.summary.unknown')
                      }}</strong>
                    </div>
                  </article>

                  <div v-else class="action-empty-box">
                    <strong>{{
                      t('adminPages.actionTemplates.steps.noEditable.title')
                    }}</strong>
                    <p>
                      {{
                        t(
                          'adminPages.actionTemplates.steps.noEditable.description'
                        )
                      }}
                    </p>
                    <BaseButton size="sm" @click="addStepAndEdit">{{
                      t('adminPages.actionTemplates.steps.noEditable.cta')
                    }}</BaseButton>
                  </div>
                </template>
              </section>

              <section v-else class="action-pane">
                <div class="action-pane-heading">
                  <h3>{{ t('adminPages.actionTemplates.auth.title') }}</h3>
                  <p>{{ t('adminPages.actionTemplates.auth.hint') }}</p>
                </div>
                <div class="action-auth-grid">
                  <div class="action-field">
                    <span>{{
                      t('adminPages.actionTemplates.auth.users')
                    }}</span>
                    <div class="action-option-grid tall">
                      <label
                        v-for="user in users"
                        :key="user.id"
                        class="action-option"
                        :class="{
                          selected: isSelected(form.visible_user_ids, user.id)
                        }"
                      >
                        <input
                          type="checkbox"
                          :checked="isSelected(form.visible_user_ids, user.id)"
                          @change="
                            toggleSelection(form.visible_user_ids, user.id)
                          "
                        />
                        <span>{{ user.display_name || user.username }}</span>
                      </label>
                    </div>
                  </div>
                  <div class="action-field">
                    <span>{{
                      t('adminPages.actionTemplates.auth.groups')
                    }}</span>
                    <div class="action-option-grid tall">
                      <label
                        v-for="group in groups"
                        :key="group.id"
                        class="action-option"
                        :class="{
                          selected: isSelected(form.visible_group_ids, group.id)
                        }"
                      >
                        <input
                          type="checkbox"
                          :checked="
                            isSelected(form.visible_group_ids, group.id)
                          "
                          @change="
                            toggleSelection(form.visible_group_ids, group.id)
                          "
                        />
                        <span>{{ group.name }}</span>
                      </label>
                    </div>
                  </div>
                </div>
              </section>
            </main>
          </section>

          <div v-if="formError" class="action-editor-error">
            {{ formError }}
          </div>
        </div>

        <template #footer>
          <div class="action-editor-footer">
            <div class="action-editor-footer-actions">
              <BaseButton variant="secondary" @click="closeModal">{{
                t('adminPages.actionTemplates.actions.cancel')
              }}</BaseButton>
              <BaseButton
                v-if="!isFirstEditorTab"
                variant="secondary"
                @click="goPreviousEditorTab"
              >
                {{ t('adminPages.actionTemplates.actions.previous') }}
              </BaseButton>
              <BaseButton v-if="!isLastEditorTab" @click="goNextEditorTab">
                {{ t('adminPages.actionTemplates.actions.next') }}
              </BaseButton>
              <BaseButton v-else :loading="saving" @click="saveTemplate">
                {{ t('adminPages.actionTemplates.actions.save') }}
              </BaseButton>
            </div>
          </div>
        </template>
      </BaseModal>

      <BaseModal
        :show="showPreviewModal"
        size="wide"
        :title="
          previewTemplate
            ? t('adminPages.actionTemplates.preview.title')
            : t('adminPages.actionTemplates.preview.titleFallback')
        "
        @close="closePreviewModal"
      >
        <div v-if="previewTemplate" class="action-preview">
          <section class="action-preview-summary">
            <div>
              <p class="action-editor-eyebrow">
                {{ t('adminPages.actionTemplates.preview.kicker') }}
              </p>
              <h3>{{ previewTemplate.name }}</h3>
              <p>
                {{
                  previewTemplate.description ||
                  t('adminPages.actionTemplates.preview.noDescription')
                }}
              </p>
            </div>
            <div class="action-preview-stats">
              <span>{{
                t('adminPages.actionTemplates.preview.stepCount', {
                  count: previewTemplate.steps?.length || 0
                })
              }}</span>
              <span>
                {{
                  previewTemplate.scope === 'admin'
                    ? t('adminPages.actionTemplates.preview.scopeAdmin')
                    : t('adminPages.actionTemplates.preview.scopePersonal')
                }}
              </span>
              <span>{{
                previewTemplate.is_active
                  ? t('adminPages.actionTemplates.table.active')
                  : t('adminPages.actionTemplates.table.inactive')
              }}</span>
            </div>
          </section>

          <div v-if="previewSteps.length" class="action-flow-canvas">
            <article
              v-for="(step, index) in previewSteps"
              :key="step.id || `${step.order}-${index}`"
              class="action-flow-node"
              :class="`action-flow-node--${step.action_type}`"
            >
              <div class="action-flow-node-index">{{ index + 1 }}</div>
              <div class="action-flow-node-body">
                <div class="action-flow-node-type">
                  {{ actionTypeText(step.action_type) }}
                </div>
                <h4>
                  {{
                    step.name ||
                    t('adminPages.actionTemplates.steps.step', {
                      count: index + 1
                    })
                  }}
                </h4>
                <p>{{ previewStepSummary(step) }}</p>
                <span
                  :class="
                    step.failure_policy === 'continue'
                      ? 'action-flow-policy action-flow-policy--continue'
                      : 'action-flow-policy'
                  "
                >
                  {{
                    step.failure_policy === 'continue'
                      ? t('adminPages.actionTemplates.steps.policyContinue')
                      : t('adminPages.actionTemplates.steps.policyStop')
                  }}
                </span>
              </div>
              <div
                v-if="index < previewSteps.length - 1"
                class="action-flow-arrow"
              >
                →
              </div>
            </article>
          </div>

          <div v-else class="action-empty-box">
            <strong>{{
              t('adminPages.actionTemplates.preview.empty.title')
            }}</strong>
            <p>
              {{ t('adminPages.actionTemplates.preview.empty.description') }}
            </p>
          </div>
        </div>

        <template #footer>
          <div class="flex w-full justify-end">
            <BaseButton @click="closePreviewModal">{{
              t('adminPages.actionTemplates.actions.close')
            }}</BaseButton>
          </div>
        </template>
      </BaseModal>

      <div
        v-if="toast.show"
        :class="[
          'admin-toast',
          toast.type === 'success'
            ? 'admin-toast--success'
            : 'admin-toast--error'
        ]"
      >
        {{ toast.message }}
      </div>
    </PageFrame>
  </AdminLayout>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import AdminLayout from '@/admin/layout/AdminLayout.vue'
import AdminListSection from '@/admin/components/AdminListSection.vue'
import AdminTable from '@/admin/components/AdminTable.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseModal from '@/components/ui/BaseModal.vue'
import EmptyState from '@/components/ui/EmptyState.vue'
import PageFrame from '@/components/ui/PageFrame.vue'
import actionsApi from '@/api/actions'
import jenkinsApi from '@/api/jenkins'
import gitlabApi from '@/api/gitlab'
import { managementApi } from '@/admin/api/management'

const { t } = useI18n()

const templates = ref([])
const users = ref([])
const groups = ref([])
const jenkinsEntries = ref([])
const gitlabProjects = ref([])
const searchQuery = ref('')
const showModal = ref(false)
const showPreviewModal = ref(false)
const editingTemplate = ref(null)
const previewTemplate = ref(null)
const saving = ref(false)
const formError = ref('')
const parameterSchemaText = ref('[]')
const parameterRows = ref([])
const activeEditorTab = ref('basic')
const selectedStepIndex = ref(0)
const stepEditorOpen = ref(false)
const actionProjectSearch = ref('')
const actionProjectGroupFilter = ref('')
const actionProjectSelectedOnly = ref(false)
const toast = ref({ show: false, message: '', type: 'success' })

const form = ref(buildEmptyForm())

const filteredTemplates = computed(() => {
  const keyword = searchQuery.value.trim().toLowerCase()
  if (!keyword) return templates.value
  return templates.value.filter((item) =>
    `${item.name || ''} ${item.description || ''}`
      .toLowerCase()
      .includes(keyword)
  )
})

const previewSteps = computed(() => {
  return [...(previewTemplate.value?.steps || [])].sort((a, b) => {
    return (Number(a.order) || 0) - (Number(b.order) || 0)
  })
})

const editorTabs = computed(() => [
  {
    key: 'basic',
    index: '01',
    label: t('adminPages.actionTemplates.tabs.basic.label'),
    hint: t('adminPages.actionTemplates.tabs.basic.hint')
  },
  {
    key: 'params',
    index: '02',
    label: t('adminPages.actionTemplates.tabs.params.label'),
    hint: t('adminPages.actionTemplates.tabs.params.hint')
  },
  {
    key: 'steps',
    index: '03',
    label: t('adminPages.actionTemplates.tabs.steps.label'),
    hint: t('adminPages.actionTemplates.tabs.steps.hint')
  },
  {
    key: 'auth',
    index: '04',
    label: t('adminPages.actionTemplates.tabs.auth.label'),
    hint: t('adminPages.actionTemplates.tabs.auth.hint')
  }
])

const activeEditorTabIndex = computed(() => {
  return editorTabs.value.findIndex(
    (item) => item.key === activeEditorTab.value
  )
})

const isFirstEditorTab = computed(() => activeEditorTabIndex.value <= 0)

const isLastEditorTab = computed(() => {
  return activeEditorTabIndex.value === editorTabs.value.length - 1
})

const selectedStep = computed(() => {
  return form.value.steps[selectedStepIndex.value] || null
})

const actionProjectGroupOptions = computed(() => {
  const groupMap = new Map()
  gitlabProjects.value.forEach((project) => {
    const groupId = project.group
    if (groupId == null || groupId === '') return
    groupMap.set(Number(groupId), {
      id: Number(groupId),
      name: project.group_name || `Group #${groupId}`
    })
  })
  return [...groupMap.values()].sort((a, b) =>
    a.name.localeCompare(b.name, 'zh-Hans')
  )
})

const filteredActionProjects = computed(() => {
  const step = selectedStep.value
  if (!step || !isGitLabStep(step)) return []

  const selectedIds = new Set(
    (step.config.project_ids || []).map((projectId) => Number(projectId))
  )
  const keyword = actionProjectSearch.value.trim().toLowerCase()
  const groupId = actionProjectGroupFilter.value

  return gitlabProjects.value.filter((project) => {
    if (groupId && Number(project.group) !== Number(groupId)) return false
    if (
      actionProjectSelectedOnly.value &&
      !selectedIds.has(Number(project.id))
    ) {
      return false
    }
    if (!keyword) return true
    return `${project.name || ''} ${project.path || ''} ${project.group_name || ''}`
      .toLowerCase()
      .includes(keyword)
  })
})

const globalParamNames = computed(() => {
  return parameterRows.value.map((item) => item.name).filter(Boolean)
})

const gitlabStepOptions = [
  {
    value: 'gitlab_branch_operation:create',
    label: t('adminPages.actionTemplates.gitlab.operations.create')
  },
  {
    value: 'gitlab_branch_operation:protect',
    label: t('adminPages.actionTemplates.gitlab.operations.protect')
  },
  {
    value: 'gitlab_branch_operation:unprotect',
    label: t('adminPages.actionTemplates.gitlab.operations.unprotect')
  },
  {
    value: 'gitlab_tag_operation:create',
    label: t('adminPages.actionTemplates.gitlab.tagOperations.create')
  },
  {
    value: 'gitlab_webhook_operation:create',
    label: t('adminPages.actionTemplates.gitlab.webhookOperations.create')
  }
]

const branchOperatorOptions = computed(() => [
  {
    value: 'equals',
    label: t('adminPages.actionTemplates.branch.operators.equals')
  },
  {
    value: 'not_equals',
    label: t('adminPages.actionTemplates.branch.operators.notEquals')
  },
  {
    value: 'contains',
    label: t('adminPages.actionTemplates.branch.operators.contains')
  },
  {
    value: 'is_empty',
    label: t('adminPages.actionTemplates.branch.operators.isEmpty')
  },
  {
    value: 'is_not_empty',
    label: t('adminPages.actionTemplates.branch.operators.isNotEmpty')
  }
])

const nestedActionTypeOptions = computed(() => [
  {
    value: 'jenkins_trigger',
    label: t('adminPages.actionTemplates.steps.types.jenkinsTrigger')
  },
  {
    value: 'gitlab_branch_operation',
    label: t('adminPages.actionTemplates.steps.types.gitlabBranchOperation')
  },
  {
    value: 'gitlab_tag_operation',
    label: t('adminPages.actionTemplates.steps.types.gitlabTagOperation')
  },
  {
    value: 'gitlab_webhook_operation',
    label: t('adminPages.actionTemplates.steps.types.gitlabWebhookOperation')
  },
  {
    value: 'manual_approval',
    label: t('adminPages.actionTemplates.steps.types.manualApproval')
  }
])

function buildEmptyForm() {
  return {
    name: '',
    description: '',
    scope: 'admin',
    is_active: true,
    visible_user_ids: [],
    visible_group_ids: [],
    steps: []
  }
}

function showToast(message, type = 'success') {
  toast.value = { show: true, message, type }
  setTimeout(() => {
    toast.value.show = false
  }, 2600)
}

function normalizeList(payload) {
  if (Array.isArray(payload)) return payload
  if (payload?.results) return payload.results
  return []
}

async function loadTemplates() {
  try {
    templates.value = normalizeList(await actionsApi.listAdminTemplates())
  } catch (error) {
    showToast(
      t('adminPages.actionTemplates.toast.loadTemplatesFailed', {
        message: error.message || ''
      }),
      'error'
    )
  }
}

async function loadOptions() {
  const [usersPayload, groupsPayload, entriesPayload, projectsPayload] =
    await Promise.allSettled([
      managementApi.getUsers({ page_size: 10000 }),
      managementApi.getGroups({ page_size: 10000 }),
      jenkinsApi.listEntries(),
      gitlabApi.listProjects()
    ])

  users.value =
    usersPayload.status === 'fulfilled' ? normalizeList(usersPayload.value) : []
  groups.value =
    groupsPayload.status === 'fulfilled'
      ? normalizeList(groupsPayload.value)
      : []
  jenkinsEntries.value =
    entriesPayload.status === 'fulfilled'
      ? normalizeList(entriesPayload.value)
      : []
  gitlabProjects.value =
    projectsPayload.status === 'fulfilled'
      ? normalizeList(projectsPayload.value)
      : []
}

function openCreateModal() {
  editingTemplate.value = null
  form.value = buildEmptyForm()
  parameterSchemaText.value = '[]'
  parameterRows.value = []
  formError.value = ''
  activeEditorTab.value = 'basic'
  selectedStepIndex.value = 0
  stepEditorOpen.value = false
  showModal.value = true
}

function openEditModal(template) {
  editingTemplate.value = template
  form.value = {
    name: template.name || '',
    description: template.description || '',
    scope: template.scope || 'admin',
    is_active: Boolean(template.is_active),
    visible_user_ids: (template.visible_users || []).map((item) => item.id),
    visible_group_ids: (template.visible_groups || []).map((item) => item.id),
    steps: (template.steps || []).map((step) => normalizeStep(step))
  }
  parameterRows.value = buildParameterRows(template.parameter_schema || [])
  syncParameterSchemaText()
  formError.value = ''
  activeEditorTab.value = 'basic'
  selectedStepIndex.value = 0
  stepEditorOpen.value = false
  showModal.value = true
  hydrateJenkinsStepParams(form.value.steps)
}

function closeModal() {
  showModal.value = false
  stepEditorOpen.value = false
}

function setEditorTab(tabKey) {
  activeEditorTab.value = tabKey
  if (tabKey !== 'steps') {
    stepEditorOpen.value = false
  }
}

function goPreviousEditorTab() {
  const previousTab = editorTabs.value[activeEditorTabIndex.value - 1]
  if (!previousTab) return
  setEditorTab(previousTab.key)
}

function goNextEditorTab() {
  const nextTab = editorTabs.value[activeEditorTabIndex.value + 1]
  if (!nextTab) return
  setEditorTab(nextTab.key)
}

function openPreviewModal(template) {
  previewTemplate.value = template
  showPreviewModal.value = true
}

function closePreviewModal() {
  showPreviewModal.value = false
  previewTemplate.value = null
}

function fillParamExample() {
  parameterRows.value = buildParameterRows([
    {
      name: 'branch_name',
      label: t('adminPages.actionTemplates.params.head.name'),
      required: true,
      default: ''
    },
    {
      name: 'source_ref',
      label: t('adminPages.actionTemplates.gitlab.ref'),
      required: false,
      default: t('adminPages.actionTemplates.gitlab.refPlaceholder')
    }
  ])
  syncParameterSchemaText()
}

function buildParameterRows(schema = []) {
  return (Array.isArray(schema) ? schema : []).map((item) => ({
    client_id: `${Date.now()}-${Math.random()}`,
    name: item.name || '',
    label: item.label || '',
    default: item.default ?? '',
    required: Boolean(item.required)
  }))
}

function addParamRow() {
  parameterRows.value.push({
    client_id: `${Date.now()}-${Math.random()}`,
    name: '',
    label: '',
    default: '',
    required: false
  })
  syncParameterSchemaText()
}

function removeParamRow(index) {
  parameterRows.value.splice(index, 1)
  syncParameterSchemaText()
}

function buildParameterSchemaFromRows() {
  return parameterRows.value
    .filter((item) => item.name.trim())
    .map((item) => ({
      name: item.name.trim(),
      label: item.label.trim() || item.name.trim(),
      required: Boolean(item.required),
      default: item.default ?? ''
    }))
}

function syncParameterSchemaText() {
  parameterSchemaText.value = JSON.stringify(
    buildParameterSchemaFromRows(),
    null,
    2
  )
}

function defaultConfig(actionType) {
  if (actionType === 'jenkins_trigger') {
    return { entry_id: '', params: {}, wait_for_completion: false }
  }
  if (actionType === 'conditional_branch') {
    return {
      match_mode: 'first',
      default_behavior: 'skip',
      branches: [buildDefaultBranchCase(1)]
    }
  }
  if (
    actionType === 'gitlab_branch_create' ||
    actionType === 'gitlab_branch_operation'
  ) {
    return {
      operation: 'create',
      project_ids: [],
      branch_name: '${branch_name}',
      ref: '${source_ref}',
      allow_runtime_project_selection: false
    }
  }
  if (actionType === 'gitlab_tag_operation') {
    return {
      operation: 'create',
      project_ids: [],
      tag_name: 'v${version}',
      ref: '${source_ref}',
      allow_runtime_project_selection: false
    }
  }
  if (actionType === 'gitlab_webhook_operation') {
    return {
      operation: 'create',
      project_ids: [],
      url: '',
      push_events: true,
      tag_push_events: false,
      merge_requests_events: false,
      enable_ssl_verification: true,
      push_events_branch_filter: '',
      allow_runtime_project_selection: false
    }
  }
  return { message: '', approver_user_ids: [], approver_group_ids: [] }
}

function buildDefaultBranchCase(index = 1) {
  const branchId = `branch-${Date.now()}-${Math.random()
    .toString(36)
    .slice(2, 8)}`
  return {
    id: branchId,
    client_id: branchId,
    label: t('adminPages.actionTemplates.branch.caseTitle', {
      count: index
    }),
    condition: {
      param: globalParamNames.value[0] || '',
      operator: 'equals',
      value: ''
    },
    steps: [buildDefaultNestedStep(1)],
    uiOpen: false
  }
}

function buildDefaultNestedStep(index = 1) {
  const actionType = 'jenkins_trigger'
  const config = defaultConfig(actionType)
  return {
    client_id: `${Date.now()}-${Math.random()}`,
    name: t('adminPages.actionTemplates.branch.nestedStepTitle', {
      count: index
    }),
    action_type: actionType,
    failure_policy: 'stop',
    config,
    paramsText: JSON.stringify(config.params || {}, null, 2),
    paramRows: buildJenkinsParamRows([], config.params || {}),
    paramsLoading: false,
    showAdvancedParams: false,
    uiOpen: false
  }
}

function normalizeBranchCase(branch = {}, index = 1) {
  const fallback = buildDefaultBranchCase(index)
  return {
    ...fallback,
    ...branch,
    client_id: branch.id || branch.client_id || fallback.client_id,
    id: branch.id || fallback.id,
    label: branch.label || fallback.label,
    condition: {
      ...fallback.condition,
      ...(branch.condition || {})
    },
    steps: normalizeBranchNestedSteps(branch.steps || fallback.steps),
    uiOpen: branch.uiOpen ?? false
  }
}

function normalizeBranchNestedSteps(steps = []) {
  const source =
    Array.isArray(steps) && steps.length ? steps : [buildDefaultNestedStep(1)]
  return source.map((step, index) => normalizeBranchNestedStep(step, index + 1))
}

function normalizeBranchNestedStep(step = {}, index = 1) {
  const actionType = step.action_type || 'jenkins_trigger'
  const config = { ...defaultConfig(actionType), ...(step.config || {}) }
  const normalized = {
    client_id: step.client_id || `${Date.now()}-${Math.random()}`,
    name:
      step.name ||
      t('adminPages.actionTemplates.branch.nestedStepTitle', { count: index }),
    action_type: actionType,
    failure_policy: step.failure_policy || 'stop',
    config,
    paramsText: JSON.stringify(config.params || {}, null, 2),
    paramRows: [],
    paramsLoading: false,
    showAdvancedParams: false,
    uiOpen: step.uiOpen ?? false
  }
  normalized.paramRows = buildJenkinsParamRows([], config.params || {})
  return normalized
}

function normalizeStep(step = {}) {
  const actionType =
    step.action_type === 'gitlab_branch_create'
      ? 'gitlab_branch_operation'
      : step.action_type || 'jenkins_trigger'
  const config = { ...defaultConfig(actionType), ...(step.config || {}) }
  if (step.action_type === 'gitlab_branch_create') {
    config.operation = 'create'
  }
  if (actionType === 'conditional_branch') {
    config.branches = (config.branches || []).map((branch, index) =>
      normalizeBranchCase(branch, index + 1)
    )
    if (!config.branches.length) {
      config.branches = [buildDefaultBranchCase(1)]
    }
  }
  const normalized = {
    client_id: step.id || `${Date.now()}-${Math.random()}`,
    id: step.id,
    name: step.name || '',
    order: step.order || form.value.steps.length + 1,
    action_type: actionType,
    failure_policy: step.failure_policy || 'stop',
    config,
    paramsText: JSON.stringify(config.params || {}, null, 2),
    paramRows: [],
    paramsLoading: false,
    showAdvancedParams: false
  }
  normalized.paramRows = buildJenkinsParamRows([], config.params || {})
  return normalized
}

function addStep() {
  form.value.steps.push(
    normalizeStep({
      name: t('adminPages.actionTemplates.steps.step', {
        count: form.value.steps.length + 1
      }),
      order: form.value.steps.length + 1
    })
  )
  selectedStepIndex.value = form.value.steps.length - 1
}

function addStepAndEdit() {
  addStep()
  stepEditorOpen.value = true
}

function removeStep(index) {
  form.value.steps.splice(index, 1)
  syncStepOrders()
  if (!form.value.steps.length) {
    selectedStepIndex.value = 0
    stepEditorOpen.value = false
    return
  }
  selectedStepIndex.value = Math.min(index, form.value.steps.length - 1)
}

function syncStepOrders() {
  form.value.steps.forEach((step, idx) => {
    step.order = idx + 1
  })
}

function openStepEditor(index) {
  selectedStepIndex.value = index
  stepEditorOpen.value = true
}

function closeStepEditor() {
  stepEditorOpen.value = false
}

function moveStep(index, direction) {
  const targetIndex = index + direction
  if (targetIndex < 0 || targetIndex >= form.value.steps.length) return
  const [step] = form.value.steps.splice(index, 1)
  form.value.steps.splice(targetIndex, 0, step)
  syncStepOrders()
  selectedStepIndex.value = targetIndex
}

function resetStepConfig(step) {
  step.config = defaultConfig(step.action_type)
  step.paramsText = JSON.stringify(step.config.params || {}, null, 2)
  step.paramRows = buildJenkinsParamRows([], step.config.params || {})
  step.showAdvancedParams = false
}

function changeStepType(step, actionType) {
  step.action_type = actionType
  resetStepConfig(step)
}

function actionCategory(step) {
  if (step?.action_type === 'conditional_branch') return 'conditional'
  if (isGitLabStep(step)) return 'gitlab'
  if (step?.action_type === 'manual_approval') return 'approval'
  return 'jenkins'
}

function setActionCategory(step, category) {
  if (!step) return
  if (category === 'gitlab') {
    if (!isGitLabStep(step)) {
      changeStepType(step, 'gitlab_branch_operation')
    }
    return
  }
  if (category === 'approval') {
    changeStepType(step, 'manual_approval')
    return
  }
  if (category === 'conditional') {
    changeStepType(step, 'conditional_branch')
    return
  }
  changeStepType(step, 'jenkins_trigger')
}

function gitlabStepValue(step) {
  if (!isGitLabStep(step)) return gitlabStepOptions[0].value
  return `${step.action_type}:${step.config?.operation || 'create'}`
}

function setGitLabStepValue(step, value) {
  if (!step) return
  const [actionType, operation = 'create'] = String(value).split(':')
  const previousConfig = step.config || {}
  if (step.action_type !== actionType) {
    step.action_type = actionType
    step.config = {
      ...defaultConfig(actionType),
      allow_runtime_project_selection: Boolean(
        previousConfig.allow_runtime_project_selection
      ),
      project_ids: [...(previousConfig.project_ids || [])]
    }
    step.paramsText = JSON.stringify(step.config.params || {}, null, 2)
    step.paramRows = buildJenkinsParamRows([], step.config.params || {})
    step.showAdvancedParams = false
  }
  step.config.operation = operation
}

function isGitLabActionType(actionType) {
  return [
    'gitlab_branch_create',
    'gitlab_branch_operation',
    'gitlab_tag_operation',
    'gitlab_webhook_operation'
  ].includes(actionType)
}

function isGitLabStep(step) {
  return isGitLabActionType(step?.action_type)
}

function gitlabOperationOptions(actionType) {
  if (
    actionType === 'gitlab_branch_create' ||
    actionType === 'gitlab_branch_operation'
  ) {
    return [
      {
        value: 'create',
        label: t('adminPages.actionTemplates.gitlab.operations.create')
      },
      {
        value: 'protect',
        label: t('adminPages.actionTemplates.gitlab.operations.protect')
      },
      {
        value: 'unprotect',
        label: t('adminPages.actionTemplates.gitlab.operations.unprotect')
      }
    ]
  }
  if (actionType === 'gitlab_tag_operation') {
    return [
      {
        value: 'create',
        label: t('adminPages.actionTemplates.gitlab.tagOperations.create')
      }
    ]
  }
  if (actionType === 'gitlab_webhook_operation') {
    return [
      {
        value: 'create',
        label: t('adminPages.actionTemplates.gitlab.webhookOperations.create')
      }
    ]
  }
  return []
}

function gitlabPrimaryFieldKey(step) {
  if (step?.action_type === 'gitlab_tag_operation') return 'tag_name'
  if (step?.action_type === 'gitlab_webhook_operation') return 'url'
  return 'branch_name'
}

function gitlabPrimaryFieldLabel(step) {
  if (step?.action_type === 'gitlab_tag_operation')
    return t('adminPages.actionTemplates.gitlab.primaryFieldTag')
  if (step?.action_type === 'gitlab_webhook_operation')
    return t('adminPages.actionTemplates.gitlab.primaryFieldUrl')
  return t('adminPages.actionTemplates.gitlab.primaryFieldBranch')
}

function gitlabPrimaryFieldPlaceholder(step) {
  if (step?.action_type === 'gitlab_tag_operation')
    return t('adminPages.actionTemplates.gitlab.primaryPlaceholderTag')
  if (step?.action_type === 'gitlab_webhook_operation')
    return t('adminPages.actionTemplates.gitlab.primaryPlaceholderUrl')
  return t('adminPages.actionTemplates.gitlab.primaryPlaceholderBranch')
}

function gitlabNeedsRef(step) {
  if (step?.action_type === 'gitlab_tag_operation') return true
  if (
    step?.action_type !== 'gitlab_branch_create' &&
    step?.action_type !== 'gitlab_branch_operation'
  ) {
    return false
  }
  return (step.config?.operation || 'create') === 'create'
}

function buildJenkinsParamRows(definitions = [], savedParams = {}) {
  const seen = new Set()
  const normalizedSavedParams = new Map(
    Object.entries(savedParams || {}).map(([name, value]) => [
      String(name).toLowerCase(),
      value
    ])
  )
  const rows = (definitions || [])
    .filter((definition) => definition.mode !== 'hidden')
    .map((definition) => {
      const normalizedName = String(definition.name).toLowerCase()
      const value = normalizedSavedParams.get(normalizedName)
      seen.add(normalizedName)
      const mode = definition.mode || 'editable'
      return {
        name: definition.name,
        type: definition.type,
        mode,
        defaultValue: definition.default_value ?? '',
        choices: definition.choices || [],
        description: definition.description || '',
        source:
          mode === 'readonly'
            ? 'default'
            : resolveParamSource(value, definition.default_value),
        value:
          mode === 'readonly'
            ? (definition.default_value ?? '')
            : resolveParamValue(value, definition.default_value)
      }
    })

  Object.entries(savedParams || {}).forEach(([name, value]) => {
    if (seen.has(String(name).toLowerCase())) return
    rows.push({
      name,
      type: 'StringParameterDefinition',
      mode: 'editable',
      defaultValue: '',
      choices: [],
      description: '',
      source: resolveParamSource(value, ''),
      value: resolveParamValue(value, '')
    })
  })

  return rows
}

function resolveParamSource(value, defaultValue) {
  if (value === undefined || value === defaultValue) return 'default'
  if (
    typeof value === 'string' &&
    value.match(/^\$\{[A-Za-z_][A-Za-z0-9_]*\}$/)
  ) {
    return 'param'
  }
  return 'fixed'
}

function resolveParamValue(value, defaultValue) {
  if (value === undefined) return defaultValue ?? ''
  if (typeof value === 'string') {
    const matched = value.match(/^\$\{([A-Za-z_][A-Za-z0-9_]*)\}$/)
    if (matched) return matched[1]
  }
  return value ?? ''
}

async function loadJenkinsStepParams(step) {
  if (!step?.config?.entry_id) {
    step.paramRows = []
    step.config.params = {}
    step.paramsText = '{}'
    return
  }
  step.paramsLoading = true
  try {
    const data = await jenkinsApi.getEntryAdminParams(step.config.entry_id)
    const savedParams = parseJson(
      step.paramsText,
      {},
      t('adminPages.actionTemplates.error.jenkinsJsonInvalid')
    )
    step.paramRows = buildJenkinsParamRows(data.params || [], savedParams)
    syncJenkinsParamsFromRows(step)
  } catch (error) {
    showToast(
      t('adminPages.actionTemplates.toast.loadJenkinsParamsFailed', {
        message: error.message || ''
      }),
      'error'
    )
  } finally {
    step.paramsLoading = false
  }
}

function hydrateJenkinsStepParams(steps) {
  ;(steps || []).forEach((step) => {
    if (step.action_type === 'jenkins_trigger' && step.config?.entry_id) {
      loadJenkinsStepParams(step)
    }
    if (step.action_type === 'conditional_branch') {
      ;(step.config?.branches || []).forEach((branch) => {
        ;(branch.steps || []).forEach((nestedStep) => {
          if (
            nestedStep.action_type === 'jenkins_trigger' &&
            nestedStep.config?.entry_id
          ) {
            loadJenkinsStepParams(nestedStep)
          }
        })
      })
    }
  })
}

function syncJenkinsParamsFromRows(step) {
  const params = {}
  ;(step.paramRows || []).forEach((row) => {
    if (row.mode === 'hidden') return
    if (row.mode === 'readonly') {
      params[row.name] = row.defaultValue ?? ''
      return
    }
    if (row.source === 'default') {
      params[row.name] = row.defaultValue ?? ''
      return
    }
    if (row.source === 'param') {
      params[row.name] = row.value ? `\${${row.value}}` : ''
      return
    }
    params[row.name] = row.value ?? ''
  })
  step.config.params = params
  step.paramsText = JSON.stringify(params, null, 2)
}

function syncJenkinsRowsFromParamsText(step) {
  try {
    const params = JSON.parse(step.paramsText || '{}')
    step.config.params = params
    step.paramRows = buildJenkinsParamRows(step.paramRows || [], params)
  } catch {
    return
  }
}

function toggleJenkinsAdvanced(step) {
  step.showAdvancedParams = !step.showAdvancedParams
}

function branchOperatorNeedsValue(operator) {
  return !['is_empty', 'is_not_empty'].includes(operator)
}

function addBranchCase(step) {
  if (!step?.config?.branches) return
  step.config.branches.forEach((branch) => {
    branch.uiOpen = false
  })
  const branch = buildDefaultBranchCase(step.config.branches.length + 1)
  branch.uiOpen = true
  step.config.branches.push(branch)
}

function removeBranchCase(step, index) {
  if (!step?.config?.branches || step.config.branches.length <= 1) return
  step.config.branches.splice(index, 1)
}

function addBranchNestedStep(branch) {
  if (!branch?.steps) return
  branch.steps.forEach((nestedStep) => {
    nestedStep.uiOpen = false
  })
  const nestedStep = buildDefaultNestedStep(branch.steps.length + 1)
  nestedStep.uiOpen = true
  branch.steps.push(nestedStep)
}

function removeBranchNestedStep(branch, index) {
  if (!branch?.steps || branch.steps.length <= 1) return
  branch.steps.splice(index, 1)
}

function isBranchCaseOpen(branch) {
  return Boolean(branch?.uiOpen)
}

function openBranchCase(step, branch) {
  ;(step?.config?.branches || []).forEach((item) => {
    item.uiOpen = item === branch
  })
}

function toggleBranchCase(step, branch) {
  if (isBranchCaseOpen(branch)) {
    branch.uiOpen = false
    return
  }
  openBranchCase(step, branch)
}

function isBranchNestedStepOpen(nestedStep) {
  return Boolean(nestedStep?.uiOpen)
}

function toggleBranchNestedStep(branch, nestedStep) {
  if (isBranchNestedStepOpen(nestedStep)) {
    nestedStep.uiOpen = false
    return
  }
  ;(branch?.steps || []).forEach((item) => {
    item.uiOpen = item === nestedStep
  })
}

function resetNestedStepConfig(nestedStep) {
  const config = defaultConfig(nestedStep.action_type)
  nestedStep.config = config
  nestedStep.paramsText = JSON.stringify(config.params || {}, null, 2)
  nestedStep.paramRows = buildJenkinsParamRows([], config.params || {})
  nestedStep.paramsLoading = false
  nestedStep.showAdvancedParams = false
}

function branchConditionText(branch) {
  const condition = branch?.condition || {}
  const operator = branchOperatorOptions.value.find(
    (item) => item.value === condition.operator
  )
  if (!condition.param) {
    return t('adminPages.actionTemplates.branch.conditionMissing')
  }
  if (!branchOperatorNeedsValue(condition.operator)) {
    return `${condition.param} ${operator?.label || condition.operator}`
  }
  return `${condition.param} ${operator?.label || condition.operator} ${condition.value || ''}`
}

function branchNestedStepNames(branch) {
  const names = (branch?.steps || [])
    .map((step) => step.name || actionTypeText(step.action_type))
    .filter(Boolean)
  return names.length
    ? names.join(', ')
    : t('adminPages.actionTemplates.branch.noNestedSteps')
}

function cleanConditionalBranchConfig(config, stepIndex) {
  return {
    match_mode: 'first',
    default_behavior: 'skip',
    branches: (config.branches || []).map((branch, branchIndex) => ({
      id: branch.id || `branch-${branchIndex + 1}`,
      label:
        branch.label ||
        t('adminPages.actionTemplates.branch.caseTitle', {
          count: branchIndex + 1
        }),
      condition: {
        param: branch.condition?.param || '',
        operator: branch.condition?.operator || 'equals',
        value: branchOperatorNeedsValue(branch.condition?.operator)
          ? branch.condition?.value || ''
          : ''
      },
      steps: (branch.steps || []).map((nestedStep, nestedIndex) => ({
        name:
          nestedStep.name ||
          t('adminPages.actionTemplates.branch.nestedStepTitle', {
            count: nestedIndex + 1
          }),
        action_type: nestedStep.action_type || 'jenkins_trigger',
        failure_policy: nestedStep.failure_policy || 'stop',
        config: cleanNestedStepConfig(
          nestedStep,
          stepIndex,
          branchIndex + 1,
          nestedIndex + 1
        )
      }))
    }))
  }
}

function cleanNestedStepConfig(
  nestedStep,
  stepIndex,
  branchIndex,
  nestedIndex
) {
  const config = { ...(nestedStep.config || {}) }
  if (nestedStep.action_type === 'jenkins_trigger') {
    config.params = parseJson(
      nestedStep.paramsText,
      {},
      t('adminPages.actionTemplates.error.paramJsonInvalid', {
        index: `${stepIndex}.${branchIndex}.${nestedIndex}`
      })
    )
  }
  if (isGitLabActionType(nestedStep.action_type)) {
    config.operation = config.operation || 'create'
    config.project_ids = (config.project_ids || []).map((item) => Number(item))
  }
  return config
}

function isSelected(list, id) {
  return (list || []).map((item) => Number(item)).includes(Number(id))
}

function toggleSelection(list, id) {
  const value = Number(id)
  const index = list.findIndex((item) => Number(item) === value)
  if (index >= 0) {
    list.splice(index, 1)
  } else {
    list.push(value)
  }
}

function selectAllActionProjects(step) {
  if (!step?.config?.project_ids) return
  const selected = new Set(step.config.project_ids.map((id) => Number(id)))
  filteredActionProjects.value.forEach((project) => {
    selected.add(Number(project.id))
  })
  step.config.project_ids = [...selected]
}

function clearActionProjects(step) {
  if (!step?.config) return
  step.config.project_ids = []
}

function parseJson(text, fallback, label) {
  try {
    return JSON.parse(text || JSON.stringify(fallback))
  } catch {
    throw new Error(label)
  }
}

function buildPayload() {
  const parameterSchema = buildParameterSchemaFromRows()
  const paramNames = parameterSchema.map((item) => item.name)
  if (new Set(paramNames).size !== paramNames.length) {
    throw new Error(t('adminPages.actionTemplates.error.paramDuplicate'))
  }
  if (!form.value.name.trim()) {
    throw new Error(t('adminPages.actionTemplates.error.nameRequired'))
  }
  const steps = form.value.steps
    .map((step, index) => {
      const config = { ...(step.config || {}) }
      if (step.action_type === 'jenkins_trigger') {
        config.params = parseJson(
          step.paramsText,
          {},
          t('adminPages.actionTemplates.error.paramJsonInvalid', {
            index: index + 1
          })
        )
      }
      if (isGitLabActionType(step.action_type)) {
        config.operation = config.operation || 'create'
        config.project_ids = (config.project_ids || []).map((item) =>
          Number(item)
        )
      }
      if (step.action_type === 'conditional_branch') {
        Object.assign(config, cleanConditionalBranchConfig(config, index + 1))
      }
      return {
        name:
          step.name ||
          t('adminPages.actionTemplates.steps.step', { count: index + 1 }),
        order: Number(step.order) || index + 1,
        action_type: step.action_type,
        failure_policy: step.failure_policy || 'stop',
        config
      }
    })
    .sort((a, b) => a.order - b.order)

  return {
    name: form.value.name.trim(),
    description: form.value.description || '',
    scope: form.value.scope,
    is_active: form.value.is_active,
    parameter_schema: parameterSchema,
    visible_user_ids: form.value.visible_user_ids,
    visible_group_ids: form.value.visible_group_ids,
    steps
  }
}

async function saveTemplate() {
  saving.value = true
  formError.value = ''
  try {
    const payload = buildPayload()
    if (editingTemplate.value) {
      await actionsApi.updateTemplate(editingTemplate.value.id, payload)
    } else {
      await actionsApi.createTemplate(payload)
    }
    closeModal()
    await loadTemplates()
    showToast(t('adminPages.actionTemplates.toast.templateSaved'))
  } catch (error) {
    formError.value =
      error.message ||
      t('adminPages.actionTemplates.toast.saveFailed', { message: '' })
  } finally {
    saving.value = false
  }
}

async function deleteTemplate(template) {
  if (
    !window.confirm(
      t('adminPages.actionTemplates.toast.deleteConfirm', {
        name: template.name
      })
    )
  )
    return
  try {
    await actionsApi.deleteTemplate(template.id)
    await loadTemplates()
    showToast(t('adminPages.actionTemplates.toast.templateDeleted'))
  } catch (error) {
    showToast(
      t('adminPages.actionTemplates.toast.deleteFailed', {
        message: error.message || ''
      }),
      'error'
    )
  }
}

function actionTypeText(type) {
  const map = {
    jenkins_trigger: t('adminPages.actionTemplates.steps.types.jenkinsTrigger'),
    gitlab_branch_create: t(
      'adminPages.actionTemplates.steps.types.gitlabBranchCreate'
    ),
    gitlab_branch_operation: t(
      'adminPages.actionTemplates.steps.types.gitlabBranchOperation'
    ),
    gitlab_tag_operation: t(
      'adminPages.actionTemplates.steps.types.gitlabTagOperation'
    ),
    gitlab_webhook_operation: t(
      'adminPages.actionTemplates.steps.types.gitlabWebhookOperation'
    ),
    manual_approval: t('adminPages.actionTemplates.steps.types.manualApproval'),
    conditional_branch: t(
      'adminPages.actionTemplates.steps.types.conditionalBranch'
    )
  }
  return map[type] || t('adminPages.actionTemplates.steps.types.unknown')
}

function gitlabOperationText(step) {
  const operation = step.config?.operation || 'create'
  const matched = gitlabOperationOptions(step.action_type).find(
    (item) => item.value === operation
  )
  return matched?.label || operation
}

function stepSummaryItems(step) {
  const config = step.config || {}
  if (step.action_type === 'conditional_branch') {
    return [
      {
        label: t('adminPages.actionTemplates.summary.branches'),
        value: t('adminPages.actionTemplates.branch.caseCount', {
          count: (config.branches || []).length
        })
      },
      {
        label: t('adminPages.actionTemplates.summary.default'),
        value: t('adminPages.actionTemplates.branch.defaultSkip')
      }
    ]
  }
  if (step.action_type === 'jenkins_trigger') {
    const entry = jenkinsEntries.value.find(
      (item) => Number(item.id) === Number(config.entry_id)
    )
    return [
      {
        label: t('adminPages.actionTemplates.summary.entry'),
        value:
          entry?.name ||
          (config.entry_id
            ? t('adminPages.actionTemplates.summary.entryLabel', {
                id: config.entry_id
              })
            : t('adminPages.actionTemplates.summary.entryNotSelected'))
      },
      {
        label: t('adminPages.actionTemplates.summary.wait'),
        value: config.wait_for_completion
          ? t('adminPages.actionTemplates.summary.waitComplete')
          : t('adminPages.actionTemplates.summary.triggerContinue')
      }
    ]
  }
  if (step.action_type === 'gitlab_branch_create') {
    return [
      {
        label: t('adminPages.actionTemplates.summary.branch'),
        value:
          config.branch_name ||
          t('adminPages.actionTemplates.summary.urlNotSet')
      },
      {
        label: t('adminPages.actionTemplates.summary.base'),
        value:
          config.ref || t('adminPages.actionTemplates.gitlab.refPlaceholder')
      },
      {
        label: t('adminPages.actionTemplates.summary.projectsLabel'),
        value: t('adminPages.actionTemplates.summary.projects', {
          count: (config.project_ids || []).length
        })
      }
    ]
  }
  if (step.action_type === 'gitlab_branch_operation') {
    return [
      {
        label: t('adminPages.actionTemplates.summary.operation'),
        value: gitlabOperationText(step)
      },
      {
        label: t('adminPages.actionTemplates.summary.branch'),
        value:
          config.branch_name ||
          t('adminPages.actionTemplates.summary.urlNotSet')
      },
      {
        label: t('adminPages.actionTemplates.summary.projectsLabel'),
        value: t('adminPages.actionTemplates.summary.projects', {
          count: (config.project_ids || []).length
        })
      }
    ]
  }
  if (step.action_type === 'gitlab_tag_operation') {
    return [
      {
        label: t('adminPages.actionTemplates.summary.tag'),
        value:
          config.tag_name || t('adminPages.actionTemplates.summary.urlNotSet')
      },
      {
        label: t('adminPages.actionTemplates.summary.base'),
        value:
          config.ref || t('adminPages.actionTemplates.gitlab.refPlaceholder')
      },
      {
        label: t('adminPages.actionTemplates.summary.projectsLabel'),
        value: t('adminPages.actionTemplates.summary.projects', {
          count: (config.project_ids || []).length
        })
      }
    ]
  }
  if (step.action_type === 'gitlab_webhook_operation') {
    return [
      {
        label: t('adminPages.actionTemplates.summary.url'),
        value: config.url || t('adminPages.actionTemplates.summary.urlNotSet')
      },
      {
        label: t('adminPages.actionTemplates.summary.projectsLabel'),
        value: t('adminPages.actionTemplates.summary.projects', {
          count: (config.project_ids || []).length
        })
      }
    ]
  }
  if (step.action_type === 'manual_approval') {
    return [
      {
        label: t('adminPages.actionTemplates.summary.approverUserLabel'),
        value: t('adminPages.actionTemplates.summary.approverCount', {
          count: (config.approver_user_ids || []).length
        })
      },
      {
        label: t('adminPages.actionTemplates.summary.approverGroupLabel'),
        value: t('adminPages.actionTemplates.summary.approverCount', {
          count: (config.approver_group_ids || []).length
        })
      }
    ]
  }
  return [
    {
      label: t('adminPages.actionTemplates.summary.type'),
      value: t('adminPages.actionTemplates.summary.unknown')
    }
  ]
}

function previewStepSummary(step) {
  const config = step.config || {}
  if (step.action_type === 'conditional_branch') {
    const cases = (config.branches || [])
      .map((branch) =>
        t('adminPages.actionTemplates.preview.branchCaseSummary', {
          condition: branchConditionText(branch),
          steps: branchNestedStepNames(branch)
        })
      )
      .join(' / ')
    return cases || t('adminPages.actionTemplates.branch.defaultSkip')
  }
  if (step.action_type === 'jenkins_trigger') {
    const entry = jenkinsEntries.value.find(
      (item) => Number(item.id) === Number(config.entry_id)
    )
    return entry
      ? `${entry.name}${config.wait_for_completion ? t('adminPages.actionTemplates.summary.waitComplete') : t('adminPages.actionTemplates.summary.triggerContinue')}`
      : config.entry_id
        ? t('adminPages.actionTemplates.summary.entryLabel', {
            id: config.entry_id
          })
        : t('adminPages.actionTemplates.summary.entryNotSelected')
  }
  if (step.action_type === 'gitlab_branch_create') {
    const count = (config.project_ids || []).length
    const branch =
      config.branch_name ||
      t('adminPages.actionTemplates.summary.branchNameMissing')
    const ref = config.ref || 'main'
    return t('adminPages.actionTemplates.preview.branchCreateSummary', {
      branch,
      ref,
      count
    })
  }
  if (step.action_type === 'gitlab_branch_operation') {
    const count = (config.project_ids || []).length
    const branch =
      config.branch_name ||
      t('adminPages.actionTemplates.summary.branchNameMissing')
    const ref =
      config.operation === 'create'
        ? t('adminPages.actionTemplates.preview.basedOn', {
            ref:
              config.ref ||
              t('adminPages.actionTemplates.gitlab.refPlaceholder')
          })
        : ''
    return t('adminPages.actionTemplates.preview.branchOperationSummary', {
      operation: gitlabOperationText(step),
      branch,
      ref,
      count
    })
  }
  if (step.action_type === 'gitlab_tag_operation') {
    const count = (config.project_ids || []).length
    const tag =
      config.tag_name || t('adminPages.actionTemplates.summary.tagNameMissing')
    return t('adminPages.actionTemplates.preview.tagCreateSummary', {
      tag,
      ref: config.ref || t('adminPages.actionTemplates.gitlab.refPlaceholder'),
      count
    })
  }
  if (step.action_type === 'gitlab_webhook_operation') {
    const count = (config.project_ids || []).length
    return t('adminPages.actionTemplates.preview.webhookCreateSummary', {
      url: config.url || t('adminPages.actionTemplates.summary.urlNotSet'),
      count
    })
  }
  if (step.action_type === 'manual_approval') {
    const userCount = (config.approver_user_ids || []).length
    const groupCount = (config.approver_group_ids || []).length
    return t('adminPages.actionTemplates.preview.approvalSummary', {
      users: userCount,
      groups: groupCount
    })
  }
  return t('adminPages.actionTemplates.preview.unknown')
}

onMounted(() => {
  loadTemplates()
  loadOptions()
})
</script>

<style scoped>
.action-template-chip {
  border: 1px solid #dbe3ef;
  border-radius: 999px;
  background: #f8fafc;
  color: #475569;
  font-size: 12px;
  font-weight: 600;
  line-height: 1;
  padding: 7px 10px;
}

.action-preview {
  display: grid;
  gap: 18px;
}

.action-preview-summary {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 20px;
  border: 1px solid #e2e8f0;
  border-radius: 26px;
  background: linear-gradient(180deg, #f8fafc 0%, #ffffff 100%);
  padding: 20px;
}

.action-preview-summary h3 {
  margin: 0;
  color: #0f172a;
  font-size: 24px;
  font-weight: 800;
  letter-spacing: -0.03em;
}

.action-preview-summary p {
  margin: 8px 0 0;
  color: #64748b;
  font-size: 14px;
}

.action-preview-stats {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 8px;
}

.action-preview-stats span {
  border: 1px solid #dbe3ef;
  border-radius: 999px;
  background: #ffffff;
  color: #334155;
  font-size: 12px;
  font-weight: 800;
  padding: 8px 11px;
}

.action-flow-canvas {
  display: flex;
  gap: 18px;
  overflow-x: auto;
  border: 1px solid #e2e8f0;
  border-radius: 28px;
  background:
    linear-gradient(#f8fafc 1px, transparent 1px),
    linear-gradient(90deg, #f8fafc 1px, transparent 1px), #ffffff;
  background-size: 24px 24px;
  padding: 24px;
}

.action-flow-node {
  position: relative;
  display: flex;
  min-width: 260px;
  gap: 14px;
  align-items: flex-start;
}

.action-flow-node-index {
  display: inline-flex;
  width: 42px;
  height: 42px;
  flex: 0 0 42px;
  align-items: center;
  justify-content: center;
  border-radius: 16px;
  background: #1f2d3f;
  color: #ffffff;
  font-weight: 900;
}

.action-flow-node-body {
  min-height: 168px;
  flex: 1;
  border: 1px solid #dbe3ef;
  border-radius: 22px;
  background: rgba(255, 255, 255, 0.94);
  box-shadow: 0 18px 36px rgba(15, 23, 42, 0.08);
  padding: 16px;
}

.action-flow-node-type {
  color: #64748b;
  font-size: 12px;
  font-weight: 900;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.action-flow-node-body h4 {
  margin: 8px 0 0;
  color: #0f172a;
  font-size: 18px;
  font-weight: 900;
}

.action-flow-node-body p {
  min-height: 42px;
  margin: 8px 0 14px;
  color: #64748b;
  font-size: 13px;
  line-height: 1.6;
}

.action-flow-policy {
  display: inline-flex;
  border-radius: 999px;
  background: #fff1f2;
  color: #be123c;
  font-size: 12px;
  font-weight: 900;
  padding: 6px 9px;
}

.action-flow-policy--continue {
  background: #ecfdf5;
  color: #047857;
}

.action-flow-arrow {
  align-self: center;
  color: #94a3b8;
  font-size: 28px;
  font-weight: 900;
  margin-left: -2px;
}

.action-flow-node--jenkins_trigger .action-flow-node-index {
  background: #1f2d3f;
}

.action-flow-node--gitlab_branch_create .action-flow-node-index {
  background: #9a5b35;
}

.action-flow-node--gitlab_branch_operation .action-flow-node-index {
  background: #9a5b35;
}

.action-flow-node--gitlab_tag_operation .action-flow-node-index {
  background: #b7791f;
}

.action-flow-node--gitlab_webhook_operation .action-flow-node-index {
  background: #0369a1;
}

.action-flow-node--manual_approval .action-flow-node-index {
  background: #0f766e;
}

.action-flow-node--conditional_branch .action-flow-node-index {
  background: #6d5d2e;
}

.action-editor {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.action-editor-redesigned {
  --action-ink: #172033;
  --action-muted: #64748b;
  --action-line: #dbe3ef;
  --action-soft: #f6f8fb;
  --action-tint: #eef3f8;
}

.action-editor-topbar {
  display: flex;
  gap: 18px;
  align-items: center;
  justify-content: space-between;
  overflow: hidden;
  border: 1px solid var(--action-line);
  border-radius: 24px;
  background:
    radial-gradient(circle at 0% 0%, rgba(29, 140, 255, 0.1), transparent 28%),
    linear-gradient(135deg, #ffffff 0%, #f6f8fb 100%);
  padding: 14px 16px;
}

.action-editor-topbar-main {
  display: grid;
  min-width: 0;
  gap: 4px;
}

.action-editor-title-line {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: 10px;
}

.action-editor-title-line strong {
  overflow: hidden;
  color: var(--action-ink);
  font-size: 20px;
  font-weight: 900;
  letter-spacing: -0.035em;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.action-editor-title-line em {
  flex: 0 0 auto;
  border: 1px solid #cbd5e1;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.76);
  color: #334155;
  font-size: 12px;
  font-style: normal;
  font-weight: 800;
  padding: 5px 9px;
}

.action-editor-topbar-main small {
  overflow: hidden;
  color: var(--action-muted);
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.action-editor-eyebrow {
  margin: 0 0 8px;
  color: #64748b;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.16em;
  text-transform: uppercase;
}

.action-editor-title-input,
.action-step-title-input {
  width: 100%;
  border: 0;
  background: transparent !important;
  color: #0f172a !important;
  font-weight: 700;
  outline: 0;
}

.action-editor-title-input {
  font-size: 26px;
  letter-spacing: -0.03em;
}

.action-editor-desc-input {
  margin-top: 10px;
  width: 100%;
  resize: none;
  border: 0;
  background: transparent !important;
  color: #64748b !important;
  outline: 0;
}

.action-editor-topbar-actions {
  display: flex;
  flex: 0 0 auto;
  align-items: center;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 10px;
}

.action-switch {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  color: #334155;
  font-size: 13px;
  font-weight: 700;
}

.action-switch-pill {
  border: 1px solid #dbe3ef;
  border-radius: 999px;
  background: #ffffff;
  padding: 7px 10px;
}

.action-switch input[type='checkbox'],
.action-checkbox-line input[type='checkbox'],
.action-option input[type='checkbox'] {
  width: 16px !important;
  height: 16px !important;
  min-width: 16px !important;
  flex: 0 0 16px;
  padding: 0 !important;
}

.action-scope-switch {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 6px;
  border: 1px solid #dbe3ef;
  border-radius: 16px;
  background: rgba(226, 232, 240, 0.58);
  padding: 4px;
}

.action-scope-switch button {
  border-radius: 12px;
  padding: 8px 11px;
  color: #64748b;
  font-size: 13px;
  font-weight: 700;
  transition: all 0.16s ease;
}

.action-scope-switch button.active {
  background: #ffffff;
  color: #0f172a;
  box-shadow: 0 8px 18px rgba(15, 23, 42, 0.08);
}

.action-editor-body {
  display: grid;
  grid-template-columns: 1fr;
  gap: 10px;
  align-items: start;
}

.action-editor-nav {
  display: flex;
  gap: 6px;
  overflow-x: auto;
  border: 1px solid var(--action-line);
  border-radius: 18px;
  background: #f8fafc;
  padding: 5px;
}

.action-editor-nav-item {
  display: inline-flex;
  min-width: 0;
  flex: 1 1 0;
  gap: 8px;
  align-items: center;
  justify-content: center;
  border: 0;
  border-radius: 14px;
  background: transparent;
  padding: 9px 10px;
  text-align: center;
  transition: all 0.16s ease;
}

.action-editor-nav-item.active {
  border-color: transparent;
  background: var(--action-ink);
  color: #ffffff;
  box-shadow: 0 10px 22px rgba(15, 23, 42, 0.18);
}

.action-editor-nav-index {
  display: inline-flex;
  width: 26px;
  height: 26px;
  align-items: center;
  justify-content: center;
  border-radius: 9px;
  background: #ffffff;
  color: #475569;
  font-size: 11px;
  font-weight: 800;
}

.action-editor-nav-item.active .action-editor-nav-index {
  background: rgba(255, 255, 255, 0.14);
  color: #ffffff;
}

.action-editor-nav-item strong {
  font-size: 13px;
  white-space: nowrap;
}

.action-editor-panel,
.action-pane {
  min-width: 0;
}

.action-pane {
  border: 1px solid var(--action-line);
  border-radius: 24px;
  background: linear-gradient(180deg, #ffffff 0%, #fbfcfe 100%);
  padding: 18px;
}

.action-pane-heading {
  margin-bottom: 14px;
}

.action-pane-heading-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.action-pane-heading h3 {
  margin: 0;
  color: #0f172a;
  font-size: 18px;
  font-weight: 800;
  letter-spacing: -0.02em;
}

.action-pane-heading p {
  margin: 6px 0 0;
  color: #64748b;
  font-size: 14px;
}

.action-field-grid,
.action-step-config,
.action-auth-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.action-step-grid {
  grid-template-columns: minmax(220px, 1.4fr) repeat(3, minmax(150px, 1fr));
}

.action-field {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 8px;
}

.action-field-wide {
  grid-column: 1 / -1;
}

.action-field > span {
  color: #64748b;
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.action-field input,
.action-field select,
.action-field textarea,
.action-code-editor {
  width: 100%;
  border: 1px solid #dbe3ef;
  border-radius: 16px;
  background: #ffffff !important;
  color: #0f172a !important;
  font-size: 14px;
  outline: 0;
  padding: 11px 13px;
  transition:
    border-color 0.16s ease,
    box-shadow 0.16s ease;
}

.action-field textarea,
.action-code-editor {
  resize: vertical;
}

.action-field input:focus,
.action-field select:focus,
.action-field textarea:focus,
.action-code-editor:focus {
  border-color: #64748b;
  box-shadow: 0 0 0 4px rgba(100, 116, 139, 0.12);
}

.action-code-editor {
  min-height: 320px;
  font-family: 'IBM Plex Mono', ui-monospace, SFMono-Regular, Menlo, monospace;
  line-height: 1.7;
}

.action-branch-config {
  grid-template-columns: 1fr;
}

.action-branch-section {
  display: grid;
  grid-column: 1 / -1;
  gap: 16px;
}

.action-branch-section-head {
  padding: 2px 2px 8px;
}

.action-branch-case {
  display: grid;
  gap: 16px;
  border: 1px solid #d7e0ec;
  border-radius: 16px;
  background: #ffffff;
  padding: 12px 14px;
  transition:
    border-color 0.16s ease,
    background-color 0.16s ease;
}

.action-branch-case--active {
  border-color: #b7c4d6;
  background: #f8fafc;
  padding: 16px;
}

.action-branch-case-head,
.action-branch-nested-head,
.action-branch-nested-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.action-branch-case-actions,
.action-branch-nested-actions {
  display: flex;
  flex: 0 0 auto;
  align-items: center;
  gap: 10px;
}

.action-branch-case-title {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: 12px;
}

.action-branch-case-index {
  display: inline-flex;
  width: 34px;
  height: 34px;
  flex: 0 0 34px;
  align-items: center;
  justify-content: center;
  border: 1px solid #cbd5e1;
  border-radius: 12px;
  background: #0f172a;
  color: #ffffff;
  font-size: 13px;
  font-weight: 900;
}

.action-branch-case-head strong {
  color: #0f172a;
  font-size: 14px;
  font-weight: 900;
}

.action-branch-case-detail {
  display: block;
  max-width: 64ch;
  overflow: hidden;
  color: #64748b;
  font-size: 12px;
  font-weight: 600;
  line-height: 1.5;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.action-branch-rule-card {
  display: grid;
  gap: 12px;
  border: 1px solid #e2e8f0;
  border-radius: 14px;
  background: #ffffff;
  padding: 14px;
}

.action-branch-rule-card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  border-bottom: 1px solid #edf2f7;
  padding-bottom: 10px;
}

.action-branch-rule-card-head span {
  color: #64748b;
  font-size: 12px;
  font-weight: 900;
}

.action-branch-rule-card-head strong {
  min-width: 0;
  overflow: hidden;
  color: #0f172a;
  font-size: 13px;
  font-weight: 900;
  text-align: right;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.action-branch-condition-grid,
.action-branch-nested-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.action-branch-nested-head {
  color: #64748b;
  font-size: 12px;
  font-weight: 900;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.action-branch-nested-list {
  display: grid;
  gap: 12px;
}

.action-branch-nested-step {
  display: grid;
  grid-template-columns: 34px minmax(0, 1fr);
  gap: 12px;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  background: #ffffff;
  padding: 10px 12px;
}

.action-branch-nested-step--active {
  border-color: #cbd5e1;
  background: #ffffff;
  padding: 14px;
}

.action-branch-flow-rail {
  position: relative;
  display: flex;
  justify-content: center;
}

.action-branch-flow-rail::after {
  position: absolute;
  top: 38px;
  bottom: 0;
  width: 1px;
  background: #dbe3ef;
  content: '';
}

.action-branch-nested-step:last-child .action-branch-flow-rail::after {
  display: none;
}

.action-branch-flow-rail span {
  position: relative;
  z-index: 1;
  display: inline-flex;
  width: 30px;
  height: 30px;
  flex: 0 0 30px;
  align-items: center;
  justify-content: center;
  border-radius: 10px;
  background: #1f2d3f;
  color: #ffffff;
  font-size: 12px;
  font-weight: 900;
}

.action-branch-nested-body {
  display: grid;
  min-width: 0;
  gap: 12px;
}

.action-branch-nested-summary {
  display: flex;
  min-width: 0;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  min-height: 34px;
}

.action-branch-nested-summary strong {
  display: block;
  overflow: hidden;
  color: #0f172a;
  font-size: 13px;
  font-weight: 900;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.action-branch-nested-summary small {
  display: block;
  color: #64748b;
  font-size: 12px;
  font-weight: 700;
}

.action-branch-nested-top input {
  min-width: 0;
  flex: 1;
  border: 1px solid #dbe3ef;
  border-radius: 14px;
  background: #ffffff;
  color: #0f172a;
  font-size: 14px;
  padding: 10px 12px;
}

.action-branch-nested-config {
  display: grid;
  gap: 12px;
  border-top: 1px solid #edf2f7;
  padding-top: 12px;
}

@media (max-width: 960px) {
  .action-branch-condition-grid,
  .action-branch-nested-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .action-branch-rule-card-head {
    align-items: flex-start;
    flex-direction: column;
  }

  .action-branch-rule-card-head strong,
  .action-branch-case-detail {
    width: 100%;
    text-align: left;
    white-space: normal;
  }
}

@media (max-width: 640px) {
  .action-branch-condition-grid,
  .action-branch-nested-grid {
    grid-template-columns: 1fr;
  }

  .action-branch-case {
    padding: 12px;
  }

  .action-branch-case-head,
  .action-branch-nested-top,
  .action-branch-nested-summary {
    align-items: stretch;
    flex-direction: column;
  }

  .action-branch-case-title {
    align-items: flex-start;
  }

  .action-branch-nested-step {
    grid-template-columns: 1fr;
  }

  .action-branch-flow-rail {
    justify-content: flex-start;
  }

  .action-branch-flow-rail::after {
    display: none;
  }
}

.action-step-list {
  display: grid;
  gap: 16px;
}

.action-step-overview {
  display: grid;
  gap: 14px;
}

.action-flow-canvas--editor {
  min-height: 260px;
}

.action-flow-node--editable {
  min-width: 310px;
}

.action-flow-node--editable .action-flow-node-body {
  display: flex;
  flex-direction: column;
  transition:
    border-color 0.16s ease,
    box-shadow 0.16s ease,
    transform 0.16s ease;
}

.action-flow-node-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.action-flow-node--editable .action-flow-node-index {
  width: 32px;
  height: 32px;
  flex: 0 0 32px;
  border-radius: 12px;
  font-size: 13px;
}

.action-flow-node-summary {
  display: grid;
  gap: 8px;
  min-height: 76px;
  margin: 10px 0 14px;
}

.action-flow-node-summary div {
  display: grid;
  grid-template-columns: 42px minmax(0, 1fr);
  gap: 10px;
  align-items: baseline;
}

.action-flow-node-summary dt {
  color: #94a3b8;
  font-size: 12px;
  font-weight: 900;
}

.action-flow-node-summary dd {
  min-width: 0;
  margin: 0;
  overflow: hidden;
  color: #64748b;
  font-size: 13px;
  font-weight: 700;
  line-height: 1.45;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.action-flow-node--editable:hover .action-flow-node-body,
.action-flow-node--editable.active .action-flow-node-body {
  border-color: #94a3b8;
  box-shadow: 0 22px 46px rgba(15, 23, 42, 0.12);
  transform: translateY(-2px);
}

.action-flow-connector {
  position: relative;
  width: 42px;
  flex: 0 0 42px;
  align-self: center;
  border-top: 1px solid #cbd5e1;
}

.action-flow-connector::after {
  position: absolute;
  top: -4px;
  right: 0;
  width: 8px;
  height: 8px;
  border-top: 1px solid #cbd5e1;
  border-right: 1px solid #cbd5e1;
  content: '';
  transform: rotate(45deg);
}

.action-flow-node-footer {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-top: auto;
}

.action-flow-node-actions {
  display: inline-flex;
  align-items: center;
  justify-content: flex-end;
  gap: 6px;
}

.action-flow-node-actions button {
  border: 1px solid #dbe3ef;
  border-radius: 999px;
  background: #ffffff;
  color: #334155;
  font-size: 12px;
  font-weight: 800;
  padding: 6px 9px;
  transition: all 0.16s ease;
}

.action-flow-node-edit {
  border-color: #bfdbfe !important;
  background: #eff6ff !important;
  color: #1d4ed8 !important;
}

.action-flow-node-actions button:hover:not(:disabled) {
  border-color: #94a3b8;
  background: #f8fafc;
  color: #0f172a;
}

.action-flow-node-actions button:disabled {
  cursor: not-allowed;
  color: #cbd5e1;
}

.action-flow-node-more {
  position: relative;
}

.action-flow-node-more summary {
  display: inline-flex;
  align-items: center;
  border: 1px solid #dbe3ef;
  border-radius: 999px;
  background: #ffffff;
  color: #334155;
  font-size: 12px;
  font-weight: 800;
  list-style: none;
  padding: 6px 9px;
  transition: all 0.16s ease;
}

.action-flow-node-more summary::-webkit-details-marker {
  display: none;
}

.action-flow-node-more summary:hover {
  border-color: #94a3b8;
  background: #f8fafc;
}

.action-flow-node-menu {
  display: grid;
  gap: 6px;
  margin-top: 8px;
  border: 1px solid #dbe3ef;
  border-radius: 14px;
  background: #f8fafc;
  padding: 8px;
}

.action-flow-node-menu button {
  justify-content: center;
  width: 100%;
  background: #ffffff;
}

.action-step-detail {
  min-width: 0;
  border: 1px solid #e2e8f0;
  border-radius: 22px;
  background: #ffffff;
  padding: 16px;
}

.action-step-detail--page {
  box-shadow: 0 18px 38px rgba(15, 23, 42, 0.06);
}

.action-step-detail-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 18px;
}

.action-step-detail-head p {
  margin: 0 0 4px;
  color: #64748b;
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.action-step-detail-head h4 {
  margin: 0;
  color: #0f172a;
  font-size: 20px;
  font-weight: 800;
  letter-spacing: -0.02em;
}

.action-step-card {
  border: 1px solid #e2e8f0;
  border-radius: 24px;
  background: #f8fafc;
  padding: 16px;
}

.action-step-card-head {
  display: flex;
  align-items: center;
  gap: 14px;
  margin-bottom: 16px;
}

.action-step-number {
  display: inline-flex;
  width: 42px;
  height: 42px;
  align-items: center;
  justify-content: center;
  border-radius: 16px;
  background: #172033;
  color: #ffffff;
  font-weight: 800;
}

.action-step-title-input {
  font-size: 18px;
}

.action-step-meta {
  margin-top: 4px;
  color: #64748b;
  font-size: 13px;
}

.action-step-config {
  margin-top: 16px;
  border-top: 1px solid #e2e8f0;
  padding-top: 16px;
}

.action-gitlab-config {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 14px;
}

.action-gitlab-section {
  border: 1px solid #dbe3ef;
  border-radius: 20px;
  background: #f8fafc;
  padding: 14px;
}

.action-gitlab-section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  margin-bottom: 12px;
}

.action-gitlab-section-head strong,
.action-gitlab-section-head small {
  display: block;
}

.action-gitlab-section-head strong {
  color: #0f172a;
  font-size: 14px;
  font-weight: 900;
}

.action-gitlab-section-head small {
  margin-top: 2px;
  color: #64748b;
  font-size: 12px;
}

.action-gitlab-form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

.action-inline-switch {
  display: inline-flex;
  flex: 0 0 auto;
  align-items: center;
  gap: 8px;
  border: 1px solid #dbe3ef;
  border-radius: 999px;
  background: #ffffff;
  color: #334155;
  font-size: 13px;
  font-weight: 800;
  padding: 8px 10px;
}

.action-inline-switch input[type='checkbox'] {
  width: 16px !important;
  height: 16px !important;
  min-width: 16px !important;
  padding: 0 !important;
}

.action-project-picker-actions {
  display: inline-flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
  color: #94a3b8;
  font-size: 12px;
  font-weight: 800;
}

.action-project-picker-actions button {
  color: #0f6fbf;
  transition: color 0.16s ease;
}

.action-project-picker-actions button:hover:not(:disabled) {
  color: #0f172a;
}

.action-project-picker-actions button:disabled {
  cursor: not-allowed;
  color: #cbd5e1;
}

.action-project-picker-toolbar {
  display: grid;
  grid-template-columns: minmax(0, 0.9fr) minmax(0, 1.3fr) auto;
  gap: 10px;
  align-items: end;
  margin-bottom: 12px;
}

.action-project-selected-only {
  display: inline-flex;
  min-height: 46px;
  align-items: center;
  gap: 8px;
  border: 1px solid #dbe3ef;
  border-radius: 16px;
  background: #ffffff;
  color: #334155;
  font-size: 13px;
  font-weight: 800;
  padding: 0 12px;
  white-space: nowrap;
}

.action-project-selected-only input[type='checkbox'],
.action-project-card input[type='checkbox'] {
  width: 16px !important;
  height: 16px !important;
  min-width: 16px !important;
  padding: 0 !important;
}

.action-project-grid {
  display: grid;
  max-height: 260px;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  overflow: auto;
  border: 1px solid #e2e8f0;
  border-radius: 18px;
  background: #ffffff;
  padding: 10px;
}

.action-project-card {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: 10px;
  align-items: flex-start;
  border: 1px solid #e2e8f0;
  border-radius: 16px;
  background: #f8fafc;
  color: #334155;
  padding: 11px;
  transition: all 0.16s ease;
}

.action-project-card:hover {
  border-color: #bfdbfe;
  background: #f1f8ff;
}

.action-project-card.selected {
  border-color: #1d8cff;
  background: #e7f2ff;
  color: #0f172a;
  box-shadow: inset 0 0 0 1px rgba(29, 140, 255, 0.18);
}

.action-project-card.selected input[type='checkbox'] {
  border-color: #1d8cff !important;
  background-color: #1d8cff !important;
}

.action-project-card-copy {
  min-width: 0;
}

.action-project-card-copy strong,
.action-project-card-copy span,
.action-project-card-copy em {
  display: block;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.action-project-card-copy strong {
  color: #0f172a;
  font-size: 13px;
  font-weight: 900;
}

.action-project-card-copy span {
  margin-top: 3px;
  color: #64748b;
  font-size: 12px;
  font-weight: 700;
}

.action-project-card-copy em {
  margin-top: 7px;
  width: fit-content;
  max-width: 100%;
  border-radius: 999px;
  background: #e2e8f0;
  color: #475569;
  font-size: 11px;
  font-style: normal;
  font-weight: 800;
  padding: 3px 7px;
}

.action-project-empty {
  border: 1px dashed #cbd5e1;
  border-radius: 18px;
  background: #ffffff;
  color: #94a3b8;
  font-size: 13px;
  font-weight: 800;
  padding: 28px 14px;
  text-align: center;
}

.action-checkbox-line {
  display: flex;
  align-items: center;
  gap: 10px;
  color: #334155;
  font-size: 14px;
  font-weight: 600;
}

.action-toggle-row {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  border: 1px solid #dbe3ef;
  border-radius: 18px;
  background: #ffffff;
  padding: 12px;
}

.action-toggle-row .action-checkbox-line {
  border: 1px solid #e2e8f0;
  border-radius: 999px;
  background: #f8fafc;
  padding: 8px 11px;
}

.action-option-grid {
  display: grid;
  max-height: 220px;
  gap: 8px;
  overflow: auto;
  border: 1px solid #dbe3ef;
  border-radius: 18px;
  background: #ffffff;
  padding: 10px;
}

.action-option-grid.compact {
  max-height: 180px;
}

.action-option-grid.tall {
  max-height: 360px;
}

.action-option {
  position: relative;
  display: flex;
  align-items: center;
  gap: 10px;
  border: 1px solid transparent;
  border-radius: 14px;
  color: #334155;
  font-size: 14px;
  font-weight: 600;
  padding: 10px 11px;
  transition: all 0.16s ease;
}

.action-option:hover {
  border-color: #dbe3ef;
  background: #f8fafc;
}

.action-option.selected {
  border-color: #1d8cff;
  background: #e7f2ff;
  color: #0f172a;
  box-shadow: inset 0 0 0 1px rgba(29, 140, 255, 0.18);
}

.action-option.selected input[type='checkbox'] {
  border-color: #1d8cff !important;
  background-color: #1d8cff !important;
}

.action-option span {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.action-param-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.action-param-head > span {
  color: #64748b;
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.action-link-button {
  border-radius: 999px;
  color: #334155;
  font-size: 12px;
  font-weight: 800;
  padding: 7px 10px;
  transition: all 0.16s ease;
}

.action-link-button:hover:not(:disabled) {
  background: #eef3f8;
}

.action-link-button:disabled {
  cursor: not-allowed;
  color: #94a3b8;
}

.action-param-table {
  overflow: hidden;
  border: 1px solid #dbe3ef;
  border-radius: 18px;
  background: #ffffff;
}

.action-global-param-list {
  overflow: hidden;
  border: 1px solid #dbe3ef;
  border-radius: 20px;
  background: #ffffff;
}

.action-global-param-head,
.action-global-param-row {
  display: grid;
  grid-template-columns:
    minmax(10rem, 1fr) minmax(10rem, 1fr) minmax(10rem, 1fr)
    7rem 4rem;
  gap: 10px;
  align-items: center;
}

.action-global-param-head {
  background: #f8fafc;
  color: #64748b;
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.08em;
  padding: 10px 12px;
  text-transform: uppercase;
}

.action-global-param-row {
  border-top: 1px solid #e2e8f0;
  padding: 12px;
}

.action-global-param-row input {
  width: 100%;
  border: 1px solid #dbe3ef;
  border-radius: 14px;
  background: #ffffff !important;
  color: #0f172a !important;
  font-size: 13px;
  outline: 0;
  padding: 10px 12px;
}

.action-param-required {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: #334155;
  font-size: 13px;
  font-weight: 800;
}

.action-param-required input[type='checkbox'] {
  width: 16px !important;
  height: 16px !important;
  min-width: 16px !important;
  padding: 0 !important;
}

.action-param-table-head,
.action-param-row {
  display: grid;
  grid-template-columns: minmax(12rem, 1.1fr) minmax(10rem, 0.8fr) minmax(
      12rem,
      1fr
    );
  gap: 10px;
  align-items: center;
}

.action-param-table-head {
  background: #f8fafc;
  color: #64748b;
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.08em;
  padding: 10px 12px;
  text-transform: uppercase;
}

.action-param-row {
  border-top: 1px solid #e2e8f0;
  padding: 12px;
}

.action-param-name strong,
.action-param-name small {
  display: block;
}

.action-param-name strong {
  color: #0f172a;
  font-size: 13px;
  font-weight: 800;
}

.action-param-name small {
  margin-top: 4px;
  color: #64748b;
  font-size: 12px;
  line-height: 1.45;
}

.action-param-mode {
  display: inline-flex;
  margin-left: 7px;
  border-radius: 999px;
  font-size: 11px;
  font-style: normal;
  font-weight: 800;
  padding: 3px 7px;
  vertical-align: middle;
}

.action-param-mode.editable {
  background: #e0f2fe;
  color: #0369a1;
}

.action-param-mode.readonly {
  background: #f1f5f9;
  color: #475569;
}

.action-param-row input,
.action-param-row select {
  width: 100%;
  border: 1px solid #dbe3ef;
  border-radius: 14px;
  background: #ffffff !important;
  color: #0f172a !important;
  font-size: 13px;
  outline: 0;
  padding: 10px 12px;
}

.action-param-row input:disabled,
.action-param-row select:disabled {
  background: #f1f5f9 !important;
  color: #64748b !important;
}

.action-param-readonly-mode {
  display: inline-flex;
  min-height: 42px;
  align-items: center;
  border: 1px solid #dbe3ef;
  border-radius: 14px;
  background: #f8fafc;
  color: #64748b;
  font-size: 13px;
  font-weight: 800;
  padding: 0 13px;
}

.action-param-empty {
  border: 1px dashed #cbd5e1;
  border-radius: 18px;
  background: #f8fafc;
  color: #64748b;
  font-size: 14px;
  padding: 18px;
}

.action-empty-box {
  display: grid;
  place-items: center;
  gap: 10px;
  border: 1px dashed #cbd5e1;
  border-radius: 24px;
  background: #f8fafc;
  color: #64748b;
  padding: 42px 20px;
  text-align: center;
}

.action-empty-box strong {
  color: #0f172a;
  font-size: 16px;
}

.action-editor-error {
  border: 1px solid #fecdd3;
  border-radius: 18px;
  background: #fff1f2;
  color: #be123c;
  font-size: 14px;
  padding: 12px 14px;
}

.action-editor-footer {
  display: flex;
  width: 100%;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.action-editor-footer-actions {
  display: flex;
  gap: 10px;
  margin-left: auto;
}

.action-editor--flat {
  gap: 0;
}

.action-editor--flat .action-editor-topbar {
  border: 0;
  border-bottom: 1px solid var(--action-line);
  border-radius: 0;
  background: transparent;
  padding: 4px 0 14px;
}

.action-editor--flat .action-editor-title-line em {
  background: #f8fafc;
}

.action-editor--flat .action-editor-body {
  gap: 0;
}

.action-editor--flat .action-editor-nav {
  border: 0;
  border-bottom: 1px solid var(--action-line);
  border-radius: 0;
  background: transparent;
  padding: 10px 0;
}

.action-editor--flat .action-editor-nav-item {
  border-radius: 10px;
  padding-block: 8px;
}

.action-editor--flat .action-editor-nav-item.active {
  box-shadow: none;
}

.action-editor--flat .action-pane {
  border: 0;
  border-radius: 0;
  background: transparent;
  padding: 18px 0 0;
}

.action-editor--flat .action-step-detail {
  border: 0;
  border-radius: 0;
  background: transparent;
  padding: 0;
}

.action-editor--flat .action-step-detail--page {
  box-shadow: none;
}

.action-editor--flat .action-step-detail-head {
  border-bottom: 1px solid #e2e8f0;
  margin-bottom: 14px;
  padding-bottom: 14px;
}

.action-editor--flat .action-step-config {
  border-top-color: #edf2f7;
  margin-top: 14px;
  padding-top: 14px;
}

.action-editor--flat .action-branch-section {
  gap: 12px;
}

.action-editor--flat .action-branch-case {
  border-radius: 12px;
  background: #ffffff;
}

.action-editor--flat .action-branch-case--active {
  background: #ffffff;
}

.action-editor--flat .action-branch-rule-card {
  border: 0;
  border-top: 1px solid #edf2f7;
  border-radius: 0;
  padding: 12px 0 0;
}

.action-editor--flat .action-branch-nested-step {
  border: 0;
  border-top: 1px solid #edf2f7;
  border-radius: 0;
  padding-inline: 0;
}

.action-editor--flat .action-branch-nested-step--active {
  background: transparent;
}

.action-editor--flat .action-branch-nested-config {
  border-top-color: #edf2f7;
}

@media (max-width: 900px) {
  .action-editor-topbar,
  .action-editor-body {
    grid-template-columns: 1fr;
  }

  .action-editor-topbar {
    align-items: stretch;
    flex-direction: column;
  }

  .action-editor-topbar-actions {
    justify-content: space-between;
    min-width: 0;
  }

  .action-editor-nav {
    display: flex;
    overflow-x: auto;
    padding-bottom: 4px;
  }

  .action-editor-nav-item {
    min-width: 220px;
  }

  .action-field-grid,
  .action-step-config,
  .action-auth-grid,
  .action-step-grid,
  .action-gitlab-form-grid,
  .action-project-picker-toolbar,
  .action-project-grid {
    grid-template-columns: 1fr;
  }

  .action-step-detail-head {
    flex-direction: column;
  }

  .action-editor-footer {
    align-items: stretch;
    flex-direction: column;
  }

  .action-editor-footer-actions {
    justify-content: flex-end;
  }

  .action-global-param-head {
    display: none;
  }

  .action-global-param-row {
    grid-template-columns: 1fr;
  }
}
</style>

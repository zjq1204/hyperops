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
                    </div>
                    <div class="action-pane-heading-actions">
                      <BaseButton size="sm" @click="openFlowEditor">
                        {{ t('adminPages.actionTemplates.actions.edit') }}
                      </BaseButton>
                    </div>
                  </div>

                  <div v-if="form.steps.length" class="action-step-overview">
                    <ol class="action-step-map">
                      <li
                        v-for="(step, index) in form.steps"
                        :key="step.client_id"
                        class="action-step-map-node"
                        :class="`action-step-map-node--${step.action_type}`"
                      >
                        <div class="action-step-map-index">
                          {{ previewStepIndex(index) }}
                        </div>
                        <div class="action-step-map-card">
                          <div class="action-step-map-head">
                            <span>{{ actionTypeText(step.action_type) }}</span>
                            <strong>
                              {{
                                step.name ||
                                t('adminPages.actionTemplates.steps.step', {
                                  count: index + 1
                                })
                              }}
                            </strong>
                          </div>
                          <p>{{ stepMapSummary(step) }}</p>
                          <div
                            v-if="step.action_type === 'conditional_branch'"
                            class="action-step-map-branches"
                          >
                            <span
                              v-for="(
                                branch, branchIndex
                              ) in previewBranchCases(step).slice(0, 4)"
                              :key="
                                branch.client_id || branch.id || branchIndex
                              "
                            >
                              {{ previewBranchConditionText(branch) }}
                            </span>
                            <em v-if="previewBranchCases(step).length > 4">
                              +{{ previewBranchCases(step).length - 4 }}
                            </em>
                          </div>
                        </div>
                      </li>
                    </ol>
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
                    <BaseButton size="sm" @click="openFlowEditor">{{
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
                          v-if="gitlabProjectLabels.length"
                          class="action-project-label-filter"
                        >
                          <div class="action-project-label-filter-head">
                            <span>{{
                              t(
                                'adminPages.actionTemplates.gitlab.resourceLabels'
                              )
                            }}</span>
                            <button
                              v-if="actionProjectLabelFilter.length"
                              type="button"
                              @click="clearActionProjectLabelFilter"
                            >
                              {{
                                t('adminPages.actionTemplates.gitlab.allLabels')
                              }}
                            </button>
                          </div>
                          <div class="action-project-label-chips">
                            <button
                              v-for="label in gitlabProjectLabels"
                              :key="label.id"
                              type="button"
                              :class="{
                                active: actionProjectLabelFilter.includes(
                                  Number(label.id)
                                )
                              }"
                              @click="toggleActionProjectLabelFilter(label.id)"
                            >
                              {{ label.name }}
                            </button>
                          </div>
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
                              <div
                                v-if="project.labels?.length"
                                class="action-project-card-labels"
                              >
                                <i
                                  v-for="label in project.labels"
                                  :key="label.id"
                                >
                                  {{ label.name }}
                                </i>
                              </div>
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

          <Teleport to="body">
            <section
              v-if="flowEditorOpen"
              class="action-flow-editor-overlay"
              :class="{ 'inspector-closed': !flowInspectorOpen }"
              :aria-label="t('adminPages.actionTemplates.flowEditor.aria')"
            >
              <main class="action-flow-editor-stage">
                <header class="action-flow-editor-topbar">
                  <div class="action-flow-editor-title">
                    <h3>
                      {{ t('adminPages.actionTemplates.flowEditor.title') }}
                    </h3>
                  </div>
                  <div class="action-flow-editor-toolbar">
                    <div class="action-flow-editor-zoom">
                      <button
                        type="button"
                        @click="zoomFlowCanvas('editor', -1)"
                      >
                        −
                      </button>
                      <button type="button" @click="fitFlowCanvas('editor')">
                        {{ t('adminPages.actionTemplates.flowEditor.fitView') }}
                      </button>
                      <button
                        type="button"
                        @click="resetFlowCanvasZoom('editor')"
                      >
                        {{ flowZoomPercent(flowEditorCanvasZoom) }}
                      </button>
                      <button
                        type="button"
                        @click="zoomFlowCanvas('editor', 1)"
                      >
                        +
                      </button>
                    </div>
                    <BaseButton
                      variant="secondary"
                      size="sm"
                      @click="addFlowEditorStep"
                    >
                      {{ t('adminPages.actionTemplates.flowEditor.addNode') }}
                    </BaseButton>
                    <BaseButton size="sm" @click="closeFlowEditor">
                      {{ t('adminPages.actionTemplates.flowEditor.done') }}
                    </BaseButton>
                  </div>
                </header>

                <div
                  ref="flowEditorCanvasRef"
                  class="action-flow-editor-scroll"
                  :class="{ dragging: flowEditorDragging }"
                  @click.capture="handleFlowEditorCanvasClick"
                  @mousedown="startFlowCanvasPan($event, 'editor')"
                  @mousemove="moveFlowCanvasPan"
                  @mouseup="stopFlowCanvasPan"
                  @mouseleave="stopFlowCanvasPan"
                  @wheel="handleFlowCanvasWheel($event, 'editor')"
                  @scroll="scheduleFlowEditorMeasure"
                >
                  <div
                    class="action-flow-canvas-viewport"
                    :style="
                      flowCanvasViewportStyle(
                        flowEditorCanvasSize,
                        flowEditorCanvasZoom
                      )
                    "
                  >
                    <div
                      class="action-flow-editor-canvas action-flow-canvas-inner"
                      :style="flowCanvasInnerStyle(flowEditorCanvasZoom)"
                    >
                      <svg
                        v-if="flowEditorConnections.length"
                        class="action-flow-editor-svg"
                        :viewBox="`0 0 ${flowEditorCanvasSize.width} ${flowEditorCanvasSize.height}`"
                        :style="{
                          width: `${flowEditorCanvasSize.width}px`,
                          height: `${flowEditorCanvasSize.height}px`
                        }"
                        aria-hidden="true"
                      >
                        <defs>
                          <marker
                            id="flowEditorArrow"
                            markerWidth="10"
                            markerHeight="10"
                            refX="9"
                            refY="5"
                            orient="auto"
                          >
                            <path d="M 0 0 L 10 5 L 0 10 z" />
                          </marker>
                        </defs>
                        <path
                          v-for="connection in flowEditorConnections"
                          :key="connection.id"
                          class="action-flow-editor-path"
                          :class="{ active: connection.label }"
                          :d="connection.path"
                          marker-end="url(#flowEditorArrow)"
                        />
                      </svg>
                      <div
                        v-if="
                          flowEditorCanvasZoom >= 1.02 &&
                          flowEditorConnections.some(
                            (connection) => connection.label
                          )
                        "
                        class="action-flow-editor-labels"
                        :style="{
                          width: `${flowEditorCanvasSize.width}px`,
                          height: `${flowEditorCanvasSize.height}px`
                        }"
                        aria-hidden="true"
                      >
                        <span
                          v-for="connection in flowEditorConnections.filter(
                            (item) => item.label && flowEditorCanvasZoom >= 1.02
                          )"
                          :key="`${connection.id}-label`"
                          class="action-flow-editor-label"
                          :style="connection.labelStyle"
                        >
                          {{ connection.label }}
                        </span>
                      </div>

                      <article
                        v-for="(step, index) in form.steps"
                        :key="step.client_id"
                        class="action-flow-editor-node"
                        :class="[
                          `action-flow-editor-node--${step.action_type}`,
                          {
                            selected:
                              selectedFlowTarget.kind === 'step' &&
                              selectedFlowTarget.stepIndex === index,
                            branch: step.action_type === 'conditional_branch'
                          }
                        ]"
                        @click="selectFlowStep(index)"
                      >
                        <span
                          class="action-flow-editor-port action-flow-editor-port--in"
                          :data-flow-editor-port="
                            flowEditorStepPort(index, 'in')
                          "
                          aria-hidden="true"
                        />
                        <span
                          class="action-flow-editor-port action-flow-editor-port--out"
                          :data-flow-editor-port="
                            flowEditorStepPort(index, 'out')
                          "
                          aria-hidden="true"
                        />
                        <span
                          class="action-flow-editor-badge"
                          :class="{
                            green: step.action_type === 'jenkins_trigger',
                            violet: step.action_type === 'conditional_branch'
                          }"
                        >
                          {{ previewStepIndex(index) }}
                        </span>
                        <div class="action-flow-editor-kind">
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

                        <template
                          v-if="step.action_type === 'conditional_branch'"
                        >
                          <div class="action-flow-editor-branch-list">
                            <section
                              v-for="(branch, branchIndex) in step.config
                                .branches"
                              :key="
                                branch.client_id || branch.id || branchIndex
                              "
                              class="action-flow-editor-branch-case"
                              :class="{
                                selected:
                                  selectedFlowTarget.stepIndex === index &&
                                  selectedFlowTarget.branchIndex ===
                                    branchIndex &&
                                  selectedFlowTarget.kind === 'branch'
                              }"
                              @click.stop="selectFlowBranch(index, branchIndex)"
                            >
                              <span
                                class="action-flow-editor-port action-flow-editor-port--branch-in"
                                :data-flow-editor-port="
                                  flowEditorBranchPort(index, branchIndex, 'in')
                                "
                                aria-hidden="true"
                              />
                              <span
                                class="action-flow-editor-port action-flow-editor-port--branch-out"
                                :data-flow-editor-port="
                                  flowEditorBranchPort(
                                    index,
                                    branchIndex,
                                    'out'
                                  )
                                "
                                aria-hidden="true"
                              />
                              <div class="action-flow-editor-branch-head">
                                <strong>
                                  <span>{{ branchIndex + 1 }}</span>
                                  {{
                                    branch.label ||
                                    t(
                                      'adminPages.actionTemplates.branch.caseTitle',
                                      {
                                        count: branchIndex + 1
                                      }
                                    )
                                  }}
                                </strong>
                                <code>{{
                                  previewBranchConditionText(branch)
                                }}</code>
                              </div>
                              <div class="action-flow-editor-mini-steps">
                                <template
                                  v-for="(
                                    nestedStep, nestedIndex
                                  ) in branch.steps"
                                  :key="nestedStep.client_id || nestedIndex"
                                >
                                  <button
                                    type="button"
                                    class="action-flow-editor-mini-step"
                                    :class="{
                                      selected:
                                        selectedFlowTarget.kind === 'nested' &&
                                        selectedFlowTarget.stepIndex ===
                                          index &&
                                        selectedFlowTarget.branchIndex ===
                                          branchIndex &&
                                        selectedFlowTarget.nestedIndex ===
                                          nestedIndex
                                    }"
                                    @click.stop="
                                      selectFlowNestedStep(
                                        index,
                                        branchIndex,
                                        nestedIndex
                                      )
                                    "
                                  >
                                    {{
                                      nestedStep.name ||
                                      actionTypeText(nestedStep.action_type)
                                    }}
                                  </button>
                                  <span
                                    v-if="nestedIndex < branch.steps.length - 1"
                                    class="action-flow-editor-mini-arrow"
                                    aria-hidden="true"
                                  >
                                    →
                                  </span>
                                </template>
                                <span
                                  v-if="!branch.steps?.length"
                                  class="action-flow-editor-mini-step muted"
                                >
                                  {{
                                    t(
                                      'adminPages.actionTemplates.branch.noNestedSteps'
                                    )
                                  }}
                                </span>
                              </div>
                            </section>
                          </div>
                          <div class="action-flow-editor-branch-footer">
                            <span>{{ branchMatchModeText(step) }}</span>
                            <em>{{ flowFailurePolicyText(step) }}</em>
                          </div>
                        </template>

                        <template v-else>
                          <dl class="action-flow-editor-meta">
                            <div
                              v-for="item in stepSummaryItems(step)"
                              :key="item.label"
                            >
                              <dt>{{ item.label }}</dt>
                              <dd>{{ item.value }}</dd>
                            </div>
                          </dl>
                          <span class="action-flow-editor-policy">
                            {{ flowFailurePolicyText(step) }}
                          </span>
                        </template>
                      </article>
                    </div>
                  </div>
                </div>
              </main>

              <aside
                v-if="flowInspectorOpen"
                class="action-flow-editor-inspector"
              >
                <header class="action-flow-inspector-head">
                  <h3>{{ selectedFlowTitle }}</h3>
                  <p>{{ selectedFlowSubtitle }}</p>
                </header>

                <div class="action-flow-inspector-body">
                  <template v-if="selectedFlowTarget.kind === 'step'">
                    <section class="action-flow-inspector-section">
                      <strong>{{
                        t('adminPages.actionTemplates.flowEditor.sections.node')
                      }}</strong>
                      <label class="action-field">
                        <span>{{
                          t('adminPages.actionTemplates.steps.editor.name')
                        }}</span>
                        <input
                          v-model="selectedFlowStep.name"
                          :placeholder="
                            t(
                              'adminPages.actionTemplates.steps.editor.namePlaceholder'
                            )
                          "
                        />
                      </label>
                      <div class="action-flow-inspector-grid">
                        <label class="action-field">
                          <span>{{
                            t(
                              'adminPages.actionTemplates.steps.editor.category'
                            )
                          }}</span>
                          <select
                            :value="actionCategory(selectedFlowStep)"
                            @change="
                              setActionCategory(
                                selectedFlowStep,
                                $event.target.value
                              )
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
                                t(
                                  'adminPages.actionTemplates.steps.types.gitlab'
                                )
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
                        <label class="action-field">
                          <span>{{
                            t('adminPages.actionTemplates.steps.policyName')
                          }}</span>
                          <select v-model="selectedFlowStep.failure_policy">
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
                    </section>

                    <section
                      v-if="selectedFlowStep.action_type === 'jenkins_trigger'"
                      class="action-flow-inspector-section"
                    >
                      <strong>{{
                        t(
                          'adminPages.actionTemplates.flowEditor.sections.jenkins'
                        )
                      }}</strong>
                      <label class="action-field">
                        <span>{{
                          t('adminPages.actionTemplates.jenkins.entry')
                        }}</span>
                        <select
                          v-model.number="selectedFlowStep.config.entry_id"
                          @change="loadJenkinsStepParams(selectedFlowStep)"
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
                          v-model="selectedFlowStep.config.wait_for_completion"
                          type="checkbox"
                        />
                        {{
                          t(
                            'adminPages.actionTemplates.jenkins.waitForCompletion'
                          )
                        }}
                      </label>
                      <div class="action-flow-param-card">
                        <div class="action-param-head">
                          <span>{{
                            t('adminPages.actionTemplates.jenkins.paramsTitle')
                          }}</span>
                          <button
                            type="button"
                            class="action-link-button"
                            :disabled="!selectedFlowStep.config.entry_id"
                            @click="loadJenkinsStepParams(selectedFlowStep)"
                          >
                            {{
                              t('adminPages.actionTemplates.jenkins.refresh')
                            }}
                          </button>
                        </div>
                        <div
                          v-if="selectedFlowStep.paramsLoading"
                          class="action-param-empty"
                        >
                          {{ t('adminPages.actionTemplates.jenkins.loading') }}
                        </div>
                        <div
                          v-else-if="selectedFlowStep.paramRows?.length"
                          class="action-param-table action-flow-param-table"
                        >
                          <div
                            v-for="row in selectedFlowStep.paramRows"
                            :key="row.name"
                            class="action-param-row"
                          >
                            <div class="action-param-name">
                              <strong>{{ row.name }}</strong>
                              <small>{{
                                row.description || row.type || 'String'
                              }}</small>
                            </div>
                            <select
                              v-if="row.mode !== 'readonly'"
                              v-model="row.source"
                              @change="
                                syncJenkinsParamsFromRows(selectedFlowStep)
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
                            <div v-else class="action-param-readonly-mode">
                              {{
                                t('adminPages.actionTemplates.jenkins.entry')
                              }}
                            </div>
                            <select
                              v-if="row.source === 'param'"
                              v-model="row.value"
                              @change="
                                syncJenkinsParamsFromRows(selectedFlowStep)
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
                            <input
                              v-else
                              v-model="row.value"
                              :disabled="
                                row.source === 'default' ||
                                row.mode === 'readonly'
                              "
                              @input="
                                syncJenkinsParamsFromRows(selectedFlowStep)
                              "
                            />
                          </div>
                        </div>
                        <div v-else class="action-param-empty">
                          {{ t('adminPages.actionTemplates.jenkins.empty') }}
                        </div>
                      </div>
                    </section>

                    <section
                      v-else-if="
                        selectedFlowStep.action_type === 'conditional_branch'
                      "
                      class="action-flow-inspector-section"
                    >
                      <strong>{{
                        t(
                          'adminPages.actionTemplates.flowEditor.sections.branch'
                        )
                      }}</strong>
                      <div class="action-flow-inspector-grid">
                        <label class="action-field">
                          <span>{{
                            t('adminPages.actionTemplates.flowEditor.matchMode')
                          }}</span>
                          <select v-model="selectedFlowStep.config.match_mode">
                            <option value="first">
                              {{
                                t(
                                  'adminPages.actionTemplates.flowEditor.matchFirst'
                                )
                              }}
                            </option>
                            <option value="all">
                              {{
                                t(
                                  'adminPages.actionTemplates.flowEditor.matchAll'
                                )
                              }}
                            </option>
                          </select>
                        </label>
                        <label class="action-field">
                          <span>{{
                            t('adminPages.actionTemplates.flowEditor.noMatch')
                          }}</span>
                          <select
                            v-model="selectedFlowStep.config.default_behavior"
                          >
                            <option value="skip">
                              {{
                                t(
                                  'adminPages.actionTemplates.flowEditor.skipBlock'
                                )
                              }}
                            </option>
                            <option value="fail">
                              {{
                                t(
                                  'adminPages.actionTemplates.flowEditor.markFailed'
                                )
                              }}
                            </option>
                          </select>
                        </label>
                      </div>
                      <div class="action-flow-branch-config-list">
                        <button
                          v-for="(branch, branchIndex) in selectedFlowStep
                            .config.branches"
                          :key="branch.client_id || branch.id || branchIndex"
                          type="button"
                          :class="{
                            active:
                              selectedFlowTarget.kind === 'branch' &&
                              selectedFlowTarget.branchIndex === branchIndex
                          }"
                          @click="
                            selectFlowBranch(
                              selectedFlowTarget.stepIndex,
                              branchIndex
                            )
                          "
                        >
                          <strong>{{
                            branch.label ||
                            t('adminPages.actionTemplates.branch.caseTitle', {
                              count: branchIndex + 1
                            })
                          }}</strong>
                          <span>{{ previewBranchConditionText(branch) }}</span>
                        </button>
                      </div>
                      <BaseButton
                        variant="secondary"
                        size="sm"
                        @click="addBranchCase(selectedFlowStep)"
                      >
                        {{ t('adminPages.actionTemplates.branch.addCase') }}
                      </BaseButton>
                    </section>

                    <section
                      v-else-if="isGitLabStep(selectedFlowStep)"
                      class="action-flow-inspector-section"
                    >
                      <strong>{{
                        t(
                          'adminPages.actionTemplates.flowEditor.sections.gitlab'
                        )
                      }}</strong>
                      <label class="action-field">
                        <span>{{
                          t('adminPages.actionTemplates.gitlab.operation')
                        }}</span>
                        <select v-model="selectedFlowStep.config.operation">
                          <option
                            v-for="operation in gitlabOperationOptions(
                              selectedFlowStep.action_type
                            )"
                            :key="operation.value"
                            :value="operation.value"
                          >
                            {{ operation.label }}
                          </option>
                        </select>
                      </label>
                      <label class="action-field">
                        <span>{{
                          t(
                            'adminPages.actionTemplates.steps.editor.specificAction'
                          )
                        }}</span>
                        <select
                          :value="gitlabStepValue(selectedFlowStep)"
                          @change="
                            setGitLabStepValue(
                              selectedFlowStep,
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
                          gitlabPrimaryFieldLabel(selectedFlowStep)
                        }}</span>
                        <input
                          v-model="
                            selectedFlowStep.config[
                              gitlabPrimaryFieldKey(selectedFlowStep)
                            ]
                          "
                          :placeholder="
                            gitlabPrimaryFieldPlaceholder(selectedFlowStep)
                          "
                        />
                      </label>
                      <label
                        v-if="gitlabNeedsRef(selectedFlowStep)"
                        class="action-field"
                      >
                        <span>{{
                          t('adminPages.actionTemplates.gitlab.ref')
                        }}</span>
                        <input v-model="selectedFlowStep.config.ref" />
                      </label>
                      <div class="action-flow-project-picker">
                        <div class="action-flow-project-head">
                          <div>
                            <strong>{{
                              t(
                                'adminPages.actionTemplates.gitlab.fixedProjects'
                              )
                            }}</strong>
                            <span>{{
                              t(
                                'adminPages.actionTemplates.gitlab.selectedCount',
                                {
                                  count:
                                    selectedFlowStep.config.project_ids
                                      ?.length || 0
                                }
                              )
                            }}</span>
                          </div>
                          <div class="action-project-picker-actions">
                            <button
                              type="button"
                              :disabled="
                                !filteredGitLabProjectsForStep(selectedFlowStep)
                                  .length
                              "
                              @click="selectAllGitLabProjects(selectedFlowStep)"
                            >
                              {{
                                t('adminPages.actionTemplates.gitlab.selectAll')
                              }}
                            </button>
                            <span>|</span>
                            <button
                              type="button"
                              :disabled="
                                !selectedFlowStep.config.project_ids?.length
                              "
                              @click="clearActionProjects(selectedFlowStep)"
                            >
                              {{ t('adminPages.actionTemplates.gitlab.clear') }}
                            </button>
                          </div>
                        </div>
                        <div class="action-project-picker-toolbar compact">
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
                          v-if="gitlabProjectLabels.length"
                          class="action-project-label-filter"
                        >
                          <div class="action-project-label-filter-head">
                            <span>{{
                              t(
                                'adminPages.actionTemplates.gitlab.resourceLabels'
                              )
                            }}</span>
                            <button
                              v-if="actionProjectLabelFilter.length"
                              type="button"
                              @click="clearActionProjectLabelFilter"
                            >
                              {{
                                t('adminPages.actionTemplates.gitlab.allLabels')
                              }}
                            </button>
                          </div>
                          <div class="action-project-label-chips">
                            <button
                              v-for="label in gitlabProjectLabels"
                              :key="label.id"
                              type="button"
                              :class="{
                                active: actionProjectLabelFilter.includes(
                                  Number(label.id)
                                )
                              }"
                              @click="toggleActionProjectLabelFilter(label.id)"
                            >
                              {{ label.name }}
                            </button>
                          </div>
                        </div>
                        <label class="action-inline-switch">
                          <input
                            v-model="
                              selectedFlowStep.config
                                .allow_runtime_project_selection
                            "
                            type="checkbox"
                          />
                          <span>{{
                            t('adminPages.actionTemplates.gitlab.allowRuntime')
                          }}</span>
                        </label>
                        <div
                          v-if="
                            filteredGitLabProjectsForStep(selectedFlowStep)
                              .length
                          "
                          class="action-project-grid action-flow-project-grid"
                        >
                          <label
                            v-for="project in filteredGitLabProjectsForStep(
                              selectedFlowStep
                            )"
                            :key="project.id"
                            class="action-project-card"
                            :class="{
                              selected: isSelected(
                                selectedFlowStep.config.project_ids,
                                project.id
                              )
                            }"
                          >
                            <input
                              type="checkbox"
                              :checked="
                                isSelected(
                                  selectedFlowStep.config.project_ids,
                                  project.id
                                )
                              "
                              @change="
                                toggleSelection(
                                  selectedFlowStep.config.project_ids,
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
                              <div
                                v-if="project.labels?.length"
                                class="action-project-card-labels"
                              >
                                <i
                                  v-for="label in project.labels"
                                  :key="label.id"
                                >
                                  {{ label.name }}
                                </i>
                              </div>
                            </div>
                          </label>
                        </div>
                        <div v-else class="action-project-empty">
                          {{
                            t('adminPages.actionTemplates.gitlab.emptyNoMatch')
                          }}
                        </div>
                      </div>
                    </section>

                    <section
                      v-else-if="
                        selectedFlowStep.action_type === 'manual_approval'
                      "
                      class="action-flow-inspector-section"
                    >
                      <strong>{{
                        t(
                          'adminPages.actionTemplates.flowEditor.sections.approval'
                        )
                      }}</strong>
                      <label class="action-field">
                        <span>{{
                          t('adminPages.actionTemplates.approval.message')
                        }}</span>
                        <textarea
                          v-model="selectedFlowStep.config.message"
                          rows="3"
                        ></textarea>
                      </label>
                    </section>
                  </template>

                  <template v-else-if="selectedFlowTarget.kind === 'branch'">
                    <section class="action-flow-inspector-section">
                      <strong>{{
                        t(
                          'adminPages.actionTemplates.flowEditor.sections.condition'
                        )
                      }}</strong>
                      <label class="action-field">
                        <span>{{
                          t('adminPages.actionTemplates.branch.label')
                        }}</span>
                        <input v-model="selectedFlowBranch.label" />
                      </label>
                      <div class="action-flow-inspector-grid">
                        <label class="action-field">
                          <span>{{
                            t('adminPages.actionTemplates.branch.param')
                          }}</span>
                          <select v-model="selectedFlowBranch.condition.param">
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
                            t('adminPages.actionTemplates.branch.operator')
                          }}</span>
                          <select
                            v-model="selectedFlowBranch.condition.operator"
                          >
                            <option
                              v-for="operator in branchOperatorOptions"
                              :key="operator.value"
                              :value="operator.value"
                            >
                              {{ operator.label }}
                            </option>
                          </select>
                        </label>
                      </div>
                      <label
                        v-if="
                          branchOperatorNeedsValue(
                            selectedFlowBranch.condition.operator
                          )
                        "
                        class="action-field"
                      >
                        <span>{{
                          t('adminPages.actionTemplates.branch.value')
                        }}</span>
                        <input v-model="selectedFlowBranch.condition.value" />
                      </label>
                    </section>

                    <section class="action-flow-inspector-section">
                      <div class="action-flow-inspector-section-head">
                        <strong>{{
                          t('adminPages.actionTemplates.branch.steps')
                        }}</strong>
                        <button
                          type="button"
                          class="action-link-button"
                          @click="addFlowNestedStep"
                        >
                          {{
                            t('adminPages.actionTemplates.branch.addNestedStep')
                          }}
                        </button>
                      </div>
                      <div class="action-flow-nested-config-list">
                        <button
                          v-for="(
                            nestedStep, nestedIndex
                          ) in selectedFlowBranch.steps"
                          :key="nestedStep.client_id || nestedIndex"
                          type="button"
                          @click="
                            selectFlowNestedStep(
                              selectedFlowTarget.stepIndex,
                              selectedFlowTarget.branchIndex,
                              nestedIndex
                            )
                          "
                        >
                          <strong>
                            {{ nestedIndex + 1 }}.
                            {{
                              nestedStep.name ||
                              actionTypeText(nestedStep.action_type)
                            }}
                          </strong>
                          <span>{{
                            actionTypeText(nestedStep.action_type)
                          }}</span>
                        </button>
                      </div>
                    </section>
                  </template>

                  <template v-else-if="selectedFlowTarget.kind === 'nested'">
                    <section class="action-flow-inspector-section">
                      <strong>{{
                        t(
                          'adminPages.actionTemplates.flowEditor.sections.nested'
                        )
                      }}</strong>
                      <label class="action-field">
                        <span>{{
                          t('adminPages.actionTemplates.steps.editor.name')
                        }}</span>
                        <input v-model="selectedFlowNestedStep.name" />
                      </label>
                      <div class="action-flow-inspector-grid">
                        <label class="action-field">
                          <span>{{
                            t(
                              'adminPages.actionTemplates.steps.editor.specificAction'
                            )
                          }}</span>
                          <select
                            v-model="selectedFlowNestedStep.action_type"
                            @change="
                              resetNestedStepConfig(selectedFlowNestedStep)
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
                            t('adminPages.actionTemplates.steps.policyName')
                          }}</span>
                          <select
                            v-model="selectedFlowNestedStep.failure_policy"
                          >
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
                    </section>

                    <section
                      v-if="
                        selectedFlowNestedStep.action_type === 'jenkins_trigger'
                      "
                      class="action-flow-inspector-section"
                    >
                      <strong>{{
                        t(
                          'adminPages.actionTemplates.flowEditor.sections.jenkins'
                        )
                      }}</strong>
                      <label class="action-field">
                        <span>{{
                          t('adminPages.actionTemplates.jenkins.entry')
                        }}</span>
                        <select
                          v-model.number="
                            selectedFlowNestedStep.config.entry_id
                          "
                          @change="
                            loadJenkinsStepParams(selectedFlowNestedStep)
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
                            selectedFlowNestedStep.config.wait_for_completion
                          "
                          type="checkbox"
                        />
                        {{
                          t(
                            'adminPages.actionTemplates.jenkins.waitForCompletion'
                          )
                        }}
                      </label>
                      <div class="action-flow-param-card">
                        <div class="action-param-head">
                          <span>{{
                            t('adminPages.actionTemplates.jenkins.paramsTitle')
                          }}</span>
                          <button
                            type="button"
                            class="action-link-button"
                            :disabled="!selectedFlowNestedStep.config.entry_id"
                            @click="
                              loadJenkinsStepParams(selectedFlowNestedStep)
                            "
                          >
                            {{
                              t('adminPages.actionTemplates.jenkins.refresh')
                            }}
                          </button>
                        </div>
                        <div
                          v-if="selectedFlowNestedStep.paramsLoading"
                          class="action-param-empty"
                        >
                          {{ t('adminPages.actionTemplates.jenkins.loading') }}
                        </div>
                        <div
                          v-else-if="selectedFlowNestedStep.paramRows?.length"
                          class="action-param-table action-flow-param-table"
                        >
                          <div
                            v-for="row in selectedFlowNestedStep.paramRows"
                            :key="row.name"
                            class="action-param-row"
                          >
                            <div class="action-param-name">
                              <strong>{{ row.name }}</strong>
                              <small>{{
                                row.description || row.type || 'String'
                              }}</small>
                            </div>
                            <select
                              v-if="row.mode !== 'readonly'"
                              v-model="row.source"
                              @change="
                                syncJenkinsParamsFromRows(
                                  selectedFlowNestedStep
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
                            <div v-else class="action-param-readonly-mode">
                              {{
                                t('adminPages.actionTemplates.jenkins.entry')
                              }}
                            </div>
                            <select
                              v-if="row.source === 'param'"
                              v-model="row.value"
                              @change="
                                syncJenkinsParamsFromRows(
                                  selectedFlowNestedStep
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
                            <input
                              v-else
                              v-model="row.value"
                              :disabled="
                                row.source === 'default' ||
                                row.mode === 'readonly'
                              "
                              @input="
                                syncJenkinsParamsFromRows(
                                  selectedFlowNestedStep
                                )
                              "
                            />
                          </div>
                        </div>
                        <div v-else class="action-param-empty">
                          {{ t('adminPages.actionTemplates.jenkins.empty') }}
                        </div>
                      </div>
                    </section>

                    <section
                      v-else-if="isGitLabStep(selectedFlowNestedStep)"
                      class="action-flow-inspector-section"
                    >
                      <strong>{{
                        t(
                          'adminPages.actionTemplates.flowEditor.sections.gitlab'
                        )
                      }}</strong>
                      <label class="action-field">
                        <span>{{
                          t('adminPages.actionTemplates.gitlab.operation')
                        }}</span>
                        <select
                          v-model="selectedFlowNestedStep.config.operation"
                        >
                          <option
                            v-for="operation in gitlabOperationOptions(
                              selectedFlowNestedStep.action_type
                            )"
                            :key="operation.value"
                            :value="operation.value"
                          >
                            {{ operation.label }}
                          </option>
                        </select>
                      </label>
                      <label class="action-field">
                        <span>{{
                          gitlabPrimaryFieldLabel(selectedFlowNestedStep)
                        }}</span>
                        <input
                          v-model="
                            selectedFlowNestedStep.config[
                              gitlabPrimaryFieldKey(selectedFlowNestedStep)
                            ]
                          "
                        />
                      </label>
                      <label
                        v-if="gitlabNeedsRef(selectedFlowNestedStep)"
                        class="action-field"
                      >
                        <span>{{
                          t('adminPages.actionTemplates.gitlab.ref')
                        }}</span>
                        <input v-model="selectedFlowNestedStep.config.ref" />
                      </label>
                      <div class="action-flow-project-picker">
                        <div class="action-flow-project-head">
                          <div>
                            <strong>{{
                              t(
                                'adminPages.actionTemplates.gitlab.fixedProjects'
                              )
                            }}</strong>
                            <span>{{
                              t(
                                'adminPages.actionTemplates.gitlab.selectedCount',
                                {
                                  count:
                                    selectedFlowNestedStep.config.project_ids
                                      ?.length || 0
                                }
                              )
                            }}</span>
                          </div>
                          <div class="action-project-picker-actions">
                            <button
                              type="button"
                              :disabled="
                                !filteredGitLabProjectsForStep(
                                  selectedFlowNestedStep
                                ).length
                              "
                              @click="
                                selectAllGitLabProjects(selectedFlowNestedStep)
                              "
                            >
                              {{
                                t('adminPages.actionTemplates.gitlab.selectAll')
                              }}
                            </button>
                            <span>|</span>
                            <button
                              type="button"
                              :disabled="
                                !selectedFlowNestedStep.config.project_ids
                                  ?.length
                              "
                              @click="
                                clearActionProjects(selectedFlowNestedStep)
                              "
                            >
                              {{ t('adminPages.actionTemplates.gitlab.clear') }}
                            </button>
                          </div>
                        </div>
                        <div class="action-project-picker-toolbar compact">
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
                          v-if="gitlabProjectLabels.length"
                          class="action-project-label-filter"
                        >
                          <div class="action-project-label-filter-head">
                            <span>{{
                              t(
                                'adminPages.actionTemplates.gitlab.resourceLabels'
                              )
                            }}</span>
                            <button
                              v-if="actionProjectLabelFilter.length"
                              type="button"
                              @click="clearActionProjectLabelFilter"
                            >
                              {{
                                t('adminPages.actionTemplates.gitlab.allLabels')
                              }}
                            </button>
                          </div>
                          <div class="action-project-label-chips">
                            <button
                              v-for="label in gitlabProjectLabels"
                              :key="label.id"
                              type="button"
                              :class="{
                                active: actionProjectLabelFilter.includes(
                                  Number(label.id)
                                )
                              }"
                              @click="toggleActionProjectLabelFilter(label.id)"
                            >
                              {{ label.name }}
                            </button>
                          </div>
                        </div>
                        <label class="action-inline-switch">
                          <input
                            v-model="
                              selectedFlowNestedStep.config
                                .allow_runtime_project_selection
                            "
                            type="checkbox"
                          />
                          <span>{{
                            t('adminPages.actionTemplates.gitlab.allowRuntime')
                          }}</span>
                        </label>
                        <div
                          v-if="
                            filteredGitLabProjectsForStep(
                              selectedFlowNestedStep
                            ).length
                          "
                          class="action-project-grid action-flow-project-grid"
                        >
                          <label
                            v-for="project in filteredGitLabProjectsForStep(
                              selectedFlowNestedStep
                            )"
                            :key="project.id"
                            class="action-project-card"
                            :class="{
                              selected: isSelected(
                                selectedFlowNestedStep.config.project_ids,
                                project.id
                              )
                            }"
                          >
                            <input
                              type="checkbox"
                              :checked="
                                isSelected(
                                  selectedFlowNestedStep.config.project_ids,
                                  project.id
                                )
                              "
                              @change="
                                toggleSelection(
                                  selectedFlowNestedStep.config.project_ids,
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
                              <div
                                v-if="project.labels?.length"
                                class="action-project-card-labels"
                              >
                                <i
                                  v-for="label in project.labels"
                                  :key="label.id"
                                >
                                  {{ label.name }}
                                </i>
                              </div>
                            </div>
                          </label>
                        </div>
                        <div v-else class="action-project-empty">
                          {{
                            t('adminPages.actionTemplates.gitlab.emptyNoMatch')
                          }}
                        </div>
                      </div>
                    </section>

                    <section
                      v-else-if="
                        selectedFlowNestedStep.action_type === 'manual_approval'
                      "
                      class="action-flow-inspector-section"
                    >
                      <strong>{{
                        t(
                          'adminPages.actionTemplates.flowEditor.sections.approval'
                        )
                      }}</strong>
                      <label class="action-field">
                        <span>{{
                          t('adminPages.actionTemplates.approval.message')
                        }}</span>
                        <textarea
                          v-model="selectedFlowNestedStep.config.message"
                          rows="3"
                        ></textarea>
                      </label>
                    </section>
                  </template>
                </div>

                <footer class="action-flow-inspector-footer">
                  <BaseButton
                    variant="secondary"
                    size="sm"
                    @click="handleFlowInspectorBack"
                  >
                    {{ flowInspectorBackLabel }}
                  </BaseButton>
                  <BaseButton
                    variant="secondary"
                    size="sm"
                    @click="duplicateFlowSelection"
                  >
                    {{ flowInspectorDuplicateLabel }}
                  </BaseButton>
                  <BaseButton size="sm" @click="closeFlowInspector">
                    {{ flowInspectorSaveLabel }}
                  </BaseButton>
                </footer>
              </aside>
            </section>
          </Teleport>
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

          <div
            v-if="previewSteps.length"
            ref="previewCanvasRef"
            class="action-flow-canvas action-flow-canvas--interactive"
            :class="{ dragging: previewCanvasDragging }"
            @mousedown="startFlowCanvasPan($event, 'preview')"
            @mousemove="moveFlowCanvasPan"
            @mouseup="stopFlowCanvasPan"
            @mouseleave="stopFlowCanvasPan"
            @wheel="handleFlowCanvasWheel($event, 'preview')"
            @scroll="schedulePreviewFlowMeasure"
          >
            <div class="action-flow-canvas-tools">
              <button type="button" @click="zoomFlowCanvas('preview', -1)">
                −
              </button>
              <button
                type="button"
                class="action-flow-canvas-fit"
                @click="fitFlowCanvas('preview')"
              >
                {{ t('adminPages.actionTemplates.flowEditor.fitView') }}
              </button>
              <button
                type="button"
                class="action-flow-canvas-zoom-value"
                @click="resetFlowCanvasZoom('preview')"
              >
                {{ flowZoomPercent(previewCanvasZoom) }}
              </button>
              <button type="button" @click="zoomFlowCanvas('preview', 1)">
                +
              </button>
            </div>
            <div
              class="action-flow-canvas-viewport"
              :style="
                flowCanvasViewportStyle(
                  previewFlowCanvasSize,
                  previewCanvasZoom
                )
              "
            >
              <div
                class="action-flow-canvas-inner"
                :style="flowCanvasInnerStyle(previewCanvasZoom)"
              >
                <svg
                  v-if="previewFlowConnections.length"
                  class="action-flow-connection-layer"
                  :viewBox="`0 0 ${previewFlowCanvasSize.width} ${previewFlowCanvasSize.height}`"
                  :style="{
                    width: `${previewFlowCanvasSize.width}px`,
                    height: `${previewFlowCanvasSize.height}px`
                  }"
                  aria-hidden="true"
                >
                  <path
                    v-for="connection in previewFlowConnections"
                    :key="connection.id"
                    class="action-flow-connection-path"
                    :d="connection.path"
                  />
                </svg>
                <div
                  v-if="
                    previewFlowConnections.some(
                      (connection) => connection.label
                    )
                  "
                  class="action-flow-connection-labels"
                  :style="{
                    width: `${previewFlowCanvasSize.width}px`,
                    height: `${previewFlowCanvasSize.height}px`
                  }"
                  aria-hidden="true"
                >
                  <span
                    v-for="connection in previewFlowConnections.filter(
                      (item) => item.label
                    )"
                    :key="`${connection.id}-label`"
                    class="action-flow-connection-label"
                    :style="connection.labelStyle"
                  >
                    {{ connection.label }}
                  </span>
                </div>
                <article
                  v-for="(step, index) in previewSteps"
                  :key="step.id || `${step.order}-${index}`"
                  class="action-flow-node"
                  :class="[
                    `action-flow-node--${step.action_type}`,
                    {
                      'action-flow-node--branch-preview':
                        step.action_type === 'conditional_branch'
                    }
                  ]"
                >
                  <span
                    class="action-flow-port action-flow-port--in"
                    :data-flow-port="previewStepPort(index, 'in')"
                    aria-hidden="true"
                  />
                  <span
                    class="action-flow-port action-flow-port--out"
                    :data-flow-port="previewStepPort(index, 'out')"
                    aria-hidden="true"
                  />
                  <div class="action-flow-node-index">
                    {{ previewStepIndex(index) }}
                  </div>
                  <div class="action-flow-node-body">
                    <template v-if="step.action_type === 'conditional_branch'">
                      <div class="action-flow-branch-top">
                        <div>
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
                        </div>
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
                              : t('adminPages.actionTemplates.steps.policyStop')
                          }}
                        </span>
                      </div>
                      <div class="action-flow-branch-diagram">
                        <div class="action-flow-branch-lanes">
                          <div
                            v-for="(branch, branchIndex) in previewBranchCases(
                              step
                            )"
                            :key="branch.id || branch.client_id || branchIndex"
                            class="action-flow-branch-lane"
                          >
                            <span
                              class="action-flow-port action-flow-port--branch-in"
                              :data-flow-port="
                                previewBranchPort(index, branchIndex, 'in')
                              "
                              aria-hidden="true"
                            />
                            <span
                              class="action-flow-port action-flow-port--branch-out"
                              :data-flow-port="
                                previewBranchPort(index, branchIndex, 'out')
                              "
                              aria-hidden="true"
                            />
                            <div class="action-flow-branch-condition">
                              <div class="action-flow-branch-title">
                                <span class="action-flow-branch-number">{{
                                  branchIndex + 1
                                }}</span>
                                <strong>{{
                                  branch.label ||
                                  previewBranchConditionText(branch)
                                }}</strong>
                              </div>
                              <code class="action-flow-branch-rule-chip">{{
                                previewBranchConditionText(branch)
                              }}</code>
                            </div>
                            <div class="action-flow-branch-step-list">
                              <div
                                v-for="(
                                  nestedStep, nestedIndex
                                ) in previewBranchNestedSteps(branch)"
                                :key="
                                  nestedStep.id ||
                                  nestedStep.client_id ||
                                  nestedIndex
                                "
                                class="action-flow-branch-step-item"
                              >
                                <span class="action-flow-branch-step">
                                  {{
                                    nestedStep.name ||
                                    actionTypeText(nestedStep.action_type)
                                  }}
                                </span>
                                <span
                                  v-if="
                                    nestedIndex <
                                    previewBranchNestedSteps(branch).length - 1
                                  "
                                  class="action-flow-branch-step-arrow"
                                  aria-hidden="true"
                                >
                                  →
                                </span>
                              </div>
                              <span
                                v-if="!previewBranchNestedSteps(branch).length"
                                class="action-flow-branch-step action-flow-branch-step--empty"
                              >
                                {{
                                  t(
                                    'adminPages.actionTemplates.branch.noNestedSteps'
                                  )
                                }}
                              </span>
                            </div>
                          </div>
                        </div>
                        <div
                          class="action-flow-branch-merge"
                          aria-hidden="true"
                        />
                      </div>
                      <div class="action-flow-branch-default">
                        {{ t('adminPages.actionTemplates.branch.defaultSkip') }}
                      </div>
                    </template>
                    <template v-else>
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
                            ? t(
                                'adminPages.actionTemplates.steps.policyContinue'
                              )
                            : t('adminPages.actionTemplates.steps.policyStop')
                        }}
                      </span>
                    </template>
                  </div>
                </article>
              </div>
            </div>
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
    </PageFrame>
  </AdminLayout>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import AdminLayout from '@/admin/layout/AdminLayout.vue'
import AdminListSection from '@/admin/components/AdminListSection.vue'
import AdminTable from '@/admin/components/AdminTable.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseModal from '@/components/ui/BaseModal.vue'
import EmptyState from '@/components/ui/EmptyState.vue'
import PageFrame from '@/components/ui/PageFrame.vue'
import { useToast } from '@/composables/useToast'
import actionsApi from '@/api/actions'
import jenkinsApi from '@/api/jenkins'
import gitlabApi from '@/api/gitlab'
import { managementApi } from '@/admin/api/management'

const { t } = useI18n()
const { showToast } = useToast()

const templates = ref([])
const users = ref([])
const groups = ref([])
const jenkinsEntries = ref([])
const gitlabProjects = ref([])
const gitlabProjectLabels = ref([])
const searchQuery = ref('')
const showModal = ref(false)
const showPreviewModal = ref(false)
const editingTemplate = ref(null)
const previewTemplate = ref(null)
const overviewCanvasRef = ref(null)
const overviewFlowConnections = ref([])
const overviewFlowCanvasSize = ref({ width: 1, height: 1 })
const overviewCanvasZoom = ref(1)
const overviewCanvasDragging = ref(false)
const previewCanvasRef = ref(null)
const previewFlowConnections = ref([])
const previewFlowCanvasSize = ref({ width: 1, height: 1 })
const previewCanvasZoom = ref(1)
const previewCanvasDragging = ref(false)
const flowEditorOpen = ref(false)
const flowInspectorOpen = ref(false)
const flowEditorCanvasRef = ref(null)
const flowEditorConnections = ref([])
const flowEditorCanvasSize = ref({ width: 1, height: 1 })
const flowEditorCanvasZoom = ref(0.86)
const flowEditorDragging = ref(false)
const selectedFlowTarget = ref({
  kind: 'step',
  stepIndex: 0,
  branchIndex: null,
  nestedIndex: null
})
const saving = ref(false)
const formError = ref('')
const parameterSchemaText = ref('[]')
const parameterRows = ref([])
const activeEditorTab = ref('basic')
const selectedStepIndex = ref(0)
const stepEditorOpen = ref(false)
const actionProjectSearch = ref('')
const actionProjectGroupFilter = ref('')
const actionProjectLabelFilter = ref([])
const actionProjectSelectedOnly = ref(false)
const FLOW_CANVAS_PAN_BUFFER = 360
const FLOW_CANVAS_MIN_ZOOM = 0.6
const FLOW_CANVAS_MAX_ZOOM = 1.35
const FLOW_CANVAS_ZOOM_STEP = 0.1
let overviewMeasureTimer = null
let previewMeasureTimer = null
let flowEditorMeasureTimer = null
let overviewResizeObserver = null
let previewResizeObserver = null
let flowEditorResizeObserver = null
let flowCanvasPanState = null
let flowEditorSuppressClick = false

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
    label: t('adminPages.actionTemplates.tabs.basic.label')
  },
  {
    key: 'params',
    index: '02',
    label: t('adminPages.actionTemplates.tabs.params.label')
  },
  {
    key: 'steps',
    index: '03',
    label: t('adminPages.actionTemplates.tabs.steps.label')
  },
  {
    key: 'auth',
    index: '04',
    label: t('adminPages.actionTemplates.tabs.auth.label')
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

const selectedFlowStep = computed(() => {
  return form.value.steps[selectedFlowTarget.value.stepIndex] || null
})

const selectedFlowBranch = computed(() => {
  const step = selectedFlowStep.value
  if (!step || step.action_type !== 'conditional_branch') return null
  return step.config?.branches?.[selectedFlowTarget.value.branchIndex] || null
})

const selectedFlowNestedStep = computed(() => {
  return (
    selectedFlowBranch.value?.steps?.[selectedFlowTarget.value.nestedIndex] ||
    null
  )
})

const selectedFlowTitle = computed(() => {
  if (selectedFlowTarget.value.kind === 'nested') {
    return (
      selectedFlowNestedStep.value?.name ||
      actionTypeText(selectedFlowNestedStep.value?.action_type)
    )
  }
  if (selectedFlowTarget.value.kind === 'branch') {
    return (
      selectedFlowBranch.value?.label ||
      t('adminPages.actionTemplates.branch.caseTitle', {
        count: Number(selectedFlowTarget.value.branchIndex) + 1
      })
    )
  }
  return (
    selectedFlowStep.value?.name ||
    t('adminPages.actionTemplates.steps.step', {
      count: Number(selectedFlowTarget.value.stepIndex) + 1
    })
  )
})

const selectedFlowSubtitle = computed(() => {
  if (selectedFlowTarget.value.kind === 'nested') {
    return `${selectedFlowBranch.value?.label || t('adminPages.actionTemplates.branch.caseTitle', { count: Number(selectedFlowTarget.value.branchIndex) + 1 })} · ${actionTypeText(selectedFlowNestedStep.value?.action_type)}`
  }
  if (selectedFlowTarget.value.kind === 'branch') {
    return `${t('adminPages.actionTemplates.branch.title')} ${Number(selectedFlowTarget.value.branchIndex) + 1} · ${previewBranchConditionText(selectedFlowBranch.value)}`
  }
  return `${actionTypeText(selectedFlowStep.value?.action_type)} · ${t('adminPages.actionTemplates.steps.step', { count: Number(selectedFlowTarget.value.stepIndex) + 1 })}`
})

const flowInspectorBackLabel = computed(() => {
  if (selectedFlowTarget.value.kind === 'nested') {
    return t('adminPages.actionTemplates.flowEditor.backToBranch')
  }
  if (selectedFlowTarget.value.kind === 'branch') {
    return t('adminPages.actionTemplates.flowEditor.backToNode')
  }
  return t('adminPages.actionTemplates.flowEditor.closePanel')
})

const flowInspectorDuplicateLabel = computed(() => {
  if (selectedFlowTarget.value.kind === 'nested') {
    return t('adminPages.actionTemplates.flowEditor.duplicateNested')
  }
  if (selectedFlowTarget.value.kind === 'branch') {
    return t('adminPages.actionTemplates.flowEditor.duplicateBranch')
  }
  return t('adminPages.actionTemplates.flowEditor.duplicateNode')
})

const flowInspectorSaveLabel = computed(() => {
  if (selectedFlowTarget.value.kind === 'nested') {
    return t('adminPages.actionTemplates.flowEditor.saveNested')
  }
  if (selectedFlowTarget.value.kind === 'branch') {
    return t('adminPages.actionTemplates.flowEditor.saveBranch')
  }
  return t('adminPages.actionTemplates.flowEditor.saveNode')
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

  return filteredGitLabProjectsForStep(step)
})

function projectMatchesActionFilters(project, step) {
  if (!step || !isGitLabStep(step)) return false

  const selectedIds = new Set(
    (step.config.project_ids || []).map((projectId) => Number(projectId))
  )
  const keyword = actionProjectSearch.value.trim().toLowerCase()
  const groupId = actionProjectGroupFilter.value
  const labelIds = actionProjectLabelFilter.value.map((labelId) =>
    Number(labelId)
  )
  const projectLabelIds = (project.labels || []).map((label) =>
    Number(label.id)
  )

  if (groupId && Number(project.group) !== Number(groupId)) return false
  if (actionProjectSelectedOnly.value && !selectedIds.has(Number(project.id))) {
    return false
  }
  if (
    labelIds.length &&
    !labelIds.some((labelId) => projectLabelIds.includes(labelId))
  ) {
    return false
  }
  if (!keyword) return true
  return `${project.name || ''} ${project.path || ''} ${project.group_name || ''}`
    .toLowerCase()
    .includes(keyword)
}

function filteredGitLabProjectsForStep(step) {
  if (!step || !isGitLabStep(step)) return []
  return gitlabProjects.value.filter((project) =>
    projectMatchesActionFilters(project, step)
  )
}

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
  const [
    usersPayload,
    groupsPayload,
    entriesPayload,
    projectsPayload,
    projectLabelsPayload
  ] = await Promise.allSettled([
    managementApi.getUsers({ page_size: 10000 }),
    managementApi.getGroups({ page_size: 10000 }),
    jenkinsApi.listEntries(),
    gitlabApi.listProjects(),
    gitlabApi.listProjectLabels({ page_size: 1000 })
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
  gitlabProjectLabels.value =
    projectLabelsPayload.status === 'fulfilled'
      ? normalizeList(projectLabelsPayload.value)
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
  schedulePreviewFlowMeasure()
}

function closePreviewModal() {
  showPreviewModal.value = false
  previewTemplate.value = null
  previewFlowConnections.value = []
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

function openFlowEditor() {
  if (!form.value.steps.length) {
    addStep()
  }
  selectedFlowTarget.value = {
    kind: 'step',
    stepIndex: Math.min(selectedStepIndex.value, form.value.steps.length - 1),
    branchIndex: null,
    nestedIndex: null
  }
  stepEditorOpen.value = false
  flowEditorOpen.value = true
  flowInspectorOpen.value = true
  nextTick(() => {
    if (flowEditorResizeObserver && flowEditorCanvasRef.value) {
      flowEditorResizeObserver.observe(flowEditorCanvasRef.value)
    }
    if (flowEditorCanvasRef.value) {
      delete flowEditorCanvasRef.value.dataset.flowCanvasBuffered
    }
    flowEditorCanvasZoom.value = 0.78
    scheduleFlowEditorMeasure()
    window.setTimeout(() => fitFlowCanvas('editor'), 100)
  })
}

function openFlowEditorForStep(index) {
  selectedStepIndex.value = index
  selectedFlowTarget.value = {
    kind: 'step',
    stepIndex: index,
    branchIndex: null,
    nestedIndex: null
  }
  openFlowEditor()
}

function closeFlowEditor() {
  flowEditorOpen.value = false
  flowInspectorOpen.value = false
  flowEditorConnections.value = []
  stopFlowCanvasPan()
}

function closeFlowInspector() {
  flowInspectorOpen.value = false
  nextTick(() => {
    scheduleFlowEditorMeasure()
  })
}

function handleFlowInspectorBack() {
  const target = selectedFlowTarget.value
  if (target.kind === 'nested') {
    selectFlowBranch(target.stepIndex, target.branchIndex)
    return
  }
  if (target.kind === 'branch') {
    selectFlowStep(target.stepIndex)
    return
  }
  closeFlowInspector()
}

function isFlowEditorInteractiveTarget(target) {
  return Boolean(
    target?.closest?.(
      'button, input, select, textarea, a, [role="button"], [contenteditable="true"]'
    )
  )
}

function handleFlowEditorCanvasClick(event) {
  if (!flowEditorSuppressClick) return
  event.preventDefault()
  event.stopPropagation()
}

function centerFlowEditorSelectedNode() {
  const canvas = flowEditorCanvasRef.value
  if (!canvas) return
  window.requestAnimationFrame(() => {
    const targetNode =
      canvas.querySelector('.action-flow-editor-node.selected') ||
      canvas.querySelector('.action-flow-editor-node')
    if (!targetNode) return
    const canvasRect = canvas.getBoundingClientRect()
    const nodeRect = targetNode.getBoundingClientRect()
    canvas.scrollLeft += Math.round(
      nodeRect.left +
        nodeRect.width / 2 -
        canvasRect.left -
        canvas.clientWidth / 2
    )
    canvas.scrollTop += Math.round(
      nodeRect.top +
        nodeRect.height / 2 -
        canvasRect.top -
        canvas.clientHeight / 2
    )
    scheduleFlowEditorMeasure()
  })
}

function centerFlowEditorGraph() {
  const canvas = flowEditorCanvasRef.value
  if (!canvas) return
  window.requestAnimationFrame(() => {
    const nodes = [...canvas.querySelectorAll('.action-flow-editor-node')]
    if (!nodes.length) return
    const canvasRect = canvas.getBoundingClientRect()
    const rects = nodes.map((node) => node.getBoundingClientRect())
    const left = Math.min(...rects.map((rect) => rect.left))
    const right = Math.max(...rects.map((rect) => rect.right))
    const top = Math.min(...rects.map((rect) => rect.top))
    const bottom = Math.max(...rects.map((rect) => rect.bottom))
    canvas.scrollLeft += Math.round(
      (left + right) / 2 - (canvasRect.left + canvas.clientWidth / 2)
    )
    canvas.scrollTop += Math.round(
      (top + bottom) / 2 - (canvasRect.top + canvas.clientHeight / 2)
    )
    scheduleFlowEditorMeasure()
  })
}

function selectFlowStep(stepIndex) {
  selectedStepIndex.value = stepIndex
  flowInspectorOpen.value = true
  selectedFlowTarget.value = {
    kind: 'step',
    stepIndex,
    branchIndex: null,
    nestedIndex: null
  }
}

function selectFlowBranch(stepIndex, branchIndex) {
  selectedStepIndex.value = stepIndex
  flowInspectorOpen.value = true
  selectedFlowTarget.value = {
    kind: 'branch',
    stepIndex,
    branchIndex,
    nestedIndex: null
  }
}

function selectFlowNestedStep(stepIndex, branchIndex, nestedIndex) {
  selectedStepIndex.value = stepIndex
  flowInspectorOpen.value = true
  selectedFlowTarget.value = {
    kind: 'nested',
    stepIndex,
    branchIndex,
    nestedIndex
  }
}

function addFlowEditorStep() {
  addStep()
  selectFlowStep(form.value.steps.length - 1)
  scheduleFlowEditorMeasure()
}

function addFlowNestedStep() {
  const branch = selectedFlowBranch.value
  if (!branch) return
  addBranchNestedStep(branch)
  selectFlowNestedStep(
    selectedFlowTarget.value.stepIndex,
    selectedFlowTarget.value.branchIndex,
    branch.steps.length - 1
  )
  scheduleFlowEditorMeasure()
}

function duplicateFlowSelection() {
  const target = selectedFlowTarget.value
  if (target.kind === 'nested' && selectedFlowNestedStep.value) {
    const source = selectedFlowNestedStep.value
    const copy = normalizeBranchNestedStep({
      ...JSON.parse(JSON.stringify(source)),
      id: undefined,
      client_id: undefined,
      name: t('adminPages.actionTemplates.flowEditor.copyName', {
        name: source.name || actionTypeText(source.action_type)
      })
    })
    selectedFlowBranch.value.steps.splice(target.nestedIndex + 1, 0, copy)
    selectFlowNestedStep(
      target.stepIndex,
      target.branchIndex,
      target.nestedIndex + 1
    )
    return
  }
  if (target.kind === 'branch' && selectedFlowBranch.value) {
    const source = selectedFlowBranch.value
    const copy = normalizeBranchCase(
      {
        ...JSON.parse(JSON.stringify(source)),
        id: undefined,
        client_id: undefined,
        label: t('adminPages.actionTemplates.flowEditor.copyName', {
          name:
            source.label ||
            t('adminPages.actionTemplates.branch.caseTitle', {
              count: target.branchIndex + 1
            })
        })
      },
      target.branchIndex + 2
    )
    selectedFlowStep.value.config.branches.splice(
      target.branchIndex + 1,
      0,
      copy
    )
    selectFlowBranch(target.stepIndex, target.branchIndex + 1)
    return
  }
  if (selectedFlowStep.value) {
    const source = selectedFlowStep.value
    const copy = normalizeStep({
      ...JSON.parse(JSON.stringify(source)),
      id: undefined,
      client_id: undefined,
      name: t('adminPages.actionTemplates.flowEditor.copyName', {
        name: source.name || actionTypeText(source.action_type)
      })
    })
    form.value.steps.splice(target.stepIndex + 1, 0, copy)
    syncStepOrders()
    selectFlowStep(target.stepIndex + 1)
  }
  scheduleFlowEditorMeasure()
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

function previewBranchConditionText(branch) {
  const condition = branch?.condition || {}
  if (!condition.param) {
    return t('adminPages.actionTemplates.branch.conditionMissing')
  }

  const operatorSymbols = {
    equals: '=',
    not_equals: '!=',
    contains: 'contains',
    is_empty: 'is empty',
    is_not_empty: 'is not empty'
  }
  const operator = operatorSymbols[condition.operator] || condition.operator

  if (!branchOperatorNeedsValue(condition.operator)) {
    return `${condition.param} ${operator}`
  }

  return `${condition.param} ${operator} "${condition.value || ''}"`
}

function branchNestedStepNames(branch) {
  const names = (branch?.steps || [])
    .map((step) => step.name || actionTypeText(step.action_type))
    .filter(Boolean)
  return names.length
    ? names.join(', ')
    : t('adminPages.actionTemplates.branch.noNestedSteps')
}

function previewBranchCases(step) {
  return step?.config?.branches || []
}

function previewBranchNestedSteps(branch) {
  return branch?.steps || []
}

function previewStepIndex(index) {
  return String(index + 1).padStart(2, '0')
}

function previewStepPort(index, side) {
  return `step-${index}-${side}`
}

function previewBranchPort(stepIndex, branchIndex, side) {
  return `step-${stepIndex}-branch-${branchIndex}-${side}`
}

function overviewStepPort(index, side) {
  return `overview-step-${index}-${side}`
}

function overviewBranchPort(stepIndex, branchIndex, side) {
  return `overview-step-${stepIndex}-branch-${branchIndex}-${side}`
}

function flowEditorStepPort(index, side) {
  return `editor-step-${index}-${side}`
}

function flowEditorBranchPort(stepIndex, branchIndex, side) {
  return `editor-step-${stepIndex}-branch-${branchIndex}-${side}`
}

function branchMatchModeText(step) {
  return step?.config?.match_mode === 'all'
    ? t('adminPages.actionTemplates.flowEditor.matchAllSummary')
    : t('adminPages.actionTemplates.flowEditor.matchFirstSummary')
}

function flowFailurePolicyText(step) {
  return step?.failure_policy === 'continue'
    ? t('adminPages.actionTemplates.steps.policyContinue')
    : t('adminPages.actionTemplates.steps.policyStop')
}

function isPreviewBranchStep(step) {
  return step?.action_type === 'conditional_branch'
}

function clampFlowCanvasZoom(value) {
  return Math.min(
    FLOW_CANVAS_MAX_ZOOM,
    Math.max(FLOW_CANVAS_MIN_ZOOM, Number(value) || 1)
  )
}

function flowZoomPercent(value) {
  return `${Math.round(clampFlowCanvasZoom(value) * 100)}%`
}

function flowCanvasInnerStyle(zoom) {
  const buffer = FLOW_CANVAS_PAN_BUFFER
  return {
    transform: `translate(${buffer}px, ${buffer}px) scale(${clampFlowCanvasZoom(zoom)})`
  }
}

function flowCanvasViewportStyle(size, zoom) {
  const scale = clampFlowCanvasZoom(zoom)
  const buffer = FLOW_CANVAS_PAN_BUFFER * 2
  return {
    width: `${Math.max(1, Math.ceil((size?.width || 1) * scale + buffer))}px`,
    height: `${Math.max(1, Math.ceil((size?.height || 1) * scale + buffer))}px`
  }
}

function flowCanvasState(kind) {
  if (kind === 'overview') {
    return {
      canvasRef: overviewCanvasRef,
      draggingRef: overviewCanvasDragging,
      zoomRef: overviewCanvasZoom,
      measure: scheduleOverviewFlowMeasure
    }
  }
  if (kind === 'editor') {
    return {
      canvasRef: flowEditorCanvasRef,
      draggingRef: flowEditorDragging,
      zoomRef: flowEditorCanvasZoom,
      measure: scheduleFlowEditorMeasure
    }
  }

  return {
    canvasRef: previewCanvasRef,
    draggingRef: previewCanvasDragging,
    zoomRef: previewCanvasZoom,
    measure: schedulePreviewFlowMeasure
  }
}

function setFlowCanvasZoom(kind, value) {
  const state = flowCanvasState(kind)
  state.zoomRef.value = clampFlowCanvasZoom(value)
  nextTick(() => {
    state.measure()
  })
}

function zoomFlowCanvas(kind, direction, anchorEvent = null) {
  const state = flowCanvasState(kind)
  const canvas = state.canvasRef.value
  const oldZoom = clampFlowCanvasZoom(state.zoomRef.value)
  const nextZoom = clampFlowCanvasZoom(
    state.zoomRef.value + FLOW_CANVAS_ZOOM_STEP * direction
  )
  if (nextZoom === oldZoom) return

  let anchorX = canvas ? canvas.clientWidth / 2 : 0
  let anchorY = canvas ? canvas.clientHeight / 2 : 0
  if (anchorEvent && canvas) {
    const rect = canvas.getBoundingClientRect()
    anchorX = anchorEvent.clientX - rect.left
    anchorY = anchorEvent.clientY - rect.top
  }

  const originX = canvas ? (canvas.scrollLeft + anchorX) / oldZoom : 0
  const originY = canvas ? (canvas.scrollTop + anchorY) / oldZoom : 0
  state.zoomRef.value = nextZoom
  nextTick(() => {
    state.measure()
    window.requestAnimationFrame(() => {
      if (!canvas) return
      canvas.scrollLeft = Math.max(0, Math.round(originX * nextZoom - anchorX))
      canvas.scrollTop = Math.max(0, Math.round(originY * nextZoom - anchorY))
    })
  })
}

function resetFlowCanvasZoom(kind) {
  const state = flowCanvasState(kind)
  state.zoomRef.value = 1
  nextTick(() => {
    state.measure()
    centerFlowCanvas(kind)
  })
}

function handleFlowCanvasWheel(event, kind) {
  event.preventDefault()
  zoomFlowCanvas(kind, event.deltaY > 0 ? -1 : 1, event)
}

function startFlowCanvasPan(event, kind) {
  if (event.button !== 0 || isFlowEditorInteractiveTarget(event.target)) return
  const state = flowCanvasState(kind)
  const canvas = state.canvasRef.value
  if (!canvas) return
  flowCanvasPanState = {
    kind,
    startX: event.clientX,
    startY: event.clientY,
    scrollLeft: canvas.scrollLeft,
    scrollTop: canvas.scrollTop,
    moved: false
  }
  state.draggingRef.value = true
}

function moveFlowCanvasPan(event) {
  if (!flowCanvasPanState) return
  const state = flowCanvasState(flowCanvasPanState.kind)
  const canvas = state.canvasRef.value
  if (!canvas) return
  const deltaX = event.clientX - flowCanvasPanState.startX
  const deltaY = event.clientY - flowCanvasPanState.startY
  if (Math.abs(deltaX) > 3 || Math.abs(deltaY) > 3) {
    flowCanvasPanState.moved = true
  }
  canvas.scrollLeft = flowCanvasPanState.scrollLeft - deltaX
  canvas.scrollTop = flowCanvasPanState.scrollTop - deltaY
}

function stopFlowCanvasPan() {
  if (!flowCanvasPanState) return
  const state = flowCanvasState(flowCanvasPanState.kind)
  if (flowCanvasPanState.kind === 'editor' && flowCanvasPanState.moved) {
    flowEditorSuppressClick = true
    window.setTimeout(() => {
      flowEditorSuppressClick = false
    }, 0)
  }
  state.draggingRef.value = false
  flowCanvasPanState = null
}

function ensureFlowCanvasBufferedScroll(canvas, scale = 1) {
  if (!canvas || canvas.dataset.flowCanvasBuffered === 'true') return
  canvas.dataset.flowCanvasBuffered = 'true'
  window.requestAnimationFrame(() => {
    const bounds = flowCanvasContentBounds(canvas)
    if (!bounds) {
      canvas.scrollLeft = Math.round(FLOW_CANVAS_PAN_BUFFER * scale)
      canvas.scrollTop = Math.round(FLOW_CANVAS_PAN_BUFFER * scale)
      return
    }
    canvas.scrollLeft = Math.max(
      0,
      Math.round(bounds.left + bounds.width / 2 - canvas.clientWidth / 2)
    )
    canvas.scrollTop = Math.max(
      0,
      Math.round(bounds.top + bounds.height / 2 - canvas.clientHeight / 2)
    )
  })
}

function flowCanvasContentBounds(canvas) {
  const inner = canvas?.querySelector('.action-flow-canvas-inner')
  if (!canvas || !inner) return null
  const innerRect = inner.getBoundingClientRect()
  const itemRects = [
    ...canvas.querySelectorAll(
      [
        '.action-flow-node',
        '.action-flow-editor-node',
        '.action-flow-connection-label',
        '.action-flow-editor-label'
      ].join(', ')
    )
  ].map((node) => node.getBoundingClientRect())
  if (!itemRects.length) return null
  const left = Math.min(...itemRects.map((rect) => rect.left)) - innerRect.left
  const right =
    Math.max(...itemRects.map((rect) => rect.right)) - innerRect.left
  const top = Math.min(...itemRects.map((rect) => rect.top)) - innerRect.top
  const bottom =
    Math.max(...itemRects.map((rect) => rect.bottom)) - innerRect.top
  return { left, right, top, bottom, width: right - left, height: bottom - top }
}

function centerFlowCanvas(kind) {
  const state = flowCanvasState(kind)
  const canvas = state.canvasRef.value
  if (!canvas) return
  window.requestAnimationFrame(() => {
    const bounds = flowCanvasContentBounds(canvas)
    if (!bounds) return
    canvas.scrollLeft = Math.max(
      0,
      Math.round(bounds.left + bounds.width / 2 - canvas.clientWidth / 2)
    )
    canvas.scrollTop = Math.max(
      0,
      Math.round(bounds.top + bounds.height / 2 - canvas.clientHeight / 2)
    )
  })
}

function fitFlowCanvas(kind) {
  const state = flowCanvasState(kind)
  const canvas = state.canvasRef.value
  if (!canvas) return
  const bounds = flowCanvasContentBounds(canvas)
  if (!bounds) return
  const currentZoom = clampFlowCanvasZoom(state.zoomRef.value)
  const rawWidth = bounds.width / currentZoom
  const rawHeight = bounds.height / currentZoom
  const nextZoom = clampFlowCanvasZoom(
    Math.min(
      1,
      (canvas.clientWidth - 88) / Math.max(rawWidth, 1),
      (canvas.clientHeight - 72) / Math.max(rawHeight, 1)
    )
  )
  state.zoomRef.value = nextZoom
  nextTick(() => {
    state.measure()
    if (kind === 'editor') {
      centerFlowEditorGraph()
      return
    }
    centerFlowCanvas(kind)
  })
}

function previewConnectionPath(start, end) {
  const deltaX = end.x - start.x
  const direction = deltaX >= 0 ? 1 : -1
  const bend = Math.max(56, Math.min(180, Math.abs(deltaX) * 0.46))
  const c1x = start.x + bend * direction
  const c2x = end.x - bend * direction
  return `M ${start.x} ${start.y} C ${c1x} ${start.y}, ${c2x} ${end.y}, ${end.x} ${end.y}`
}

function previewConnectionLabelStyle(start, end, offsetY = 0) {
  const x = start.x + (end.x - start.x) * 0.45
  const y = start.y + (end.y - start.y) * 0.45 + offsetY
  return {
    left: `${x}px`,
    top: `${y}px`
  }
}

function getPreviewPortMap(canvas, selector, datasetKey, zoom = 1) {
  const inner = canvas.querySelector('.action-flow-canvas-inner') || canvas
  const canvasRect = inner.getBoundingClientRect()
  const ports = new Map()
  const scale = clampFlowCanvasZoom(zoom)
  canvas.querySelectorAll(selector).forEach((node) => {
    const rect = node.getBoundingClientRect()
    ports.set(node.dataset[datasetKey], {
      x: (rect.left - canvasRect.left + rect.width / 2) / scale,
      y: (rect.top - canvasRect.top + rect.height / 2) / scale
    })
  })
  return ports
}

function getPreviewConnectionDescriptors(
  steps = previewSteps.value,
  stepPort = previewStepPort,
  branchPort = previewBranchPort,
  idPrefix = 'preview'
) {
  const descriptors = []

  steps.slice(0, -1).forEach((step, index) => {
    const nextStep = steps[index + 1]
    const currentIsBranch = isPreviewBranchStep(step)
    const nextIsBranch = isPreviewBranchStep(nextStep)

    if (!currentIsBranch && !nextIsBranch) {
      descriptors.push({
        id: `${idPrefix}-step-${index}-to-step-${index + 1}`,
        from: stepPort(index, 'out'),
        to: stepPort(index + 1, 'in')
      })
      return
    }

    if (!currentIsBranch && nextIsBranch) {
      previewBranchCases(nextStep).forEach((branch, branchIndex) => {
        descriptors.push({
          id: `${idPrefix}-step-${index}-to-branch-${index + 1}-${branchIndex}`,
          from: stepPort(index, 'out'),
          to: branchPort(index + 1, branchIndex, 'in'),
          label: previewBranchConditionText(branch)
        })
      })
      return
    }

    if (currentIsBranch && !nextIsBranch) {
      previewBranchCases(step).forEach((branch, branchIndex) => {
        descriptors.push({
          id: `${idPrefix}-branch-${index}-${branchIndex}-to-step-${index + 1}`,
          from: branchPort(index, branchIndex, 'out'),
          to: stepPort(index + 1, 'in')
        })
      })
      return
    }

    previewBranchCases(step).forEach((branch, branchIndex) => {
      previewBranchCases(nextStep).forEach((nextBranch, nextBranchIndex) => {
        descriptors.push({
          id: `${idPrefix}-branch-${index}-${branchIndex}-to-branch-${index + 1}-${nextBranchIndex}`,
          from: branchPort(index, branchIndex, 'out'),
          to: branchPort(index + 1, nextBranchIndex, 'in'),
          label: previewBranchConditionText(nextBranch)
        })
      })
    })
  })

  return descriptors
}

function getFlowEditorConnectionDescriptors() {
  const steps = form.value.steps
  const descriptors = []

  steps.slice(0, -1).forEach((step, index) => {
    const nextStep = steps[index + 1]
    const currentIsBranch = isPreviewBranchStep(step)
    const nextIsBranch = isPreviewBranchStep(nextStep)

    if (!currentIsBranch && !nextIsBranch) {
      descriptors.push({
        id: `editor-step-${index}-to-step-${index + 1}`,
        from: flowEditorStepPort(index, 'out'),
        to: flowEditorStepPort(index + 1, 'in')
      })
      return
    }

    if (!currentIsBranch && nextIsBranch) {
      previewBranchCases(nextStep).forEach((branch, branchIndex) => {
        descriptors.push({
          id: `editor-step-${index}-to-branch-${index + 1}-${branchIndex}`,
          from: flowEditorStepPort(index, 'out'),
          to: flowEditorBranchPort(index + 1, branchIndex, 'in'),
          label: previewBranchConditionText(branch),
          labelOffset: (branchIndex % 2 === 0 ? -1 : 1) * 8
        })
      })
      return
    }

    if (currentIsBranch && !nextIsBranch) {
      previewBranchCases(step).forEach((branch, branchIndex) => {
        descriptors.push({
          id: `editor-branch-${index}-${branchIndex}-to-step-${index + 1}`,
          from: flowEditorBranchPort(index, branchIndex, 'out'),
          to: flowEditorStepPort(index + 1, 'in')
        })
      })
      return
    }

    previewBranchCases(step).forEach((branch, branchIndex) => {
      previewBranchCases(nextStep).forEach((nextBranch, nextBranchIndex) => {
        descriptors.push({
          id: `editor-branch-${index}-${branchIndex}-to-branch-${index + 1}-${nextBranchIndex}`,
          from: flowEditorBranchPort(index, branchIndex, 'out'),
          to: flowEditorBranchPort(index + 1, nextBranchIndex, 'in'),
          label: previewBranchConditionText(nextBranch),
          labelOffset: (nextBranchIndex % 2 === 0 ? -1 : 1) * 8
        })
      })
    })
  })

  return descriptors
}

function measureFlowEditorConnections() {
  const canvas = flowEditorCanvasRef.value
  if (!canvas || !flowEditorOpen.value || !form.value.steps.length) {
    flowEditorConnections.value = []
    return
  }

  const inner = canvas.querySelector('.action-flow-canvas-inner') || canvas
  const scale = clampFlowCanvasZoom(flowEditorCanvasZoom.value)
  const ports = getPreviewPortMap(
    canvas,
    '[data-flow-editor-port]',
    'flowEditorPort',
    scale
  )
  flowEditorCanvasSize.value = {
    width: Math.max(inner.scrollWidth, 1),
    height: Math.max(inner.scrollHeight, 1)
  }
  flowEditorConnections.value = getFlowEditorConnectionDescriptors()
    .map((descriptor) => {
      const start = ports.get(descriptor.from)
      const end = ports.get(descriptor.to)
      if (!start || !end) return null
      return {
        ...descriptor,
        path: previewConnectionPath(start, end),
        labelStyle: previewConnectionLabelStyle(
          start,
          end,
          descriptor.labelOffset || 0
        )
      }
    })
    .filter(Boolean)
}

function scheduleFlowEditorMeasure() {
  if (flowEditorMeasureTimer) {
    window.clearTimeout(flowEditorMeasureTimer)
  }
  flowEditorMeasureTimer = window.setTimeout(() => {
    flowEditorMeasureTimer = null
    nextTick(() => {
      measureFlowEditorConnections()
    })
  }, 24)
}

function measurePreviewFlowConnections() {
  const canvas = previewCanvasRef.value
  if (!canvas || !showPreviewModal.value || !previewSteps.value.length) {
    previewFlowConnections.value = []
    return
  }

  const inner = canvas.querySelector('.action-flow-canvas-inner') || canvas
  const scale = clampFlowCanvasZoom(previewCanvasZoom.value)
  const ports = getPreviewPortMap(canvas, '[data-flow-port]', 'flowPort', scale)
  previewFlowCanvasSize.value = {
    width: Math.max(inner.scrollWidth, 1),
    height: Math.max(inner.scrollHeight, 1)
  }
  ensureFlowCanvasBufferedScroll(canvas, scale)
  previewFlowConnections.value = getPreviewConnectionDescriptors()
    .map((descriptor) => {
      const start = ports.get(descriptor.from)
      const end = ports.get(descriptor.to)
      if (!start || !end) return null
      return {
        ...descriptor,
        path: previewConnectionPath(start, end),
        labelStyle: previewConnectionLabelStyle(start, end)
      }
    })
    .filter(Boolean)
}

function measureOverviewFlowConnections() {
  const canvas = overviewCanvasRef.value
  if (
    !canvas ||
    activeEditorTab.value !== 'steps' ||
    !form.value.steps.length
  ) {
    overviewFlowConnections.value = []
    return
  }

  const inner = canvas.querySelector('.action-flow-canvas-inner') || canvas
  const scale = clampFlowCanvasZoom(overviewCanvasZoom.value)
  const ports = getPreviewPortMap(
    canvas,
    '[data-overview-flow-port]',
    'overviewFlowPort',
    scale
  )
  overviewFlowCanvasSize.value = {
    width: Math.max(inner.scrollWidth, 1),
    height: Math.max(inner.scrollHeight, 1)
  }
  ensureFlowCanvasBufferedScroll(canvas, scale)
  overviewFlowConnections.value = getPreviewConnectionDescriptors(
    form.value.steps,
    overviewStepPort,
    overviewBranchPort,
    'overview'
  )
    .map((descriptor) => {
      const start = ports.get(descriptor.from)
      const end = ports.get(descriptor.to)
      if (!start || !end) return null
      return {
        ...descriptor,
        path: previewConnectionPath(start, end),
        labelStyle: previewConnectionLabelStyle(start, end)
      }
    })
    .filter(Boolean)
}

function scheduleOverviewFlowMeasure() {
  if (overviewMeasureTimer) {
    window.clearTimeout(overviewMeasureTimer)
  }
  overviewMeasureTimer = window.setTimeout(() => {
    overviewMeasureTimer = null
    nextTick(() => {
      measureOverviewFlowConnections()
    })
  }, 24)
}

function schedulePreviewFlowMeasure() {
  if (previewMeasureTimer) {
    window.clearTimeout(previewMeasureTimer)
  }
  previewMeasureTimer = window.setTimeout(() => {
    previewMeasureTimer = null
    nextTick(() => {
      measurePreviewFlowConnections()
    })
  }, 24)
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
  filteredGitLabProjectsForStep(step).forEach((project) => {
    selected.add(Number(project.id))
  })
  step.config.project_ids = [...selected]
}

function selectAllGitLabProjects(step) {
  if (!step?.config?.project_ids) return
  const selected = new Set(step.config.project_ids.map((id) => Number(id)))
  filteredGitLabProjectsForStep(step).forEach((project) => {
    selected.add(Number(project.id))
  })
  step.config.project_ids = [...selected]
}

function clearActionProjects(step) {
  if (!step?.config) return
  step.config.project_ids = []
}

function toggleActionProjectLabelFilter(labelId) {
  const normalizedId = Number(labelId)
  if (actionProjectLabelFilter.value.includes(normalizedId)) {
    actionProjectLabelFilter.value = actionProjectLabelFilter.value.filter(
      (id) => id !== normalizedId
    )
  } else {
    actionProjectLabelFilter.value = [
      ...actionProjectLabelFilter.value,
      normalizedId
    ]
  }
}

function clearActionProjectLabelFilter() {
  actionProjectLabelFilter.value = []
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

function stepMapSummary(step) {
  if (step.action_type !== 'conditional_branch') {
    return previewStepSummary(step)
  }
  return `${t('adminPages.actionTemplates.branch.caseCount', {
    count: previewBranchCases(step).length
  })} · ${branchMatchModeText(step)} · ${t(
    'adminPages.actionTemplates.branch.defaultSkip'
  )}`
}

onMounted(() => {
  loadTemplates()
  loadOptions()
  window.addEventListener('resize', scheduleOverviewFlowMeasure)
  window.addEventListener('resize', schedulePreviewFlowMeasure)
  window.addEventListener('resize', scheduleFlowEditorMeasure)
  overviewResizeObserver = new ResizeObserver(() => {
    scheduleOverviewFlowMeasure()
  })
  previewResizeObserver = new ResizeObserver(() => {
    schedulePreviewFlowMeasure()
  })
  flowEditorResizeObserver = new ResizeObserver(() => {
    scheduleFlowEditorMeasure()
  })
  if (previewCanvasRef.value) {
    previewResizeObserver.observe(previewCanvasRef.value)
  }
  if (overviewCanvasRef.value) {
    overviewResizeObserver.observe(overviewCanvasRef.value)
  }
  if (flowEditorCanvasRef.value) {
    flowEditorResizeObserver.observe(flowEditorCanvasRef.value)
  }
})

watch(activeEditorTab, (tab) => {
  if (tab !== 'steps') return
  nextTick(() => {
    if (overviewResizeObserver && overviewCanvasRef.value) {
      overviewResizeObserver.observe(overviewCanvasRef.value)
    }
    scheduleOverviewFlowMeasure()
  })
})

watch(
  () => form.value.steps,
  () => {
    scheduleOverviewFlowMeasure()
  },
  { deep: true }
)

watch(showPreviewModal, (isOpen) => {
  if (!isOpen) return
  nextTick(() => {
    if (previewResizeObserver && previewCanvasRef.value) {
      previewResizeObserver.observe(previewCanvasRef.value)
    }
    schedulePreviewFlowMeasure()
  })
})

watch(
  previewSteps,
  () => {
    schedulePreviewFlowMeasure()
  },
  { deep: true }
)

watch(flowEditorOpen, (isOpen) => {
  if (!isOpen) return
  nextTick(() => {
    if (flowEditorResizeObserver && flowEditorCanvasRef.value) {
      flowEditorResizeObserver.observe(flowEditorCanvasRef.value)
    }
    scheduleFlowEditorMeasure()
  })
})

watch(
  () => form.value.steps,
  () => {
    scheduleFlowEditorMeasure()
  },
  { deep: true }
)

onBeforeUnmount(() => {
  window.removeEventListener('resize', scheduleOverviewFlowMeasure)
  window.removeEventListener('resize', schedulePreviewFlowMeasure)
  window.removeEventListener('resize', scheduleFlowEditorMeasure)
  if (overviewResizeObserver) {
    overviewResizeObserver.disconnect()
  }
  if (previewResizeObserver) {
    previewResizeObserver.disconnect()
  }
  if (flowEditorResizeObserver) {
    flowEditorResizeObserver.disconnect()
  }
  if (previewMeasureTimer) {
    window.clearTimeout(previewMeasureTimer)
  }
  if (overviewMeasureTimer) {
    window.clearTimeout(overviewMeasureTimer)
  }
  if (flowEditorMeasureTimer) {
    window.clearTimeout(flowEditorMeasureTimer)
  }
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
  gap: 18px;
  border: 1px solid #e2e8f0;
  border-radius: 16px;
  background: #ffffff;
  padding: 18px 20px;
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
  position: relative;
  display: block;
  height: clamp(360px, 46vh, 560px);
  min-height: 360px;
  overflow: auto;
  border: 1px solid #e8edf5;
  border-radius: 16px;
  background:
    radial-gradient(
      circle at 1px 1px,
      rgba(148, 163, 184, 0.24) 1px,
      transparent 0
    ),
    #fbfdff;
  background-size: 28px 28px;
  cursor: grab;
  padding: 0;
  scrollbar-width: thin;
}

.action-flow-canvas.dragging {
  cursor: grabbing;
  user-select: none;
}

.action-flow-canvas--interactive .action-flow-node,
.action-flow-canvas--interactive .action-flow-connection-label {
  cursor: inherit;
}

.action-flow-canvas-tools {
  position: absolute;
  top: 12px;
  right: 12px;
  z-index: 12;
  display: flex;
  width: fit-content;
  align-items: center;
  gap: 4px;
  border: 1px solid #dbe5f0;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.94);
  box-shadow: 0 14px 30px rgba(15, 23, 42, 0.1);
  padding: 4px;
}

.action-flow-canvas-tools button {
  display: inline-grid;
  min-width: 30px;
  height: 30px;
  place-items: center;
  border-radius: 9px;
  color: #334155;
  font-size: 14px;
  font-weight: 900;
}

.action-flow-canvas-tools button:hover {
  background: #eef4fb;
}

.action-flow-canvas-tools .action-flow-canvas-zoom-value {
  min-width: 50px;
  color: #64748b;
  font-size: 12px;
}

.action-flow-canvas-tools .action-flow-canvas-fit {
  min-width: 44px;
  color: #475569;
  font-size: 12px;
}

.action-flow-canvas-viewport {
  position: relative;
  min-width: 100%;
  min-height: 100%;
}

.action-flow-canvas-inner {
  position: absolute;
  top: 0;
  left: 0;
  display: flex;
  min-width: max-content;
  min-height: 300px;
  align-items: center;
  gap: 20px;
  padding: 54px 42px 52px;
  padding-right: 402px;
  padding-bottom: 412px;
  transform-origin: top left;
}

.action-flow-connection-layer {
  position: absolute;
  top: 0;
  left: 0;
  z-index: 0;
  overflow: visible;
  pointer-events: none;
}

.action-flow-connection-path {
  fill: none;
  stroke: rgba(203, 213, 225, 0.78);
  stroke-linecap: round;
  stroke-width: 2.25px;
}

.action-flow-connection-labels {
  position: absolute;
  top: 0;
  left: 0;
  z-index: 1;
  pointer-events: none;
}

.action-flow-connection-label {
  position: absolute;
  display: inline-flex;
  max-width: 172px;
  overflow: hidden;
  border: 1px solid #e8eef6;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.94);
  color: #94a3b8;
  font-family:
    ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono',
    'Courier New', monospace;
  font-size: 10px;
  font-weight: 800;
  line-height: 1.35;
  padding: 7px 10px;
  text-overflow: ellipsis;
  transform: translate(-50%, -50%);
  white-space: nowrap;
}

.action-flow-node {
  position: relative;
  z-index: 2;
  display: flex;
  min-width: 250px;
  gap: 0;
  align-items: center;
}

.action-flow-port {
  position: absolute;
  z-index: 3;
  width: 8px;
  height: 8px;
  border-radius: 999px;
  pointer-events: none;
}

.action-flow-port--in {
  top: 50%;
  left: 0;
  transform: translate(-50%, -50%);
}

.action-flow-port--out {
  top: 50%;
  right: 0;
  transform: translate(50%, -50%);
}

.action-flow-port--branch-in {
  top: 50%;
  left: 0;
  transform: translate(-50%, -50%);
}

.action-flow-port--branch-out {
  top: 50%;
  right: 0;
  transform: translate(50%, -50%);
}

.action-flow-node-index {
  position: absolute;
  top: 0;
  left: 28px;
  z-index: 4;
  display: inline-flex;
  min-width: 46px;
  height: 26px;
  align-items: center;
  justify-content: center;
  border-radius: 999px;
  background: #101827;
  color: #ffffff;
  font-size: 12px;
  font-weight: 900;
  letter-spacing: 0.12em;
  transform: translateY(-50%);
  box-shadow: 0 8px 18px rgba(15, 23, 42, 0.18);
}

.action-flow-node-body {
  position: relative;
  min-height: 168px;
  flex: 1;
  border: 1px solid #e1e8f2;
  border-radius: 16px;
  background: #ffffff;
  box-shadow: 0 2px 6px rgba(15, 23, 42, 0.04);
  padding: 22px 20px;
}

.action-flow-node-body::after {
  position: absolute;
  top: 22px;
  right: 22px;
  display: inline-flex;
  width: 18px;
  height: 18px;
  align-items: center;
  justify-content: center;
  border: 2px solid #10b981;
  border-radius: 999px;
  color: #10b981;
  content: '✓';
  font-size: 11px;
  font-weight: 900;
}

.action-flow-node-type {
  display: inline-flex;
  width: fit-content;
  align-items: center;
  border-radius: 999px;
  background: #f1f5f9;
  color: #64748b;
  font-size: 12px;
  font-weight: 900;
  letter-spacing: 0;
  line-height: 1;
  padding: 6px 10px;
  text-transform: none;
}

.action-flow-node-body h4 {
  margin: 14px 0 0;
  color: #0f172a;
  font-size: 20px;
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
  background: #059669;
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
  background: #101827;
}

.action-flow-node--conditional_branch .action-flow-node-index {
  background: #21194f;
}

.action-flow-node--branch-preview {
  min-width: 880px;
  justify-content: center;
  padding: 0 180px;
}

.action-flow-node--branch-preview .action-flow-node-body {
  width: 520px;
  flex: 0 0 520px;
  border-color: #10b981;
  min-height: 0;
  background: rgba(255, 255, 255, 0.98);
  box-shadow: none;
  padding: 30px 34px 26px;
}

.action-flow-node--branch-preview .action-flow-node-index {
  left: 50%;
  transform: translate(-50%, -50%);
}

.action-flow-node--branch-preview .action-flow-node-type {
  background: #eef2ff;
  color: #4f46e5;
}

.action-flow-node--branch-preview .action-flow-policy {
  margin-right: 38px;
}

.action-flow-node--jenkins_trigger .action-flow-node-body {
  border-color: #10b981;
  box-shadow: none;
}

.action-flow-node--jenkins_trigger .action-flow-node-body::before,
.action-flow-node--manual_approval .action-flow-node-body::before {
  position: absolute;
  top: 18px;
  bottom: 18px;
  left: 0;
  width: 7px;
  border-radius: 999px;
  background: #10b981;
  content: '';
}

.action-flow-node--manual_approval .action-flow-node-body::before {
  background: #cbd5e1;
}

.action-flow-node--manual_approval .action-flow-node-body::after {
  display: none;
}

.action-flow-node--manual_approval .action-flow-node-body {
  border-color: #dbe5f0;
}

.action-flow-branch-top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.action-flow-branch-diagram {
  position: relative;
  display: block;
  margin-top: 18px;
}

.action-flow-branch-split,
.action-flow-branch-merge {
  display: none;
}

.action-flow-branch-split::before,
.action-flow-branch-merge::before {
  position: absolute;
  top: 24px;
  bottom: 24px;
  left: 50%;
  width: 1px;
  border-radius: 999px;
  background: #b8c7d9;
  content: '';
  transform: translateX(-50%);
}

.action-flow-branch-split::after,
.action-flow-branch-merge::after {
  position: absolute;
  top: 50%;
  width: 14px;
  height: 1px;
  border-radius: 999px;
  background: #b8c7d9;
  content: '';
  transform: translateY(-50%);
}

.action-flow-branch-split::after {
  right: 0;
}

.action-flow-branch-merge::after {
  left: 0;
}

.action-flow-branch-lanes {
  display: grid;
  gap: 14px;
}

.action-flow-branch-lane {
  position: relative;
  display: grid;
  gap: 16px;
  min-height: 96px;
  border: 1px solid #edf2f7;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.72);
  box-shadow: none;
  padding: 16px;
}

.action-flow-branch-lane::before,
.action-flow-branch-lane::after {
  display: none;
}

.action-flow-branch-condition {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: center;
  min-width: 0;
}

.action-flow-branch-title {
  display: inline-flex;
  min-width: 0;
  gap: 10px;
  align-items: center;
}

.action-flow-branch-number {
  display: inline-flex;
  width: 22px;
  height: 22px;
  flex: 0 0 22px;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
  background: #eef2f7;
  color: #94a3b8;
  font-size: 12px;
  font-weight: 900;
}

.action-flow-branch-title strong {
  display: block;
  min-width: 0;
  overflow: hidden;
  color: #64748b;
  font-size: 13px;
  font-weight: 900;
  line-height: 1.35;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.action-flow-branch-rule-chip {
  display: inline-flex;
  max-width: 168px;
  flex: 0 1 auto;
  overflow: hidden;
  border: 1px solid #edf2f7;
  border-radius: 6px;
  background: #f8fafc;
  color: #94a3b8;
  font-size: 11px;
  font-weight: 800;
  line-height: 1.2;
  padding: 5px 10px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.action-flow-branch-step-list {
  display: flex;
  min-width: 0;
  gap: 0;
  align-items: center;
  overflow-x: auto;
  border-radius: 0;
  background: transparent;
  padding: 0;
  scrollbar-width: thin;
}

.action-flow-branch-step-item {
  display: inline-flex;
  flex: 0 0 auto;
  align-items: center;
}

.action-flow-branch-step {
  display: inline-flex;
  max-width: 140px;
  align-items: center;
  overflow: hidden;
  border: 1px solid #d8f3e8;
  border-radius: 10px;
  background: #f0fdf7;
  color: #047857;
  font-size: 12px;
  font-weight: 800;
  line-height: 1.3;
  padding: 8px 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.action-flow-branch-step-arrow {
  display: inline-flex;
  width: 24px;
  flex: 0 0 24px;
  align-items: center;
  justify-content: center;
  color: #94a3b8;
  font-size: 14px;
  font-weight: 900;
}

.action-flow-branch-step--empty {
  background: #f1f5f9;
  color: #64748b;
}

.action-flow-branch-default {
  display: inline-flex;
  width: fit-content;
  margin-top: 12px;
  border-radius: 999px;
  background: #f1f5f9;
  color: #475569;
  font-size: 12px;
  font-weight: 800;
  padding: 6px 9px;
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
  align-items: flex-start;
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

.action-step-map {
  display: grid;
  gap: 0;
  margin: 0;
  padding: 0;
  list-style: none;
}

.action-step-map-node {
  position: relative;
  display: grid;
  grid-template-columns: 42px minmax(0, 1fr);
  gap: 12px;
  padding: 0 0 18px;
}

.action-step-map-node::before {
  position: absolute;
  top: 38px;
  bottom: 0;
  left: 20px;
  width: 2px;
  border-radius: 999px;
  background: #dbe5f0;
  content: '';
}

.action-step-map-node:last-child::before {
  display: none;
}

.action-step-map-index {
  position: relative;
  z-index: 1;
  display: grid;
  width: 42px;
  height: 42px;
  place-items: center;
  border-radius: 14px;
  background: #101827;
  color: #ffffff;
  font-size: 12px;
  font-weight: 900;
  letter-spacing: 0.08em;
}

.action-step-map-node--jenkins_trigger .action-step-map-index {
  background: #047857;
}

.action-step-map-node--conditional_branch .action-step-map-index {
  background: #4338ca;
}

.action-step-map-card {
  display: grid;
  gap: 10px;
  min-width: 0;
  border: 1px solid #e4ebf3;
  border-radius: 14px;
  background: #ffffff;
  padding: 14px 16px;
}

.action-step-map-head {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: 10px;
}

.action-step-map-head span {
  flex: 0 0 auto;
  border-radius: 999px;
  background: #eef4fb;
  color: #64748b;
  font-size: 12px;
  font-weight: 900;
  padding: 6px 9px;
}

.action-step-map-head strong {
  min-width: 0;
  overflow: hidden;
  color: #0f172a;
  font-size: 15px;
  font-weight: 900;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.action-step-map-card p {
  margin: 0;
  color: #64748b;
  font-size: 13px;
  font-weight: 700;
}

.action-step-map-branches {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.action-step-map-branches span,
.action-step-map-branches em {
  display: inline-flex;
  max-width: 190px;
  overflow: hidden;
  border-radius: 8px;
  background: #f1f5f9;
  color: #64748b;
  font-family:
    ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono',
    'Courier New', monospace;
  font-size: 11px;
  font-style: normal;
  font-weight: 800;
  padding: 6px 8px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.action-flow-canvas--editor {
  height: clamp(260px, 36vh, 460px);
  min-height: 260px;
  border: 1px solid #dbe9f7;
  border-radius: 14px;
  background:
    radial-gradient(
      circle at 1px 1px,
      rgba(172, 187, 205, 0.32) 1px,
      transparent 0
    ),
    #f8fbff;
  background-size: 28px 28px;
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

.action-flow-node--preview-only .action-flow-node-body {
  box-shadow: none;
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
  grid-template-columns: 68px minmax(0, 1fr);
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
  border-color: #c7d7e8;
}

.action-flow-node--editable:not(.action-flow-node--preview-only):hover
  .action-flow-node-body,
.action-flow-node--editable:not(.action-flow-node--preview-only).active
  .action-flow-node-body {
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

.action-project-picker-toolbar.compact {
  grid-template-columns: 1fr;
  margin-bottom: 0;
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

.action-project-card-labels {
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
  margin-top: 8px;
}

.action-project-card-labels i {
  max-width: 100%;
  overflow: hidden;
  border: 1px solid #bfdbfe;
  border-radius: 999px;
  background: #eff6ff;
  color: #2563eb;
  font-size: 11px;
  font-style: normal;
  font-weight: 800;
  line-height: 1.2;
  padding: 3px 7px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.action-project-label-filter {
  display: grid;
  gap: 8px;
  border: 1px solid #e2e8f0;
  border-radius: 14px;
  background: #ffffff;
  padding: 10px;
}

.action-project-label-filter-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.action-project-label-filter-head span {
  color: #64748b;
  font-size: 12px;
  font-weight: 900;
}

.action-project-label-filter-head button,
.action-project-label-chips button {
  border: 0;
  background: transparent;
  color: #2563eb;
  font-size: 12px;
  font-weight: 900;
}

.action-project-label-chips {
  display: flex;
  max-height: 74px;
  flex-wrap: wrap;
  gap: 6px;
  overflow: auto;
}

.action-project-label-chips button {
  border: 1px solid #dbe5f0;
  border-radius: 999px;
  background: #f8fafc;
  color: #475569;
  line-height: 1.2;
  padding: 6px 10px;
}

.action-project-label-chips button:hover,
.action-project-label-chips button.active {
  border-color: #93c5fd;
  background: #dbeafe;
  color: #1d4ed8;
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

.action-pane-heading-actions {
  display: inline-flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 8px;
}

.action-flow-editor-overlay {
  position: fixed;
  inset: 0;
  z-index: 120;
  display: grid;
  width: 100vw;
  height: 100vh;
  grid-template-columns: minmax(0, 1fr) clamp(460px, 34vw, 540px);
  grid-template-rows: minmax(0, 1fr);
  overflow: hidden;
  background: #f5f8fb;
}

.action-flow-editor-overlay.inspector-closed {
  grid-template-columns: minmax(0, 1fr);
}

.action-flow-editor-overlay.inspector-closed .action-flow-editor-stage {
  border-right: 0;
}

.action-flow-editor-stage {
  display: grid;
  min-width: 0;
  min-height: 0;
  grid-template-rows: auto minmax(0, 1fr);
  border-right: 1px solid #dbe5f0;
  background: #fbfdff;
}

.action-flow-editor-topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  border-bottom: 1px solid #dbe5f0;
  background: rgba(255, 255, 255, 0.96);
  padding: 13px 18px;
}

.action-flow-editor-title {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: 10px;
}

.action-flow-editor-title h3 {
  margin: 0;
  overflow: hidden;
  color: #0f172a;
  font-size: 18px;
  font-weight: 900;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.action-flow-editor-toolbar {
  display: inline-flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
}

.action-flow-editor-zoom {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  border: 1px solid #dbe5f0;
  border-radius: 12px;
  background: #ffffff;
  padding: 4px;
}

.action-flow-editor-zoom button {
  display: inline-grid;
  min-width: 32px;
  height: 30px;
  place-items: center;
  border-radius: 9px;
  color: #334155;
  font-size: 12px;
  font-weight: 900;
  padding: 0 8px;
}

.action-flow-editor-zoom button:hover {
  background: #eef4fb;
}

.action-flow-editor-scroll {
  position: relative;
  min-width: 0;
  min-height: 0;
  overflow: auto;
  cursor: grab;
  background:
    radial-gradient(
      circle at 1px 1px,
      rgba(172, 187, 205, 0.32) 1px,
      transparent 0
    ),
    #f8fbff;
  background-size: 26px 26px;
}

.action-flow-editor-scroll.dragging {
  cursor: grabbing;
  user-select: none;
}

.action-flow-editor-canvas {
  position: absolute;
  top: 0;
  left: 0;
  display: flex;
  align-items: center;
  gap: 126px;
  min-width: max-content;
  min-height: 560px;
  padding: 58px 190px 120px;
  transform-origin: top left;
}

.action-flow-editor-svg,
.action-flow-editor-labels {
  position: absolute;
  top: 0;
  left: 0;
  z-index: 0;
  overflow: visible;
  pointer-events: none;
}

.action-flow-editor-svg marker path {
  fill: #c9d8e6;
}

.action-flow-editor-path {
  fill: none;
  stroke: rgba(148, 181, 207, 0.55);
  stroke-linecap: round;
  stroke-width: 1.8px;
}

.action-flow-editor-path.active {
  stroke: rgba(82, 139, 179, 0.58);
}

.action-flow-editor-labels {
  z-index: 1;
}

.action-flow-editor-label {
  position: absolute;
  display: inline-flex;
  max-width: 156px;
  overflow: hidden;
  border: 1px solid rgba(210, 224, 238, 0.82);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.88);
  color: #6f86a0;
  font-family:
    ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono',
    'Courier New', monospace;
  font-size: 10px;
  font-weight: 800;
  line-height: 1.35;
  padding: 4px 7px;
  text-overflow: ellipsis;
  transform: translate(-50%, -50%);
  white-space: nowrap;
}

.action-flow-editor-node {
  position: relative;
  z-index: 2;
  width: 310px;
  min-height: 160px;
  flex: 0 0 310px;
  border: 1px solid #dbe6f1;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.98);
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.05);
  padding: 24px 20px 18px;
  transition:
    border-color 0.16s ease,
    box-shadow 0.16s ease,
    transform 0.16s ease;
}

.action-flow-editor-node:hover {
  transform: translateY(-1px);
}

.action-flow-editor-node.selected,
.action-flow-editor-branch-case.selected,
.action-flow-editor-mini-step.selected {
  border-color: #10b981;
  box-shadow: 0 0 0 3px rgba(16, 185, 129, 0.08);
}

.action-flow-editor-node.branch {
  width: 520px;
  min-height: 540px;
  flex-basis: 520px;
  padding: 28px 22px 22px;
}

.action-flow-editor-port {
  position: absolute;
  z-index: 3;
  width: 8px;
  height: 8px;
  border-radius: 999px;
  pointer-events: none;
}

.action-flow-editor-port--in {
  top: 50%;
  left: 0;
  transform: translate(-50%, -50%);
}

.action-flow-editor-port--out {
  top: 50%;
  right: 0;
  transform: translate(50%, -50%);
}

.action-flow-editor-port--branch-in {
  top: 50%;
  left: 0;
  transform: translate(-50%, -50%);
}

.action-flow-editor-port--branch-out {
  top: 50%;
  right: 0;
  transform: translate(50%, -50%);
}

.action-flow-editor-badge {
  position: absolute;
  top: -17px;
  left: 18px;
  display: inline-flex;
  min-width: 52px;
  height: 34px;
  align-items: center;
  justify-content: center;
  border-radius: 11px;
  background: #101827;
  color: #ffffff;
  font-size: 13px;
  font-weight: 900;
  letter-spacing: 0.06em;
}

.action-flow-editor-badge.green {
  background: #047857;
}

.action-flow-editor-badge.violet {
  background: #4338ca;
}

.action-flow-editor-kind {
  display: inline-flex;
  width: fit-content;
  border-radius: 999px;
  background: #eef2f7;
  color: #64748b;
  font-size: 12px;
  font-weight: 900;
  padding: 7px 10px;
}

.action-flow-editor-node--jenkins_trigger .action-flow-editor-kind {
  background: #ecfdf5;
  color: #047857;
}

.action-flow-editor-node--conditional_branch .action-flow-editor-kind {
  background: #eef2ff;
  color: #4338ca;
}

.action-flow-editor-node h4 {
  margin: 14px 0 0;
  color: #0f172a;
  font-size: 18px;
  font-weight: 900;
}

.action-flow-editor-meta {
  display: grid;
  grid-template-columns: 60px minmax(0, 1fr);
  gap: 8px 12px;
  margin: 12px 0 16px;
}

.action-flow-editor-meta div {
  display: contents;
}

.action-flow-editor-meta dt {
  color: #64748b;
  font-size: 13px;
  font-weight: 800;
}

.action-flow-editor-meta dd {
  min-width: 0;
  margin: 0;
  overflow: hidden;
  color: #334155;
  font-size: 13px;
  font-weight: 800;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.action-flow-editor-policy,
.action-flow-editor-branch-footer em {
  display: inline-flex;
  width: fit-content;
  border: 1px solid #fecdd3;
  border-radius: 8px;
  background: #fff1f2;
  color: #e11d48;
  font-size: 12px;
  font-style: normal;
  font-weight: 900;
  padding: 7px 10px;
}

.action-flow-editor-branch-list {
  display: grid;
  gap: 10px;
  margin-top: 18px;
}

.action-flow-editor-branch-case {
  position: relative;
  border: 1px solid #edf2f7;
  border-radius: 11px;
  background: #fcfdff;
  padding: 12px;
}

.action-flow-editor-branch-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
}

.action-flow-editor-branch-head strong {
  display: inline-flex;
  min-width: 0;
  align-items: center;
  gap: 10px;
  color: #334155;
  font-size: 13px;
  font-weight: 900;
}

.action-flow-editor-branch-head strong span {
  display: grid;
  width: 22px;
  height: 22px;
  flex: 0 0 22px;
  place-items: center;
  border-radius: 999px;
  background: #eef2f7;
  color: #8aa0b8;
  font-size: 12px;
}

.action-flow-editor-branch-head code {
  max-width: 155px;
  overflow: hidden;
  border: 1px solid #eaf0f7;
  border-radius: 7px;
  background: #f8fafc;
  color: #8297ae;
  font-size: 11px;
  font-weight: 850;
  padding: 5px 7px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.action-flow-editor-mini-steps {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: center;
  margin-top: 10px;
}

.action-flow-editor-mini-step {
  display: inline-flex;
  align-items: center;
  border: 1px solid #bbf7d0;
  border-radius: 8px;
  background: #f0fdf7;
  color: #047857;
  font-size: 12px;
  font-weight: 900;
  padding: 6px 9px;
}

.action-flow-editor-mini-step.muted {
  background: #f1f5f9;
  color: #64748b;
}

.action-flow-editor-mini-arrow {
  color: #a8b7c8;
  font-weight: 900;
}

.action-flow-editor-branch-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  border-top: 1px solid #eaf0f7;
  margin-top: 14px;
  padding-top: 12px;
}

.action-flow-editor-branch-footer span {
  border-radius: 8px;
  background: #f1f5f9;
  color: #506986;
  font-size: 12px;
  font-weight: 900;
  padding: 6px 9px;
}

.action-flow-editor-inspector {
  display: grid;
  min-width: 0;
  grid-template-rows: auto minmax(0, 1fr) auto;
  background: #ffffff;
}

.action-flow-inspector-head {
  border-bottom: 1px solid #dbe5f0;
  padding: 19px 22px 17px;
}

.action-flow-inspector-head h3 {
  margin: 0;
  color: #0f172a;
  font-size: 18px;
  font-weight: 900;
}

.action-flow-inspector-head p {
  margin: 6px 0 0;
  color: #64748b;
  font-size: 13px;
  font-weight: 700;
}

.action-flow-inspector-body {
  display: grid;
  align-content: start;
  gap: 20px;
  min-height: 0;
  overflow-y: auto;
  padding: 20px 24px 36px;
}

.action-flow-inspector-section {
  display: grid;
  gap: 14px;
}

.action-flow-inspector-section + .action-flow-inspector-section {
  border-top: 1px solid #eaf0f7;
  padding-top: 18px;
}

.action-flow-inspector-section > strong,
.action-flow-inspector-section-head > strong {
  color: #0f172a;
  font-size: 14px;
  font-weight: 900;
}

.action-flow-inspector-section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.action-flow-inspector-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 12px;
}

.action-flow-editor-inspector .action-field input,
.action-flow-editor-inspector .action-field select,
.action-flow-editor-inspector .action-field textarea {
  min-height: 46px;
  border-radius: 14px;
}

.action-flow-editor-inspector .action-checkbox-line {
  align-items: flex-start;
  border: 1px solid #e2e8f0;
  border-radius: 14px;
  background: #f8fafc;
  line-height: 1.45;
  padding: 10px 12px;
}

.action-flow-param-card,
.action-flow-branch-config-list,
.action-flow-nested-config-list {
  display: grid;
  gap: 10px;
}

.action-flow-param-table {
  display: grid;
  gap: 10px;
  overflow: visible;
  border: 0;
  background: transparent;
}

.action-flow-param-table .action-param-row {
  grid-template-columns: 1fr;
  align-items: start;
  gap: 10px;
  border: 1px solid #e2e8f0;
  border-radius: 14px;
  background: #ffffff;
  padding: 14px;
}

.action-flow-param-table .action-param-name {
  min-width: 0;
}

.action-flow-param-table .action-param-name small {
  overflow-wrap: anywhere;
}

.action-flow-param-table .action-param-row input,
.action-flow-param-table .action-param-row select,
.action-flow-param-table .action-param-readonly-mode {
  min-height: 42px;
  border-radius: 12px;
}

.action-flow-project-picker {
  display: grid;
  gap: 12px;
  border-top: 1px solid #eaf0f7;
  padding-top: 14px;
}

.action-flow-project-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.action-flow-project-head strong,
.action-flow-project-head span {
  display: block;
}

.action-flow-project-head strong {
  color: #0f172a;
  font-size: 14px;
  font-weight: 900;
}

.action-flow-project-head span {
  margin-top: 4px;
  color: #64748b;
  font-size: 12px;
  font-weight: 800;
}

.action-flow-project-picker .action-inline-switch {
  width: 100%;
  border: 1px solid #e2e8f0;
  border-radius: 14px;
  background: #f8fafc;
  padding: 10px 12px;
}

.action-flow-project-grid {
  max-height: 220px;
  grid-template-columns: 1fr;
  border-radius: 14px;
  padding: 8px;
}

.action-flow-project-grid .action-project-card {
  border-radius: 12px;
  padding: 10px;
}

.action-flow-branch-config-list button,
.action-flow-nested-config-list button {
  display: grid;
  gap: 4px;
  width: 100%;
  border: 1px solid #dbe5f0;
  border-radius: 12px;
  background: #f8fafc;
  padding: 11px 12px;
  text-align: left;
}

.action-flow-branch-config-list button.active,
.action-flow-branch-config-list button:hover,
.action-flow-nested-config-list button:hover {
  border-color: #bfdbfe;
  background: #f8fbff;
}

.action-flow-branch-config-list strong,
.action-flow-nested-config-list strong {
  color: #0f172a;
  font-size: 13px;
  font-weight: 900;
}

.action-flow-branch-config-list span,
.action-flow-nested-config-list span {
  overflow: hidden;
  color: #64748b;
  font-size: 12px;
  font-weight: 800;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.action-flow-inspector-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  border-top: 1px solid #dbe5f0;
  padding: 15px 22px;
}

@media (max-width: 900px) {
  .action-flow-editor-overlay {
    grid-template-columns: 1fr;
    grid-template-rows: minmax(0, 1fr) minmax(320px, 42vh);
  }

  .action-flow-editor-stage {
    border-right: 0;
    border-bottom: 1px solid #dbe5f0;
  }

  .action-flow-editor-topbar {
    align-items: stretch;
    flex-direction: column;
  }

  .action-flow-editor-toolbar {
    justify-content: flex-start;
  }

  .action-flow-editor-inspector {
    min-height: 0;
  }

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

@media (prefers-reduced-motion: reduce) {
  .action-flow-editor-node,
  .action-flow-editor-node:hover {
    transform: none;
    transition: none;
  }
}
</style>

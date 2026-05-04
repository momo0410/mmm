<template>
  <div class="payloader-page">
    <PayloaderToolbar>
      <template #left>
        <div class="payloader-toolbar-left">
          <button 
            v-if="state.viewMode === 'detail'"
            class="payloader-back-btn"
            @click="goBack"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M15 18l-6-6 6-6"></path>
            </svg>
            返回
          </button>
          <template v-else>
            <div class="payloader-dropdowns">
              <div class="payloader-dropdown">
                <button 
                  class="payloader-dropdown-btn"
                  @click="toggleViewDropdown"
                >
                  {{ getViewLabel(state.currentView) }}
                  <svg class="payloader-dropdown-arrow" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M6 9l6 6 6-6"></path>
                  </svg>
                </button>
                <div v-if="showViewDropdown" class="payloader-dropdown-menu">
                  <button 
                    v-for="view in views" 
                    :key="view.id"
                    :class="['payloader-dropdown-item', { active: state.currentView === view.id }]"
                    @click="selectView(view.id)"
                  >
                    {{ view.label }}
                  </button>
                </div>
              </div>

              <div v-if="state.currentView !== 'tools'" class="payloader-dropdown">
                <button 
                  class="payloader-dropdown-btn"
                  @click="toggleCategoryDropdown"
                >
                  {{ getSelectedCategoryLabel() }}
                  <svg class="payloader-dropdown-arrow" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M6 9l6 6 6-6"></path>
                  </svg>
                </button>
                <div v-if="showCategoryDropdown" class="payloader-dropdown-menu payloader-dropdown-menu--large">
                  <button 
                    v-for="cat in categories" 
                    :key="cat.id"
                    :class="['payloader-dropdown-item', { active: state.selectedCategory === cat.id }]"
                    @click="selectCategoryWrapper(cat.id)"
                  >
                    {{ getText(cat.label) }}
                  </button>
                </div>
              </div>

              <button
                class="payloader-btn payloader-btn--tool"
                @click="selectView('tools')"
                :class="{ active: state.currentView === 'tools' }"
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"></path>
                </svg>
                工具命令
              </button>

              <button
                class="payloader-btn payloader-btn--tool"
                @click="selectView('encoding')"
                :class="{ active: state.currentView === 'encoding' }"
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <polyline points="16 18 22 12 16 6"></polyline>
                  <polyline points="8 6 2 12 8 18"></polyline>
                </svg>
                编解码
              </button>
            </div>
          </template>
        </div>
      </template>
      <template #right>
        <div v-if="state.viewMode === 'list'" class="payloader-search-box">
          <svg class="payloader-search-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="11" cy="11" r="8"></circle>
            <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
          </svg>
          <input 
            type="text" 
            class="payloader-search-input" 
            placeholder="搜索 payload... (Ctrl+F)"
            :value="state.searchQuery"
            @input="setSearchQuery(($event.target as HTMLInputElement).value)"
          />
        </div>
        <button
          v-if="state.viewMode === 'list'"
          class="payloader-btn payloader-btn--history"
          @click="showHistoryModal = true; loadHistory()"
          title="渗透历史"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M12 20v-6M6 20V10M18 20V4"></path>
          </svg>
          历史
        </button>
        <button
          v-if="state.viewMode === 'list'"
          :class="['payloader-btn', 'payloader-btn--pentest', { 'is-running': agentRunning }]"
          @click="handlePentestEntry"
          :title="agentRunning ? `继续查看任务：${pentestTarget || '当前目标'}` : '智能分析'"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M12 2L2 7l10 5 10-5-10-5z"></path>
            <path d="M2 17l10 5 10-5"></path>
            <path d="M2 12l10 5 10-5"></path>
          </svg>
          {{ agentRunning ? '继续任务' : '智能分析' }}
          <span v-if="agentRunning" class="payloader-btn-running-badge">
            <span class="payloader-btn-running-dot"></span>
            运行中
          </span>
        </button>
        <button
          v-if="state.viewMode === 'list'"
          class="payloader-btn payloader-btn--tool"
          @click="openSkillsManager"
          title="skills管理"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M12 3l7 4v10l-7 4-7-4V7l7-4z"></path>
            <path d="M9 12l2 2 4-4"></path>
          </svg>
          skills管理
        </button>
        <button
          v-if="state.viewMode === 'list'"
          class="payloader-btn payloader-btn--tool"
          @click="openKnowledgeBaseManager"
          title="本地知识库管理"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"></path>
            <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 0 4 24V4.5A2.5 2.5 0 0 1 6.5 2z"></path>
          </svg>
          本地知识库管理
        </button>
        <button 
          v-if="state.viewMode === 'list'"
          class="page-refresh-btn payloader-refresh-btn" 
          @click="refresh" 
          :disabled="isLoading"
          title="刷新"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" :class="{ 'spinning': isLoading }">
            <path d="M23 4v6h-6"></path>
            <path d="M1 20v-6h6"></path>
            <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"></path>
          </svg>
          <span>刷新</span>
        </button>
      </template>
    </PayloaderToolbar>

    <PayloaderContent>
      <!-- Agent 启动确认弹窗 -->
      <div v-if="showPentestModal" class="payloader-modal-overlay" @click.self="closePentestModal">
        <div class="payloader-modal">
          <div class="payloader-modal-header">
            <h3>智能分析</h3>
            <button class="payloader-modal-close" @click="closePentestModal">&times;</button>
          </div>
          <div class="payloader-modal-body">
            <p class="payloader-modal-desc">请输入要检测的目标 IP 地址或域名，系统会按以下 5 个阶段执行自动化安全验证流程。</p>
            <div class="payloader-modal-input-group">
              <label class="payloader-modal-label" for="payloader-pentest-target">目标 IP / 域名</label>
              <input
                id="payloader-pentest-target"
                v-model="pentestTarget"
                class="payloader-modal-input"
                type="text"
                placeholder="例如: 192.168.1.10 或 example.com"
                autocomplete="off"
                spellcheck="false"
                @keyup.enter="startHostAgent"
              />
              <p class="payloader-modal-helper">仅用于你已授权的目标资产。支持输入 IP 地址或域名。</p>
            </div>
            <div class="payloader-modal-input-group payloader-modal-input-group--mode">
              <label class="payloader-modal-label">执行模式</label>
              <div class="payloader-mode-toggle" role="radiogroup" aria-label="渗透任务执行模式">
                <button
                  type="button"
                  :class="['payloader-mode-toggle-btn', { active: pentestExecutionMode === 'serial' }]"
                  @click="setPentestExecutionMode('serial')"
                >
                  串行
                </button>
                <button
                  type="button"
                  :class="['payloader-mode-toggle-btn', { active: pentestExecutionMode === 'parallel' }]"
                  @click="setPentestExecutionMode('parallel')"
                >
                  并行
                </button>
              </div>
            </div>
            <div v-if="pentestModalError" class="payloader-modal-error">{{ pentestModalError }}</div>
          </div>
          <div class="payloader-modal-footer">
            <button class="payloader-btn payloader-btn--secondary" @click="closePentestModal">取消</button>
            <button
              class="payloader-btn payloader-btn--primary"
              :disabled="agentRunning || !normalizedPentestTarget"
              @click="startHostAgent"
            >
              {{ agentRunning ? '运行中...' : '开始检测' }}
            </button>
          </div>
        </div>
      </div>

      <!-- Agent 结果弹窗 -->
      <div v-if="showResultModal" class="payloader-modal-overlay" @click.self="requestCloseResultModal">
        <div class="payloader-modal payloader-modal--result">
          <div class="payloader-modal-header">
            <h3>渗透结果分析</h3>
            <div class="payloader-modal-header-actions">
              <button class="payloader-modal-header-btn" :disabled="!currentTaskId" @click="openLogModal()">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                  <polyline points="14 2 14 8 20 8"></polyline>
                  <line x1="16" y1="13" x2="8" y2="13"></line>
                  <line x1="16" y1="17" x2="8" y2="17"></line>
                  <polyline points="10 9 9 9 8 9"></polyline>
                </svg>
                日志
              </button>
              <button class="payloader-modal-close" title="关闭" @click="requestCloseResultModal">&times;</button>
            </div>
          </div>
          <div class="payloader-modal-body payloader-modal-body--scroll">
            <!-- 运行中 -->
            <div v-if="agentRunning" class="payloader-agent-running">
              <div class="payloader-agent-running-header">
                <div class="payloader-agent-running-spinner"></div>
                <div class="payloader-agent-running-header-text">
                  <p class="payloader-agent-running-text">正在对 {{ pentestTarget || '目标资产' }} 执行智能分析...</p>
                  <p class="payloader-agent-running-sub">
                    <span class="payloader-agent-phase-badge">{{ getPhaseLabel(agentResult?.phase) }}</span>
                    <span v-if="agentResult?.actions_count" class="payloader-agent-round-info">第 {{ agentResult.actions_count }} 步</span>
                    <span class="payloader-agent-pulse"></span>
                  </p>
                </div>
              </div>
              <div v-if="agentResult" class="payloader-agent-live-panel">
                <div class="payloader-agent-live-stats">
                  <div class="payloader-agent-live-stat">
                    <span class="payloader-agent-live-label">当前阶段</span>
                    <span class="payloader-agent-live-value">{{ getPhaseLabel(agentResult.phase) }}</span>
                  </div>
                  <div class="payloader-agent-live-stat">
                    <span class="payloader-agent-live-label">已执行动作</span>
                    <span class="payloader-agent-live-value">{{ agentResult.actions_count || 0 }} 步</span>
                  </div>
                  <div class="payloader-agent-live-stat">
                    <span class="payloader-agent-live-label">资产发现</span>
                    <span class="payloader-agent-live-value">{{ agentResult.findings_count || 0 }} 项</span>
                  </div>
                  <div class="payloader-agent-live-stat">
                    <span class="payloader-agent-live-label">漏洞发现</span>
                    <span class="payloader-agent-live-value">{{ agentResult.vuln_count || 0 }} 项</span>
                  </div>
                </div>
                <div v-if="currentActionSummary" class="payloader-agent-current-action">
                  <span class="payloader-agent-current-action-dot"></span>
                  <span class="payloader-agent-current-action-text">{{ currentActionSummary }}</span>
                  <span v-if="currentActionElapsed" class="payloader-agent-current-action-elapsed">{{ currentActionElapsed }}</span>
                </div>
                <pre v-if="currentPlanningStream" class="payloader-agent-planning-stream">{{ currentPlanningStream }}</pre>
                <div class="payloader-agent-live-log payloader-agent-live-log--compact">
                  <div class="payloader-agent-live-log-header">
                    <h4>执行摘要</h4>
                    <span>{{ compactActionItems.length }} / {{ (agentResult.actions || []).length }} 条</span>
                  </div>
                  <div class="payloader-agent-log-hint">详细参数和完整输出请点击右上角“日志”查看。</div>
                  <div v-if="compactActionItems.length > 0" class="payloader-agent-compact-list">
                    <div v-for="(action, idx) in compactActionItems" :key="`${action.time}-${idx}`" class="payloader-agent-compact-item" :class="{ 'payloader-agent-action-running': action.status === 'running' }">
                      <div class="payloader-agent-compact-top">
                        <span class="payloader-agent-action-tool" :class="{ 'payloader-agent-action-tool-active': action.status === 'running' }">{{ formatActionToolLabel(action.tool) }}</span>
                        <span class="payloader-agent-action-time">{{ formatActionTime(action.time) }}</span>
                        <span v-if="action.status === 'running'" class="payloader-agent-action-status-running">执行中</span>
                      </div>
                      <div class="payloader-agent-compact-line">
                        <span class="payloader-agent-action-label">参数</span>
                        <span class="payloader-agent-compact-text">{{ summarizeActionPayload(action.args, '无参数') }}</span>
                      </div>
                      <div class="payloader-agent-compact-line">
                        <span class="payloader-agent-action-label">输出</span>
                        <span class="payloader-agent-compact-text">{{ summarizeActionPayload(action.result, action.status === 'running' ? '等待输出...' : '暂无输出') }}</span>
                      </div>
                    </div>
                  </div>
                  <div v-else class="payloader-agent-action-empty">AI 已启动，正在等待第一条执行记录...</div>
                </div>
              </div>
            </div>

            <!-- 错误 -->
            <div v-else-if="agentError" class="payloader-agent-error">
              <div class="payloader-agent-error-icon">!</div>
              <h4 class="payloader-agent-error-title">渗透检测失败</h4>
              <p class="payloader-agent-error-desc">{{ agentError }}</p>
            </div>

            <!-- 结果 -->
            <div v-else-if="agentResult" class="payloader-agent-result">
              <!-- 状态栏 -->
              <div class="payloader-agent-summary">
                <div class="payloader-agent-summary-header">
                  <h3>阶段化安全验证报告</h3>
                  <span :class="['payloader-agent-status', agentResult.status]">
                    {{ agentResult.status === 'completed' ? '已完成' : agentResult.status === 'failed' ? '失败' : '运行中' }}
                  </span>
                </div>
                <p class="payloader-agent-summary-text">
                  当前阶段：{{ getPhaseLabel(agentResult.final?.phase || agentResult.phase) }}，
                  已执行动作 {{ agentResult.actions_count || 0 }} 步，
                  发现资产 {{ agentResult.findings_count || 0 }} 项，
                  发现漏洞 {{ agentResult.vuln_count || 0 }} 项。
                </p>
              </div>

              <div v-if="agentResult.actions && agentResult.actions.length > 0" class="payloader-agent-section payloader-agent-live-log-section">
                <h4 class="payloader-agent-section-title">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M9 11l3 3L22 4"></path>
                    <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"></path>
                  </svg>
                  AI 执行摘要
                </h4>
                <div class="payloader-agent-log-hint">页面仅展示最近摘要，完整执行过程、参数和输出请查看右上角“日志”。</div>
                <div class="payloader-agent-compact-list">
                  <div v-for="(action, idx) in compactActionItems" :key="`${action.time}-${idx}`" class="payloader-agent-compact-item">
                    <div class="payloader-agent-compact-top">
                      <span class="payloader-agent-action-tool">{{ formatActionToolLabel(action.tool) }}</span>
                      <span class="payloader-agent-action-time">{{ formatActionTime(action.time) }}</span>
                    </div>
                    <div class="payloader-agent-compact-line">
                      <span class="payloader-agent-action-label">参数</span>
                      <span class="payloader-agent-compact-text">{{ summarizeActionPayload(action.args, '无参数') }}</span>
                    </div>
                    <div class="payloader-agent-compact-line">
                      <span class="payloader-agent-action-label">输出</span>
                      <span class="payloader-agent-compact-text">{{ summarizeActionPayload(action.result, '暂无输出') }}</span>
                    </div>
                  </div>
                </div>
              </div>

              <!-- 目标画像 (remote_target 模式) -->
              <div v-if="agentResult.final?.target_profile" class="payloader-agent-section payloader-agent-target-profile">
                <h4 class="payloader-agent-section-title">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <circle cx="12" cy="12" r="10"></circle>
                    <line x1="2" y1="12" x2="22" y2="12"></line>
                    <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"></path>
                  </svg>
                  目标画像
                </h4>
                <div class="payloader-target-profile-grid">
                  <div class="payloader-target-profile-item">
                    <span class="payloader-target-profile-label">目标 URL</span>
                    <span class="payloader-target-profile-value">{{ agentResult.final.target_profile.target_url }}</span>
                  </div>
                  <div class="payloader-target-profile-item">
                    <span class="payloader-target-profile-label">目标类型</span>
                    <span class="payloader-target-profile-value">{{ agentResult.final.target_profile.target_type }}</span>
                  </div>
                  <div v-if="agentResult.final.target_profile.classification" class="payloader-target-profile-item">
                    <span class="payloader-target-profile-label">分类置信度</span>
                    <span class="payloader-target-profile-value">{{ (agentResult.final.target_profile.classification.confidence * 100).toFixed(0) }}%</span>
                  </div>
                </div>
              </div>

              <!-- 阶段验证链 (remote_target 模式优先渲染) -->
              <div v-if="agentResult.final?.phase_results && agentResult.final.phase_results.length > 0" class="payloader-agent-section payloader-agent-phases">
                <h4 class="payloader-agent-section-title">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M12 2L2 7l10 5 10-5-10-5z"></path>
                    <path d="M2 17l10 5 10-5"></path>
                    <path d="M2 12l10 5 10-5"></path>
                  </svg>
                  阶段验证链
                </h4>
                <div class="payloader-phase-chain">
                  <div v-for="(phase, idx) in agentResult.final.phase_results" :key="phase.name" class="payloader-phase-node-wrapper">
                    <div :class="['payloader-phase-node', `payloader-phase-node--${phase.status}`]">
                      <div class="payloader-phase-node-header">
                        <span class="payloader-phase-step">PHASE {{ idx + 1 }}</span>
                        <span :class="['payloader-phase-status', `payloader-phase-status--${phase.status}`]">
                          {{ phase.status === 'completed' ? '✅ 完成' : phase.status === 'failed' ? '❌ 失败' : phase.status === 'partial' ? '⏳ 部分' : '⏭️ 跳过' }}
                        </span>
                      </div>
                      <h5 class="payloader-phase-node-title">{{ phase.label }}</h5>
                      <p class="payloader-phase-node-summary">{{ phase.summary }}</p>
                      <div class="payloader-phase-node-meta">
                        <span class="payloader-phase-evidence">证据: {{ phase.evidence_count }} 项</span>
                        <span v-if="phase.risk_conclusion" class="payloader-phase-risk">{{ phase.risk_conclusion }}</span>
                      </div>
                    </div>
                    <div v-if="idx < agentResult.final!.phase_results!.length - 1" class="payloader-phase-connector">
                      <div class="payloader-phase-arrow"></div>
                    </div>
                  </div>
                </div>
              </div>

              <!-- 验证链详情 -->
              <div v-if="agentResult.final?.validation_chain && agentResult.final.validation_chain.length > 0" class="payloader-agent-section payloader-agent-validation">
                <h4 class="payloader-agent-section-title">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path>
                    <polyline points="22 4 12 14.01 9 11.01"></polyline>
                  </svg>
                  验证链结果
                </h4>
                <div class="payloader-validation-list">
                  <div v-for="(vc, idx) in agentResult.final.validation_chain" :key="idx" :class="['payloader-validation-item', vc.validated ? 'validated' : 'unvalidated']">
                    <span class="payloader-validation-icon">{{ vc.validated ? '✅' : '❌' }}</span>
                    <div class="payloader-validation-content">
                      <span class="payloader-validation-finding">{{ vc.finding }}</span>
                      <span class="payloader-validation-conclusion">{{ vc.conclusion }}</span>
                    </div>
                    <span :class="['payloader-validation-severity', vc.severity]">{{ vc.severity }}</span>
                  </div>
                </div>
              </div>

              <!-- 风险假设 -->
              <div v-if="agentResult.final?.risk_hypotheses && agentResult.final.risk_hypotheses.length > 0" class="payloader-agent-section payloader-agent-risk-hypotheses">
                <h4 class="payloader-agent-section-title">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path>
                    <line x1="12" y1="9" x2="12" y2="13"></line>
                    <line x1="12" y1="17" x2="12.01" y2="17"></line>
                  </svg>
                  风险假设
                </h4>
                <div class="payloader-hypothesis-list">
                  <div v-for="(rh, idx) in agentResult.final.risk_hypotheses" :key="idx" class="payloader-hypothesis-item">
                    <span :class="['payloader-hypothesis-severity', rh.severity]">{{ rh.severity }}</span>
                    <span class="payloader-hypothesis-text">{{ rh.hypothesis }}</span>
                    <span class="payloader-hypothesis-confidence">置信度: {{ (rh.confidence * 100).toFixed(0) }}%</span>
                  </div>
                </div>
              </div>

              <!-- 渗透结果分析 (fallback: 如果没有 phase_results 则用旧逻辑) -->
              <div v-if="!agentResult.final?.phase_results?.length && agentResult.final && (agentResult.final.attack_type || agentResult.final.scan_results || agentResult.final.risks)" class="payloader-agent-section payloader-agent-analysis">
                <h4 class="payloader-agent-section-title">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M12 2L2 7l10 5 10-5-10-5z"></path>
                    <path d="M2 17l10 5 10-5"></path>
                    <path d="M2 12l10 5 10-5"></path>
                  </svg>
                  渗透结果分析
                </h4>
                
                <div v-if="agentResult.final.attack_type" class="payloader-agent-attack-type">
                  <div class="payloader-agent-analysis-label">攻击类型</div>
                  <div class="payloader-agent-analysis-value">
                    <span class="payloader-agent-attack-type-badge">{{ agentResult.final.attack_type }}</span>
                    <p v-if="agentResult.final.attack_description" class="payloader-agent-attack-desc">{{ agentResult.final.attack_description }}</p>
                  </div>
                </div>
                
                <div v-if="agentResult.final.scan_results" class="payloader-agent-scan-results">
                  <div class="payloader-agent-analysis-label">扫描发现</div>
                  <pre class="payloader-detail-code">{{ agentResult.final.scan_results }}</pre>
                </div>
                
                <div v-if="agentResult.final.risks && agentResult.final.risks.length > 0" class="payloader-agent-risks">
                  <div class="payloader-agent-analysis-label">发现风险</div>
                  <ul class="payloader-agent-risk-list">
                    <li v-for="(risk, idx) in agentResult.final.risks" :key="idx" class="payloader-agent-risk-item">
                      <span class="payloader-agent-risk-icon">⚠</span>
                      <span>{{ risk }}</span>
                    </li>
                  </ul>
                </div>
              </div>

              <!-- 安全防护建议 -->
              <div v-if="agentResult.final && (agentResult.final.recommendations || agentResult.final.commands)" class="payloader-agent-section payloader-agent-suggestions">
                <h4 class="payloader-agent-section-title">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path>
                  </svg>
                  安全防护建议
                </h4>
                
                <div v-if="agentResult.final.recommendations && agentResult.final.recommendations.length > 0" class="payloader-agent-recommendations">
                  <ul class="payloader-agent-suggestion-list">
                    <li v-for="(rec, idx) in agentResult.final.recommendations" :key="idx" class="payloader-agent-suggestion-item">
                      <span class="payloader-agent-suggestion-icon">✓</span>
                      <span>{{ rec }}</span>
                    </li>
                  </ul>
                </div>
                
                <div v-if="agentResult.final.commands && agentResult.final.commands.length > 0" class="payloader-agent-commands">
                  <div class="payloader-agent-analysis-label">相关命令</div>
                  <div v-for="(cmd, idx) in agentResult.final.commands" :key="idx" class="payloader-agent-command">
                    <pre class="payloader-detail-code">{{ cmd }}</pre>
                    <button class="payloader-btn payloader-btn--secondary payloader-btn--sm" @click.stop="handleCopy(cmd)">复制</button>
                  </div>
                </div>
              </div>

              <!-- 检测报告 -->
              <div v-if="agentResult.final?.report" class="payloader-agent-section payloader-agent-report-section">
                <h4 class="payloader-agent-section-title">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                    <polyline points="14 2 14 8 20 8"></polyline>
                    <line x1="16" y1="13" x2="8" y2="13"></line>
                    <line x1="16" y1="17" x2="8" y2="17"></line>
                    <polyline points="10 9 9 9 8 9"></polyline>
                  </svg>
                  完整检测报告
                </h4>
                <div class="payloader-agent-report-content" v-html="renderReportMarkdown(agentResult.final.report)"></div>
              </div>

              <!-- 使用的 Skills -->
              <div v-if="agentResult.skill_results && agentResult.skill_results.length > 0" class="payloader-agent-section payloader-agent-skills-section">
                <h4 class="payloader-agent-section-title">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"></path>
                  </svg>
                  使用的 Skills
                </h4>
                <div class="payloader-agent-skills-grid">
                  <div v-for="(skill, idx) in agentResult.skill_results" :key="idx" class="payloader-agent-skill-card">
                    <div class="payloader-agent-skill-header">
                      <span class="payloader-agent-skill-name">{{ skill.skill_name }}</span>
                      <span :class="['payloader-agent-skill-risk', skill.risk_level]">{{ skill.risk_level }}</span>
                    </div>
                    <p class="payloader-agent-skill-summary">{{ skill.summary }}</p>
                  </div>
                </div>
              </div>
            </div>
          </div>
          <div v-if="!agentRunning" class="payloader-modal-footer">
            <button class="payloader-btn payloader-btn--secondary" @click="requestCloseResultModal">关闭</button>
            <button class="payloader-btn payloader-btn--primary" @click="closeResultModal(); startHostAgent()">重新检测</button>
          </div>
        </div>
      </div>

      <div v-if="showCloseConfirmModal" class="payloader-modal-overlay" @click.self="cancelCloseConfirmation">
        <div class="payloader-modal payloader-modal--confirm">
          <div class="payloader-modal-header">
            <h3>确认关闭</h3>
            <button class="payloader-modal-close" title="关闭" @click="cancelCloseConfirmation">&times;</button>
          </div>
          <div class="payloader-modal-body">
            <p class="payloader-modal-desc">
              当前任务仍在运行。你可以关闭当前弹窗并让任务在后台继续，或者立即中断本次任务。
            </p>
          </div>
          <div class="payloader-modal-footer">
            <button class="payloader-btn payloader-btn--secondary" @click="continueTaskInBackground">后台继续运行</button>
            <button class="payloader-btn payloader-btn--danger" :disabled="stoppingTask" @click="interruptTaskAndClose">
              {{ stoppingTask ? '中断中...' : '中断任务' }}
            </button>
          </div>
        </div>
      </div>

      <!-- 日志弹窗 -->
      <div v-if="showLogModal" class="payloader-modal-overlay payloader-log-overlay" @click.self="closeLogModal">
          <div class="payloader-modal payloader-modal--log">
          <div class="payloader-modal-header">
            <div class="payloader-log-header-main">
              <h3>执行日志 ({{ logRounds.length }} 轮 / {{ logData.length }} 条任务)</h3>
              <p v-if="currentLogTaskId" class="payloader-log-header-sub">
                任务 {{ currentLogTaskId }} · 当前阶段 {{ getPhaseLabel(logPhase) }}
              </p>
            </div>
            <div class="payloader-modal-header-actions">
              <button
                v-if="currentLogTaskId"
                class="payloader-modal-header-btn"
                :disabled="logLoading"
                @click="loadLogs(currentLogTaskId)"
              >
                刷新
              </button>
              <button class="payloader-modal-close" @click="closeLogModal">&times;</button>
            </div>
          </div>
          <div class="payloader-modal-body payloader-modal-body--scroll payloader-log-body">
            <div v-if="logLoading && logData.length === 0" class="payloader-log-empty">正在加载日志...</div>
            <div v-else-if="logError" class="payloader-log-empty payloader-log-empty--error">{{ logError }}</div>
            <template v-else>
              <section v-if="logReport" class="payloader-log-report-section">
                <div class="payloader-log-report-header">
                  <div>
                    <div class="payloader-log-report-eyebrow">执行报告</div>
                    <h4>本次任务总结</h4>
                  </div>
                  <button
                    v-if="logData.length > 0"
                    class="payloader-log-jump-btn"
                    type="button"
                    @click="scrollLogDetailsIntoView"
                  >
                    查看日志详情
                  </button>
                </div>
                <div class="payloader-agent-report-content" v-html="renderReportMarkdown(logReport)"></div>
              </section>
              <div v-if="logData.length === 0" class="payloader-log-empty">
              {{ agentRunning ? 'AI 已决策，正在等待第一条执行日志落盘...' : '暂无日志数据' }}
              </div>
            </template>
            <div
              v-for="(round, roundIdx) in logRounds"
              :key="round.key"
              ref="logDetailRefs"
              class="payloader-log-round-group"
            >
              <div class="payloader-log-round-header">
                <span class="payloader-log-round">Round {{ round.round ?? roundIdx + 1 }}</span>
                <span class="payloader-log-round-count">{{ round.actions.length }} 个任务</span>
                <span class="payloader-log-time">{{ formatActionTime(round.time) }}</span>
              </div>
              <div class="payloader-log-think">
                <div class="payloader-log-think-label">🤖 AI 决策</div>
                <pre class="payloader-log-think-content">{{ formatActionPayload(round.llm_decision, '[暂无决策记录]') }}</pre>
              </div>
              <div v-for="(log, actionIdx) in round.actions" :key="log.id || `${round.key}-${actionIdx}`" class="payloader-log-entry">
                <div class="payloader-log-meta">
                  <span v-if="log.task_label" class="payloader-log-task">{{ log.task_label }}</span>
                  <span class="payloader-log-tool">{{ formatActionToolLabel(log.tool) }}</span>
                  <span v-if="log.surface" class="payloader-log-surface">{{ log.surface }}</span>
                  <span :class="['payloader-log-status', `payloader-log-status--${log.status || 'completed'}`]">
                    {{ getLogStatusLabel(log.status) }}
                  </span>
                  <span class="payloader-log-time">{{ formatActionTime(log.time) }}</span>
                  <span v-if="log.returncode !== null" :class="['payloader-log-rc', log.returncode === 0 ? 'ok' : 'err']">rc={{ log.returncode }}</span>
                </div>
                <div v-if="log.purpose" class="payloader-log-args">
                  <div class="payloader-log-args-label">🎯 目的</div>
                  <pre class="payloader-log-code">{{ formatActionPayload(log.purpose, '暂无目的说明') }}</pre>
                </div>
                <div v-if="log.args" class="payloader-log-args">
                  <div class="payloader-log-args-label">📌 参数</div>
                  <pre class="payloader-log-code">{{ formatActionPayload(log.args, '无参数') }}</pre>
                </div>
                <div v-if="log.capabilities?.length" class="payloader-log-args">
                  <div class="payloader-log-args-label">🧠 能力</div>
                  <pre class="payloader-log-code">{{ log.capabilities.join(', ') }}</pre>
                </div>
                <div v-if="log.full_stdout || log.result || log.status === 'running'" class="payloader-log-stdout">
                  <div class="payloader-log-stdout-label">📤 原始输出</div>
                  <pre class="payloader-log-code">{{ formatActionPayload(log.full_stdout || log.result, log.status === 'running' ? '工具执行中，等待输出...' : '暂无输出') }}</pre>
                </div>
                <div v-if="log.error" class="payloader-log-error">
                  <div class="payloader-log-error-label">❌ 错误</div>
                  <pre class="payloader-log-code">{{ formatActionPayload(log.error, '暂无错误信息') }}</pre>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 历史弹窗 -->
      <div v-if="showHistoryModal" class="payloader-modal-overlay" @click.self="showHistoryModal = false">
        <div class="payloader-modal payloader-modal--history">
          <div class="payloader-modal-header">
            <h3>渗透历史 ({{ historyData.length }} 条)</h3>
            <button class="payloader-modal-close" @click="showHistoryModal = false">&times;</button>
          </div>
          <div class="payloader-modal-body payloader-modal-body--scroll">
            <div v-if="historyData.length === 0" class="payloader-log-empty">暂无历史记录</div>
            <div v-for="item in historyData" :key="item.task_id" class="payloader-history-item">
              <div class="payloader-history-main">
                <div class="payloader-history-target">{{ item.target }}</div>
                <div class="payloader-history-meta">
                  <span class="payloader-history-time">{{ item.start_time }}</span>
                  <span :class="['payloader-history-status', item.status]">{{ item.status }}</span>
                  <span class="payloader-history-phase">{{ getPhaseLabel(item.phase) }}</span>
                </div>
              </div>
              <div class="payloader-history-stats">
                <span class="payloader-history-stat">🔍 {{ item.findings_count }}</span>
                <span class="payloader-history-stat">⚠️ {{ item.vuln_count }}</span>
                <span class="payloader-history-stat">🛠 {{ item.actions_count }}</span>
              </div>
              <div class="payloader-history-actions">
                <button class="payloader-btn payloader-btn--secondary payloader-btn--sm" @click="viewHistoryLogs(item.task_id)">日志</button>
                <button class="payloader-btn payloader-btn--secondary payloader-btn--sm" @click="deleteHistory(item.task_id)">删除</button>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div v-if="isLoading" class="payloader-loading">
        <div class="payloader-loading-spinner"></div>
        <p class="payloader-loading-text">正在加载 Payload...</p>
      </div>

      <div v-else-if="error" class="payloader-error">
        <div class="payloader-error-icon">⚠️</div>
        <h3 class="payloader-error-title">加载失败</h3>
        <p class="payloader-error-description">{{ error }}</p>
        <button class="payloader-btn payloader-btn--primary" @click="refresh">
          重试
        </button>
      </div>

      <template v-else-if="state.viewMode === 'list'">
        <!-- 编解码工具 -->
        <EncodingTools v-if="state.currentView === 'encoding'" />

        <!-- 其他视图的列表 -->
        <template v-else>
          <div v-if="filteredItems.length === 0" class="payloader-empty">
          <div class="payloader-empty-icon">📦</div>
          <h3 class="payloader-empty-title">暂无内容</h3>
          <p class="payloader-empty-description">
            {{ state.searchQuery ? '没有找到匹配的内容' : '该分类下暂无内容' }}
          </p>
        </div>

        <div v-else class="payloader-cards-grid">
          <template v-if="state.currentView === 'tools'">
            <div 
              v-for="tool in filteredTools" 
              :key="tool.id"
              class="payloader-card"
              @click="openDetail(tool.id)"
            >
              <div class="payloader-card-header">
                <span class="payloader-card-category">{{ getText(tool.category) }}</span>
              </div>
              <h3 class="payloader-card-title">{{ getText(tool.name) }}</h3>
              <p class="payloader-card-desc">{{ getText(tool.description) }}</p>
              <div class="payloader-card-footer">
                <span class="payloader-card-count">{{ tool.commands.length }} 条命令</span>
              </div>
            </div>
          </template>

          <template v-else>
            <div 
              v-for="payload in filteredPayloadsList" 
              :key="payload.id"
              class="payloader-card"
              @click="openDetail(payload.id)"
            >
              <div class="payloader-card-header">
                <span class="payloader-card-category">{{ getText(payload.category) }}</span>
                <span v-if="payload.subCategory" class="payloader-card-subcategory">{{ getText(payload.subCategory) }}</span>
              </div>
              <h3 class="payloader-card-title">{{ getText(payload.name) }}</h3>
              <p class="payloader-card-desc">{{ getText(payload.description) }}</p>
              <div class="payloader-card-tags">
                <span v-for="tag in payload.tags.slice(0, 3)" :key="tag" class="payloader-card-tag">{{ tag }}</span>
                <span v-if="payload.tags.length > 3" class="payloader-card-tag">+{{ payload.tags.length - 3 }}</span>
              </div>
            </div>
          </template>
        </div>
        </template>
      </template>

      <template v-else-if="state.viewMode === 'detail'">
        <div class="payloader-detail">
          <template v-if="state.currentView === 'tools' && selectedTool">
            <div class="payloader-detail-header">
              <div class="payloader-detail-meta">
                <span class="payloader-detail-category">{{ getText(selectedTool.category) }}</span>
              </div>
              <h1 class="payloader-detail-title">{{ getText(selectedTool.name) }}</h1>
              <p class="payloader-detail-desc">{{ getText(selectedTool.description) }}</p>
            </div>
            
            <div v-if="selectedTool.installation" class="payloader-detail-section">
              <h3 class="payloader-detail-section-title">安装方式</h3>
              <pre class="payloader-detail-code">{{ selectedTool.installation }}</pre>
            </div>

            <div class="payloader-detail-section">
              <h3 class="payloader-detail-section-title">命令列表</h3>
              <div class="payloader-detail-commands">
                <div v-for="(cmd, idx) in selectedTool.commands" :key="idx" class="payloader-detail-command">
                  <div class="payloader-detail-command-header">
                    <h4 class="payloader-detail-command-title">{{ getText(cmd.name) }}</h4>
                    <button class="payloader-btn payloader-btn--secondary payloader-btn--sm" @click.stop="handleCopy(cmd.command)">
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
                        <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
                      </svg>
                      复制
                    </button>
                  </div>
                  <pre class="payloader-detail-code">{{ cmd.command }}</pre>
                  <p v-if="cmd.description" class="payloader-detail-command-desc">{{ getText(cmd.description) }}</p>
                </div>
              </div>
            </div>
          </template>

          <template v-else-if="selectedPayload">
            <div class="payloader-detail-header">
              <div class="payloader-detail-meta">
                <span class="payloader-detail-category">{{ getText(selectedPayload.category) }}</span>
                <span v-if="selectedPayload.subCategory" class="payloader-detail-subcategory">{{ getText(selectedPayload.subCategory) }}</span>
              </div>
              <h1 class="payloader-detail-title">{{ getText(selectedPayload.name) }}</h1>
              <p class="payloader-detail-desc">{{ getText(selectedPayload.description) }}</p>
              <div class="payloader-detail-tags">
                <span v-for="tag in selectedPayload.tags" :key="tag" class="payloader-detail-tag">{{ tag }}</span>
              </div>
            </div>

            <div v-if="selectedPayload.prerequisites && selectedPayload.prerequisites.length > 0" class="payloader-detail-section">
              <h3 class="payloader-detail-section-title">前提条件</h3>
              <ul class="payloader-detail-list">
                <li v-for="(prereq, idx) in selectedPayload.prerequisites" :key="idx">{{ getText(prereq) }}</li>
              </ul>
            </div>

            <!-- 标签切换 -->
            <div class="payloader-section-tabs">
              <button
                :class="['payloader-section-tab', { active: activeSection === 'execution' }]"
                @click="activeSection = 'execution'"
              >
                执行步骤
              </button>
              <button
                :class="['payloader-section-tab', { active: activeSection === 'chain' }]"
                @click="activeSection = 'chain'"
              >
                攻击链
              </button>
              <button
                :class="['payloader-section-tab', { active: activeSection === 'analysis' }]"
                @click="activeSection = 'analysis'"
              >
                分析
              </button>
              <button
                v-if="selectedPayload.tutorial"
                :class="['payloader-section-tab', { active: activeSection === 'tutorial' }]"
                @click="activeSection = 'tutorial'"
              >
                教程
              </button>
            </div>

            <!-- 执行步骤 -->
            <div v-if="activeSection === 'execution'" class="payloader-detail-section">
              <div class="payloader-detail-executions">
                <div v-for="(exec, idx) in selectedPayload.execution" :key="idx" class="payloader-detail-execution">
                  <div class="payloader-detail-execution-header">
                    <h4 class="payloader-detail-execution-title">{{ getText(exec.title) }}</h4>
                    <button class="payloader-btn payloader-btn--secondary payloader-btn--sm" @click.stop="handleCopy(exec.command)">
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
                        <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
                      </svg>
                      复制
                    </button>
                  </div>
                  <pre class="payloader-detail-code">{{ exec.command }}</pre>
                  <div v-if="exec.description" class="payloader-detail-execution-desc">{{ getText(exec.description) }}</div>
                </div>
              </div>
            </div>

            <!-- 攻击链可视化 -->
            <div v-if="activeSection === 'chain'" class="payloader-detail-section">
              <div class="payloader-chain-header">
                <h3>攻击链可视化</h3>
                <p>展示完整的攻击流程和步骤之间的关联关系</p>
              </div>
              <div class="payloader-chain-visualization">
                <div v-for="(exec, idx) in selectedPayload.execution" :key="idx" class="payloader-chain-node-wrapper">
                  <div :class="['payloader-chain-node', { first: idx === 0, last: idx === selectedPayload.execution.length - 1 }]">
                    <div class="payloader-chain-node-header">
                      <span class="payloader-chain-step">STEP {{ idx + 1 }}</span>
                      <span v-if="exec.platform" :class="['payloader-chain-platform', exec.platform]">
                        {{ exec.platform === 'all' ? '🌐' : exec.platform === 'windows' ? '🪟' : '🐧' }}
                      </span>
                    </div>
                    <h4 class="payloader-chain-node-title">{{ getText(exec.title) }}</h4>
                    <p v-if="exec.description" class="payloader-chain-node-desc">{{ getText(exec.description) }}</p>
                    <div class="payloader-chain-command-preview">
                      <code>{{ exec.command.substring(0, 80) }}{{ exec.command.length > 80 ? '...' : '' }}</code>
                    </div>
                    <div class="payloader-chain-node-actions">
                      <button class="payloader-chain-copy-btn" @click.stop="handleCopy(exec.command)">📋</button>
                    </div>
                  </div>
                  <div v-if="idx < selectedPayload.execution.length - 1" class="payloader-chain-connector">
                    <div class="payloader-chain-arrow"></div>
                    <div class="payloader-chain-arrowhead"></div>
                  </div>
                </div>
              </div>
            </div>

            <!-- 分析部分 -->
            <div v-if="activeSection === 'analysis'" class="payloader-detail-section">
              <div class="payloader-analysis-card">
                <h3>分析说明</h3>
                <p>{{ selectedPayload.analysis ? getText(selectedPayload.analysis) : '暂无分析内容' }}</p>
              </div>

              <div v-if="selectedPayload.opsecTips && selectedPayload.opsecTips.length > 0" class="payloader-analysis-card warning">
                <h3>OPSEC 提示</h3>
                <ul>
                  <li v-for="(tip, idx) in selectedPayload.opsecTips" :key="idx">{{ getText(tip) }}</li>
                </ul>
              </div>

              <div v-if="selectedPayload.references && selectedPayload.references.length > 0" class="payloader-analysis-card">
                <h3>参考链接</h3>
                <ul class="payloader-references-list">
                  <li v-for="(ref, idx) in selectedPayload.references" :key="idx">
                    <a :href="ref" target="_blank" rel="noopener noreferrer">{{ ref }}</a>
                  </li>
                </ul>
              </div>
            </div>

            <!-- 教程部分 -->
            <div v-if="activeSection === 'tutorial' && selectedPayload.tutorial" class="payloader-detail-section">
              <div class="payloader-detail-tutorial">
                <div class="payloader-detail-tutorial-item">
                  <h4>概述</h4>
                  <p>{{ getText(selectedPayload.tutorial.overview) }}</p>
                </div>
                <div class="payloader-detail-tutorial-item">
                  <h4>漏洞原理</h4>
                  <p>{{ getText(selectedPayload.tutorial.vulnerability) }}</p>
                </div>
                <div class="payloader-detail-tutorial-item">
                  <h4>利用方式</h4>
                  <p>{{ getText(selectedPayload.tutorial.exploitation) }}</p>
                </div>
                <div class="payloader-detail-tutorial-item">
                  <h4>修复方案</h4>
                  <p>{{ getText(selectedPayload.tutorial.mitigation) }}</p>
                </div>
              </div>
            </div>

            <!-- WAF 绕过 -->
            <div v-if="selectedPayload.wafBypass && selectedPayload.wafBypass.length > 0" class="payloader-detail-section">
              <h3 class="payloader-detail-section-title">WAF 绕过</h3>
              <div class="payloader-detail-executions">
                <div v-for="(bypass, idx) in selectedPayload.wafBypass" :key="idx" class="payloader-detail-execution">
                  <div class="payloader-detail-execution-header">
                    <h4 class="payloader-detail-execution-title">{{ getText(bypass.title) }}</h4>
                    <button class="payloader-btn payloader-btn--secondary payloader-btn--sm" @click.stop="handleCopy(bypass.command)">
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
                        <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
                      </svg>
                      复制
                    </button>
                  </div>
                  <pre class="payloader-detail-code">{{ bypass.command }}</pre>
                </div>
              </div>
            </div>
          </template>
        </div>
      </template>
    </PayloaderContent>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue';
import PayloaderToolbar from './components/PayloaderToolbar.vue';
import PayloaderContent from './components/PayloaderContent.vue';
import EncodingTools from './components/EncodingTools.vue';
import { usePayloader } from './composables/usePayloaderState';
import type { PayloadItem, ToolCommand, I18nText } from './types';
import { aiService } from '../ai/aiService';

const { 
  state, 
  filteredPayloads, 
  categories, 
  isLoading, 
  error,
  refresh, 
  selectCategory, 
  setSearchQuery,
  setCurrentView,
  setSelectedItemId,
  copyPayload
} = usePayloader();

const showViewDropdown = ref(false);
const showCategoryDropdown = ref(false);
const activeSection = ref<'execution' | 'chain' | 'analysis' | 'tutorial'>('execution');

const views = [
  { id: 'web', label: 'Web 渗透' },
  { id: 'intranet', label: '内网渗透' }
];

const filteredItems = computed(() => {
  if (state.currentView === 'tools') {
    let result = state.toolCommands as readonly ToolCommand[];
    if (state.searchQuery) {
      const query = state.searchQuery.toLowerCase();
      result = result.filter(t => {
        const name = getText(t.name).toLowerCase();
        const desc = getText(t.description).toLowerCase();
        const cmds = t.commands.map(c => c.command).join('\n').toLowerCase();
        return name.includes(query) || desc.includes(query) || cmds.includes(query);
      });
    }
    return result;
  } else {
    return filteredPayloads.value as readonly PayloadItem[];
  }
});

const filteredTools = computed<ToolCommand[]>(() => {
  if (state.currentView !== 'tools') return [];
  let result = state.toolCommands;
  if (state.searchQuery) {
    const query = state.searchQuery.toLowerCase();
    result = result.filter(t => {
      const name = getText(t.name).toLowerCase();
      const desc = getText(t.description).toLowerCase();
      const cmds = t.commands.map(c => c.command).join('\n').toLowerCase();
      return name.includes(query) || desc.includes(query) || cmds.includes(query);
    });
  }
  return result as ToolCommand[];
});

const filteredPayloadsList = computed<PayloadItem[]>(() => {
  if (state.currentView === 'tools') return [];
  return filteredPayloads.value as PayloadItem[];
});

const selectedPayload = computed<PayloadItem | null>(() => {
  if (!state.selectedItemId || state.currentView === 'tools') return null;
  const all = [...state.webPayloads, ...state.intranetPayloads];
  const found = all.find(p => p.id === state.selectedItemId);
  if (!found) return null;
  
  // Helper to deep-spread PayloadExecution arrays
  const mapExecutions = (arr: readonly { title: any; command: string; syntaxBreakdown?: readonly any[]; description?: any; platform?: any; requiresAdmin?: boolean }[] | undefined) => {
    if (!arr) return undefined;
    return arr.map(e => ({
      title: e.title,
      command: e.command,
      syntaxBreakdown: e.syntaxBreakdown ? [...e.syntaxBreakdown] : undefined,
      description: e.description,
      platform: e.platform,
      requiresAdmin: e.requiresAdmin,
    }));
  };

  return {
    id: found.id,
    name: found.name,
    description: found.description,
    category: found.category,
    subCategory: found.subCategory,
    tags: Array.isArray(found.tags) ? [...found.tags] : [],
    prerequisites: found.prerequisites ? [...found.prerequisites] : undefined,
    execution: mapExecutions(found.execution)!,
    analysis: found.analysis,
    opsecTips: found.opsecTips ? [...found.opsecTips] : undefined,
    wafBypass: mapExecutions(found.wafBypass),
    edrBypass: mapExecutions(found.edrBypass),
    references: found.references ? [...found.references] : undefined,
    tutorial: found.tutorial,
  };
});

const selectedTool = computed<ToolCommand | null>(() => {
  if (!state.selectedItemId || state.currentView !== 'tools') return null;
  const found = state.toolCommands.find(t => t.id === state.selectedItemId);
  if (!found) return null;
  
  return {
    id: found.id,
    name: found.name,
    description: found.description,
    category: found.category,
    commands: found.commands.map(c => ({
      name: c.name,
      command: c.command,
      description: c.description,
      syntaxBreakdown: c.syntaxBreakdown ? [...c.syntaxBreakdown] : undefined,
      examples: c.examples ? [...c.examples] : undefined,
      platform: c.platform,
    })),
    installation: found.installation,
    references: found.references ? [...found.references] : undefined,
  };
});

function getViewLabel(view: string): string {
  const viewItem = views.find(v => v.id === view);
  return viewItem?.label || 'Web 渗透';
}

function getSelectedCategoryLabel(): string {
  if (state.selectedCategory === 'all') {
    return '全部';
  }
  const cat = categories.value.find(c => c.id === state.selectedCategory);
  return cat ? getText(cat.label) : '全部';
}

function getText(text: I18nText, lang: 'zh' | 'en' = 'zh'): string {
  if (typeof text === 'string') return text;
  return text[lang];
}

function toggleViewDropdown() {
  showViewDropdown.value = !showViewDropdown.value;
  showCategoryDropdown.value = false;
}

function toggleCategoryDropdown() {
  showCategoryDropdown.value = !showCategoryDropdown.value;
  showViewDropdown.value = false;
}

function selectView(viewId: string) {
  setCurrentView(viewId as any);
  showViewDropdown.value = false;
}

function selectCategoryWrapper(categoryId: string) {
  selectCategory(categoryId);
  showCategoryDropdown.value = false;
}

function goBack() {
  setSelectedItemId(null);
}

function openDetail(id: string) {
  setSelectedItemId(id);
}

const handleCopy = async (code: string) => {
  await copyPayload(code);
};

 // ==================== 安全检测 Agent ====================
const showPentestModal = ref(false);
const showResultModal = ref(false);
const showCloseConfirmModal = ref(false);
const agentRunning = ref(false);
const agentError = ref('');
const agentResult = ref<any>(null);
const stoppingTask = ref(false);
const pentestTarget = ref<string>('');
type PentestExecutionMode = 'serial' | 'parallel';
const PENTEST_EXECUTION_MODE_STORAGE_KEY = 'LERT-pentest-execution-mode';
const pentestExecutionMode = ref<PentestExecutionMode>(loadPentestExecutionMode());
const pentestModalError = ref('');
const normalizedPentestTarget = computed(() => String(pentestTarget.value || '').trim());
const currentTaskId = ref<string>('');

let statusTimer: ReturnType<typeof setInterval> | null = null;

function loadPentestExecutionMode(): PentestExecutionMode {
  try {
    const cached = localStorage.getItem(PENTEST_EXECUTION_MODE_STORAGE_KEY);
    return cached === 'serial' ? 'serial' : 'parallel';
  } catch {
    return 'parallel';
  }
}

function setPentestExecutionMode(mode: PentestExecutionMode) {
  pentestExecutionMode.value = mode;
  try {
    localStorage.setItem(PENTEST_EXECUTION_MODE_STORAGE_KEY, mode);
  } catch {
    // ignore persistence errors
  }
}

function getAIConfig() {
  try {
    const raw = localStorage.getItem('LERT-ai-config');
    if (!raw) return null;
    const cfg = JSON.parse(raw);
    return {
      apiKey: cfg.apiKey || '',
      model: cfg.model || 'gpt-4o-mini',
      baseUrl: cfg.baseUrl || 'https://api.openai.com/v1',
      provider: cfg.provider || 'openai',
      temperature: cfg.temperature ?? 0.3,
    };
  } catch {
    return null;
  }
}

function openPentestModal() {
  pentestModalError.value = '';
  showPentestModal.value = true;
}

function handlePentestEntry() {
  pentestModalError.value = '';
  if (agentRunning.value && currentTaskId.value) {
    showResultModal.value = true;
    return;
  }
  openPentestModal();
}

function openSkillsManager() {
  (window as any).showSkillsModal?.();
}

function openKnowledgeBaseManager() {
  (window as any).showKnowledgeBaseModal?.();
}

function closePentestModal() {
  pentestModalError.value = '';
  showPentestModal.value = false;
}

function closeResultModal() {
  showCloseConfirmModal.value = false;
  showResultModal.value = false;
}

function requestCloseResultModal() {
  if (agentRunning.value && currentTaskId.value) {
    showCloseConfirmModal.value = true;
    return;
  }
  closeResultModal();
}

function cancelCloseConfirmation() {
  showCloseConfirmModal.value = false;
}

function continueTaskInBackground() {
  closeResultModal();
}

async function interruptTaskAndClose() {
  if (!currentTaskId.value || stoppingTask.value) {
    closeResultModal();
    return;
  }

  stoppingTask.value = true;
  try {
    const pythonApi = (await import('../../config/python-api.config')).default;
    await pythonApi.pentestStop(currentTaskId.value);
    if (statusTimer) {
      clearInterval(statusTimer);
      statusTimer = null;
    }
    agentRunning.value = false;
    showCloseConfirmModal.value = false;
    agentError.value = '';

    const currentPhase = agentResult.value?.phase || 'init';
    agentResult.value = {
      status: 'failed',
      final: {
        report: '# 正在生成阶段性总结报告...\n\n任务已中断，正在根据当前阶段已获取的信息整理总结，请稍候。',
        phase: currentPhase,
      },
      phase: currentPhase,
      targets: agentResult.value?.targets || [normalizedPentestTarget.value].filter(Boolean),
      findings_count: agentResult.value?.findings_count || 0,
      vuln_count: agentResult.value?.vuln_count || 0,
      actions_count: agentResult.value?.actions_count || 0,
      actions: agentResult.value?.actions || [],
    };

    (window as any).showNotification?.('任务已中断，正在生成总结报告', 'success');

    const summary = await buildInterruptedPentestSummary(currentTaskId.value);
    agentResult.value = {
      status: 'failed',
      final: {
        report: summary.report,
        phase: summary.phase,
      },
      phase: summary.phase,
      targets: agentResult.value?.targets || [normalizedPentestTarget.value].filter(Boolean),
      findings_count: summary.findingsCount,
      vuln_count: summary.vulnCount,
      actions_count: summary.actionsCount,
      actions: summary.actions,
    };
  } catch (err: any) {
    (window as any).showNotification?.(err?.message || '中断任务失败', 'error');
  } finally {
    stoppingTask.value = false;
  }
}

function getPhaseLabel(phase: string | undefined) {
  switch (phase) {
    case 'init':    return '初始化';
    case 'recon':   return '侦察与信息收集';
    case 'web':     return 'Web 漏洞发现';
    case 'exploit': return '漏洞利用';
    case 'post':    return '后渗透与证据收集';
    case 'lateral': return '横向移动与扩展';
    case 'done':    return '已完成';
    default:        return phase || '运行中';
  }
}

function formatActionToolLabel(tool?: string) {
  const toolLabel: Record<string, string> = {
    _llm_wait: 'AI 规划',
    nmap: '端口扫描',
    msfconsole: '漏洞利用',
    hydra: '密码爆破',
    shell: '命令执行',
    searchsploit: '漏洞搜索',
    nuclei: '漏洞扫描',
    sqlmap: 'SQL注入检测',
    ffuf: '目录扫描',
    nikto: 'Web扫描',
  };
  return toolLabel[String(tool || '')] || String(tool || 'unknown');
}

const currentActionSummary = computed(() => {
  if (!agentResult.value?.actions?.length) return '';
  const latest = agentResult.value.actions[agentResult.value.actions.length - 1];
  if (!latest) return '';
  if (latest.tool === '_llm_wait') {
    return 'AI 正在分析当前态势，规划下一步操作...';
  }
  if (latest.status === 'running') {
    const label = formatActionToolLabel(latest.tool);
    return `正在执行: ${label}`;
  }
  return '';
});

const currentPlanningStream = computed(() => {
  if (!agentResult.value?.actions?.length) return '';
  const latest = agentResult.value.actions[agentResult.value.actions.length - 1];
  if (!latest || latest.tool !== '_llm_wait') {
    return '';
  }
  return formatActionPayload(latest.result || latest.full_stdout, '');
});

const currentActionElapsed = ref('');
let elapsedTimer: ReturnType<typeof setInterval> | null = null;

const compactActionItems = computed(() => {
  const actions = Array.isArray(agentResult.value?.actions) ? agentResult.value.actions : [];
  return actions.slice(-3).reverse();
});

watch([() => agentResult.value?.actions, agentRunning], () => {
  if (elapsedTimer) { clearInterval(elapsedTimer); elapsedTimer = null; }
  if (!agentRunning.value || !agentResult.value?.actions?.length) {
    currentActionElapsed.value = '';
    return;
  }
  const latest = agentResult.value.actions[agentResult.value.actions.length - 1];
  if (!latest || latest.status !== 'running') {
    currentActionElapsed.value = '';
    return;
  }
  const startTime = new Date(latest.time).getTime();
  if (Number.isNaN(startTime)) {
    currentActionElapsed.value = '';
    return;
  }
  const updateElapsed = () => {
    const elapsed = Math.floor((Date.now() - startTime) / 1000);
    if (elapsed < 60) {
      currentActionElapsed.value = `${elapsed}s`;
    } else {
      const min = Math.floor(elapsed / 60);
      const sec = elapsed % 60;
      currentActionElapsed.value = `${min}m${sec}s`;
    }
  };
  updateElapsed();
  elapsedTimer = setInterval(updateElapsed, 1000);
}, { deep: true });

function formatActionTime(value: string | undefined) {
  if (!value) {
    return '刚刚';
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return date.toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
}

// 移除 ANSI 转义码（终端颜色代码）
function stripAnsiEscapeCodes(text: string): string {
  // 匹配 ANSI 转义序列: ESC [ ... m 或 ESC [ ... ; ... m 等
  return text.replace(/\x1b\[[0-9;]*[a-zA-Z]/g, '')
    // 匹配其他常见 ANSI 转义序列
    .replace(/\x1b\([0-9a-zA-Z]/g, '')
    .replace(/\x1b\)[0-9a-zA-Z]/g, '')
    .replace(/\x1b[0-9]/g, '');
}

function formatActionPayload(value: unknown, fallback: string) {
  if (value === null || value === undefined) {
    return fallback;
  }

  if (typeof value === 'object') {
    try {
      return JSON.stringify(value, null, 2);
    } catch {
      return stripAnsiEscapeCodes(String(value));
    }
  }

  const rawText = String(value).trim();
  if (!rawText) {
    return fallback;
  }

  // 先移除 ANSI 转义码
  const text = stripAnsiEscapeCodes(rawText);
  if (!text) {
    return fallback;
  }

  if (text.startsWith('{') || text.startsWith('[')) {
    try {
      return JSON.stringify(JSON.parse(text), null, 2);
    } catch {
      return text;
    }
  }

  return text;
}

function summarizeActionPayload(value: unknown, fallback: string, maxLength = 120) {
  const formatted = formatActionPayload(value, fallback)
    .replace(/\s+/g, ' ')
    .trim();

  if (!formatted) {
    return fallback;
  }

  if (formatted.length <= maxLength) {
    return formatted;
  }

  return `${formatted.slice(0, maxLength).trimEnd()}...`;
}

function escapeReportHtml(value: string) {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

function formatReportInline(text: string) {
  return escapeReportHtml(text)
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/`([^`]+)`/g, '<code>$1</code>');
}

function summarizeReportValue(value: unknown, fallback: string, maxLength = 120) {
  const raw = stripAnsiEscapeCodes(formatActionPayload(value, fallback))
    .replace(/\s+/g, ' ')
    .trim();

  if (!raw) {
    return fallback;
  }

  let summary = raw;
  const jsonLike = raw.startsWith('[') || raw.startsWith('{');
  if (jsonLike) {
    try {
      const parsed = JSON.parse(raw);
      if (Array.isArray(parsed)) {
        const preview = parsed.slice(0, 3).map((item) => {
          if (item && typeof item === 'object') {
            const record = item as Record<string, unknown>;
            const port = record.port ? `${record.port}` : '';
            const service = record.service ? `${record.service}` : '';
            const url = record.url ? `${record.url}` : '';
            const techs = Array.isArray(record.technologies) ? record.technologies.slice(0, 3).join(', ') : '';
            const pieces = [port && `端口 ${port}`, service, url, techs].filter(Boolean);
            return pieces.join(' / ');
          }
          return String(item);
        }).filter(Boolean);
        summary = preview.join('；');
        if (parsed.length > preview.length) {
          summary += ` 等 ${parsed.length} 项`;
        }
      } else if (parsed && typeof parsed === 'object') {
        const entries = Object.entries(parsed as Record<string, unknown>)
          .slice(0, 4)
          .map(([key, item]) => `${key}: ${String(item)}`);
        summary = entries.join('；');
      }
    } catch {
      summary = raw;
    }
  }

  summary = summary
    .replace(/^\s*[-*]\s*/, '')
    .replace(/\s*[\r\n]+\s*/g, ' ')
    .replace(/\s{2,}/g, ' ')
    .trim();

  if (summary.length <= maxLength) {
    return summary;
  }

  return `${summary.slice(0, maxLength).trimEnd()}...`;
}

function buildReportListItem(label: string, value: unknown, fallback: string, maxLength = 140) {
  return `- **${label}**：${summarizeReportValue(value, fallback, maxLength)}`;
}

function renderReportMarkdown(md: string): string {
  try {
    const lines = String(md || '').replace(/\r\n/g, '\n').split('\n');
    const parts: string[] = [];
    let paragraph: string[] = [];
    let listItems: string[] = [];
    let orderedItems: string[] = [];
    let inCodeBlock = false;
    let codeLines: string[] = [];

    const flushParagraph = () => {
      if (paragraph.length === 0) return;
      parts.push(`<p>${formatReportInline(paragraph.join(' '))}</p>`);
      paragraph = [];
    };

    const flushList = () => {
      if (listItems.length === 0) return;
      parts.push(`<ul>${listItems.map((item) => `<li>${formatReportInline(item)}</li>`).join('')}</ul>`);
      listItems = [];
    };

    const flushOrderedList = () => {
      if (orderedItems.length === 0) return;
      parts.push(`<ol>${orderedItems.map((item) => `<li>${formatReportInline(item)}</li>`).join('')}</ol>`);
      orderedItems = [];
    };

    const flushCodeBlock = () => {
      if (!inCodeBlock) return;
      parts.push(`<pre><code>${escapeReportHtml(codeLines.join('\n'))}</code></pre>`);
      inCodeBlock = false;
      codeLines = [];
    };

    for (const rawLine of lines) {
      const line = rawLine.trimEnd();
      const trimmed = line.trim();

      if (trimmed.startsWith('```')) {
        flushParagraph();
        flushList();
        flushOrderedList();
        if (inCodeBlock) {
          flushCodeBlock();
        } else {
          inCodeBlock = true;
          codeLines = [];
        }
        continue;
      }

      if (inCodeBlock) {
        codeLines.push(line);
        continue;
      }

      if (!trimmed) {
        flushParagraph();
        flushList();
        flushOrderedList();
        continue;
      }

      const heading = trimmed.match(/^(#{1,3})\s+(.+)$/);
      if (heading) {
        flushParagraph();
        flushList();
        flushOrderedList();
        const level = heading[1].length;
        parts.push(`<h${level}>${formatReportInline(heading[2].trim())}</h${level}>`);
        continue;
      }

      if (trimmed === '---') {
        flushParagraph();
        flushList();
        flushOrderedList();
        parts.push('<hr>');
        continue;
      }

      const unordered = trimmed.match(/^[-*]\s+(.+)$/);
      if (unordered) {
        flushParagraph();
        flushOrderedList();
        listItems.push(unordered[1].trim());
        continue;
      }

      const ordered = trimmed.match(/^\d+\.\s+(.+)$/);
      if (ordered) {
        flushParagraph();
        flushList();
        orderedItems.push(ordered[1].trim());
        continue;
      }

      paragraph.push(trimmed);
    }

    flushParagraph();
    flushList();
    flushOrderedList();
    flushCodeBlock();

    return parts.join('');
  } catch {
    return escapeReportHtml(String(md || '')).replace(/\n/g, '<br>');
  }
}

function buildFallbackPentestReport(params: {
  phase: string;
  target?: string;
  findingsCount?: number;
  vulnCount?: number;
  actionsCount?: number;
  error?: string;
  actions?: Array<{ tool?: string; time?: string; result?: string; status?: string }>;
}) {
  return [
    '## 总结',
    params.error
      ? `任务在 ${getPhaseLabel(params.phase)} 阶段结束，原因：${params.error}`
      : `任务在 ${getPhaseLabel(params.phase)} 阶段结束。`,
    '',
    `- 目标: ${params.target || normalizedPentestTarget.value || '未知目标'}`,
    `- 风险等级: ${getPentestRiskLevel(params.vulnCount || 0, 0)}`,
    `- 执行动作: ${params.actionsCount || 0} 步`,
    `- 发现资产: ${params.findingsCount || 0} 项`,
    `- 发现漏洞: ${params.vulnCount || 0} 项`,
    '',
    '## 说明',
    '- 当前仅能基于已有执行结果生成简要总结。',
    '- 详细参数、原始输出和完整过程请查看右上角“日志”。',
  ].join('\n');
}

function extractPotentialVulnerabilityHints(report: string, vulnCount: number): string[] {
  const lines = report
    .split('\n')
    .map((line) => line.trim())
    .filter((line) => line.length > 0);

  const matched = lines.filter((line) => /漏洞|风险|可利用|exploit|cve/i.test(line)).slice(0, 5);
  if (matched.length > 0) {
    return matched;
  }
  if (vulnCount > 0) {
    return [`已发现 ${vulnCount} 项潜在漏洞，建议结合执行日志继续验证利用条件。`];
  }
  return [];
}

function getPentestRiskLevel(vulnCount: number, failedCount: number) {
  if (vulnCount >= 3) return '高';
  if (vulnCount >= 1) return '中';
  if (failedCount > 0) return '待确认';
  return '低';
}

function buildUserFacingPentestReport(params: {
  phase: string;
  target?: string;
  findingsCount?: number;
  vulnCount?: number;
  actionsCount?: number;
  error?: string;
  backendReport?: string;
  logs?: PentestLogEntry[];
}) {
  const logs = params.logs || [];
  const actionableLogs = logs.filter((log) => !String(log.tool || '').startsWith('_'));
  const completedLogs = actionableLogs.filter((log) => (log.status || 'completed') !== 'failed' && !log.error);
  const failedLogs = actionableLogs.filter((log) => (log.status || 'completed') === 'failed' || !!log.error || (typeof log.returncode === 'number' && log.returncode !== 0));

  const workedOn = Array.from(new Set(actionableLogs.map((log) => {
    const purpose = summarizeActionPayload(log.purpose, '', 100);
    return purpose || `${log.tool} ${summarizeActionPayload(log.args, '', 70)}`.trim();
  }).filter(Boolean))).slice(0, 6);

  const successItems = completedLogs.slice(0, 6).map((log) =>
    buildReportListItem(log.tool, log.result || log.full_stdout || log.purpose, '执行完成', 150)
  );
  const failureItems = failedLogs.slice(0, 6).map((log) =>
    buildReportListItem(log.tool, log.error || log.result || log.full_stdout, '执行失败', 150)
  );
  const decisionItems = Array.from(new Set(
    logs
      .map((log) => summarizeReportValue(log.llm_decision, '', 220))
      .filter(Boolean)
  )).slice(0, 4).map((item, index) => `${index + 1}. ${item}`);
  const vulnHints = extractPotentialVulnerabilityHints(params.backendReport || '', params.vulnCount || 0);
  const riskLevel = getPentestRiskLevel(params.vulnCount || 0, failedLogs.length);
  const target = params.target || normalizedPentestTarget.value || '未知目标';
  const phaseLabel = getPhaseLabel(params.phase);
  const workedOnText = workedOn.length > 0 ? workedOn.join('；') : '已进行基础环境检查与探测';
  const statusSummary = params.error
    ? `任务在 **${phaseLabel}** 阶段结束。结束原因：${params.error}`
    : `任务已在 **${phaseLabel}** 阶段结束，当前结果可用于继续复核和整理证据。`;

  return [
    '# 渗透任务总结',
    statusSummary,
    '',
    '## 概览',
    `- **目标**：${target}`,
    `- **结束阶段**：${phaseLabel}`,
    `- **风险等级**：${riskLevel}`,
    `- **执行动作**：${params.actionsCount || actionableLogs.length || 0} 步`,
    `- **成功项**：${completedLogs.length} 项`,
    `- **失败项**：${failedLogs.length} 项`,
    `- **发现资产**：${params.findingsCount || 0} 项`,
    `- **发现漏洞**：${params.vulnCount || 0} 项`,
    '',
    '## 本次完成',
    workedOnText,
    '',
    '## 关键结果',
    ...(successItems.length > 0 ? successItems : ['- 暂无明确成功结果']),
    '',
    '## 失败与阻塞',
    ...(failureItems.length > 0 ? failureItems : ['- 暂无明确失败项']),
    '',
    '## 重点风险',
    ...(vulnHints.length > 0 ? vulnHints.map((item) => `- ${item}`) : ['- 暂未发现明确可直接利用的漏洞，建议结合日志继续验证。']),
    '',
    '## AI 决策摘要',
    ...(decisionItems.length > 0 ? decisionItems : ['1. 暂无 AI 决策记录']),
    '',
    '## 说明',
    '- 页面展示的是面向阅读的总结版，详细参数、原始输出和完整过程请查看右上角“日志”。',
  ].join('\n');
}

async function resolvePentestFinalReport(params: {
  taskId: string;
  phase: string;
  target?: string;
  findingsCount?: number;
  vulnCount?: number;
  actionsCount?: number;
  error?: string;
  actions?: Array<{ tool?: string; time?: string; result?: string; status?: string }>;
}) {
  let backendReport = '';
  let finalPhase = params.phase;
  let normalizedLogs: PentestLogEntry[] = [];

  try {
    const pythonApi = (await import('../../config/python-api.config')).default;
    const [report, logs] = await Promise.all([
      pythonApi.pentestGetReport(params.taskId).catch(() => null),
      pythonApi.pentestLogs(params.taskId).catch(() => null),
    ]);
    backendReport = String(report?.report || '').trim();
    finalPhase = report?.phase || params.phase;
    normalizedLogs = (logs?.actions || []).map((item: any) => normalizeLogEntry(item));
  } catch {
    // ignore and use fallback
  }

  return {
    report: buildUserFacingPentestReport({
      ...params,
      phase: finalPhase,
      backendReport,
      logs: normalizedLogs,
    }) || buildFallbackPentestReport(params),
    phase: finalPhase,
  };
}

async function buildInterruptedPentestSummary(taskId: string) {
  const pythonApi = (await import('../../config/python-api.config')).default;

  const [statusResult, logResult] = await Promise.allSettled([
    pythonApi.pentestStatus(taskId),
    pythonApi.pentestLogs(taskId),
  ]);

  const status = statusResult.status === 'fulfilled' ? statusResult.value : null;
  const rawLogs = logResult.status === 'fulfilled' ? (logResult.value.actions || []) : [];
  const normalizedLogs = rawLogs.map((item: any) => normalizeLogEntry(item));

  const phase = status?.phase || logPhase.value || agentResult.value?.phase || 'init';
  const findingsCount = status?.findings_count ?? agentResult.value?.findings_count ?? 0;
  const vulnCount = status?.vuln_count ?? agentResult.value?.vuln_count ?? 0;
  const actionsCount = status?.actions_count ?? agentResult.value?.actions_count ?? normalizedLogs.length ?? 0;
  const actions = Array.isArray(status?.actions) ? status!.actions : (agentResult.value?.actions || []);

  const fallbackReport = buildUserFacingPentestReport({
    phase,
    target: normalizedPentestTarget.value,
    findingsCount,
    vulnCount,
    actionsCount,
    error: '任务已由用户手动中断，以下为中断前的阶段性结果。',
    logs: normalizedLogs,
  }) || buildFallbackPentestReport({
    phase,
    target: normalizedPentestTarget.value,
    findingsCount,
    vulnCount,
    actionsCount,
    error: '任务已由用户手动中断，以下为中断前的阶段性结果。',
    actions,
  });

  if (!aiService.isConfigured()) {
    return {
      report: fallbackReport,
      phase,
      findingsCount,
      vulnCount,
      actionsCount,
      actions,
    };
  }

  const recentLogs = normalizedLogs.slice(-8).map((log, index) => [
    `${index + 1}. 工具: ${log.tool}`,
    `   时间: ${log.time || '未知'}`,
    `   状态: ${getLogStatusLabel(log.status)}`,
    `   目的: ${summarizeActionPayload(log.purpose, '暂无目的说明', 120)}`,
    `   参数: ${summarizeActionPayload(log.args, '无参数', 140)}`,
    `   输出: ${summarizeActionPayload(log.full_stdout || log.result || log.error, '暂无输出', 180)}`,
  ].join('\n')).join('\n\n');

  const llmDecisions = Array.from(
    new Set(
      normalizedLogs
        .map((log) => summarizeActionPayload(log.llm_decision, '', 260))
        .filter((item) => item && item !== '...')
    )
  ).slice(-3).join('\n\n');

  try {
    const report = await aiService.chatStream([
      {
        role: 'system',
        content: '你是一名渗透测试总结助手。任务已被用户手动中断，请严格基于当前阶段已确认的信息生成中文 Markdown 报告。必须包含：1. 中断说明 2. 当前阶段与进展 3. 已获得的有效信息 4. 已确认风险/异常 5. 未完成项与下一步建议。不要虚构不存在的结果。',
      },
      {
        role: 'user',
        content: `目标: ${normalizedPentestTarget.value || '未知目标'}
任务ID: ${taskId}
中断时阶段: ${getPhaseLabel(phase)}
已执行动作: ${actionsCount}
发现资产: ${findingsCount}
发现漏洞: ${vulnCount}

AI 决策摘要:
${llmDecisions || '暂无 AI 决策记录'}

最近执行日志:
${recentLogs || '暂无执行日志'}

请输出一份阶段性总结报告，明确哪些信息已经确认，哪些任务尚未完成。`,
      },
    ]);

    return {
      report: report?.trim() || fallbackReport,
      phase,
      findingsCount,
      vulnCount,
      actionsCount,
      actions,
    };
  } catch {
    return {
      report: fallbackReport,
      phase,
      findingsCount,
      vulnCount,
      actionsCount,
      actions,
    };
  }
}

async function startHostAgent() {
  const aiConfig = getAIConfig();
  if (!aiConfig || !aiConfig.apiKey) {
    agentError.value = '请先在 AI 设置中配置 LLM API Key';
    showResultModal.value = true;
    return;
  }

  const normalizedTarget = normalizedPentestTarget.value;
  if (!normalizedTarget) {
    pentestModalError.value = '请输入目标 IP 地址或域名';
    return;
  }

  pentestModalError.value = '';

  showPentestModal.value = false;
  showResultModal.value = true;
  agentRunning.value = true;
  agentError.value = '';
  agentResult.value = null;

  try {
    const pythonApi = (await import('../../config/python-api.config')).default;
    const startRes = await pythonApi.pentestStart({
      target: normalizedTarget,
      max_rounds: 30,
      dry_run: false,
      execution_mode: pentestExecutionMode.value,
      api_key: aiConfig.apiKey,
      model: aiConfig.model,
      base_url: aiConfig.baseUrl,
      provider: aiConfig.provider,
      temperature: aiConfig.temperature,
    });

    if (!startRes.success) {
      agentRunning.value = false;
      agentError.value = startRes.message;
      return;
    }

    currentTaskId.value = startRes.task_id;
    statusTimer = setInterval(pollStatus, 2000);
  } catch (err: any) {
    agentRunning.value = false;
    agentError.value = err?.message || '启动渗透任务失败';
  }
}

async function restoreRunningPentestTask() {
  try {
    const pythonApi = (await import('../../config/python-api.config')).default;
    const historyRes = await pythonApi.pentestHistory();
    const runningTask = (historyRes.history || []).find((item: any) => item?.status === 'running');

    if (!runningTask?.task_id) {
      return;
    }

    const status = await pythonApi.pentestStatus(runningTask.task_id);
    if (!status?.running) {
      return;
    }

    currentTaskId.value = runningTask.task_id;
    pentestTarget.value = runningTask.target || status.targets?.[0] || '';
    agentRunning.value = true;
    agentError.value = '';
    agentResult.value = {
      phase: status.phase,
      targets: status.targets,
      findings_count: status.findings_count,
      vuln_count: status.vuln_count,
      actions_count: status.actions_count,
      actions: status.actions,
    };

    if (statusTimer) {
      clearInterval(statusTimer);
    }
    statusTimer = setInterval(pollStatus, 2000);
  } catch (err) {
    console.error('恢复后台渗透任务失败:', err);
  }
}

async function pollStatus() {
  if (!currentTaskId.value) return;
  try {
    const pythonApi = (await import('../../config/python-api.config')).default;
    const status = await pythonApi.pentestStatus(currentTaskId.value);

    if (!status.running) {
      if (statusTimer) { clearInterval(statusTimer); statusTimer = null; }
      agentRunning.value = false;
      agentError.value = '';

      const report = await resolvePentestFinalReport({
        taskId: currentTaskId.value,
        phase: status.phase,
        target: normalizedPentestTarget.value,
        findingsCount: status.findings_count,
        vulnCount: status.vuln_count,
        actionsCount: status.actions_count,
        error: status.error,
        actions: status.actions,
      });

      agentResult.value = {
        status: !status.error && status.phase === 'done' ? 'completed' : 'failed',
        final: { report: report.report, phase: report.phase },
        phase: status.phase,
        targets: status.targets,
        findings_count: status.findings_count,
        vuln_count: status.vuln_count,
        actions_count: status.actions_count,
        actions: status.actions,
      };
    } else {
      agentResult.value = {
        status: 'running',
        phase: status.phase,
        targets: status.targets,
        findings_count: status.findings_count,
        vuln_count: status.vuln_count,
        actions_count: status.actions_count,
        actions: status.actions,
      };
    }
  } catch (err: any) {
    if (statusTimer) { clearInterval(statusTimer); statusTimer = null; }
    agentRunning.value = false;
    agentError.value = err?.message || '查询状态失败';
  }
}

// ==================== 日志查看 ====================
const showLogModal = ref(false);
type PentestLogEntry = {
  id?: string;
  tool: string;
  args: string;
  time: string;
  result: string;
  full_stdout: string;
  llm_decision: string;
  returncode: number | null;
  error: string;
  status?: string;
  updated_at?: string;
  surface?: string;
  purpose?: string;
  round?: number;
  task_label?: string;
  ports?: number[];
  capabilities?: string[];
};

type PentestLogRound = {
  key: string;
  round: number | null;
  time: string;
  llm_decision: string;
  actions: PentestLogEntry[];
};

const logData = ref<PentestLogEntry[]>([]);
const logLoading = ref(false);
const logError = ref('');
const logPhase = ref<string>('init');
const currentLogTaskId = ref('');
const logReport = ref('');
const logDetailRefs = ref<HTMLElement[]>([]);

let logTimer: ReturnType<typeof setInterval> | null = null;

function getLogStatusLabel(status: string | undefined) {
  switch (status) {
    case 'running':
      return '执行中';
    case 'failed':
      return '失败';
    case 'dry_run':
      return '演练';
    default:
      return '已完成';
  }
}

function normalizeLogEntry(log: Record<string, unknown>) {
  return {
    id: typeof log.id === 'string' ? log.id : undefined,
    tool: String(log.tool || 'unknown'),
    args: String(log.args || ''),
    time: String(log.time || ''),
    result: stripAnsiEscapeCodes(String(log.result || '')),
    full_stdout: stripAnsiEscapeCodes(String(log.full_stdout || '')),
    llm_decision: stripAnsiEscapeCodes(String(log.llm_decision || '')),
    returncode: typeof log.returncode === 'number' ? log.returncode : null,
    error: stripAnsiEscapeCodes(String(log.error || '')),
    status: typeof log.status === 'string' ? log.status : 'completed',
    updated_at: typeof log.updated_at === 'string' ? log.updated_at : undefined,
    surface: typeof log.surface === 'string' ? log.surface : '',
    purpose: stripAnsiEscapeCodes(typeof log.purpose === 'string' ? log.purpose : ''),
    round: typeof log.round === 'number' ? log.round : undefined,
    task_label: typeof log.task_label === 'string' ? log.task_label : '',
  };
}

const logRounds = computed<PentestLogRound[]>(() => {
  const groups: PentestLogRound[] = [];
  const groupIndex = new Map<string, number>();

  logData.value.forEach((log, index) => {
    const streamingDecision = log.tool === '_llm_wait'
      ? formatActionPayload(log.result || log.full_stdout, log.llm_decision)
      : log.llm_decision;
    const round = typeof log.round === 'number' ? log.round : null;
    const key = round !== null ? `round-${round}` : `single-${log.id || index}`;
    let group = groupIndex.has(key) ? groups[groupIndex.get(key)!] : undefined;

    if (!group) {
      group = {
        key,
        round,
        time: log.time,
        llm_decision: streamingDecision,
        actions: [],
      };
      groupIndex.set(key, groups.length);
      groups.push(group);
    }

    if (!group.llm_decision && streamingDecision) {
      group.llm_decision = streamingDecision;
    }
    if (!group.time && log.time) {
      group.time = log.time;
    }
    group.actions.push(log);
  });

  return groups;
});

function stopLogPolling() {
  if (logTimer) {
    clearInterval(logTimer);
    logTimer = null;
  }
}

function syncLogPolling() {
  stopLogPolling();

  if (!showLogModal.value || !currentLogTaskId.value) {
    return;
  }

  if (currentLogTaskId.value === currentTaskId.value && agentRunning.value) {
    logTimer = setInterval(() => {
      void loadLogs(currentLogTaskId.value, true);
    }, 400);
  }
}

async function openLogModal(taskId?: string) {
  const tid = taskId || currentTaskId.value;
  showLogModal.value = true;
  logError.value = '';
  logDetailRefs.value = [];

  if (!tid) {
    logData.value = [];
    logReport.value = '';
    logPhase.value = 'init';
    logError.value = '当前任务尚未生成日志，请稍后再试。';
    return;
  }

  if (currentLogTaskId.value !== tid) {
    logData.value = [];
    logReport.value = '';
  }
  currentLogTaskId.value = tid;
  await loadLogs(tid);
}

function closeLogModal() {
  stopLogPolling();
  showLogModal.value = false;
}

async function loadLogs(taskId?: string, silent = false) {
  const tid = taskId || currentLogTaskId.value || currentTaskId.value;
  if (!tid) return;

  currentLogTaskId.value = tid;
  if (!silent) {
    logLoading.value = true;
  }
  logError.value = '';
  try {
    const pythonApi = (await import('../../config/python-api.config')).default;
    const [logRes, reportRes] = await Promise.all([
      pythonApi.pentestLogs(tid),
      pythonApi.pentestGetReport(tid).catch(() => null),
    ]);
    logPhase.value = logRes.phase || reportRes?.phase || 'init';
    logData.value = (logRes.actions || []).map(normalizeLogEntry);
    const fallbackReport = tid === currentTaskId.value
      ? String(agentResult.value?.final?.report || '').trim()
      : '';
    logReport.value = String(reportRes?.report || fallbackReport).trim();
  } catch (err: any) {
    console.error('加载日志失败:', err);
    logError.value = err?.message || '加载日志失败';
  } finally {
    logLoading.value = false;
    syncLogPolling();
  }
}

function scrollLogDetailsIntoView() {
  const firstDetail = logDetailRefs.value[0];
  if (!firstDetail) {
    return;
  }
  firstDetail.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

// ==================== 历史记录 ====================
const showHistoryModal = ref(false);
const historyData = ref<Array<{
  task_id: string;
  target: string;
  start_time: string;
  status: string;
  phase: string;
  findings_count: number;
  vuln_count: number;
  actions_count: number;
}>>([]);

async function loadHistory() {
  try {
    const pythonApi = (await import('../../config/python-api.config')).default;
    const res = await pythonApi.pentestHistory();
    historyData.value = res.history || [];
  } catch (err: any) {
    console.error('加载历史失败:', err);
  }
}

async function viewHistoryLogs(taskId: string) {
  showHistoryModal.value = false;
  await openLogModal(taskId);
}

async function deleteHistory(taskId: string) {
  try {
    const pythonApi = (await import('../../config/python-api.config')).default;
    await pythonApi.pentestDeleteHistory(taskId);
    await loadHistory();
  } catch (err: any) {
    console.error('删除历史失败:', err);
  }
}

document.addEventListener('click', (e) => {
  const target = e.target as HTMLElement;
  if (!target.closest('.payloader-dropdown')) {
    showViewDropdown.value = false;
    showCategoryDropdown.value = false;
  }
});

onUnmounted(() => {
  if (statusTimer) {
    clearInterval(statusTimer);
    statusTimer = null;
  }
  stopLogPolling();
});

onMounted(() => {
  void restoreRunningPentestTask();
});
</script>

<style scoped>
.payloader-page {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--bg-primary);
}

.payloader-toolbar-left {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
}

.payloader-back-btn {
  display: flex;
  align-items: center;
  gap: var(--spacing-xs);
  padding: 8px 16px;
  border: 1px solid var(--border-color);
  border-radius: var(--border-radius);
  background: var(--bg-secondary);
  color: var(--text-primary);
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s ease;
  position: fixed;
  top: calc(3% + 16px);
  left: calc(10% + 16px);
  z-index: 1000;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}

.payloader-back-btn:hover {
  background: var(--bg-tertiary);
  border-color: var(--primary-color);
}

.payloader-dropdowns {
  display: flex;
  gap: var(--spacing-sm);
  align-items: center;
}

.payloader-dropdown {
  position: relative;
}

.payloader-dropdown-btn {
  display: flex;
  align-items: center;
  gap: var(--spacing-xs);
  padding: 8px 16px;
  border: 1px solid var(--border-color);
  border-radius: var(--border-radius);
  background: var(--bg-secondary);
  color: var(--text-primary);
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.payloader-dropdown-btn:hover {
  background: var(--bg-tertiary);
  border-color: var(--primary-color);
}

.payloader-dropdown-arrow {
  transition: transform 0.2s ease;
}

.payloader-dropdown-menu {
  position: absolute;
  top: 100%;
  left: 0;
  margin-top: 4px;
  min-width: 160px;
  max-height: 300px;
  overflow-y: auto;
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: var(--border-radius);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  z-index: 1000;
}

.payloader-dropdown-menu--large {
  min-width: 200px;
}

.payloader-dropdown-item {
  display: block;
  width: 100%;
  padding: 10px 16px;
  border: none;
  background: transparent;
  color: var(--text-primary);
  font-size: 13px;
  text-align: left;
  cursor: pointer;
  transition: all 0.15s ease;
}

.payloader-dropdown-item:hover {
  background: var(--bg-tertiary);
}

.payloader-dropdown-item.active {
  background: var(--primary-color);
  color: var(--text-white);
}

.payloader-search-box {
  display: flex;
  align-items: center;
  gap: var(--spacing-xs);
  padding: 6px 12px;
  border: 1px solid var(--border-color);
  border-radius: var(--border-radius);
  background: var(--bg-secondary);
}

.payloader-search-icon {
  color: var(--text-secondary);
  flex-shrink: 0;
}

.payloader-search-input {
  border: none;
  background: transparent;
  color: var(--text-primary);
  font-size: 13px;
  width: 200px;
  outline: none;
}

.payloader-search-input::placeholder {
  color: var(--text-secondary);
}

.payloader-cards-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: var(--spacing-lg);
  padding: var(--spacing-lg);
}

.payloader-card {
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: var(--border-radius);
  padding: var(--spacing-lg);
  cursor: pointer;
  transition: all 0.2s ease;
}

.payloader-card:hover {
  border-color: var(--primary-color);
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

.payloader-card-header {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  margin-bottom: var(--spacing-sm);
}

.payloader-card-category {
  font-size: 11px;
  color: var(--primary-color);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  font-weight: 600;
}

.payloader-card-subcategory {
  font-size: 10px;
  color: var(--text-secondary);
  background: var(--bg-tertiary);
  padding: 2px 6px;
  border-radius: 4px;
}

.payloader-card-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 var(--spacing-sm) 0;
}

.payloader-card-desc {
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.5;
  margin: 0 0 var(--spacing-md) 0;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.payloader-card-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.payloader-card-count {
  font-size: 12px;
  color: var(--text-tertiary);
}

.payloader-card-tags {
  display: flex;
  flex-wrap: wrap;
  gap: var(--spacing-xs);
}

.payloader-card-tag {
  font-size: 10px;
  color: var(--text-tertiary);
  background: var(--bg-tertiary);
  padding: 2px 6px;
  border-radius: 4px;
}

.payloader-detail {
  padding: var(--spacing-lg);
  max-width: 1200px;
  margin: 0 auto;
}

.payloader-detail-header {
  margin-bottom: var(--spacing-xl);
  padding-bottom: var(--spacing-lg);
  border-bottom: 1px solid var(--border-color);
}

.payloader-detail-meta {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  margin-bottom: var(--spacing-md);
}

.payloader-detail-category {
  font-size: 12px;
  color: var(--primary-color);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  font-weight: 600;
}

.payloader-detail-subcategory {
  font-size: 11px;
  color: var(--text-secondary);
  background: var(--bg-tertiary);
  padding: 2px 8px;
  border-radius: 4px;
}

.payloader-detail-title {
  font-size: 28px;
  font-weight: 700;
  color: var(--text-primary);
  margin: 0 0 var(--spacing-sm) 0;
}

.payloader-detail-desc {
  font-size: 15px;
  color: var(--text-secondary);
  line-height: 1.6;
  margin: 0 0 var(--spacing-md) 0;
}

.payloader-detail-tags {
  display: flex;
  flex-wrap: wrap;
  gap: var(--spacing-xs);
}

.payloader-detail-tag {
  font-size: 12px;
  color: var(--text-tertiary);
  background: var(--bg-tertiary);
  padding: 4px 10px;
  border-radius: 6px;
}

.payloader-detail-section {
  margin-bottom: var(--spacing-xl);
}

.payloader-detail-section-title {
  font-size: 18px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 var(--spacing-md) 0;
}

.payloader-detail-list {
  margin: 0;
  padding-left: var(--spacing-lg);
  color: var(--text-secondary);
  line-height: 1.8;
}

.payloader-detail-list li {
  margin-bottom: var(--spacing-xs);
}

/* 标签切换样式 */
.payloader-section-tabs {
  display: flex;
  gap: 8px;
  margin-bottom: var(--spacing-lg);
  padding-bottom: var(--spacing-md);
  border-bottom: 1px solid var(--border-color);
}

.payloader-section-tab {
  background: var(--bg-tertiary);
  border: 1px solid var(--border-color);
  color: var(--text-secondary);
  padding: 10px 20px;
  border-radius: 6px;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.payloader-section-tab:hover {
  border-color: var(--primary-color);
  color: var(--text-primary);
}

.payloader-section-tab.active {
  background: rgba(0, 240, 255, 0.1);
  border-color: var(--primary-color);
  color: var(--primary-color);
}

.payloader-detail-commands,
.payloader-detail-executions {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-lg);
}

.payloader-detail-command,
.payloader-detail-execution {
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: var(--border-radius);
  padding: var(--spacing-lg);
}

.payloader-detail-command-header,
.payloader-detail-execution-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--spacing-sm);
}

.payloader-detail-command-title,
.payloader-detail-execution-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.payloader-detail-command-desc,
.payloader-detail-execution-desc {
  font-size: 13px;
  color: var(--text-secondary);
  margin: var(--spacing-sm) 0 0 0;
}

.payloader-detail-code {
  background: var(--bg-tertiary);
  padding: var(--spacing-md);
  border-radius: var(--border-radius);
  font-family: var(--font-mono);
  font-size: 13px;
  color: var(--text-primary);
  overflow-x: auto;
  border: 1px solid var(--border-color);
  white-space: pre-wrap;
  word-break: break-all;
  margin: 0;
}

/* 攻击链可视化样式 */
.payloader-chain-header {
  margin-bottom: var(--spacing-lg);
}

.payloader-chain-header h3 {
  font-size: 16px;
  font-weight: 600;
  color: var(--primary-color);
  margin: 0 0 6px 0;
}

.payloader-chain-header p {
  font-size: 13px;
  color: var(--text-tertiary);
  margin: 0;
}

.payloader-chain-visualization {
  display: flex;
  flex-direction: column;
  gap: 0;
  position: relative;
}

.payloader-chain-node-wrapper {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.payloader-chain-node {
  width: 100%;
  max-width: 600px;
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: 12px;
  padding: 20px;
  position: relative;
  transition: all 0.2s ease;
}

.payloader-chain-node:hover {
  border-color: var(--primary-color);
  transform: translateY(-2px);
}

.payloader-chain-node.first {
  border-color: var(--success-color, #00ff88);
}

.payloader-chain-node.last {
  border-color: var(--danger-color, #ff0055);
}

.payloader-chain-node-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.payloader-chain-step {
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 2px;
  padding: 3px 10px;
  border-radius: 4px;
  background: rgba(0, 240, 255, 0.1);
  color: var(--primary-color);
  border: 1px solid rgba(0, 240, 255, 0.3);
}

.payloader-chain-node.first .payloader-chain-step {
  background: rgba(0, 255, 136, 0.15);
  color: var(--success-color, #00ff88);
  border-color: var(--success-color, #00ff88);
}

.payloader-chain-node.last .payloader-chain-step {
  background: rgba(255, 0, 85, 0.15);
  color: var(--danger-color, #ff0055);
  border-color: var(--danger-color, #ff0055);
}

.payloader-chain-platform {
  font-size: 14px;
}

.payloader-chain-node-title {
  font-size: 15px;
  font-weight: 600;
  margin: 0 0 6px 0;
  color: var(--text-primary);
}

.payloader-chain-node-desc {
  font-size: 12px;
  color: var(--text-tertiary);
  margin: 0 0 10px 0;
  line-height: 1.5;
}

.payloader-chain-command-preview {
  background: var(--bg-tertiary);
  border: 1px solid var(--border-color);
  border-radius: 6px;
  padding: 8px 12px;
  margin-bottom: 10px;
}

.payloader-chain-command-preview code {
  font-family: var(--font-mono);
  font-size: 11px;
  color: var(--primary-color);
  word-break: break-all;
}

.payloader-chain-node-actions {
  display: flex;
  gap: 6px;
  justify-content: flex-end;
}

.payloader-chain-copy-btn {
  background: var(--bg-tertiary);
  border: 1px solid var(--border-color);
  color: var(--text-secondary);
  width: 30px;
  height: 30px;
  border-radius: 4px;
  font-size: 14px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s ease;
}

.payloader-chain-copy-btn:hover {
  border-color: var(--primary-color);
  color: var(--primary-color);
}

.payloader-chain-connector {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 8px 0 10px;
  min-height: 42px;
}

.payloader-chain-arrow {
  width: 2px;
  height: 24px;
  background: linear-gradient(180deg, var(--primary-color), var(--accent-color, #a855f7));
  border-radius: 999px;
}

.payloader-chain-arrowhead {
  width: 10px;
  height: 10px;
  margin-top: -1px;
  border-right: 2px solid var(--accent-color, #a855f7);
  border-bottom: 2px solid var(--accent-color, #a855f7);
  transform: rotate(45deg);
}

/* 分析卡片样式 */
.payloader-analysis-card {
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  padding: 20px;
  margin-bottom: var(--spacing-md);
}

.payloader-analysis-card.warning {
  background: rgba(255, 102, 0, 0.05);
  border-color: rgba(255, 102, 0, 0.3);
}

.payloader-analysis-card h3 {
  font-size: 14px;
  font-weight: 600;
  margin: 0 0 12px 0;
  color: var(--primary-color);
}

.payloader-analysis-card p {
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.8;
  margin: 0;
}

.payloader-analysis-card ul {
  list-style: none;
  padding: 0;
  margin: 0;
}

.payloader-analysis-card li {
  font-size: 13px;
  color: var(--text-secondary);
  padding: 8px 0;
  padding-left: 20px;
  position: relative;
}

.payloader-analysis-card.warning li::before {
  content: '⚠';
  position: absolute;
  left: 0;
}

.payloader-references-list {
  list-style: none;
  padding: 0;
  margin: 0;
}

.payloader-references-list li {
  padding: 8px 0;
}

.payloader-references-list a {
  color: var(--primary-color);
  font-size: 13px;
  text-decoration: none;
}

.payloader-references-list a:hover {
  color: var(--accent-color, #a855f7);
  text-decoration: underline;
}

.payloader-detail-tutorial {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-lg);
}

.payloader-detail-tutorial-item {
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: var(--border-radius);
  padding: var(--spacing-lg);
}

.payloader-detail-tutorial-item h4 {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 var(--spacing-sm) 0;
}

.payloader-detail-tutorial-item p {
  font-size: 14px;
  color: var(--text-secondary);
  line-height: 1.7;
  margin: 0;
}

.payloader-btn--sm {
  padding: 6px 12px;
  font-size: 12px;
}

.payloader-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: var(--spacing-xl);
  color: var(--text-secondary);
}

.payloader-loading-spinner {
  width: 40px;
  height: 40px;
  border: 3px solid var(--border-color);
  border-top-color: var(--primary-color);
  border-radius: 50%;
  animation: payloader-spin 1s linear infinite;
  margin-bottom: var(--spacing-md);
}

@keyframes payloader-spin {
  to { transform: rotate(360deg); }
}

.payloader-loading-text {
  font-size: 14px;
}

.payloader-error {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: var(--spacing-xl);
  text-align: center;
}

.payloader-error-icon {
  font-size: 48px;
  margin-bottom: var(--spacing-md);
}

.payloader-error-title {
  margin: 0 0 var(--spacing-sm) 0;
  font-size: 18px;
  color: var(--text-primary);
}

.payloader-error-description {
  margin: 0 0 var(--spacing-lg) 0;
  font-size: 14px;
  color: var(--text-secondary);
  max-width: 300px;
}

.payloader-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: var(--spacing-xl);
  text-align: center;
}

.payloader-empty-icon {
  font-size: 48px;
  margin-bottom: var(--spacing-md);
}

.payloader-empty-title {
  margin: 0 0 var(--spacing-sm) 0;
  font-size: 18px;
  color: var(--text-primary);
}

.payloader-empty-description {
  margin: 0;
  font-size: 14px;
  color: var(--text-secondary);
  max-width: 300px;
}

.spinning {
  animation: payloader-spin 1s linear infinite;
}

/* Agent 按钮样式 */
.payloader-detail-actions {
  display: flex;
  gap: var(--spacing-sm);
  margin-top: var(--spacing-md);
}

.payloader-btn--agent {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: var(--border-radius);
  color: var(--text-primary);
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s ease;
  white-space: nowrap;
}

.payloader-btn--agent:hover:not(:disabled) {
  background: var(--bg-tertiary);
  border-color: var(--primary-color);
  color: var(--primary-color);
}

.payloader-btn--agent:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.payloader-btn--pentest {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  background: linear-gradient(135deg, #e74c3c, #c0392b);
  border: 1px solid #c0392b;
  border-radius: var(--border-radius);
  color: #fff;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
  white-space: nowrap;
}

.payloader-btn--pentest:hover:not(:disabled) {
  background: linear-gradient(135deg, #c0392b, #a93226);
  border-color: #a93226;
  box-shadow: 0 2px 8px rgba(231, 76, 60, 0.3);
}

.payloader-btn--pentest.is-running {
  background: linear-gradient(135deg, rgba(59, 130, 246, 0.18), rgba(16, 185, 129, 0.18));
  border-color: rgba(59, 130, 246, 0.35);
  color: var(--text-primary);
  box-shadow: 0 10px 24px rgba(59, 130, 246, 0.16);
}

.payloader-btn--pentest.is-running:hover:not(:disabled) {
  background: linear-gradient(135deg, rgba(59, 130, 246, 0.24), rgba(16, 185, 129, 0.24));
  border-color: rgba(59, 130, 246, 0.45);
  box-shadow: 0 14px 32px rgba(59, 130, 246, 0.2);
}

.payloader-btn-running-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  margin-left: 4px;
  padding: 2px 8px;
  border-radius: 999px;
  background: rgba(59, 130, 246, 0.14);
  color: var(--primary-color);
  font-size: 11px;
  font-weight: 600;
  line-height: 1;
}

.payloader-btn-running-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #22c55e;
  box-shadow: 0 0 0 4px rgba(34, 197, 94, 0.14);
  animation: payloader-running-pulse 1.6s ease-in-out infinite;
}

.payloader-btn--pentest:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.payloader-agent-planning-stream {
  margin: 0 0 16px;
  padding: 14px 16px;
  border-radius: 12px;
  border: 1px solid var(--border-color);
  background: linear-gradient(180deg, rgba(59, 130, 246, 0.08), rgba(59, 130, 246, 0.03));
  color: var(--text-primary);
  font-size: 12px;
  line-height: 1.65;
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 220px;
  overflow: auto;
}

@keyframes payloader-running-pulse {
  0%,
  100% {
    transform: scale(1);
    opacity: 1;
  }
  50% {
    transform: scale(1.18);
    opacity: 0.78;
  }
}

/* 工具和编解码按钮样式 */
.payloader-btn--tool {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: var(--border-radius);
  color: var(--text-primary);
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s ease;
  white-space: nowrap;
}

.payloader-btn--tool:hover {
  background: var(--bg-tertiary);
  border-color: var(--primary-color);
  color: var(--primary-color);
}

.payloader-btn--tool.active {
  background: var(--bg-tertiary);
  border-color: var(--primary-color);
  color: var(--primary-color);
}

.payloader-refresh-btn {
  min-height: 44px;
  white-space: nowrap;
}

/* Agent 运行中 */
.payloader-agent-running {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: var(--spacing-xl);
  gap: var(--spacing-md);
}

.payloader-agent-running-spinner {
  width: 40px;
  height: 40px;
  border: 3px solid var(--border-color);
  border-top-color: var(--primary-color);
  border-right-color: rgba(168, 85, 247, 0.8);
  border-radius: 50%;
  animation: payloader-spin 0.8s linear infinite;
  flex-shrink: 0;
}

.payloader-agent-running-header {
  display: flex;
  align-items: center;
  gap: 16px;
}

.payloader-agent-running-header-text {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.payloader-agent-phase-badge {
  display: inline-block;
  padding: 2px 8px;
  background: rgba(168, 85, 247, 0.15);
  color: var(--primary-color);
  border-radius: 4px;
  font-size: 12px;
  font-weight: 500;
}

.payloader-agent-round-info {
  font-size: 12px;
  color: var(--text-secondary);
  margin-left: 8px;
}

.payloader-agent-pulse {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #22c55e;
  margin-left: 8px;
  animation: payloader-pulse 1.5s ease-in-out infinite;
}

@keyframes payloader-pulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.4; transform: scale(0.8); }
}

.payloader-agent-current-action {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: rgba(168, 85, 247, 0.08);
  border: 1px solid rgba(168, 85, 247, 0.2);
  border-radius: 8px;
  font-size: 13px;
  color: var(--text-primary);
}

.payloader-agent-current-action-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--primary-color);
  animation: payloader-pulse 1.5s ease-in-out infinite;
  flex-shrink: 0;
}

.payloader-agent-current-action-text {
  flex: 1;
}

.payloader-agent-current-action-elapsed {
  color: var(--text-secondary);
  font-size: 12px;
  font-variant-numeric: tabular-nums;
}

.payloader-agent-action-running {
  border-color: rgba(168, 85, 247, 0.3);
  background: rgba(168, 85, 247, 0.04);
}

.payloader-agent-action-tool-active {
  color: var(--primary-color);
  font-weight: 600;
}

.payloader-agent-action-status-running {
  font-size: 11px;
  color: #22c55e;
  background: rgba(34, 197, 94, 0.1);
  padding: 1px 6px;
  border-radius: 4px;
  margin-left: 6px;
}

.payloader-agent-running-text {
  font-size: 14px;
  color: var(--primary-color);
  font-weight: 500;
}

.payloader-agent-running-sub {
  font-size: 13px;
  color: var(--text-secondary);
  margin: 0;
}

.payloader-agent-live-panel {
  width: 100%;
  max-width: 760px;
  display: flex;
  flex-direction: column;
  gap: 16px;
  margin-top: 8px;
}

.payloader-agent-live-stats {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 12px;
}

.payloader-agent-live-stat {
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: 10px;
  padding: 12px 14px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.payloader-agent-live-label {
  font-size: 12px;
  color: var(--text-secondary);
}

.payloader-agent-live-value {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

.payloader-agent-live-log {
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: 12px;
  padding: 16px;
}

.payloader-agent-live-log-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.payloader-agent-live-log-header h4 {
  margin: 0;
  font-size: 14px;
  color: var(--text-primary);
}

.payloader-agent-live-log-header span {
  font-size: 12px;
  color: var(--text-secondary);
}

.payloader-agent-live-log-section {
  padding-top: 16px;
}

.payloader-agent-live-log--compact {
  gap: 10px;
}

.payloader-agent-log-hint {
  margin-bottom: 12px;
  font-size: 12px;
  line-height: 1.6;
  color: var(--text-secondary);
}

.payloader-agent-compact-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.payloader-agent-compact-item {
  background: var(--bg-primary);
  border: 1px solid var(--border-color);
  border-radius: 10px;
  padding: 12px;
}

.payloader-agent-compact-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 8px;
}

.payloader-agent-compact-line {
  display: flex;
  align-items: flex-start;
  gap: 8px;
}

.payloader-agent-compact-line + .payloader-agent-compact-line {
  margin-top: 6px;
}

.payloader-agent-compact-text {
  flex: 1;
  min-width: 0;
  font-size: 12px;
  line-height: 1.6;
  color: var(--text-primary);
  word-break: break-word;
}

.payloader-agent-action-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.payloader-agent-action-item {
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: 10px;
  padding: 12px;
  box-shadow: var(--shadow-sm);
}

.payloader-agent-action-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 8px;
}

.payloader-agent-action-block {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.payloader-agent-action-label {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-secondary);
}

.payloader-agent-action-tool {
  font-size: 13px;
  font-weight: 700;
  color: var(--primary-color);
}

.payloader-agent-action-time {
  font-size: 11px;
  color: var(--text-secondary);
  white-space: nowrap;
}

.payloader-agent-action-args {
  margin: 0 0 10px;
  padding: 10px 12px;
  border: 1px solid rgba(66, 153, 225, 0.18);
  border-radius: 8px;
  background: rgba(66, 153, 225, 0.08);
  color: var(--text-primary);
  font-size: 13px;
  font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace;
  line-height: 1.7;
  white-space: pre-wrap;
  word-break: break-word;
  overflow-x: auto;
}

.payloader-agent-action-result {
  margin: 0;
  padding: 12px 14px;
  background: var(--bg-primary);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  color: var(--text-primary);
  font-size: 13px;
  font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace;
  line-height: 1.75;
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 240px;
  overflow-y: auto;
  overflow-x: auto;
}

.payloader-agent-action-empty {
  font-size: 12px;
  color: var(--text-secondary);
  padding: 12px 0 4px;
}

[data-theme="light"] .payloader-agent-action-result {
  background: #f8fbff;
  border-color: rgba(66, 153, 225, 0.18);
}

[data-theme="dark"] .payloader-agent-action-args {
  background: rgba(66, 153, 225, 0.12);
  border-color: rgba(96, 165, 250, 0.28);
}

[data-theme="dark"] .payloader-agent-action-result {
  background: rgba(15, 23, 42, 0.72);
  border-color: rgba(148, 163, 184, 0.28);
}

/* Agent 错误 */
.payloader-agent-error {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: var(--spacing-lg);
  text-align: center;
  background: rgba(255, 0, 85, 0.05);
  border: 1px solid rgba(255, 0, 85, 0.3);
  border-radius: 8px;
}

.payloader-agent-error-icon {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: rgba(255, 0, 85, 0.15);
  color: var(--danger-color, #ff0055);
  font-size: 16px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: var(--spacing-sm);
}

.payloader-agent-error-title {
  font-size: 15px;
  color: var(--text-primary);
  margin: 0 0 var(--spacing-sm) 0;
}

.payloader-agent-error-desc {
  font-size: 13px;
  color: var(--text-secondary);
  margin: 0 0 var(--spacing-md) 0;
}

/* Agent 结果 */
.payloader-agent-result {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-lg);
}

/* 渗透攻击类型 */
.payloader-agent-attack-type {
  margin-bottom: var(--spacing-md);
}

.payloader-agent-attack-type-content {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm);
  padding: 16px;
  background: linear-gradient(135deg, rgba(255, 0, 85, 0.05), rgba(255, 102, 0, 0.05));
  border: 1px solid rgba(255, 0, 85, 0.2);
  border-radius: 8px;
}

.payloader-agent-attack-type-badge {
  display: inline-block;
  padding: 6px 16px;
  background: linear-gradient(135deg, rgba(255, 0, 85, 0.15), rgba(255, 102, 0, 0.15));
  border: 1px solid rgba(255, 0, 85, 0.3);
  border-radius: 20px;
  color: var(--danger-color, #ff0055);
  font-size: 14px;
  font-weight: 600;
  text-align: center;
}

.payloader-agent-attack-desc {
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.6;
  margin: 0;
}

/* 扫描结果 */
.payloader-agent-scan-results {
  margin-bottom: var(--spacing-md);
}

.payloader-agent-summary {
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  padding: 20px;
}

.payloader-agent-summary-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--spacing-sm);
}

.payloader-agent-summary-header h3 {
  font-size: 15px;
  font-weight: 600;
  color: var(--primary-color);
  margin: 0;
}

.payloader-agent-status {
  font-size: 11px;
  font-weight: 600;
  padding: 3px 10px;
  border-radius: 4px;
  text-transform: uppercase;
}

.payloader-agent-status.completed {
  background: rgba(0, 255, 136, 0.15);
  color: var(--success-color, #00ff88);
}

.payloader-agent-status.failed {
  background: rgba(255, 0, 85, 0.15);
  color: var(--danger-color, #ff0055);
}

.payloader-agent-status.running {
  background: rgba(0, 240, 255, 0.15);
  color: var(--primary-color);
}

.payloader-agent-summary-text {
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.8;
  margin: 0;
}

/* Agent section */
.payloader-agent-section {
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  padding: 20px;
}

.payloader-agent-section-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--primary-color);
  margin: 0 0 var(--spacing-md) 0;
}

/* Agent steps */
.payloader-agent-steps {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.payloader-agent-step {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  padding: 8px 12px;
  background: var(--bg-tertiary);
  border-radius: 6px;
}

.payloader-agent-step-status {
  font-size: 10px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 4px;
  text-transform: uppercase;
}

.payloader-agent-step-status.completed {
  background: rgba(0, 255, 136, 0.15);
  color: var(--success-color, #00ff88);
}

.payloader-agent-step-status.failed {
  background: rgba(255, 0, 85, 0.15);
  color: var(--danger-color, #ff0055);
}

.payloader-agent-step-status.running {
  background: rgba(0, 240, 255, 0.15);
  color: var(--primary-color);
}

.payloader-agent-step-status.pending,
.payloader-agent-step-status.skipped {
  background: var(--bg-secondary);
  color: var(--text-tertiary);
}

.payloader-agent-step-title {
  font-size: 13px;
  color: var(--text-primary);
}

/* Agent traces */
.payloader-agent-traces {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.payloader-agent-trace {
  background: var(--bg-tertiary);
  border: 1px solid var(--border-color);
  border-radius: 6px;
  padding: 12px;
}

.payloader-agent-trace-header {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  margin-bottom: 6px;
}

.payloader-agent-trace-tool {
  font-size: 12px;
  font-weight: 600;
  color: var(--primary-color);
}

.payloader-agent-trace-status {
  font-size: 10px;
  font-weight: 600;
  padding: 2px 6px;
  border-radius: 3px;
  text-transform: uppercase;
}

.payloader-agent-trace-status.completed {
  background: rgba(0, 255, 136, 0.15);
  color: var(--success-color, #00ff88);
}

.payloader-agent-trace-status.failed {
  background: rgba(255, 0, 85, 0.15);
  color: var(--danger-color, #ff0055);
}

.payloader-agent-trace-duration {
  font-size: 11px;
  color: var(--text-tertiary);
  margin-left: auto;
}

.payloader-agent-trace-summary,
.payloader-agent-trace-output {
  font-size: 12px;
  color: var(--text-secondary);
  line-height: 1.5;
  margin: 4px 0 0 0;
  word-break: break-all;
}

.payloader-agent-trace-error {
  font-size: 12px;
  color: var(--danger-color, #ff0055);
  margin: 4px 0 0 0;
}

/* Agent risks/recommendations/commands */
.payloader-agent-risks,
.payloader-agent-recommendations,
.payloader-agent-commands {
  margin-bottom: var(--spacing-md);
}

.payloader-agent-risks ul,
.payloader-agent-recommendations ul {
  list-style: none;
  padding: 0;
  margin: 0;
}

.payloader-agent-risks li {
  font-size: 13px;
  color: var(--danger-color, #ff0055);
  padding: 6px 0;
  padding-left: 20px;
  position: relative;
}

.payloader-agent-risks li::before {
  content: '!';
  position: absolute;
  left: 0;
  font-weight: 700;
}

.payloader-agent-recommendations li {
  font-size: 13px;
  color: var(--text-secondary);
  padding: 6px 0;
  padding-left: 20px;
  position: relative;
  line-height: 1.6;
}

.payloader-agent-recommendations li::before {
  content: '>';
  position: absolute;
  left: 0;
  color: var(--primary-color);
  font-weight: 700;
}

.payloader-agent-command {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  margin-bottom: var(--spacing-sm);
}

.payloader-agent-command pre {
  flex: 1;
  margin: 0;
}

/* Agent skill results */
.payloader-agent-skill-result {
  background: var(--bg-tertiary);
  border: 1px solid var(--border-color);
  border-radius: 6px;
  padding: 12px;
  margin-bottom: 8px;
}

.payloader-agent-skill-header {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  margin-bottom: 6px;
}

.payloader-agent-skill-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
}

.payloader-agent-skill-risk {
  font-size: 10px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 4px;
  text-transform: uppercase;
}

.payloader-agent-skill-risk.critical,
.payloader-agent-skill-risk.high {
  background: rgba(255, 0, 85, 0.15);
  color: var(--danger-color, #ff0055);
}

.payloader-agent-skill-risk.medium {
  background: rgba(255, 165, 0, 0.15);
  color: #ffa500;
}

.payloader-agent-skill-risk.low,
.payloader-agent-skill-risk.info {
  background: rgba(0, 255, 136, 0.15);
  color: var(--success-color, #00ff88);
}

.payloader-agent-report-section .payloader-agent-report-content {
  font-size: 13px;
  line-height: 1.6;
  color: var(--text-primary);
}
.payloader-agent-report-content p { margin: 0 0 10px; }
.payloader-agent-report-content h1 { font-size: 1.4em; font-weight: 600; margin: 16px 0 8px; color: var(--text-primary); }
.payloader-agent-report-content h2 { font-size: 1.2em; font-weight: 600; margin: 14px 0 6px; color: var(--text-primary); border-bottom: 1px solid var(--border-color); padding-bottom: 4px; }
.payloader-agent-report-content h3 { font-size: 1.1em; font-weight: 600; margin: 10px 0 4px; color: var(--text-primary); }
.payloader-agent-report-content strong { color: var(--text-primary); }
.payloader-agent-report-content code { background: var(--bg-secondary); padding: 2px 6px; border-radius: 4px; font-family: monospace; font-size: 0.9em; }
.payloader-agent-report-content pre { margin: 10px 0; padding: 12px; background: var(--bg-secondary); border: 1px solid var(--border-color); border-radius: 8px; overflow-x: auto; white-space: pre-wrap; }
.payloader-agent-report-content pre code { display: block; padding: 0; background: transparent; border-radius: 0; }
.payloader-agent-report-content ul,
.payloader-agent-report-content ol { margin: 8px 0 12px 18px; padding: 0; }
.payloader-agent-report-content li { margin: 4px 0; padding-left: 4px; }
.payloader-agent-report-content hr { border: none; border-top: 1px solid var(--border-color); margin: 12px 0; }

.payloader-agent-skill-summary {
  font-size: 12px;
  color: var(--text-secondary);
  line-height: 1.5;
  margin: 0;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

/* 渗透结果分析区块 */
.payloader-agent-analysis {
  background: rgba(255, 87, 34, 0.05);
  border: 1px solid rgba(255, 87, 34, 0.2);
  border-radius: 8px;
}

.payloader-agent-section-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 12px 0;
  display: flex;
  align-items: center;
  gap: 8px;
}

.payloader-agent-section-title svg {
  flex-shrink: 0;
}

.payloader-agent-analysis-label {
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: var(--text-tertiary);
  margin-bottom: 6px;
}

.payloader-agent-analysis-value {
  margin-bottom: 16px;
}

.payloader-agent-attack-type-badge {
  display: inline-block;
  background: linear-gradient(135deg, #ff5722, #ff9800);
  color: #fff;
  padding: 4px 14px;
  border-radius: 16px;
  font-size: 13px;
  font-weight: 600;
  letter-spacing: 0.5px;
}

.payloader-agent-attack-desc {
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.6;
  margin-top: 8px;
}

.payloader-agent-scan-results {
  margin-bottom: 16px;
}

.payloader-agent-scan-results .payloader-detail-code {
  max-height: 200px;
  overflow-y: auto;
}

.payloader-agent-risks {
  margin-bottom: 0;
}

.payloader-agent-risk-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.payloader-agent-risk-item {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.5;
  background: rgba(255, 87, 34, 0.08);
  padding: 10px 12px;
  border-radius: 6px;
  border-left: 3px solid #ff5722;
}

.payloader-agent-risk-icon {
  flex-shrink: 0;
  font-size: 14px;
}

/* 安全防护建议区块 */
.payloader-agent-suggestions {
  background: rgba(76, 175, 80, 0.05);
  border: 1px solid rgba(76, 175, 80, 0.2);
  border-radius: 8px;
}

.payloader-agent-recommendations {
  margin-bottom: 16px;
}

.payloader-agent-suggestion-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.payloader-agent-suggestion-item {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.5;
  background: rgba(76, 175, 80, 0.08);
  padding: 10px 12px;
  border-radius: 6px;
  border-left: 3px solid #4caf50;
}

.payloader-agent-suggestion-icon {
  flex-shrink: 0;
  font-size: 14px;
  color: #4caf50;
  font-weight: bold;
}

.payloader-agent-commands {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.payloader-agent-command {
  display: flex;
  gap: 8px;
  align-items: flex-start;
}

.payloader-agent-command .payloader-detail-code {
  flex: 1;
  margin: 0;
}

.payloader-agent-command .payloader-btn--sm {
  flex-shrink: 0;
  margin-top: 4px;
}

/* 使用的 Skills 区块 */
.payloader-agent-skills-section {
  background: rgba(103, 58, 183, 0.05);
  border: 1px solid rgba(103, 58, 183, 0.2);
  border-radius: 8px;
}

.payloader-agent-skills-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 12px;
}

.payloader-agent-skill-card {
  background: var(--bg-tertiary);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  padding: 12px;
  transition: all 0.2s ease;
}

.payloader-agent-skill-card:hover {
  border-color: var(--primary-color);
  transform: translateY(-1px);
}

.payloader-agent-skill-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 6px;
}

.payloader-agent-skill-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
  font-family: var(--font-mono);
}

.payloader-agent-skill-risk {
  font-size: 10px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  padding: 2px 8px;
  border-radius: 10px;
}

.payloader-agent-skill-risk.critical,
.payloader-agent-skill-risk.high {
  background: rgba(244, 67, 54, 0.2);
  color: #f44336;
}

.payloader-agent-skill-risk.medium {
  background: rgba(255, 152, 0, 0.2);
  color: #ff9800;
}

.payloader-agent-skill-risk.low,
.payloader-agent-skill-risk.info {
  background: rgba(76, 175, 80, 0.2);
  color: #4caf50;
}

.payloader-agent-skill-summary {
  font-size: 12px;
  color: var(--text-secondary);
  line-height: 1.5;
  margin: 0;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

/* Agent empty */
.payloader-agent-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--spacing-xl);
}

.payloader-agent-empty p {
  font-size: 14px;
  color: var(--text-tertiary);
}

/* Agent 面板（列表模式） */
.payloader-agent-panel {
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: var(--border-radius);
  padding: var(--spacing-lg);
  margin: var(--spacing-lg);
}

.payloader-agent-panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--spacing-md);
  padding-bottom: var(--spacing-sm);
  border-bottom: 1px solid var(--border-color);
}

.payloader-agent-panel-header h3 {
  font-size: 15px;
  font-weight: 600;
  color: var(--primary-color);
  margin: 0;
}

/* Agent URL 弹窗 */
.payloader-modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.6);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 10000;
  animation: fadeIn 0.2s ease;
}

@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

@keyframes slideUp {
  from { opacity: 0; transform: translateY(20px) scale(0.95); }
  to { opacity: 1; transform: translateY(0) scale(1); }
}

.payloader-modal {
  background: var(--bg-secondary, #1e1e2e);
  border: 1px solid var(--border-color, rgba(255, 255, 255, 0.1));
  border-radius: 16px;
  width: 520px;
  max-width: 90vw;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5), 0 0 0 1px rgba(59, 130, 246, 0.1);
  animation: slideUp 0.3s ease;
}

.payloader-modal--confirm {
  width: 460px;
}

.payloader-modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20px 24px 16px;
  border-bottom: 1px solid var(--border-color, rgba(255, 255, 255, 0.06));
}

.payloader-modal-header h3 {
  font-size: 18px;
  font-weight: 600;
  color: var(--text-primary, #e4e4e7);
  margin: 0;
}

.payloader-modal-close {
  width: 32px;
  height: 32px;
  background: transparent;
  border: none;
  border-radius: 8px;
  color: var(--text-secondary, #a1a1aa);
  font-size: 20px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
}

.payloader-modal-close:hover {
  background: var(--bg-tertiary, rgba(255, 255, 255, 0.05));
  color: var(--text-primary, #e4e4e7);
}

.payloader-btn--danger {
  background: linear-gradient(135deg, #ef4444, #dc2626);
  border-color: #dc2626;
  color: #fff;
}

.payloader-btn--danger:hover:not(:disabled) {
  background: linear-gradient(135deg, #dc2626, #b91c1c);
  border-color: #b91c1c;
  box-shadow: 0 4px 12px rgba(220, 38, 38, 0.28);
}

.payloader-modal-body {
  padding: 20px 24px;
}

.payloader-modal-desc {
  font-size: 14px;
  color: var(--text-secondary, #a1a1aa);
  line-height: 1.6;
  margin: 0 0 20px;
}

.payloader-modal-input-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.payloader-modal-input-group--mode {
  margin-top: 14px;
}

.payloader-modal-label {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-primary, #e4e4e7);
}

.payloader-modal-input {
  width: 100%;
  padding: 12px 16px;
  background: var(--bg-primary, #12121a);
  border: 1px solid var(--border-color, rgba(255, 255, 255, 0.1));
  border-radius: 10px;
  color: var(--text-primary, #e4e4e7);
  font-size: 14px;
  font-family: var(--font-mono, 'Fira Code', 'Consolas', monospace);
  outline: none;
  transition: all 0.2s;
  box-sizing: border-box;
}

.payloader-modal-input:focus {
  border-color: var(--primary-color, #3b82f6);
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.15);
}

.payloader-modal-input::placeholder {
  color: var(--text-tertiary, #71717a);
}

.payloader-modal-helper {
  margin: 0;
  font-size: 12px;
  line-height: 1.5;
  color: var(--text-secondary, #a1a1aa);
}

.payloader-mode-toggle {
  display: flex;
  width: 100%;
  border-radius: 10px;
  border: 1px solid var(--border-color, rgba(255, 255, 255, 0.1));
  background: var(--bg-primary, #12121a);
  overflow: hidden;
}

.payloader-mode-toggle-btn {
  flex: 1;
  padding: 10px 12px;
  border: none;
  background: transparent;
  color: var(--text-secondary, #a1a1aa);
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
}

.payloader-mode-toggle-btn:not(.active):hover {
  background: var(--bg-tertiary, rgba(255, 255, 255, 0.04));
  color: var(--text-primary, #e4e4e7);
}

.payloader-mode-toggle-btn.active {
  background: var(--primary-color, #3b82f6);
  color: #fff;
}

.payloader-modal-error {
  margin-top: 12px;
  padding: 10px 14px;
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.2);
  border-radius: 8px;
  font-size: 13px;
  color: #f87171;
}

.payloader-modal-footer {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 12px;
  padding: 16px 24px 20px;
  border-top: 1px solid var(--border-color, rgba(255, 255, 255, 0.06));
}

/* 结果弹窗特有样式 */
.payloader-modal--result {
  width: 680px;
  max-height: 85vh;
  display: flex;
  flex-direction: column;
}

.payloader-modal-body--scroll {
  overflow-y: auto;
  max-height: calc(85vh - 140px);
}

.payloader-agent-running-sub {
  font-size: 12px;
  color: var(--text-tertiary);
  margin-top: 4px;
}

/* ── 目标画像样式 ── */
.payloader-target-profile-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 12px;
}

.payloader-target-profile-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 10px;
  background: var(--bg-tertiary);
  border-radius: 8px;
  border: 1px solid var(--border-color);
}

.payloader-target-profile-label {
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: var(--text-tertiary);
}

.payloader-target-profile-value {
  font-size: 13px;
  color: var(--text-primary);
  font-family: var(--font-mono);
  word-break: break-all;
}

/* ── 阶段验证链样式 ── */
.payloader-phase-chain {
  display: flex;
  flex-direction: column;
  gap: 0;
}

.payloader-phase-node-wrapper {
  display: flex;
  flex-direction: column;
  align-items: stretch;
}

.payloader-phase-node {
  padding: 16px;
  background: var(--bg-tertiary);
  border: 1px solid var(--border-color);
  border-radius: 10px;
  transition: all 0.2s ease;
}

.payloader-phase-node:hover {
  border-color: var(--primary-color);
  transform: translateY(-1px);
}

.payloader-phase-node--completed {
  border-left: 3px solid var(--success-color, #00ff88);
}

.payloader-phase-node--failed {
  border-left: 3px solid var(--danger-color, #ff0055);
}

.payloader-phase-node--partial {
  border-left: 3px solid #ffa500;
}

.payloader-phase-node--skipped {
  border-left: 3px solid var(--text-tertiary);
  opacity: 0.7;
}

.payloader-phase-node-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.payloader-phase-step {
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 2px;
  padding: 3px 10px;
  border-radius: 4px;
  background: rgba(0, 240, 255, 0.1);
  color: var(--primary-color);
  border: 1px solid rgba(0, 240, 255, 0.3);
}

.payloader-phase-status {
  font-size: 12px;
  font-weight: 500;
}

.payloader-phase-node-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 6px 0;
}

.payloader-phase-node-summary {
  font-size: 12px;
  color: var(--text-secondary);
  line-height: 1.5;
  margin: 0 0 8px 0;
}

.payloader-phase-node-meta {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 11px;
}

.payloader-phase-evidence {
  color: var(--text-tertiary);
}

.payloader-phase-risk {
  color: var(--danger-color, #ff0055);
  font-weight: 500;
}

.payloader-phase-connector {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 4px 0;
}

.payloader-phase-arrow {
  width: 2px;
  height: 16px;
  background: linear-gradient(180deg, var(--primary-color), var(--accent-color, #a855f7));
}

/* ── 验证链样式 ── */
.payloader-validation-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.payloader-validation-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 6px;
  border-left: 3px solid;
}

.payloader-validation-item.validated {
  background: rgba(0, 255, 136, 0.05);
  border-left-color: var(--success-color, #00ff88);
}

.payloader-validation-item.unvalidated {
  background: rgba(255, 0, 85, 0.05);
  border-left-color: var(--danger-color, #ff0055);
}

.payloader-validation-icon {
  flex-shrink: 0;
  font-size: 14px;
}

.payloader-validation-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.payloader-validation-finding {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-primary);
}

.payloader-validation-conclusion {
  font-size: 11px;
  color: var(--text-secondary);
}

.payloader-validation-severity {
  font-size: 10px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  padding: 2px 8px;
  border-radius: 10px;
}

.payloader-validation-severity.critical,
.payloader-validation-severity.high {
  background: rgba(244, 67, 54, 0.2);
  color: #f44336;
}

.payloader-validation-severity.medium {
  background: rgba(255, 152, 0, 0.2);
  color: #ff9800;
}

.payloader-validation-severity.low,
.payloader-validation-severity.info {
  background: rgba(76, 175, 80, 0.2);
  color: #4caf50;
}

/* ── 风险假设样式 ── */
.payloader-hypothesis-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.payloader-hypothesis-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  background: rgba(255, 152, 0, 0.05);
  border: 1px solid rgba(255, 152, 0, 0.2);
  border-radius: 6px;
}

.payloader-hypothesis-severity {
  font-size: 10px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  padding: 2px 8px;
  border-radius: 10px;
  flex-shrink: 0;
}

.payloader-hypothesis-severity.critical,
.payloader-hypothesis-severity.high {
  background: rgba(244, 67, 54, 0.2);
  color: #f44336;
}

.payloader-hypothesis-severity.medium {
  background: rgba(255, 152, 0, 0.2);
  color: #ff9800;
}

.payloader-hypothesis-severity.low {
  background: rgba(76, 175, 80, 0.2);
  color: #4caf50;
}

.payloader-hypothesis-text {
  flex: 1;
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.5;
}

.payloader-hypothesis-confidence {
  font-size: 11px;
  color: var(--text-tertiary);
  flex-shrink: 0;
}

/* ── Agent 阶段概览（确认弹窗中） ── */
.payloader-agent-phases-overview {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-top: 16px;
}

.payloader-agent-phase-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 14px;
  background: var(--bg-tertiary);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  border-left: 3px solid var(--primary-color);
}

.payloader-agent-phase-num {
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  background: linear-gradient(135deg, rgba(0, 240, 255, 0.2), rgba(168, 85, 247, 0.2));
  border: 1px solid var(--primary-color);
  color: var(--primary-color);
  font-size: 13px;
  font-weight: 700;
  flex-shrink: 0;
}

.payloader-agent-phase-label {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-primary);
}

/* ── 日志模态框 ── */
.payloader-modal--log {
  width: 85vw;
  max-width: 1200px;
  height: 80vh;
  display: flex;
  flex-direction: column;
}

.payloader-modal-header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.payloader-log-header-main {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.payloader-log-header-sub {
  margin: 0;
  font-size: 12px;
  color: var(--text-secondary);
  word-break: break-all;
}

.payloader-modal-header-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  background: var(--bg-tertiary);
  border: 1px solid var(--border-color);
  border-radius: var(--border-radius);
  color: var(--text-primary);
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.payloader-modal-header-btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.payloader-modal-header-btn:hover {
  background: var(--primary-color);
  color: #fff;
  border-color: var(--primary-color);
}

.payloader-modal-header-btn:disabled:hover {
  background: var(--bg-tertiary);
  color: var(--text-primary);
  border-color: var(--border-color);
}

.payloader-log-body {
  flex: 1;
  overflow-y: auto;
  background: var(--bg-tertiary);
  padding: 16px;
}

.payloader-log-report-section {
  margin-bottom: 18px;
  border: 1px solid var(--border-color);
  border-radius: 10px;
  background: var(--bg-secondary);
  padding: 16px 18px;
}

.payloader-log-report-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 14px;
}

.payloader-log-report-eyebrow {
  font-size: 12px;
  font-weight: 600;
  color: var(--primary-color);
  text-transform: uppercase;
  letter-spacing: 0.4px;
  margin-bottom: 4px;
}

.payloader-log-report-header h4 {
  margin: 0;
  font-size: 18px;
  line-height: 1.3;
  color: var(--text-primary);
}

.payloader-log-jump-btn {
  flex-shrink: 0;
  padding: 8px 12px;
  border: 1px solid var(--border-color);
  border-radius: 8px;
  background: var(--bg-primary);
  color: var(--text-primary);
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.2s ease, border-color 0.2s ease;
}

.payloader-log-jump-btn:hover {
  background: rgba(59, 130, 246, 0.08);
  border-color: rgba(59, 130, 246, 0.3);
}

.payloader-log-empty {
  text-align: center;
  color: var(--text-secondary);
  padding: 40px 0;
}

.payloader-log-empty--error {
  color: var(--error-color);
}

.payloader-log-round-group {
  margin-bottom: 18px;
  border: 1px solid var(--border-color);
  border-radius: 10px;
  overflow: hidden;
  background: var(--bg-secondary);
}

.payloader-log-round-header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 14px;
  background: linear-gradient(90deg, rgba(59, 130, 246, 0.12), rgba(16, 185, 129, 0.08));
  border-bottom: 1px solid var(--border-color);
  font-size: 12px;
}

.payloader-log-round-count {
  color: var(--text-secondary);
  font-weight: 600;
}

.payloader-log-entry {
  margin: 0 12px 12px;
  border: 1px solid var(--border-color);
  border-radius: 8px;
  overflow: hidden;
  background: var(--bg-secondary);
}

.payloader-log-meta {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 14px;
  background: var(--bg-primary);
  border-bottom: 1px solid var(--border-color);
  font-size: 12px;
}

.payloader-log-round {
  color: var(--primary-color);
  font-weight: 700;
  font-size: 13px;
}

.payloader-log-tool {
  color: var(--accent-color, var(--primary-color));
  font-weight: 600;
  font-size: 13px;
}

.payloader-log-task {
  color: var(--primary-color);
  font-weight: 700;
  font-size: 12px;
}

.payloader-log-surface {
  color: var(--text-secondary);
  font-size: 12px;
  max-width: 320px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.payloader-log-status {
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 600;
}

.payloader-log-status--running {
  background: rgba(66, 153, 225, 0.15);
  color: var(--primary-color);
}

.payloader-log-status--completed {
  background: rgba(72, 187, 120, 0.15);
  color: var(--success-color);
}

.payloader-log-status--failed {
  background: rgba(245, 101, 101, 0.15);
  color: var(--error-color);
}

.payloader-log-status--dry_run {
  background: rgba(237, 137, 54, 0.15);
  color: var(--warning-color);
}

.payloader-log-time {
  color: var(--text-secondary);
  margin-left: auto;
}

.payloader-log-rc {
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 600;
}

.payloader-log-rc.ok {
  background: var(--success-color, #238636);
  color: #fff;
}

.payloader-log-rc.err {
  background: var(--error-color, #da3633);
  color: #fff;
}

.payloader-log-think,
.payloader-log-args,
.payloader-log-stdout,
.payloader-log-error {
  padding: 12px 14px;
  border-bottom: 1px solid var(--border-color);
}

.payloader-log-round-group > .payloader-log-think {
  background: rgba(59, 130, 246, 0.03);
}

.payloader-log-think-label,
.payloader-log-args-label,
.payloader-log-stdout-label,
.payloader-log-error-label {
  font-size: 12px;
  font-weight: 600;
  margin-bottom: 8px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.payloader-log-think-label { color: var(--primary-color); }
.payloader-log-args-label { color: var(--info-color, var(--primary-color)); }
.payloader-log-stdout-label { color: var(--success-color, #3fb950); }
.payloader-log-error-label { color: var(--error-color, #f85149); }

.payloader-log-think-content {
  color: var(--text-primary);
  font-size: 13px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
  font-family: inherit;
}

.payloader-log-code {
  margin: 0;
  padding: 10px 12px;
  background: var(--bg-primary);
  border: 1px solid var(--border-color);
  border-radius: 6px;
  color: var(--text-primary);
  font-family: 'JetBrains Mono', 'Fira Code', 'Consolas', monospace;
  font-size: 12px;
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-word;
  overflow-x: auto;
  max-height: 300px;
  overflow-y: auto;
}

/* ── 历史按钮 ── */
.payloader-btn--history {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: var(--border-radius);
  color: var(--text-primary);
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s ease;
  white-space: nowrap;
}

.payloader-btn--history:hover {
  background: var(--bg-tertiary);
  border-color: var(--primary-color);
  color: var(--primary-color);
}

/* ── 历史弹窗 ── */
.payloader-modal--history {
  width: 600px;
  max-height: 70vh;
  display: flex;
  flex-direction: column;
}

.payloader-history-item {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 14px;
  border-bottom: 1px solid var(--border-color);
  transition: background 0.15s ease;
}

.payloader-history-item:hover {
  background: var(--bg-tertiary);
}

.payloader-history-main {
  flex: 1;
  min-width: 0;
}

.payloader-history-target {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 4px;
}

.payloader-history-meta {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 12px;
}

.payloader-history-time {
  color: var(--text-secondary);
}

.payloader-history-status {
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
}

.payloader-history-status.running {
  background: #e6a23c33;
  color: #e6a23c;
}

.payloader-history-status.done {
  background: #67c23a33;
  color: #67c23a;
}

.payloader-history-status.stopped {
  background: #f56c6c33;
  color: #f56c6c;
}

.payloader-history-phase {
  color: var(--text-secondary);
}

.payloader-history-stats {
  display: flex;
  gap: 12px;
  font-size: 13px;
  color: var(--text-secondary);
}

.payloader-history-actions {
  display: flex;
  gap: 6px;
}

.payloader-btn--sm {
  padding: 4px 10px;
  font-size: 12px;
}
</style>

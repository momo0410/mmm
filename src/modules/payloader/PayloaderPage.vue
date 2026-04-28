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
          class="payloader-btn payloader-btn--primary" 
          @click="refresh" 
          :disabled="isLoading"
          title="刷新"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" :class="{ 'spinning': isLoading }">
            <path d="M23 4v6h-6"></path>
            <path d="M1 20v-6h6"></path>
            <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"></path>
          </svg>
        </button>
      </template>
    </PayloaderToolbar>

    <PayloaderContent>
      <!-- Agent 启动确认弹窗 -->
      <div v-if="showUrlModal" class="payloader-modal-overlay" @click.self="showUrlModal = false">
        <div class="payloader-modal">
          <div class="payloader-modal-header">
            <h3>一键渗透检测</h3>
            <button class="payloader-modal-close" @click="showUrlModal = false">&times;</button>
          </div>
          <div class="payloader-modal-body">
            <p class="payloader-modal-desc">将自动对当前连接的主机系统执行以下5阶段安全检测：</p>
            <div class="payloader-agent-phases-overview">
              <div class="payloader-agent-phase-item">
                <span class="payloader-agent-phase-num">1</span>
                <span class="payloader-agent-phase-label">侦察与信息收集</span>
              </div>
              <div class="payloader-agent-phase-item">
                <span class="payloader-agent-phase-num">2</span>
                <span class="payloader-agent-phase-label">漏洞发现与分析</span>
              </div>
              <div class="payloader-agent-phase-item">
                <span class="payloader-agent-phase-num">3</span>
                <span class="payloader-agent-phase-label">漏洞利用与权限提升</span>
              </div>
              <div class="payloader-agent-phase-item">
                <span class="payloader-agent-phase-num">4</span>
                <span class="payloader-agent-phase-label">证据收集与风险验证</span>
              </div>
              <div class="payloader-agent-phase-item">
                <span class="payloader-agent-phase-num">5</span>
                <span class="payloader-agent-phase-label">报告与修复验证</span>
              </div>
            </div>
          </div>
          <div class="payloader-modal-footer">
            <button class="payloader-btn payloader-btn--secondary" @click="showUrlModal = false">取消</button>
            <button
              class="payloader-btn payloader-btn--primary"
              :disabled="agentRunning"
              @click="startHostAgent"
            >
              {{ agentRunning ? '运行中...' : '开始检测' }}
            </button>
          </div>
        </div>
      </div>

      <!-- Agent 结果弹窗 -->
      <div v-if="showResultModal" class="payloader-modal-overlay" @click.self="!agentRunning && (showResultModal = false)">
        <div class="payloader-modal payloader-modal--result">
          <div class="payloader-modal-header">
            <h3>渗透结果分析</h3>
            <button v-if="!agentRunning" class="payloader-modal-close" @click="showResultModal = false">&times;</button>
          </div>
          <div class="payloader-modal-body payloader-modal-body--scroll">
            <!-- 运行中 -->
            <div v-if="agentRunning" class="payloader-agent-running">
              <div class="payloader-agent-running-spinner"></div>
              <p class="payloader-agent-running-text">正在执行一键渗透检测...</p>
              <p class="payloader-agent-running-sub">5 阶段自动化验证链</p>
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
            <button class="payloader-btn payloader-btn--secondary" @click="showResultModal = false">关闭</button>
            <button class="payloader-btn payloader-btn--primary" @click="showResultModal = false; startHostAgent()">重新检测</button>
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
                    <span class="payloader-chain-connector-label">→</span>
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
import { ref, computed } from 'vue';
import PayloaderToolbar from './components/PayloaderToolbar.vue';
import PayloaderContent from './components/PayloaderContent.vue';
import EncodingTools from './components/EncodingTools.vue';
import { usePayloader } from './composables/usePayloaderState';
import type { PayloadItem, ToolCommand, I18nText } from './types';

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

document.addEventListener('click', (e) => {
  const target = e.target as HTMLElement;
  if (!target.closest('.payloader-dropdown')) {
    showViewDropdown.value = false;
    showCategoryDropdown.value = false;
  }
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
  padding: 4px 0;
}

.payloader-chain-arrow {
  width: 2px;
  height: 20px;
  background: linear-gradient(180deg, var(--primary-color), var(--accent-color, #a855f7));
}

.payloader-chain-connector-label {
  font-size: 16px;
  color: var(--primary-color);
  font-weight: 700;
  transform: rotate(90deg);
  line-height: 1;
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
}

.payloader-agent-running-text {
  font-size: 14px;
  color: var(--primary-color);
  font-weight: 500;
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
</style>

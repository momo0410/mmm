<template>
  <div class="payloader-panel" :class="{ 'payloader-panel--hover': hoverable }">
    <div v-if="title" class="payloader-panel__header">
      <h3 class="payloader-panel__title">{{ title }}</h3>
      <slot name="header-actions"></slot>
    </div>
    <div class="payloader-panel__content">
      <slot></slot>
    </div>
  </div>
</template>

<script setup lang="ts">
interface Props {
  title?: string;
  hoverable?: boolean;
}

withDefaults(defineProps<Props>(), {
  title: '',
  hoverable: true,
});
</script>

<style scoped>
.payloader-panel {
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: var(--border-radius-lg);
  box-shadow: var(--shadow-sm);
  overflow: hidden;
  transition: all 0.2s ease;
}

.payloader-panel--hover:hover {
  box-shadow: var(--shadow-md);
  border-color: var(--primary-color);
  transform: translateY(-2px);
}

.payloader-panel__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--spacing-md) var(--spacing-lg);
  border-bottom: 1px solid var(--border-color);
  background: var(--bg-tertiary);
}

.payloader-panel__title {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

.payloader-panel__content {
  padding: var(--spacing-lg);
}
</style>

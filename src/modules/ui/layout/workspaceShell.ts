import type { AppPage } from '../pageTypes';

export function renderWorkspaceShell(content: string): string {
  return `
    <div class="main-workspace">
      <div class="workspace-content page-transition" id="workspace-content">
        ${content}
      </div>
    </div>
  `;
}

export function renderPageContainer(pageId: AppPage, content: string, isVisible: boolean): string {
  const display = isVisible ? 'block' : 'none';
  return `
    <div class="page-container" id="page-${pageId}" style="display:${display}">
      ${content}
    </div>
  `;
}

import type React from 'react';
import { useEffect, useRef, useState } from 'react';
import { useAuth, useSystemConfig } from '../hooks';
import { createParsedApiError, getParsedApiError, type ParsedApiError } from '../api/error';
import { alphasiftApi, notifyAlphaSiftConfigChanged, notifySystemConfigChanged } from '../api/alphasift';
import { systemConfigApi } from '../api/systemConfig';
import { ApiErrorAlert, Button, ConfirmDialog, EmptyState } from '../components/common';
import {
  AuthSettingsCard,
  ChangePasswordCard,
  IntelligentImport,
  LLMChannelEditor,
  NotificationTestPanel,
  SettingsCategoryNav,
  SettingsAlert,
  SettingsField,
  SettingsLoading,
  SettingsPanelErrorBoundary,
  SettingsSectionCard,
} from '../components/settings';
import { WEB_BUILD_INFO } from '../utils/constants';
import { getCategoryDescriptionZh } from '../utils/systemConfigI18n';
import type { SystemConfigCategory } from '../types/systemConfig';

type DesktopWindow = Window & {
  dsaDesktop?: {
    version?: unknown;
    getUpdateState?: () => Promise<RawDesktopUpdateState>;
    checkForUpdates?: () => Promise<RawDesktopUpdateState>;
    installDownloadedUpdate?: () => Promise<boolean>;
    openReleasePage?: (releaseUrl?: string) => Promise<boolean>;
    onUpdateStateChange?: (listener: (state: RawDesktopUpdateState) => void) => (() => void) | void;
  };
};

type DesktopUpdateState = {
  status?: string;
  updateMode?: string;
  currentVersion?: string;
  latestVersion?: string;
  releaseUrl?: string;
  checkedAt?: string;
  publishedAt?: string;
  message?: string;
  releaseName?: string;
  tagName?: string;
  downloadPercent?: number | null;
  downloadedBytes?: number | null;
  totalBytes?: number | null;
};

type RawDesktopUpdateState = {
  status?: unknown;
  updateMode?: unknown;
  currentVersion?: unknown;
  latestVersion?: unknown;
  releaseUrl?: unknown;
  checkedAt?: unknown;
  publishedAt?: unknown;
  message?: unknown;
  releaseName?: unknown;
  tagName?: unknown;
  downloadPercent?: unknown;
  downloadedBytes?: unknown;
  totalBytes?: unknown;
};

type DesktopUpdateNotice = {
  title: string;
  message: string;
  variant: 'error' | 'success' | 'warning';
  actionLabel?: string;
  actionKind?: 'release' | 'install';
};

function trimDesktopRuntimeString(value: unknown) {
  return typeof value === 'string' ? value.trim() : '';
}

function normalizeDesktopRuntimeNumber(value: unknown) {
  if (value === null || value === undefined || value === '') {
    return null;
  }
  const numberValue = typeof value === 'number' ? value : Number(value);
  return Number.isFinite(numberValue) ? numberValue : null;
}

function getDesktopRuntimeApi() {
  if (typeof window === 'undefined') {
    return undefined;
  }

  return (window as DesktopWindow).dsaDesktop;
}

function getDesktopAppVersion() {
  return trimDesktopRuntimeString(getDesktopRuntimeApi()?.version);
}

function normalizeDesktopUpdateState(state: RawDesktopUpdateState | null | undefined) {
  if (!state || typeof state !== 'object') {
    return null;
  }

  return {
    status: trimDesktopRuntimeString(state.status) || 'idle',
    updateMode: trimDesktopRuntimeString(state.updateMode) || 'manual',
    currentVersion: trimDesktopRuntimeString(state.currentVersion),
    latestVersion: trimDesktopRuntimeString(state.latestVersion),
    releaseUrl: trimDesktopRuntimeString(state.releaseUrl),
    checkedAt: trimDesktopRuntimeString(state.checkedAt),
    publishedAt: trimDesktopRuntimeString(state.publishedAt),
    message: trimDesktopRuntimeString(state.message),
    releaseName: trimDesktopRuntimeString(state.releaseName),
    tagName: trimDesktopRuntimeString(state.tagName),
    downloadPercent: normalizeDesktopRuntimeNumber(state.downloadPercent),
    downloadedBytes: normalizeDesktopRuntimeNumber(state.downloadedBytes),
    totalBytes: normalizeDesktopRuntimeNumber(state.totalBytes),
  };
}

function getDesktopUpdateNotice(state: DesktopUpdateState | null): DesktopUpdateNotice | null {
  if (!state) {
    return null;
  }

  if (state.status === 'update-available') {
    const latestLabel = state.latestVersion || state.tagName || 'Latest Version';
    const currentLabel = state.currentVersion || getDesktopAppVersion() || 'Current Version';
    return {
      title: 'New Version Available',
      message: `Current: ${currentLabel}, Latest: ${latestLabel}. ${state.message || 'Go to GitHub Releases to download the update.'}`,
      variant: 'warning' as const,
      actionLabel: state.updateMode === 'auto' ? undefined : 'Download',
      actionKind: state.updateMode === 'auto' ? undefined : 'release',
    };
  }

  if (state.status === 'downloading') {
    const percentText = typeof state.downloadPercent === 'number' ? ` (${state.downloadPercent}%)` : '';
    return {
      title: 'Downloading Update',
      message: state.message || `Downloading desktop update in the background${percentText}.`,
      variant: 'warning' as const,
    };
  }

  if (state.status === 'update-downloaded') {
    return {
      title: 'Update Downloaded',
      message: state.message || 'New version downloaded. Restart application to complete installation.',
      variant: 'success' as const,
      actionLabel: 'Restart to Install',
      actionKind: 'install',
    };
  }

  if (state.status === 'installing') {
    return {
      title: 'Installing Update',
      message: state.message || 'Restarting and installing update.',
      variant: 'warning' as const,
    };
  }

  if (state.status === 'up-to-date') {
    return {
      title: 'Up to Date',
      message: state.message || 'Desktop client is up to date.',
      variant: 'success' as const,
    };
  }

  if (state.status === 'checking') {
    return {
      title: 'Checking for Updates',
      message: state.message || 'Checking GitHub Releases for available new versions.',
      variant: 'warning' as const,
    };
  }

  if (state.status === 'error') {
    return {
      title: 'Failed to Check for Updates',
      message: state.message || 'Unable to complete update check, please try again later.',
      variant: 'error' as const,
      actionLabel: state.updateMode === 'auto' && state.releaseUrl ? 'Download' : undefined,
      actionKind: state.updateMode === 'auto' && state.releaseUrl ? 'release' : undefined,
    };
  }

  return null;
}

function formatEnvBackupFilename(isDesktopRuntime: boolean) {
  const now = new Date();
  const pad = (value: number) => value.toString().padStart(2, '0');
  const date = `${now.getFullYear()}${pad(now.getMonth() + 1)}${pad(now.getDate())}`;
  const time = `${pad(now.getHours())}${pad(now.getMinutes())}`;
  return `${isDesktopRuntime ? 'dsa-desktop-env' : 'dsa-env'}_${date}_${time}.env`;
}

const SettingsPage: React.FC = () => {
  const { authEnabled, passwordChangeable } = useAuth();
  const [envBackupActionError, setEnvBackupActionError] = useState<ParsedApiError | null>(null);
  const [envBackupActionSuccess, setEnvBackupActionSuccess] = useState<string>('');
  const [alphaSiftActionError, setAlphaSiftActionError] = useState<ParsedApiError | null>(null);
  const [alphaSiftActionSuccess, setAlphaSiftActionSuccess] = useState<string>('');
  const [isExportingEnv, setIsExportingEnv] = useState(false);
  const [isImportingEnv, setIsImportingEnv] = useState(false);
  const [isUpdatingAlphaSift, setIsUpdatingAlphaSift] = useState(false);
  const [showImportConfirm, setShowImportConfirm] = useState(false);
  const [desktopUpdateState, setDesktopUpdateState] = useState<DesktopUpdateState | null>(null);
  const [isCheckingDesktopUpdate, setIsCheckingDesktopUpdate] = useState(false);
  const envBackupImportRef = useRef<HTMLInputElement | null>(null);
  const desktopRuntimeApi = getDesktopRuntimeApi();
  const isDesktopRuntime = Boolean(desktopRuntimeApi);
  const canCheckDesktopUpdate = Boolean(
    desktopRuntimeApi?.getUpdateState && desktopRuntimeApi?.checkForUpdates && desktopRuntimeApi?.openReleasePage
  );
  const desktopAppVersion = getDesktopAppVersion();
  const shouldShowDesktopVersionCard = Boolean(desktopAppVersion);

  // Set page title
  useEffect(() => {
    document.title = 'System Settings - DSA';
  }, []);

  const {
    categories,
    itemsByCategory,
    issueByKey,
    activeCategory,
    setActiveCategory,
    hasDirty,
    dirtyCount,
    toast,
    clearToast,
    isLoading,
    isSaving,
    loadError,
    saveError,
    retryAction,
    load,
    retry,
    save,
    resetDraft,
    setDraftValue,
    getChangedItems,
    refreshAfterExternalSave,
    configVersion,
    maskToken,
  } = useSystemConfig();

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    if (!toast) {
      return;
    }

    const timer = window.setTimeout(() => {
      clearToast();
    }, 3200);

    return () => {
      window.clearTimeout(timer);
    };
  }, [clearToast, toast]);

  useEffect(() => {
    if (!canCheckDesktopUpdate) {
      setDesktopUpdateState(null);
      setIsCheckingDesktopUpdate(false);
      return;
    }

    let active = true;

    const syncDesktopUpdateState = async () => {
      try {
        const state = await desktopRuntimeApi?.getUpdateState?.();
        if (active) {
          setDesktopUpdateState(normalizeDesktopUpdateState(state));
        }
      } catch (error: unknown) {
        if (!active) {
          return;
        }
        setDesktopUpdateState({
          status: 'error',
          message: error instanceof Error ? error.message : 'Failed to read desktop update status.',
        });
      }
    };

    void syncDesktopUpdateState();

    const unsubscribe = desktopRuntimeApi?.onUpdateStateChange?.((state) => {
      if (!active) {
        return;
      }
      setDesktopUpdateState(normalizeDesktopUpdateState(state));
      setIsCheckingDesktopUpdate(false);
    });

    return () => {
      active = false;
      if (typeof unsubscribe === 'function') {
        unsubscribe();
      }
    };
  }, [canCheckDesktopUpdate, desktopRuntimeApi]);

  const rawActiveItems = itemsByCategory[activeCategory] || [];
  const rawActiveItemMap = new Map(rawActiveItems.map((item) => [item.key, String(item.value ?? '')]));
  const alphasiftItem = (itemsByCategory.data_source || []).find((item) => item.key === 'ALPHASIFT_ENABLED');
  const alphasiftEnabled = String(alphasiftItem?.value ?? '').trim().toLowerCase() === 'true';
  const hasConfiguredChannels = Boolean((rawActiveItemMap.get('LLM_CHANNELS') || '').trim());
  const hasLitellmConfig = Boolean((rawActiveItemMap.get('LITELLM_CONFIG') || '').trim());

  // UI rendering rule only: hide channel-managed and legacy provider-specific
  // LLM keys from generic fields when channel mode is active. This does not
  // alter save/refresh payloads or config migration/rollback behavior.
  const LLM_CHANNEL_KEY_RE = /^LLM_[A-Z0-9_]+_(PROTOCOL|BASE_URL|API_KEY|API_KEYS|MODELS|EXTRA_HEADERS|ENABLED)$/;
  const AI_MODEL_HIDDEN_KEYS = new Set([
    'LLM_CHANNELS',
    'LLM_TEMPERATURE',
    'LITELLM_MODEL',
    'AGENT_LITELLM_MODEL',
    'LITELLM_FALLBACK_MODELS',
    'AIHUBMIX_KEY',
    'DEEPSEEK_API_KEY',
    'DEEPSEEK_API_KEYS',
    'GEMINI_API_KEY',
    'GEMINI_API_KEYS',
    'GEMINI_MODEL',
    'GEMINI_MODEL_FALLBACK',
    'GEMINI_TEMPERATURE',
    'ANTHROPIC_API_KEY',
    'ANTHROPIC_API_KEYS',
    'ANTHROPIC_MODEL',
    'ANTHROPIC_TEMPERATURE',
    'ANTHROPIC_MAX_TOKENS',
    'OPENAI_API_KEY',
    'OPENAI_API_KEYS',
    'OPENAI_BASE_URL',
    'OPENAI_MODEL',
    'OPENAI_VISION_MODEL',
    'OPENAI_TEMPERATURE',
    'VISION_MODEL',
  ]);
  const SYSTEM_HIDDEN_KEYS = new Set([
    'ADMIN_AUTH_ENABLED',
  ]);
  const AGENT_HIDDEN_KEYS = new Set<string>();
  const activeItems =
    activeCategory === 'ai_model'
      ? rawActiveItems.filter((item) => {
        if (hasConfiguredChannels && LLM_CHANNEL_KEY_RE.test(item.key)) {
          return false;
        }
        if (hasConfiguredChannels && !hasLitellmConfig && AI_MODEL_HIDDEN_KEYS.has(item.key)) {
          return false;
        }
        return true;
      })
      : activeCategory === 'system'
        ? rawActiveItems.filter((item) => !SYSTEM_HIDDEN_KEYS.has(item.key))
      : activeCategory === 'agent'
        ? rawActiveItems.filter((item) => !AGENT_HIDDEN_KEYS.has(item.key))
      : rawActiveItems;
  const isEnvBackupAllowed = isDesktopRuntime || authEnabled;
  const envBackupActionDisabled = isLoading || isSaving || isExportingEnv || isImportingEnv || !isEnvBackupAllowed;

  const downloadEnvBackup = async () => {
    setEnvBackupActionError(null);
    setEnvBackupActionSuccess('');
    setIsExportingEnv(true);
    try {
      const payload = await systemConfigApi.exportEnv();
      const blob = new Blob([payload.content], { type: 'text/plain;charset=utf-8' });
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = formatEnvBackupFilename(isDesktopRuntime);
      document.body.appendChild(anchor);
      anchor.click();
      document.body.removeChild(anchor);
      URL.revokeObjectURL(url);
      setEnvBackupActionSuccess('Successfully exported the currently saved .env backup.');
    } catch (error: unknown) {
      setEnvBackupActionError(getParsedApiError(error));
    } finally {
      setIsExportingEnv(false);
    }
  };

  const beginEnvBackupImport = () => {
    setEnvBackupActionError(null);
    setEnvBackupActionSuccess('');
    if (hasDirty) {
      setShowImportConfirm(true);
      return;
    }
    envBackupImportRef.current?.click();
  };

  const handleEnvBackupImportFile = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = '';
    setShowImportConfirm(false);
    if (!file) {
      return;
    }

    setEnvBackupActionError(null);
    setEnvBackupActionSuccess('');
    setIsImportingEnv(true);
    try {
      const content = await file.text();
      await systemConfigApi.importEnv({
        configVersion,
        content,
        reloadNow: true,
      });
      const reloaded = await load();
      if (!reloaded) {
        setEnvBackupActionError(createParsedApiError({
          title: 'Config Imported but Refresh Failed',
          message: 'Backup imported, but failed to reload config. Please manually refresh the page.',
          rawMessage: 'Env import succeeded but config refresh failed',
          category: 'http_error',
        }));
        return;
      }
      notifySystemConfigChanged();
      setEnvBackupActionSuccess('Successfully imported .env backup and reloaded config.');
    } catch (error: unknown) {
      setEnvBackupActionError(getParsedApiError(error));
    } finally {
      setIsImportingEnv(false);
    }
  };

  const handleDesktopUpdateCheck = async () => {
    if (!desktopRuntimeApi?.checkForUpdates) {
      return;
    }

    setIsCheckingDesktopUpdate(true);
    setDesktopUpdateState((current) => ({
      ...(current || {}),
      status: 'checking',
      message: 'Checking GitHub Releases for available new versions.',
    }));

    try {
      const state = await desktopRuntimeApi.checkForUpdates();
      setDesktopUpdateState(normalizeDesktopUpdateState(state));
    } catch (error: unknown) {
      setDesktopUpdateState({
        status: 'error',
        message: error instanceof Error ? error.message : 'Failed to check for updates, please try again later.',
      });
    } finally {
      setIsCheckingDesktopUpdate(false);
    }
  };

  const updateAlphaSiftEnabled = async (nextEnabled: boolean) => {
    setAlphaSiftActionError(null);
    setAlphaSiftActionSuccess('');
    setIsUpdatingAlphaSift(true);
    try {
      if (nextEnabled) {
        await alphasiftApi.enable();
        await refreshAfterExternalSave(['ALPHASIFT_ENABLED']);
        setAlphaSiftActionSuccess('AlphaSift stock screening enabled.');
        return;
      }

      await systemConfigApi.update({
        configVersion,
        maskToken,
        reloadNow: true,
        items: [{ key: 'ALPHASIFT_ENABLED', value: 'false' }],
      });
      notifyAlphaSiftConfigChanged();
      await refreshAfterExternalSave(['ALPHASIFT_ENABLED']);
      setAlphaSiftActionSuccess('AlphaSift stock screening disabled.');
    } catch (error: unknown) {
      setAlphaSiftActionError(getParsedApiError(error));
      await refreshAfterExternalSave(['ALPHASIFT_ENABLED']);
    } finally {
      setIsUpdatingAlphaSift(false);
    }
  };

  const handleSaveConfig = async () => {
    const changedItems = getChangedItems();
    const changedAlphaSiftItem = changedItems.find((item) => item.key === 'ALPHASIFT_ENABLED');
    const result = await save();
    if (!result.success) {
      return;
    }
    notifySystemConfigChanged();
    if (!changedAlphaSiftItem) {
      return;
    }

    setAlphaSiftActionError(null);
    setAlphaSiftActionSuccess('');
    try {
      const isAlphaSiftEnabled = changedAlphaSiftItem.value.trim().toLowerCase() === 'true';
      if (isAlphaSiftEnabled) {
        await alphasiftApi.enable();
        await refreshAfterExternalSave(['ALPHASIFT_ENABLED']);
        setAlphaSiftActionSuccess('AlphaSift stock screening enabled.');
        return;
      }

      notifyAlphaSiftConfigChanged();
      setAlphaSiftActionSuccess('AlphaSift stock screening disabled.');
    } catch (error: unknown) {
      setAlphaSiftActionError(getParsedApiError(error));
      await refreshAfterExternalSave(['ALPHASIFT_ENABLED']);
    }
  };

  const openDesktopReleasePage = async () => {
    if (!desktopRuntimeApi?.openReleasePage) {
      return;
    }

    await desktopRuntimeApi.openReleasePage(desktopUpdateState?.releaseUrl);
  };

  const installDesktopUpdate = async () => {
    if (!desktopRuntimeApi?.installDownloadedUpdate) {
      setDesktopUpdateState((current) => ({
        ...(current || {}),
        status: 'error',
        message: 'Current desktop version does not support auto-installing updates. Please go to the release page to update manually.',
      }));
      return;
    }

    try {
      setDesktopUpdateState((current) => ({
        ...(current || {}),
        status: 'installing',
        message: 'Restarting and installing update...',
      }));
      await desktopRuntimeApi.installDownloadedUpdate();
    } catch (error: unknown) {
      setDesktopUpdateState((current) => ({
        ...(current || {}),
        status: 'error',
        message: error instanceof Error ? error.message : 'Failed to auto-install update. Please go to the release page to update manually.',
      }));
    }
  };

  const desktopUpdateNotice = getDesktopUpdateNotice(desktopUpdateState);
  const shouldGuardActiveConfigPanel = activeCategory === 'notification' || activeCategory === 'agent';
  const activeConfigPanelErrorTitle = activeCategory === 'agent' ? 'Agent Settings' : 'Notification Settings';
  const settingsPanelDiagnosticHint = isDesktopRuntime ? (
    <>
      Please check and provide desktop logs
      <code className="mx-1 rounded bg-background/45 px-1 py-0.5 font-mono text-xs">desktop.log</code>
      , along with the release version, Windows version, and trigger context.
    </>
  ) : (
    <>Please check browser devtools console and backend logs, along with release version, browser version, and trigger context.</>
  );
  const activeConfigPanel = activeItems.length ? (
    <SettingsSectionCard
      title="Current Category Config"
      description={getCategoryDescriptionZh(activeCategory as SystemConfigCategory, '') || 'Use unified field cards to manage system config for the current category.'}
    >
      {activeItems.map((item) => (
        <SettingsField
          key={item.key}
          item={item}
          value={item.value}
          disabled={isSaving}
          onChange={setDraftValue}
          issues={issueByKey[item.key] || []}
        />
      ))}
    </SettingsSectionCard>
  ) : (
    <EmptyState
      title="No config items in current category"
      description="There are no editable fields in the current category; select a category on the left to view other system configs."
      className="settings-surface-panel settings-border-strong border-none bg-transparent shadow-none"
    />
  );

  return (
    <div className="settings-page min-h-full px-4 pb-6 pt-4 md:px-6">
      <div className="mb-5 rounded-[1.5rem] border settings-border bg-card/94 px-5 py-5 shadow-soft-card-strong backdrop-blur-sm">
        <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <div>
            <h1 className="text-xl font-semibold tracking-tight text-foreground">System Settings</h1>
            <p className="text-xs leading-6 text-muted-text">
              Centrally manage models, data sources, notifications, security authentication, and import capabilities.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <Button
              type="button"
              variant="settings-secondary"
              onClick={resetDraft}
              disabled={isLoading || isSaving}
            >
              Reset
            </Button>
            <Button
              type="button"
              variant="settings-primary"
              onClick={() => void handleSaveConfig()}
              disabled={!hasDirty || isSaving || isLoading}
              isLoading={isSaving}
              loadingText="Saving..."
            >
              {isSaving ? 'Saving...' : `Save Config${dirtyCount ? ` (${dirtyCount})` : ''}`}
            </Button>
          </div>
        </div>

        {saveError ? (
          <ApiErrorAlert
            className="mt-3"
            error={saveError}
            actionLabel={retryAction === 'save' ? 'Retry Save' : undefined}
            onAction={retryAction === 'save' ? () => void retry() : undefined}
          />
        ) : null}
      </div>

      {loadError ? (
        <ApiErrorAlert
          error={loadError}
          actionLabel={retryAction === 'load' ? 'Retry Load' : 'Reload'}
          onAction={() => void retry()}
          className="mb-4"
        />
      ) : null}

      {isLoading ? (
        <SettingsLoading />
      ) : (
        <div className="grid grid-cols-1 gap-5 lg:grid-cols-[280px_1fr]">
          <aside className="lg:sticky lg:top-4 lg:self-start">
            <SettingsCategoryNav
              categories={categories}
              itemsByCategory={itemsByCategory}
              activeCategory={activeCategory}
              onSelect={setActiveCategory}
            />
          </aside>

          <section className="space-y-4">
            {alphasiftItem && activeCategory === 'data_source' ? (
              <SettingsSectionCard
                title="AlphaSift Stock Screening"
                description="Enable stock screening capabilities provided by third-party project AlphaSift."
              >
                <div className="flex flex-col gap-4 rounded-2xl border settings-border bg-background/35 px-4 py-4 md:flex-row md:items-center md:justify-between">
                  <div>
                    <p className="text-sm font-semibold text-foreground">
                      {alphasiftEnabled ? 'Screening Enabled' : 'Screening Disabled'}
                    </p>
                    <p className="mt-1 text-xs leading-6 text-muted-text">
                      When enabled, "Stock Screening" will appear in the left navigation. Strategies, data processing, and candidate generation come from AlphaSift; DSA only handles calling and displaying.
                    </p>
                    <p className="mt-2 text-xs leading-6 text-amber-700 dark:text-amber-300">
                      Risk Warning: Screening results are for research and reference only and do not constitute investment advice. Trading involves risk; all decisions and profits/losses are the user's sole responsibility.
                    </p>
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    <Button
                      type="button"
                      variant="settings-secondary"
                      onClick={() => setActiveCategory('data_source')}
                    >
                      View Config Items
                    </Button>
                    <Button
                      type="button"
                      variant={alphasiftEnabled ? 'settings-secondary' : 'settings-primary'}
                      onClick={() => void updateAlphaSiftEnabled(!alphasiftEnabled)}
                      disabled={isSaving || isLoading || isUpdatingAlphaSift}
                      isLoading={isUpdatingAlphaSift}
                      loadingText={alphasiftEnabled ? 'Disabling...' : 'Enabling...'}
                    >
                      {alphasiftEnabled ? 'Disable Screening' : 'Enable Screening'}
                    </Button>
                  </div>
                </div>
                {alphaSiftActionError ? (
                  <div className="mt-3">
                    <ApiErrorAlert error={alphaSiftActionError} />
                  </div>
                ) : null}
                {!alphaSiftActionError && alphaSiftActionSuccess ? (
                  <div className="mt-3">
                    <SettingsAlert title="Operation Successful" message={alphaSiftActionSuccess} variant="success" />
                  </div>
                ) : null}
              </SettingsSectionCard>
            ) : null}
            {activeCategory === 'system' ? <AuthSettingsCard /> : null}
            {activeCategory === 'system' ? (
              <SettingsSectionCard
                title="Version Information"
                description="Used to verify if the current WebUI static resources have switched to the latest build."
              >
                <div
                  className={`grid grid-cols-1 gap-3 ${shouldShowDesktopVersionCard ? 'md:grid-cols-4' : 'md:grid-cols-3'}`}
                >
                  <div className="rounded-2xl border settings-border bg-background/40 px-4 py-3">
                    <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-text">
                      WebUI Version
                    </p>
                    <p className="mt-2 break-all font-mono text-sm text-foreground">
                      {WEB_BUILD_INFO.version}
                    </p>
                  </div>
                  <div className="rounded-2xl border settings-border bg-background/40 px-4 py-3">
                    <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-text">
                      Build ID
                    </p>
                    <p className="mt-2 break-all font-mono text-sm text-foreground">
                      {WEB_BUILD_INFO.buildId}
                    </p>
                  </div>
                  <div className="rounded-2xl border settings-border bg-background/40 px-4 py-3">
                    <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-text">
                      Build Time
                    </p>
                    <p className="mt-2 break-all font-mono text-sm text-foreground">
                      {WEB_BUILD_INFO.buildTime}
                    </p>
                  </div>
                  {shouldShowDesktopVersionCard ? (
                    <div className="rounded-2xl border settings-border bg-background/40 px-4 py-3">
                      <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-text">
                        Desktop Version
                      </p>
                      <p className="mt-2 break-all font-mono text-sm text-foreground">
                        {desktopAppVersion}
                      </p>
                    </div>
                  ) : null}
                </div>
                <p className="text-xs leading-6 text-muted-text">
                  After rebuilding the frontend or Docker image, the Build ID and Build Time will update, confirming the page resources have refreshed.
                </p>
                {canCheckDesktopUpdate ? (
                  <div className="mt-4 space-y-3 rounded-2xl border settings-border bg-background/30 px-4 py-4">
                    <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
                      <div>
                        <p className="text-sm font-medium text-foreground">Desktop Update</p>
                        <p className="text-xs leading-6 text-muted-text">
                          Checks GitHub Releases for the latest stable version on startup. The Windows installer downloads updates in the background and silently restarts to install upon confirmation.
                        </p>
                      </div>
                      <Button
                        type="button"
                        variant="settings-secondary"
                        onClick={() => void handleDesktopUpdateCheck()}
                        disabled={isCheckingDesktopUpdate}
                        isLoading={isCheckingDesktopUpdate}
                        loadingText="Checking..."
                      >
                        Check for Updates
                      </Button>
                    </div>
                    {desktopUpdateNotice ? (
                      <SettingsAlert
                        title={desktopUpdateNotice.title}
                        message={desktopUpdateNotice.message}
                        variant={desktopUpdateNotice.variant}
                        actionLabel={desktopUpdateNotice.actionLabel}
                        onAction={desktopUpdateNotice.actionLabel ? () => {
                          if (desktopUpdateNotice.actionKind === 'install') {
                            void installDesktopUpdate();
                            return;
                          }
                          void openDesktopReleasePage();
                        } : undefined}
                      />
                    ) : (
                      <p className="text-xs leading-6 text-muted-text">
                        No update status available. The application will automatically check in the background after startup.
                      </p>
                    )}
                  </div>
                ) : null}
                {WEB_BUILD_INFO.isFallbackVersion ? (
                  <p className="text-xs leading-6 text-amber-700 dark:text-amber-300">
                    Current package.json is still placeholder version 0.0.0. The page has automatically fallen back to display the Build ID to avoid misjudging that old resources are still active.
                  </p>
                ) : null}
              </SettingsSectionCard>
            ) : null}
            {activeCategory === 'system' ? (
              <SettingsSectionCard
                title="Configuration Backup"
                description="Export the currently saved .env backup, or restore configuration from a backup file. Importing will overwrite keys present in the backup and reload immediately."
              >
                <div className="space-y-4">
                  {!isEnvBackupAllowed ? (
                    <p className="text-xs leading-6 text-amber-700 dark:text-amber-300">
                      Admin authentication is currently disabled on the Web frontend, so export/import of `.env` backups is disabled. Please set `ADMIN_AUTH_ENABLED` to `true` and log in as an admin to use this feature.
                    </p>
                  ) : null}
                  <div className="flex flex-wrap items-center gap-3">
                    <Button
                      type="button"
                      variant="settings-secondary"
                      onClick={() => void downloadEnvBackup()}
                      disabled={envBackupActionDisabled}
                      isLoading={isExportingEnv}
                      loadingText="Exporting..."
                    >
                      Export .env
                    </Button>
                    <Button
                      type="button"
                      variant="settings-primary"
                      onClick={beginEnvBackupImport}
                      disabled={envBackupActionDisabled}
                      isLoading={isImportingEnv}
                      loadingText="Importing..."
                    >
                      Import .env
                    </Button>
                    <input
                      ref={envBackupImportRef}
                      type="file"
                      accept=".env,.txt"
                      className="hidden"
                      onChange={(event) => {
                        void handleEnvBackupImportFile(event);
                      }}
                    />
                  </div>
                  <p className="text-xs leading-6 text-muted-text">
                    The export only contains the currently saved configuration and does not include unsaved local drafts.
                  </p>
                  {envBackupActionError ? (
                    <ApiErrorAlert
                      error={envBackupActionError}
                      actionLabel={envBackupActionError.status === 409 ? 'Reload' : undefined}
                      onAction={envBackupActionError.status === 409 ? () => void load() : undefined}
                    />
                  ) : null}
                  {!envBackupActionError && envBackupActionSuccess ? (
                    <SettingsAlert title="Operation Successful" message={envBackupActionSuccess} variant="success" />
                  ) : null}
                </div>
              </SettingsSectionCard>
            ) : null}
            {activeCategory === 'base' ? (
              <SettingsSectionCard
                title="Smart Import"
                description="Extract stock codes from images, files, or the clipboard, and merge them into the watchlist."
              >
                <IntelligentImport
                  stockListValue={
                    (activeItems.find((i) => i.key === 'STOCK_LIST')?.value as string) ?? ''
                  }
                  configVersion={configVersion}
                  maskToken={maskToken}
                  onMerged={async () => {
                    await refreshAfterExternalSave(['STOCK_LIST']);
                  }}
                  disabled={isSaving || isLoading}
                />
              </SettingsSectionCard>
            ) : null}
            {activeCategory === 'ai_model' ? (
              <SettingsSectionCard
                title="AI Model Access"
                description="Centrally manage model channels, base URLs, API Keys, main models, and fallback models."
              >
                <LLMChannelEditor
                  items={rawActiveItems}
                  configVersion={configVersion}
                  maskToken={maskToken}
                  onSaved={async (updatedItems) => {
                    await refreshAfterExternalSave(updatedItems.map((item) => item.key));
                  }}
                  disabled={isSaving || isLoading}
                />
              </SettingsSectionCard>
            ) : null}
            {activeCategory === 'system' && passwordChangeable ? (
              <ChangePasswordCard />
            ) : null}
            {activeCategory === 'notification' ? (
              <SettingsPanelErrorBoundary
                title="Teste de Notificação"
                resetKey={`notification-test:${configVersion}`}
                diagnosticHint={settingsPanelDiagnosticHint}
              >
                <NotificationTestPanel
                  items={rawActiveItems.map((item) => ({ key: item.key, value: String(item.value ?? '') }))}
                  maskToken={maskToken}
                  disabled={isSaving || isLoading}
                />
              </SettingsPanelErrorBoundary>
            ) : null}
            {shouldGuardActiveConfigPanel && activeItems.length ? (
              <SettingsPanelErrorBoundary
                title={activeConfigPanelErrorTitle}
                resetKey={`${activeCategory}:${configVersion}`}
                diagnosticHint={settingsPanelDiagnosticHint}
              >
                {activeConfigPanel}
              </SettingsPanelErrorBoundary>
            ) : activeConfigPanel}
          </section>
        </div>
      )}

      {toast ? (
        <div className="fixed bottom-5 right-5 z-50 w-[320px] max-w-[calc(100vw-24px)]">
          {toast.type === 'success'
            ? (
                <SettingsAlert
                  title="Operation Successful"
                  message={toast.message}
                  variant="success"
                  presentation="toast"
                />
              )
            : <ApiErrorAlert error={toast.error} />}
        </div>
      ) : null}
      <ConfirmDialog
        isOpen={showImportConfirm}
        title="Importing will overwrite current drafts"
        message="There are unsaved changes on the current page. Continuing with the import will discard these local drafts and immediately update the saved configuration with the values from the backup file."
        confirmText="Continue Import"
        cancelText="Cancel"
        onConfirm={() => {
          setShowImportConfirm(false);
          envBackupImportRef.current?.click();
        }}
        onCancel={() => {
          setShowImportConfirm(false);
        }}
      />
    </div>
  );
};

export default SettingsPage;

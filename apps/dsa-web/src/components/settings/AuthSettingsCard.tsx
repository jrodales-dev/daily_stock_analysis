import type React from 'react';
import { useEffect, useMemo, useState } from 'react';
import { authApi } from '../../api/auth';
import { getParsedApiError, isParsedApiError, type ParsedApiError } from '../../api/error';
import { useAuth } from '../../hooks';
import { Badge, Button, Input, Checkbox } from '../common';
import { SettingsAlert } from './SettingsAlert';
import { SettingsSectionCard } from './SettingsSectionCard';

function createNextModeLabel(authEnabled: boolean, desiredEnabled: boolean) {
  if (authEnabled && !desiredEnabled) {
    return 'Desativar Autenticação';
  }
  if (!authEnabled && desiredEnabled) {
    return 'Ativar Autenticação';
  }
  return authEnabled ? 'Mantido Ativado' : 'Mantido Desativado';
}

export const AuthSettingsCard: React.FC = () => {
  const { authEnabled, setupState, refreshStatus } = useAuth();
  const [desiredEnabled, setDesiredEnabled] = useState(authEnabled);
  const [currentPassword, setCurrentPassword] = useState('');
  const [password, setPassword] = useState('');
  const [passwordConfirm, setPasswordConfirm] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | ParsedApiError | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const isDirty = desiredEnabled !== authEnabled || currentPassword || password || passwordConfirm;
  const targetActionLabel = createNextModeLabel(authEnabled, desiredEnabled);

  const helperText = useMemo(() => {
    switch (setupState) {
      case 'no_password':
        return 'Senha não definida. Defina uma senha antes de habilitar a Autenticação.';
      case 'password_retained':
        return 'Senha anterior salva! Informe para ativar a Autenticação.';
      case 'enabled':
        return !desiredEnabled 
          ? 'Caso a sessão atual ainda seja válida, a Autenticação pode ser desativada; se expirar, insira a Senha novamente.'
          : 'Autenticação Ativa. Para alterar a Senha, vá para o painel de Senhas.';
      default:
        return 'Protege suas configurações contra acessos remotos.';
    }
  }, [setupState, desiredEnabled]);

  useEffect(() => {
    setDesiredEnabled(authEnabled);
  }, [authEnabled]);

  const resetForm = () => {
    setCurrentPassword('');
    setPassword('');
    setPasswordConfirm('');
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setError(null);
    setSuccessMessage(null);

    // Initial setup validation
    if (setupState === 'no_password' && desiredEnabled) {
      if (!password) {
        setError('A nova senha é obrigatória');
        return;
      }
      if (password !== passwordConfirm) {
        setError('As novas senhas não coincidem');
        return;
      }
    }

    setIsSubmitting(true);
    try {
      await authApi.updateSettings(
        desiredEnabled,
        password.trim() || undefined,
        passwordConfirm.trim() || undefined,
        currentPassword.trim() || undefined,
      );
      await refreshStatus();
      setSuccessMessage(desiredEnabled ? 'Configurações de Autenticação atualizada' : 'Autenticação desativada');
      resetForm();
    } catch (err: unknown) {
      setError(getParsedApiError(err));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <SettingsSectionCard
      title="Autenticação e Proteção"
      description="Gerencie a Autenticação por Senha para manter sua API e Sistema protegidos."
      actions={
        <Badge
          variant={authEnabled ? 'success' : 'default'}
          size="sm"
          className={authEnabled ? '' : 'border-[var(--settings-border)] bg-[var(--settings-surface-hover)] text-secondary-text'}
        >
          {authEnabled ? 'Ativado' : 'Desativado'}
        </Badge>
      }
    >
      <form className="space-y-4" onSubmit={handleSubmit}>
        <div className="rounded-xl border border-[var(--settings-border)] bg-[var(--settings-surface)] p-4 shadow-soft-card transition-[background-color,border-color] duration-200 hover:border-[var(--settings-border-strong)] hover:bg-[var(--settings-surface-hover)]">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="space-y-1">
              <p className="text-sm font-semibold text-foreground">Autenticação do Administrador</p>
              <p className="text-xs leading-6 text-muted-text">{helperText}</p>
            </div>
            <Checkbox
              checked={desiredEnabled}
              disabled={isSubmitting}
              label={desiredEnabled ? 'Ligado' : 'Desligado'}
              onChange={(event) => setDesiredEnabled(event.target.checked)}
              containerClassName="rounded-full border border-[var(--settings-border)] bg-[var(--settings-surface-hover)] px-4 py-2 shadow-soft-card transition-[background-color,border-color] duration-200 hover:border-[var(--settings-border-strong)] hover:bg-[var(--settings-surface)]"
            />
          </div>
        </div>

        {/* Password input fields logic based on setupState and desiredEnabled */}
        {(desiredEnabled || (authEnabled && !desiredEnabled)) && (
          <div className="grid gap-4 md:grid-cols-2">
            {/* Show Current Password if we have one and we're either re-enabling or turning off */}
            {(setupState === 'password_retained' && desiredEnabled) || 
             (setupState === 'enabled' && !desiredEnabled) ? (
              <div className="space-y-3">
                <Input
                  label="Senha Atual"
                  type="password"
                  allowTogglePassword
                  iconType="password"
                  value={currentPassword}
                  onChange={(event) => setCurrentPassword(event.target.value)}
                  autoComplete="current-password"
                  disabled={isSubmitting}
                  placeholder="Informe sua senha"
                  hint={setupState === 'password_retained' ? 'Insira a senha anterior' : 'Será necessária confirmar a sua Identidade antes de desabilitar'}
                />
              </div>
            ) : null}

            {/* Show New Password fields only during initial setup */}
            {setupState === 'no_password' && desiredEnabled ? (
              <>
                <div className="space-y-3">
                  <Input
                    label="Ajuste a nova Senha"
                    type="password"
                    allowTogglePassword
                    iconType="password"
                    value={password}
                    onChange={(event) => setPassword(event.target.value)}
                    autoComplete="new-password"
                    disabled={isSubmitting}
                    placeholder="Nova senha (mais de 6 caracteres)"
                  />
                </div>
                <div className="space-y-3">
                  <Input
                    label="Confirmação"
                    type="password"
                    allowTogglePassword
                    iconType="password"
                    value={passwordConfirm}
                    onChange={(event) => setPasswordConfirm(event.target.value)}
                    autoComplete="new-password"
                    disabled={isSubmitting}
                    placeholder="Insira de novo para confirmar"
                  />
                </div>
              </>
            ) : null}
          </div>
        )}

        {error ? (
          isParsedApiError(error) ? (
            <SettingsAlert
              title="Erro ao Configurar"
              message={error.message}
              variant="error"
            />
          ) : (
            <SettingsAlert title="Erro ao Configurar" message={error} variant="error" />
          )
        ) : null}

        {successMessage ? (
          <SettingsAlert title="Operação Sucesso!" message={successMessage} variant="success" />
        ) : null}

        <div className="flex flex-wrap items-center gap-2">
          <Button type="submit" variant="settings-primary" isLoading={isSubmitting} disabled={!isDirty}>
            {targetActionLabel}
          </Button>
          <Button
            type="button"
            variant="settings-secondary"
            onClick={() => {
              setDesiredEnabled(authEnabled);
              setError(null);
              setSuccessMessage(null);
              resetForm();
            }}
            disabled={isSubmitting || !isDirty}
          >
            Redefinir
          </Button>
        </div>
      </form>
    </SettingsSectionCard>
  );
};

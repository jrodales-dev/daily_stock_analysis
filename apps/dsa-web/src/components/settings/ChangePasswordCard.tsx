import type React from 'react';
import { useState } from 'react';
import type { ParsedApiError } from '../../api/error';
import { isParsedApiError } from '../../api/error';
import { useAuth } from '../../hooks';
import { Button, Input } from '../common';
import { SettingsAlert } from './SettingsAlert';
import { SettingsSectionCard } from './SettingsSectionCard';

export const ChangePasswordCard: React.FC = () => {
  const { changePassword } = useAuth();
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [newPasswordConfirm, setNewPasswordConfirm] = useState('');
  
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | ParsedApiError | null>(null);
  const [success, setSuccess] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSuccess(false);

    if (!currentPassword.trim()) {
      setError('Informe a Senha Atual');
      return;
    }
    if (!newPassword.trim()) {
      setError('Informe a Nova Senha');
      return;
    }
    if (newPassword.length < 6) {
      setError('A Nova Senha precisa de ao menos 6 caracteres');
      return;
    }
    if (newPassword !== newPasswordConfirm) {
      setError('As duas senhas não coincidem');
      return;
    }

    setIsSubmitting(true);
    try {
      const result = await changePassword(currentPassword, newPassword, newPasswordConfirm);
      if (result.success) {
        setSuccess(true);
        setCurrentPassword('');
        setNewPassword('');
        setNewPasswordConfirm('');
        setTimeout(() => setSuccess(false), 4000);
      } else {
        setError(result.error ?? 'Falha ao alterar');
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <SettingsSectionCard
      title="Alterar Senha"
      description="Atualizar Senha Local. O próximo login irá necessitar que essa Nova Senha seja utilizada."
    >
      <form onSubmit={handleSubmit} className="space-y-3">
        <div className="grid gap-4 md:grid-cols-2">
          <div className="space-y-3">
            <Input
              id="change-pass-current"
              type="password"
              allowTogglePassword
              iconType="password"
              label="Senha atual"
              placeholder="Insira a Senha atual"
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
              disabled={isSubmitting}
              autoComplete="current-password"
            />
          </div>

          <div className="space-y-3">
            <Input
              id="change-pass-new"
              type="password"
              allowTogglePassword
              iconType="password"
              label="Nova senha"
              hint="Ao menos 6 dígitos."
              placeholder="Nova Senha"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              disabled={isSubmitting}
              autoComplete="new-password"
            />
          </div>
        </div>

        <div className="space-y-3 md:max-w-md">
          <Input
            id="change-pass-confirm"
            type="password"
            allowTogglePassword
            iconType="password"
            label="Confirme a Senha"
            placeholder="Insira a Nova Senha novamente"
            value={newPasswordConfirm}
            onChange={(e) => setNewPasswordConfirm(e.target.value)}
            disabled={isSubmitting}
            autoComplete="new-password"
          />
        </div>

        {error
          ? isParsedApiError(error)
            ? <SettingsAlert title="Falha ao alterar" message={error.message} variant="error" className="!mt-3" />
            : <SettingsAlert title="Falha ao alterar" message={error} variant="error" className="!mt-3" />
          : null}
        {success ? (
          <SettingsAlert title="Ação Bem Sucedida!" message="A Senha foi devidamente atualizada." variant="success" />
        ) : null}

        <Button type="submit" variant="primary" isLoading={isSubmitting}>
          SalvarNova senha
        </Button>
      </form>
    </SettingsSectionCard>
  );
};

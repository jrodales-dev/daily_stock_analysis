import type React from 'react';
import { useEffect, useState } from 'react';
import { motion, useMotionValue, useTransform, useSpring } from "motion/react";
import { UserPlus, Loader2 } from "lucide-react";
import { Button, Input, ParticleBackground } from '../components/common';
import { useNavigate, Link } from 'react-router-dom';
import { SettingsAlert } from '../components/settings';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import * as z from 'zod';
import { toast } from 'sonner';

const registerSchema = z.object({
  email: z.string().email('E-mail inválido'),
  username: z.string().min(3, 'O usuário deve ter pelo menos 3 caracteres'),
  password: z.string().min(6, 'A senha deve ter pelo menos 6 caracteres'),
  confirmPassword: z.string()
}).refine((data) => data.password === data.confirmPassword, {
  message: "As senhas não coincidem",
  path: ["confirmPassword"]
});

type RegisterForm = z.infer<typeof registerSchema>;

const RegisterPage: React.FC = () => {
  const navigate = useNavigate();
  const [apiError, setApiError] = useState<string | null>(null);

  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm<RegisterForm>({
    resolver: zodResolver(registerSchema),
  });

  useEffect(() => {
    document.title = 'Registro - DSA Terminal';
  }, []);

  const mouseX = useMotionValue(0);
  const mouseY = useMotionValue(0);
  const smoothX = useSpring(mouseX, { damping: 30, stiffness: 200 });
  const smoothY = useSpring(mouseY, { damping: 30, stiffness: 200 });

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      const x = e.clientX / window.innerWidth - 0.5;
      const y = e.clientY / window.innerHeight - 0.5;
      mouseX.set(x);
      mouseY.set(y);
    };
    window.addEventListener("mousemove", handleMouseMove);
    return () => window.removeEventListener("mousemove", handleMouseMove);
  }, [mouseX, mouseY]);

  const onSubmit = async (data: RegisterForm) => {
    setApiError(null);
    try {
      // API call to register
      const response = await fetch(`${import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1'}/auth/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email: data.email,
          username: data.username,
          password: data.password
        })
      });
      
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || 'Erro ao registrar usuário');
      }

      toast.success('Conta criada com sucesso! Faça login.');
      navigate('/login');
    } catch (err: any) {
      setApiError(err.message || 'Erro de comunicação');
      toast.error('Falha no registro');
    }
  };

  return (
    <div className="relative flex min-h-screen flex-col justify-center overflow-hidden bg-[var(--login-bg-main)] py-12 font-sans selection:bg-[var(--login-accent-soft)] sm:px-6 lg:px-8 [perspective:1500px]">
      <ParticleBackground />
      <div className="absolute inset-0 z-0 bg-[linear-gradient(to_right,var(--login-grid-line)_1px,transparent_1px),linear-gradient(to_bottom,var(--login-grid-line)_1px,transparent_1px)] bg-[size:24px_24px] [mask-image:var(--login-grid-mask)]" />

      <motion.div
        style={{
          x: useTransform(smoothX, [-0.5, 0.5], [-50, 50]),
          y: useTransform(smoothY, [-0.5, 0.5], [-50, 50]),
        }}
        className="absolute left-[20%] top-[20%] -z-10 h-[300px] w-[300px] -translate-x-1/2 -translate-y-1/2 rounded-full bg-[var(--login-accent-glow)] blur-[100px]"
      />
      
      <div className="sm:mx-auto sm:w-full sm:max-w-md relative z-10">
        <motion.div
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, ease: "easeOut" }}
          className="flex flex-col items-center justify-center mb-10 relative"
        >
          <div className="mt-8 flex flex-col items-center">
            <h2 className="text-4xl font-extrabold tracking-tighter text-[var(--login-text-primary)] sm:text-6xl">
              <span className="bg-gradient-to-r from-[var(--login-text-primary)] via-[var(--login-text-primary)] to-[var(--login-text-secondary)] bg-clip-text text-transparent">DAILY </span>
              <span className="bg-gradient-to-r from-[var(--login-brand-start)] to-[var(--login-brand-end)] bg-clip-text text-transparent drop-shadow-[0_0_20px_var(--login-accent-glow)]">STOCK</span>
            </h2>
            <h3 className="mt-1 text-xl font-bold uppercase tracking-[0.5em] text-[var(--login-text-muted)]">
              Terminal
            </h3>
          </div>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.5, delay: 0.1 }}
          className="relative group z-20 pointer-events-auto"
        >
          <div className="pointer-events-none absolute -inset-0.5 rounded-3xl bg-gradient-to-b from-[var(--login-accent-glow)] to-[hsl(214_100%_56%_/_0.18)] opacity-50 blur-sm transition duration-1000 group-hover:opacity-100 group-hover:duration-200" />
          <div className="pointer-events-auto relative flex flex-col overflow-hidden rounded-3xl border border-[var(--login-border-card)] bg-[var(--login-bg-card)]/80 p-8 shadow-2xl backdrop-blur-xl">
            <div className="mb-8">
              <h1 className="flex items-center gap-2 text-2xl font-bold tracking-tight text-[var(--login-text-primary)]">
                <UserPlus className="h-5 w-5 text-[var(--login-accent-text)]" />
                <span>Criar Conta Institucional</span>
              </h1>
              <p className="mt-2 text-sm text-[var(--login-text-secondary)]">
                Preencha os dados para obter acesso.
              </p>
            </div>

            <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
              <div className="space-y-4">
                <div>
                  <Input
                    id="username"
                    type="text"
                    appearance="login"
                    label="Nome de Usuário"
                    placeholder="Ex: trader_01"
                    disabled={isSubmitting}
                    autoFocus
                    {...register('username')}
                  />
                  {errors.username && <span className="text-red-500 text-xs mt-1">{errors.username.message}</span>}
                </div>

                <div>
                  <Input
                    id="email"
                    type="email"
                    appearance="login"
                    label="E-mail"
                    placeholder="user@example.com"
                    disabled={isSubmitting}
                    {...register('email')}
                  />
                  {errors.email && <span className="text-red-500 text-xs mt-1">{errors.email.message}</span>}
                </div>

                <div>
                  <Input
                    id="password"
                    type="password"
                    appearance="login"
                    allowTogglePassword
                    iconType="password"
                    label="Senha"
                    placeholder="Insira sua senha"
                    disabled={isSubmitting}
                    {...register('password')}
                  />
                  {errors.password && <span className="text-red-500 text-xs mt-1">{errors.password.message}</span>}
                </div>

                <div>
                  <Input
                    id="confirmPassword"
                    type="password"
                    appearance="login"
                    allowTogglePassword
                    iconType="password"
                    label="Confirmar Senha"
                    placeholder="Confirme sua senha"
                    disabled={isSubmitting}
                    {...register('confirmPassword')}
                  />
                  {errors.confirmPassword && <span className="text-red-500 text-xs mt-1">{errors.confirmPassword.message}</span>}
                </div>
              </div>

              {apiError && (
                <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }}>
                  <SettingsAlert title="Erro" message={apiError} variant="error" />
                </motion.div>
              )}

              <Button
                type="submit"
                variant="primary"
                size="lg"
                className="w-full"
                disabled={isSubmitting}
              >
                {isSubmitting ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                Registrar Conta
              </Button>
            </form>
            <div className="mt-4 text-center text-sm text-[var(--login-text-muted)]">
              Já tem uma conta? <Link to="/login" className="text-[var(--login-brand-end)] hover:underline">Faça login</Link>
            </div>
          </div>
        </motion.div>
      </div>
    </div>
  );
};

export default RegisterPage;

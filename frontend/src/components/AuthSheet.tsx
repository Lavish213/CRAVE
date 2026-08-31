import React, { useState } from 'react';
import {
  ActivityIndicator,
  KeyboardAvoidingView,
  Modal,
  Platform,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import * as Haptics from 'expo-haptics';
import * as AuthSession from 'expo-auth-session';
import * as QueryParams from 'expo-auth-session/build/QueryParams';
import * as WebBrowser from 'expo-web-browser';
import { supabase } from '../lib/supabase';
import { Colors, Spacing, Radius } from '../constants/colors';
import { useToast } from '../hooks/useToast';

// Required so that when the OAuth browser tab redirects back into the app,
// the pending WebBrowser.openAuthSessionAsync() promise actually resolves
// (otherwise the browser closes but the app never sees the redirect).
WebBrowser.maybeCompleteAuthSession();

// Deep link the OAuth provider redirects back to — must match app.json's
// "scheme" ("crave") and whatever redirect URL is allow-listed in the
// Supabase project's Auth > URL Configuration settings.
const OAUTH_REDIRECT_TO = AuthSession.makeRedirectUri({ scheme: 'crave' });

async function createSessionFromUrl(url: string) {
  const { params, errorCode } = QueryParams.getQueryParams(url);
  if (errorCode) throw new Error(errorCode);

  const { access_token, refresh_token } = params;
  if (!access_token || !refresh_token) return null;

  const { data, error } = await supabase.auth.setSession({
    access_token,
    refresh_token,
  });
  if (error) throw error;
  return data.session;
}

async function performOAuth(provider: 'google' | 'apple') {
  const { data, error } = await supabase.auth.signInWithOAuth({
    provider,
    options: {
      redirectTo: OAUTH_REDIRECT_TO,
      skipBrowserRedirect: true,
    },
  });
  if (error) throw error;
  if (!data?.url) throw new Error('No OAuth URL returned from Supabase');

  const result = await WebBrowser.openAuthSessionAsync(data.url, OAUTH_REDIRECT_TO);
  if (result.type === 'success' && result.url) {
    return createSessionFromUrl(result.url);
  }
  return null;
}

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

// Supabase's raw error strings are accurate but not user-facing copy —
// map the handful users will actually hit to something actionable.
function humanizeAuthError(message: string): string {
  const m = message.toLowerCase();
  if (m.includes('invalid login credentials')) {
    return "That email or password isn't right.";
  }
  if (m.includes('already registered') || m.includes('already exists')) {
    return 'An account already exists for that email. Try signing in instead.';
  }
  if (m.includes('password should be at least') || m.includes('password is too short')) {
    return 'Password must be at least 6 characters.';
  }
  if (m.includes('email not confirmed')) {
    return 'Confirm your email first — check your inbox for the link.';
  }
  if (m.includes('rate limit')) {
    return 'Too many attempts. Wait a bit and try again.';
  }
  return message;
}

interface Props {
  visible: boolean;
  onClose: () => void;
  reason?: 'save' | 'craves' | 'profile' | 'add-spot' | 'default';
}

const REASON_COPY: Record<NonNullable<Props['reason']>, { title: string; body: string }> = {
  save: {
    title: 'Save this spot',
    body: 'Create a free account to keep your Craves across devices.',
  },
  craves: {
    title: 'Your Craves await',
    body: 'Sign in to access your saved places and food memories.',
  },
  'add-spot': {
    title: 'Add a spot',
    body: 'Sign in so we know who found it — new spots are credited to the person who confirms them.',
  },
  profile: {
    title: 'Build your list',
    body: 'Rank the places you’ve eaten, follow friends, and see how your taste stacks up.',
  },
  default: {
    title: 'Join CRAVE',
    body: 'Your cultural discovery engine. Save spots, track craves, find the city.',
  },
};

export function AuthSheet({ visible, onClose, reason = 'default' }: Props) {
  const [loading, setLoading] = useState<'google' | 'apple' | 'email' | null>(null);
  const [view, setView] = useState<'options' | 'email'>('options');
  const [authMode, setAuthMode] = useState<'signin' | 'signup'>('signin');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const copy = REASON_COPY[reason];
  const toast = useToast((s) => s.show);

  const resetAndClose = () => {
    setView('options');
    setAuthMode('signin');
    setEmail('');
    setPassword('');
    onClose();
  };

  const handleGoogle = async () => {
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
    setLoading('google');
    try {
      const session = await performOAuth('google');
      if (session) resetAndClose();
    } catch (err) {
      // Previously silent outside __DEV__ — a real failure here (network,
      // misconfigured redirect, provider error) looked identical to
      // nothing happening at all, with no way to tell "try again" from
      // "the app is broken."
      if (__DEV__) console.log('[AUTH] google_oauth_failed', err);
      toast("Couldn't sign in with Google. Try again.");
    } finally {
      setLoading(null);
    }
  };

  const handleApple = async () => {
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
    setLoading('apple');
    try {
      const session = await performOAuth('apple');
      if (session) resetAndClose();
    } catch (err) {
      if (__DEV__) console.log('[AUTH] apple_oauth_failed', err);
      toast("Couldn't sign in with Apple. Try again.");
    } finally {
      setLoading(null);
    }
  };

  const handleEmailAuth = async () => {
    const trimmedEmail = email.trim();
    if (!EMAIL_RE.test(trimmedEmail)) {
      toast('Enter a valid email address.');
      return;
    }
    if (password.length < 6) {
      toast('Password must be at least 6 characters.');
      return;
    }

    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
    setLoading('email');
    try {
      if (authMode === 'signup') {
        const { data, error } = await supabase.auth.signUp({
          email: trimmedEmail,
          password,
        });
        if (error) throw error;
        if (data.session) {
          resetAndClose();
        } else {
          // No session back means Supabase requires email confirmation
          // before the account is usable — not an error, just a different
          // next step than sign-in gets.
          toast('Check your email to confirm your account, then sign in.');
          setAuthMode('signin');
          setPassword('');
        }
      } else {
        const { data, error } = await supabase.auth.signInWithPassword({
          email: trimmedEmail,
          password,
        });
        if (error) throw error;
        if (data.session) resetAndClose();
      }
    } catch (err) {
      if (__DEV__) console.log('[AUTH] email_auth_failed', err);
      toast(err instanceof Error ? humanizeAuthError(err.message) : "Couldn't sign in. Try again.");
    } finally {
      setLoading(null);
    }
  };

  return (
    <Modal
      visible={visible}
      transparent
      animationType="slide"
      onRequestClose={resetAndClose}
      statusBarTranslucent
    >
      {/* accessible=false so VoiceOver/TalkBack skip straight to the
          labeled "Close"/"Back" button below instead of stopping on an
          invisible, undescribed full-screen element first. */}
      <Pressable style={styles.backdrop} onPress={resetAndClose} accessible={false} />

      <KeyboardAvoidingView
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
        style={styles.keyboardWrap}
      >
        <View style={styles.sheet}>
          {/* Handle */}
          <View style={styles.handle} />

          {/* Close / Back */}
          <TouchableOpacity
            style={styles.closeBtn}
            onPress={view === 'email' ? () => setView('options') : resetAndClose}
            accessibilityRole="button"
            accessibilityLabel={view === 'email' ? 'Back' : 'Close'}
          >
            <Ionicons
              name={view === 'email' ? 'chevron-back' : 'close'}
              size={20}
              color={Colors.textSecondary}
            />
          </TouchableOpacity>

          {/* Identity */}
          <View style={styles.identity}>
            <Text style={styles.wordmark}>CRAVE</Text>
            <Text style={styles.title}>
              {view === 'email'
                ? authMode === 'signup'
                  ? 'Create your account'
                  : 'Sign in'
                : copy.title}
            </Text>
            <Text style={styles.body}>
              {view === 'email'
                ? authMode === 'signup'
                  ? 'Use your email to get started.'
                  : 'Enter your email and password.'
                : copy.body}
            </Text>
          </View>

          {view === 'options' ? (
            <>
              {/* Auth buttons */}
              <View style={styles.buttons}>
                {/* Apple */}
                <TouchableOpacity
                  style={[styles.authBtn, styles.authBtnApple]}
                  onPress={handleApple}
                  activeOpacity={0.85}
                  disabled={loading !== null}
                  accessibilityRole="button"
                  accessibilityLabel="Continue with Apple"
                >
                  {loading === 'apple' ? (
                    <ActivityIndicator color={Colors.background} size="small" />
                  ) : (
                    <>
                      <Ionicons name="logo-apple" size={18} color={Colors.background} />
                      <Text style={[styles.authBtnText, styles.authBtnTextApple]}>
                        Continue with Apple
                      </Text>
                    </>
                  )}
                </TouchableOpacity>

                {/* Google */}
                <TouchableOpacity
                  style={[styles.authBtn, styles.authBtnGoogle]}
                  onPress={handleGoogle}
                  activeOpacity={0.85}
                  disabled={loading !== null}
                  accessibilityRole="button"
                  accessibilityLabel="Continue with Google"
                >
                  {loading === 'google' ? (
                    <ActivityIndicator color={Colors.text} size="small" />
                  ) : (
                    <>
                      <Ionicons name="logo-google" size={16} color={Colors.text} />
                      <Text style={styles.authBtnText}>Continue with Google</Text>
                    </>
                  )}
                </TouchableOpacity>

                {/* Divider */}
                <View style={styles.divider}>
                  <View style={styles.dividerLine} />
                  <Text style={styles.dividerText}>or</Text>
                  <View style={styles.dividerLine} />
                </View>

                {/* Email */}
                <TouchableOpacity
                  style={[styles.authBtn, styles.authBtnEmail]}
                  onPress={() => setView('email')}
                  activeOpacity={0.85}
                  disabled={loading !== null}
                  accessibilityRole="button"
                  accessibilityLabel="Continue with email"
                >
                  <Ionicons name="mail-outline" size={18} color={Colors.text} />
                  <Text style={styles.authBtnText}>Continue with email</Text>
                </TouchableOpacity>
              </View>

              <Text style={styles.legal}>
                By continuing you agree to our{' '}
                <Text style={styles.legalLink}>Terms</Text>
                {' & '}
                <Text style={styles.legalLink}>Privacy Policy</Text>
              </Text>
            </>
          ) : (
            <View style={styles.buttons}>
              <View style={styles.field}>
                <TextInput
                  style={styles.input}
                  value={email}
                  onChangeText={setEmail}
                  placeholder="Email"
                  placeholderTextColor={Colors.textSecondary}
                  autoCapitalize="none"
                  autoCorrect={false}
                  keyboardType="email-address"
                  textContentType="emailAddress"
                  accessibilityLabel="Email"
                  editable={loading === null}
                />
              </View>
              <View style={styles.field}>
                <TextInput
                  style={styles.input}
                  value={password}
                  onChangeText={setPassword}
                  placeholder="Password"
                  placeholderTextColor={Colors.textSecondary}
                  secureTextEntry
                  autoCapitalize="none"
                  autoCorrect={false}
                  textContentType={authMode === 'signup' ? 'newPassword' : 'password'}
                  accessibilityLabel="Password"
                  editable={loading === null}
                  onSubmitEditing={handleEmailAuth}
                  returnKeyType="go"
                />
              </View>

              <TouchableOpacity
                style={[styles.authBtn, styles.authBtnApple]}
                onPress={handleEmailAuth}
                activeOpacity={0.85}
                disabled={loading !== null}
                accessibilityRole="button"
                accessibilityLabel={authMode === 'signup' ? 'Create account' : 'Sign in'}
              >
                {loading === 'email' ? (
                  <ActivityIndicator color={Colors.background} size="small" />
                ) : (
                  <Text style={[styles.authBtnText, styles.authBtnTextApple]}>
                    {authMode === 'signup' ? 'Create account' : 'Sign in'}
                  </Text>
                )}
              </TouchableOpacity>

              <TouchableOpacity
                onPress={() => setAuthMode(authMode === 'signup' ? 'signin' : 'signup')}
                disabled={loading !== null}
                style={styles.switchModeBtn}
              >
                <Text style={styles.switchModeText}>
                  {authMode === 'signup'
                    ? 'Already have an account? '
                    : "Don't have an account? "}
                  <Text style={styles.legalLink}>
                    {authMode === 'signup' ? 'Sign in' : 'Sign up'}
                  </Text>
                </Text>
              </TouchableOpacity>
            </View>
          )}
        </View>
      </KeyboardAvoidingView>
    </Modal>
  );
}

const styles = StyleSheet.create({
  backdrop: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.65)',
  },
  keyboardWrap: {
    justifyContent: 'flex-end',
  },
  sheet: {
    backgroundColor: Colors.surface,
    borderTopLeftRadius: Radius.card,
    borderTopRightRadius: Radius.card,
    borderTopWidth: 1,
    borderColor: Colors.border,
    paddingBottom: 40,
  },
  handle: {
    width: 36,
    height: 4,
    borderRadius: Radius.full,
    backgroundColor: Colors.border,
    alignSelf: 'center',
    marginTop: Spacing.sm,
  },
  closeBtn: {
    position: 'absolute',
    top: Spacing.sm,
    right: Spacing.md,
    padding: Spacing.sm,
    minWidth: 44,
    minHeight: 44,
    alignItems: 'center',
    justifyContent: 'center',
  },
  identity: {
    paddingHorizontal: Spacing.xl,
    paddingTop: Spacing.xl,
    paddingBottom: Spacing.lg,
  },
  wordmark: {
    fontSize: 13,
    fontWeight: '900',
    color: Colors.primary,
    letterSpacing: 3,
    marginBottom: Spacing.md,
  },
  title: {
    fontSize: 26,
    fontWeight: '800',
    color: Colors.text,
    marginBottom: Spacing.sm,
  },
  body: {
    fontSize: 15,
    color: Colors.textSecondary,
    lineHeight: 22,
  },
  buttons: {
    paddingHorizontal: Spacing.xl,
    gap: Spacing.sm,
  },
  authBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: Spacing.sm,
    height: 52,
    borderRadius: Radius.md,
  },
  authBtnApple: {
    backgroundColor: Colors.text,
  },
  authBtnGoogle: {
    backgroundColor: Colors.surfaceElevated,
    borderWidth: 1,
    borderColor: Colors.border,
  },
  authBtnEmail: {
    backgroundColor: Colors.surfaceElevated,
    borderWidth: 1,
    borderColor: Colors.border,
  },
  authBtnText: {
    fontSize: 16,
    fontWeight: '700',
    color: Colors.text,
  },
  authBtnTextApple: {
    color: Colors.background,
  },
  divider: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.sm,
    marginVertical: Spacing.xs,
  },
  dividerLine: {
    flex: 1,
    height: StyleSheet.hairlineWidth,
    backgroundColor: Colors.border,
  },
  dividerText: {
    fontSize: 12,
    fontWeight: '600',
    color: Colors.textSecondary,
  },
  field: {
    backgroundColor: Colors.background,
    borderRadius: Radius.md,
    borderWidth: 1,
    borderColor: Colors.border,
  },
  input: {
    height: 52,
    paddingHorizontal: Spacing.md,
    fontSize: 16,
    color: Colors.text,
  },
  switchModeBtn: {
    alignItems: 'center',
    paddingTop: Spacing.sm,
    minHeight: 44,
    justifyContent: 'center',
  },
  switchModeText: {
    fontSize: 14,
    color: Colors.textSecondary,
  },
  legal: {
    textAlign: 'center',
    color: Colors.textSecondary,
    fontSize: 12,
    marginTop: Spacing.lg,
    paddingHorizontal: Spacing.xl,
  },
  legalLink: {
    color: Colors.textSecondary,
    textDecorationLine: 'underline',
  },
});

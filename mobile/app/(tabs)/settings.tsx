import React, { useState, useEffect } from 'react';
import { 
  View, Text, StyleSheet, ScrollView, Switch, 
  TextInput, TouchableOpacity, Alert, ActivityIndicator 
} from 'react-native';
import Header from '../../src/components/Header';
import { api } from '../../src/services/api';
import { theme } from '../../src/styles/theme';
import { Ionicons } from '@expo/vector-icons';

type RouterMode = 'paper' | 'shadow' | 'live';

export default function SettingsDashboard() {
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  
  // States
  const [killSwitch, setKillSwitch] = useState({ enabled: false, reason: '' });
  const [routerMode, setRouterMode] = useState<RouterMode>('paper');
  const [dailyLoss, setDailyLoss] = useState({ enabled: true, soft_warn_usd: 100, hard_halt_usd: 200 });
  const [telegram, setTelegram] = useState({ bot_token: '', chat_id: '', enabled: false, reachable: false, hint: '' });
  const [systemInfo, setSystemInfo] = useState<any>(null);

  const fetchSettings = async () => {
    try {
      const [ks, dl, rm, tg, info] = await Promise.all([
        api.get<any>('/api/v1/trading/kill-switch'),
        api.get<any>('/api/v1/risk/daily-loss'),
        api.get<any>('/api/v1/trading/algo-router-mode'),
        api.get<any>('/api/v1/config/telegram'),
        api.get<any>('/api/v1/config/info'),
      ]);

      setKillSwitch({ enabled: ks.enabled, reason: ks.reason || '' });
      setRouterMode((rm.mode || 'paper') as RouterMode);
      setDailyLoss({
        enabled: dl.enabled !== false,
        soft_warn_usd: dl.soft_warn_usd || 100,
        hard_halt_usd: dl.hard_halt_usd || 200
      });
      setTelegram({
        bot_token: '',
        chat_id: tg.chat_id || '',
        enabled: tg.enabled || false,
        reachable: tg.reachable || false,
        hint: tg.bot_token_hint || ''
      });
      setSystemInfo(info);
    } catch (e) {
      console.warn('Error loading settings:', e);
    }
  };

  useEffect(() => {
    setLoading(true);
    fetchSettings().finally(() => setLoading(false));
  }, []);

  const handleToggleKill = async () => {
    setBusy(true);
    try {
      const next = !killSwitch.enabled;
      await api.post('/api/v1/trading/kill-switch', {
        enabled: next,
        reason: next ? 'manual mobile operator halt' : ''
      });
      Alert.alert(next ? 'SYSTEM HALTED' : 'SYSTEM ARMED', next ? 'All auto-trading has been paused.' : 'System is active.');
      await fetchSettings();
    } catch (e: any) {
      Alert.alert('Error', e.message || 'Failed to update kill switch.');
    } finally {
      setBusy(false);
    }
  };

  const handleChangeMode = async (mode: RouterMode) => {
    setBusy(true);
    try {
      await api.post('/api/v1/trading/algo-router-mode', { mode });
      setRouterMode(mode);
      Alert.alert('Mode Switched', `Trading engine router is now in ${mode.toUpperCase()} mode.`);
      await fetchSettings();
    } catch (e: any) {
      Alert.alert('Error', e.message || 'Failed to switch router mode.');
    } finally {
      setBusy(false);
    }
  };

  const handleSaveDailyLoss = async () => {
    setBusy(true);
    try {
      await api.post('/api/v1/risk/daily-loss', {
        enabled: dailyLoss.enabled,
        soft_warn_usd: Number(dailyLoss.soft_warn_usd),
        hard_halt_usd: Number(dailyLoss.hard_halt_usd)
      });
      Alert.alert('Success', 'Daily loss limits updated successfully.');
      await fetchSettings();
    } catch (e: any) {
      Alert.alert('Error', e.message || 'Failed to save daily loss configurations.');
    } finally {
      setBusy(false);
    }
  };

  const handleSaveTelegram = async () => {
    setBusy(true);
    try {
      await api.put('/api/v1/config/telegram', {
        bot_token: telegram.bot_token,
        chat_id: telegram.chat_id,
        enabled: true
      });
      Alert.alert('Success', 'Telegram credentials saved.');
      await fetchSettings();
    } catch (e: any) {
      Alert.alert('Error', e.message || 'Failed to save Telegram configurations.');
    } finally {
      setBusy(false);
    }
  };

  const handleTestTelegram = async () => {
    setBusy(true);
    try {
      const res = await api.post<any>('/api/v1/config/telegram/test', {});
      if (res.reachable) {
        Alert.alert('Success', 'Test message sent successfully!');
      } else {
        Alert.alert('Fail', 'Verification message failed to deliver.');
      }
      await fetchSettings();
    } catch (e: any) {
      Alert.alert('Error', e.message || 'Failed to trigger Telegram test.');
    } finally {
      setBusy(false);
    }
  };

  if (loading) {
    return (
      <View style={[styles.container, styles.center]}>
        <ActivityIndicator size="large" color={theme.colors.blue} />
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <Header />
      <ScrollView contentContainerStyle={styles.scrollContainer}>
        
        {/* Trading Mode Selector */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>ROUTER MODE</Text>
          <View style={styles.modeRow}>
            {(['paper', 'shadow', 'live'] as RouterMode[]).map((mode) => {
              const isActive = routerMode === mode;
              let activeColor = theme.colors.textMuted;
              if (mode === 'paper') activeColor = theme.colors.textDim;
              if (mode === 'shadow') activeColor = theme.colors.blue;
              if (mode === 'live') activeColor = theme.colors.red;

              return (
                <TouchableOpacity
                  key={mode}
                  style={[
                    styles.modeButton,
                    isActive ? { backgroundColor: 'rgba(255,255,255,0.05)', borderColor: activeColor } : null
                  ]}
                  onPress={() => handleChangeMode(mode)}
                  disabled={busy}
                >
                  <Text style={[styles.modeButtonText, { color: isActive ? activeColor : theme.colors.textMuted }]}>
                    {mode.toUpperCase()}
                  </Text>
                </TouchableOpacity>
              );
            })}
          </View>
        </View>

        {/* Global Safety (Kill Switch) */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>GLOBAL SAFETY</Text>
          <View style={styles.card}>
            <View style={styles.switchRow}>
              <View>
                <Text style={styles.cardTitle}>Kill Switch</Text>
                <Text style={styles.cardSubtitle}>
                  {killSwitch.enabled ? `HALTED: ${killSwitch.reason}` : 'System is ARMED and operating'}
                </Text>
              </View>
              <Switch
                value={killSwitch.enabled}
                onValueChange={handleToggleKill}
                disabled={busy}
                trackColor={{ false: '#3f3f46', true: theme.colors.red }}
                thumbColor={killSwitch.enabled ? '#fff' : '#a1a1aa'}
              />
            </View>
          </View>
        </View>

        {/* Daily Loss Control */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>DAILY LOSS CONFIG</Text>
          <View style={styles.card}>
            <View style={styles.switchRow}>
              <Text style={styles.cardTitle}>Enable Circuit Breaker</Text>
              <Switch
                value={dailyLoss.enabled}
                onValueChange={(val) => setDailyLoss({ ...dailyLoss, enabled: val })}
                trackColor={{ false: '#3f3f46', true: theme.colors.green }}
              />
            </View>

            <View style={styles.inputContainer}>
              <Text style={styles.inputLabel}>SOFT WARN LIMIT (USD)</Text>
              <TextInput
                style={styles.input}
                value={String(dailyLoss.soft_warn_usd)}
                onChangeText={(val) => setDailyLoss({ ...dailyLoss, soft_warn_usd: Number(val) || 0 })}
                keyboardType="numeric"
                placeholderTextColor={theme.colors.textMuted}
              />
            </View>

            <View style={styles.inputContainer}>
              <Text style={styles.inputLabel}>HARD HALT LIMIT (USD)</Text>
              <TextInput
                style={styles.input}
                value={String(dailyLoss.hard_halt_usd)}
                onChangeText={(val) => setDailyLoss({ ...dailyLoss, hard_halt_usd: Number(val) || 0 })}
                keyboardType="numeric"
                placeholderTextColor={theme.colors.textMuted}
              />
            </View>

            <TouchableOpacity style={styles.saveButton} onPress={handleSaveDailyLoss} disabled={busy}>
              <Text style={styles.saveButtonText}>SAVE LOSS PARAMETERS</Text>
            </TouchableOpacity>
          </View>
        </View>

        {/* Telegram Notifications */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>TELEGRAM NOTIFICATIONS</Text>
          <View style={styles.card}>
            <View style={styles.statusRow}>
              <Text style={styles.cardTitle}>Status</Text>
              <View style={styles.statusBadge}>
                <View style={[styles.dot, { backgroundColor: telegram.reachable ? theme.colors.green : theme.colors.red }]} />
                <Text style={[styles.statusText, { color: telegram.reachable ? theme.colors.green : theme.colors.red }]}>
                  {telegram.reachable ? 'CONNECTED' : 'DISCONNECTED'}
                </Text>
              </View>
            </View>

            <View style={styles.inputContainer}>
              <Text style={styles.inputLabel}>BOT TOKEN {telegram.hint ? `(${telegram.hint})` : ''}</Text>
              <TextInput
                style={styles.input}
                value={telegram.bot_token}
                onChangeText={(val) => setTelegram({ ...telegram, bot_token: val })}
                placeholder="Enter new token to update"
                placeholderTextColor={theme.colors.textMuted}
                secureTextEntry
              />
            </View>

            <View style={styles.inputContainer}>
              <Text style={styles.inputLabel}>CHAT ID</Text>
              <TextInput
                style={styles.input}
                value={telegram.chat_id}
                onChangeText={(val) => setTelegram({ ...telegram, chat_id: val })}
                placeholder="Enter telegram Chat ID"
                placeholderTextColor={theme.colors.textMuted}
              />
            </View>

            <View style={styles.actionsRow}>
              <TouchableOpacity style={[styles.saveButton, { flex: 1, marginRight: 8 }]} onPress={handleSaveTelegram} disabled={busy}>
                <Text style={styles.saveButtonText}>SAVE CREDENTIALS</Text>
              </TouchableOpacity>
              <TouchableOpacity 
                style={[styles.testButton, { backgroundColor: 'rgba(59, 130, 246, 0.15)', borderColor: theme.colors.blue, borderWidth: 1 }]} 
                onPress={handleTestTelegram} 
                disabled={busy}
              >
                <Text style={[styles.saveButtonText, { color: theme.colors.blue }]}>TEST MSG</Text>
              </TouchableOpacity>
            </View>
          </View>
        </View>

        {/* System Info */}
        {systemInfo && (
          <View style={styles.section}>
            <Text style={styles.sectionTitle}>SYSTEM DIAGNOSTICS</Text>
            <View style={styles.card}>
              <View style={styles.diagRow}>
                <Text style={styles.diagLabel}>Version</Text>
                <Text style={styles.diagValue}>{systemInfo.version}</Text>
              </View>
              <View style={styles.diagRow}>
                <Text style={styles.diagLabel}>Environment</Text>
                <Text style={styles.diagValue}>{systemInfo.environment}</Text>
              </View>
              <View style={styles.diagRow}>
                <Text style={styles.diagLabel}>Exchange Adapter</Text>
                <Text style={styles.diagValue}>{systemInfo.exchange_adapter}</Text>
              </View>
              <View style={styles.diagRow}>
                <Text style={styles.diagLabel}>Database File</Text>
                <Text style={styles.diagValue} numberOfLines={1}>{systemInfo.db_path}</Text>
              </View>
            </View>
          </View>
        )}
        
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: theme.colors.background,
  },
  center: {
    justifyContent: 'center',
    alignItems: 'center',
  },
  scrollContainer: {
    padding: theme.spacing.md,
    paddingBottom: 40,
  },
  section: {
    marginBottom: theme.spacing.lg,
  },
  sectionTitle: {
    color: theme.colors.textMuted,
    fontSize: 10,
    fontWeight: '800',
    letterSpacing: 1,
    marginBottom: theme.spacing.sm,
  },
  modeRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  modeButton: {
    flex: 1,
    height: 44,
    backgroundColor: theme.colors.bgCard,
    borderWidth: 1,
    borderColor: theme.colors.border,
    borderRadius: theme.borderRadius.sm,
    justifyContent: 'center',
    alignItems: 'center',
    marginHorizontal: 4,
  },
  modeButtonText: {
    fontSize: 11,
    fontWeight: '800',
  },
  card: {
    backgroundColor: theme.colors.bgCard,
    borderColor: theme.colors.border,
    borderWidth: 1,
    borderRadius: theme.borderRadius.md,
    padding: theme.spacing.md,
  },
  switchRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  cardTitle: {
    color: theme.colors.textBright,
    fontSize: 13,
    fontWeight: '700',
  },
  cardSubtitle: {
    color: theme.colors.textMuted,
    fontSize: 10,
    marginTop: 2,
  },
  inputContainer: {
    marginTop: theme.spacing.md,
  },
  inputLabel: {
    color: theme.colors.textMuted,
    fontSize: 8,
    fontWeight: '800',
    letterSpacing: 0.5,
    marginBottom: 6,
  },
  input: {
    height: 40,
    backgroundColor: theme.colors.bgHeader,
    borderColor: theme.colors.border,
    borderWidth: 1,
    borderRadius: theme.borderRadius.sm,
    paddingHorizontal: theme.spacing.sm,
    color: theme.colors.textBright,
    fontFamily: theme.fonts.mono,
    fontSize: 13,
  },
  saveButton: {
    height: 38,
    backgroundColor: theme.colors.border,
    borderRadius: theme.borderRadius.sm,
    justifyContent: 'center',
    alignItems: 'center',
    marginTop: theme.spacing.md,
  },
  saveButtonText: {
    color: theme.colors.textBright,
    fontSize: 10,
    fontWeight: '800',
    letterSpacing: 0.5,
  },
  statusRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    borderBottomWidth: 1,
    borderBottomColor: theme.colors.border,
    paddingBottom: theme.spacing.sm,
    marginBottom: theme.spacing.xs,
  },
  statusBadge: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  dot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    marginRight: 6,
  },
  statusText: {
    fontSize: 10,
    fontWeight: '800',
  },
  actionsRow: {
    flexDirection: 'row',
    marginTop: theme.spacing.xs,
  },
  testButton: {
    height: 38,
    borderRadius: theme.borderRadius.sm,
    justifyContent: 'center',
    alignItems: 'center',
    marginTop: theme.spacing.md,
    paddingHorizontal: 16,
  },
  diagRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingVertical: 6,
    borderBottomWidth: 1,
    borderBottomColor: 'rgba(255,255,255,0.03)',
  },
  diagLabel: {
    color: theme.colors.textMuted,
    fontSize: 11,
  },
  diagValue: {
    color: theme.colors.textDim,
    fontSize: 11,
    fontFamily: theme.fonts.mono,
  },
});

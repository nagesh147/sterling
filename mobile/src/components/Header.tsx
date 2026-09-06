import React, { useEffect, useState } from 'react';
import { View, Text, StyleSheet, TouchableOpacity, ActivityIndicator } from 'react-native';
import { api } from '../services/api';
import { useStore } from '../store/useStore';
import { theme } from '../styles/theme';
import { Ionicons } from '@expo/vector-icons';

export default function Header() {
  const { routerMode, setRouterMode } = useStore();
  const [algoEnabled, setAlgoEnabled] = useState(false);
  const [loading, setLoading] = useState(false);
  const [connected, setConnected] = useState(true);

  /* Both routes this polled -- /trading/algo-mode and /trading/algo-router-mode
     -- went with the crypto surface, so every poll 404'd, the dot was pinned red
     and the badge showed the store's default PAPER TRADING no matter what the
     account was actually set to. A mode badge that cannot be wrong about live
     money is worth more than one that is always there.

     Kite's own status carries the real answer: `connected`, and `is_paper` off
     the ACCOUNT rather than a router setting. The master halt is the kill
     switch, which is what `assert_safe_to_trade` consults on every order. */
  const fetchStatus = async () => {
    try {
      const status = await api.get<{ connected: boolean; is_paper: boolean }>('/api/v1/kite/status');
      setRouterMode(status.is_paper ? 'paper' : 'live');
      setConnected(status.connected);
    } catch (e) {
      setConnected(false);
    }
    try {
      const kill = await api.get<{ enabled: boolean }>('/api/v1/kite/trading/kill-switch');
      // "Algo on" is "not halted": the kill switch is the only thing on this
      // build that stops every order path at once.
      setAlgoEnabled(!kill.enabled);
    } catch (e) {
      /* leave the last known state rather than claiming the algo is off */
    }
  };

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 3000);
    return () => clearInterval(interval);
  }, []);

  const toggleAlgo = async () => {
    setLoading(true);
    try {
      const nextState = !algoEnabled;
      await api.post('/api/v1/kite/trading/kill-switch', {
        enabled: !nextState,
        reason: nextState ? '' : 'manual mobile operator halt',
      });
      setAlgoEnabled(nextState);
    } catch (e) {
      console.warn('Failed to toggle Master Algo:', e);
    } finally {
      setLoading(false);
    }
  };

  const getModeStyles = () => {
    switch (routerMode) {
      case 'live':
        return { bg: theme.colors.red, text: 'LIVE TRADING' };
      case 'shadow':
        return { bg: theme.colors.amber, text: 'SHADOW TRADING' };
      default:
        return { bg: theme.colors.blue, text: 'PAPER TRADING' };
    }
  };

  const modeInfo = getModeStyles();

  return (
    <View style={styles.container}>
      <View style={styles.topRow}>
        <View style={styles.titleContainer}>
          <Text style={styles.titleText}>STERLING</Text>
          <Text style={styles.subText}>MOBILE TERMINAL</Text>
        </View>

        <View style={styles.badgeRow}>
          <View style={[styles.badge, { backgroundColor: modeInfo.bg }]}>
            <Text style={styles.badgeText}>{modeInfo.text}</Text>
          </View>
          <View style={[styles.statusDot, { backgroundColor: connected ? theme.colors.green : theme.colors.red }]} />
        </View>
      </View>

      <View style={styles.bottomRow}>
        <View style={styles.statsContainer}>
          <View style={styles.statItem}>
            <Text style={styles.statLabel}>SYSTEM</Text>
            <Text style={[styles.statVal, { color: connected ? theme.colors.green : theme.colors.red }]}>
              {connected ? 'ONLINE' : 'OFFLINE'}
            </Text>
          </View>
        </View>

        <TouchableOpacity 
          style={[styles.algoButton, algoEnabled ? styles.algoActive : styles.algoInactive]} 
          onPress={toggleAlgo}
          disabled={loading}
        >
          {loading ? (
            <ActivityIndicator size="small" color="#fff" />
          ) : (
            <>
              <Ionicons 
                name={algoEnabled ? "play-circle" : "pause-circle"} 
                size={16} 
                color="#fff" 
                style={{ marginRight: 4 }} 
              />
              <Text style={styles.algoButtonText}>
                {algoEnabled ? 'ALGO RUNNING' : 'ALGO PAUSED'}
              </Text>
            </>
          )}
        </TouchableOpacity>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    backgroundColor: theme.colors.bgHeader,
    paddingTop: 45, // Account for status bar spacing
    paddingHorizontal: theme.spacing.md,
    paddingBottom: theme.spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: theme.colors.border,
  },
  topRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: theme.spacing.sm,
  },
  titleContainer: {
    flexDirection: 'column',
  },
  titleText: {
    color: theme.colors.textBright,
    fontSize: 18,
    fontWeight: '800',
    letterSpacing: 1.5,
    fontFamily: theme.fonts.sans,
  },
  subText: {
    color: theme.colors.textMuted,
    fontSize: 9,
    fontWeight: '700',
    letterSpacing: 1,
  },
  badgeRow: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  badge: {
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 4,
    marginRight: 8,
  },
  badgeText: {
    color: '#ffffff',
    fontSize: 9,
    fontWeight: '900',
    letterSpacing: 0.5,
  },
  statusDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
  },
  bottomRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginTop: 4,
  },
  statsContainer: {
    flexDirection: 'row',
  },
  statItem: {
    marginRight: theme.spacing.md,
  },
  statLabel: {
    color: theme.colors.textMuted,
    fontSize: 8,
    fontWeight: '600',
  },
  statVal: {
    fontSize: 11,
    fontWeight: '700',
    fontFamily: theme.fonts.mono,
  },
  algoButton: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 4,
  },
  algoActive: {
    backgroundColor: theme.colors.green,
  },
  algoInactive: {
    backgroundColor: theme.colors.border,
  },
  algoButtonText: {
    color: '#fff',
    fontSize: 10,
    fontWeight: '800',
  },
});

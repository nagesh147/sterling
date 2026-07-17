import React, { useState, useEffect } from 'react';
import { 
  View, Text, StyleSheet, FlatList, TouchableOpacity, 
  RefreshControl, ActivityIndicator, ScrollView 
} from 'react-native';
import Header from '../../src/components/Header';
import { api } from '../../src/services/api';
import { theme } from '../../src/styles/theme';
import { Ionicons } from '@expo/vector-icons';

type TrackFilter = 'ALL' | 'VCP' | 'TREND' | 'REVERSION';

export default function SignalsTerminal() {
  const [activeFilter, setActiveFilter] = useState<TrackFilter>('ALL');
  const [signals, setSignals] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);

  // Poll VCP signals
  const fetchSignals = async () => {
    try {
      const res = await api.get<{ signals: any[] }>('/api/v1/directional/signals');
      setSignals(res.signals || []);
    } catch (e) {
      console.warn('Error fetching VCP signals:', e);
    }
  };

  useEffect(() => {
    setLoading(true);
    fetchSignals().finally(() => setLoading(false));
  }, []);

  // Poll signals every 4 seconds
  useEffect(() => {
    const interval = setInterval(fetchSignals, 4000);
    return () => clearInterval(interval);
  }, []);

  const onRefresh = async () => {
    setRefreshing(true);
    await fetchSignals();
    setRefreshing(false);
  };

  // Helper to categorize track names
  const getTrackCategory = (trackName: string): TrackFilter => {
    const norm = (trackName || '').toUpperCase();
    if (norm.includes('VCP')) return 'VCP';
    if (norm.includes('TREND') || norm.includes('FOLLOWING')) return 'TREND';
    if (norm.includes('REVERSION') || norm.includes('MEAN')) return 'REVERSION';
    return 'ALL';
  };

  // Calculate live filter counts
  const counts = {
    ALL: signals.length,
    VCP: signals.filter((s) => getTrackCategory(s.track) === 'VCP').length,
    TREND: signals.filter((s) => getTrackCategory(s.track) === 'TREND').length,
    REVERSION: signals.filter((s) => getTrackCategory(s.track) === 'REVERSION').length,
  };

  // Filter signals
  const filteredSignals = signals.filter((s) => {
    if (activeFilter === 'ALL') return true;
    return getTrackCategory(s.track) === activeFilter;
  });

  const getTrackStyles = (track: string) => {
    const cat = getTrackCategory(track);
    switch (cat) {
      case 'VCP':
        return { bg: 'rgba(245, 158, 11, 0.15)', text: theme.colors.amber, border: theme.colors.amber };
      case 'TREND':
        return { bg: 'rgba(16, 185, 129, 0.15)', text: theme.colors.green, border: theme.colors.green };
      case 'REVERSION':
        return { bg: 'rgba(139, 92, 246, 0.15)', text: '#8b5cf6', border: '#8b5cf6' };
      default:
        return { bg: 'rgba(156, 163, 175, 0.15)', text: theme.colors.textDim, border: theme.colors.border };
    }
  };

  const renderFilterPills = () => {
    const filters: { key: TrackFilter; label: string; color: string }[] = [
      { key: 'ALL', label: `ALL (${counts.ALL})`, color: theme.colors.textBright },
      { key: 'VCP', label: `VCP (${counts.VCP})`, color: theme.colors.amber },
      { key: 'TREND', label: `TREND (${counts.TREND})`, color: theme.colors.green },
      { key: 'REVERSION', label: `REVERSION (${counts.REVERSION})`, color: '#8b5cf6' },
    ];

    return (
      <View style={styles.pillScroll}>
        {filters.map((f) => (
          <TouchableOpacity
            key={f.key}
            style={[
              styles.pillButton,
              activeFilter === f.key ? { backgroundColor: theme.colors.border, borderColor: f.color } : null
            ]}
            onPress={() => setActiveFilter(f.key)}
          >
            <Text style={[styles.pillText, { color: f.color }]}>{f.label}</Text>
          </TouchableOpacity>
        ))}
      </View>
    );
  };

  const renderSignalItem = ({ item }: { item: any }) => {
    const isLong = item.direction === 'LONG' || item.direction === 'BUY';
    const trackStyles = getTrackStyles(item.track);
    const ageSec = Math.max(0, Math.floor((Date.now() - (item.timestamp_ms || Date.now())) / 1000));
    const ageStr = ageSec < 60 ? `${ageSec}s ago` : `${Math.floor(ageSec / 60)}m ago`;

    return (
      <View style={styles.signalCard}>
        <View style={styles.cardHeader}>
          <View>
            <Text style={styles.symbolText}>{item.underlying || item.futures_symbol}</Text>
            <View style={styles.badgeRow}>
              <View style={[styles.trackBadge, { backgroundColor: trackStyles.bg, borderColor: trackStyles.border }]}>
                <Text style={[styles.trackText, { color: trackStyles.text }]}>
                  {item.track ? item.track.toUpperCase() : 'UNKNOWN'}
                </Text>
              </View>
              <Text style={styles.ageText}>{ageStr}</Text>
            </View>
          </View>

          <View style={styles.scoreContainer}>
            <Text style={styles.scoreVal}>{item.score || 0}</Text>
            <Text style={styles.scoreLabel}>SCORE</Text>
          </View>
        </View>

        <View style={styles.statsGrid}>
          <View style={styles.gridCol}>
            <Text style={styles.statLabel}>DIRECTION</Text>
            <Text style={[styles.statVal, { color: isLong ? theme.colors.green : theme.colors.red }]}>
              {isLong ? 'BUY / LONG' : 'SELL / SHORT'}
            </Text>
          </View>
          <View style={styles.gridCol}>
            <Text style={styles.statLabel}>ENTRY</Text>
            <Text style={styles.statVal}>${parseFloat(item.entry || 0).toLocaleString()}</Text>
          </View>
        </View>

        <View style={[styles.statsGrid, { marginTop: theme.spacing.sm }]}>
          <View style={styles.gridCol}>
            <Text style={styles.statLabel}>STOP LOSS</Text>
            <Text style={[styles.statVal, { color: theme.colors.red }]}>
              {item.stop_loss ? `$${parseFloat(item.stop_loss).toLocaleString()}` : '--'}
            </Text>
          </View>
          <View style={styles.gridCol}>
            <Text style={styles.statLabel}>TAKE PROFIT</Text>
            <Text style={[styles.statVal, { color: theme.colors.green }]}>
              {item.take_profit ? `$${parseFloat(item.take_profit).toLocaleString()}` : '--'}
            </Text>
          </View>
        </View>
      </View>
    );
  };

  return (
    <View style={styles.container}>
      <Header />
      
      {/* Scrollable filters row */}
      {renderFilterPills()}

      {/* Signals List */}
      {loading && signals.length === 0 ? (
        <ActivityIndicator style={styles.loader} size="large" color={theme.colors.amber} />
      ) : (
        <FlatList
          data={filteredSignals}
          keyExtractor={(item, index) => (item.underlying || item.futures_symbol) + index}
          renderItem={renderSignalItem}
          contentContainerStyle={styles.listContainer}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
          ListEmptyComponent={
            <ScrollView contentContainerStyle={styles.emptyContainer}>
              <Ionicons name="radio-outline" size={48} color={theme.colors.textMuted} />
              <Text style={styles.emptyText}>No Signals Found for {activeFilter}</Text>
            </ScrollView>
          }
        />
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: theme.colors.background,
  },
  pillScroll: {
    flexDirection: 'row',
    paddingVertical: theme.spacing.sm,
    paddingHorizontal: theme.spacing.md,
    backgroundColor: theme.colors.bgHeader,
    borderBottomWidth: 1,
    borderBottomColor: theme.colors.border,
  },
  pillButton: {
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 16,
    borderWidth: 1,
    borderColor: 'transparent',
    marginRight: 8,
  },
  pillText: {
    fontSize: 10,
    fontWeight: '800',
  },
  listContainer: {
    padding: theme.spacing.md,
    paddingBottom: 40,
  },
  signalCard: {
    backgroundColor: theme.colors.bgCard,
    borderColor: theme.colors.border,
    borderWidth: 1,
    borderRadius: theme.borderRadius.md,
    padding: theme.spacing.md,
    marginBottom: theme.spacing.sm,
  },
  cardHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    borderBottomWidth: 1,
    borderBottomColor: theme.colors.border,
    paddingBottom: theme.spacing.sm,
    marginBottom: theme.spacing.sm,
  },
  symbolText: {
    color: theme.colors.textBright,
    fontSize: 14,
    fontWeight: '800',
    fontFamily: theme.fonts.mono,
  },
  badgeRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: 4,
  },
  trackBadge: {
    borderWidth: 1,
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 3,
    marginRight: 8,
  },
  trackText: {
    fontSize: 8,
    fontWeight: '800',
  },
  ageText: {
    color: theme.colors.textMuted,
    fontSize: 9,
    fontFamily: theme.fonts.mono,
  },
  scoreContainer: {
    alignItems: 'center',
  },
  scoreVal: {
    color: theme.colors.amber,
    fontSize: 16,
    fontWeight: '800',
    fontFamily: theme.fonts.mono,
  },
  scoreLabel: {
    color: theme.colors.textMuted,
    fontSize: 7,
    fontWeight: '700',
  },
  statsGrid: {
    flexDirection: 'row',
  },
  gridCol: {
    flex: 1,
  },
  statLabel: {
    color: theme.colors.textMuted,
    fontSize: 8,
    fontWeight: '700',
    letterSpacing: 0.5,
    marginBottom: 2,
  },
  statVal: {
    color: theme.colors.textBright,
    fontSize: 11,
    fontWeight: '600',
    fontFamily: theme.fonts.mono,
  },
  loader: {
    marginTop: 40,
  },
  emptyContainer: {
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 80,
  },
  emptyText: {
    color: theme.colors.textMuted,
    fontSize: 12,
    fontWeight: '700',
    marginTop: 8,
  },
});

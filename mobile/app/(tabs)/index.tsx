import React, { useState, useEffect } from 'react';
import { 
  View, Text, StyleSheet, FlatList, TouchableOpacity, 
  RefreshControl, ActivityIndicator, Alert, ScrollView 
} from 'react-native';
import Header from '../../src/components/Header';
import MetricCard from '../../src/components/MetricCard';
import OrderModal from '../../src/components/OrderModal';
import { api } from '../../src/services/api';
import { useStore } from '../../src/store/useStore';
import { theme } from '../../src/styles/theme';
import { Ionicons } from '@expo/vector-icons';

export default function CryptoTerminal() {
  const { selectedUnderlying, setSelectedUnderlying } = useStore();
  const [positions, setPositions] = useState<any[]>([]);
  const [pnlData, setPnlData] = useState({ open: 0, realized: 0 });
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  
  // Order modal states
  const [orderModalVisible, setOrderModalVisible] = useState(false);

  const fetchCryptoData = async () => {
    try {
      // 1. Fetch positions
      const posRes = await api.get<{ positions: any[] }>('/api/v1/positions?status=open');
      setPositions(posRes.positions || []);

      // 2. Fetch Live PNL metrics
      const pnlRes = await api.get<any>('/api/v1/positions/live-pnl');
      setPnlData({
        open: pnlRes?.open_pnl_usd || 0,
        realized: pnlRes?.total_realized_pnl_usd || pnlRes?.realized_pnl_usd || 0,
      });
    } catch (e) {
      console.warn('Error fetching crypto terminal data:', e);
    }
  };

  useEffect(() => {
    setLoading(true);
    fetchCryptoData().finally(() => setLoading(false));
  }, []);

  // Poll rates every 3 seconds
  useEffect(() => {
    const interval = setInterval(fetchCryptoData, 3000);
    return () => clearInterval(interval);
  }, []);

  const onRefresh = async () => {
    setRefreshing(true);
    await fetchCryptoData();
    setRefreshing(false);
  };

  const handleClosePosition = async (posId: string, symbol: string) => {
    Alert.alert(
      'Confirm Close',
      `Are you sure you want to market close your ${symbol} position?`,
      [
        { text: 'Cancel', style: 'cancel' },
        { 
          text: 'Close Position', 
          style: 'destructive',
          onPress: async () => {
            try {
              await api.post(`/api/v1/positions/${posId}/close`, {});
              Alert.alert('Closed', 'Position has been queued for market close.');
              fetchCryptoData();
            } catch (e: any) {
              Alert.alert('Error', e.message || 'Failed to close position.');
            }
          }
        }
      ]
    );
  };

  const renderPositionItem = ({ item }: { item: any }) => {
    const isLong = item.direction === 'LONG' || item.side === 'BUY';
    const profit = item.unrealized_pnl_usd || item.pnl || 0;
    
    return (
      <View style={styles.positionCard}>
        <View style={styles.posHeader}>
          <View>
            <Text style={styles.posSymbol}>{item.symbol || item.underlying}</Text>
            <View style={styles.directionRow}>
              <View style={[styles.directionBadge, { backgroundColor: isLong ? theme.colors.green : theme.colors.red }]}>
                <Text style={styles.directionText}>{isLong ? 'LONG' : 'SHORT'}</Text>
              </View>
              <Text style={styles.sizeText}>Size: {item.size || item.quantity}</Text>
            </View>
          </View>

          <TouchableOpacity 
            style={styles.closeBtn} 
            onPress={() => handleClosePosition(item.id || item.position_id, item.symbol || item.underlying)}
          >
            <Text style={styles.closeBtnText}>CLOSE</Text>
          </TouchableOpacity>
        </View>

        <View style={styles.posStatsRow}>
          <View>
            <Text style={styles.statLabel}>ENTRY PRICE</Text>
            <Text style={styles.statVal}>${parseFloat(item.entry_price || item.average_price || 0).toLocaleString()}</Text>
          </View>
          <View style={styles.alignCenter}>
            <Text style={styles.statLabel}>MARK PRICE</Text>
            <Text style={styles.statVal}>${parseFloat(item.mark_price || item.last_price || 0).toLocaleString()}</Text>
          </View>
          <View style={styles.alignRight}>
            <Text style={styles.statLabel}>UNREALIZED P&L</Text>
            <Text style={[styles.statVal, { color: profit >= 0 ? theme.colors.green : theme.colors.red, fontWeight: '800' }]}>
              ${profit.toFixed(2)}
            </Text>
          </View>
        </View>
      </View>
    );
  };

  return (
    <View style={styles.container}>
      <Header />

      {/* Top Metric Cards */}
      <View style={styles.metricsRow}>
        <MetricCard 
          label="Open P&L" 
          value={`$${pnlData.open.toFixed(2)}`} 
          type={pnlData.open >= 0 ? 'green' : 'red'} 
        />
        <MetricCard 
          label="Realized P&L" 
          value={`$${pnlData.realized.toFixed(2)}`} 
          type={pnlData.realized >= 0 ? 'green' : 'red'} 
        />
        <MetricCard 
          label="Asset" 
          value={selectedUnderlying} 
          subValue="10x Leverage"
        />
      </View>

      {/* Open Positions Title */}
      <Text style={styles.sectionHeader}>OPEN POSITIONS ({positions.length})</Text>

      {/* Positions List */}
      {loading && positions.length === 0 ? (
        <ActivityIndicator style={styles.loader} size="large" color={theme.colors.blue} />
      ) : (
        <FlatList
          data={positions}
          keyExtractor={(item) => item.id || item.position_id || item.symbol}
          renderItem={renderPositionItem}
          contentContainerStyle={styles.listContainer}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
          ListEmptyComponent={
            <ScrollView contentContainerStyle={styles.emptyContainer}>
              <Ionicons name="swap-horizontal-outline" size={48} color={theme.colors.textMuted} />
              <Text style={styles.emptyText}>No Open Positions</Text>
            </ScrollView>
          }
        />
      )}

      {/* Floating Action Button (FAB) for Placing Orders */}
      <TouchableOpacity 
        style={styles.fab}
        onPress={() => setOrderModalVisible(true)}
      >
        <Ionicons name="add" size={28} color="#fff" />
      </TouchableOpacity>

      <OrderModal
        visible={orderModalVisible}
        onClose={() => setOrderModalVisible(false)}
        symbol={selectedUnderlying}
        marketType="crypto"
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: theme.colors.background,
  },
  metricsRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingHorizontal: theme.spacing.sm,
    marginTop: theme.spacing.md,
  },
  sectionHeader: {
    color: theme.colors.textMuted,
    fontSize: 10,
    fontWeight: '800',
    letterSpacing: 1,
    marginTop: theme.spacing.lg,
    marginHorizontal: theme.spacing.md,
    marginBottom: theme.spacing.sm,
  },
  listContainer: {
    paddingHorizontal: theme.spacing.md,
    paddingBottom: 80, // Safe padding for FAB
  },
  positionCard: {
    backgroundColor: theme.colors.bgCard,
    borderColor: theme.colors.border,
    borderWidth: 1,
    borderRadius: theme.borderRadius.md,
    padding: theme.spacing.md,
    marginBottom: theme.spacing.sm,
  },
  posHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    borderBottomWidth: 1,
    borderBottomColor: theme.colors.border,
    paddingBottom: theme.spacing.sm,
    marginBottom: theme.spacing.sm,
  },
  posSymbol: {
    color: theme.colors.textBright,
    fontSize: 14,
    fontWeight: '800',
    fontFamily: theme.fonts.mono,
  },
  directionRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: 4,
  },
  directionBadge: {
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 3,
    marginRight: 8,
  },
  directionText: {
    color: '#fff',
    fontSize: 8,
    fontWeight: '800',
  },
  sizeText: {
    color: theme.colors.textDim,
    fontSize: 11,
    fontFamily: theme.fonts.mono,
  },
  closeBtn: {
    backgroundColor: 'rgba(239, 68, 68, 0.15)',
    borderColor: theme.colors.red,
    borderWidth: 1,
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 4,
  },
  closeBtnText: {
    color: theme.colors.red,
    fontSize: 10,
    fontWeight: '800',
    letterSpacing: 0.5,
  },
  posStatsRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
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
    fontSize: 12,
    fontWeight: '600',
    fontFamily: theme.fonts.mono,
  },
  alignCenter: {
    alignItems: 'center',
  },
  alignRight: {
    alignItems: 'flex-end',
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
  fab: {
    position: 'absolute',
    bottom: 24,
    right: 24,
    width: 56,
    height: 56,
    borderRadius: 28,
    backgroundColor: theme.colors.blue,
    alignItems: 'center',
    justifyContent: 'center',
    elevation: 8,
    shadowColor: '#000',
    shadowOpacity: 0.3,
    shadowRadius: 4,
    shadowOffset: { width: 0, height: 2 },
  },
});

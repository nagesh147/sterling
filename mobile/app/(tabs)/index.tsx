import React, { useState, useEffect } from 'react';
import { 
  View, Text, StyleSheet, FlatList, TouchableOpacity, 
  ScrollView, RefreshControl, ActivityIndicator 
} from 'react-native';
import Header from '../../src/components/Header';
import OrderModal from '../../src/components/OrderModal';
import { api } from '../../src/services/api';
import { theme } from '../../src/styles/theme';
import { Ionicons } from '@expo/vector-icons';

type SubTab = 'WATCHLIST' | 'POSITIONS' | 'HOLDINGS' | 'ORDERS';

/* There is no placeholder watchlist any more.
   There used to be five hard-coded rows -- fixed prices, and two NIFTY July
   2026 contracts -- and the WATCHLIST tab had no fetch branch at all, so those
   rows were never replaced. Tapping one opened the LIVE order modal, which
   means a mobile operator could be shown an invented price and send an order
   for a contract that no longer lists. An empty list is the honest state while
   there is nothing real to show. */
type WatchRow = { symbol: string; name: string; price: number | null; change: number | null };

export default function IndianMarketsTerminal() {
  const [activeTab, setActiveTab] = useState<SubTab>('WATCHLIST');
  const [watchlist, setWatchlist] = useState<WatchRow[]>([]);
  const [positions, setPositions] = useState<any[]>([]);
  const [holdings, setHoldings] = useState<any[]>([]);
  const [orders, setOrders] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);

  // Order modal states
  const [orderModalVisible, setOrderModalVisible] = useState(false);
  const [selectedSymbol, setSelectedSymbol] = useState('');

  const fetchKiteData = async () => {
    try {
      if (activeTab === 'WATCHLIST') {
        // Kite Connect has no saved-marketwatch endpoint; the backend synthesises
        // one from holdings, positions and GTTs.
        const res = await api.get<{ items: { symbol: string; name?: string }[] }>(
          '/api/v1/kite/watchlist/sync');
        const items = res.items || [];
        if (!items.length) { setWatchlist([]); return; }
        const query = items.map((i) => `i=${encodeURIComponent(i.symbol)}`).join('&');
        const quotes = await api.get<Record<string, any>>(`/api/v1/kite/quote?${query}`);
        setWatchlist(items.map((i) => {
          const q = quotes?.[i.symbol];
          const ltp = typeof q?.last_price === 'number' ? q.last_price : null;
          const prev = q?.ohlc?.close;
          // A row with no quote keeps null rather than 0: zero is a price, and
          // this is the absence of one.
          const change = (ltp != null && typeof prev === 'number' && prev > 0)
            ? ((ltp - prev) / prev) * 100 : null;
          return { symbol: i.symbol, name: i.name || i.symbol, price: ltp, change };
        }));
      } else if (activeTab === 'POSITIONS') {
        const res = await api.get<{ net: any[]; day: any[] }>('/api/v1/kite/positions');
        setPositions(res.net || []);
      } else if (activeTab === 'HOLDINGS') {
        const res = await api.get<any[]>('/api/v1/kite/holdings');
        setHoldings(res || []);
      } else if (activeTab === 'ORDERS') {
        const res = await api.get<any[]>('/api/v1/kite/orders');
        setOrders(res || []);
      }
    } catch (e) {
      console.warn('Error fetching Kite data:', e);
    }
  };

  useEffect(() => {
    setLoading(true);
    fetchKiteData().finally(() => setLoading(false));
  }, [activeTab]);

  // Periodic polling for real-time rates
  useEffect(() => {
    const interval = setInterval(fetchKiteData, 4000);
    return () => clearInterval(interval);
  }, [activeTab]);

  const onRefresh = async () => {
    setRefreshing(true);
    await fetchKiteData();
    setRefreshing(false);
  };

  const handleOpenOrder = (symbol: string) => {
    setSelectedSymbol(symbol);
    setOrderModalVisible(true);
  };

  const renderSubTabs = () => {
    const tabs: SubTab[] = ['WATCHLIST', 'POSITIONS', 'HOLDINGS', 'ORDERS'];
    return (
      <View style={styles.subTabContainer}>
        {tabs.map((tab) => (
          <TouchableOpacity
            key={tab}
            style={[styles.subTabButton, activeTab === tab ? styles.subTabActive : null]}
            onPress={() => setActiveTab(tab)}
          >
            <Text style={[styles.subTabText, activeTab === tab ? styles.subTabTextActive : null]}>
              {tab}
            </Text>
          </TouchableOpacity>
        ))}
      </View>
    );
  };

  const renderWatchlist = () => {
    return (
      <FlatList
        data={watchlist}
        keyExtractor={(item) => item.symbol}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
        ListEmptyComponent={(
          <Text style={styles.emptyText}>
            {loading ? 'Loading…' : 'Nothing to watch. Holdings, open positions and GTTs appear here.'}
          </Text>
        )}
        renderItem={({ item }) => {
          // No quote, no order. The row is what tells you the price, so a row
          // that cannot tell you must not be the thing that starts a trade.
          const priced = item.price != null;
          return (
            <TouchableOpacity
              style={styles.cardRow}
              disabled={!priced}
              onPress={() => handleOpenOrder(item.symbol)}
            >
              <View>
                <Text style={styles.symbolText}>{item.symbol}</Text>
                <Text style={styles.nameText}>{item.name}</Text>
              </View>
              <View style={styles.rightAligned}>
                <Text style={styles.priceVal}>{priced ? `₹${item.price!.toFixed(2)}` : 'No quote'}</Text>
                {item.change != null && (
                  <Text style={[styles.changeText, { color: item.change >= 0 ? theme.colors.green : theme.colors.red }]}>
                    {item.change >= 0 ? '+' : ''}{item.change.toFixed(2)}%
                  </Text>
                )}
              </View>
            </TouchableOpacity>
          );
        }}
      />
    );
  };

  const renderPositions = () => {
    if (loading) return <ActivityIndicator style={styles.loader} size="large" color={theme.colors.orange} />;
    
    if (positions.length === 0) {
      return (
        <ScrollView 
          contentContainerStyle={styles.emptyContainer}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
        >
          <Ionicons name="briefcase-outline" size={48} color={theme.colors.textMuted} />
          <Text style={styles.emptyText}>No Active Positions</Text>
        </ScrollView>
      );
    }

    return (
      <FlatList
        data={positions}
        keyExtractor={(item, index) => item.tradingsymbol + index}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
        renderItem={({ item }) => {
          const pnl = item.pnl || 0;
          return (
            <View style={styles.cardRow}>
              <View>
                <Text style={styles.symbolText}>{item.exchange}:{item.tradingsymbol}</Text>
                <Text style={styles.nameText}>Qty: {item.quantity} | Avg: ₹{item.average_price}</Text>
              </View>
              <View style={styles.rightAligned}>
                <Text style={styles.priceVal}>LTP: ₹{item.last_price}</Text>
                <Text style={[styles.pnlText, { color: pnl >= 0 ? theme.colors.green : theme.colors.red }]}>
                  ₹{pnl >= 0 ? '+' : ''}{pnl.toFixed(2)}
                </Text>
              </View>
            </View>
          );
        }}
      />
    );
  };

  const renderHoldings = () => {
    if (loading) return <ActivityIndicator style={styles.loader} size="large" color={theme.colors.orange} />;

    if (holdings.length === 0) {
      return (
        <ScrollView 
          contentContainerStyle={styles.emptyContainer}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
        >
          <Ionicons name="wallet-outline" size={48} color={theme.colors.textMuted} />
          <Text style={styles.emptyText}>No Holdings Found</Text>
        </ScrollView>
      );
    }

    return (
      <FlatList
        data={holdings}
        keyExtractor={(item) => item.isin}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
        renderItem={({ item }) => {
          const currentVal = item.quantity * item.last_price;
          const investedVal = item.quantity * item.average_price;
          const pnl = currentVal - investedVal;
          return (
            <View style={styles.cardRow}>
              <View>
                <Text style={styles.symbolText}>{item.tradingsymbol}</Text>
                <Text style={styles.nameText}>Qty: {item.quantity} | Avg: ₹{item.average_price}</Text>
              </View>
              <View style={styles.rightAligned}>
                <Text style={styles.priceVal}>₹{currentVal.toFixed(2)}</Text>
                <Text style={[styles.pnlText, { color: pnl >= 0 ? theme.colors.green : theme.colors.red }]}>
                  {pnl >= 0 ? '+' : ''}{((pnl / investedVal) * 100).toFixed(2)}%
                </Text>
              </View>
            </View>
          );
        }}
      />
    );
  };

  const renderOrders = () => {
    if (loading) return <ActivityIndicator style={styles.loader} size="large" color={theme.colors.orange} />;

    if (orders.length === 0) {
      return (
        <ScrollView 
          contentContainerStyle={styles.emptyContainer}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
        >
          <Ionicons name="receipt-outline" size={48} color={theme.colors.textMuted} />
          <Text style={styles.emptyText}>No Placed Orders</Text>
        </ScrollView>
      );
    }

    return (
      <FlatList
        data={orders}
        keyExtractor={(item) => item.order_id}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
        renderItem={({ item }) => {
          const statusColor = item.status === 'COMPLETE' ? theme.colors.green : item.status === 'REJECTED' ? theme.colors.red : theme.colors.amber;
          return (
            <View style={styles.cardRow}>
              <View>
                <Text style={styles.symbolText}>{item.tradingsymbol}</Text>
                <Text style={styles.nameText}>{item.transaction_type} • {item.quantity} Qty • {item.product}</Text>
              </View>
              <View style={styles.rightAligned}>
                <Text style={styles.priceVal}>₹{item.price || item.trigger_price || 0}</Text>
                <View style={[styles.statusBadge, { borderColor: statusColor }]}>
                  <Text style={[styles.statusBadgeText, { color: statusColor }]}>{item.status}</Text>
                </View>
              </View>
            </View>
          );
        }}
      />
    );
  };

  return (
    <View style={styles.container}>
      <Header />
      {renderSubTabs()}

      <View style={styles.contentContainer}>
        {activeTab === 'WATCHLIST' && renderWatchlist()}
        {activeTab === 'POSITIONS' && renderPositions()}
        {activeTab === 'HOLDINGS' && renderHoldings()}
        {activeTab === 'ORDERS' && renderOrders()}
      </View>

      <OrderModal
        visible={orderModalVisible}
        onClose={() => setOrderModalVisible(false)}
        symbol={selectedSymbol}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: theme.colors.background,
  },
  subTabContainer: {
    flexDirection: 'row',
    backgroundColor: theme.colors.bgHeader,
    borderBottomWidth: 1,
    borderBottomColor: theme.colors.border,
  },
  subTabButton: {
    flex: 1,
    paddingVertical: 12,
    alignItems: 'center',
    borderBottomWidth: 2,
    borderBottomColor: 'transparent',
  },
  subTabActive: {
    borderBottomColor: theme.colors.orange,
  },
  subTabText: {
    color: theme.colors.textMuted,
    fontSize: 10,
    fontWeight: '700',
    letterSpacing: 0.5,
  },
  subTabTextActive: {
    color: theme.colors.textBright,
  },
  contentContainer: {
    flex: 1,
    padding: theme.spacing.sm,
  },
  cardRow: {
    backgroundColor: theme.colors.bgCard,
    borderColor: theme.colors.border,
    borderWidth: 1,
    borderRadius: theme.borderRadius.md,
    padding: theme.spacing.md,
    marginBottom: theme.spacing.sm,
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  symbolText: {
    color: theme.colors.textBright,
    fontSize: 13,
    fontWeight: '800',
    fontFamily: theme.fonts.mono,
  },
  nameText: {
    color: theme.colors.textMuted,
    fontSize: 10,
    marginTop: 2,
  },
  rightAligned: {
    alignItems: 'flex-end',
  },
  priceVal: {
    color: theme.colors.textBright,
    fontSize: 13,
    fontWeight: '700',
    fontFamily: theme.fonts.mono,
  },
  changeText: {
    fontSize: 11,
    fontWeight: '700',
    fontFamily: theme.fonts.mono,
    marginTop: 2,
  },
  pnlText: {
    fontSize: 12,
    fontWeight: '800',
    fontFamily: theme.fonts.mono,
    marginTop: 2,
  },
  statusBadge: {
    borderWidth: 1,
    borderRadius: 3,
    paddingHorizontal: 6,
    paddingVertical: 2,
    marginTop: 4,
  },
  statusBadgeText: {
    fontSize: 9,
    fontWeight: '900',
  },
  loader: {
    marginTop: 40,
  },
  emptyContainer: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 100,
  },
  emptyText: {
    color: theme.colors.textMuted,
    fontSize: 13,
    fontWeight: '700',
    marginTop: 12,
  },
});


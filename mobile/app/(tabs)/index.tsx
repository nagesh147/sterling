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

// Default Watchlist if backend is not loaded
const DEFAULT_WATCHLIST = [
  { symbol: 'NSE:INFY', name: 'Infosys Ltd', price: 1845.50, change: 1.25 },
  { symbol: 'NSE:TCS', name: 'Tata Consultancy Services', price: 3820.10, change: -0.45 },
  { symbol: 'NSE:RELIANCE', name: 'Reliance Industries', price: 2450.00, change: 0.85 },
  { symbol: 'NFO:NIFTY26JUL22000CE', name: 'Nifty Jul 22000 Call', price: 185.30, change: 12.4 },
  { symbol: 'NFO:NIFTY26JUL22000PE', name: 'Nifty Jul 22000 Put', price: 92.40, change: -8.15 },
];

export default function IndianMarketsTerminal() {
  const [activeTab, setActiveTab] = useState<SubTab>('WATCHLIST');
  const [watchlist, setWatchlist] = useState(DEFAULT_WATCHLIST);
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
      if (activeTab === 'POSITIONS') {
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
        renderItem={({ item }) => (
          <TouchableOpacity 
            style={styles.cardRow} 
            onPress={() => handleOpenOrder(item.symbol)}
          >
            <View>
              <Text style={styles.symbolText}>{item.symbol}</Text>
              <Text style={styles.nameText}>{item.name}</Text>
            </View>
            <View style={styles.rightAligned}>
              <Text style={styles.priceVal}>₹{item.price.toFixed(2)}</Text>
              <Text style={[styles.changeText, { color: item.change >= 0 ? theme.colors.green : theme.colors.red }]}>
                {item.change >= 0 ? '+' : ''}{item.change.toFixed(2)}%
              </Text>
            </View>
          </TouchableOpacity>
        )}
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


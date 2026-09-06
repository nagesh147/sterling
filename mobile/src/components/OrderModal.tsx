import React, { useState } from 'react';
import { 
  Modal, View, Text, StyleSheet, TouchableOpacity, TextInput, 
  TouchableWithoutFeedback, Keyboard, ActivityIndicator, Alert 
} from 'react-native';
import { api } from '../services/api';
import { theme } from '../styles/theme';
import { Ionicons } from '@expo/vector-icons';

interface OrderModalProps {
  visible: boolean;
  onClose: () => void;
  symbol: string;
}

export default function OrderModal({ visible, onClose, symbol }: OrderModalProps) {
  const [side, setSide] = useState<'BUY' | 'SELL'>('BUY');
  const [orderType, setOrderType] = useState<'MARKET' | 'LIMIT'>('MARKET');
  const [quantity, setQuantity] = useState('10');
  const [price, setPrice] = useState('100.0');
  const [product, setProduct] = useState<'MIS' | 'CNC'>('MIS');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async () => {
    const qty = parseInt(quantity, 10);
    const limitPrice = parseFloat(price);

    if (isNaN(qty) || qty <= 0) {
      Alert.alert('Invalid Quantity', 'Please enter a valid positive integer.');
      return;
    }

    if (orderType === 'LIMIT' && (isNaN(limitPrice) || limitPrice <= 0)) {
      Alert.alert('Invalid Price', 'Please enter a valid positive price.');
      return;
    }

    setLoading(true);

    try {
      const payload = {
        tradingsymbol: symbol.split(':').pop() || symbol,
        exchange: symbol.includes(':') ? symbol.split(':')[0] : 'NSE',
        transaction_type: side,
        order_type: orderType,
        quantity: qty,
        price: orderType === 'LIMIT' ? limitPrice : 0,
        product,
        variety: 'regular'
      };
      await api.post('/api/v1/kite/orders', payload);
      Alert.alert('Success', `Kite ${side} order placed successfully.`);
      onClose();
    } catch (e: any) {
      Alert.alert('Order Failed', e.message || 'Unknown error occurred.');
    } finally {
      setLoading(false);
    }
  };

  const handleAdjustQty = (amt: number) => {
    const currentVal = parseInt(quantity, 10) || 0;
    const nextVal = Math.max(1, currentVal + amt);
    setQuantity(String(nextVal));
  };

  return (
    <Modal
      visible={visible}
      animationType="slide"
      transparent={true}
      onRequestClose={onClose}
    >
      <TouchableWithoutFeedback onPress={() => { Keyboard.dismiss(); onClose(); }}>
        <View style={styles.backdrop}>
          <TouchableWithoutFeedback>
            <View style={styles.sheet}>
              <View style={styles.header}>
                <View>
                  <Text style={styles.title}>Place Order</Text>
                  <Text style={styles.subtitle}>{symbol} • KITE</Text>
                </View>
                <TouchableOpacity onPress={onClose}>
                  <Ionicons name="close" size={24} color={theme.colors.textDim} />
                </TouchableOpacity>
              </View>

              {/* BUY / SELL Switcher */}
              <View style={styles.tabRow}>
                <TouchableOpacity 
                  style={[
                    styles.tabButton, 
                    side === 'BUY' ? { backgroundColor: theme.colors.green } : styles.tabInactive
                  ]}
                  onPress={() => setSide('BUY')}
                >
                  <Text style={styles.tabText}>BUY</Text>
                </TouchableOpacity>
                <TouchableOpacity 
                  style={[
                    styles.tabButton, 
                    side === 'SELL' ? { backgroundColor: theme.colors.red } : styles.tabInactive
                  ]}
                  onPress={() => setSide('SELL')}
                >
                  <Text style={styles.tabText}>SELL</Text>
                </TouchableOpacity>
              </View>

              {/* Order Type Selector */}
              <View style={styles.labelValueRow}>
                <Text style={styles.sectionLabel}>ORDER TYPE</Text>
                <View style={styles.segmentContainer}>
                  <TouchableOpacity 
                    style={[styles.segment, orderType === 'MARKET' ? styles.segmentActive : null]}
                    onPress={() => setOrderType('MARKET')}
                  >
                    <Text style={[styles.segmentText, orderType === 'MARKET' ? styles.segmentTextActive : null]}>MARKET</Text>
                  </TouchableOpacity>
                  <TouchableOpacity 
                    style={[styles.segment, orderType === 'LIMIT' ? styles.segmentActive : null]}
                    onPress={() => setOrderType('LIMIT')}
                  >
                    <Text style={[styles.segmentText, orderType === 'LIMIT' ? styles.segmentTextActive : null]}>LIMIT</Text>
                  </TouchableOpacity>
                </View>
              </View>

              {/* Product Selector */}
                <View style={styles.labelValueRow}>
                  <Text style={styles.sectionLabel}>PRODUCT TYPE</Text>
                  <View style={styles.segmentContainer}>
                    <TouchableOpacity 
                      style={[styles.segment, product === 'MIS' ? styles.segmentActive : null]}
                      onPress={() => setProduct('MIS')}
                    >
                      <Text style={[styles.segmentText, product === 'MIS' ? styles.segmentTextActive : null]}>INTRADAY (MIS)</Text>
                    </TouchableOpacity>
                    <TouchableOpacity 
                      style={[styles.segment, product === 'CNC' ? styles.segmentActive : null]}
                      onPress={() => setProduct('CNC')}
                    >
                      <Text style={[styles.segmentText, product === 'CNC' ? styles.segmentTextActive : null]}>DELIVERY (CNC)</Text>
                    </TouchableOpacity>
                  </View>
                </View>

              {/* Quantity Selector */}
              <View style={styles.inputContainer}>
                <Text style={styles.inputLabel}>QUANTITY</Text>
                <View style={styles.qtyInputRow}>
                  <TouchableOpacity style={styles.qtyAdjBtn} onPress={() => handleAdjustQty(-10)}>
                    <Text style={styles.qtyAdjText}>-10</Text>
                  </TouchableOpacity>
                  <TouchableOpacity style={styles.qtyAdjBtn} onPress={() => handleAdjustQty(-1)}>
                    <Text style={styles.qtyAdjText}>-1</Text>
                  </TouchableOpacity>
                  
                  <TextInput
                    style={styles.textInput}
                    value={quantity}
                    onChangeText={setQuantity}
                    keyboardType="number-pad"
                    placeholderTextColor={theme.colors.textMuted}
                  />

                  <TouchableOpacity style={styles.qtyAdjBtn} onPress={() => handleAdjustQty(1)}>
                    <Text style={styles.qtyAdjText}>+1</Text>
                  </TouchableOpacity>
                  <TouchableOpacity style={styles.qtyAdjBtn} onPress={() => handleAdjustQty(10)}>
                    <Text style={styles.qtyAdjText}>+10</Text>
                  </TouchableOpacity>
                </View>
              </View>

              {/* Price Selector (LIMIT ONLY) */}
              {orderType === 'LIMIT' && (
                <View style={styles.inputContainer}>
                  <Text style={styles.inputLabel}>PRICE</Text>
                  <TextInput
                    style={styles.textInput}
                    value={price}
                    onChangeText={setPrice}
                    keyboardType="numeric"
                    placeholderTextColor={theme.colors.textMuted}
                  />
                </View>
              )}

              {/* Submit Order Action Button */}
              <TouchableOpacity 
                style={[
                  styles.submitBtn, 
                  { backgroundColor: side === 'BUY' ? theme.colors.green : theme.colors.red }
                ]}
                onPress={handleSubmit}
                disabled={loading}
              >
                {loading ? (
                  <ActivityIndicator color="#fff" />
                ) : (
                  <Text style={styles.submitBtnText}>
                    PLACE {side} ORDER
                  </Text>
                )}
              </TouchableOpacity>
            </View>
          </TouchableWithoutFeedback>
        </View>
      </TouchableWithoutFeedback>
    </Modal>
  );
}

const styles = StyleSheet.create({
  backdrop: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.7)',
    justifyContent: 'flex-end',
  },
  sheet: {
    backgroundColor: theme.colors.bgCard,
    borderTopLeftRadius: theme.borderRadius.lg,
    borderTopRightRadius: theme.borderRadius.lg,
    padding: theme.spacing.lg,
    borderTopColor: theme.colors.border,
    borderTopWidth: 1,
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: theme.spacing.md,
  },
  title: {
    color: theme.colors.textBright,
    fontSize: 18,
    fontWeight: '800',
  },
  subtitle: {
    color: theme.colors.textMuted,
    fontSize: 11,
    fontWeight: '600',
    marginTop: 2,
  },
  tabRow: {
    flexDirection: 'row',
    borderRadius: theme.borderRadius.md,
    overflow: 'hidden',
    marginBottom: theme.spacing.md,
  },
  tabButton: {
    flex: 1,
    height: 40,
    alignItems: 'center',
    justifyContent: 'center',
  },
  tabInactive: {
    backgroundColor: theme.colors.bgHeader,
  },
  tabText: {
    color: '#ffffff',
    fontWeight: '800',
    fontSize: 14,
    letterSpacing: 0.5,
  },
  labelValueRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: theme.spacing.md,
  },
  sectionLabel: {
    color: theme.colors.textMuted,
    fontSize: 10,
    fontWeight: '700',
  },
  segmentContainer: {
    flexDirection: 'row',
    backgroundColor: theme.colors.bgHeader,
    borderRadius: theme.borderRadius.sm,
    padding: 2,
    borderWidth: 1,
    borderColor: theme.colors.border,
  },
  segment: {
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: theme.borderRadius.sm,
  },
  segmentActive: {
    backgroundColor: theme.colors.border,
  },
  segmentText: {
    color: theme.colors.textMuted,
    fontSize: 10,
    fontWeight: '700',
  },
  segmentTextActive: {
    color: theme.colors.textBright,
  },
  inputContainer: {
    marginBottom: theme.spacing.md,
  },
  inputLabel: {
    color: theme.colors.textMuted,
    fontSize: 10,
    fontWeight: '700',
    marginBottom: 6,
  },
  qtyInputRow: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  qtyAdjBtn: {
    backgroundColor: theme.colors.bgHeader,
    borderColor: theme.colors.border,
    borderWidth: 1,
    borderRadius: theme.borderRadius.sm,
    paddingHorizontal: 8,
    paddingVertical: 10,
    marginRight: 4,
  },
  qtyAdjText: {
    color: theme.colors.textBright,
    fontSize: 10,
    fontWeight: '700',
    fontFamily: theme.fonts.mono,
  },
  textInput: {
    flex: 1,
    backgroundColor: theme.colors.bgHeader,
    borderColor: theme.colors.border,
    borderWidth: 1,
    borderRadius: theme.borderRadius.sm,
    color: theme.colors.textBright,
    fontFamily: theme.fonts.mono,
    fontSize: 14,
    paddingHorizontal: theme.spacing.md,
    paddingVertical: 8,
    marginRight: 4,
    textAlign: 'center',
  },
  submitBtn: {
    height: 48,
    borderRadius: theme.borderRadius.md,
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: theme.spacing.md,
  },
  submitBtnText: {
    color: '#ffffff',
    fontSize: 14,
    fontWeight: '800',
    letterSpacing: 1,
  },
});

import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { theme } from '../styles/theme';

interface MetricCardProps {
  label: string;
  value: string | number;
  subValue?: string | number;
  type?: 'neutral' | 'green' | 'red' | 'amber';
}

export default function MetricCard({ label, value, subValue, type = 'neutral' }: MetricCardProps) {
  const getValueColor = () => {
    switch (type) {
      case 'green':
        return theme.colors.green;
      case 'red':
        return theme.colors.red;
      case 'amber':
        return theme.colors.amber;
      default:
        return theme.colors.textBright;
    }
  };

  return (
    <View style={styles.card}>
      <Text style={styles.label}>{label.toUpperCase()}</Text>
      <Text style={[styles.value, { color: getValueColor() }]}>{value}</Text>
      {subValue !== undefined && (
        <Text style={styles.subValue}>{subValue}</Text>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: theme.colors.bgCard,
    borderColor: theme.colors.border,
    borderWidth: 1,
    borderRadius: theme.borderRadius.md,
    padding: theme.spacing.md,
    flex: 1,
    marginHorizontal: 4,
    minWidth: 100,
  },
  label: {
    color: theme.colors.textMuted,
    fontSize: 9,
    fontWeight: '700',
    letterSpacing: 0.5,
    marginBottom: 4,
  },
  value: {
    fontSize: 16,
    fontWeight: '800',
    fontFamily: theme.fonts.mono,
  },
  subValue: {
    color: theme.colors.textDim,
    fontSize: 10,
    marginTop: 2,
    fontFamily: theme.fonts.mono,
  },
});

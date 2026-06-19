import React from 'react';
import { k, Icons } from '../../styles/kiteUI';

interface KiteActionButtonsProps {
  onBuy?: (e: React.MouseEvent) => void;
  onSell?: (e: React.MouseEvent) => void;
  onDepth?: (e: React.MouseEvent) => void;
  onChart?: (e: React.MouseEvent) => void;
  onDelete?: (e: React.MouseEvent) => void;
  onMore?: (e: React.MouseEvent) => void;
  onAdd?: (e: React.MouseEvent) => void;
  className?: string;
  variant?: 'short' | 'long';
  buyLabel?: string;
  sellLabel?: string;
}

export function KiteActionButtons({ onBuy, onSell, onDepth, onChart, onDelete, onMore, onAdd, className, variant = 'short', buyLabel, sellLabel }: KiteActionButtonsProps) {
  const btnAction: React.CSSProperties = {
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    width: 28, height: 28, borderRadius: 2, cursor: 'pointer',
    fontSize: 12, border: 'none'
  };

  const buySellStyle: React.CSSProperties = variant === 'long' 
    ? {
        display: 'flex', alignItems: 'center', justifyContent: 'center', 
        width: 125, height: 32, borderRadius: 3, padding: 0, 
        border: 'none', cursor: 'pointer', 
        fontSize: 12, letterSpacing: '0.5px', color: '#fff'
      }
    : { 
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        minWidth: 35, borderRadius: 3, padding: '6px 10px', cursor: 'pointer',
        fontSize: 12, border: 'none', color: '#fff'
      };

  const iconBtnStyle: React.CSSProperties = {
    ...btnAction, background: 'transparent', color: k.dim, padding: 4
  };

  return (
    <div className={className} onClick={(e) => e.stopPropagation()}>
      {onBuy && (
        <button style={{ ...buySellStyle, background: '#4184f3' }} title={buyLabel || "Buy"} onClick={onBuy}>
          {buyLabel || (variant === 'long' ? 'BUY' : 'B')}
        </button>
      )}
      {onSell && (
        <button style={{ ...buySellStyle, background: '#ff5722' }} title={sellLabel || "Sell"} onClick={onSell}>
          {sellLabel || (variant === 'long' ? 'SELL' : 'S')}
        </button>
      )}
      {onChart && (
        <button style={iconBtnStyle} title="Chart" onClick={onChart}>
          <Icons.Chart />
        </button>
      )}
      {onDepth && (
        <button style={iconBtnStyle} title="Market Depth" onClick={onDepth}>
          <Icons.Depth />
        </button>
      )}
      {onDelete && (
        <button style={iconBtnStyle} title="Delete" onClick={onDelete}>
          <Icons.Trash />
        </button>
      )}
      {onMore && (
        <button style={iconBtnStyle} title="More" onClick={onMore}>
          <Icons.More />
        </button>
      )}
      {onAdd && (
        <button style={{ ...btnAction, background: k.green, color: '#fff', fontSize: 16, fontWeight: 600 }} title="Add to watchlist" onClick={onAdd}>
          +
        </button>
      )}
    </div>
  );
}

import React, { useState, useEffect, useMemo, useRef } from 'react';
import { k, tint, Icons } from '../../styles/kiteUI';
import {
  usePlaceKiteOrder, useKiteOrderMargins, useKiteMargins,
  useKiteInstrumentSearch, useKiteQuote, useKiteOrderCharges,
} from '../../hooks/useKite';
import { useDebounced } from '../../hooks/useDebounced';
import { useMacKite } from '../../hooks/useMacKite';
import { useKiteBasketStore } from '../../store/useKiteBasketStore';
import { useKitePendingProtectionStore } from '../../store/useKitePendingProtectionStore';
import { useEngineActivity } from '../../hooks/useSterlingKiteEngine';
import type { OrderWindowOptions } from '../../store/useOrderWindowStore';
import type { KiteInstrument } from '../../types/kite';
import { InstrumentLabel } from './InstrumentLabel';
import { getOrderNudge } from './orderNudge';
import {
  Side, OrderType, Product, Validity,
  productsForExchange, defaultProduct, marginSegment, isDerivative,
  effectiveLot, lotsFromQty, snapToLot, stepQty, lotsToQty,
  needsPrice, needsTrigger, validateTicket, resolveVariety,
  buildOrderBody, buildMarginOrder, parseMargin, buildProtectionGtt, chargeLines,
} from './orderTicket';

interface Props {
  options: OrderWindowOptions;
  onClose: () => void;
}

type Tab = 'quick' | 'regular';
const TTL_OPTIONS = [1, 2, 3, 5, 10, 15, 30, 45, 60];

const inr = (n: number) => '₹' + (Number.isFinite(n) ? n : 0).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const num = (v: any) => Number(v ?? 0);
const fmtPx = (v: any) => (v != null && !isNaN(Number(v)) ? Number(v).toFixed(2) : '0.00');
const fmtExpiry = (e?: string) => { if (!e) return ''; const d = new Date(e); return isNaN(d.getTime()) ? e : d.toLocaleDateString('en-GB', { day: '2-digit', month: 'short' }).toUpperCase(); };
const HATCH = 'repeating-linear-gradient(-45deg,#f4f4f4,#f4f4f4 5px,#fafafa 5px,#fafafa 10px)';

// ── icons ────────────────────────────────────────────────────────────────────
const Box = () => (
  <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
    <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z" /><polyline points="3.27 6.96 12 12.01 20.73 6.96" /><line x1="12" y1="22.08" x2="12" y2="12" />
  </svg>
);
const XIcon = ({ s = 14 }: { s?: number }) => (
  <svg width={s} height={s} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" /></svg>
);
const Refresh = () => (
  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="23 4 23 10 17 10" /><polyline points="1 20 1 14 7 14" /><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15" /></svg>
);
const Pencil = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 20h9" /><path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4Z" /></svg>
);

export function OrderWindow({ options, onClose }: Props) {
  const { on, motion, AnimatePresence, sp, setTicketOpen } = useMacKite();
  const { initialSide, initialQty, product: productHint, tag, onPlaced } = options;

  // Dim + 2% scale-down of the background Kite canvas while the ticket is open.
  // No-op when Mac Kite is off (setTicketOpen guards on the flag internally).
  useEffect(() => {
    setTicketOpen(true);
    return () => setTicketOpen(false);
  }, [setTicketOpen]);

  const [instr, setInstr] = useState({
    symbol: options.symbol, exchange: options.exchange,
    lotSize: options.lotSize, lastPrice: options.lastPrice || 0,
  });
  const lot = effectiveLot(instr.lotSize);
  const carryProduct = defaultProduct(instr.exchange);

  const [tab, setTab] = useState<Tab>(options.initialSlPct != null || options.initialTgtPct != null ? 'regular' : 'quick');
  const [side, setSide] = useState<Side>(initialSide);
  const [product, setProduct] = useState<Product>(productHint || carryProduct);
  const [orderType, setOrderType] = useState<OrderType>(instr.lastPrice > 0 ? 'LIMIT' : 'MARKET');
  const [qty, setQty] = useState<number>(initialQty && initialQty > 0 ? snapToLot(initialQty, instr.lotSize) : lot);
  const [lotsMode, setLotsMode] = useState(false);
  const [price, setPrice] = useState<number>(instr.lastPrice);
  const [trigger, setTrigger] = useState<number>(0);
  const [validity, setValidity] = useState<Validity>('DAY');
  const [ttlMins, setTtlMins] = useState<number>(1);
  const [disclosedQty, setDisclosedQty] = useState<number>(0);
  const [marketProtection, setMarketProtection] = useState(true);
  const [showAdvanced, setShowAdvanced] = useState(false);
  // Protective GTT (shown for carry / Overnight positions, can be initialized from trade plan).
  const [slOn, setSlOn] = useState(options.initialSlPct != null && options.initialSlPct !== 0);
  const [slPct, setSlPct] = useState<number>(options.initialSlPct ?? 0);
  const [tgtOn, setTgtOn] = useState(options.initialTgtPct != null && options.initialTgtPct !== 0);
  const [tgtPct, setTgtPct] = useState<number>(options.initialTgtPct ?? 0);
  const [error, setError] = useState<string | null>(null);

  const [searchOpen, setSearchOpen] = useState(false);   // search lives in its own component so typing doesn't re-render the ticket
  const [depthOpen, setDepthOpen] = useState(false);
  const [nudgeOpen, setNudgeOpen] = useState(true);

  const placeOrder = usePlaceKiteOrder();
  const addPendingProtection = useKitePendingProtectionStore((s) => s.add);
  const marginCalc = useKiteOrderMargins();
  const chargesCalc = useKiteOrderCharges();
  const [charges, setCharges] = useState<Record<string, any> | null>(null);
  const { data: funds, refetch: refetchFunds } = useKiteMargins(true);
  const { data: activity } = useEngineActivity();
  const variety = resolveVariety(activity?.market_open);
  const amoConfirmNeeded = variety === 'amo';
  const [amoConfirmed, setAmoConfirmed] = useState(false);

  const fullSym = `${instr.exchange}:${instr.symbol}`;
  // Depth ladder needs to feel live; subscribe full mode so the 5-level depth streams
  // over the WS (quote-mode ticks omit depth). The 5s REST poll is a cold-start/fallback.
  const { data: depthQuotes } = useKiteQuote([fullSym], depthOpen, 5_000, 'full');
  const depthQ = (depthQuotes as any)?.[fullSym];
  const nudge = useMemo(() => getOrderNudge(instr.symbol, instr.exchange), [instr.symbol, instr.exchange]);

  const needLot = isDerivative(instr.exchange) && effectiveLot(instr.lotSize) <= 1;
  const lotLookup = useKiteInstrumentSearch(needLot ? instr.symbol : '');
  useEffect(() => {
    if (!needLot) return;
    const m = lotLookup.data?.instruments?.find((i) => i.tradingsymbol === instr.symbol);
    if (m?.lot_size && m.lot_size > 1) { setInstr((p) => ({ ...p, lotSize: m.lot_size })); setQty((q) => snapToLot(q, m.lot_size)); }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lotLookup.data, needLot, instr.symbol]);

  const accent = side === 'BUY' ? k.blue : k.orange;
  const cardW = tab === 'regular' ? 650 : 420;   // Regular = roomy 650×450 ticket
  const products = useMemo(() => productsForExchange(instr.exchange), [instr.exchange]);
  const lots = lotsFromQty(qty, instr.lotSize);
  const qtySub = lotsMode ? `${qty} qty.` : (lot > 1 ? `${lots} lot${lots !== 1 ? 's' : ''}` : `${qty} Qty`);
  const quickMarket = tab === 'quick' && orderType === 'MARKET';

  const args = useMemo(() => ({
    tradingsymbol: instr.symbol, exchange: instr.exchange, side, quantity: qty, product, orderType,
    price, trigger, validity, validityTtl: ttlMins, variety,
    disclosedQty: tab === 'regular' ? disclosedQty : 0, tag,
  }), [instr.symbol, instr.exchange, side, qty, product, orderType, price, trigger, validity, ttlMins, disclosedQty, tab, tag, variety]);

  const available = useMemo(() => {
    const seg = (funds as any)?.[marginSegment(instr.exchange)];
    return Number(seg?.available?.live_balance ?? seg?.available?.cash ?? seg?.net ?? NaN);
  }, [funds, instr.exchange]);

  const [margin, setMargin] = useState<{ total: number; charges: number } | null>(null);
  const reqId = useRef(0);
  const runMargin = () => {
    if (!(qty > 0)) { setMargin(null); return; }
    if (needsPrice(orderType) && !(price > 0)) return;
    if (needsTrigger(orderType) && !(trigger > 0)) return;
    const id = ++reqId.current;
    marginCalc.mutate([buildMarginOrder(args)], {
      onSuccess: (resp) => { if (id === reqId.current) setMargin(parseMargin(resp)); },
      onError: () => { if (id === reqId.current) setMargin(null); },
    });
    chargesCalc.mutate([buildMarginOrder(args)], {
      onSuccess: (resp) => { if (id === reqId.current) setCharges(Array.isArray(resp) ? resp[0]?.charges ?? null : resp?.charges ?? null); },
      onError: () => { if (id === reqId.current) setCharges(null); },
    });
  };
  useEffect(() => {
    const t = setTimeout(runMargin, 350);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [args]);

  // Spin only on an explicit click (not the 20s background poll), with a short
  // minimum so a fast/cached refetch still gives visible feedback.
  const [refreshing, setRefreshing] = useState(false);
  const doRefresh = () => {
    if (refreshing) return;
    setRefreshing(true);
    runMargin();
    const done = Promise.resolve(refetchFunds());
    const minSpin = new Promise((r) => setTimeout(r, 450));
    Promise.all([done, minSpin]).finally(() => setRefreshing(false));
  };

  // ── dragging (clamped to viewport) ───────────────────────────────────────────
  const clamp = (x: number, y: number) => ({
    x: Math.min(Math.max(x, -(cardW - 130)), window.innerWidth - 130),
    y: Math.min(Math.max(y, 8), window.innerHeight - 72),
  });
  const [pos, setPos] = useState(() => clamp(Math.round(window.innerWidth / 2 - 220), Math.max(16, Math.round(window.innerHeight / 2 - 300))));
  const onHeaderDown = (e: React.MouseEvent) => {
    const start = { mx: e.clientX, my: e.clientY, px: pos.x, py: pos.y };
    document.body.style.userSelect = 'none'; document.body.style.cursor = 'move';
    const move = (ev: MouseEvent) => setPos(clamp(start.px + (ev.clientX - start.mx), start.py + (ev.clientY - start.my)));
    const up = () => { document.body.style.userSelect = ''; document.body.style.cursor = ''; window.removeEventListener('mousemove', move); window.removeEventListener('mouseup', up); };
    window.addEventListener('mousemove', move); window.addEventListener('mouseup', up);
  };

  const switchTab = (tb: Tab) => { if (tb === 'quick' && (orderType === 'SL' || orderType === 'SL-M')) setOrderType(price > 0 ? 'LIMIT' : 'MARKET'); setTab(tb); };
  const setQtyFromLots = (v: number) => setQty(lotsToQty(v, instr.lotSize));
  const clearPrice = () => { setPrice(0); setOrderType('MARKET'); };
  const restoreLimit = () => { setOrderType('LIMIT'); setPrice(instr.lastPrice); };
  const pickType = (ot: OrderType) => {
    setOrderType(ot);
    if (needsPrice(ot) && instr.lastPrice > 0) setPrice(instr.lastPrice);
    if (needsTrigger(ot) && instr.lastPrice > 0) setTrigger(instr.lastPrice);
  };

  // Reset the whole ticket to a (new) instrument, preserving window position/tab.
  const loadInstrument = (p: { symbol: string; exchange: string; lotSize?: number; lastPrice?: number; side?: Side; product?: Product; qty?: number }) => {
    const lp = p.lastPrice || 0;
    setInstr({ symbol: p.symbol, exchange: p.exchange, lotSize: p.lotSize, lastPrice: lp });
    if (p.side) setSide(p.side);
    setProduct(p.product || defaultProduct(p.exchange));
    setQty(p.qty && p.qty > 0 ? snapToLot(p.qty, p.lotSize) : effectiveLot(p.lotSize));
    setPrice(lp);
    setOrderType(lp > 0 ? 'LIMIT' : 'MARKET');
    setTrigger(0); setValidity('DAY'); setDisclosedQty(0);
    setSlOn(false); setSlPct(0); setTgtOn(false); setTgtPct(0);
    setError(null); setNudgeOpen(true);
    setAmoConfirmed(false);
    // Note: we intentionally do NOT close the search here — picking a result
    // updates the ticket but keeps the list open. Only an outside click closes it.
  };

  const selectInstrument = (i: KiteInstrument) => loadInstrument({
    symbol: i.tradingsymbol, exchange: i.exchange || instr.exchange,
    lotSize: i.lot_size && i.lot_size > 0 ? i.lot_size : 1, lastPrice: i.last_price,
  });

  // If the store reopens the window for a different instrument/side while it's
  // still open (user clicks another row's Buy/Sell), swap the ticket in place.
  const optKey = `${options.symbol}|${options.exchange}|${options.initialSide}`;
  const didMount = useRef(false);
  useEffect(() => {
    if (!didMount.current) { didMount.current = true; return; }
    loadInstrument({
      symbol: options.symbol, exchange: options.exchange, lotSize: options.lotSize,
      lastPrice: options.lastPrice, side: options.initialSide, product: options.product, qty: options.initialQty,
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [optKey]);

  const submit = () => {
    setError(null);
    if (nudge?.blocked) { setError(nudge.message); return; }
    const err = validateTicket({ side, exchange: instr.exchange, quantity: qty, lotSize: instr.lotSize, orderType, price, trigger, ltp: instr.lastPrice });
    if (err) { setError(err); return; }
    placeOrder.mutate(buildOrderBody(args), {
      onSuccess: (res: any) => {
        // Carry positions can attach a protective GTT — queued until the
        // order actually fills (see PendingGttProtectionWatcher), not fired
        // on mere submission-acceptance.
        if (product !== 'MIS' && (slOn || tgtOn)) {
          const base = needsPrice(orderType) ? price : instr.lastPrice;
          const gtt = buildProtectionGtt({
            tradingsymbol: instr.symbol, exchange: instr.exchange, entrySide: side, quantity: qty,
            product, basePrice: base, slPct: slOn ? slPct : undefined, tgtPct: tgtOn ? tgtPct : undefined,
          });
          if (gtt && res?.order_id) addPendingProtection({ orderId: res.order_id, gtt });
        }
        onPlaced?.(res?.order_id || ''); onClose();
      },
      onError: (e: any) => setError(e?.message || 'Order failed'),
    });
  };

  const required = margin ? margin.total : null;
  const insufficient = required != null && Number.isFinite(available) && required > available;
  const placing = placeOrder.isPending;
  const buyDisabled = placing || !!nudge?.blocked || (amoConfirmNeeded && !amoConfirmed);

  const addToBasket = useKiteBasketStore((s) => s.add);
  const addCurrentToBasket = () => {
    setError(null);
    const err = validateTicket({ side, exchange: instr.exchange, quantity: qty, lotSize: instr.lotSize, orderType, price, trigger, ltp: instr.lastPrice });
    if (err) { setError(err); return; }
    addToBasket({
      symbol: instr.symbol, exchange: instr.exchange, side, qty,
      product, orderType, price, trigger,
    });
    onClose();
  };

  // ── reusable fields ──────────────────────────────────────────────────────────
  const qtyField = (
    <Field label={lotsMode ? 'Lots' : 'Qty.'}>
      <input className="ow-num" type="number" min={1} value={lotsMode ? lots : qty}
        onChange={(e) => (lotsMode ? setQtyFromLots(Number(e.target.value)) : setQty(Number(e.target.value)))}
        onBlur={(e) => (lotsMode ? setQtyFromLots(Number(e.target.value)) : setQty(snapToLot(Number(e.target.value), instr.lotSize)))} style={fieldInput} />
      <div style={{ display: 'flex', flexDirection: 'column', borderLeft: `1px solid ${k.border}`, alignSelf: 'stretch' }}>
        <button onMouseDown={(e) => e.stopPropagation()} onClick={() => setQty((q) => stepQty(q, instr.lotSize, 1))} style={spin}><Icons.ChevronUp /></button>
        <button onMouseDown={(e) => e.stopPropagation()} onClick={() => setQty((q) => stepQty(q, instr.lotSize, -1))} style={{ ...spin, borderTop: `1px solid ${k.border}` }}><Icons.ChevronDown /></button>
      </div>
      <button onClick={() => setLotsMode((v) => !v)} title="Switch quantity / lots" style={squareBtn}><Box /></button>
    </Field>
  );

  // Quick price: editable Limit field with a clear (×) → Market; in Market mode the
  // field is disabled with a pencil to return to Limit. Regular uses radios instead.
  const quickPriceField = (
    <Field label={quickMarket ? 'Market price' : 'Price'} disabled={quickMarket}>
      <input className="ow-num" type="number" step={0.05} disabled={quickMarket}
        value={quickMarket ? '' : (price > 0 ? price : '')} placeholder={quickMarket ? '' : 'Market'}
        onChange={(e) => { const v = Number(e.target.value); setPrice(v); setOrderType(v > 0 ? 'LIMIT' : 'MARKET'); }} style={fieldInput} />
      {quickMarket
        ? <button onClick={restoreLimit} title="Set a limit price" style={squareBtn}><Pencil /></button>
        : <button onClick={clearPrice} title="Clear → Market order" style={squareBtn}><XIcon /></button>}
    </Field>
  );

  const chargeTooltip = chargeLines(charges);
  const reqAvail = (
    <div style={{ display: 'flex', alignItems: 'center', gap: 16, fontSize: 12, color: k.dim }}>
      <span>Req. <b style={{ color: insufficient ? k.red : accent, fontWeight: 600 }}>{required != null ? inr(required) : (marginCalc.isPending ? '…' : '—')}</b>{margin && margin.charges > 0 ? (
        <span title={chargeTooltip} style={{ cursor: chargeTooltip ? 'help' : 'default' }}> + {margin.charges.toFixed(2)}</span>
      ) : null}</span>
      <span>Avail. <b style={{ color: accent, fontWeight: 600 }}>{Number.isFinite(available) ? inr(available) : '—'}</b></span>
      <button onClick={doRefresh} title="Refresh funds & margin" style={{ background: 'none', border: 'none', color: accent, cursor: 'pointer', display: 'flex', padding: 2 }}>
        <span className={refreshing ? 'ow-spin' : ''} style={{ display: 'flex' }}><Refresh /></span>
      </button>
    </div>
  );

  // Shared card body (header → footer). Markup is identical in both the static
  // and the Mac App Store morph paths — only the enclosing card element differs.
  const cardInner = (
    <>
            {/* Header */}
            <div onMouseDown={onHeaderDown} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '13px 16px', background: accent, color: '#fff', cursor: 'move' }}>
              <div onMouseDown={(e) => e.stopPropagation()} style={{ minWidth: 0, flex: '0 1 auto', maxWidth: '70%', cursor: 'default' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 15, fontWeight: 600, whiteSpace: 'nowrap', overflow: 'hidden' }}>
                  <span style={{ overflow: 'hidden', textOverflow: 'ellipsis' }}><InstrumentLabel symbol={fullSym} onColor={accent} /></span>
                  <button onClick={() => setSearchOpen((o) => !o)} title="Search instrument" style={{ background: searchOpen ? 'rgba(255,255,255,0.25)' : 'none', border: 'none', color: '#fff', cursor: 'pointer', display: 'flex', padding: 3, borderRadius: 3, flexShrink: 0 }}><Icons.Search /></button>
                </div>
                <div style={{ fontSize: 11.5, opacity: 0.92, marginTop: 3 }}>{instr.exchange}{instr.lastPrice > 0 ? `  ${inr(instr.lastPrice)}` : ''}</div>
              </div>
              <div onMouseDown={(e) => e.stopPropagation()} style={{ display: 'flex', alignItems: 'center', gap: 12, flexShrink: 0 }}>
                {nudge && (
                  <button onClick={() => setNudgeOpen((o) => !o)} title={nudge.message} style={{ position: 'relative', background: '#fff', border: 'none', borderRadius: '50%', width: 22, height: 22, color: accent, fontWeight: 700, fontSize: 12, cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                    N<span style={{ position: 'absolute', top: -5, right: -5, background: k.amber, color: '#fff', borderRadius: '50%', width: 13, height: 13, fontSize: 9, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>1</span>
                  </button>
                )}
                <div onClick={() => setSide(side === 'BUY' ? 'SELL' : 'BUY')} title={side === 'BUY' ? 'Switch to Sell' : 'Switch to Buy'} style={{ width: 44, height: 23, borderRadius: 12, background: 'rgba(255,255,255,0.35)', cursor: 'pointer', position: 'relative' }}>
                  <div style={{ position: 'absolute', top: 3, left: side === 'BUY' ? 3 : 24, width: 17, height: 17, borderRadius: '50%', background: '#fff', boxShadow: '0 1px 2px rgba(0,0,0,0.3)', transition: 'left .15s' }} />
                </div>
              </div>
            </div>

            {/* Tabs */}
            <div style={{ display: 'flex', alignItems: 'stretch', borderBottom: `1px solid ${k.border}` }}>
              {(['quick', 'regular'] as Tab[]).map((tb) => (
                <div key={tb} onClick={() => switchTab(tb)} style={{ padding: '11px 18px', fontSize: 13, cursor: 'pointer', textTransform: 'capitalize', color: tab === tb ? accent : k.text, fontWeight: tab === tb ? 600 : 400, borderBottom: tab === tb ? `2px solid ${accent}` : '2px solid transparent', marginBottom: -1 }}>{tb}</div>
              ))}
              <div title="Iceberg unavailable" style={{ padding: '11px 18px', fontSize: 13, color: '#cfcfcf', cursor: 'not-allowed' }}>Iceberg</div>
              <button onClick={() => setDepthOpen((d) => !d)} title={depthOpen ? 'Close market depth' : 'Market depth'} style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', padding: '0 14px', color: k.dim, background: depthOpen ? k.surfaceHover : 'transparent', border: 'none', borderLeft: `1px solid ${k.border}`, cursor: 'pointer' }}>{depthOpen ? <XIcon s={15} /> : <Pencil />}</button>
            </div>

            {/* Body (no scroll) */}
            {tab === 'quick' ? (
              <div style={{ padding: '18px 16px 16px', display: 'flex', flexDirection: 'column', gap: 14 }}>
                {qtyField}
                {quickPriceField}
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, color: k.text, cursor: 'pointer' }}>
                    <input type="checkbox" checked={product === 'MIS'} onChange={() => setProduct(product === 'MIS' ? carryProduct : 'MIS')} style={{ accentColor: accent, width: 15, height: 15 }} />Intraday
                  </label>
                  <span style={{ fontSize: 12, color: k.dim }}>{qtySub}</span>
                </div>

                {/* Protective GTT on Quick tab */}
                {product !== 'MIS' && (
                  <div style={{ display: 'flex', alignItems: 'center', gap: 12, borderTop: `1px solid ${k.border}`, paddingTop: 12, fontSize: 12 }}>
                    <GttIcon />
                    <PctToggle accent={accent} label="Stoploss" on={slOn} setOn={setSlOn} pct={slPct} setPct={setSlPct} defaultPct={-5} />
                    <PctToggle accent={accent} label="Target" on={tgtOn} setOn={setTgtOn} pct={tgtPct} setPct={setTgtPct} defaultPct={5} />
                    <span style={{ marginLeft: 'auto', color: k.dim, display: 'flex', cursor: 'help' }} title="Automatically create a GTT for the position on order completion"><Icons.Info /></span>
                  </div>
                )}
              </div>
            ) : (
              <div style={{ padding: '22px 24px', display: 'flex', flexDirection: 'column', gap: 22 }}>
                <div style={{ display: 'flex', alignItems: 'center' }}>
                  <div style={{ display: 'flex', gap: 28 }}>
                    {products.map((p) => (
                      <Radio key={p.value} accent={accent} checked={product === p.value} onChange={() => setProduct(p.value)}>{p.label} <span style={{ fontSize: 10, color: k.dim, marginLeft: 2 }}>{p.code}</span></Radio>
                    ))}
                  </div>
                  <button onClick={() => setShowAdvanced((v) => !v)} style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 3, fontSize: 12.5, color: accent, background: 'none', border: 'none', cursor: 'pointer' }}>Advanced {showAdvanced ? <Icons.ChevronUp /> : <Icons.ChevronDown />}</button>
                </div>

                <div style={{ display: 'flex', gap: 14 }}>
                  <div style={{ flex: 1, minWidth: 0 }}>{qtyField}</div>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <Field label={orderType === 'MARKET' ? 'Market price' : 'Price'} disabled={!needsPrice(orderType)}>
                      <input className="ow-num" type="number" step={0.05} disabled={!needsPrice(orderType)} value={!needsPrice(orderType) ? '' : (price > 0 ? price : '')} placeholder="0.00" onChange={(e) => setPrice(Number(e.target.value))} style={fieldInput} />
                    </Field>
                  </div>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <Field label="Trigger price" disabled={!needsTrigger(orderType)}>
                      <input className="ow-num" type="number" step={0.05} disabled={!needsTrigger(orderType)} value={!needsTrigger(orderType) ? '' : (trigger > 0 ? trigger : '')} placeholder="0" onChange={(e) => setTrigger(Number(e.target.value))} style={fieldInput} />
                    </Field>
                  </div>
                </div>

                <div style={{ display: 'flex', gap: 14, alignItems: 'center', marginTop: -8 }}>
                  <div style={{ flex: 1, minWidth: 0, fontSize: 11, color: k.dim }}>{qtySub}</div>
                  <div style={{ flex: 1, minWidth: 0, display: 'flex', gap: 18 }}>
                    <Radio accent={accent} checked={orderType === 'MARKET'} onChange={() => pickType('MARKET')}>Market</Radio>
                    <Radio accent={accent} checked={orderType === 'LIMIT'} onChange={() => pickType('LIMIT')}>Limit</Radio>
                  </div>
                  <div style={{ flex: 1, minWidth: 0, display: 'flex', gap: 18, justifyContent: 'flex-end' }}>
                    <Radio accent={accent} checked={orderType === 'SL'} onChange={() => pickType('SL')}>SL</Radio>
                    <Radio accent={accent} checked={orderType === 'SL-M'} onChange={() => pickType('SL-M')}>SL-M</Radio>
                  </div>
                </div>

                {showAdvanced && (
                  <div style={{ display: 'flex', gap: 14, alignItems: 'flex-start', borderTop: `1px solid ${k.border}`, paddingTop: 16 }}>
                    <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', gap: 11 }}>
                      <span style={{ fontSize: 11, color: k.dim }}>Validity</span>
                      <Radio accent={accent} checked={validity === 'DAY'} onChange={() => setValidity('DAY')}>Day</Radio>
                      <Radio accent={accent} checked={validity === 'IOC'} onChange={() => setValidity('IOC')}>Immediate <span style={{ fontSize: 10, color: k.dim }}>IOC</span></Radio>
                      <Radio accent={accent} checked={validity === 'TTL'} onChange={() => setValidity('TTL')}>Minutes</Radio>
                      {orderType === 'MARKET' && (
                        <label style={{ display: 'flex', alignItems: 'center', gap: 7, fontSize: 12.5, color: k.text, cursor: 'pointer', marginTop: 2 }}>
                          <input type="checkbox" checked={marketProtection} onChange={(e) => setMarketProtection(e.target.checked)} style={{ accentColor: accent, width: 14, height: 14 }} />Market protection
                        </label>
                      )}
                    </div>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <Field label="" disabled={validity !== 'TTL'}>
                        <select disabled={validity !== 'TTL'} value={ttlMins} onChange={(e) => setTtlMins(Number(e.target.value))} style={{ ...fieldInput, fontSize: 15, cursor: validity === 'TTL' ? 'pointer' : 'default' }}>
                          {TTL_OPTIONS.map((m) => <option key={m} value={m}>{m} minute{m !== 1 ? 's' : ''}</option>)}
                        </select>
                      </Field>
                    </div>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <Field label="Disclosed qty.">
                        <input className="ow-num" type="number" min={0} step={lot} value={disclosedQty || ''} placeholder="0" onChange={(e) => setDisclosedQty(Number(e.target.value))} style={fieldInput} />
                      </Field>
                    </div>
                  </div>
                )}

                {/* Protective GTT — carry positions only (Overnight/Delivery), never Intraday */}
                {product !== 'MIS' && (
                  <div style={{ display: 'flex', alignItems: 'center', gap: 14, borderTop: `1px solid ${k.border}`, paddingTop: 14 }}>
                    <GttIcon />
                    <PctToggle accent={accent} label="Stoploss" on={slOn} setOn={setSlOn} pct={slPct} setPct={setSlPct} defaultPct={-5} />
                    <PctToggle accent={accent} label="Target" on={tgtOn} setOn={setTgtOn} pct={tgtPct} setPct={setTgtPct} defaultPct={5} />
                    <span style={{ marginLeft: 'auto', color: k.dim, display: 'flex', cursor: 'help' }} title="Automatically create a GTT for the position on order completion"><Icons.Info /></span>
                  </div>
                )}
              </div>
            )}

            {error && <div style={{ padding: '8px 16px', background: tint(k.red, 10), color: k.red, fontSize: 12 }}>{error}</div>}

            {amoConfirmNeeded && (
              <div style={{ padding: '8px 16px', background: tint(k.amber, 12), color: '#8a6100', fontSize: 12 }}>
                <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer' }}>
                  <input type="checkbox" checked={amoConfirmed} onChange={(e) => setAmoConfirmed(e.target.checked)} style={{ accentColor: k.amber, width: 14, height: 14, flexShrink: 0 }} />
                  Market is closed — this will be placed as an After Market Order (AMO) for the next session.
                </label>
              </div>
            )}

            {/* Footer */}
            {tab === 'quick' ? (
              <div style={{ borderTop: `1px solid ${k.border}`, background: k.surface, padding: '12px 16px', display: 'flex', flexDirection: 'column', gap: 12 }}>
                {reqAvail}
                <button onClick={submit} disabled={buyDisabled} style={{ ...primaryBtn, background: accent, opacity: buyDisabled ? 0.55 : 1, cursor: buyDisabled ? 'not-allowed' : 'pointer' }}>{placing ? 'Placing…' : side === 'BUY' ? 'Buy' : 'Sell'}</button>
                <button onClick={onClose} style={cancelBtnWide}>Cancel</button>
              </div>
            ) : (
              <div style={{ display: 'flex', alignItems: 'center', padding: '12px 16px', borderTop: `1px solid ${k.border}`, background: k.surface }}>
                {reqAvail}
                <div style={{ marginLeft: 'auto', paddingLeft: 28, display: 'flex', gap: 10 }}>
                  <button onClick={addCurrentToBasket} title="Add to basket instead of placing now" style={{ ...cancelBtnWide, width: 'auto', padding: '9px 16px', fontSize: 12.5 }}>+ Basket</button>
                  <button onClick={submit} disabled={buyDisabled} style={{ ...primaryBtn, width: 'auto', padding: '9px 28px', fontSize: 13.5, background: accent, opacity: buyDisabled ? 0.55 : 1, cursor: buyDisabled ? 'not-allowed' : 'pointer' }}>{placing ? '…' : side === 'BUY' ? 'Buy' : 'Sell'}</button>
                  <button onClick={onClose} style={{ ...cancelBtnWide, width: 'auto', padding: '9px 22px' }}>Cancel</button>
                </div>
              </div>
            )}
    </>
  );

  const styleTag = (
    <style>{`
        .ow-num::-webkit-outer-spin-button,.ow-num::-webkit-inner-spin-button{-webkit-appearance:none;margin:0;}
        .ow-num{-moz-appearance:textfield;}
        .ow-row:hover{background:${k.surfaceHover};}
        @keyframes ow-spin{to{transform:rotate(360deg);}} .ow-spin{animation:ow-spin .6s linear infinite;}
      `}</style>
  );

  // Card chrome shared by both paths (background, radius, shadow, layout).
  const cardStyle: React.CSSProperties = { width: '100%', background: k.bg, borderRadius: 4, boxShadow: '0 6px 34px rgba(0,0,0,0.22)', display: 'flex', flexDirection: 'column', overflow: 'hidden' };

  const searchOverlay = searchOpen && (
    <InstrumentSearchOverlay symbol={instr.symbol} accent={accent} onPick={selectInstrument} onClose={() => setSearchOpen(false)} />
  );

  // ── Off-path: byte-identical to the original static popover. ─────────────────
  if (!on) {
    return (
      <>
        {styleTag}

        <div style={{ position: 'fixed', left: pos.x, top: pos.y, zIndex: 1000, display: 'flex', alignItems: 'flex-start', fontFamily: k.fontFamily }}>
          <div style={{ position: 'relative', width: cardW, transition: 'width .12s' }}>
            {nudge && nudgeOpen && <NudgePopup message={nudge.message} onClose={() => setNudgeOpen(false)} />}

            <div style={cardStyle}>
              {cardInner}
            </div>
          </div>

          {depthOpen && <MarketDepth q={depthQ} onClose={() => setDepthOpen(false)} />}
        </div>

        {/* Centered search overlay — its own component, so typing never re-renders the ticket */}
        {searchOverlay}
      </>
    );
  }

  // ── Mac path: App Store "card expansion" morph from the anchor (top-left). ────
  return (
    <>
      {styleTag}

      <div style={{ position: 'fixed', left: pos.x, top: pos.y, zIndex: 1000, display: 'flex', alignItems: 'flex-start', fontFamily: k.fontFamily }}>
        <div style={{ position: 'relative', width: cardW, transition: 'width .12s' }}>
          {nudge && nudgeOpen && <NudgePopup message={nudge.message} onClose={() => setNudgeOpen(false)} />}

          <AnimatePresence>
            <motion.div
              key="ow-card"
              className="mac-gpu"
              style={{ ...cardStyle, transformOrigin: 'top left' }}
              initial={{ opacity: 0, scale: 0.9, y: 6 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.9, y: 6 }}
              transition={sp('standard')}
            >
              {cardInner}
            </motion.div>
          </AnimatePresence>
        </div>

        {depthOpen && <MarketDepth q={depthQ} onClose={() => setDepthOpen(false)} />}
      </div>

      {/* Centered search overlay — its own component, so typing never re-renders the ticket */}
      {searchOverlay}
    </>
  );
}

// ── nudge popup ──────────────────────────────────────────────────────────────
function NudgePopup({ message, onClose }: { message: string; onClose: () => void }) {
  return (
    <div style={{ position: 'absolute', top: -84, right: 6, width: 280, background: k.bg, borderRadius: 5, boxShadow: '0 4px 20px rgba(0,0,0,0.18)', border: `1px solid ${k.border}`, padding: '12px 14px', zIndex: 5 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
        <span style={{ background: k.blue, color: '#fff', borderRadius: '50%', width: 18, height: 18, fontSize: 11, fontWeight: 700, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>N</span>
        <span style={{ fontSize: 13, fontWeight: 600, color: k.text }}>Nudge</span>
        <button onClick={onClose} style={{ marginLeft: 'auto', background: 'none', border: 'none', color: k.dim, cursor: 'pointer', display: 'flex' }}><XIcon /></button>
      </div>
      <div style={{ fontSize: 12.5, color: k.text, marginTop: 7, lineHeight: 1.4 }}>{message}</div>
      <div style={{ position: 'absolute', bottom: -7, right: 18, width: 12, height: 12, background: k.bg, borderRight: `1px solid ${k.border}`, borderBottom: `1px solid ${k.border}`, transform: 'rotate(45deg)' }} />
    </div>
  );
}

// ── outlined field ───────────────────────────────────────────────────────────
function Field({ label, disabled, children }: { label: string; disabled?: boolean; children: React.ReactNode }) {
  return (
    <div style={{ position: 'relative', border: `1px solid ${k.border}`, borderRadius: 4, height: 52, display: 'flex', alignItems: 'center', padding: '0 0 0 12px', background: disabled ? HATCH : '#fff' }}>
      {label && <span style={{ position: 'absolute', top: -8, left: 9, background: '#fff', padding: '0 5px', fontSize: 11, color: disabled ? '#bdbdbd' : k.dim }}>{label}</span>}
      {children}
    </div>
  );
}
function Radio({ accent, checked, onChange, children }: { accent: string; checked: boolean; onChange: () => void; children: React.ReactNode }) {
  return (
    <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13, cursor: 'pointer', color: checked ? k.text : '#666', fontWeight: checked ? 500 : 400, whiteSpace: 'nowrap' }}>
      <input type="radio" checked={checked} onChange={onChange} style={{ accentColor: accent, margin: 0 }} />{children}
    </label>
  );
}

const GttIcon = () => (
  <svg width="30" height="14" viewBox="0 0 60 24" fill="none">
    <rect x="1" y="5" width="44" height="14" rx="3" fill={tint(k.blue, 14)} stroke={k.blue} strokeWidth="1.2" />
    <text x="23" y="15.5" textAnchor="middle" fontSize="9" fontWeight="700" fill={k.blue} fontFamily="inherit">GTT</text>
    <path d="M47 12h11M54 8l4 4-4 4" stroke={k.blue} strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);

// Stoploss/Target %: hatched + empty when off; on check it seeds a sensible default.
function PctToggle({ accent, label, on, setOn, pct, setPct, defaultPct }: { accent: string; label: string; on: boolean; setOn: (v: boolean) => void; pct: number; setPct: (v: number) => void; defaultPct: number }) {
  const toggle = (checked: boolean) => { setOn(checked); if (checked && !pct) setPct(defaultPct); };
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
      <label style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: 12.5, color: k.text, cursor: 'pointer' }}>
        <input type="checkbox" checked={on} onChange={(e) => toggle(e.target.checked)} style={{ accentColor: accent, width: 14, height: 14 }} />{label}
      </label>
      <input className="ow-num" type="number" step={0.5} value={on ? (pct || '') : ''} disabled={!on} onChange={(e) => setPct(Number(e.target.value))}
        style={{ width: 50, padding: '4px 6px', border: `1px solid ${k.border}`, borderRadius: 3, fontSize: 12, textAlign: 'right', outline: 'none', background: on ? '#fff' : HATCH, color: on ? k.text : '#bbb' }} />
      <span style={{ fontSize: 12, color: k.dim }}>%</span>
    </div>
  );
}

// ── market depth ─────────────────────────────────────────────────────────────
function MarketDepth({ q, onClose }: { q: any; onClose: () => void }) {
  const buy = q?.depth?.buy || []; const sell = q?.depth?.sell || [];
  const cell: React.CSSProperties = { flex: 1, textAlign: 'right', fontVariantNumeric: 'tabular-nums', padding: '5px 10px' };
  return (
    <div style={{ width: 430, marginLeft: 8, background: k.bg, borderRadius: 4, boxShadow: '0 6px 34px rgba(0,0,0,0.18)', overflow: 'hidden', fontFamily: k.fontFamily }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '13px 14px', borderBottom: `1px solid ${k.border}` }}>
        <span style={{ fontSize: 14, fontWeight: 600, color: k.text }}>Market depth</span>
        <button onClick={onClose} style={{ background: 'none', border: 'none', color: k.dim, cursor: 'pointer', display: 'flex' }}><XIcon /></button>
      </div>
      <div style={{ display: 'flex', fontSize: 11, color: k.dim, borderBottom: `1px solid ${k.border}`, padding: '4px 0' }}>
        {['Bid', 'Orders', 'Qty.', 'Offer', 'Orders', 'Qty.'].map((h, i) => <span key={i} style={cell}>{h}</span>)}
      </div>
      {Array.from({ length: 5 }).map((_, i) => {
        const b = buy[i] || {}; const s = sell[i] || {};
        return (
          <div key={i} style={{ display: 'flex', fontSize: 12, borderBottom: `1px solid ${k.surface}` }}>
            <span style={{ ...cell, color: k.blue, fontWeight: 500 }}>{fmtPx(b.price)}</span>
            <span style={{ ...cell, color: k.dim }}>{num(b.orders)}</span>
            <span style={{ ...cell, color: k.text }}>{num(b.quantity)}</span>
            <span style={{ ...cell, color: k.orange, fontWeight: 500 }}>{fmtPx(s.price)}</span>
            <span style={{ ...cell, color: k.dim }}>{num(s.orders)}</span>
            <span style={{ ...cell, color: k.text }}>{num(s.quantity)}</span>
          </div>
        );
      })}
      <div style={{ display: 'flex', fontSize: 12, fontWeight: 600, padding: '2px 0' }}>
        <span style={{ ...cell, textAlign: 'left', color: k.blue }}>Total</span>
        <span style={{ ...cell, color: k.blue }}>{num(q?.buy_quantity).toLocaleString('en-IN')}</span>
        <span style={{ flex: 1 }} />
        <span style={{ ...cell, textAlign: 'left', color: k.orange }}>Total</span>
        <span style={{ ...cell, color: k.orange }}>{num(q?.sell_quantity).toLocaleString('en-IN')}</span>
      </div>
    </div>
  );
}

// ── instrument search ────────────────────────────────────────────────────────
// Self-contained overlay: owns the query state + debounce + queries, so keystrokes
// only re-render this subtree, never the order ticket behind it.
function InstrumentSearchOverlay({ symbol, accent, onPick, onClose }: {
  symbol: string; accent: string; onPick: (i: KiteInstrument) => void; onClose: () => void;
}) {
  const [query, setQuery] = useState('');
  const dq = useDebounced(query.trim(), 220);                 // fetch only after typing pauses
  const underlying = (symbol.match(/^[A-Z&-]+/) || [''])[0];  // empty box → list the underlying
  const typed = useKiteInstrumentSearch(dq);
  const seed = useKiteInstrumentSearch(dq.length < 2 ? underlying : '');
  const active = dq.length >= 2 ? typed : seed;
  const loading = active.isFetching || query.trim() !== dq;
  return (
    <>
      <div onClick={onClose} style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.06)', zIndex: 1100 }} />
      <div style={{ position: 'fixed', top: 84, left: '50%', transform: 'translateX(-50%)', width: 560, maxWidth: '92vw', background: k.bg, borderRadius: 4, boxShadow: '0 10px 44px rgba(0,0,0,0.28)', zIndex: 1101, overflow: 'hidden', fontFamily: k.fontFamily }}>
        <SearchBox query={query} onQuery={setQuery} accent={accent} results={active.data?.instruments} loading={loading} error={active.error as Error | null} onPick={onPick} />
      </div>
    </>
  );
}

function SearchBox({ query, onQuery, accent, results, loading, error, onPick }: {
  query: string; onQuery: (q: string) => void; accent: string;
  results?: KiteInstrument[]; loading: boolean; error: Error | null; onPick: (i: KiteInstrument) => void;
}) {
  // Rows depend only on the data, not the keystroke — memoize so typing is cheap.
  const rows = React.useMemo(() => (results || []).map((i) => (
    <div key={i.instrument_token} className="ow-row" onClick={() => onPick(i)} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 10, padding: '10px 16px', cursor: 'pointer', borderBottom: `1px solid ${k.surface}` }}>
      <span style={{ color: k.text, fontSize: 13, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}><InstrumentLabel symbol={i.tradingsymbol} fallback={i.name} /></span>
      <span style={{ display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0 }}>
        {i.expiry && <span style={{ fontSize: 9.5, color: k.dim }}>{fmtExpiry(i.expiry)}</span>}
        <span style={{ fontSize: 9.5, color: accent, background: tint(accent, 10), padding: '2px 6px', borderRadius: 2, fontWeight: 600 }}>{i.exchange || (i.instrument_type || '').toUpperCase()}</span>
      </span>
    </div>
  )), [results, accent, onPick]);
  return (
    <div style={{ display: 'flex', flexDirection: 'column' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '12px 16px', borderBottom: `1px solid ${k.border}` }}>
        <span style={{ color: k.dim, display: 'flex' }}><Icons.Search /></span>
        <input value={query} onChange={(e) => onQuery(e.target.value)} autoFocus placeholder="Search eg: NIFTY, RELIANCE, INFY" style={{ flex: 1, border: 'none', outline: 'none', fontSize: 14, color: k.text, background: 'transparent' }} />
      </div>
      <div style={{ maxHeight: 380, overflowY: 'auto' }}>
        {loading && (!results || results.length === 0) && <div style={{ padding: 16, color: k.dim, fontSize: 13 }}>Searching…</div>}
        {error && <div style={{ padding: 16, color: k.red, fontSize: 13 }}>✗ {error.message}</div>}
        {rows}
        {!loading && results && results.length === 0 && <div style={{ padding: 16, color: k.dim, fontSize: 13 }}>{query.trim() ? 'No matches found.' : 'Start typing to search…'}</div>}
      </div>
    </div>
  );
}

// ── shared styles ────────────────────────────────────────────────────────────
const fieldInput: React.CSSProperties = { border: 'none', outline: 'none', background: 'transparent', flex: 1, minWidth: 0, fontSize: 19, color: k.text, fontVariantNumeric: 'tabular-nums', padding: 0, height: '100%' };
const spin: React.CSSProperties = { display: 'flex', alignItems: 'center', justifyContent: 'center', width: 22, flex: 1, background: 'transparent', border: 'none', color: k.dim, cursor: 'pointer', padding: 0 };
const squareBtn: React.CSSProperties = { display: 'flex', alignItems: 'center', justifyContent: 'center', width: 40, alignSelf: 'stretch', background: k.surface, border: 'none', borderLeft: `1px solid ${k.border}`, color: k.dim, cursor: 'pointer', padding: 0 };
const primaryBtn: React.CSSProperties = { width: '100%', color: '#fff', border: 'none', borderRadius: 3, padding: '11px', fontSize: 15, fontWeight: 600, cursor: 'pointer' };
const cancelBtnWide: React.CSSProperties = { width: '100%', background: '#fff', color: k.text, border: `1px solid ${k.border}`, borderRadius: 3, padding: '10px', fontSize: 14, cursor: 'pointer' };

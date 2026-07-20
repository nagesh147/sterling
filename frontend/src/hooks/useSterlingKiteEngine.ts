import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../utils/api';
import { notifyOrder } from '../store/useKiteNotifications';
import type {
  ActivityResponse, BacktestRequest, BacktestResponse, EngineConfigModel,
  EngineDetailResponse, EngineOrderRequest, EngineOrderResponse, LiquidityGroup,
  OpenPositionsResponse, ScanReportResponse, SetupChart, SignalsResponse,
} from '../types/kiteEngine';

const
import React from 'react';
import { createPortal } from 'react-dom';
import { k } from '../../styles/kiteUI';
import { useKiteSettings, type LoaderStyle } from '../../store/useKiteSettings';
import { useAuthFeedback } from '../../store/useAuthFeedback';

const CSS = `
@keyframes kl-fade { 0% { opacity: 1; } 100% { opacity: .14; } }
@keyframes kl-spin { to { transform: rotate(360deg); } }
@key
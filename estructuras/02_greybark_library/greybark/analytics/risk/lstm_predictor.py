"""
Greybark Research - LSTM Price Prediction Module
Based on AlphaVantage Academy tutorial.
DISCLAIMER: NOT investment advice. Risk analysis only.
"""

import os
import numpy as np
import pandas as pd
from typing import Dict, List, Tuple
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

try:
    import torch
    import torch.nn as nn
    from torch.utils.data import Dataset, DataLoader
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

try:
    from alpha_vantage.timeseries import TimeSeries
    ALPHAVANTAGE_AVAILABLE = True
except ImportError:
    ALPHAVANTAGE_AVAILABLE = False

import yfinance as yf

ALPHAVANTAGE_API_KEY = os.getenv('ALPHAVANTAGE_API_KEY', '')

DEFAULT_CONFIG = {
    'input_sequence_length': 20,
    'hidden_size': 32,
    'num_layers': 2,
    'dropout': 0.2,
    'learning_rate': 0.01,
    'epochs': 100,
    'batch_size': 16,
    'train_split': 0.8,
}


class Normalizer:
    """Normalize data for LSTM."""
    
    def __init__(self):
        self.mu = None
        self.sd = None
    
    def fit_transform(self, data: np.ndarray) -> np.ndarray:
        self.mu = np.mean(data)
        self.sd = np.std(data) or 1
        return (data - self.mu) / self.sd
    
    def inverse_transform(self, data: np.ndarray) -> np.ndarray:
        return data * self.sd + self.mu


if TORCH_AVAILABLE:
    
    class TimeSeriesDataset(Dataset):
        def __init__(self, x, y):
            self.x = torch.tensor(x, dtype=torch.float32)
            self.y = torch.tensor(y, dtype=torch.float32)
        
        def __len__(self): return len(self.x)
        def __getitem__(self, idx): return self.x[idx], self.y[idx]
    
    
    class LSTMModel(nn.Module):
        def __init__(self, input_size=1, hidden_size=32, num_layers=2, dropout=0.2):
            super().__init__()
            self.hidden_size = hidden_size
            self.num_layers = num_layers
            
            self.linear_1 = nn.Linear(input_size, hidden_size)
            self.relu = nn.ReLU()
            self.lstm = nn.LSTM(hidden_size, hidden_size, num_layers, 
                               batch_first=True, dropout=dropout if num_layers > 1 else 0)
            self.dropout = nn.Dropout(dropout)
            self.linear_2 = nn.Linear(hidden_size, 1)
        
        def forward(self, x):
            batch_size = x.shape[0]
            x = self.relu(self.linear_1(x))
            h0 = torch.zeros(self.num_layers, batch_size, self.hidden_size)
            c0 = torch.zeros(self.num_layers, batch_size, self.hidden_size)
            out, _ = self.lstm(x, (h0, c0))
            out = self.dropout(out[:, -1, :])
            return self.linear_2(out)


class PricePredictor:
    """LSTM price predictor."""
    
    def __init__(self, config: Dict = None):
        if not TORCH_AVAILABLE:
            raise ImportError("PyTorch required. pip install torch")
        self.config = config or DEFAULT_CONFIG
        self.model = None
        self.normalizer = None
        self.trained = False
        self.validation_mse = None
        self.symbol = None
    
    def fetch_data(self, symbol: str, years: int = 5) -> np.ndarray:
        """Fetch price data."""
        if ALPHAVANTAGE_AVAILABLE:
            try:
                ts = TimeSeries(key=ALPHAVANTAGE_API_KEY, output_format='pandas')
                data, _ = ts.get_daily_adjusted(symbol=symbol, outputsize='full')
                prices = data['5. adjusted close'].values[::-1]
                return prices[-252*years:]
            except: pass
        
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period=f"{years}y")
        return hist['Close'].values
    
    def train(self, symbol: str, verbose: bool = True) -> Dict:
        """Train LSTM model."""
        self.symbol = symbol
        prices = self.fetch_data(symbol)
        
        # Normalize
        self.normalizer = Normalizer()
        normalized = self.normalizer.fit_transform(prices)
        
        # Create sequences
        seq_len = self.config['input_sequence_length']
        X, y = [], []
        for i in range(len(normalized) - seq_len):
            X.append(normalized[i:i + seq_len])
            y.append(normalized[i + seq_len])
        X, y = np.array(X), np.array(y)
        
        # Split
        split = int(len(X) * self.config['train_split'])
        X_train, X_test = X[:split].reshape(-1, seq_len, 1), X[split:].reshape(-1, seq_len, 1)
        y_train, y_test = y[:split], y[split:]
        
        # DataLoaders
        train_loader = DataLoader(TimeSeriesDataset(X_train, y_train), 
                                  batch_size=self.config['batch_size'], shuffle=True)
        test_loader = DataLoader(TimeSeriesDataset(X_test, y_test),
                                 batch_size=self.config['batch_size'])
        
        # Model
        self.model = LSTMModel(1, self.config['hidden_size'], 
                               self.config['num_layers'], self.config['dropout'])
        criterion = nn.MSELoss()
        optimizer = torch.optim.Adam(self.model.parameters(), lr=self.config['learning_rate'])
        
        # Train
        for epoch in range(self.config['epochs']):
            self.model.train()
            for X_batch, y_batch in train_loader:
                optimizer.zero_grad()
                loss = criterion(self.model(X_batch).squeeze(), y_batch)
                loss.backward()
                optimizer.step()
            
            if verbose and (epoch + 1) % 25 == 0:
                self.model.eval()
                test_loss = sum(criterion(self.model(xb).squeeze(), yb).item() 
                               for xb, yb in test_loader) / len(test_loader)
                print(f"Epoch {epoch+1}/{self.config['epochs']} - Test Loss: {test_loss:.6f}")
        
        # Final validation
        self.model.eval()
        self.validation_mse = sum(criterion(self.model(xb).squeeze(), yb).item() 
                                  for xb, yb in test_loader) / len(test_loader)
        self.trained = True
        
        return {'symbol': symbol, 'validation_mse': self.validation_mse}
    
    def predict_next(self) -> Dict:
        """Predict next day price."""
        if not self.trained:
            raise ValueError("Model not trained")
        
        prices = self.fetch_data(self.symbol, years=1)
        recent = prices[-self.config['input_sequence_length']:]
        normalized = (recent - self.normalizer.mu) / self.normalizer.sd
        
        X = torch.tensor(normalized.reshape(1, -1, 1), dtype=torch.float32)
        self.model.eval()
        with torch.no_grad():
            pred_norm = self.model(X).item()
        
        pred_price = self.normalizer.inverse_transform(np.array([pred_norm]))[0]
        current = prices[-1]
        change = (pred_price - current) / current * 100
        
        return {
            'symbol': self.symbol,
            'current_price': current,
            'predicted_price': pred_price,
            'predicted_change_pct': change,
            'direction': 'UP' if change > 0 else 'DOWN',
            'validation_mse': self.validation_mse,
            'timestamp': datetime.now().isoformat(),
        }


class BatchPredictor:
    """Predict multiple assets."""
    
    def __init__(self, symbols: List[str] = None):
        self.symbols = symbols or ['SPY', 'QQQ', 'TLT', 'GLD']
        self.predictors = {}
    
    def train_all(self, verbose: bool = True) -> Dict:
        results = {}
        for i, symbol in enumerate(self.symbols):
            if verbose: print(f"\n[{i+1}/{len(self.symbols)}] Training {symbol}...")
            try:
                p = PricePredictor()
                results[symbol] = p.train(symbol, verbose=verbose)
                self.predictors[symbol] = p
            except Exception as e:
                results[symbol] = {'error': str(e)}
        return results
    
    def predict_all(self) -> Dict:
        return {s: p.predict_next() for s, p in self.predictors.items()}
    
    def get_summary(self) -> pd.DataFrame:
        preds = self.predict_all()
        rows = [{'Symbol': s, 'Current': p['current_price'], 
                 'Predicted': p['predicted_price'], 'Change%': p['predicted_change_pct']}
                for s, p in preds.items() if 'error' not in p]
        return pd.DataFrame(rows)


class VIXPredictor(PricePredictor):
    """VIX predictor for volatility regime."""
    
    def __init__(self):
        super().__init__()
        self.symbol = '^VIX'
    
    def fetch_data(self, symbol='^VIX', years=5):
        return yf.Ticker(symbol).history(period=f"{years}y")['Close'].values
    
    def predict_volatility_regime(self) -> Dict:
        pred = self.predict_next()
        vix = pred['predicted_price']
        
        if vix < 15: regime, action = 'LOW', 'Normal'
        elif vix < 20: regime, action = 'NORMAL', 'Normal'
        elif vix < 25: regime, action = 'ELEVATED', 'Consider reducing risk'
        elif vix < 35: regime, action = 'HIGH', 'Reduce positions, increase hedges'
        else: regime, action = 'EXTREME', 'Maximum defensive'
        
        return {**pred, 'regime': regime, 'action': action}


def generate_lstm_risk_signals(symbols: List[str] = None) -> Dict:
    """Generate LSTM risk signals."""
    if not TORCH_AVAILABLE:
        return {'error': 'PyTorch not available'}
    
    symbols = symbols or ['SPY', 'TLT', 'HYG']
    batch = BatchPredictor(symbols)
    batch.train_all(verbose=False)
    predictions = batch.predict_all()
    
    try:
        vix = VIXPredictor()
        vix.train('^VIX', verbose=False)
        vix_pred = vix.predict_volatility_regime()
    except: vix_pred = {}
    
    signals = [{'symbol': s, 'signal': 'LARGE_MOVE', 'change': p['predicted_change_pct']}
               for s, p in predictions.items() 
               if 'error' not in p and abs(p['predicted_change_pct']) > 2]
    
    if vix_pred.get('regime') in ['HIGH', 'EXTREME']:
        signals.append({'symbol': 'VIX', 'signal': 'VOL_SPIKE', 'regime': vix_pred['regime']})
    
    return {'predictions': predictions, 'vix': vix_pred, 'signals': signals}


if __name__ == "__main__":
    print("LSTM Price Prediction Demo")
    print("="*50)
    
    if not TORCH_AVAILABLE:
        print("Install PyTorch: pip install torch")
    else:
        p = PricePredictor()
        p.train('SPY')
        pred = p.predict_next()
        print(f"\nSPY: ${pred['current_price']:.2f} → ${pred['predicted_price']:.2f} ({pred['predicted_change_pct']:+.2f}%)")

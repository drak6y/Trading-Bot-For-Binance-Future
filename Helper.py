import os, sys, time, math
from Logger import *
from binance.client import Client
from binance import ThreadedWebsocketManager
import BotClass 
from LiveTradingConfig import *
import json
from datetime import datetime

class PaperTradingClient:
    def __init__(self, real_client: Client, initial_balance: float):
        self.real_client = real_client
        self.balance = initial_balance
        self.positions = {}  # {symbol: {'amount': float, 'entry_price': float, 'side': str}}
        self.orders = {}     # {orderId: {symbol, side, type, price, stopPrice, quantity, ...}}
        self.order_counter = 1000
        self.trade_history = []
        self.log_file = 'trades_demo.json'

    def _log_trade(self, trade_info):
        self.trade_history.append(trade_info)
        if log_to_file:
            try:
                with open(self.log_file, 'w') as f:
                    json.dump(self.trade_history, f, indent=4)
            except Exception as e:
                log.error(f"PaperTradingClient - Failed to write log: {e}")

    # --- Pass-through Read Methods ---
    def futures_exchange_info(self): return self.real_client.futures_exchange_info()
    def futures_historical_klines(self, *args, **kwargs): return self.real_client.futures_historical_klines(*args, **kwargs)
    def futures_symbol_ticker(self, **kwargs): return self.real_client.futures_symbol_ticker(**kwargs)
    def futures_order_book(self, **kwargs): return self.real_client.futures_order_book(**kwargs)
    def futures_ping(self): return self.real_client.futures_ping()
    def futures_change_leverage(self, **kwargs): pass # Mock leverage change

    # --- Mocked Write/Account Methods ---
    def futures_account_balance(self):
        return [{'asset': 'USDT', 'balance': str(self.balance), 'withdrawAvailable': str(self.balance)}]

    def futures_account(self):
        # Used for margin check
        return {
            'totalMarginBalance': str(self.balance),
            'totalWalletBalance': str(self.balance),
            'availableBalance': str(self.balance)
        }

    def futures_position_information(self, symbol=None):
        res = []
        # If symbol is specific, return just that one (or empty list if not found? API returns list)
        # If symbol is None, return all non-zero positions? API returns all symbols.
        
        # We need to return a list of dicts matching Binance structure
        # We can fetch all symbols from real client to get structure, but that's slow.
        # We'll just return the ones we have active, plus the requested one if empty.
        
        if symbol:
            pos = self.positions.get(symbol, {'amount': 0.0, 'entry_price': 0.0, 'unRealizedProfit': 0.0, 'cum_commission': 0.0})
            # Calculate unrealized PnL
            pnl = 0.0
            if pos['amount'] != 0:
                current_price = float(self.real_client.futures_symbol_ticker(symbol=symbol)['price'])
                if pos['amount'] > 0:
                    pnl = (current_price - pos['entry_price']) * abs(pos['amount'])
                else:
                    pnl = (pos['entry_price'] - current_price) * abs(pos['amount'])
            
            return [{
                'symbol': symbol,
                'positionAmt': str(pos['amount']),
                'entryPrice': str(pos['entry_price']),
                'markPrice': str(self.real_client.futures_symbol_ticker(symbol=symbol)['price']),
                'unRealizedProfit': str(pnl),
                'liquidationPrice': '0',
                'leverage': str(leverage),
                'maxNotionalValue': '10000000',
                'marginType': 'cross',
                'isolatedMargin': '0',
                'isAutoAddMargin': 'false',
                'positionSide': 'BOTH',
                'notional': str(pos['amount'] * float(self.real_client.futures_symbol_ticker(symbol=symbol)['price'])),
                'cum_commission': pos.get('cum_commission', 0.0)
            }]
        else:
            # Return all active positions
            ret = []
            for sym, pos in self.positions.items():
                if pos['amount'] == 0: continue
                current_price = float(self.real_client.futures_symbol_ticker(symbol=sym)['price'])
                pnl = 0.0
                if pos['amount'] > 0:
                    pnl = (current_price - pos['entry_price']) * abs(pos['amount'])
                else:
                    pnl = (pos['entry_price'] - current_price) * abs(pos['amount'])
                
                ret.append({
                    'symbol': sym,
                    'positionAmt': str(pos['amount']),
                    'entryPrice': str(pos['entry_price']),
                    'markPrice': str(current_price),
                    'unRealizedProfit': str(pnl),
                    'notional': str(pos['amount'] * current_price),
                    'cum_commission': pos.get('cum_commission', 0.0)
                })
            return ret

    def futures_create_order(self, **kwargs):
        self.order_counter += 1
        oid = self.order_counter
        symbol = kwargs['symbol']
        side = kwargs['side']
        type = kwargs['type']
        qty = float(kwargs['quantity'])
        price = float(kwargs.get('price', 0))
        stop_price = float(kwargs.get('stopPrice', 0))
        
        # Simulate MARKET order immediately
        if type == 'MARKET':
            # Fetch current price
            curr_price = float(self.real_client.futures_symbol_ticker(symbol=symbol)['price'])
            # Market orders are Taker (0.05%)
            self._execute_trade(symbol, side, qty, curr_price, fee_rate=0.0005)
            return {'orderId': oid, 'status': 'FILLED', 'avgPrice': str(curr_price), 'executedQty': str(qty), 'cumQuote': str(curr_price*qty)}
        
        # Store LIMIT/STOP orders
        self.orders[oid] = {
            'orderId': oid,
            'symbol': symbol,
            'side': side,
            'type': type,
            'quantity': qty,
            'price': price,
            'stopPrice': stop_price,
            'status': 'NEW',
            'reduceOnly': kwargs.get('reduceOnly', False),
            'origType': type
        }
        log.info(f"PaperTrading - Order Placed: {symbol} {side} {type} Qty:{qty} Price:{price} Stop:{stop_price}")
        return {'orderId': oid, 'status': 'NEW'}

    def _execute_trade(self, symbol, side, qty, price, fee_rate=0.0005):
        # Update position
        pos = self.positions.get(symbol, {'amount': 0.0, 'entry_price': 0.0, 'cum_commission': 0.0})
        current_amt = pos['amount']
        
        # Calculate Commission
        commission = price * qty * fee_rate
        self.balance -= commission
        pos['cum_commission'] = pos.get('cum_commission', 0.0) + commission

        new_amt = current_amt
        if side == 'BUY':
            new_amt += qty
        else:
            new_amt -= qty
            
        # Calculate average entry price if increasing position
        if (current_amt > 0 and side == 'BUY') or (current_amt < 0 and side == 'SELL'):
            total_cost = (abs(current_amt) * pos['entry_price']) + (qty * price)
            new_entry = total_cost / abs(new_amt)
            pos['entry_price'] = new_entry
        elif current_amt == 0:
            pos['entry_price'] = price
        else:
            # Closing position (partial or full) - Realize PnL
            # PnL = (Exit Price - Entry Price) * Qty * Direction
            direction = 1 if current_amt > 0 else -1
            closed_qty = min(abs(current_amt), qty)
            pnl = (price - pos['entry_price']) * closed_qty * direction
            self.balance += pnl
            self._log_trade({'symbol': symbol, 'side': side, 'price': price, 'qty': closed_qty, 'pnl': pnl, 'commission': commission, 'time': str(datetime.now())})
            log.info(f"PaperTrading - Trade Executed: {symbol} {side} @ {price}. PnL: {pnl:.2f}. Comm: {commission:.4f}. New Balance: {self.balance:.2f}")
            
            if abs(new_amt) < 0.00000001: # Close enough to zero
                new_amt = 0
                pos['entry_price'] = 0
                pos['cum_commission'] = 0 # Reset commission for closed position

        pos['amount'] = new_amt
        self.positions[symbol] = pos

    def futures_cancel_all_open_orders(self, symbol=None):
        to_delete = []
        for oid, order in self.orders.items():
            if symbol is None or order['symbol'] == symbol:
                to_delete.append(oid)
        for oid in to_delete:
            del self.orders[oid]

    def futures_get_open_orders(self, symbol=None):
        ret = []
        for oid, order in self.orders.items():
            if symbol is None or order['symbol'] == symbol:
                ret.append(order)
        return ret

    def check_orders(self, symbol, current_price):
        """Check if any pending orders should be filled based on current price."""
        filled_orders = []
        to_delete = []
        
        for oid, order in self.orders.items():
            if order['symbol'] != symbol: continue
            
            triggered = False
            side = order['side']
            price = order['price']
            stop_price = order['stopPrice']
            qty = order['quantity']
            
            # STOP_MARKET
            if order['type'] == 'STOP_MARKET':
                if (side == 'SELL' and current_price <= stop_price) or \
                   (side == 'BUY' and current_price >= stop_price):
                    triggered = True
            
            # TAKE_PROFIT (Limit) or TRAILING_STOP_MARKET (simplified as TP)
            elif order['type'] == 'TAKE_PROFIT':
                if (side == 'SELL' and current_price >= price) or \
                   (side == 'BUY' and current_price <= price): # Wait, TP for Long is Sell at Higher Price
                       # If Long, we Sell. Price > Entry.
                       # If Short, we Buy. Price < Entry.
                       # Binance TP is a Limit order usually? Or Stop?
                       # Code uses FUTURE_ORDER_TYPE_TAKE_PROFIT with price and stopPrice equal.
                       # It acts like a Stop Limit or Stop Market.
                       # Let's assume it triggers if price touches it.
                       if (side == 'SELL' and current_price >= stop_price) or \
                          (side == 'BUY' and current_price <= stop_price):
                           triggered = True

            # LIMIT
            elif order['type'] == 'LIMIT':
                 if (side == 'BUY' and current_price <= price) or \
                    (side == 'SELL' and current_price >= price):
                     triggered = True
            
            if triggered:
                # Execute
                # Calculate PnL for this specific fill?
                # We need to know the entry price of the position to calc RP (Realized Profit) for the callback
                # But _execute_trade calculates PnL based on average entry.
                
                # Determine Fee Rate
                # LIMIT orders sitting on book are Maker (0.02%)
                # STOP_MARKET / TAKE_PROFIT are Taker (0.05%)
                fee_rate = 0.0005
                if order['type'] == 'LIMIT':
                    fee_rate = 0.0002
                
                # Capture balance before
                bal_before = self.balance
                self._execute_trade(symbol, side, qty, current_price, fee_rate=fee_rate)
                bal_after = self.balance
                pnl = bal_after - bal_before
                
                filled_orders.append({
                    'oid': oid,
                    'symbol': symbol,
                    'rp': pnl,
                    'side': side,
                    'price': current_price
                })
                to_delete.append(oid)
        
        for oid in to_delete:
            del self.orders[oid]
            
        return filled_orders


def convert_buffer_to_string(buffer_int):
    """Convert candle count to Binance start_str like 'X hours/days ago'."""
    try:
        u = interval[-1]
        minutes = int(interval[:-1]) * (1 if u == 'm' else 60 if u == 'h' else 1440 if u == 'd' else 1)
        h = math.ceil((minutes * buffer_int) / 60)
        if h < 24:
            log.info(f'convert_buffer_to_string() - buffer: {h} hours ago')
            return f'{h} hours ago'
        d = math.ceil(h / 24)
        log.info(f'convert_buffer_to_string() - buffer: {d} days ago')
        return f'{d} days ago'
    except Exception as e:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        log.warning(f"convert_buffer_to_string() - Info: {(exc_obj, fname, exc_tb.tb_lineno)}, Error: {e}")

class CustomClient:
    def __init__(self, client: Client):
        self.client = client
        self.leverage = leverage
        self.twm = ThreadedWebsocketManager(api_key=API_KEY, api_secret=API_SECRET)
        self.number_of_bots = 0

    def set_leverage(self, symbols_to_trade: list[str]):
        """Set leverage per symbol as defined in config."""
        log.info("set_leverage() - Setting leverage...")
        i = 0
        while i < len(symbols_to_trade):
            sym = symbols_to_trade[i]
            log.info(f"set_leverage() - ({i+1}/{len(symbols_to_trade)}) {sym}")
            try:
                self.client.futures_change_leverage(symbol=sym, leverage=self.leverage)
                i += 1
            except Exception as e:
                exc_type, exc_obj, exc_tb = sys.exc_info()
                fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
                log.warning(f"set_leverage() - Removing {sym}. Info: {(exc_obj, fname, exc_tb.tb_lineno)}, Error: {e}")
                symbols_to_trade.pop(i)

    def start_websockets(self, bots: list[BotClass.Bot]):
        """Start kline sockets for all bots."""
        self.twm.start()
        log.info("start_websockets() - Starting sockets...")
        i = 0
        while i < len(bots):
            b = bots[i]
            try:
                b.stream = self.twm.start_kline_futures_socket(callback=b.handle_socket_message, symbol=b.symbol, interval=interval)
                i += 1
            except Exception as e:
                exc_type, exc_obj, exc_tb = sys.exc_info()
                fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
                log.warning(f"start_websockets() - {b.symbol}. Info: {(exc_obj, fname, exc_tb.tb_lineno)}, Error: {e}")
                bots.pop(i)
        self.number_of_bots = len(bots)

    def ping_server_reconnect_sockets(self, bots: list[BotClass.Bot]):
        """Keep connection alive and auto-reconnect failed sockets."""
        while True:
            time.sleep(15)
            self.client.futures_ping()
            for b in bots:
                if b.socket_failed:
                    try:
                        log.info(f"retry_websockets_job() - Resetting {b.symbol}")
                        self.twm.stop_socket(b.stream)
                        b.stream = self.twm.start_kline_futures_socket(b.handle_socket_message, symbol=b.symbol)
                        b.socket_failed = False
                        log.info("retry_websockets_job() - Reset OK")
                    except Exception as e:
                        exc_type, exc_obj, exc_tb = sys.exc_info()
                        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
                        log.error(f"retry_websockets_job() - {b.symbol}. Info: {(exc_obj, fname, exc_tb.tb_lineno)}, Error: {e}")

    def setup_bots(self, bots: list[BotClass.Bot], symbols_to_trade: list[str], signal_queue, print_trades_q):
        """Instantiate a Bot for each tradable symbol."""
        log.info("setup_bots() - Creating bots...")
        info = self.client.futures_exchange_info()['symbols']
        meta = {x['pair']: (int(x['pricePrecision']), int(x['quantityPrecision']), float(x['filters'][0]['tickSize'])) for x in info}

        i = 0
        while i < len(symbols_to_trade):
            sym = symbols_to_trade[i]
            if sym in meta:
                cp, op, tick = meta[sym]
                bots.append(BotClass.Bot(symbol=sym, Open=[], Close=[], High=[], Low=[], Volume=[], Date=[],
                                         OP=op, CP=cp, index=i, tick=tick, strategy=trading_strategy,
                                         TP_SL_choice=TP_SL_choice, SL_mult=SL_mult, TP_mult=TP_mult,
                                         signal_queue=signal_queue, print_trades_q=print_trades_q))
                i += 1
            else:
                log.info(f"setup_bots() - {sym} missing exchange info, removed")
                try:
                    symbols_to_trade.pop(i)
                except Exception as e:
                    exc_type, exc_obj, exc_tb = sys.exc_info()
                    fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
                    log.warning(f"setup_bots() - Remove failed. Info: {(exc_obj, fname, exc_tb.tb_lineno)}, Error: {e}")
        log.info("setup_bots() - Done")

    def combine_data(self, bots: list[BotClass.Bot], symbols_to_trade: list[str], buffer):
        """Fetch historical data and merge with live stream so bots can trade immediately."""
        log.info("combine_data() - Merging historical + socket data...")
        i = 0
        while i < len(bots):
            b = bots[i]
            log.info(f"combine_data() - ({i+1}/{len(bots)}) {b.symbol}")
            dt, op, cl, hi, lo, vo = self.get_historical(b.symbol, buffer)
            try:
                for arr in (dt, op, cl, hi, lo, vo): arr.pop(-1)
                b.add_hist(Date_temp=dt, Open_temp=op, Close_temp=cl, High_temp=hi, Low_temp=lo, Volume_temp=vo)
                i += 1
            except Exception as e:
                exc_type, exc_obj, exc_tb = sys.exc_info()
                fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
                try:
                    log.warning(f"combine_data() - Add failed. Info: {(exc_obj, fname, exc_tb.tb_lineno)}, Error: {e}")
                    self.twm.stop_socket(b.stream)
                    symbols_to_trade.pop(i); bots.pop(i); self.number_of_bots -= 1
                except Exception as e2:
                    exc_type2, exc_obj2, exc_tb2 = sys.exc_info()
                    fname2 = os.path.split(exc_tb2.tb_frame.f_code.co_filename)[1]
                    log.warning(f"combine_data() - Cleanup failed. Info: {(exc_obj2, fname2, exc_tb2.tb_lineno)}, Error: {e2}")
        log.info("combine_data() - All symbols ready. Scanning for trades...")

    def get_historical(self, symbol: str, buffer):
        """Download historical klines for a symbol."""
        O, H, L, C, V, D = [], [], [], [], [], []
        try:
            for k in self.client.futures_historical_klines(symbol, interval, start_str=buffer):
                D.append(int(k[6])); O.append(float(k[1])); C.append(float(k[4]))
                H.append(float(k[2])); L.append(float(k[3])); V.append(float(k[7]))
        except Exception as e:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            log.error(f'get_historical() - {symbol}. Info: {(exc_obj, fname, exc_tb.tb_lineno)}, Error: {e}')
        return D, O, C, H, L, V

    def get_account_balance(self):
        """Return USDT futures wallet balance."""
        try:
            for x in self.client.futures_account_balance():
                if x['asset'] == 'USDT': return float(x['balance'])
        except Exception as e:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            log.error(f'get_account_balance() - Info: {(exc_obj, fname, exc_tb.tb_lineno)}, Error: {e}')

class Trade:
    def __init__(self, index: int, entry_price: float, position_size: float, take_profit_val: float,
                 stop_loss_val: float, trade_direction: int, order_id: int, symbol: str, CP: int, tick_size: float):
        self.index, self.symbol, self.entry_price, self.position_size = index, symbol, entry_price, position_size
        if trade_direction:
            self.TP_val, self.SL_val = entry_price + take_profit_val, entry_price - stop_loss_val
        else:
            self.TP_val, self.SL_val = entry_price - take_profit_val, entry_price + stop_loss_val
        self.CP, self.tick_size, self.trade_direction, self.order_id = CP, tick_size, trade_direction, order_id
        self.TP_id = self.SL_id = ''
        self.trade_status, self.trade_start = 0, ''
        self.Highest_val, self.Lowest_val = -9_999_999, 9_999_999
        self.trail_activated, self.same_candle = False, True
        self.current_price = 0

"""BTC momentum bot for agent-fun/bars-replay/v1 (hello, batch, orders, bar).

Strategy: slow trailing momentum with risk control.
- Every REBAL bars, compare the latest close with the close LOOKBACK bars
  earlier: a positive trailing return is an uptrend, a negative one is not.
- Flat + uptrend -> buy with ~99% of equity. Holding + trend gone -> sell all.
- A hard 2% stop under the position's cost sells on any bar, trend or not.
- Orders carry a generous max_slippage_bps so fills are not rejected.
Deterministic: closes only, no clock, no network, no randomness.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor"))
import makefun_bars

SYMBOL = "CBBTC"
LOOKBACK = 360        # 6 hours of 1-minute bars
REBAL = 120           # re-check the trend every 2 hours
STOP = 0.02           # sell if the position is 2% under its cost
WEIGHT = 0.99         # spend 99% of equity on an entry
SLIP = 500            # max_slippage_bps: 5%

closes = []


def on_batch(state, batch):
    bar = None
    for b in batch["bars"]:
        if b["symbol"] == SYMBOL:
            bar = b
    if bar is None:
        return []
    close = int(bar["c"])
    closes.append(close)
    held = state.positions.get(SYMBOL)

    # Hard stop on every bar: cut a position 2% under its cost.
    if held is not None and held.qty > 0:
        value = state.value(SYMBOL, held.qty)
        if value * 100 <= held.cost * 98:
            return [{"side": "sell", "symbol": SYMBOL, "qty": held.qty,
                     "max_slippage_bps": SLIP}]

    # Trend decisions only on rebalance bars, once enough history exists.
    if state.seq % REBAL != 0 or len(closes) <= LOOKBACK:
        return []
    trailing = close / closes[-LOOKBACK - 1] - 1.0

    if held is not None and held.qty > 0:
        if trailing < -0.0005:  # exit only on a clearly negative trend
            return [{"side": "sell", "symbol": SYMBOL, "qty": held.qty,
                     "max_slippage_bps": SLIP}]
        return []
    if trailing > 0:
        stake = int(state.equity * WEIGHT)
        if stake > state.cash:
            stake = state.cash
        room = state.weight_room(SYMBOL)
        if stake > room:
            stake = room
        if stake >= 1_000_000:
            return [{"side": "buy", "symbol": SYMBOL,
                     "notional_quote_units": stake, "max_slippage_bps": SLIP}]
    return []


if __name__ == "__main__":
    makefun_bars.run(on_batch)

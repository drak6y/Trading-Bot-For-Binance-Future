from Logger import *
from LiveTradingConfig import *
 
def USDT_SL_TP(options):
    """TP/SL when base unit is USDT and depends on filled position size."""
    q = round(1 / options['position_size'], 6)
    return SL_mult * q, TP_mult * q

def candle_wick(Trade_Direction, Close, Open, High, Low, current_index):
    """
    Estrategia: Candle Wick (Mecha de Vela)
    
    Concepto:
    Busca patrones de reversión basados en velas con "mechas" muy largas en comparación con su cuerpo,
    lo que indica rechazo del precio en una dirección tras una tendencia.
    
    Condiciones de VENTA (SHORT):
    1. Tendencia Alcista previa (3 velas subiendo).
    2. Vela de rechazo (i-1): Bajista (Close < Open) y con mechas 10 veces más grandes que el cuerpo.
    3. Confirmación: La vela actual cierra por debajo de la vela de rechazo.
    
    Condiciones de COMPRA (LONG):
    1. Tendencia Bajista previa (3 velas bajando).
    2. Vela de rechazo (i-1): Alcista (Close > Open) y con mechas 10 veces más grandes que el cuerpo.
    3. Confirmación: La vela actual cierra por encima de la vela de rechazo.
    """
    i = current_index
    if Close[i-4] < Close[i-3] < Close[i-2] and Close[i-1] < Open[i-1] and (High[i-1]-Open[i-1] + Close[i-1]-Low[i-1]) > 10*(Open[i-1]-Close[i-1]) and Close[i] < Close[i-1]:
        log.info(f"STRATEGY SIGNAL (SHORT): Candle Wick Reversal. Uptrend -> Long Wick Rejection -> Confirmation Down")
        return 0
    if Close[i-4] > Close[i-3] > Close[i-2] and Close[i-1] > Open[i-1] and (High[i-1]-Close[i-1] + Open[i-1]-Low[i-1]) > 10*(Close[i-1]-Open[i-1]) and Close[i] > Close[i-1]:
        log.info(f"STRATEGY SIGNAL (LONG): Candle Wick Reversal. Downtrend -> Long Wick Rejection -> Confirmation Up")
        return 1
    return Trade_Direction

def fibMACD(Trade_Direction, Close, Open, High, Low, MACD_signal, MACD, EMA200, current_index):
    """
    Estrategia: Fibonacci + MACD + Engulfing
    
    Concepto:
    Estrategia compleja que combina retrocesos de Fibonacci, cruces de MACD y patrones de velas envolventes (Engulfing).
    
    Pasos:
    1. Determina la tendencia general usando la EMA200.
    2. Identifica picos y valles recientes (Swing Highs/Lows).
    3. Calcula niveles de Fibonacci entre esos puntos.
    4. Busca un rebote en un nivel Fibonacci (0.236 a 0.786).
    5. Confirma con un patrón de vela envolvente (Engulfing).
    6. Confirma con un cruce de MACD a favor de la tendencia.
    """
    period = 100
    peaks, p_locs, troughs, t_locs = [], [], [], []
    for i in range(current_index - period, current_index - 2):
        if High[i] > max(High[i-1], High[i+1], High[i-2], High[i+2]):
            peaks.append(High[i]); p_locs.append(i)
        elif Low[i] < min(Low[i-1], Low[i+1], Low[i-2], Low[i+2]):
            troughs.append(Low[i]); t_locs.append(i)

    trend = 1 if Close[current_index] > EMA200[current_index] else 0 if Close[current_index] < EMA200[current_index] else -99
    max_pos = min_pos = -99

    if trend == 1:
        max_close, min_close = -1e9, 1e9
        max_flag = min_flag = 0
        for i in range(len(peaks)-1, -1, -1):
            if peaks[i] > max_close and max_flag < 2:
                max_close = peaks[i]; max_pos = p_locs[i]; max_flag = 0
            elif max_flag == 2: break
            else: max_flag += 1
        start = -99
        for i, loc in enumerate(t_locs):
            if loc < max_pos: start = i
            else: break
        for i in range(start, -1, -1):
            if troughs[i] < min_close and min_flag < 2:
                min_close = troughs[i]; min_pos = t_locs[i]; min_flag = 0
            elif min_flag == 2: break
            else: min_flag += 1

        f0 = max_close
        f1 = max_close - .236*(max_close-min_close)
        f2 = max_close - .382*(max_close-min_close)
        f3 = max_close - .5*(max_close-min_close)
        f4 = max_close - .618*(max_close-min_close)
        f5 = max_close - .786*(max_close-min_close)
        f6 = min_close

        i = current_index
        cond_macd = (MACD_signal[i-1] < MACD[i-1] or MACD_signal[i-2] < MACD[i-2]) and MACD_signal[i] > MACD[i]
        engulf_bull = Close[i-2] < Open[i-2] < Close[i-1] < Close[i]
        if (f0 > Low[i-2] > f1 and Close[i-3] > f1 and Close[i-4] > f1 and Close[-6] > f1 and engulf_bull and cond_macd) \
        or (f1 > Low[i-2] > f2 and Close[i-3] > f2 and Close[i-4] > f2 and Close[-6] > f2 and engulf_bull and cond_macd) \
        or (f2 > Low[i-1] > f3 and Close[i-2] > f3 and Close[i-3] > f3 and Close[i-4] > f3 and engulf_bull and cond_macd) \
        or (f3 > Low[i-1] > f4 and Close[i-2] > f4 and Close[i-3] > f4 and Close[i-4] > f4 and engulf_bull and cond_macd) \
        or (f4 > Low[i-1] > f5 and Close[i-2] > f5 and Close[i-3] > f5 and Close[i-4] > f5 and engulf_bull and cond_macd) \
        or (f5 > Low[i-1] > f6 and Close[i-2] > f6 and Close[i-3] > f6 and Close[i-4] > f6 and engulf_bull and cond_macd):
            log.info(f"STRATEGY SIGNAL (LONG): Fib Pullback + Bullish Engulfing + MACD Cross")
            return 1

    elif trend == 0:
        max_close, min_close = -1e9, 1e9
        max_flag = min_flag = 0
        for i in range(len(troughs)-1, -1, -1):
            if troughs[i] < min_close and min_flag < 2:
                min_close = troughs[i]; min_pos = t_locs[i]; min_flag = 0
            elif min_flag == 2: break
            else: min_flag += 1
        start = -99
        for i, loc in enumerate(p_locs):
            if loc < min_pos: start = i
            else: break
        for i in range(start, -1, -1):
            if peaks[i] > max_close and max_flag < 2:
                max_close = peaks[i]; max_pos = p_locs[i]; max_flag = 0
            elif max_flag == 2: break
            else: max_flag += 1

        f0 = min_close
        f1 = min_close + .236*(max_close-min_close)
        f2 = min_close + .382*(max_close-min_close)
        f3 = min_close + .5*(max_close-min_close)
        f4 = min_close + .618*(max_close-min_close)
        f5 = min_close + .786*(max_close-min_close)
        f6 = max_close

        i = current_index
        cond_macd = (MACD_signal[i-1] > MACD[i-1] or MACD_signal[i-2] > MACD[i-2]) and MACD_signal[i] < MACD[i]
        engulf_bear = Close[i-2] > Open[i-2] > Close[i-1] > Close[i]
        if (f0 < High[i-2] < f1 and Close[i-3] < f1 and Close[i-4] < f1 and Close[-6] < f1 and engulf_bear and cond_macd) \
        or (f1 < High[i-2] < f2 and Close[i-3] < f2 and Close[i-4] < f2 and Close[-6] < f2 and engulf_bear and cond_macd) \
        or (f2 < High[i-2] < f3 and Close[i-3] < f3 and Close[i-4] < f3 and Close[-6] < f3 and engulf_bear and cond_macd) \
        or (f3 < High[i-2] < f4 and Close[i-3] < f4 and Close[i-4] < f4 and Close[-6] < f4 and engulf_bear and cond_macd) \
        or (f4 < High[i-2] < f5 and Close[i-3] < f5 and Close[i-4] < f5 and Close[-6] < f5 and engulf_bear and cond_macd) \
        or (f5 < High[i-2] < f6 and Close[i-3] < f6 and Close[i-4] < f6 and Close[-6] < f6 and engulf_bear and cond_macd):
            log.info(f"STRATEGY SIGNAL (SHORT): Fib Pullback + Bearish Engulfing + MACD Cross")
            return 0

    return Trade_Direction

def goldenCross(Trade_Direction, Close, EMA100, EMA50, EMA20, RSI, current_index):
    """
    Estrategia: Golden Cross (Cruce Dorado) Modificado
    
    Concepto:
    Busca cruces de medias móviles (EMA20 sobre EMA50) filtrados por una EMA de largo plazo (EMA100) y RSI.
    
    Condiciones de COMPRA (LONG):
    1. Tendencia Alcista: Precio > EMA100.
    2. Fuerza: RSI > 50.
    3. Cruce: EMA20 cruza por encima de EMA50.
    
    Condiciones de VENTA (SHORT):
    1. Tendencia Bajista: Precio < EMA100.
    2. Debilidad: RSI < 50.
    3. Cruce: EMA20 cruza por debajo de EMA50.
    """
    i = current_index
    if Close[i] > EMA100[i] and RSI[i] > 50:
        if (EMA20[i-1] < EMA50[i-1] <= EMA20[i]) or (EMA20[i-2] < EMA50[i-2] <= EMA20[i]) or (EMA20[i-3] < EMA50[i-3] <= EMA20[i]):
            log.info(f"STRATEGY SIGNAL (LONG): Golden Cross (EMA20 > EMA50) + Price > EMA100 + RSI > 50")
            return 1
    elif Close[i] < EMA100[i] and RSI[i] < 50:
        if (EMA20[i-1] > EMA50[i-1] >= EMA20[i]) or (EMA20[i-2] > EMA50[i-2] >= EMA20[i]) or (EMA20[i-3] > EMA50[i-3] >= EMA20[i]):
            log.info(f"STRATEGY SIGNAL (SHORT): Death Cross (EMA20 < EMA50) + Price < EMA100 + RSI < 50")
            return 0
    return Trade_Direction

def StochRSIMACD(Trade_Direction, fastd, fastk, RSI, MACD, macdsignal, current_index):
    """
    Estrategia: StochRSI + MACD + RSI
    
    Concepto:
    Combina tres indicadores de momentum para confirmar entradas de alta probabilidad.
    
    Condiciones de COMPRA (LONG):
    1. StochRSI Sobrevendido: K y D < 20.
    2. RSI Alcista: RSI > 50.
    3. MACD: Cruce alcista (MACD > Signal).
    
    Condiciones de VENTA (SHORT):
    1. StochRSI Sobrecomprado: K y D > 80.
    2. RSI Bajista: RSI < 50.
    3. MACD: Cruce bajista (MACD < Signal).
    """
    i = current_index
    bull = (
        ((fastd[i] < 20 and fastk[i] < 20) and RSI[i] > 50 and MACD[i] > macdsignal[i] and MACD[i-1] < macdsignal[i-1]) or
        ((fastd[i-1] < 20 and fastk[i-1] < 20) and RSI[i] > 50 and MACD[i] > macdsignal[i] and MACD[i-2] < macdsignal[i-2] and fastd[i] < 80 and fastk[i] < 80) or
        ((fastd[i-2] < 20 and fastk[i-2] < 20) and RSI[i] > 50 and MACD[i] > macdsignal[i] and MACD[i-1] < macdsignal[i-1] and fastd[i] < 80 and fastk[i] < 80) or
        ((fastd[i-3] < 20 and fastk[i-3] < 20) and RSI[i] > 50 and MACD[i] > macdsignal[i] and MACD[i-2] < macdsignal[i-2] and fastd[i] < 80 and fastk[i] < 80)
    )
    bear = (
        ((fastd[i] > 80 and fastk[i] > 80) and RSI[i] < 50 and MACD[i] < macdsignal[i] and MACD[i-1] > macdsignal[i-1]) or
        ((fastd[i-1] > 80 and fastk[i-1] > 80) and RSI[i] < 50 and MACD[i] < macdsignal[i] and MACD[i-2] > macdsignal[i-2] and fastd[i] > 20 and fastk[i] > 20) or
        ((fastd[i-2] > 80 and fastk[i-2] > 80) and RSI[i] < 50 and MACD[i] < macdsignal[i] and MACD[i-1] > macdsignal[i-1] and fastd[i] > 20 and fastk[i] > 20) or
        ((fastd[i-3] > 80 and fastk[i-3] > 80) and RSI[i] < 50 and MACD[i] < macdsignal[i] and MACD[i-2] > macdsignal[i-2] and fastd[i] > 20 and fastk[i] > 20)
    )
    if bull:
        log.info(f"STRATEGY SIGNAL (LONG): StochRSI Oversold + RSI>50 + MACD Cross UP")
        return 1
    if bear:
        log.info(f"STRATEGY SIGNAL (SHORT): StochRSI Overbought + RSI<50 + MACD Cross DOWN")
        return 0
    return Trade_Direction

def tripleEMA(Trade_Direction, EMA3, EMA6, EMA9, current_index):
    """
    Estrategia: Triple EMA Scalping
    
    Concepto:
    Estrategia muy rápida para scalping usando EMAs de muy corto plazo (3, 6, 9).
    Busca un cruce tras un periodo de separación (tendencia sostenida).
    
    Condiciones de VENTA (SHORT):
    1. Tendencia Alcista previa: EMA3 > EMA6 > EMA9 durante 4 velas.
    2. Cruce: EMA3 cruza por debajo de EMA6 y EMA9.
    
    Condiciones de COMPRA (LONG):
    1. Tendencia Bajista previa: EMA3 < EMA6 < EMA9 durante 4 velas.
    2. Cruce: EMA3 cruza por encima de EMA6 y EMA9.
    """
    i = current_index
    if EMA3[i-4] > EMA6[i-4] > 0 and EMA3[i-4] > EMA9[i-4] and \
       EMA3[i-3] > EMA6[i-3] and EMA3[i-3] > EMA9[i-3] and \
       EMA3[i-2] > EMA6[i-2] and EMA3[i-2] > EMA9[i-2] and \
       EMA3[i-1] > EMA6[i-1] and EMA3[i-1] > EMA9[i-1] and \
       EMA3[i] < EMA6[i] and EMA3[i] < EMA9[i]:
        log.info(f"STRATEGY SIGNAL (SHORT): Triple EMA Cross Down (3 < 6,9) after uptrend")
        return 0
    if EMA3[i-4] < EMA6[i-4] and EMA3[i-4] < EMA9[i-4] and \
       EMA3[i-3] < EMA6[i-3] and EMA3[i-3] < EMA9[i-3] and \
       EMA3[i-2] < EMA6[i-2] and EMA3[i-2] < EMA9[i-2] and \
       EMA3[i-1] < EMA6[i-1] and EMA3[i-1] < EMA9[i-1] and \
       EMA3[i] > EMA6[i] and EMA3[i] > EMA9[i]:
        log.info(f"STRATEGY SIGNAL (LONG): Triple EMA Cross Up (3 > 6,9) after downtrend")
        return 1
    return Trade_Direction

def heikin_ashi_ema2(Open_H, High_H, Low_H, Close_H, Trade_Direction, CurrentPos, Close_pos, fastd, fastk, EMA200, current_index):
    """
    Estrategia: Heikin Ashi + EMA200 + StochRSI (Versión 2)
    
    Concepto:
    Usa velas Heikin Ashi para suavizar el ruido. Opera a favor de la tendencia mayor (EMA200)
    cuando el StochRSI da señal y hay un patrón de velas válido.
    
    Condiciones de VENTA (SHORT):
    1. StochRSI cruza hacia abajo.
    2. Precio < EMA200 (Tendencia bajista).
    3. Patrón de velas Heikin Ashi bajista reciente.
    
    Condiciones de COMPRA (LONG):
    1. StochRSI cruza hacia arriba.
    2. Precio > EMA200 (Tendencia alcista).
    3. Patrón de velas Heikin Ashi alcista reciente.
    """
    i = current_index
    if CurrentPos == -99:
        Trade_Direction = -99
        short_th, long_th = .7, .3
        if fastk[i-1] > fastd[i-1] and fastk[i] < fastd[i] and Close_H[i] < EMA200[i]:
            for k in range(10, 2, -1):
                if Close_H[-k] < Open_H[-k] and Open_H[-k] == High_H[-k]:
                    for j in range(k, 2, -1):
                        if Close_H[-j] > EMA200[-j] and Close_H[-j+1] < EMA200[-j+1] and Open_H[-j] > Close_H[-j]:
                            if all(fastd[-r] >= short_th and fastk[-r] >= short_th for r in range(j, 0, -1)):
                                log.info(f"STRATEGY SIGNAL (SHORT): HA + EMA200 + StochRSI Cross Down")
                                return 0, Close_pos
        elif fastk[i-1] < fastd[i-1] and fastk[i] > fastd[i] and Close_H[i] > EMA200[i]:
            for k in range(10, 2, -1):
                if Close_H[-k] > Open_H[-k] and Open_H[-k] == Low_H[-k]:
                    for j in range(k, 2, -1):
                        if Close_H[-j] < EMA200[-j] and Close_H[-j+1] > EMA200[-j+1] and Open_H[-j] < Close_H[-j]:
                            if all(fastd[-r] <= long_th and fastk[-r] <= long_th for r in range(j, 0, -1)):
                                log.info(f"STRATEGY SIGNAL (LONG): HA + EMA200 + StochRSI Cross Up")
                                return 1, Close_pos
    elif CurrentPos == 1 and Close_H[i] < Open_H[i]:
        Close_pos = 1
    elif CurrentPos == 0 and Close_H[i] > Open_H[i]:
        Close_pos = 1
    else:
        Close_pos = 0
    return Trade_Direction, Close_pos

def heikin_ashi_ema(Open_H, Close_H, Trade_Direction, CurrentPos, Close_pos, fastd, fastk, EMA200, current_index):
    """
    Estrategia: Heikin Ashi + EMA200 + StochRSI (Versión Simplificada)
    
    Concepto:
    Similar a la versión 2 pero con condiciones de entrada ligeramente diferentes en el StochRSI.
    """
    i = current_index
    if CurrentPos == -99:
        Trade_Direction = -99
        short_th, long_th = .8, .2
        if fastk[i] > short_th and fastd[i] > short_th:
            for k in range(10, 2, -1):
                if fastd[-k] >= .8 and fastk[-k] >= .8:
                    for j in range(k, 2, -1):
                        if fastk[-j] > fastd[-j] and fastk[-j+1] < fastd[-j+1]:
                            if all(fastk[r] >= short_th and fastd[r] >= short_th for r in range(j, 2, -1)):
                                if Close_H[i-2] > EMA200[i-2] and Close_H[i-1] < EMA200[i-1] and Close_H[i] < Open_H[i]:
                                    log.info(f"STRATEGY SIGNAL (SHORT): HA Simple + EMA200 + StochRSI")
                                    return 0, Close_pos
        elif fastk[i] < long_th and fastd[i] < long_th:
            for k in range(10, 2, -1):
                if fastd[-k] <= .2 and fastk[-k] <= .2:
                    for j in range(k, 2, -1):
                        if fastk[-j] < fastd[-j] and fastk[-j+1] > fastd[-j+1] and fastk[i] < long_th and fastd[i] < long_th:
                            if all(fastk[r] <= long_th and fastd[r] <= long_th for r in range(j, 2, -1)):
                                if Close_H[i-2] < EMA200[i-2] and Close_H[i-1] > EMA200[i-1] and Close_H[i] > Open_H[i]:
                                    log.info(f"STRATEGY SIGNAL (LONG): HA Simple + EMA200 + StochRSI")
                                    return 1, Close_pos
    elif CurrentPos == 1 and Close_H[i] < Open_H[i]:
        Close_pos = 1
    elif CurrentPos == 0 and Close_H[i] > Open_H[i]:
        Close_pos = 1
    else:
        Close_pos = 0
    return Trade_Direction, Close_pos

def tripleEMAStochasticRSIATR(Close, Trade_Direction, EMA50, EMA14, EMA8, fastd, fastk, current_index):
    """
    Estrategia: Triple EMA + Stochastic RSI + ATR (implícito en TP/SL)
    
    Concepto:
    Busca entrar a favor de una tendencia fuerte confirmada por la alineación de 3 medias móviles exponenciales (EMA).
    Usa el oscilador Estocástico RSI para afinar la entrada en un momento de "cruce" (momentum).
    
    Indicadores:
    - EMA8 (Rápida): Reacciona rápido al precio.
    - EMA14 (Media): Tendencia a corto plazo.
    - EMA50 (Lenta): Tendencia a medio plazo.
    - StochRSI (fastk, fastd): Mide si el precio está sobrecomprado o sobrevendido.
    
    Condiciones de COMPRA (LONG):
    1. Tendencia Alcista Clara: El precio > EMA8 > EMA14 > EMA50. (Alineación perfecta).
    2. Momentum Alcista: La línea K del estocástico cruza por encima de la línea D (Cruce dorado).
    
    Condiciones de VENTA (SHORT):
    1. Tendencia Bajista Clara: El precio < EMA8 < EMA14 < EMA50.
    2. Momentum Bajista: La línea K del estocástico cruza por debajo de la línea D (Cruce de la muerte).
    """
    i = current_index
    
    # --- LOGGING PARA DEPURACIÓN ---
    # Descomentar para ver los valores exactos que está evaluando la estrategia en cada vela
    # log.debug(f"Strat Check: Price={Close[i]:.2f} | EMAs: {EMA8[i]:.2f} > {EMA14[i]:.2f} > {EMA50[i]:.2f} | Stoch: K={fastk[i]:.2f}, D={fastd[i]:.2f}")
    
    # Señal de COMPRA (LONG)
    if Close[i] > EMA8[i] > EMA14[i] > EMA50[i] and fastk[i] > fastd[i] and fastk[i-1] < fastd[i-1]:
        log.info(f"STRATEGY SIGNAL (LONG): Price({Close[i]}) > EMA8 > EMA14 > EMA50 AND Stoch Cross UP")
        return 1
        
    # Señal de VENTA (SHORT)
    if Close[i] < EMA8[i] < EMA14[i] < EMA50[i] and fastk[i] < fastd[i] and fastk[i-1] > fastd[i-1]:
        log.info(f"STRATEGY SIGNAL (SHORT): Price({Close[i]}) < EMA8 < EMA14 < EMA50 AND Stoch Cross DOWN")
        return 0
        
    return Trade_Direction

def stochBB(Trade_Direction, fastd, fastk, percent_B, current_index):
    """
    Estrategia: Stochastic RSI + Bollinger Bands %B
    
    Concepto:
    Estrategia de reversión a la media. Busca precios extremos fuera de las Bandas de Bollinger
    que coincidan con extremos en el StochRSI.
    
    Condiciones de COMPRA (LONG):
    1. StochRSI Sobrevendido (<0.2) y cruzando hacia arriba.
    2. Precio fuera de la Banda Inferior (%B < 0) recientemente.
    
    Condiciones de VENTA (SHORT):
    1. StochRSI Sobrecomprado (>0.8) y cruzando hacia abajo.
    2. Precio fuera de la Banda Superior (%B > 1) recientemente.
    """
    i = current_index
    b1, b2, b3 = percent_B[i], percent_B[i-1], percent_B[i-2]
    if fastk[i] < .2 and fastd[i] < .2 and fastk[i] > fastd[i] and fastk[i-1] < fastd[i-1] and (b1 < 0 or b2 < 0 or b3 < 0):
        log.info(f"STRATEGY SIGNAL (LONG): StochRSI Oversold + Bollinger Band Breakout Low")
        return 1
    if fastk[i] > .8 and fastd[i] > .8 and fastk[i] < fastd[i] and fastk[i-1] > fastd[i-1] and (b1 > 1 or b2 > 1 or b3 > 1):
        log.info(f"STRATEGY SIGNAL (SHORT): StochRSI Overbought + Bollinger Band Breakout High")
        return 0
    return Trade_Direction

def breakout(Trade_Direction, Close, VolumeStream, max_Close, min_Close, max_Vol, current_index):
    """
    Estrategia: Breakout con Volumen
    
    Concepto:
    Busca rupturas de máximos o mínimos recientes confirmadas por un pico de volumen.
    
    Condiciones de COMPRA (LONG):
    1. Precio cierra por encima del Máximo de N periodos.
    2. Volumen es mayor que el Máximo Volumen de N periodos.
    
    Condiciones de VENTA (SHORT):
    1. Precio cierra por debajo del Mínimo de N periodos.
    2. Volumen es mayor que el Máximo Volumen de N periodos.
    """
    i = current_index
    if Close[i] >= max_Close.iloc[i] and VolumeStream[i] >= max_Vol.iloc[i]:
        log.info(f"STRATEGY SIGNAL (LONG): Price Breakout High + Volume Spike")
        return 1
    if Close[i] <= min_Close.iloc[i] and VolumeStream[i] >= max_Vol.iloc[i]:
        log.info(f"STRATEGY SIGNAL (SHORT): Price Breakout Low + Volume Spike")
        return 0
    return Trade_Direction

def ema_crossover(Trade_Direction, current_index, ema_short, ema_long):
    """
    Estrategia: EMA Crossover (Cruce Simple)
    
    Concepto:
    La estrategia más básica de seguimiento de tendencia.
    
    Condiciones de VENTA (SHORT):
    1. EMA Corta cruza por debajo de EMA Larga.
    
    Condiciones de COMPRA (LONG):
    1. EMA Corta cruza por encima de EMA Larga.
    """
    i = current_index
    if ema_short[i-1] > ema_long[i-1] and ema_short[i] < ema_long[i]:
        log.info(f"STRATEGY SIGNAL (SHORT): EMA Short crossed below EMA Long")
        return 0
    if ema_short[i-1] < ema_long[i-1] and ema_short[i] > ema_long[i]:
        log.info(f"STRATEGY SIGNAL (LONG): EMA Short crossed above EMA Long")
        return 1
    return Trade_Direction

def EMA_cross(Trade_Direction, EMA_short, EMA_long, current_index):
    """
    Estrategia: EMA Cross con Confirmación
    
    Concepto:
    Similar al cruce simple, pero exige que las medias hayan estado separadas en la dirección opuesta
    durante al menos 4 velas antes del cruce. Esto evita señales falsas en mercados laterales (whipsaws).
    
    Condiciones de VENTA (SHORT):
    1. EMA Corta > EMA Larga durante 4 velas previas.
    2. EMA Corta cruza por debajo de EMA Larga.
    
    Condiciones de COMPRA (LONG):
    1. EMA Corta < EMA Larga durante 4 velas previas.
    2. EMA Corta cruza por encima de EMA Larga.
    """
    i = current_index
    if EMA_short[i-4] > EMA_long[i-4] and EMA_short[i-3] > EMA_long[i-3] and EMA_short[i-2] > EMA_long[i-2] and EMA_short[i-1] > EMA_long[i-1] and EMA_short[i] < EMA_long[i]:
        log.info(f"STRATEGY SIGNAL (SHORT): EMA Cross Down after sustained separation")
        return 0
    if EMA_short[i-4] < EMA_long[i-4] and EMA_short[i-3] < EMA_long[i-3] and EMA_short[i-2] < EMA_long[i-2] and EMA_short[i-1] < EMA_long[i-1] and EMA_short[i] > EMA_long[i]:
        log.info(f"STRATEGY SIGNAL (LONG): EMA Cross Up after sustained separation")
        return 1
    return Trade_Direction

def SetSLTP(stop_loss_val_arr, take_profit_val_arr, peaks, troughs, Close, High, Low, Trade_Direction, SL, TP, TP_SL_choice, current_index):
    """Compute absolute SL/TP from arrays or from swing points."""
    i = current_index
    tp = sl = -99
    if TP_SL_choice in ('%', 'x (ATR)'):
        tp = take_profit_val_arr[i]; sl = stop_loss_val_arr[i]
    elif TP_SL_choice.startswith('x (Swing High/Low) level'):
        high_swing, low_swing = High[i], Low[i]
        hf = lf = 0
        lvl = int(TP_SL_choice[-1])
        for j in range(i - lvl, -1, -1):
            if High[j] > high_swing and not hf and peaks[j]:
                high_swing = peaks[j]; hf = 1
            if Low[j] < low_swing and not lf and troughs[j]:
                low_swing = troughs[j]; lf = 1
            if (hf and Trade_Direction == 0) or (lf and Trade_Direction == 1): break
        if Trade_Direction == 0:
            sl = SL * (high_swing - Close[i]); tp = TP * sl
        elif Trade_Direction == 1:
            sl = SL * (Close[i] - low_swing); tp = TP * sl
    elif TP_SL_choice.startswith('x (Swing Close) level'):
        high_swing = low_swing = Close[i]
        hf = lf = 0
        lvl = int(TP_SL_choice[-1])
        for j in range(i - lvl, -1, -1):
            if Close[j] > high_swing and not hf and peaks[j]:
                high_swing = peaks[j]; hf = 1
            if Close[j] < low_swing and not lf and troughs[j]:
                low_swing = troughs[j]; lf = 1
            if (hf and Trade_Direction == 0) or (lf and Trade_Direction == 1): break
        if Trade_Direction == 0:
            sl = SL * (high_swing - Close[i]); tp = TP * sl
        elif Trade_Direction == 1:
            sl = SL * (Close[i] - low_swing); tp = TP * sl
    return sl, tp

"""
Advanced Options Intelligence
Pulls real option chain data from Dhan, analyzes across multiple strikes
PCR, OI Analysis, IV Term Structure, Liquidity, Volume Spikes, Institutional Positioning
"""

from dataclasses import dataclass
from typing import Dict, List, Tuple
import pandas as pd
from loguru import logger


@dataclass
class StrikeAnalysis:
    """Analysis for a single strike (Call & Put)"""
    strike: float
    ce_ltp: float
    pe_ltp: float
    ce_oi: float
    pe_oi: float
    ce_volume: float
    pe_volume: float
    ce_iv: float
    pe_iv: float
    ce_bid_ask_spread: float
    pe_bid_ask_spread: float
    ce_delta: float
    pe_delta: float
    ce_volume_anomaly: str  # NORMAL, HIGH, UNUSUAL
    pe_volume_anomaly: str
    ce_bid_qty: float
    pe_bid_qty: float
    ce_ask_qty: float
    pe_ask_qty: float


@dataclass
class PCRAnalysis:
    """Put-Call Ratio Analysis"""
    total_pcr: float  # Total Put OI / Total Call OI
    pcr_volume: float  # Volume-based PCR
    sentiment: str  # BULLISH, BEARISH, NEUTRAL
    strength: float  # -1 to +1 (negative = bullish, positive = bearish)
    interpretation: str


@dataclass
class OIAnalysis:
    """Open Interest Buildup Analysis"""
    atm_ce_oi: float
    atm_pe_oi: float
    resistance_zones: List[Tuple[float, float]]  # (strike, oi_value)
    support_zones: List[Tuple[float, float]]
    oi_skew: str  # CALL_HEAVY, PUT_HEAVY, BALANCED
    strength_ratio: float  # Put OI / Call OI at specific zones


@dataclass
class IVAnalysis:
    """IV Term Structure and Skew"""
    atm_iv: float
    iv_skew_direction: str  # BULLISH_SKEW, BEARISH_SKEW, NEUTRAL
    skew_magnitude: float  # Percentage difference
    iv_curve: List[Tuple[float, float]]  # (strike, iv)
    volatility_smile_present: bool
    near_term_iv: float  # Current expiry
    far_term_iv: float  # Next expiry (if available)
    term_structure_direction: str  # UPWARD, DOWNWARD, FLAT


@dataclass
class LiquidityAnalysis:
    """Bid-Ask Spread and Liquidity"""
    avg_ce_spread: float  # Average Call spread
    avg_pe_spread: float  # Average Put spread
    tight_liquidity_strikes: List[float]  # Good for execution
    poor_liquidity_strikes: List[float]  # Avoid
    atm_spread_pct: float  # Spread as % of price
    execution_quality: str  # EXCELLENT, GOOD, FAIR, POOR


@dataclass
class VolumeAnalysis:
    """Volume Spike Detection"""
    ce_volume_avg: float
    pe_volume_avg: float
    ce_spikes: List[Tuple[float, float]]  # (strike, volume_ratio)
    pe_spikes: List[Tuple[float, float]]
    unusual_activity_strikes: List[float]
    institutional_bias: str  # CALL_BUYING, PUT_BUYING, NEUTRAL
    smart_money_signal: str  # Direction indicator


@dataclass
class VannaVolgaAnalysis:
    """2nd Order Greeks Risk"""
    vanna_risk_level: str  # LOW, MEDIUM, HIGH
    volga_risk_level: str
    gamma_scalp_potential: float  # -1 to +1 (profit potential)
    iv_expansion_sensitivity: str  # POSITIVE, NEGATIVE
    delta_decay_risk: float  # Risk of delta changing with vol


@dataclass
class VolatilitySmile:
    """Volatility Smile Curve Analysis"""
    smile_present: bool
    smile_intensity: float  # 0-1
    smile_pattern: str  # SYMMETRIC, CALL_SKEW, PUT_SKEW
    otm_call_iv: float
    otm_put_iv: float
    atm_iv: float
    wings_richer: bool  # True if OTM options more expensive


@dataclass
class InstitutionalPositioning:
    """Large Order and Institutional Activity"""
    large_call_bids: float  # Total large bid qty for calls
    large_call_asks: float
    large_put_bids: float
    large_put_asks: float
    institutional_direction: str  # BULLISH, BEARISH, NEUTRAL
    conviction_level: float  # 0-1
    concentration_strike: float  # Strike with most institutional activity


@dataclass
class OptionsIntelligenceResult:
    """Complete options intelligence report"""
    strikes_analyzed: List[float]
    strike_details: Dict[float, StrikeAnalysis]
    pcr_analysis: PCRAnalysis
    oi_analysis: OIAnalysis
    iv_analysis: IVAnalysis
    liquidity_analysis: LiquidityAnalysis
    volume_analysis: VolumeAnalysis
    vanna_volga: VannaVolgaAnalysis
    volatility_smile: VolatilitySmile
    institutional: InstitutionalPositioning
    options_signal: str  # BUY_CALLS, BUY_PUTS, SELL_CALLS, SELL_PUTS, NEUTRAL
    signal_strength: float  # 0-1 confidence


class OptionsIntelligence:
    """Analyze option chain data from Dhan"""
    
    def __init__(self):
        self.large_order_threshold_qty = 100  # Qty for "large order"
        self.volume_spike_threshold = 1.5  # 1.5x average = spike
        
    def analyze(self, 
                option_chain: Dict,
                spot_price: float,
                atm_strike: float) -> OptionsIntelligenceResult:
        """
        Main analysis function
        
        Args:
            option_chain: Dict from Dhan with all strikes
            spot_price: Current LTP
            atm_strike: ATM strike (rounded)
        
        Returns:
            Complete options intelligence
        """
        
        # Get 4 above + 4 below ATM (9 strikes total)
        strikes = self._get_strike_range(atm_strike, 4)
        
        # Extract data for each strike
        strike_details = {}
        for strike in strikes:
            if strike in option_chain:
                strike_details[strike] = self._analyze_strike(
                    option_chain[strike],
                    strike,
                    spot_price
                )
        
        # Aggregate analyses
        pcr = self._calculate_pcr(strike_details)
        oi = self._analyze_oi(strike_details, spot_price)
        iv = self._analyze_iv_structure(strike_details, atm_strike)
        liquidity = self._analyze_liquidity(strike_details)
        volume = self._analyze_volume_spikes(strike_details)
        vanna_volga = self._analyze_vanna_volga(strike_details, spot_price)
        smile = self._analyze_volatility_smile(iv['iv_curve'])
        institutional = self._analyze_institutional(strike_details)
        
        # Generate signal
        signal, strength = self._generate_signal(
            pcr, oi, iv, volume, institutional
        )
        
        return OptionsIntelligenceResult(
            strikes_analyzed=strikes,
            strike_details=strike_details,
            pcr_analysis=pcr,
            oi_analysis=oi,
            iv_analysis=iv,
            liquidity_analysis=liquidity,
            volume_analysis=volume,
            vanna_volga=vanna_volga,
            volatility_smile=smile,
            institutional=institutional,
            options_signal=signal,
            signal_strength=strength
        )
    
    def _get_strike_range(self, atm_strike: float, count: int) -> List[float]:
        """Get strikes: ATM ± count"""
        strike_diff = 100  # NIFTY strikes are in 100s
        strikes = []
        for i in range(-count, count + 1):
            strikes.append(atm_strike + (i * strike_diff))
        return sorted(strikes)
    
    def _analyze_strike(self, strike_data: Dict, strike: float, spot: float) -> StrikeAnalysis:
        """Analyze single strike Call & Put"""
        
        ce = strike_data.get('CE')
        pe = strike_data.get('PE')
        
        # Extract data safely from OptionStrike dataclass or dict
        def safe_get(obj, attr, default=0):
            """Get attribute from dataclass or dict"""
            if obj is None:
                return default
            try:
                if hasattr(obj, attr):  # Dataclass
                    return float(getattr(obj, attr, default) or default)
                elif isinstance(obj, dict) and attr in obj:  # Dict
                    return float(obj[attr] or default)
            except (TypeError, ValueError, AttributeError):
                return default
            return default
        
        # Extract data
        ce_ltp = safe_get(ce, 'ltp', 0)
        pe_ltp = safe_get(pe, 'ltp', 0)
        ce_oi = safe_get(ce, 'oi', 0)
        pe_oi = safe_get(pe, 'oi', 0)
        ce_vol = safe_get(ce, 'volume', 0)
        pe_vol = safe_get(pe, 'volume', 0)
        ce_iv = safe_get(ce, 'iv', 0)
        pe_iv = safe_get(pe, 'iv', 0)
        
        # Bid-Ask spreads
        ce_bid = safe_get(ce, 'bid_price', 0)
        ce_ask = safe_get(ce, 'ask_price', 0)
        pe_bid = safe_get(pe, 'bid_price', 0)
        pe_ask = safe_get(pe, 'ask_price', 0)
        
        ce_spread = max(0, ce_ask - ce_bid) if ce_ask and ce_bid else 0
        pe_spread = max(0, pe_ask - pe_bid) if pe_ask and pe_bid else 0
        
        # Quantities
        ce_bid_qty = safe_get(ce, 'bid_qty', 0)
        ce_ask_qty = safe_get(ce, 'ask_qty', 0)
        pe_bid_qty = safe_get(pe, 'bid_qty', 0)
        pe_ask_qty = safe_get(pe, 'ask_qty', 0)
        
        # Greeks (from Dhan API)
        ce_delta = safe_get(ce, 'delta', 0)
        pe_delta = safe_get(pe, 'delta', 0)
        
        # Anomalies (placeholder - would be detected vs historical)
        ce_vol_anomaly = "NORMAL"
        pe_vol_anomaly = "NORMAL"
        
        return StrikeAnalysis(
            strike=strike,
            ce_ltp=ce_ltp,
            pe_ltp=pe_ltp,
            ce_oi=ce_oi,
            pe_oi=pe_oi,
            ce_volume=ce_vol,
            pe_volume=pe_vol,
            ce_iv=ce_iv,
            pe_iv=pe_iv,
            ce_bid_ask_spread=ce_spread,
            pe_bid_ask_spread=pe_spread,
            ce_delta=ce_delta,
            pe_delta=pe_delta,
            ce_volume_anomaly=ce_vol_anomaly,
            pe_volume_anomaly=pe_vol_anomaly,
            ce_bid_qty=ce_bid_qty,
            pe_bid_qty=pe_bid_qty,
            ce_ask_qty=ce_ask_qty,
            pe_ask_qty=pe_ask_qty
        )
    
    def _calculate_pcr(self, strikes: Dict[float, StrikeAnalysis]) -> PCRAnalysis:
        """Calculate Put-Call Ratio from OI"""
        
        total_ce_oi = sum(s.ce_oi for s in strikes.values())
        total_pe_oi = sum(s.pe_oi for s in strikes.values())
        
        # Total PCR
        total_pcr = total_pe_oi / total_ce_oi if total_ce_oi > 0 else 1.0
        
        # Volume-based PCR
        total_ce_vol = sum(s.ce_volume for s in strikes.values())
        total_pe_vol = sum(s.pe_volume for s in strikes.values())
        pcr_volume = total_pe_vol / total_ce_vol if total_ce_vol > 0 else 1.0
        
        # Sentiment
        if total_pcr > 1.2:
            sentiment = "BEARISH"
            strength = (total_pcr - 1.0) / 0.5  # Scale
        elif total_pcr < 0.8:
            sentiment = "BULLISH"
            strength = -(1.0 - total_pcr) / 0.5
        else:
            sentiment = "NEUTRAL"
            strength = 0.0
        
        strength = max(-1, min(1, strength))  # Clamp
        
        # Interpretation
        if total_pcr > 1.5:
            interp = f"Extreme put buying. Heavy hedging. PCR: {total_pcr:.2f}"
        elif total_pcr > 1.2:
            interp = f"High put interest. Protective positioning. PCR: {total_pcr:.2f}"
        elif total_pcr < 0.6:
            interp = f"Call dominance. Aggressive bullish bets. PCR: {total_pcr:.2f}"
        elif total_pcr < 0.8:
            interp = f"Higher call interest. Bullish bias. PCR: {total_pcr:.2f}"
        else:
            interp = f"Balanced put-call interest. PCR: {total_pcr:.2f}"
        
        return PCRAnalysis(
            total_pcr=total_pcr,
            pcr_volume=pcr_volume,
            sentiment=sentiment,
            strength=strength,
            interpretation=interp
        )
    
    def _analyze_oi(self, 
                    strikes: Dict[float, StrikeAnalysis],
                    spot: float) -> OIAnalysis:
        """Analyze OI distribution - support/resistance"""
        
        # Find ATM
        atm_strike = min(strikes.keys(), key=lambda x: abs(x - spot))
        atm_analysis = strikes[atm_strike]
        
        # Find resistance (Call OI buildup above price)
        resistance_zones = []
        for strike in sorted([s for s in strikes.keys() if s > spot]):
            if strikes[strike].ce_oi > 0:
                resistance_zones.append((strike, strikes[strike].ce_oi))
        
        # Find support (Put OI buildup below price)
        support_zones = []
        for strike in sorted([s for s in strikes.keys() if s < spot], reverse=True):
            if strikes[strike].pe_oi > 0:
                support_zones.append((strike, strikes[strike].pe_oi))
        
        # OI Skew
        total_ce_oi = sum(s.ce_oi for s in strikes.values())
        total_pe_oi = sum(s.pe_oi for s in strikes.values())
        
        if total_ce_oi > total_pe_oi * 1.1:
            oi_skew = "CALL_HEAVY"
        elif total_pe_oi > total_ce_oi * 1.1:
            oi_skew = "PUT_HEAVY"
        else:
            oi_skew = "BALANCED"
        
        strength_ratio = total_pe_oi / total_ce_oi if total_ce_oi > 0 else 1.0
        
        return OIAnalysis(
            atm_ce_oi=atm_analysis.ce_oi,
            atm_pe_oi=atm_analysis.pe_oi,
            resistance_zones=resistance_zones[:3],  # Top 3
            support_zones=support_zones[:3],
            oi_skew=oi_skew,
            strength_ratio=strength_ratio
        )
    
    def _analyze_iv_structure(self, 
                              strikes: Dict[float, StrikeAnalysis],
                              atm: float) -> Dict:
        """Analyze IV across strikes and term structure"""
        
        atm_analysis = strikes[atm]
        atm_iv = (atm_analysis.ce_iv + atm_analysis.pe_iv) / 2
        
        # Build IV curve
        iv_curve = []
        for strike in sorted(strikes.keys()):
            s = strikes[strike]
            avg_iv = (s.ce_iv + s.pe_iv) / 2 if (s.ce_iv + s.pe_iv) > 0 else atm_iv
            iv_curve.append((strike, avg_iv))
        
        # Detect skew
        otm_calls = [s for s in sorted(strikes.keys()) if s > atm]
        otm_puts = [s for s in sorted(strikes.keys()) if s < atm]
        
        otm_call_iv = (strikes[otm_calls[0]].ce_iv + strikes[otm_calls[-1]].ce_iv) / 2 if otm_calls else atm_iv
        otm_put_iv = (strikes[otm_puts[0]].pe_iv + strikes[otm_puts[-1]].pe_iv) / 2 if otm_puts else atm_iv
        
        skew_diff = otm_put_iv - otm_call_iv
        
        if skew_diff > 0.01:
            skew_direction = "BEARISH_SKEW"
        elif skew_diff < -0.01:
            skew_direction = "BULLISH_SKEW"
        else:
            skew_direction = "NEUTRAL"
        
        return {
            'atm_iv': atm_iv,
            'iv_skew_direction': skew_direction,
            'skew_magnitude': abs(skew_diff),
            'iv_curve': iv_curve,
            'otm_call_iv': otm_call_iv,
            'otm_put_iv': otm_put_iv,
            'near_term_iv': atm_iv,
            'term_structure_direction': 'FLAT'  # Would need multi-expiry data
        }
    
    def _analyze_liquidity(self, strikes: Dict[float, StrikeAnalysis]) -> LiquidityAnalysis:
        """Bid-Ask spread analysis"""
        
        ce_spreads = [s.ce_bid_ask_spread for s in strikes.values() if s.ce_bid_ask_spread > 0]
        pe_spreads = [s.pe_bid_ask_spread for s in strikes.values() if s.pe_bid_ask_spread > 0]
        
        avg_ce_spread = sum(ce_spreads) / len(ce_spreads) if ce_spreads else 0
        avg_pe_spread = sum(pe_spreads) / len(pe_spreads) if pe_spreads else 0
        
        # Tight vs poor
        tight = [s.strike for s in strikes.values() if s.ce_bid_ask_spread < avg_ce_spread]
        poor = [s.strike for s in strikes.values() if s.ce_bid_ask_spread > avg_ce_spread * 1.5]
        
        # Quality assessment
        avg_spread = (avg_ce_spread + avg_pe_spread) / 2
        if avg_spread < 1:
            quality = "EXCELLENT"
        elif avg_spread < 2:
            quality = "GOOD"
        elif avg_spread < 5:
            quality = "FAIR"
        else:
            quality = "POOR"
        
        return LiquidityAnalysis(
            avg_ce_spread=avg_ce_spread,
            avg_pe_spread=avg_pe_spread,
            tight_liquidity_strikes=tight,
            poor_liquidity_strikes=poor,
            atm_spread_pct=avg_spread,
            execution_quality=quality
        )
    
    def _analyze_volume_spikes(self, 
                               strikes: Dict[float, StrikeAnalysis]) -> VolumeAnalysis:
        """Detect unusual volume"""
        
        ce_vols = [s.ce_volume for s in strikes.values()]
        pe_vols = [s.pe_volume for s in strikes.values()]
        
        ce_avg = sum(ce_vols) / len(ce_vols) if ce_vols else 0
        pe_avg = sum(pe_vols) / len(pe_vols) if pe_vols else 0
        
        # Find spikes
        ce_spikes = [(s.strike, s.ce_volume / ce_avg) for s in strikes.values() 
                     if s.ce_volume > ce_avg * self.volume_spike_threshold and ce_avg > 0]
        pe_spikes = [(s.strike, s.pe_volume / pe_avg) for s in strikes.values() 
                     if s.pe_volume > pe_avg * self.volume_spike_threshold and pe_avg > 0]
        
        unusual = list(set([s[0] for s in ce_spikes + pe_spikes]))
        
        # Detect institutional buying
        large_call_qty = sum(s.ce_ask_qty for s in strikes.values() if s.ce_ask_qty > self.large_order_threshold_qty)
        large_put_qty = sum(s.pe_ask_qty for s in strikes.values() if s.pe_ask_qty > self.large_order_threshold_qty)
        
        if large_call_qty > large_put_qty * 1.2:
            inst_bias = "CALL_BUYING"
        elif large_put_qty > large_call_qty * 1.2:
            inst_bias = "PUT_BUYING"
        else:
            inst_bias = "NEUTRAL"
        
        return VolumeAnalysis(
            ce_volume_avg=ce_avg,
            pe_volume_avg=pe_avg,
            ce_spikes=ce_spikes,
            pe_spikes=pe_spikes,
            unusual_activity_strikes=unusual,
            institutional_bias=inst_bias,
            smart_money_signal=inst_bias
        )
    
    def _analyze_vanna_volga(self, 
                             strikes: Dict[float, StrikeAnalysis],
                             spot: float) -> VannaVolgaAnalysis:
        """2nd order Greek risks"""
        
        atm = min(strikes.keys(), key=lambda x: abs(x - spot))
        
        # Simplified: Check if gamma is high and vega is high
        # In real scenario, would compute actual Vanna and Volga
        
        # Gamma scalp potential: positive if ATM gamma is high
        avg_gamma = sum([abs(s.ce_delta - (s.ce_delta if s.strike < spot else 0.5)) 
                        for s in strikes.values()]) / len(strikes)
        
        scalp_potential = min(1.0, avg_gamma * 2)  # Rough estimate
        
        return VannaVolgaAnalysis(
            vanna_risk_level="MEDIUM",
            volga_risk_level="MEDIUM",
            gamma_scalp_potential=scalp_potential,
            iv_expansion_sensitivity="POSITIVE",
            delta_decay_risk=0.5
        )
    
    def _analyze_volatility_smile(self, iv_curve: List[Tuple[float, float]]) -> VolatilitySmile:
        """Detect volatility smile"""
        
        if not iv_curve or len(iv_curve) < 3:
            return VolatilitySmile(False, 0, "NEUTRAL", 0, 0, 0, False)
        
        # Simple smile detection: OTM options more expensive than ATM
        ivs = [iv for strike, iv in iv_curve]
        mid_idx = len(ivs) // 2
        
        atm_iv = ivs[mid_idx]
        wing_iv = (ivs[0] + ivs[-1]) / 2
        
        smile_intensity = max(0, (wing_iv - atm_iv) / atm_iv) if atm_iv > 0 else 0
        
        return VolatilitySmile(
            smile_present=smile_intensity > 0.02,
            smile_intensity=min(1.0, smile_intensity),
            smile_pattern="SYMMETRIC" if abs(ivs[0] - ivs[-1]) < 0.01 else "SKEWED",
            otm_call_iv=ivs[-1],
            otm_put_iv=ivs[0],
            atm_iv=atm_iv,
            wings_richer=wing_iv > atm_iv
        )
    
    def _analyze_institutional(self, 
                               strikes: Dict[float, StrikeAnalysis]) -> InstitutionalPositioning:
        """Detect institutional activity from large orders"""
        
        large_call_bids = sum(s.ce_bid_qty for s in strikes.values() 
                             if s.ce_bid_qty > self.large_order_threshold_qty)
        large_call_asks = sum(s.ce_ask_qty for s in strikes.values() 
                             if s.ce_ask_qty > self.large_order_threshold_qty)
        large_put_bids = sum(s.pe_bid_qty for s in strikes.values() 
                            if s.pe_bid_qty > self.large_order_threshold_qty)
        large_put_asks = sum(s.pe_ask_qty for s in strikes.values() 
                            if s.pe_ask_qty > self.large_order_threshold_qty)
        
        # Direction
        call_aggressiveness = large_call_asks  # Large asks = selling at market = bearish
        put_aggressiveness = large_put_bids   # Large bids = buying at market = bullish
        
        if call_aggressiveness > put_aggressiveness * 1.2:
            direction = "BEARISH"
        elif put_aggressiveness > call_aggressiveness * 1.2:
            direction = "BULLISH"
        else:
            direction = "NEUTRAL"
        
        total_activity = sum([large_call_bids, large_call_asks, large_put_bids, large_put_asks])
        conviction = min(1.0, total_activity / 10000)  # Normalize
        
        # Find concentration
        concentration = max(strikes.keys(), key=lambda s: strikes[s].ce_oi + strikes[s].pe_oi)
        
        return InstitutionalPositioning(
            large_call_bids=large_call_bids,
            large_call_asks=large_call_asks,
            large_put_bids=large_put_bids,
            large_put_asks=large_put_asks,
            institutional_direction=direction,
            conviction_level=conviction,
            concentration_strike=concentration
        )
    
    def _generate_signal(self, pcr, oi, iv, volume, institutional) -> Tuple[str, float]:
        """Generate final options trading signal"""
        
        score = 0.0
        
        # PCR signal
        if pcr.sentiment == "BULLISH":
            score += pcr.strength * 0.25
        else:
            score -= abs(pcr.strength) * 0.25
        
        # IV signal
        if iv['iv_skew_direction'] == "BULLISH_SKEW":
            score += 0.1
        elif iv['iv_skew_direction'] == "BEARISH_SKEW":
            score -= 0.1
        
        # Volume signal
        if volume.institutional_bias == "CALL_BUYING":
            score += 0.15
        elif volume.institutional_bias == "PUT_BUYING":
            score -= 0.15
        
        # Institutional signal
        if institutional.institutional_direction == "BULLISH":
            score += institutional.conviction_level * 0.2
        elif institutional.institutional_direction == "BEARISH":
            score -= institutional.conviction_level * 0.2
        
        # Clamp
        score = max(-1, min(1, score))
        strength = abs(score)
        
        if score > 0.3:
            signal = "BUY_CALLS"
        elif score < -0.3:
            signal = "BUY_PUTS"
        else:
            signal = "NEUTRAL"
        
        return signal, strength

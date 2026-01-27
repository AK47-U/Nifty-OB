"""
OPTIONS ANALYSIS MODULE
Calculates Greeks, IV, Skew, Max Pain
"""

import math
from dataclasses import dataclass
from datetime import datetime
from scipy.stats import norm


@dataclass
class OptionGreeks:
    """Option Greeks (Delta, Gamma, Theta, Vega, Rho)"""
    delta: float        # Price sensitivity (-1 to +1)
    gamma: float        # Delta sensitivity
    theta: float        # Time decay per day
    vega: float         # IV sensitivity
    rho: float          # Interest rate sensitivity
    iv: float           # Implied Volatility (%)


class BlackScholesCalculator:
    """Black-Scholes Options Greeks Calculator"""
    
    @staticmethod
    def d1(S, K, T, r, sigma):
        """Calculate d1 for Black-Scholes"""
        if T <= 0 or sigma <= 0:
            return 0
        return (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
    
    @staticmethod
    def d2(S, K, T, r, sigma):
        """Calculate d2 for Black-Scholes"""
        d1 = BlackScholesCalculator.d1(S, K, T, r, sigma)
        if T <= 0 or sigma <= 0:
            return 0
        return d1 - sigma * math.sqrt(T)
    
    @staticmethod
    def call_delta(S, K, T, r, sigma):
        """Call option delta"""
        if T <= 0:
            return 1.0 if S > K else 0.0
        return norm.cdf(BlackScholesCalculator.d1(S, K, T, r, sigma))
    
    @staticmethod
    def put_delta(S, K, T, r, sigma):
        """Put option delta"""
        return BlackScholesCalculator.call_delta(S, K, T, r, sigma) - 1
    
    @staticmethod
    def gamma(S, K, T, r, sigma):
        """Gamma for both calls and puts"""
        if T <= 0 or sigma <= 0:
            return 0
        d1 = BlackScholesCalculator.d1(S, K, T, r, sigma)
        return norm.pdf(d1) / (S * sigma * math.sqrt(T))
    
    @staticmethod
    def call_theta(S, K, T, r, sigma):
        """Call option theta (per day)"""
        if T <= 0 or sigma <= 0:
            return 0
        d1 = BlackScholesCalculator.d1(S, K, T, r, sigma)
        d2 = BlackScholesCalculator.d2(S, K, T, r, sigma)
        
        term1 = -(S * norm.pdf(d1) * sigma) / (2 * math.sqrt(T))
        term2 = -r * K * math.exp(-r * T) * norm.cdf(d2)
        
        return (term1 + term2) / 365
    
    @staticmethod
    def put_theta(S, K, T, r, sigma):
        """Put option theta (per day)"""
        if T <= 0 or sigma <= 0:
            return 0
        d1 = BlackScholesCalculator.d1(S, K, T, r, sigma)
        d2 = BlackScholesCalculator.d2(S, K, T, r, sigma)
        
        term1 = -(S * norm.pdf(d1) * sigma) / (2 * math.sqrt(T))
        term2 = r * K * math.exp(-r * T) * norm.cdf(-d2)
        
        return (term1 + term2) / 365
    
    @staticmethod
    def vega(S, K, T, r, sigma):
        """Vega (per 1% change in IV)"""
        if T <= 0 or sigma <= 0:
            return 0
        d1 = BlackScholesCalculator.d1(S, K, T, r, sigma)
        return S * norm.pdf(d1) * math.sqrt(T) / 100


class OptionAnalyzer:
    """Analyze options data for trading signals"""
    
    def __init__(self, spot_price: float, rate: float = 0.06):
        self.spot = spot_price
        self.rate = rate
    
    def calculate_greeks(self, 
                        strike: float, 
                        days_to_expiry: int, 
                        iv: float,
                        option_type: str = "CALL") -> OptionGreeks:
        """
        Calculate Greeks for an option
        
        Args:
            strike: Strike price
            days_to_expiry: Days until expiration
            iv: Implied Volatility (as decimal, e.g., 0.25 for 25%)
            option_type: "CALL" or "PUT"
        """
        T = days_to_expiry / 365
        
        if option_type.upper() == "CALL":
            delta = BlackScholesCalculator.call_delta(self.spot, strike, T, self.rate, iv)
            theta = BlackScholesCalculator.call_theta(self.spot, strike, T, self.rate, iv)
        else:  # PUT
            delta = BlackScholesCalculator.put_delta(self.spot, strike, T, self.rate, iv)
            theta = BlackScholesCalculator.put_theta(self.spot, strike, T, self.rate, iv)
        
        gamma = BlackScholesCalculator.gamma(self.spot, strike, T, self.rate, iv)
        vega = BlackScholesCalculator.vega(self.spot, strike, T, self.rate, iv)
        rho = 0  # Simplified
        
        return OptionGreeks(
            delta=delta,
            gamma=gamma,
            theta=theta,
            vega=vega,
            rho=rho,
            iv=iv * 100  # Convert to percentage
        )
    
    def calculate_max_pain(self, 
                          call_oi_by_strike: dict, 
                          put_oi_by_strike: dict) -> float:
        """
        Calculate Max Pain level (strike where max traders lose money at expiry)
        
        Args:
            call_oi_by_strike: {strike: oi_count}
            put_oi_by_strike: {strike: oi_count}
        
        Returns:
            Max pain strike price
        """
        if not call_oi_by_strike or not put_oi_by_strike:
            return self.spot
        
        all_strikes = set(list(call_oi_by_strike.keys()) + list(put_oi_by_strike.keys()))
        max_pain_strike = self.spot
        min_pain = float('inf')
        
        for strike in all_strikes:
            call_oi = call_oi_by_strike.get(strike, 0)
            put_oi = put_oi_by_strike.get(strike, 0)
            
            call_loss = abs(self.spot - strike) * call_oi
            put_loss = abs(strike - self.spot) * put_oi
            total_pain = call_loss + put_loss
            
            if total_pain < min_pain:
                min_pain = total_pain
                max_pain_strike = strike
        
        return max_pain_strike
    
    def analyze_skew(self, 
                    atm_iv: float, 
                    otm_call_iv: float, 
                    otm_put_iv: float) -> dict:
        """
        Analyze volatility skew (put skew = direction bias)
        
        Returns:
            {
                'put_call_skew': float,  # Put IV - Call IV (positive = bearish)
                'call_skew': float,       # OTM Call IV - ATM IV
                'put_skew': float,        # OTM Put IV - ATM IV
                'direction_bias': str     # BULLISH, BEARISH, NEUTRAL
            }
        """
        put_call_skew = otm_put_iv - otm_call_iv
        call_skew = otm_call_iv - atm_iv
        put_skew = otm_put_iv - atm_iv
        
        if put_call_skew > 0.02:  # 2% threshold
            direction = "BEARISH"
        elif put_call_skew < -0.02:
            direction = "BULLISH"
        else:
            direction = "NEUTRAL"
        
        return {
            'put_call_skew': put_call_skew * 100,  # Convert to percentage
            'call_skew': call_skew * 100,
            'put_skew': put_skew * 100,
            'direction_bias': direction
        }
    
    def analyze_iv_levels(self, 
                         current_iv: float, 
                         iv_high_52w: float, 
                         iv_low_52w: float) -> dict:
        """
        Analyze IV rank and percentile
        
        Returns:
            {
                'iv_rank': float,        # 0-100 (% between 52w low and high)
                'iv_percentile': float,  # Position in IV range
                'iv_status': str         # LOW, MEDIUM, HIGH, EXTREME
            }
        """
        if iv_high_52w == iv_low_52w:
            iv_rank = 50
        else:
            iv_rank = ((current_iv - iv_low_52w) / (iv_high_52w - iv_low_52w)) * 100
        
        iv_rank = max(0, min(100, iv_rank))  # Clamp 0-100
        
        if iv_rank < 25:
            status = "LOW"
        elif iv_rank < 50:
            status = "MEDIUM_LOW"
        elif iv_rank < 75:
            status = "MEDIUM_HIGH"
        else:
            status = "HIGH"
        
        return {
            'iv_rank': iv_rank,
            'iv_percentile': iv_rank,
            'iv_status': status,
            'current_iv': current_iv * 100,
            '52w_high': iv_high_52w * 100,
            '52w_low': iv_low_52w * 100
        }

"""
Multi-Timeframe Trend Analyzer
Consensus-based trend classification across 5m, 30m, 15m, 60m, and daily timeframes.
Weighs longer timeframes more heavily when shorter TFs show mixed signals.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Dict, Tuple
import pandas as pd
from loguru import logger


class TrendType(Enum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    RANGE_BOUND = "RANGE_BOUND"


@dataclass
class EMATrendSignal:
    """EMA alignment signal for a single timeframe"""
    tf_name: str
    alignment: str  # BULLISH, BEARISH, MIXED
    strength: float  # 0-1: how many EMAs are aligned
    price: float
    ema5: float
    ema20: float
    ema50: float
    ema100: float
    ema200: float


@dataclass
class MomentumSignal:
    """Momentum signal for a single timeframe"""
    rsi: float
    macd_histogram: float
    macd_direction: str  # RISING, FALLING, FLAT


@dataclass
class TimeframeAnalysis:
    """Complete analysis for a single timeframe"""
    tf_name: str
    ema_signal: EMATrendSignal
    momentum: MomentumSignal
    trend_score: float  # -1 to +1: -1=bearish, 0=range, +1=bullish
    confidence: float  # 0-1: how strong is the signal


@dataclass
class MTFConsensusResult:
    """Multi-timeframe consensus output"""
    trend: TrendType
    consensus_score: float  # -1 to +1
    confidence: float  # 0-1
    primary_driver_tf: str  # which timeframe is driving the consensus
    analysis_by_tf: Dict[str, TimeframeAnalysis]
    guidance: str  # plain-English summary


class MTFTrendAnalyzer:
    """Analyzes trends across multiple timeframes and produces consensus"""

    def __init__(self):
        self.logger = logger

    def resample_to_30m(self, df5m: pd.DataFrame) -> pd.DataFrame:
        """Resample 5m candles to 30m OHLCV"""
        if df5m.empty:
            return pd.DataFrame()
        
        # Ensure datetime index
        if not isinstance(df5m.index, pd.DatetimeIndex):
            if 'timestamp' in df5m.columns:
                df5m = df5m.copy()
                df5m['timestamp'] = pd.to_datetime(df5m['timestamp'])
                df5m.set_index('timestamp', inplace=True)
            else:
                return pd.DataFrame()

        # Resample to 30m
        agg_dict = {
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum'
        }
        df30m = df5m.resample('30min').agg(agg_dict).dropna()
        return df30m

    def analyze_ema_alignment(self, df: pd.DataFrame, price: float) -> EMATrendSignal:
        """Analyze EMA alignment on a dataframe"""
        ema5 = float(df['ema_5'].iloc[-1]) if 'ema_5' in df else price
        ema20 = float(df['ema_20'].iloc[-1]) if 'ema_20' in df else price
        ema50 = float(df['ema_50'].iloc[-1]) if 'ema_50' in df else price
        ema100 = float(df['ema_100'].iloc[-1]) if 'ema_100' in df else price
        ema200 = float(df['ema_200'].iloc[-1]) if 'ema_200' in df else price

        # Count bullish alignment (5>12>20>50>100>200)
        bullish_count = sum([
            ema5 > (float(df['ema_12'].iloc[-1]) if 'ema_12' in df else ema5),
            float(df['ema_12'].iloc[-1]) if 'ema_12' in df else ema5 > ema20,
            ema20 > ema50,
            ema50 > ema100,
            ema100 > ema200
        ])

        # Count bearish alignment (5<12<20<50<100<200)
        bearish_count = sum([
            ema5 < (float(df['ema_12'].iloc[-1]) if 'ema_12' in df else ema5),
            float(df['ema_12'].iloc[-1]) if 'ema_12' in df else ema5 < ema20,
            ema20 < ema50,
            ema50 < ema100,
            ema100 < ema200
        ])

        if bullish_count >= 4:
            alignment = "BULLISH"
            strength = bullish_count / 5
        elif bearish_count >= 4:
            alignment = "BEARISH"
            strength = bearish_count / 5
        else:
            alignment = "MIXED"
            strength = max(bullish_count, bearish_count) / 5

        return EMATrendSignal(
            tf_name="temp",
            alignment=alignment,
            strength=strength,
            price=price,
            ema5=ema5,
            ema20=ema20,
            ema50=ema50,
            ema100=ema100,
            ema200=ema200
        )

    def analyze_momentum(self, df: pd.DataFrame) -> MomentumSignal:
        """Analyze momentum signals (RSI, MACD)"""
        rsi = float(df['rsi'].iloc[-1]) if 'rsi' in df else 50.0
        macd_hist = float(df['hist'].iloc[-1]) if 'hist' in df else 0.0

        if macd_hist > 0:
            macd_direction = "RISING"
        elif macd_hist < 0:
            macd_direction = "FALLING"
        else:
            macd_direction = "FLAT"

        return MomentumSignal(
            rsi=rsi,
            macd_histogram=macd_hist,
            macd_direction=macd_direction
        )

    def calculate_trend_score(self, ema_signal: EMATrendSignal, momentum: MomentumSignal) -> Tuple[float, float]:
        """
        Calculate trend score (-1 to +1) and confidence (0 to 1).
        
        Returns:
            (trend_score, confidence)
        """
        ema_score = 0.0
        if ema_signal.alignment == "BULLISH":
            ema_score = ema_signal.strength
        elif ema_signal.alignment == "BEARISH":
            ema_score = -ema_signal.strength
        # MIXED = 0

        momentum_score = 0.0
        rsi_score = (momentum.rsi - 50) / 50  # Normalize RSI to -1 to +1
        momentum_score += rsi_score * 0.5

        if momentum.macd_direction == "RISING":
            momentum_score += 0.5
        elif momentum.macd_direction == "FALLING":
            momentum_score -= 0.5

        momentum_score = max(-1, min(1, momentum_score))

        # Weighted combination
        trend_score = ema_score * 0.6 + momentum_score * 0.4
        trend_score = max(-1, min(1, trend_score))

        # Confidence: higher when EMA and momentum agree
        ema_bullish = ema_signal.alignment == "BULLISH"
        momentum_bullish = momentum_score > 0.2
        aligned = (ema_bullish and momentum_bullish) or (not ema_bullish and not momentum_bullish)
        confidence = ema_signal.strength if aligned else ema_signal.strength * 0.6

        return trend_score, confidence

    def analyze_timeframe(self, df: pd.DataFrame, tf_name: str) -> TimeframeAnalysis:
        """Analyze a single timeframe"""
        if df.empty:
            return TimeframeAnalysis(
                tf_name=tf_name,
                ema_signal=EMATrendSignal(tf_name, "MIXED", 0, 0, 0, 0, 0, 0, 0),
                momentum=MomentumSignal(50, 0, "FLAT"),
                trend_score=0,
                confidence=0
            )

        price = float(df['close'].iloc[-1])
        ema_signal = self.analyze_ema_alignment(df, price)
        ema_signal.tf_name = tf_name
        momentum = self.analyze_momentum(df)
        trend_score, confidence = self.calculate_trend_score(ema_signal, momentum)

        return TimeframeAnalysis(
            tf_name=tf_name,
            ema_signal=ema_signal,
            momentum=momentum,
            trend_score=trend_score,
            confidence=confidence
        )

    def compute_consensus(
        self,
        analysis_5m: TimeframeAnalysis,
        analysis_30m: TimeframeAnalysis,
        analysis_15m: TimeframeAnalysis,
        analysis_60m: TimeframeAnalysis,
        analysis_daily: TimeframeAnalysis
    ) -> MTFConsensusResult:
        """
        Compute MTF consensus with intelligent weighting.
        
        Rules:
        - When 5m and 15m show mixed signals, weight 60m and daily more heavily.
        - Longer timeframes always have a base weight.
        - Confidence indicates agreement across timeframes.
        """
        analyses = {
            "5m": analysis_5m,
            "30m": analysis_30m,
            "15m": analysis_15m,
            "60m": analysis_60m,
            "daily": analysis_daily
        }

        # Detect if short-term (5m/15m) are mixed
        short_tf_mixed = (
            analysis_5m.ema_signal.alignment == "MIXED" or
            analysis_15m.ema_signal.alignment == "MIXED"
        )

        # Base weights (always favor longer TFs)
        weights = {
            "5m": 0.10,
            "30m": 0.15,
            "15m": 0.15,
            "60m": 0.30,
            "daily": 0.30
        }

        # If short-term are mixed, reduce their weight and boost long-term
        if short_tf_mixed:
            weights["5m"] *= 0.5
            weights["15m"] *= 0.7
            weights["30m"] *= 0.8
            weights["60m"] *= 1.5
            weights["daily"] *= 1.3

        # Normalize weights
        total_weight = sum(weights.values())
        weights = {k: v / total_weight for k, v in weights.items()}

        # Compute weighted consensus score
        consensus_score = sum(
            analyses[tf].trend_score * weights[tf]
            for tf in analyses.keys()
        )
        consensus_score = max(-1, min(1, consensus_score))

        # Determine trend
        if consensus_score > 0.3:
            trend = TrendType.BULLISH
        elif consensus_score < -0.3:
            trend = TrendType.BEARISH
        else:
            trend = TrendType.RANGE_BOUND

        # Find primary driver (highest confidence * weight)
        driver_scores = {
            tf: analyses[tf].confidence * weights[tf]
            for tf in analyses.keys()
        }
        primary_driver = max(driver_scores, key=driver_scores.get)

        # Compute overall confidence (weighted average, clipped 0-1)
        conf_list = [analyses[tf].confidence for tf in analyses.keys()]
        weighted_conf = sum(
            analyses[tf].confidence * weights[tf]
            for tf in analyses.keys()
        )
        overall_confidence = max(0, min(1, weighted_conf))

        # Guidance text
        if short_tf_mixed:
            guidance = (
                f"Short-term mixed (5m/15m) → Consensus weighted to 60m/daily. "
                f"Trend: {trend.value} (primary: {primary_driver}). "
                f"Watch for intraday volatility."
            )
        else:
            alignment_5m = analysis_5m.ema_signal.alignment
            guidance = (
                f"Short-term aligned ({alignment_5m}) across timeframes. "
                f"Trend: {trend.value}. Confidence: {overall_confidence:.0%}."
            )

        return MTFConsensusResult(
            trend=trend,
            consensus_score=consensus_score,
            confidence=overall_confidence,
            primary_driver_tf=primary_driver,
            analysis_by_tf=analyses,
            guidance=guidance
        )

    def compute_consensus_intraday(
        self,
        analysis_5m: TimeframeAnalysis,
        analysis_30m: TimeframeAnalysis,
        analysis_15m: TimeframeAnalysis
    ) -> MTFConsensusResult:
        """
        Compute consensus from intraday timeframes only (5m, 30m, 15m).
        Uses different weights than full MTF - emphasizes 15m and 30m for intraday structure.
        """
        analyses = {
            "5m": analysis_5m,
            "30m": analysis_30m,
            "15m": analysis_15m
        }

        # Detect if short-term (5m) is mixed
        short_tf_mixed = analysis_5m.ema_signal.alignment == "MIXED"

        # Base weights for intraday: 30m is the primary structure, 15m confirms, 5m is entry signal
        weights = {
            "5m": 0.20,
            "30m": 0.50,
            "15m": 0.30
        }

        # If 5m is mixed, reduce its weight
        if short_tf_mixed:
            weights["5m"] *= 0.5
            weights["30m"] *= 1.2
            weights["15m"] *= 1.1

        # Normalize weights
        total_weight = sum(weights.values())
        weights = {k: v / total_weight for k, v in weights.items()}

        # Compute weighted consensus score
        consensus_score = sum(
            analyses[tf].trend_score * weights[tf]
            for tf in analyses.keys()
        )
        consensus_score = max(-1, min(1, consensus_score))

        # Determine trend
        if consensus_score > 0.3:
            trend = TrendType.BULLISH
        elif consensus_score < -0.3:
            trend = TrendType.BEARISH
        else:
            trend = TrendType.RANGE_BOUND

        # Find primary driver (highest confidence * weight)
        driver_scores = {
            tf: analyses[tf].confidence * weights[tf]
            for tf in analyses.keys()
        }
        primary_driver = max(driver_scores, key=driver_scores.get)

        # Compute overall confidence (weighted average)
        weighted_conf = sum(
            analyses[tf].confidence * weights[tf]
            for tf in analyses.keys()
        )
        overall_confidence = max(0, min(1, weighted_conf))

        # Guidance text
        guidance = (
            f"Intraday analysis (5m/15m/30m): {trend.value}. "
            f"Primary driver: {primary_driver}. Confidence: {overall_confidence:.0%}."
        )

        return MTFConsensusResult(
            trend=trend,
            consensus_score=consensus_score,
            confidence=overall_confidence,
            primary_driver_tf=primary_driver,
            analysis_by_tf=analyses,
            guidance=guidance
        )

    def analyze_all(
        self,
        df5m: pd.DataFrame,
        df15m: pd.DataFrame,
        df60m: pd.DataFrame,
        dfd: pd.DataFrame,
        ti  # TechnicalIndicators instance
    ) -> MTFConsensusResult:
        """
        Convenience method: resample 30m, compute indicators, analyze all TFs, return consensus.
        """
        # Resample 30m
        df30m = self.resample_to_30m(df5m)
        
        # Compute indicators if missing
        for df_name, df in [("5m", df5m), ("30m", df30m), ("15m", df15m), ("60m", df60m), ("daily", dfd)]:
            if df.empty:
                continue
            for p in [5, 12, 20, 50, 100, 200]:
                if f'ema_{p}' not in df.columns:
                    df[f'ema_{p}'] = ti.calculate_ema(df['close'], p)
            if 'rsi' not in df.columns:
                df['rsi'] = ti.calculate_rsi(df['close'], 14)
            if 'hist' not in df.columns:
                macd_result = ti.calculate_macd(df['close'], 12, 26, 9)
                df['hist'] = macd_result['Histogram']

        # Analyze each timeframe
        a5 = self.analyze_timeframe(df5m, "5m")
        a30 = self.analyze_timeframe(df30m, "30m")
        a15 = self.analyze_timeframe(df15m, "15m")
        a60 = self.analyze_timeframe(df60m, "60m")
        ad = self.analyze_timeframe(dfd, "daily")

        # Compute consensus
        return self.compute_consensus(a5, a30, a15, a60, ad)
    def analyze_intraday(
        self,
        df5m: pd.DataFrame,
        df30m: pd.DataFrame,
        df15m: pd.DataFrame,
        ti  # TechnicalIndicators instance
    ) -> MTFConsensusResult:
        """
        Intraday-only analysis: uses 5m, 30m, 15m timeframes (skip 60m/daily).
        Better for scalping - focuses on immediate market structure.
        """
        # Compute indicators if missing
        for df_name, df in [("5m", df5m), ("30m", df30m), ("15m", df15m)]:
            if df.empty:
                continue
            for p in [5, 12, 20, 50, 100, 200]:
                if f'ema_{p}' not in df.columns:
                    df[f'ema_{p}'] = ti.calculate_ema(df['close'], p)
            if 'rsi' not in df.columns:
                df['rsi'] = ti.calculate_rsi(df['close'], 14)
            if 'hist' not in df.columns:
                macd_result = ti.calculate_macd(df['close'], 12, 26, 9)
                df['hist'] = macd_result['Histogram']

        # Analyze each timeframe
        a5 = self.analyze_timeframe(df5m, "5m")
        a30 = self.analyze_timeframe(df30m, "30m")
        a15 = self.analyze_timeframe(df15m, "15m")

        # Compute consensus from intraday timeframes only
        return self.compute_consensus_intraday(a5, a30, a15)
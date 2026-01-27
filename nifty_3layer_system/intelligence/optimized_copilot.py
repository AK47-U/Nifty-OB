"""
UPDATED COPILOT FORMATTER WITH OPTIMIZED RISK MANAGEMENT
Integrates PositionSizer for realistic entry, SL, targets based on confluence
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from intelligence.copilot_formatter import CopilotFormatter
from risk_management import PositionSizer, RiskProfile
from intelligence.scenario_classifier import ScenarioOutput
from intelligence.confluence_scorer import ConfluenceScore
from intelligence.confidence_calculator import ConfidenceOutput


class OptimizedCopilotFormatter(CopilotFormatter):
    """
    Enhanced CopilotFormatter that integrates PositionSizer
    for confluence-based risk optimization
    """
    
    def __init__(self):
        super().__init__()
        self.position_sizer = PositionSizer(capital=15000, risk_pct_per_trade=1.0)
    
    def format_sniper_output_optimized(
        self,
        confidence: ConfidenceOutput,
        scenario: ScenarioOutput,
        confluence: ConfluenceScore,
        
        # Market data
        ltp: float,
        pdh: float,
        pdl: float,
        cpr_pivot: float,
        r1: float,
        r2: float,
        s1: float,
        s2: float,
        
        # Options
        atm_strike: float,
        atm_delta: float,
        atm_ce_ltp: float,
        atm_pe_ltp: float,
        atm_iv: float,
        
        # ATR for volatility context
        atr: float,
        
        # Capital
        capital: float = 15000,
        risk_pct: float = 1.0
    ) -> str:
        """
        Format with optimized risk management based on confluence
        """
        
        # Get optimized position based on confluence score
        risk_profile = self.position_sizer.calculate_position(
            confluence_score=confluence.overall_score,
            entry_price=atm_ce_ltp if confidence.trade_decision == "BUY" else atm_pe_ltp,
            atm_ltp=ltp,
            atr=atr,
            trend_bias=scenario.market_bias
        )
        
        # Build output based on confidence level
        if confidence.confidence_level == "SNIPER":
            return self._format_sniper_optimized(
                confidence=confidence,
                scenario=scenario,
                confluence=confluence,
                ltp=ltp, pdh=pdh, pdl=pdl, cpr_pivot=cpr_pivot,
                r1=r1, r2=r2, s1=s1, s2=s2,
                atm_strike=atm_strike,
                atm_delta=atm_delta,
                atm_ce_ltp=atm_ce_ltp,
                atm_pe_ltp=atm_pe_ltp,
                atm_iv=atm_iv,
                risk_profile=risk_profile
            )
        elif confidence.confidence_level == "CAUTIONARY":
            return self._format_cautionary_optimized(
                confidence=confidence,
                scenario=scenario,
                confluence=confluence,
                ltp=ltp, pdh=pdh, pdl=pdl, cpr_pivot=cpr_pivot,
                s1=s1, s2=s2,
                atm_strike=atm_strike,
                atm_ce_ltp=atm_ce_ltp,
                atm_pe_ltp=atm_pe_ltp,
                risk_profile=risk_profile
            )
        else:
            return self._format_wait_optimized(confluence=confluence)
    
    def _format_sniper_optimized(
        self,
        confidence: ConfidenceOutput,
        scenario: ScenarioOutput,
        confluence: ConfluenceScore,
        ltp: float, pdh: float, pdl: float, cpr_pivot: float,
        r1: float, r2: float, s1: float, s2: float,
        atm_strike: float,
        atm_delta: float,
        atm_ce_ltp: float,
        atm_pe_ltp: float,
        atm_iv: float,
        risk_profile: RiskProfile
    ) -> str:
        """Format SNIPER recommendation with optimized risk"""
        
        lines = []
        lines.append("\n" + "="*80)
        lines.append(f"SNIPER: {scenario.market_bias} [Confidence: {confidence.confidence_score:.1f}/10]")
        lines.append("="*80)
        
        lines.append(f"\nWHY ARE YOU TAKING THIS TRADE?")
        lines.append("-"*80)
        lines.append(f"Scenario: {scenario.scenario.value} ({scenario.market_bias})")
        lines.append(f"  → {scenario.primary_trigger}")
        lines.append(f"\nConfluence Score: {confluence.overall_score:.1f}/10 ({confluence.quality_description})")
        lines.append(f"  → {', '.join(list(confluence.score_breakdown.keys())[:3])}... all aligned")
        lines.append(f"\nConviction: {confidence.confidence_score:.1f}/10")
        if confidence.confidence_score >= 8.5:
            lines.append(f"  → MAXIMUM CONVICTION - All technical & institutional signals aligned")
        elif confidence.confidence_score >= 8:
            lines.append(f"  → HIGH CONVICTION - Strong setup with multiple confluences")
        
        lines.append(f"\nWHEN SHOULD YOU ENTER?")
        lines.append("-"*80)
        lines.append(f"Entry Zone: Rs.{risk_profile.entry:.2f}")
        lines.append(f"Trigger: {scenario.primary_trigger}")
        if scenario.market_bias == "BULLISH":
            lines.append(f"  → Entry on {s1:.2f} support or at market")
        else:
            lines.append(f"  → Entry on {r1:.2f} resistance or at market")
        
        lines.append(f"\nTHE LEVELS (Your Trading Grid)")
        lines.append("-"*80)
        lines.append(f"Current LTP:      Rs.{ltp:.2f}")
        if scenario.market_bias == "BULLISH":
            lines.append(f"Upside Target:    Rs.{pdh:.2f} (PDH)")
            lines.append(f"Intermediate:     Rs.{r1:.2f} (R1)")
        else:
            lines.append(f"Downside Target:  Rs.{pdl:.2f} (PDL)")
            lines.append(f"Intermediate:     Rs.{s1:.2f} (S1)")
        lines.append(f"Pivot:            Rs.{cpr_pivot:.2f} (CPR Pivot)")
        
        lines.append(f"\nEXECUTION PLAN (Optimized for {confluence.overall_score:.1f}/10 confluence)")
        lines.append("-"*80)
        
        side = "CALL" if scenario.market_bias == "BULLISH" else "PUT"
        lines.append(f"Strike:           {atm_strike:.0f} {side}")
        lines.append(f"Entry Price:      Rs.{risk_profile.entry:.2f}")
        lines.append(f"Stop Loss:        Rs.{risk_profile.stop_loss:.2f} ({risk_profile.risk_points:.1f} point risk)")
        
        lines.append(f"\nTARGET PROFIT LEVELS")
        lines.append(f"Target 1:         Rs.{risk_profile.target_1:.2f} (Exit 70% | +{risk_profile.reward_1_points:.1f} pts)")
        lines.append(f"  RR Ratio:       1:{risk_profile.rr_ratio_1:.2f}")
        lines.append(f"  Profit on 70%:  Rs.{risk_profile.max_profit_1 * 0.7:.0f}")
        
        lines.append(f"\nTarget 2:         Rs.{risk_profile.target_2:.2f} (Trail 30% | +{risk_profile.reward_2_points:.1f} pts)")
        lines.append(f"  RR Ratio:       1:{risk_profile.rr_ratio_2:.2f}")
        lines.append(f"  Profit on 30%:  Rs.{risk_profile.max_profit_2 * 0.3:.0f}")
        
        lines.append(f"\nPOSITION SIZING")
        lines.append("-"*80)
        lines.append(f"Quantity:         {risk_profile.quantity} lot(s)")
        lines.append(f"Position Value:   Rs.{risk_profile.position_value:.0f}")
        lines.append(f"Risk Capital:     Rs.{risk_profile.risk_capital:.0f} ({risk_profile.risk_pct:.2f}% of capital)")
        
        lines.append(f"\nPROFIT / LOSS POTENTIAL")
        lines.append("-"*80)
        lines.append(f"Max Profit T1:    Rs.{risk_profile.max_profit_1:.0f}")
        lines.append(f"Max Profit T2:    Rs.{risk_profile.max_profit_2:.0f}")
        lines.append(f"Max Loss (SL):    Rs.{risk_profile.risk_capital:.0f}")
        
        lines.append(f"\nALERTS & RISK MANAGEMENT")
        lines.append("-"*80)
        if confidence.confidence_score >= 8.5:
            lines.append(f"✓ Very Strong Setup - Confidence to hold Target 2")
            lines.append(f"⚠ BUT: Exit 70% at Target 1 to secure profits")
        elif confidence.confidence_score >= 8:
            lines.append(f"✓ Strong Setup - Good risk/reward")
            lines.append(f"⚠ Watch for exhaustion near Target 1")
        
        lines.append(f"⚠ Hard SL @ Rs.{risk_profile.stop_loss:.2f} - No trailing below this")
        
        lines.append(f"\nRECOMMENDATION")
        lines.append("-"*80)
        if risk_profile.rr_ratio_1 >= 2:
            lines.append(f"EXECUTE NOW | Excellent Risk/Reward | {scenario.market_bias} Momentum Trade")
        elif risk_profile.rr_ratio_1 >= 1:
            lines.append(f"EXECUTE | Good Risk/Reward | Full Position")
        else:
            lines.append(f"EXECUTE CAUTIOUSLY | Fair Risk/Reward | Consider 50% Position")
        
        lines.append("="*80 + "\n")
        
        return "\n".join(lines)
    
    def _format_cautionary_optimized(
        self,
        confidence: ConfidenceOutput,
        scenario: ScenarioOutput,
        confluence: ConfluenceScore,
        ltp: float, pdh: float, pdl: float, cpr_pivot: float,
        s1: float, s2: float,
        atm_strike: float,
        atm_ce_ltp: float,
        atm_pe_ltp: float,
        risk_profile: RiskProfile
    ) -> str:
        """Format CAUTIONARY recommendation"""
        
        lines = []
        lines.append("\n" + "="*80)
        lines.append(f"CAUTIONARY: {scenario.market_bias} SCALP [Confidence: {confidence.confidence_score:.1f}/10]")
        lines.append("="*80)
        
        lines.append(f"\nSETUP ANALYSIS")
        lines.append("-"*80)
        lines.append(f"Scenario: {scenario.scenario.value}")
        lines.append(f"Confluence: {confluence.overall_score:.1f}/10 ({confluence.quality_description})")
        lines.append(f"\nRISK LEVEL: MEDIUM - Not recommended for beginners")
        
        lines.append(f"\nEXECUTION (SCALP ONLY)")
        lines.append("-"*80)
        side = "CALL" if scenario.market_bias == "BULLISH" else "PUT"
        lines.append(f"Strike:       {atm_strike:.0f} {side}")
        lines.append(f"Entry:        Rs.{risk_profile.entry:.2f}")
        lines.append(f"Target:       Rs.{risk_profile.target_1:.2f} ({risk_profile.reward_1_points:.1f} pt profit)")
        lines.append(f"Stop Loss:    Rs.{risk_profile.stop_loss:.2f} (Tight - {risk_profile.risk_points:.1f} pt risk)")
        
        lines.append(f"\nHOLDING PERIOD")
        lines.append("-"*80)
        lines.append(f"Max Hold: <30 mins | Scalp only")
        lines.append(f"Exit By: 15:20 (before market close)")
        lines.append(f"No Target 2 - Exit at Target 1 or SL")
        
        lines.append(f"\nPOSITION")
        lines.append("-"*80)
        lines.append(f"Quantity: {risk_profile.quantity} lot(s)")
        lines.append(f"Max Profit: Rs.{risk_profile.max_profit_1:.0f}")
        lines.append(f"Max Loss: Rs.{risk_profile.risk_capital:.0f}")
        
        lines.append(f"\nRECOMMENDATION")
        lines.append("-"*80)
        lines.append(f"CAUTIOUS ENTRY | Scalp Only | Exit at Target or SL - No Trailing")
        
        lines.append("="*80 + "\n")
        
        return "\n".join(lines)
    
    def _format_wait_optimized(self, confluence: ConfluenceScore) -> str:
        """Format WAIT recommendation"""
        
        lines = []
        lines.append("\n" + "="*80)
        lines.append(f"WAIT: LOW CONVICTION [Confluence: {confluence.overall_score:.1f}/10]")
        lines.append("="*80)
        
        lines.append(f"\nMARKET STATUS")
        lines.append("-"*80)
        lines.append(f"Confluence: {confluence.overall_score:.1f}/10 ({confluence.quality_description})")
        lines.append(f"Recommendation: DO NOT TRADE")
        
        lines.append(f"\nREASON")
        lines.append("-"*80)
        lines.append(f"✓ Cash is a position")
        lines.append(f"✓ Low quality confluence - High whipsaw risk")
        lines.append(f"✓ Better opportunities coming")
        
        lines.append(f"\nNEXT TRIGGER")
        lines.append("-"*80)
        lines.append(f"Wait for confluence to improve above 7.0")
        lines.append(f"Or wait for clear CPR breakout with volume")
        
        lines.append("="*80 + "\n")
        
        return "\n".join(lines)


# Test the optimized formatter
if __name__ == "__main__":
    from intelligence import ScenarioClassifier, ConfluenceScorer, ConfidenceCalculator, TechnicalContext
    
    print("\nTesting Optimized Copilot Formatter...")
    print("="*80)
    
    # Create test context with high confluence
    context = TechnicalContext(
        ltp=25310.0, cpr_pivot=25300.0, cpr_tc=25360.0, cpr_bc=25240.0, cpr_width=120.0,
        pdh=25385.0, pdl=25200.0,
        ema_5=25320.0, ema_12=25315.0, ema_20=25310.0,
        ema_50=25290.0, ema_100=25270.0, ema_200=25240.0,
        rsi=68.0, macd_histogram=45.0, macd_line=120.0, macd_signal=100.0,
        volume=2500000.0, volume_20ma=1800000.0, atr=85.0, vix=12.5,
        current_hour=10, current_minute=30,
        pcr=1.28, call_oi_change=-15000, put_oi_change=25000, bid_ask_spread=2.0
    )
    
    classifier = ScenarioClassifier()
    scenario = classifier.classify(context)
    
    scorer = ConfluenceScorer()
    confluence = scorer.score(
        ltp=context.ltp, cpr_pivot=context.cpr_pivot, cpr_tc=context.cpr_tc, cpr_bc=context.cpr_bc,
        pdh=context.pdh, pdl=context.pdl,
        ema_5=context.ema_5, ema_12=context.ema_12, ema_20=context.ema_20,
        ema_50=context.ema_50, ema_100=context.ema_100, ema_200=context.ema_200,
        rsi=context.rsi, macd_histogram=context.macd_histogram, macd_line=context.macd_line,
        volume=context.volume, volume_20ma=context.volume_20ma,
        pcr=context.pcr, call_oi_change=context.call_oi_change,
        put_oi_change=context.put_oi_change, bid_ask_spread=context.bid_ask_spread,
        trend_bias="BULLISH"
    )
    
    calc = ConfidenceCalculator()
    confidence = calc.calculate(scenario, confluence)
    
    # Format with optimized risk management
    formatter = OptimizedCopilotFormatter()
    output = formatter.format_sniper_output_optimized(
        confidence=confidence,
        scenario=scenario,
        confluence=confluence,
        ltp=context.ltp,
        pdh=context.pdh,
        pdl=context.pdl,
        cpr_pivot=context.cpr_pivot,
        r1=25350.0, r2=25385.0, s1=25250.0, s2=25200.0,
        atm_strike=25300.0,
        atm_delta=0.52,
        atm_ce_ltp=118.0,
        atm_pe_ltp=115.0,
        atm_iv=0.22,
        atr=85.0,
        capital=15000,
        risk_pct=1.0
    )
    
    print(output)

"""
INTELLIGENCE LAYER: AI Copilot Trading System
Complete decision intelligence for NIFTY 3-Layer Trading System

Modules:
- scenario_classifier: Detects 5 market scenarios dynamically
- confluence_scorer: Calculates 1-10 confluence score
- confidence_calculator: Maps scenario + confluence → confidence level
- copilot_formatter: Renders AI copilot recommendations
- mtf_trend_analyzer: Multi-timeframe consensus analysis
- options_intelligence: Advanced options chain analysis (PCR, OI, IV, Liquidity, Volume Spikes, Vanna/Volga, Smile, Institutional)
"""

from .scenario_classifier import (
    ScenarioClassifier,
    ScenarioType,
    ScenarioOutput,
    TechnicalContext,
    DivergenceSignals
)

from .confluence_scorer import (
    ConfluenceScorer,
    ConfluenceScore,
    ConfluenceFactors
)

from .confidence_calculator import (
    ConfidenceCalculator,
    ConfidenceOutput
)

from .mtf_trend_analyzer import (
    MTFTrendAnalyzer,
    MTFConsensusResult,
    TrendType,
    TimeframeAnalysis
)

from .options_intelligence import (
    OptionsIntelligence,
    OptionsIntelligenceResult,
    PCRAnalysis,
    OIAnalysis,
    IVAnalysis,
    LiquidityAnalysis,
    VolumeAnalysis,
    VannaVolgaAnalysis,
    VolatilitySmile,
    InstitutionalPositioning,
    StrikeAnalysis
)
from .copilot_formatter import (
    CopilotFormatter,
    CopilotRecommendation
)

from .mtf_trend_analyzer import (
    MTFTrendAnalyzer,
    MTFConsensusResult,
    TrendType,
    TimeframeAnalysis
)

from .market_condition_classifier import (
    MarketCondition,
    SetupQuality,
    MarketClassification,
    classify_market_condition,
    classify_setup_quality,
    get_dynamic_parameters,
    get_expected_move,
    format_classification
)

from .metrics_repository import (
    MetricsRepository,
    get_database_stats,
    query_best_conditions
)

__all__ = [
    'ScenarioClassifier',
    'ScenarioType',
    'ScenarioOutput',
    'TechnicalContext',
    'DivergenceSignals',
    'ConfluenceScorer',
    'ConfluenceScore',
    'ConfluenceFactors',
    'ConfidenceCalculator',
    'ConfidenceOutput',
    'CopilotFormatter',
    'CopilotRecommendation',
    'MTFTrendAnalyzer',
    'MTFConsensusResult',
    'TrendType',
    'TimeframeAnalysis',
    'MarketCondition',
    'SetupQuality',
    'MarketClassification',
    'classify_market_condition',
    'classify_setup_quality',
    'get_dynamic_parameters',
    'get_expected_move',
    'format_classification',
    'MetricsRepository',
    'get_database_stats',
    'query_best_conditions'
]

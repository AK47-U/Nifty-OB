"""
3-Layer Trading System Architecture

Layer 1: level_engine.py - Context & Proximity (WHERE to trade)
Layer 2: signal_engine.py - Signal & Momentum (WHEN to trade)  
Layer 3: execution_engine.py - Strike & Risk (WHAT to trade)

Orchestrator: orchestrator.py - Coordinates all 3 layers
"""

from .level_engine import LevelContextEngine
from .signal_engine import SignalMomentumEngine, SignalConfluence
from .execution_engine import ExecutionGreeksEngine, ExecutionSetup

# Aliases
ExecutionEngine = ExecutionGreeksEngine

__all__ = [
    'LevelContextEngine',
    'SignalMomentumEngine',
    'SignalConfluence',
    'ExecutionGreeksEngine',
    'ExecutionEngine',
    'ExecutionSetup'
]

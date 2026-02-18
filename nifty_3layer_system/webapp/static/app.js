// Suppress lightweight-charts internal "Value is null" errors during render cycles
window.addEventListener('error', (e) => {
  if (e.message && e.message.includes('Value is null')) {
    e.preventDefault();
    e.stopPropagation();
    return true;
  }
}, true);

// Also suppress in console by overriding console.error temporarily
const originalConsoleError = console.error;
console.error = function(...args) {
  const msg = args[0];
  if (typeof msg === 'string' && msg.includes('Value is null')) {
    return; // Suppress
  }
  originalConsoleError.apply(console, args);
};

const chartContainer = document.getElementById("chart");
const lastPriceEl = document.getElementById("lastPrice");
const lastUpdatedEl = document.getElementById("lastUpdated");
const signalDisplay = document.getElementById("signalDisplay");

const directionEl = document.getElementById("direction");
const confidenceEl = document.getElementById("confidence");
const qualityEl = document.getElementById("quality");
const entryEl = document.getElementById("entry");
const targetEl = document.getElementById("target");
const stoplossEl = document.getElementById("stoploss");
const rrEl = document.getElementById("rr");
const zoneEl = document.getElementById("zone");
const noteEl = document.getElementById("note");

const refreshBtn = document.getElementById("refreshBtn");
const symbolButtons = document.querySelectorAll(".seg-btn");
const statusText = document.getElementById("statusText");
const signalBadge = document.querySelector(".signal-badge");

let activeSymbol = "NIFTY";
let chart = null;
let candleSeries = null;
let priceLines = [];
let historicalPriceLines = []; // Store all historical position markers
let historicalRenderLines = []; // Rendered lightweight price lines for history
let lastCandle = null;
let ws = null;
let isChartReady = false;
let isUpdating = false;
let isInitialLoad = true;
let currentCandleBuffer = null;
let tickBuffer = [];
let lastTickTime = 0;
let overlayEl = null;
let lastLevels = null;
let lastLevelGeneratedTime = null; // Track when levels were last generated
const LEVEL_VALIDITY_MS = 15 * 60 * 1000; // 15 minutes cadence from start

// Performance optimization: Client-side cache
let candleCache = {};
let levelsCache = {};
let cacheTimestamp = {};
let resizeObserver = null;

// Safe helpers to guard lightweight-charts calls
function safePriceToCoordinate(series, price) {
  try {
    const y = series.priceToCoordinate(price);
    return Number.isFinite(y) ? y : null;
  } catch (e) {
    console.warn('priceToCoordinate failed', e);
    return null;
  }
}

function safeTimeToCoordinate(scale, time) {
  try {
    const x = scale.timeToCoordinate(time);
    return Number.isFinite(x) ? x : null;
  } catch (e) {
    console.warn('timeToCoordinate failed', e);
    return null;
  }
}

function safeSetData(series, data) {
  try {
    series.setData(data);
    return true;
  } catch (e) {
    console.error('setData failed', e);
    return false;
  }
}

function safeUpdate(series, bar) {
  try {
    series.update(bar);
    return true;
  } catch (e) {
    console.error('series.update failed', e, bar);
    return false;
  }
}

function initChart() {
  if (chart) {
    console.log("Chart already initialized");
    return true;
  }
  
  if (!chartContainer) {
    console.error("Chart container not found!");
    return false;
  }

  // Check if LightweightCharts is available
  if (typeof window.LightweightCharts === 'undefined') {
    console.error("LightweightCharts library not loaded yet!");
    return false;
  }

  try {
    // Check if createChart exists
    if (typeof window.LightweightCharts.createChart !== 'function') {
      console.error("LightweightCharts.createChart is not a function");
      return false;
    }

    chart = window.LightweightCharts.createChart(chartContainer, {
      layout: {
        background: { color: "#111827" },
        textColor: "#e5e7eb",
      },
      grid: {
        vertLines: { color: "#1f2937" },
        horzLines: { color: "#1f2937" },
      },
      timeScale: {
        timeVisible: true,
        secondsVisible: false,
        borderColor: "#1f2937",
      },
      rightPriceScale: {
        borderColor: "#1f2937",
        scaleMargins: {
          top: 0.1,
          bottom: 0.1,
        },
      },
      crosshair: {
        mode: window.LightweightCharts.CrosshairMode.Normal,
      },
      handleScroll: {
        mouseWheel: true,
        pressedMouseMove: true,
      },
      handleScale: {
        axisPressedMouseMove: true,
        mouseWheel: true,
        pinch: true,
      },
    });

    console.log("Chart created:", chart);

    if (typeof chart.addCandlestickSeries !== 'function') {
      console.error("chart.addCandlestickSeries is not available");
      return false;
    }

    candleSeries = chart.addCandlestickSeries({
      upColor: "#22c55e",
      downColor: "#ef4444",
      borderVisible: false,
      wickUpColor: "#22c55e",
      wickDownColor: "#ef4444",
    });

    // Handle window resize
    resizeObserver = new ResizeObserver(entries => {
      if (entries.length === 0 || entries[0].target !== chartContainer) {
        return;
      }
      const newRect = entries[0].contentRect;
      chart.applyOptions({ 
        width: newRect.width,
        height: newRect.height
      });
      // Native price lines auto-resize, no manual redraw needed
    });
    
    resizeObserver.observe(chartContainer);
    createChartOverlay();

    console.log("✓ Chart initialized successfully");
    isChartReady = true;
    setStatus("Ready");
    return true;
  } catch (error) {
    console.error("Failed to initialize chart:", error);
    setStatus("X Chart initialization failed");
    isChartReady = false;
    return false;
  }
}

function createChartOverlay() {
  if (!chartContainer || overlayEl) {
    return;
  }
  overlayEl = document.createElement("div");
  overlayEl.className = "chart-overlay";
  chartContainer.appendChild(overlayEl);
}

function setStatus(message) {
  if (statusText) statusText.textContent = message;
  console.log("Status:", message);
}

function setPriceLines(levels) {
  if (!candleSeries || !isChartReady) {
    console.warn("Chart not ready for price lines");
    return;
  }
  const seriesData = candleSeries.data();
  if (!seriesData || seriesData.length === 0) {
    console.warn("No series data available for price lines yet");
    return;
  }

  // Always anchor marker time to the latest candle so position aligns with current chart
  const markerCandidate = lastCandle && lastCandle.time != null ? lastCandle.time : levels.last_candle_time;
  const markerTime = Number(markerCandidate);
  const hasMarkerTime = Number.isFinite(markerTime);
  if (!hasMarkerTime) {
    console.warn("No valid marker time available; skipping markers");
  } else {
    levels.last_candle_time = markerTime;
  }
  
  // Validate required numeric fields
  const entryVal = Number(levels?.entry);
  const targetVal = Number(levels?.exit_target);
  const stopVal = Number(levels?.stoploss);
  if (![entryVal, targetVal, stopVal].every((v) => Number.isFinite(v))) {
    console.warn("Invalid levels data for price lines", levels);
    return;
  }

  // Clear existing price lines safely
  priceLines.forEach((line) => {
    try {
      if (line && candleSeries) {
        candleSeries.removePriceLine(line);
      }
    } catch (e) {
      console.warn("Error removing price line:", e);
    }
  });
  priceLines = [];

  const direction = levels.direction;
  const isBuy = direction === "BUY";

  // Use native lightweight-charts price lines - these ARE seamlessly integrated
  try {
    // Entry line
    priceLines.push(
      candleSeries.createPriceLine({
        price: entryVal,
        color: isBuy ? "#22c55e" : "#ef4444",
        lineWidth: 2,
        lineStyle: 0, // Solid
        axisLabelVisible: true,
        title: isBuy ? "Buy" : "Sell",
      })
    );

    // Target line
    priceLines.push(
      candleSeries.createPriceLine({
        price: targetVal,
        color: "#a855f7",
        lineWidth: 2,
        lineStyle: 0, // Solid
        axisLabelVisible: true,
        title: isBuy ? "Long TP" : "Short TP",
      })
    );

    // Stop Loss line
    priceLines.push(
      candleSeries.createPriceLine({
        price: stopVal,
        color: "#6b7280",
        lineWidth: 2,
        lineStyle: 2, // Dashed
        axisLabelVisible: true,
        title: "SL",
      })
    );

    // Add marker at entry candle
    if (hasMarkerTime) {
      const seriesData = candleSeries.data();
      const firstTime = seriesData[0].time;
      const lastTime = seriesData[seriesData.length - 1].time;
      if (markerTime >= firstTime && markerTime <= lastTime) {
        candleSeries.setMarkers([
          {
            time: markerTime,
            position: isBuy ? "belowBar" : "aboveBar",
            color: isBuy ? "#22c55e" : "#ef4444",
            shape: isBuy ? "arrowUp" : "arrowDown",
            text: isBuy ? "LONG" : "SHORT",
          },
        ]);
      }
    }
  } catch (e) {
    console.warn("Error creating price lines:", e);
  }

  const direction2 = levels.direction;
  const isBuy2 = direction2 === "BUY";

  try {
    // Store in historical markers array for persistence
    historicalPriceLines.push({
      timestamp: Date.now(),
      direction: direction,
      entry: entryVal,
      target: targetVal,
      sl: stopVal,
      candleTime: markerTime,
    });

    const entryTimeForRegion = Number(levels.last_candle_time);
    
    // Price lines handle the levels - no trade zone overlay needed
    
    lastLevels = levels;
    lastLevelGeneratedTime = Date.now(); // Update timestamp
  } catch (error) {
    console.error("Error setting price lines:", error);
  }
}

// Draw short horizontal segments for entry/target/stop instead of full-width price lines
function renderLevelSegments(entryVal, targetVal, stopVal, startTime, endTime, isBuy) {
  if (!overlayEl || !chart || !candleSeries || !isChartReady) return;

  // Clean previous segments/boxes
  overlayEl.querySelectorAll('.level-segment, .position-box').forEach((el) => el.remove());

  const data = candleSeries.data();
  if (!data || data.length === 0) return;

  const timeScale = chart.timeScale();
  // Anchor around entry candle time if available; else use 70% of overlay width
  const anchorX = (Number.isFinite(startTime) && timeScale && typeof timeScale.timeToCoordinate === 'function')
    ? safeTimeToCoordinate(timeScale, startTime)
    : (overlayEl.clientWidth * 0.7);

  const centerX = Number.isFinite(anchorX) ? anchorX : (overlayEl.clientWidth * 0.7);
  const boxWidth = 180; // width similar to TradingView position tool
  const left = Math.max(0, centerX - boxWidth / 2);

  const entryY = safePriceToCoordinate(candleSeries, entryVal);
  const targetY = safePriceToCoordinate(candleSeries, targetVal);
  const stopY = safePriceToCoordinate(candleSeries, stopVal);
  if (![entryY, targetY, stopY].every((v) => Number.isFinite(v))) return;

  // Profit and risk rectangles
  const profitTop = Math.min(entryY, targetY);
  const profitHeight = Math.max(2, Math.abs(targetY - entryY));
  const riskTop = Math.min(entryY, stopY);
  const riskHeight = Math.max(2, Math.abs(stopY - entryY));

  const addBox = (top, height, bg, border) => {
    const box = document.createElement('div');
    box.className = 'position-box';
    box.style.position = 'absolute';
    box.style.left = `${left}px`;
    box.style.top = `${top}px`;
    box.style.width = `${boxWidth}px`;
    box.style.height = `${height}px`;
    box.style.background = bg;
    box.style.border = `1px solid ${border}`;
    box.style.borderRadius = '3px';
    box.style.opacity = '0.25';
    box.style.pointerEvents = 'none';
    box.style.zIndex = '4';
    overlayEl.appendChild(box);
  };

  // Profit (green for buy, purple for short TP) and Risk (red/gray)
  addBox(profitTop, profitHeight, isBuy ? 'rgba(34,197,94,0.18)' : 'rgba(168,85,247,0.16)', isBuy ? '#16a34a80' : '#a855f780');
  addBox(riskTop, riskHeight, 'rgba(239,68,68,0.14)', '#ef444480');

  // Thin lines at entry/TP/SL for clarity
  const addLine = (y, color) => {
    const seg = document.createElement('div');
    seg.className = 'level-segment';
    seg.style.position = 'absolute';
    seg.style.left = `${left}px`;
    seg.style.top = `${y}px`;
    seg.style.width = `${boxWidth}px`;
    seg.style.height = '2px';
    seg.style.transform = 'translateY(-50%)';
    seg.style.background = color;
    seg.style.opacity = '0.9';
    seg.style.zIndex = '5';
    seg.style.pointerEvents = 'none';
    overlayEl.appendChild(seg);
  };

  addLine(entryY, isBuy ? '#22c55e' : '#ef4444');
  addLine(targetY, isBuy ? '#a855f7' : '#a855f7');
  addLine(stopY, '#6b7280');
}

function drawTradeZones(levels) {
  // Strict validation - abort if chart not stable
  if (!overlayEl || !candleSeries || !levels || !chart || !isChartReady) {
    console.warn('Trade zones: Chart not ready');
    return;
  }
  
  // Additional safety: verify chart has data
  try {
    const chartData = candleSeries.data();
    if (!chartData || chartData.length === 0) {
      console.warn('Trade zones: Chart has no data');
      return;
    }
  } catch (e) {
    console.error('Trade zones: Chart data check failed:', e);
    return;
  }

  const entry = Number(levels.entry);
  const target = Number(levels.exit_target);
  const stop = Number(levels.stoploss);

  if (![entry, target, stop].every((v) => Number.isFinite(v))) {
    console.warn('Trade zones: Missing or invalid level values');
    return;
  }

  let entryY, targetY, stopY;
  
  try {
    entryY = safePriceToCoordinate(candleSeries, entry);
    targetY = safePriceToCoordinate(candleSeries, target);
    stopY = safePriceToCoordinate(candleSeries, stop);

    if (entryY == null || targetY == null || stopY == null) {
      console.warn('Trade zones: Coordinate conversion returned null');
      return;
    }
    
    if (isNaN(entryY) || isNaN(targetY) || isNaN(stopY)) {
      console.warn('Trade zones: Coordinate conversion returned NaN');
      return;
    }
  } catch (e) {
    console.error('Trade zones: Coordinate conversion failed:', e);
    return;
  }

  // Clear only zone-rect elements, preserve position boxes and other overlays
  overlayEl.querySelectorAll('.zone-rect').forEach((el) => el.remove());

  const isBuy = levels.direction === "BUY";
  const profitTop = Math.min(entryY, targetY);
  const profitBottom = Math.max(entryY, targetY);
  const riskTop = Math.min(entryY, stopY);
  const riskBottom = Math.max(entryY, stopY);

  const profitRect = document.createElement("div");
  profitRect.className = `zone-rect ${isBuy ? "zone-profit-long" : "zone-profit-short"}`;
  profitRect.style.top = `${profitTop}px`;
  profitRect.style.height = `${Math.max(1, profitBottom - profitTop)}px`;
  overlayEl.appendChild(profitRect);

  const riskRect = document.createElement("div");
  riskRect.className = `zone-rect ${isBuy ? "zone-risk-long" : "zone-risk-short"}`;
  riskRect.style.top = `${riskTop}px`;
  riskRect.style.height = `${Math.max(1, riskBottom - riskTop)}px`;
  overlayEl.appendChild(riskRect);
}

// Draw time-based validity region for 30-minute window
function drawTimeValidityRegion(startTime, endTime, isBuy) {
  if (!overlayEl || !chart || !candleSeries || !isChartReady) return;

  if (!Number.isFinite(startTime) || !Number.isFinite(endTime)) {
    console.warn('Time validity region skipped due to invalid start/end');
    return;
  }
  
  try {
    const data = candleSeries.data();
    if (!data || data.length === 0) return;

    const firstTime = data[0].time;
    const lastTime = data[data.length - 1].time;

    // Clamp to visible data range
    if (startTime < firstTime || startTime > lastTime || endTime < firstTime) {
      console.warn('Time validity window outside chart range');
      return;
    }

    const clampedEnd = Math.min(endTime, lastTime);
    if (startTime > clampedEnd) return;

    const timeScale = chart.timeScale();
    if (!timeScale || typeof timeScale.timeToCoordinate !== 'function') return;
    const visible = timeScale.getVisibleRange();
    if (visible && (!Number.isFinite(visible.from) || !Number.isFinite(visible.to))) {
      console.warn('Visible range invalid, skipping time region');
      return;
    }
    if (visible && (startTime < visible.from || startTime > visible.to)) {
      // If marker is outside view, skip drawing to avoid null coords
      return;
    }
    
    const startX = timeScale.timeToCoordinate(startTime);
    const endX = timeScale.timeToCoordinate(clampedEnd);
    
    if (startX == null || endX == null || isNaN(startX) || isNaN(endX)) {
      console.warn('Time coordinate conversion failed');
      return;
    }
    
    const width = Math.max(0, endX - startX);
    if (width === 0) return;
    
    // Clear previous time markers to avoid duplicates
    overlayEl.querySelectorAll('.time-marker-line, .time-validity-region').forEach((el) => el.remove());
    
    // Create vertical line at entry time
    const verticalLine = document.createElement("div");
    verticalLine.className = "time-marker-line";
    verticalLine.style.position = "absolute";
    verticalLine.style.left = `${startX}px`;
    verticalLine.style.top = "0";
    verticalLine.style.bottom = "0";
    verticalLine.style.width = "2px";
    verticalLine.style.backgroundColor = isBuy ? "#22c55e" : "#ef4444";
    verticalLine.style.opacity = "0.5";
    verticalLine.style.pointerEvents = "none";
    verticalLine.style.zIndex = "5";
    overlayEl.appendChild(verticalLine);
    
    // Create shaded time region for validity window
    const timeRegion = document.createElement("div");
    timeRegion.className = "time-validity-region";
    timeRegion.style.position = "absolute";
    timeRegion.style.left = `${startX}px`;
    timeRegion.style.top = "0";
    timeRegion.style.bottom = "0";
    timeRegion.style.width = `${width}px`;
    timeRegion.style.backgroundColor = isBuy ? "rgba(34, 197, 94, 0.15)" : "rgba(239, 68, 68, 0.15)";
    timeRegion.style.borderLeft = `3px solid ${isBuy ? '#22c55e' : '#ef4444'}`;
    timeRegion.style.borderRight = `2px dashed ${isBuy ? '#22c55e80' : '#ef444480'}`;
    timeRegion.style.pointerEvents = "none";
    timeRegion.style.zIndex = "4";
    overlayEl.appendChild(timeRegion);
    
    console.log(`✓ Time validity region drawn: ${width}px (${startTime} to ${endTime})`);
  } catch (e) {
    console.error('Failed to draw time validity region:', e);
  }
}

function updateLevelsCard(levels) {
  console.log('Updating levels card with:', levels);
  
  // Null check for all elements
  if (!directionEl || !confidenceEl || !entryEl || !targetEl || !stoplossEl || !rrEl) {
    console.error('Some card elements are missing!');
    return;
  }
  
  // Direction with color
  directionEl.textContent = levels.direction;
  directionEl.style.color = levels.direction === "BUY" ? "#22c55e" : "#ef4444";
  directionEl.style.fontWeight = "bold";
  
  // Update signal badge in header (with null checks)
  if (signalBadge && signalDisplay) {
    signalBadge.className = "signal-badge";
    if (levels.direction === "BUY") {
      signalBadge.classList.add("long");
      signalDisplay.textContent = "LONG";
    } else {
      signalBadge.classList.add("short");
      signalDisplay.textContent = "SHORT";
    }
  }
  
  // Confidence (null check)
  confidenceEl.textContent = levels.confidence != null ? `${levels.confidence.toFixed(1)}%` : '--';
  
  // Quality Score (with color coding)
  if (qualityEl) {
    const qualityScore = levels.quality_score;
    if (qualityScore != null) {
      qualityEl.textContent = `${qualityScore.toFixed(0)}%`;
      // Color code: Green >= 70%, Yellow 50-70%, Red < 50%
      if (qualityScore >= 70) {
        qualityEl.style.color = "#22c55e"; // Green
      } else if (qualityScore >= 50) {
        qualityEl.style.color = "#eab308"; // Yellow
      } else {
        qualityEl.style.color = "#ef4444"; // Red
      }
    } else {
      qualityEl.textContent = '--';
      qualityEl.style.color = '#6b7280';
    }
  }
  
  // Entry, Target, Stop Loss (null checks)
  entryEl.textContent = levels.entry != null ? levels.entry.toFixed(2) : '--';
  targetEl.textContent = levels.exit_target != null ? levels.exit_target.toFixed(2) : '--';
  stoplossEl.textContent = levels.stoploss != null ? levels.stoploss.toFixed(2) : '--';
  
  // Risk Reward (null check)
  rrEl.textContent = levels.risk_reward_ratio != null ? `1:${levels.risk_reward_ratio.toFixed(2)}` : '--';
  
  // Zone and Note (with null checks)
  if (zoneEl) zoneEl.textContent = levels.zone_description || '--';
  if (noteEl) {
    if (levels.action === 'WAIT') {
      noteEl.textContent = `⚠️ WAIT: ${levels.wait_reason || 'Low quality signal - skip this trade'}`;
      noteEl.style.color = "#ef4444"; // Red for WAIT
    } else if (levels.position_status === 'HOLD') {
      noteEl.textContent = `HOLD: ${levels.hold_reason || 'No change; keeping position'}`;
      noteEl.style.color = "#eab308"; // Yellow for HOLD
    } else {
      noteEl.textContent = levels.entry_description || '--';
      noteEl.style.color = "#22c55e"; // Green for tradeable
    }
  }
}

function connectStream(symbol) {
  if (ws) {
    ws.close();
    ws = null;
  }

  const wsUrl = `${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws/stream?symbol=${symbol}`;
  console.log('Connecting to WebSocket:', wsUrl);
  
  ws = new WebSocket(wsUrl);

  ws.onopen = () => {
    console.log('WebSocket connected for', symbol);
  };

  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      
      // Handle outcome notifications (target/SL hit)
      if (data.type === 'outcome') {
        console.log(`📢 Outcome: ${data.outcome} for ${data.direction} @ ${data.price}`);
        showOutcomeToast(data.outcome, data.direction, data.price);
        return;
      }
      
      const ltp = Number(data.ltp);
      if (!Number.isFinite(ltp)) {
        console.warn('No LTP in tick data');
        return;
      }

      // Wait for initial data load before processing ticks
      if (!lastCandle || !candleSeries || !isChartReady) {
        return;
      }

      // Throttle updates: only process every 100ms for smooth rendering
      const now = Date.now();
      if (now - lastTickTime < 100) {
        // Buffer the tick
        tickBuffer.push(data.ltp);
        return;
      }
      
      // Use latest price from buffer or current
      const latestBuffered = tickBuffer.length > 0 ? tickBuffer[tickBuffer.length - 1] : ltp;
      const latestPrice = Number(latestBuffered);
      if (!Number.isFinite(latestPrice)) {
        console.warn('Invalid latest price in buffer');
        return;
      }
      tickBuffer = [];
      lastTickTime = now;
      
      // Update header displays
      if (lastPriceEl) lastPriceEl.textContent = latestPrice.toFixed(2);
      if (lastUpdatedEl) {
        // Display current time in IST
        lastUpdatedEl.textContent = new Date().toLocaleTimeString('en-IN', {
          hour: '2-digit',
          minute: '2-digit',
          second: '2-digit',
          hour12: true,
          timeZone: 'Asia/Kolkata'
        });
      }

      // Get current timestamp in seconds (convert to IST to match historical candles)
      const IST_OFFSET = 19800; // 5.5 hours in seconds
      const currentTime = Math.floor(Date.now() / 1000) + IST_OFFSET;
      const lastCandleTime = lastCandle.time;
      
      // Calculate candle interval (5 minutes = 300 seconds)
      const candleInterval = 300;
      const currentCandleTime = Math.floor(currentTime / candleInterval) * candleInterval;
      
      // Check if this tick belongs to the current candle or starts a new one
      if (currentCandleTime === lastCandleTime) {
        // Update existing candle (same 5-min period)
        const updatedCandle = {
          time: lastCandle.time,
          open: lastCandle.open,
          high: Math.max(lastCandle.high, latestPrice),
          low: Math.min(lastCandle.low, latestPrice),
          close: latestPrice
        };
        
        if (safeUpdate(candleSeries, updatedCandle)) {
          lastCandle = updatedCandle;
          currentCandleBuffer = updatedCandle;
        }
      } else if (currentCandleTime > lastCandleTime) {
        // New candle (new 5-min period)
        const newCandle = {
          time: currentCandleTime,
          open: latestPrice,
          high: latestPrice,
          low: latestPrice,
          close: latestPrice
        };

        if (safeUpdate(candleSeries, newCandle)) {
          lastCandle = newCandle;
          currentCandleBuffer = newCandle;
          const candleTime = new Date(currentCandleTime * 1000).toLocaleTimeString();
          console.log(`🕐 New candle @ ${candleTime}: ${latestPrice.toFixed(2)}`);
          
          // Scroll to latest candle
          if (chart && chart.timeScale) {
            chart.timeScale().scrollToRealTime();
          }
        }
      }
    } catch (err) {
      console.error('WebSocket message error:', err);
    }
  };

  ws.onerror = (error) => {
    console.error('WebSocket error:', error);
  };

  ws.onclose = () => {
    console.log('WebSocket closed for', symbol);
  };
}

async function loadData(symbol, forceRefresh = false) {
  // Prevent concurrent updates
  if (isUpdating) {
    console.warn('Update already in progress, skipping');
    return;
  }
  
  isUpdating = true;
  
  // Check cache (valid for 30 seconds)
  const cacheKey = `${symbol}_candles`;
  const now = Date.now();
  if (!forceRefresh && candleCache[cacheKey] && (now - cacheTimestamp[cacheKey] < 30000)) {
    console.log('✓ Using cached candles');
    setStatus(`✓ Chart ready (cached) | ${symbol}`);
    isUpdating = false;
    return;
  }
  
  setStatus(`Loading ${symbol}...`);
  
  try {
    // Ensure chart is initialized
    if (!isChartReady || !chart || !candleSeries) {
      const initialized = initChart();
      if (!initialized) {
        setStatus("✗ Chart init failed");
        isUpdating = false;
        return;
      }
      await new Promise(resolve => setTimeout(resolve, 100));
    }

    // Fetch candles only
    console.log(`📥 Fetching candles for ${symbol}...`);
    const t0 = performance.now();
    const candlesRes = await fetch(`/api/candles?symbol=${symbol}&interval=5&days=5`);
    const t1 = performance.now();
    console.log(`⏱️  Candles fetch: ${(t1-t0).toFixed(0)}ms`);
    
    if (!candlesRes.ok) throw new Error(`Candles API failed: ${candlesRes.status}`);
    
    const candlesData = await candlesRes.json();
    let candles = Array.isArray(candlesData) ? candlesData : (candlesData.candles || []);
    
    if (candles.length === 0) throw new Error('No candles received');

    // Drop any candles with null/invalid OHLC to avoid lightweight-charts errors
    // Also convert UTC timestamps to IST (+5:30 = +19800 seconds)
    const IST_OFFSET = 19800; // 5.5 hours in seconds
    const sanitized = candles.filter((c) =>
      c && [c.time, c.open, c.high, c.low, c.close].every((v) => Number.isFinite(Number(v)))
    ).map((c) => ({
      time: Number(c.time) + IST_OFFSET,  // Convert UTC to IST
      open: Number(c.open),
      high: Number(c.high),
      low: Number(c.low),
      close: Number(c.close),
    }));

    if (sanitized.length === 0) throw new Error('All candles invalid after sanitization');
    candles = sanitized;
    
    // Sort by time
    candles.sort((a, b) => a.time - b.time);
    
    // Cache candles
    candleCache[cacheKey] = candles;
    cacheTimestamp[cacheKey] = now;
    
    // Update chart
    if (candleSeries) {
      if (isInitialLoad) {
        if (!safeSetData(candleSeries, candles)) {
          isUpdating = false;
          return;
        }
        isInitialLoad = false;
        console.log('📊 Initial chart loaded');
      } else {
        // On refresh: only update historical, preserve live candle
        const hist = candles.slice(0, -1);
        if (!safeSetData(candleSeries, hist)) {
          isUpdating = false;
          return;
        }
        safeUpdate(candleSeries, candles[candles.length - 1]);
      }
      
      if (chart && chart.timeScale) {
        chart.timeScale().fitContent();
      }
      isChartReady = true;
    }

    // Update price display
    const lastPrice = candles[candles.length - 1].close;
    if (lastPriceEl) lastPriceEl.textContent = lastPrice.toFixed(2);
    if (lastUpdatedEl) {
      // Display current time in IST
      lastUpdatedEl.textContent = new Date().toLocaleTimeString('en-IN', {
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        hour12: true,
        timeZone: 'Asia/Kolkata'
      });
    }
    
    lastCandle = candles[candles.length - 1];
    
    // Check if 15 minutes have elapsed since last level generation
    const shouldFetchNewLevels = !lastLevelGeneratedTime || (now - lastLevelGeneratedTime >= LEVEL_VALIDITY_MS);
    
    if (shouldFetchNewLevels) {
      console.log('⏰ 15 minutes elapsed or first load - fetching fresh levels');
      
      // Fetch levels asynchronously after chart settles (300ms delay)
      setTimeout(async () => {
        if (!isChartReady || !candleSeries) {
          console.warn('Chart not ready for levels update');
          return;
        }
        
        try {
          const levelsRes = await fetch(`/api/levels?symbol=${symbol}&interval=5&days=5`);
          if (levelsRes.ok) {
            const levelsData = await levelsRes.json();
            levelsCache[symbol] = levelsData;

            // Attach latest candle time for overlays if missing
            if (!levelsData.last_candle_time && lastCandle) {
              levelsData.last_candle_time = lastCandle.time;
            }

            if (levelsData && levelsData.entry && isChartReady && candleSeries) {
              levelsData.entry = Number(levelsData.entry);
              levelsData.exit_target = Number(levelsData.exit_target);
              levelsData.stoploss = Number(levelsData.stoploss);
              if ([levelsData.entry, levelsData.exit_target, levelsData.stoploss].every(Number.isFinite)) {
              setPriceLines(levelsData);
              }
            }
            if (levelsData && levelsData.direction) {
              updateLevelsCard(levelsData);
              if (levelsData.position_status === 'HOLD') {
                setStatus(`HOLD existing position - ${levelsData.hold_reason || 'structure unchanged'}`);
              } else {
                setStatus(`✓ ${levelsData.direction} signal generated - Entry: ${levelsData.entry.toFixed(2)}`);
              }
            }
          }
        } catch (e) {
          console.error('Levels load failed:', e);
        }
      }, 300); // Wait 300ms for chart to settle
    } else {
      const remainingTime = LEVEL_VALIDITY_MS - (now - lastLevelGeneratedTime);
      const remainingMinutes = Math.floor(remainingTime / 60000);
      const remainingSeconds = Math.floor((remainingTime % 60000) / 1000);
      console.log(`⏳ Current levels still valid - ${remainingMinutes}m ${remainingSeconds}s remaining`);
    }

    setStatus(`🟢 LIVE | ${symbol} | ${candles.length} candles`);
    console.log(`✓ Chart ready in ${(performance.now() - t0).toFixed(0)}ms`);
      
  } catch (error) {
    console.error('Load failed:', error);
    setStatus(`✗ ${error.message}`);
  } finally {
    isUpdating = false;
  }
}

symbolButtons.forEach((btn) => {
  btn.addEventListener("click", () => {
    symbolButtons.forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    activeSymbol = btn.dataset.symbol;
    console.log(`Switching to ${activeSymbol}, restarting live mode...`);
    loadData(activeSymbol);
    connectStream(activeSymbol);
    startAutoRefresh(); // Restart auto-refresh for new symbol
  });
});

refreshBtn.addEventListener("click", () => {
  console.log("Generate Levels button clicked for", activeSymbol);
  setStatus("Generating levels...");
  generateLevels(activeSymbol);
});

async function generateLevels(symbol) {
  try {
    const levelsRes = await fetch(`/api/levels?symbol=${symbol}&interval=5&days=5`);
    if (!levelsRes.ok) {
      throw new Error(`Levels API failed: ${levelsRes.status}`);
    }
    const levelsData = await levelsRes.json();
    console.log('Generated levels:', levelsData);

    if (levelsData && levelsData.direction) {
      // Update the card
      updateLevelsCard(levelsData);
      
      // Update chart with price lines and markers
      if (lastCandle) {
        levelsData.last_candle_time = lastCandle.time;
        setPriceLines(levelsData);
      }
      
      if (levelsData.position_status === 'HOLD') {
        setStatus(`HOLD existing position - ${levelsData.hold_reason || 'structure unchanged'}`);
      } else {
        setStatus(`✓ ${levelsData.direction} signal generated - Entry: ${levelsData.entry.toFixed(2)}`);
      }
    } else {
      setStatus("✗ Failed to generate levels");
      console.error('Invalid levels data:', levelsData);
    }
  } catch (error) {
    console.error('Error generating levels:', error);
    setStatus(`✗ Error: ${error.message}`);
  }
}

// Initialize in correct order with proper library loading check
console.log("Page loaded, waiting for library...");

let autoRefreshInterval = null;

// Auto-refresh function to keep chart live
function startAutoRefresh() {
  // Refresh candles every 5 minutes to get latest data
  if (autoRefreshInterval) {
    clearInterval(autoRefreshInterval);
  }
  
  autoRefreshInterval = setInterval(() => {
    console.log("Auto-refreshing candles for live data (15m cadence)...");
    loadData(activeSymbol);
  }, 15 * 60 * 1000); // 15 minutes
  
  console.log("✓ Auto-refresh enabled (every 15 minutes)");
}

// Wait for LightweightCharts library to load
function waitForLibrary(callback, attempts = 0) {
  if (typeof window.LightweightCharts !== 'undefined') {
    console.log("LightweightCharts library is ready!");
    callback();
  } else if (attempts < 50) {
    setTimeout(() => waitForLibrary(callback, attempts + 1), 100);
  } else {
    console.error("LightweightCharts library failed to load after 5 seconds");
    setStatus("X Chart library failed to load");
  }
}

waitForLibrary(() => {
  console.log("Initializing chart...");
  initChart();

  // Native price lines move with pan/zoom automatically - no redraw needed

  // Delay data loading to ensure chart is ready
  setTimeout(() => {
    console.log("Loading initial data and starting live mode...");
    loadData(activeSymbol);
    connectStream(activeSymbol);
    startAutoRefresh();
    
    // Load performance stats
    loadStats();
  }, 100);
});

// ============ PERFORMANCE STATS ============

async function loadStats() {
  try {
    const response = await fetch('/api/stats?days=7');
    const data = await response.json();
    
    if (data.error || data.message) {
      document.getElementById('statsNote').textContent = data.message || 'No completed signals yet';
      return;
    }
    
    // Update stats display
    document.getElementById('winRate').textContent = `${(data.win_rate || 0).toFixed(1)}%`;
    document.getElementById('totalTrades').textContent = data.total_signals || 0;
    document.getElementById('winCount').textContent = data.wins || 0;
    document.getElementById('lossCount').textContent = data.losses || 0;
    
    const totalPnl = data.total_pnl || 0;
    const pnlEl = document.getElementById('totalPnl');
    pnlEl.textContent = totalPnl.toFixed(1);
    pnlEl.style.color = totalPnl >= 0 ? 'var(--green)' : 'var(--red)';
    
    const avgDur = data.avg_win_duration_min;
    document.getElementById('avgDuration').textContent = avgDur ? `${avgDur.toFixed(0)}m` : '--';
    
    // Update note with best hour
    if (data.best_hour !== undefined) {
      document.getElementById('statsNote').textContent = 
        `Best hour: ${data.best_hour}:00 | Last 7 days`;
    } else {
      document.getElementById('statsNote').textContent = 'Last 7 days';
    }
    
    console.log('✓ Stats loaded:', data);
  } catch (error) {
    console.error('Failed to load stats:', error);
    document.getElementById('statsNote').textContent = 'Failed to load stats';
  }
}

// Refresh stats button
document.getElementById('refreshStats')?.addEventListener('click', loadStats);

// Show outcome notification toast
function showOutcomeToast(outcome, direction, price) {
  // Remove any existing toast
  document.querySelectorAll('.outcome-toast').forEach(el => el.remove());
  
  const toast = document.createElement('div');
  toast.className = `outcome-toast ${outcome.toLowerCase()}`;
  
  if (outcome === 'TARGET') {
    toast.textContent = `🎯 TARGET HIT! ${direction} @ ${price.toFixed(2)}`;
  } else {
    toast.textContent = `⛔ SL HIT! ${direction} @ ${price.toFixed(2)}`;
  }
  
  document.body.appendChild(toast);
  
  // Remove after 5 seconds
  setTimeout(() => toast.remove(), 5000);
  
  // Refresh stats after outcome
  setTimeout(() => loadStats(), 1000);
}

// Auto-refresh stats every 5 minutes
setInterval(loadStats, 5 * 60 * 1000);


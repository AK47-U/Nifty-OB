const chartContainer = document.getElementById("chart");
const lastPriceEl = document.getElementById("lastPrice");
const lastUpdatedEl = document.getElementById("lastUpdated");
const signalDisplay = document.getElementById("signalDisplay");

const directionEl = document.getElementById("direction");
const confidenceEl = document.getElementById("confidence");
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
let lastCandle = null;
let ws = null;
let isChartReady = false;
let isUpdating = false;

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
      },
      rightPriceScale: {
        borderColor: "#1f2937",
      },
      height: 480,
    });

    console.log("Chart created:", chart);
    console.log("Chart methods:", Object.keys(chart));

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

function setStatus(message) {
  if (statusText) statusText.textContent = message;
  console.log("Status:", message);
}

function setPriceLines(levels) {
  if (!candleSeries || !isChartReady) {
    console.warn("Chart not ready for price lines");
    return;
  }
  
  if (!levels || !levels.entry) {
    console.warn("Invalid levels data for price lines");
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
  const entryColor = direction === "BUY" ? "#22c55e" : "#ef4444";

  try {
    // Entry line
    priceLines.push(
      candleSeries.createPriceLine({
        price: levels.entry,
        color: "#38bdf8",
        lineWidth: 2,
        lineStyle: 0,
        axisLabelVisible: true,
        title: "ENTRY",
      })
    );

    // Target line
    priceLines.push(
      candleSeries.createPriceLine({
        price: levels.exit_target,
        color: "#f59e0b",
        lineWidth: 2,
        lineStyle: 0,
        axisLabelVisible: true,
        title: "TARGET",
      })
    );

    // Stop Loss line
    priceLines.push(
      candleSeries.createPriceLine({
        price: levels.stoploss,
        color: "#a78bfa",
        lineWidth: 2,
        lineStyle: 0,
        axisLabelVisible: true,
        title: "SL",
      })
    );

    // Add LONG/SHORT marker on chart
    if (candleSeries && levels.last_candle_time) {
      candleSeries.setMarkers([
        {
          time: levels.last_candle_time,
          position: direction === "BUY" ? "belowBar" : "aboveBar",
          color: entryColor,
          shape: direction === "BUY" ? "arrowUp" : "arrowDown",
          text: direction === "BUY" ? "LONG" : "SHORT",
        },
      ]);
      
      console.log(`✓ ${direction} position marked on chart - Entry: ${levels.entry}, Target: ${levels.exit_target}, SL: ${levels.stoploss}`);
    }
  } catch (error) {
    console.error("Error setting price lines:", error);
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
  
  // Confidence
  confidenceEl.textContent = `${levels.confidence.toFixed(1)}%`;
  
  // Entry, Target, Stop Loss
  entryEl.textContent = levels.entry.toFixed(2);
  targetEl.textContent = levels.exit_target.toFixed(2);
  stoplossEl.textContent = levels.stoploss.toFixed(2);
  
  // Risk Reward
  rrEl.textContent = `1:${levels.risk_reward_ratio.toFixed(2)}`;
  
  // Zone and Note (with null checks)
  if (zoneEl) zoneEl.textContent = levels.zone_description || '--';
  if (noteEl) noteEl.textContent = levels.entry_description || '--';
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
      // Prevent concurrent updates
      if (isUpdating) return;
      
      const data = JSON.parse(event.data);
      
      if (!data.ltp) {
        console.warn('No LTP in tick data');
        return;
      }

      // Wait for initial data load before processing ticks
      if (!lastCandle || !candleSeries || !isChartReady) {
        console.warn('Waiting for initial chart data...');
        return;
      }

      isUpdating = true;
      
      // Update header displays
      if (lastPriceEl) lastPriceEl.textContent = data.ltp.toFixed(2);
      if (lastUpdatedEl) lastUpdatedEl.textContent = new Date().toLocaleTimeString();

      // Get current timestamp in seconds
      const currentTime = Math.floor(Date.now() / 1000);
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
          high: Math.max(lastCandle.high, data.ltp),
          low: Math.min(lastCandle.low, data.ltp),
          close: data.ltp
        };
        
        try {
          candleSeries.update(updatedCandle);
          lastCandle = updatedCandle;
          console.log(`Updated candle: C=${data.ltp.toFixed(2)} H=${updatedCandle.high.toFixed(2)} L=${updatedCandle.low.toFixed(2)}`);
        } catch (updateErr) {
          console.error('Candle update failed:', updateErr);
        }
      } else if (currentCandleTime > lastCandleTime) {
        // New candle (new 5-min period)
        const newCandle = {
          time: currentCandleTime,
          open: data.ltp,
          high: data.ltp,
          low: data.ltp,
          close: data.ltp
        };
        
        try {
          candleSeries.update(newCandle);
          lastCandle = newCandle;
          console.log(`New candle started at ${new Date(currentCandleTime * 1000).toLocaleTimeString()}: ${data.ltp.toFixed(2)}`);
        } catch (updateErr) {
          console.error('New candle creation failed:', updateErr);
        }
      }
      
      isUpdating = false;
    } catch (err) {
      console.error('WebSocket message error:', err);
      isUpdating = false;
    }
  };

  ws.onerror = (error) => {
    console.error('WebSocket error:', error);
  };

  ws.onclose = () => {
    console.log('WebSocket closed for', symbol);
  };
}

async function loadData(symbol) {
  // Prevent concurrent updates
  if (isUpdating) {
    console.warn('Update already in progress, skipping');
    return;
  }
  
  isUpdating = true;
  setStatus(`Loading ${symbol} data...`);
  
  try {
    // Ensure chart is initialized
    if (!isChartReady || !chart || !candleSeries) {
      console.error("Chart not ready, attempting initialization...");
      const initialized = initChart();
      if (!initialized) {
        setStatus("✗ Chart initialization failed");
        isUpdating = false;
        return;
      }
      // Wait a bit for chart to be fully ready
      await new Promise(resolve => setTimeout(resolve, 200));
    }

    // Fetch candles
    console.log(`Fetching candles for ${symbol}...`);
    const candlesRes = await fetch(`/api/candles?symbol=${symbol}&interval=5&days=5`);
    if (!candlesRes.ok) {
      throw new Error(`Candles API failed: ${candlesRes.status}`);
    }
    const candlesData = await candlesRes.json();
    console.log('Raw candles response:', candlesData);
    console.log('Has candles property:', 'candles' in candlesData);
    console.log('Candles is array:', Array.isArray(candlesData?.candles));
    console.log('Candles length:', candlesData?.candles?.length);

    // Fetch levels
    console.log(`Fetching levels for ${symbol}...`);
    const levelsRes = await fetch(`/api/levels?symbol=${symbol}&interval=5&days=5`);
    if (!levelsRes.ok) {
      throw new Error(`Levels API failed: ${levelsRes.status}`);
    }
    const levelsData = await levelsRes.json();
    console.log('Levels data:', levelsData);

    // Process candles - handle both direct array and object with candles property
    let candles = [];
    if (Array.isArray(candlesData)) {
      candles = candlesData.slice();
      console.log('Candles data is direct array');
    } else if (candlesData && Array.isArray(candlesData.candles) && candlesData.candles.length > 0) {
      candles = candlesData.candles.slice();
      console.log('Candles data has candles property');
    } else {
      throw new Error('Invalid candles data structure');
    }
    
    if (candles.length > 0) {

      // Sort by time
      candles.sort((a, b) => a.time - b.time);
      
      console.log(`Loaded ${candles.length} candles, first time: ${candles[0].time}, last time: ${candles[candles.length-1].time}`);
      
      // Validate all required fields
      const validCandles = candles.every(c => 
        c.time && typeof c.open === 'number' && typeof c.high === 'number' && 
        typeof c.low === 'number' && typeof c.close === 'number'
      );
      
      if (!validCandles) {
        throw new Error('Candles have invalid data structure');
      }
      
      if (candleSeries) {
        candleSeries.setData(candles);
        if (chart && chart.timeScale) {
          chart.timeScale().fitContent();
        }
        // Mark chart as ready after first successful data load
        isChartReady = true;
        console.log('Chart is now ready for live updates');
      } else {
        throw new Error('Chart series not initialized');
      }

      // Get last price from response or from last candle
      const lastPrice = candlesData.last_price || candles[candles.length - 1].close;
      if (lastPriceEl) lastPriceEl.textContent = lastPrice.toFixed(2);
      if (lastUpdatedEl) lastUpdatedEl.textContent = new Date().toLocaleTimeString();

      const lastTime = candles[candles.length - 1].time;
      lastCandle = candles[candles.length - 1];
      
      // Set price lines if we have levels
      if (levelsData && levelsData.entry) {
        levelsData.last_candle_time = lastTime;
        setPriceLines(levelsData);
      }
      
      setStatus(`✓ Loaded ${candles.length} candles for ${symbol}`);
      console.log(`Chart is now LIVE with ${candles.length} candles!`);
      
      // Clear any previous error states
      if (statusText) {
        statusText.style.color = '';
      }
    } else {
      setStatus(`✗ No candle data available for ${symbol}`);
      console.error('No candles found after processing');
    }

    // Update levels card
    if (levelsData && levelsData.direction) {
      updateLevelsCard(levelsData);
      console.log('Levels updated successfully');
      // Update status to show live mode
      setStatus(`🟢 LIVE | ${symbol} | ${levelsData.direction} @ ${levelsData.confidence.toFixed(1)}% | Auto-refresh: ON`);
    } else {
      setStatus(`✗ Levels not available for ${symbol}`);
      console.error('Invalid levels data:', levelsData);
    }
    
  } catch (error) {
    console.error('Error loading data:', error);
    setStatus(`✗ Error: ${error.message}`);
    isChartReady = false;
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
      
      setStatus(`✓ ${levelsData.direction} signal generated - Entry: ${levelsData.entry.toFixed(2)}`);
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
    console.log("Auto-refreshing candles for live data...");
    loadData(activeSymbol);
  }, 5 * 60 * 1000); // 5 minutes
  
  console.log("✓ Auto-refresh enabled (every 5 minutes)");
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

  // Delay data loading to ensure chart is ready
  setTimeout(() => {
    console.log("Loading initial data and starting live mode...");
    loadData(activeSymbol);
    connectStream(activeSymbol);
    startAutoRefresh();
  }, 100);
});

export const quantTheme = {
  background: "#05080d",
  panel: "#0b1119",
  panelAlt: "#101823",
  panelElevated: "#131d2a",
  gridline: "#1f2b3a",
  axis: "#718098",
  text: "#e6edf7",
  muted: "#8b99ad",
  positive: "#2fd48a",
  positiveSoft: "rgba(47, 212, 138, 0.16)",
  negative: "#ff5d73",
  negativeSoft: "rgba(255, 93, 115, 0.16)",
  warning: "#f2b84b",
  neutral: "#a7b1c2",
  benchmark: "#8d96ff",
  strategy: "#32d3d3",
  volume: "rgba(128, 145, 170, 0.28)",
  buy: "#35d98c",
  sell: "#ff637d",
  mcOuter: "rgba(141, 150, 255, 0.14)",
  mcInner: "rgba(50, 211, 211, 0.18)",
  mcMedian: "#32d3d3",
};

export const plotlyLayoutDefaults: any = {
  paper_bgcolor: quantTheme.panel,
  plot_bgcolor: quantTheme.panel,
  font: { color: quantTheme.text, size: 11 },
  margin: { l: 48, r: 20, t: 18, b: 36 },
  xaxis: {
    gridcolor: quantTheme.gridline,
    zerolinecolor: quantTheme.gridline,
    tickfont: { color: quantTheme.axis },
  },
  yaxis: {
    gridcolor: quantTheme.gridline,
    zerolinecolor: quantTheme.gridline,
    tickfont: { color: quantTheme.axis },
  },
  legend: {
    orientation: "h",
    x: 0,
    y: 1.1,
    font: { color: quantTheme.muted, size: 11 },
  },
};

export const plotlyConfig: any = {
  displaylogo: false,
  responsive: true,
  modeBarButtonsToRemove: [
    "select2d",
    "lasso2d",
    "autoScale2d",
    "toggleSpikelines",
    "hoverClosestCartesian",
    "hoverCompareCartesian",
  ],
};

/**
 * پالت رنگی و استایل دارک‌مود اختصاصی چارت نهایت‌نگر (TradingView Style)
 * سازگار با KlineCharts v10.0.3
 */

export const nahayatNegarDarkTheme = {
  grid: {
    show: true,
    horizontal: {
      show: true,
      size: 1,
      color: '#242832',
      style: 'dashed' as const,
      dashedValue: [2, 2]
    },
    vertical: {
      show: true,
      size: 1,
      color: '#242832',
      style: 'dashed' as const,
      dashedValue: [2, 2]
    }
  },
  candle: {
    type: 'candle_solid' as const,
    bar: {
      upColor: '#089981',
      downColor: '#f23645',
      noChangeColor: '#888888',
      upBorderColor: '#089981',
      downBorderColor: '#f23645',
      noChangeBorderColor: '#888888',
      upWickColor: '#089981',
      downWickColor: '#f23645',
      noChangeWickColor: '#888888'
    },
    area: {
      lineSize: 2,
      lineColor: '#2962ff',
      value: 'close' as const,
      fillColor: [
        { offset: 0, color: 'rgba(41, 98, 255, 0.28)' },
        { offset: 1, color: 'rgba(41, 98, 255, 0.00)' }
      ]
    },
    priceMark: {
      show: true,
      last: {
        show: true,
        upColor: '#089981',
        downColor: '#f23645',
        noChangeColor: '#888888',
        line: {
          show: true,
          style: 'dashed' as const,
          dashedValue: [3, 3],
          size: 1
        },
        text: {
          show: true,
          size: 11,
          family: 'Vazirmatn',
          color: '#ffffff'
        }
      },
      high: {
        show: true,
        color: '#d1d4dc',
        text: { size: 10, family: 'Vazirmatn' }
      },
      low: {
        show: true,
        color: '#d1d4dc',
        text: { size: 10, family: 'Vazirmatn' }
      }
    },
    tooltip: {
      showRule: 'always' as const,
      showType: 'standard' as const,
      legend: {
        template: '{time}  باز: {open}  بیشترین: {high}  کمترین: {low}  بسته: {close}  حجم: {volume}'
      }
    }
  },
  indicator: {
    ohlc: {
      upColor: '#089981',
      downColor: '#f23645',
      noChangeColor: '#888888'
    },
    lines: [
      { style: 'solid' as const, size: 1.5, color: '#2962ff' },
      { style: 'solid' as const, size: 1.5, color: '#ff9800' },
      { style: 'solid' as const, size: 1.5, color: '#ab47bc' },
      { style: 'solid' as const, size: 1.5, color: '#00bcd4' },
      { style: 'solid' as const, size: 1.5, color: '#e91e63' }
    ],
    tooltip: {
      showRule: 'always' as const,
      showType: 'standard' as const
    }
  },
  xAxis: {
    show: true,
    size: 'auto' as const,
    axisLine: {
      show: true,
      color: '#2a2e39',
      size: 1
    },
    tickText: {
      show: true,
      color: '#787b86',
      size: 11,
      family: 'Vazirmatn'
    },
    tickLine: {
      show: true,
      size: 1,
      length: 3,
      color: '#2a2e39'
    }
  },
  yAxis: {
    show: true,
    size: 'auto' as const,
    axisLine: {
      show: true,
      color: '#2a2e39',
      size: 1
    },
    tickText: {
      show: true,
      color: '#787b86',
      size: 11,
      family: 'Vazirmatn'
    },
    tickLine: {
      show: true,
      size: 1,
      length: 3,
      color: '#2a2e39'
    }
  },
  crosshair: {
    show: true,
    horizontal: {
      show: true,
      line: {
        show: true,
        style: 'dashed' as const,
        dashedValue: [3, 3],
        size: 1,
        color: '#787b86'
      },
      text: {
        show: true,
        color: '#ffffff',
        size: 11,
        family: 'Vazirmatn',
        backgroundColor: '#2a2e39'
      }
    },
    vertical: {
      show: true,
      line: {
        show: true,
        style: 'dashed' as const,
        dashedValue: [3, 3],
        size: 1,
        color: '#787b86'
      },
      text: {
        show: true,
        color: '#ffffff',
        size: 11,
        family: 'Vazirmatn',
        backgroundColor: '#2a2e39'
      }
    }
  },
  overlay: {
    point: {
      color: '#2962ff',
      borderColor: 'rgba(41, 98, 255, 0.4)',
      borderSize: 1,
      radius: 4,
      activeColor: '#2962ff',
      activeBorderColor: '#ffffff',
      activeBorderSize: 2,
      activeRadius: 5
    },
    line: {
      style: 'solid' as const,
      size: 1.5,
      color: '#2962ff'
    },
    polygon: {
      style: 'solid' as const,
      color: 'rgba(41, 98, 255, 0.15)',
      borderColor: '#2962ff',
      borderSize: 1.5
    },
    circle: {
      style: 'solid' as const,
      color: 'rgba(41, 98, 255, 0.15)',
      borderColor: '#2962ff',
      borderSize: 1.5
    },
    text: {
      color: '#d1d4dc',
      size: 12,
      family: 'Vazirmatn'
    }
  }
};

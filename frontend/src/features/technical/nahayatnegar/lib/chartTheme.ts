/**
 * Nahayat Negar (TradingView style) Theme for KLineCharts
 * Matches color palette, fonts (Vazirmatn), and grid styling of nahayatnegar.com/tv
 */

export const nahayatNegarDarkTheme = {
  grid: {
    show: true,
    horizontal: {
      show: true,
      size: 1,
      color: '#242832',
      style: 'dashed',
      dashedValue: [2, 2]
    },
    vertical: {
      show: true,
      size: 1,
      color: '#242832',
      style: 'dashed',
      dashedValue: [2, 2]
    }
  },
  candle: {
    type: 'candle_solid',
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
      value: 'close',
      backgroundColor: [
        { offset: 0, color: 'rgba(41, 98, 255, 0.28)' },
        { offset: 1, color: 'rgba(41, 98, 255, 0.02)' }
      ]
    },
    priceMark: {
      show: true,
      high: {
        show: true,
        color: '#787b86',
        textMargin: 5,
        textSize: 10,
        textFamily: 'Vazirmatn, sans-serif'
      },
      low: {
        show: true,
        color: '#787b86',
        textMargin: 5,
        textSize: 10,
        textFamily: 'Vazirmatn, sans-serif'
      },
      last: {
        show: true,
        upColor: '#089981',
        downColor: '#f23645',
        noChangeColor: '#888888',
        line: {
          show: true,
          style: 'dashed',
          dashedValue: [4, 4],
          size: 1
        },
        text: {
          show: true,
          style: 'fill',
          size: 12,
          paddingLeft: 4,
          paddingTop: 4,
          paddingRight: 4,
          paddingBottom: 4,
          borderColor: 'transparent',
          borderRadius: 2,
          color: '#ffffff',
          family: 'Vazirmatn, sans-serif'
        }
      }
    },
    tooltip: {
      showRule: 'always',
      showType: 'standard',
      labels: ['زمان: ', 'باز: ', 'بسته: ', 'بیشترین: ', 'کمترین: ', 'حجم: '],
      values: null,
      defaultValue: 'n/a',
      rect: {
        paddingLeft: 4,
        paddingRight: 4,
        paddingTop: 4,
        paddingBottom: 4,
        offsetLeft: 8,
        offsetTop: 8,
        offsetRight: 8,
        borderRadius: 4,
        borderSize: 1,
        borderColor: '#2a2e39',
        color: 'rgba(19, 23, 34, 0.85)'
      },
      text: {
        size: 12,
        family: 'Vazirmatn, sans-serif',
        color: '#d1d4dc',
        marginLeft: 8,
        marginTop: 6,
        marginRight: 8,
        marginBottom: 0
      }
    }
  },
  xAxis: {
    show: true,
    size: 'auto',
    axisLine: {
      show: true,
      color: '#2a2e39',
      size: 1
    },
    tickText: {
      show: true,
      color: '#787b86',
      family: 'Vazirmatn, sans-serif',
      size: 11,
      marginStart: 4,
      marginEnd: 4
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
    size: 'auto',
    position: 'right',
    type: 'normal',
    inside: false,
    axisLine: {
      show: true,
      color: '#2a2e39',
      size: 1
    },
    tickText: {
      show: true,
      color: '#787b86',
      family: 'Vazirmatn, sans-serif',
      size: 11,
      marginStart: 4,
      marginEnd: 4
    },
    tickLine: {
      show: true,
      size: 1,
      length: 3,
      color: '#2a2e39'
    }
  },
  separator: {
    size: 1,
    color: '#2a2e39',
    fill: true,
    activeBackgroundColor: 'rgba(41, 98, 255, 0.15)'
  },
  crosshair: {
    show: true,
    horizontal: {
      show: true,
      line: {
        show: true,
        style: 'dashed',
        dashedValue: [4, 4],
        size: 1,
        color: '#787b86'
      },
      text: {
        show: true,
        style: 'fill',
        color: '#ffffff',
        size: 11,
        family: 'Vazirmatn, sans-serif',
        paddingLeft: 4,
        paddingRight: 4,
        paddingTop: 2,
        paddingBottom: 2,
        borderSize: 1,
        borderColor: '#2a2e39',
        borderRadius: 2,
        backgroundColor: '#2a2e39'
      }
    },
    vertical: {
      show: true,
      line: {
        show: true,
        style: 'dashed',
        dashedValue: [4, 4],
        size: 1,
        color: '#787b86'
      },
      text: {
        show: true,
        style: 'fill',
        color: '#ffffff',
        size: 11,
        family: 'Vazirmatn, sans-serif',
        paddingLeft: 4,
        paddingRight: 4,
        paddingTop: 2,
        paddingBottom: 2,
        borderSize: 1,
        borderColor: '#2a2e39',
        borderRadius: 2,
        backgroundColor: '#2a2e39'
      }
    }
  },
  overlay: {
    point: {
      color: '#2962ff',
      borderColor: 'rgba(41, 98, 255, 0.35)',
      borderSize: 1,
      radius: 4,
      activeColor: '#2962ff',
      activeBorderColor: 'rgba(41, 98, 255, 0.5)',
      activeBorderSize: 2,
      activeRadius: 5
    },
    line: {
      style: 'solid',
      smooth: false,
      color: '#2962ff',
      size: 1,
      dashedValue: [2, 2]
    },
    rect: {
      style: 'fill',
      color: 'rgba(41, 98, 255, 0.15)',
      borderColor: '#2962ff',
      borderSize: 1,
      borderRadius: 0
    },
    text: {
      color: '#d1d4dc',
      size: 12,
      family: 'Vazirmatn, sans-serif',
      marginLeft: 2,
      marginRight: 2,
      marginTop: 2,
      marginBottom: 2
    }
  }
};

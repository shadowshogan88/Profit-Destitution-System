'use strict';

$(document).ready(function () {

  // Column chart
  if ($('#sales_chart').length > 0) {
    var columnCtx = document.getElementById("sales_chart"),
      columnConfig = {
        colors: ['#7638ff', '#fda600'],
        series: [
          {
            name: "Received",
            type: "column",
            data: [70, 150, 80, 180]
          },
          {
            name: "Pending",
            type: "column",
            data: [23, 42, 35]
          }
        ],
        chart: {
          type: 'bar',
          fontFamily: 'Roboto, sans-serif',
          height: 150,
          toolbar: {
            show: false
          }
        },
        plotOptions: {
          bar: {
            horizontal: false,
            columnWidth: '60%',
            endingShape: 'rounded'
          },
        },
        dataLabels: {
          enabled: false
        },
        stroke: {
          show: true,
          width: 2,
          colors: ['transparent']
        },
        xaxis: {
          categories: ['Jan', 'Feb', 'Mar', 'Apr'],
        },
        yaxis: {
          title: {
            text: '$ (thousands)'
          }
        },
        fill: {
          opacity: 1
        },
        tooltip: {
          y: {
            formatter: function (val) {
              return "$ " + val + " thousands"
            }
          }
        }
      };
    var columnChart = new ApexCharts(columnCtx, columnConfig);
    columnChart.render();
  }

  // Bar Chart
  if ($('#s-col').length > 0) {
    var sCol = {
      chart: {
        height: 190,
        type: 'bar',
        toolbar: {
          show: false,
        }
      },
      plotOptions: {
        bar: {
          horizontal: false,
          columnWidth: '80%',
          borderRadius: 5,
          endingShape: 'rounded', // This rounds the top edges of the bars
        },
      },
      colors: ['#FFAD6A'],
      dataLabels: {
        enabled: false
      },
      stroke: {
        show: true,
        width: 2,
        colors: ['transparent']
      },

      series: [{
        name: 'Inprogress',
        data: [19]
      }, {
        name: 'Active',
        data: [89]
      },
      {
        name: 'Completed',
        data: [39]
      }],
      xaxis: {
        categories: ['15 Jan', '16 Jan', '17 Jan'],
        labels: {
          style: {
            colors: '#0C1C29',
            fontSize: '12px',
          }
        }
      },
      yaxis: {
        labels: {
          offsetX: -15,
          style: {
            colors: '#6D777F',
            fontSize: '14px',
          }
        }
      },
      grid: {
        borderColor: '#CED2D4',
        strokeDashArray: 5,
        padding: {
          left: -8,
          right: -15,
        },
      },
      fill: {
        opacity: 1
      },
      tooltip: {
        y: {
          formatter: function (val) {
            return "" + val + "%"
          }
        }
      }
    }

    var chart = new ApexCharts(
      document.querySelector("#s-col"),
      sCol
    );

    chart.render();
  }

   /*chart-bar-stacked*/
   var chart = c3.generate({
    bindto: '#chart-bar-stacked',
    size: {
        height: 90   // small height like screenshot
    },
    data: {
        columns: [
            ['data1']
        ],
        type: 'bar',
        colors: {
            data1: '#20b8c9' // teal color like image
        }
    },
    axis: {
        x: {
            show: false
        },
        y: {
            show: false
        }
    },
    bar: {
        width: 10   // thin bars
    },
    legend: {
        show: false
    },
    grid: {
        x: { show: false },
        y: { show: false }
    },
    padding: {
        top: 5,
        bottom: 5,
        left: 0,
        right: 0
    },
    tooltip: {
        show: false
    }
});

// Revenue Chart
if ($('#revenue-chart').length > 0) {
  var options = {
    series: [{
    name: 'Order',
    data: [4, 2, 3.5, 3, 2, 2.8, 3.2]
  }],
  chart: {
    height: 220,
    type: 'bar',
    toolbar: {
      show: false
    }
  },
  plotOptions: {
    bar: {
      borderRadius: 10,
      dataLabels: {
        position: 'top', // top, center, bottom
      },
    }
  },
  dataLabels: {
    enabled: true,
    formatter: function (val) {
      return val + "%";
    },
    offsetY: -20,
    style: {
      fontSize: '12px',
      colors: ["#304758"]
    }
  },
  
  xaxis: {
    categories: ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
    axisBorder: {
      show: false
    },
    axisTicks: {
      show: false
    },
    crosshairs: {
      fill: {
        type: 'gradient',
        gradient: {
          colorFrom: '#13B5C9',
          colorTo: '#F9C126',
          stops: [0, 100],
          opacityFrom: 0.4,
          opacityTo: 0.5,
        }
      }
    },
    tooltip: {
      enabled: true,
    }
  },
  yaxis: {
    axisBorder: {
      show: false
    },
    axisTicks: {
      show: true,
    },
    labels: {
      show: true,
      formatter: function (val) {
        return val + "k";
      }
    },
    
  
  },
  colors: ['#0D76E1']
  };

  var chart = new ApexCharts(document.querySelector("#revenue-chart"), options);
  chart.render();
}

// Revenue Chart-1
if ($('#revenue-chart-1').length > 0) {
  var options = {
    series: [{
      name: 'Categories',
      data: [60, 20, 12, 18] 
    }],
    chart: {
      height: 290,
      type: 'bar',
      toolbar: { show: false }
    },
    plotOptions: {
      bar: {
        borderRadius: 20,
        borderRadiusApplication: 'around',
        distributed: true, 
        columnWidth: '85%', // Adjusted to show a small gap between background bars
        colors: {
          backgroundBarColors: ['#F2F2F2'], // This creates the full height light bg
          backgroundBarOpacity: 0.4,
          backgroundBarRadius: 20,
        }
      }
    },
    // Vibrant colors from your screenshot
    colors: ['#13B5C9', '#F9C126', '#FF7EE9', '#14B51D'], 
    fill: {
      type: 'gradient',
      gradient: {
        shade: 'light',
        type: "vertical",
        shadeIntensity: 0.3,
        opacityFrom: 1,
        opacityTo: 0.6, // Keeps the bar color visible but slightly faded at the bottom
        stops: [0, 100]
      }
    },
    dataLabels: {
      enabled: false 
    },
    xaxis: {
      categories: ["", "", "", ""],
      axisBorder: { show: false },
      axisTicks: { show: false },
      labels: {
        style: {
          fontSize: '14px',
          fontWeight: 600,
          colors: '#666'
        }
      }
    },
    yaxis: { show: false },
    grid: { show: false },
    legend: { show: false }
  };

  var chart = new ApexCharts(document.querySelector("#revenue-chart-1"), options);
  chart.render();
}

// Bar chart 1 
if ($('#bar-chart-1').length > 0) {
  var options = {
    series: [{
      name: 'Order',
      // Values representing the width of each segment
      data: [214, 192, 151, 120, 98] 
    }],
    chart: {
      type: 'bar',
      height: 178, // Slim height to look like a progress bar
      toolbar: { show: false },
      sparkline: { enabled: true } // Removes all extra space/labels for a clean look
    },
    plotOptions: {
      bar: {
        horizontal: true,
        distributed: true, // Allows each segment to have a unique color
        barHeight: '90%',
        borderRadius: 8,
        borderRadiusApplication: 'around',
        // This removes the gap between the bars to make it look like one continuous line
        dataLabels: { position: 'top' } 
      }
    },
    // Progressively lighter teal shades to create the "light-by-light fade"
    colors: [
      '#3EBCC9', // Evening Dress (Darkest)
      '#77CCD5', // Blouse
      '#9DDBE2', // Dress Shorten
      '#BDE7EC', // Long Coat
      '#DFF3F6'  // Suit 2pc (Lightest)
    ],
    fill: {
      type: 'solid',
      opacity: 1
    },
    grid: {
      show: false,
      padding: {
        left: 0,
        right: 0,
        top: 0,
        bottom: 0
      }
    },
    xaxis: {
      labels: { show: false },
      axisBorder: { show: false },
      axisTicks: { show: false }
    },
    yaxis: {
      labels: { show: false }
    },
    legend: {
      show: false
    },
    tooltip: {
      enabled: false
    }
  };

  var chart = new ApexCharts(document.querySelector("#bar-chart-1"), options);
  chart.render();
}

// Statistic Chart
if ($('#statistic-chart').length > 0) {
  const options = {
    series: [{
      name: 'Orders',
      data: [40, 35, 45, 44, 63, 50, 84, 72, 68, 60, 55, 62]
    }],

    chart: {
      height: 260,
      type: 'area',
      zoom: { enabled: false },
      toolbar: { show: false },
      animations: {
        enabled: true,
        easing: 'easeinout',
        speed: 800
      }
    },

    stroke: {
      curve: 'smooth',   // 🔥 wave effect
      width: 2           // thin clean line
    },

    markers: {
      size: 0,
      hover: {
        size: 6           // single dot on hover
      }
    },

    tooltip: {
      enabled: true,
      marker: { show: false },
      y: {
        formatter: function (val) {
          return '$' + val;
        }
      }
    },

    dataLabels: {
      enabled: false
    },

    fill: {
      type: "gradient",
      gradient: {
        shadeIntensity: 1,
        opacityFrom: 0.35,
        opacityTo: 0,
        stops: [0, 90, 100]
      }
    },

    grid: {
      borderColor: '#eaeaea',
      strokeDashArray: 4,          // dotted vertical grid like screenshot
      xaxis: {
        lines: { show: true }
      },
      yaxis: {
        lines: { show: false }
      },
      padding: {
        top: 0,
        left: 10,
        right: 10,
        bottom: 0
      }
    },

    xaxis: {
      categories: ['10:00', '11:00', '12:00', '13:00', '14:00', '15:00',
                   '16:00', '17:00', '18:00', '19:00', '20:00', '21:00'],
      axisBorder: { show: false },
      axisTicks: { show: false },
      labels: {
        style: {
          colors: '#8c8c8c',
          fontSize: '11px'
        }
      }
    },

    yaxis: {
      labels: { show: false }
    },

    colors: ['#22c1dc'] // teal-blue wave color
  };

  const chart = new ApexCharts(
    document.querySelector("#statistic-chart"),
    options
  );
  chart.render();
}

// Order Chart
if ($('#order-chart').length > 0) {

  var options = {
    series: [14, 23, 21, 17],

    chart: {
      type: 'polarArea',
      height: 350,
      toolbar: { show: false }
    },

    colors: [
      '#13b5c9',
      '#2088ee',
      '#ffa5da',
      '#fdb600'
    ],

    plotOptions: {
      polarArea: {
        rings: {
          strokeColor: '#E5E7EB',
          strokeWidth: 1
        },
        spokes: {
          strokeColor: '#E5E7EB'
        }
      }
    },

    labels: [],
    legend: { show: false },
    dataLabels: { enabled: false },

    tooltip: {
      enabled: true,
      x: { show: false },
      y: {
        formatter: val => val,
        title: { formatter: () => '' }
      }
    },

    stroke: {
      colors: ['#fff']
    },

    fill: {
      opacity: 0.85
    },

    yaxis: {
      show: false
    }
  };

  new ApexCharts(
    document.querySelector("#order-chart"),
    options
  ).render();
}

// Revenue Chart-2
if ($('#bar-chart-2').length > 0) {
  var options = {
    series: [{
      name: 'Categories',
      data: [100, 50, 60, 30,80] 
    }],
    chart: {
      height: 50,      
      width: 90, 
      type: 'bar',
      toolbar: { show: false },
      sparkline: { enabled: true } 
    },
    plotOptions: {
      bar: {
        // Set to 20 for a full pill shape. 
        // If it looks uneven, reduce to 10-15 due to the 50px chart height.
        borderRadius: 3, 
        borderRadiusApplication: 'around',
        distributed: true, 
        columnWidth: '80%', 
      }
    },
    fill: {
      type: 'solid',
      opacity: 1
    },
    colors: ['#13B5C9', '#13B5C9', '#13B5C9', '#13B5C9','#13B5C9'], 
    stroke: {
      show: true,
      // Reduced to 3 to keep the bars thick enough to show the radius clearly
      width: 2,         
      colors: ['#fff']  
    },
    dataLabels: {
      enabled: false 
    },
    grid: { 
      padding: {
        left: 5,
        right: 5
      }
    },
    tooltip: { enabled: true }
  };

  var chart = new ApexCharts(document.querySelector("#bar-chart-2"), options);
  chart.render();
}

// Revenue Chart-3
if ($('#bar-chart-3').length > 0) {
  var options = {
    series: [{
      name: 'Categories',
      data: [70, 40, 65, 30,80] 
    }],
    chart: {
      height: 50,      
      width: 90, 
      type: 'bar',
      toolbar: { show: false },
      sparkline: { enabled: true } 
    },
    plotOptions: {
      bar: {
        // Set to 20 for a full pill shape. 
        // If it looks uneven, reduce to 10-15 due to the 50px chart height.
        borderRadius: 3, 
        borderRadiusApplication: 'around',
        distributed: true, 
        columnWidth: '80%', 
      }
    },
    fill: {
      type: 'solid',
      opacity: 1
    },
    colors: ['#F9C126', '#F9C126', '#F9C126', '#F9C126','#F9C126'], 
    stroke: {
      show: true,
      // Reduced to 3 to keep the bars thick enough to show the radius clearly
      width: 2,         
      colors: ['#fff']  
    },
    dataLabels: {
      enabled: false 
    },
    grid: { 
      padding: {
        left: 5,
        right: 5
      }
    },
    tooltip: { enabled: true }
  };

  var chart = new ApexCharts(document.querySelector("#bar-chart-3"), options);
  chart.render();
}

// Revenue Chart-4
if ($('#bar-chart-4').length > 0) {
  var options = {
    series: [{
      name: 'Categories',
      data: [100, 50, 60, 30,80] 
    }],
    chart: {
      height: 50,      
      width: 90, 
      type: 'bar',
      toolbar: { show: false },
      sparkline: { enabled: true } 
    },
    plotOptions: {
      bar: {
        // Set to 20 for a full pill shape. 
        // If it looks uneven, reduce to 10-15 due to the 50px chart height.
        borderRadius: 3, 
        borderRadiusApplication: 'around',
        distributed: true, 
        columnWidth: '80%', 
      }
    },
    fill: {
      type: 'solid',
      opacity: 1
    },
    colors: ['#14B51D', '#14B51D', '#14B51D', '#14B51D','#14B51D'], 
    stroke: {
      show: true,
      // Reduced to 3 to keep the bars thick enough to show the radius clearly
      width: 2,         
      colors: ['#fff']  
    },
    dataLabels: {
      enabled: false 
    },
    grid: { 
      padding: {
        left: 5,
        right: 5
      }
    },
    tooltip: { enabled: true }
  };

  var chart = new ApexCharts(document.querySelector("#bar-chart-4"), options);
  chart.render();
}


});


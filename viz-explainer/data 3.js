window.PILOT402_EXPLAINER_DATA = {
  "generatedAt": "2026-05-06T00:57:14.801Z",
  "provenance": {
    "S1": "logs/m3f_results.md + results/scenario_sweep/S1",
    "S2": "logs/m3f_results.md + results/scenario_sweep/S2",
    "S3": "logs/m3f_results.md + results/scenario_sweep_s3promo_v2"
  },
  "providers": {
    "P-cheap": {
      "label": "Cheap",
      "model": "Qwen3-8B",
      "cost": 0.0005,
      "signal": "省钱但能力有限",
      "note": "适合作为低成本保底臂。",
      "quality": 0.61,
      "reliability": 1
    },
    "P-mid": {
      "label": "Mid",
      "model": "GPT-5.4-mini + BM25",
      "cost": 0.002,
      "signal": "平衡点",
      "note": "静态市场里的强固定基线。",
      "quality": 0.82,
      "reliability": 1
    },
    "P-premium": {
      "label": "Premium",
      "model": "GPT-5.4 + tools",
      "cost": 0.01,
      "signal": "高质量高价格",
      "note": "S3 降价后变成机会臂。",
      "quality": 0.87,
      "reliability": 1
    },
    "P-adv": {
      "label": "Adversarial",
      "model": "GPT-5.4-mini + BM25",
      "cost": 0.002,
      "signal": "看似可信但会错",
      "note": "价格和栈都像 P-mid，只能靠反馈识别。",
      "quality": 0.52,
      "reliability": 0.96
    },
    "P-flaky": {
      "label": "Flaky",
      "model": "GPT-5.4-mini + BM25",
      "cost": 0.002,
      "signal": "成功时不错但会 timeout",
      "note": "40% timeout，付款不可逆。",
      "quality": 0.49,
      "reliability": 0.6
    }
  },
  "scenarios": {
    "S1": {
      "label": "S1 静态市场",
      "short": "baseline",
      "source": "results/scenario_sweep/S1",
      "eventRound": null,
      "eventWindow": null,
      "summary": "无市场冲击，用来对照正常学习成本和稳定选择分布。"
    },
    "S2": {
      "label": "S2 Mid outage",
      "short": "outage",
      "source": "results/scenario_sweep/S2",
      "eventRound": 3000,
      "eventWindow": [
        3000,
        5500
      ],
      "summary": "P-mid 在 3000-5500 轮注入 30% timeout。"
    },
    "S3": {
      "label": "S3 Premium promo",
      "short": "promo",
      "source": "results/scenario_sweep_s3promo_v2",
      "eventRound": 1000,
      "eventWindow": [
        1000,
        10000
      ],
      "summary": "P-premium 从 $0.01 降到 $0.002。"
    }
  },
  "headline": {
    "S1": [
      {
        "policy": "PA-DCT",
        "cumPA": 5512,
        "cumStd": 54,
        "meanQ": 0.797,
        "roi": 377,
        "regret": 1325,
        "spend": 21.11,
        "failPct": 0.4
      },
      {
        "policy": "AlwaysMid",
        "cumPA": 5831,
        "cumStd": 29,
        "meanQ": 0.819,
        "roi": 410,
        "regret": 1006,
        "spend": 20,
        "failPct": 0
      },
      {
        "policy": "AlwaysCheap",
        "cumPA": 5164,
        "cumStd": 23,
        "meanQ": 0.61,
        "roi": 1220,
        "regret": 1673,
        "spend": 5,
        "failPct": 0
      },
      {
        "policy": "AlwaysPremium",
        "cumPA": -3887,
        "cumStd": 3,
        "meanQ": 0.866,
        "roi": 87,
        "regret": 10725,
        "spend": 50,
        "failPct": 0
      },
      {
        "policy": "BudgetRule",
        "cumPA": -82,
        "cumStd": 14,
        "meanQ": 0.831,
        "roi": 208,
        "regret": 6919,
        "spend": 40,
        "failPct": 0
      },
      {
        "policy": "Oracle",
        "cumPA": 6837,
        "cumStd": 27,
        "meanQ": 0.901,
        "roi": 561,
        "regret": 0,
        "spend": 16.05,
        "failPct": 0
      }
    ],
    "S2": [
      {
        "policy": "PA-DCT",
        "cumPA": 5147,
        "cumStd": 80,
        "meanQ": 0.761,
        "roi": 356,
        "regret": 1662,
        "spend": 21.37,
        "failPct": 1.9
      },
      {
        "policy": "AlwaysMid",
        "cumPA": 5069,
        "cumStd": 37,
        "meanQ": 0.757,
        "roi": 379,
        "regret": 1740,
        "spend": 20,
        "failPct": 7.5
      },
      {
        "policy": "AlwaysCheap",
        "cumPA": 5164,
        "cumStd": 23,
        "meanQ": 0.61,
        "roi": 1220,
        "regret": 1645,
        "spend": 5,
        "failPct": 0
      },
      {
        "policy": "AlwaysPremium",
        "cumPA": -3887,
        "cumStd": 3,
        "meanQ": 0.866,
        "roi": 87,
        "regret": 10696,
        "spend": 50,
        "failPct": 0
      },
      {
        "policy": "BudgetRule",
        "cumPA": -408,
        "cumStd": 18,
        "meanQ": 0.769,
        "roi": 192,
        "regret": 7217,
        "spend": 40,
        "failPct": 7.5
      },
      {
        "policy": "Oracle",
        "cumPA": 6809,
        "cumStd": 25,
        "meanQ": 0.901,
        "roi": 551,
        "regret": 0,
        "spend": 16.34,
        "failPct": 0
      }
    ],
    "S3": [
      {
        "policy": "PA-DCT",
        "cumPA": 5911,
        "cumStd": 51,
        "meanQ": 0.831,
        "roi": 429,
        "regret": 1206,
        "spend": 19.38,
        "failPct": 0.4
      },
      {
        "policy": "AlwaysMid",
        "cumPA": 5831,
        "cumStd": 29,
        "meanQ": 0.819,
        "roi": 410,
        "regret": 1286,
        "spend": 20,
        "failPct": 0
      },
      {
        "policy": "AlwaysCheap",
        "cumPA": 5164,
        "cumStd": 23,
        "meanQ": 0.61,
        "roi": 1220,
        "regret": 1952,
        "spend": 5,
        "failPct": 0
      },
      {
        "policy": "AlwaysPremium",
        "cumPA": 3112,
        "cumStd": 19,
        "meanQ": 0.865,
        "roi": 309,
        "regret": 4004,
        "spend": 28,
        "failPct": 0
      },
      {
        "policy": "BudgetRule",
        "cumPA": 3064,
        "cumStd": 17,
        "meanQ": 0.859,
        "roi": 307,
        "regret": 4053,
        "spend": 28,
        "failPct": 0
      },
      {
        "policy": "Oracle",
        "cumPA": 7117,
        "cumStd": 24,
        "meanQ": 0.906,
        "roi": 722,
        "regret": 0,
        "spend": 12.54,
        "failPct": 0
      }
    ]
  },
  "armShares": {
    "S1": [
      {
        "round": 100,
        "shares": {
          "P-cheap": 0.2043,
          "P-mid": 0.4757,
          "P-premium": 0.1018,
          "P-adv": 0.159,
          "P-flaky": 0.0592
        }
      },
      {
        "round": 300,
        "shares": {
          "P-cheap": 0.1845,
          "P-mid": 0.654,
          "P-premium": 0.0513,
          "P-adv": 0.1012,
          "P-flaky": 0.009
        }
      },
      {
        "round": 500,
        "shares": {
          "P-cheap": 0.1653,
          "P-mid": 0.704,
          "P-premium": 0.043,
          "P-adv": 0.0803,
          "P-flaky": 0.0073
        }
      },
      {
        "round": 700,
        "shares": {
          "P-cheap": 0.139,
          "P-mid": 0.744,
          "P-premium": 0.0422,
          "P-adv": 0.0662,
          "P-flaky": 0.0087
        }
      },
      {
        "round": 900,
        "shares": {
          "P-cheap": 0.1223,
          "P-mid": 0.7743,
          "P-premium": 0.0345,
          "P-adv": 0.0597,
          "P-flaky": 0.0092
        }
      },
      {
        "round": 1100,
        "shares": {
          "P-cheap": 0.131,
          "P-mid": 0.7798,
          "P-premium": 0.0328,
          "P-adv": 0.0455,
          "P-flaky": 0.0108
        }
      },
      {
        "round": 1300,
        "shares": {
          "P-cheap": 0.1282,
          "P-mid": 0.775,
          "P-premium": 0.033,
          "P-adv": 0.0523,
          "P-flaky": 0.0115
        }
      },
      {
        "round": 1500,
        "shares": {
          "P-cheap": 0.1258,
          "P-mid": 0.7773,
          "P-premium": 0.034,
          "P-adv": 0.0557,
          "P-flaky": 0.0072
        }
      },
      {
        "round": 1700,
        "shares": {
          "P-cheap": 0.1137,
          "P-mid": 0.7933,
          "P-premium": 0.0298,
          "P-adv": 0.0525,
          "P-flaky": 0.0107
        }
      },
      {
        "round": 1900,
        "shares": {
          "P-cheap": 0.1258,
          "P-mid": 0.779,
          "P-premium": 0.0337,
          "P-adv": 0.0495,
          "P-flaky": 0.012
        }
      },
      {
        "round": 2100,
        "shares": {
          "P-cheap": 0.1257,
          "P-mid": 0.7847,
          "P-premium": 0.0312,
          "P-adv": 0.0488,
          "P-flaky": 0.0097
        }
      },
      {
        "round": 2300,
        "shares": {
          "P-cheap": 0.1117,
          "P-mid": 0.8093,
          "P-premium": 0.0303,
          "P-adv": 0.0402,
          "P-flaky": 0.0085
        }
      },
      {
        "round": 2500,
        "shares": {
          "P-cheap": 0.1115,
          "P-mid": 0.7958,
          "P-premium": 0.0402,
          "P-adv": 0.042,
          "P-flaky": 0.0105
        }
      },
      {
        "round": 2700,
        "shares": {
          "P-cheap": 0.1152,
          "P-mid": 0.7947,
          "P-premium": 0.0327,
          "P-adv": 0.048,
          "P-flaky": 0.0095
        }
      },
      {
        "round": 2900,
        "shares": {
          "P-cheap": 0.1162,
          "P-mid": 0.7893,
          "P-premium": 0.0388,
          "P-adv": 0.043,
          "P-flaky": 0.0127
        }
      },
      {
        "round": 3100,
        "shares": {
          "P-cheap": 0.1092,
          "P-mid": 0.7988,
          "P-premium": 0.0343,
          "P-adv": 0.0462,
          "P-flaky": 0.0115
        }
      },
      {
        "round": 3300,
        "shares": {
          "P-cheap": 0.097,
          "P-mid": 0.8243,
          "P-premium": 0.0292,
          "P-adv": 0.0403,
          "P-flaky": 0.0092
        }
      },
      {
        "round": 3500,
        "shares": {
          "P-cheap": 0.1063,
          "P-mid": 0.8108,
          "P-premium": 0.0333,
          "P-adv": 0.0395,
          "P-flaky": 0.01
        }
      },
      {
        "round": 3700,
        "shares": {
          "P-cheap": 0.1008,
          "P-mid": 0.8217,
          "P-premium": 0.0347,
          "P-adv": 0.0338,
          "P-flaky": 0.009
        }
      },
      {
        "round": 3900,
        "shares": {
          "P-cheap": 0.0992,
          "P-mid": 0.8163,
          "P-premium": 0.033,
          "P-adv": 0.0405,
          "P-flaky": 0.011
        }
      },
      {
        "round": 4100,
        "shares": {
          "P-cheap": 0.0982,
          "P-mid": 0.8007,
          "P-premium": 0.0282,
          "P-adv": 0.0583,
          "P-flaky": 0.0147
        }
      },
      {
        "round": 4300,
        "shares": {
          "P-cheap": 0.1048,
          "P-mid": 0.7938,
          "P-premium": 0.0372,
          "P-adv": 0.0527,
          "P-flaky": 0.0115
        }
      },
      {
        "round": 4500,
        "shares": {
          "P-cheap": 0.1008,
          "P-mid": 0.8077,
          "P-premium": 0.0323,
          "P-adv": 0.0518,
          "P-flaky": 0.0073
        }
      },
      {
        "round": 4700,
        "shares": {
          "P-cheap": 0.0925,
          "P-mid": 0.8128,
          "P-premium": 0.0358,
          "P-adv": 0.0517,
          "P-flaky": 0.0072
        }
      },
      {
        "round": 4900,
        "shares": {
          "P-cheap": 0.1103,
          "P-mid": 0.8,
          "P-premium": 0.0295,
          "P-adv": 0.0505,
          "P-flaky": 0.0097
        }
      },
      {
        "round": 5100,
        "shares": {
          "P-cheap": 0.1227,
          "P-mid": 0.777,
          "P-premium": 0.0357,
          "P-adv": 0.0533,
          "P-flaky": 0.0113
        }
      },
      {
        "round": 5300,
        "shares": {
          "P-cheap": 0.1078,
          "P-mid": 0.8058,
          "P-premium": 0.029,
          "P-adv": 0.0495,
          "P-flaky": 0.0078
        }
      },
      {
        "round": 5500,
        "shares": {
          "P-cheap": 0.0982,
          "P-mid": 0.8103,
          "P-premium": 0.0317,
          "P-adv": 0.05,
          "P-flaky": 0.0098
        }
      },
      {
        "round": 5700,
        "shares": {
          "P-cheap": 0.1058,
          "P-mid": 0.8068,
          "P-premium": 0.0305,
          "P-adv": 0.0485,
          "P-flaky": 0.0083
        }
      },
      {
        "round": 5900,
        "shares": {
          "P-cheap": 0.1137,
          "P-mid": 0.798,
          "P-premium": 0.0318,
          "P-adv": 0.049,
          "P-flaky": 0.0075
        }
      },
      {
        "round": 6100,
        "shares": {
          "P-cheap": 0.1023,
          "P-mid": 0.8107,
          "P-premium": 0.0308,
          "P-adv": 0.0448,
          "P-flaky": 0.0113
        }
      },
      {
        "round": 6300,
        "shares": {
          "P-cheap": 0.1063,
          "P-mid": 0.7952,
          "P-premium": 0.0373,
          "P-adv": 0.0535,
          "P-flaky": 0.0077
        }
      },
      {
        "round": 6500,
        "shares": {
          "P-cheap": 0.0993,
          "P-mid": 0.8045,
          "P-premium": 0.0367,
          "P-adv": 0.0493,
          "P-flaky": 0.0102
        }
      },
      {
        "round": 6700,
        "shares": {
          "P-cheap": 0.1107,
          "P-mid": 0.8015,
          "P-premium": 0.0307,
          "P-adv": 0.0497,
          "P-flaky": 0.0075
        }
      },
      {
        "round": 6900,
        "shares": {
          "P-cheap": 0.107,
          "P-mid": 0.803,
          "P-premium": 0.033,
          "P-adv": 0.0462,
          "P-flaky": 0.0108
        }
      },
      {
        "round": 7100,
        "shares": {
          "P-cheap": 0.102,
          "P-mid": 0.8005,
          "P-premium": 0.0342,
          "P-adv": 0.0532,
          "P-flaky": 0.0102
        }
      },
      {
        "round": 7300,
        "shares": {
          "P-cheap": 0.0985,
          "P-mid": 0.8035,
          "P-premium": 0.0392,
          "P-adv": 0.0477,
          "P-flaky": 0.0112
        }
      },
      {
        "round": 7500,
        "shares": {
          "P-cheap": 0.107,
          "P-mid": 0.8027,
          "P-premium": 0.0305,
          "P-adv": 0.0478,
          "P-flaky": 0.012
        }
      },
      {
        "round": 7700,
        "shares": {
          "P-cheap": 0.0947,
          "P-mid": 0.8143,
          "P-premium": 0.03,
          "P-adv": 0.0513,
          "P-flaky": 0.0097
        }
      },
      {
        "round": 7900,
        "shares": {
          "P-cheap": 0.101,
          "P-mid": 0.8077,
          "P-premium": 0.035,
          "P-adv": 0.0483,
          "P-flaky": 0.008
        }
      },
      {
        "round": 8100,
        "shares": {
          "P-cheap": 0.1075,
          "P-mid": 0.7998,
          "P-premium": 0.0342,
          "P-adv": 0.0515,
          "P-flaky": 0.007
        }
      },
      {
        "round": 8300,
        "shares": {
          "P-cheap": 0.109,
          "P-mid": 0.7957,
          "P-premium": 0.0308,
          "P-adv": 0.0587,
          "P-flaky": 0.0058
        }
      },
      {
        "round": 8500,
        "shares": {
          "P-cheap": 0.104,
          "P-mid": 0.8095,
          "P-premium": 0.0343,
          "P-adv": 0.0397,
          "P-flaky": 0.0125
        }
      },
      {
        "round": 8700,
        "shares": {
          "P-cheap": 0.0937,
          "P-mid": 0.8182,
          "P-premium": 0.0317,
          "P-adv": 0.0472,
          "P-flaky": 0.0093
        }
      },
      {
        "round": 8900,
        "shares": {
          "P-cheap": 0.1005,
          "P-mid": 0.812,
          "P-premium": 0.03,
          "P-adv": 0.0478,
          "P-flaky": 0.0097
        }
      },
      {
        "round": 9100,
        "shares": {
          "P-cheap": 0.1067,
          "P-mid": 0.8063,
          "P-premium": 0.029,
          "P-adv": 0.0463,
          "P-flaky": 0.0117
        }
      },
      {
        "round": 9300,
        "shares": {
          "P-cheap": 0.1102,
          "P-mid": 0.7978,
          "P-premium": 0.0327,
          "P-adv": 0.0498,
          "P-flaky": 0.0095
        }
      },
      {
        "round": 9500,
        "shares": {
          "P-cheap": 0.1003,
          "P-mid": 0.8137,
          "P-premium": 0.034,
          "P-adv": 0.0438,
          "P-flaky": 0.0082
        }
      },
      {
        "round": 9700,
        "shares": {
          "P-cheap": 0.0993,
          "P-mid": 0.8125,
          "P-premium": 0.03,
          "P-adv": 0.0482,
          "P-flaky": 0.01
        }
      },
      {
        "round": 9900,
        "shares": {
          "P-cheap": 0.114,
          "P-mid": 0.7973,
          "P-premium": 0.0343,
          "P-adv": 0.0447,
          "P-flaky": 0.0097
        }
      }
    ],
    "S2": [
      {
        "round": 100,
        "shares": {
          "P-cheap": 0.2043,
          "P-mid": 0.4757,
          "P-premium": 0.1018,
          "P-adv": 0.159,
          "P-flaky": 0.0592
        }
      },
      {
        "round": 300,
        "shares": {
          "P-cheap": 0.1845,
          "P-mid": 0.654,
          "P-premium": 0.0513,
          "P-adv": 0.1012,
          "P-flaky": 0.009
        }
      },
      {
        "round": 500,
        "shares": {
          "P-cheap": 0.1653,
          "P-mid": 0.704,
          "P-premium": 0.043,
          "P-adv": 0.0803,
          "P-flaky": 0.0073
        }
      },
      {
        "round": 700,
        "shares": {
          "P-cheap": 0.139,
          "P-mid": 0.744,
          "P-premium": 0.0422,
          "P-adv": 0.0662,
          "P-flaky": 0.0087
        }
      },
      {
        "round": 900,
        "shares": {
          "P-cheap": 0.1223,
          "P-mid": 0.7743,
          "P-premium": 0.0345,
          "P-adv": 0.0597,
          "P-flaky": 0.0092
        }
      },
      {
        "round": 1100,
        "shares": {
          "P-cheap": 0.131,
          "P-mid": 0.7798,
          "P-premium": 0.0328,
          "P-adv": 0.0455,
          "P-flaky": 0.0108
        }
      },
      {
        "round": 1300,
        "shares": {
          "P-cheap": 0.1282,
          "P-mid": 0.775,
          "P-premium": 0.033,
          "P-adv": 0.0523,
          "P-flaky": 0.0115
        }
      },
      {
        "round": 1500,
        "shares": {
          "P-cheap": 0.1258,
          "P-mid": 0.7773,
          "P-premium": 0.034,
          "P-adv": 0.0557,
          "P-flaky": 0.0072
        }
      },
      {
        "round": 1700,
        "shares": {
          "P-cheap": 0.1137,
          "P-mid": 0.7933,
          "P-premium": 0.0298,
          "P-adv": 0.0525,
          "P-flaky": 0.0107
        }
      },
      {
        "round": 1900,
        "shares": {
          "P-cheap": 0.1258,
          "P-mid": 0.779,
          "P-premium": 0.0337,
          "P-adv": 0.0495,
          "P-flaky": 0.012
        }
      },
      {
        "round": 2100,
        "shares": {
          "P-cheap": 0.1257,
          "P-mid": 0.7847,
          "P-premium": 0.0312,
          "P-adv": 0.0488,
          "P-flaky": 0.0097
        }
      },
      {
        "round": 2300,
        "shares": {
          "P-cheap": 0.1117,
          "P-mid": 0.8093,
          "P-premium": 0.0303,
          "P-adv": 0.0402,
          "P-flaky": 0.0085
        }
      },
      {
        "round": 2500,
        "shares": {
          "P-cheap": 0.1115,
          "P-mid": 0.7958,
          "P-premium": 0.0402,
          "P-adv": 0.042,
          "P-flaky": 0.0105
        }
      },
      {
        "round": 2700,
        "shares": {
          "P-cheap": 0.1152,
          "P-mid": 0.7947,
          "P-premium": 0.0327,
          "P-adv": 0.048,
          "P-flaky": 0.0095
        }
      },
      {
        "round": 2900,
        "shares": {
          "P-cheap": 0.1162,
          "P-mid": 0.7893,
          "P-premium": 0.0388,
          "P-adv": 0.043,
          "P-flaky": 0.0127
        }
      },
      {
        "round": 3100,
        "shares": {
          "P-cheap": 0.178,
          "P-mid": 0.667,
          "P-premium": 0.059,
          "P-adv": 0.0812,
          "P-flaky": 0.0148
        }
      },
      {
        "round": 3300,
        "shares": {
          "P-cheap": 0.2597,
          "P-mid": 0.4943,
          "P-premium": 0.0927,
          "P-adv": 0.1387,
          "P-flaky": 0.0147
        }
      },
      {
        "round": 3500,
        "shares": {
          "P-cheap": 0.331,
          "P-mid": 0.3335,
          "P-premium": 0.1158,
          "P-adv": 0.196,
          "P-flaky": 0.0237
        }
      },
      {
        "round": 3700,
        "shares": {
          "P-cheap": 0.3585,
          "P-mid": 0.2545,
          "P-premium": 0.1442,
          "P-adv": 0.2285,
          "P-flaky": 0.0143
        }
      },
      {
        "round": 3900,
        "shares": {
          "P-cheap": 0.3917,
          "P-mid": 0.1848,
          "P-premium": 0.1352,
          "P-adv": 0.2765,
          "P-flaky": 0.0118
        }
      },
      {
        "round": 4100,
        "shares": {
          "P-cheap": 0.3937,
          "P-mid": 0.1407,
          "P-premium": 0.1332,
          "P-adv": 0.3165,
          "P-flaky": 0.016
        }
      },
      {
        "round": 4300,
        "shares": {
          "P-cheap": 0.4013,
          "P-mid": 0.0952,
          "P-premium": 0.131,
          "P-adv": 0.3558,
          "P-flaky": 0.0167
        }
      },
      {
        "round": 4500,
        "shares": {
          "P-cheap": 0.408,
          "P-mid": 0.0667,
          "P-premium": 0.1163,
          "P-adv": 0.3978,
          "P-flaky": 0.0112
        }
      },
      {
        "round": 4700,
        "shares": {
          "P-cheap": 0.4345,
          "P-mid": 0.045,
          "P-premium": 0.1057,
          "P-adv": 0.4033,
          "P-flaky": 0.0115
        }
      },
      {
        "round": 4900,
        "shares": {
          "P-cheap": 0.4268,
          "P-mid": 0.0392,
          "P-premium": 0.0925,
          "P-adv": 0.4268,
          "P-flaky": 0.0147
        }
      },
      {
        "round": 5100,
        "shares": {
          "P-cheap": 0.4457,
          "P-mid": 0.0288,
          "P-premium": 0.1092,
          "P-adv": 0.4042,
          "P-flaky": 0.0122
        }
      },
      {
        "round": 5300,
        "shares": {
          "P-cheap": 0.4513,
          "P-mid": 0.0352,
          "P-premium": 0.1058,
          "P-adv": 0.3975,
          "P-flaky": 0.0102
        }
      },
      {
        "round": 5500,
        "shares": {
          "P-cheap": 0.441,
          "P-mid": 0.0455,
          "P-premium": 0.1178,
          "P-adv": 0.3857,
          "P-flaky": 0.01
        }
      },
      {
        "round": 5700,
        "shares": {
          "P-cheap": 0.4025,
          "P-mid": 0.1208,
          "P-premium": 0.099,
          "P-adv": 0.3628,
          "P-flaky": 0.0148
        }
      },
      {
        "round": 5900,
        "shares": {
          "P-cheap": 0.3838,
          "P-mid": 0.23,
          "P-premium": 0.0708,
          "P-adv": 0.3068,
          "P-flaky": 0.0085
        }
      },
      {
        "round": 6100,
        "shares": {
          "P-cheap": 0.35,
          "P-mid": 0.3315,
          "P-premium": 0.063,
          "P-adv": 0.245,
          "P-flaky": 0.0105
        }
      },
      {
        "round": 6300,
        "shares": {
          "P-cheap": 0.3118,
          "P-mid": 0.4537,
          "P-premium": 0.0515,
          "P-adv": 0.174,
          "P-flaky": 0.009
        }
      },
      {
        "round": 6500,
        "shares": {
          "P-cheap": 0.2452,
          "P-mid": 0.567,
          "P-premium": 0.039,
          "P-adv": 0.1382,
          "P-flaky": 0.0107
        }
      },
      {
        "round": 6700,
        "shares": {
          "P-cheap": 0.2068,
          "P-mid": 0.6635,
          "P-premium": 0.0345,
          "P-adv": 0.0863,
          "P-flaky": 0.0088
        }
      },
      {
        "round": 6900,
        "shares": {
          "P-cheap": 0.1917,
          "P-mid": 0.7095,
          "P-premium": 0.0252,
          "P-adv": 0.0603,
          "P-flaky": 0.0133
        }
      },
      {
        "round": 7100,
        "shares": {
          "P-cheap": 0.165,
          "P-mid": 0.7457,
          "P-premium": 0.0245,
          "P-adv": 0.0547,
          "P-flaky": 0.0102
        }
      },
      {
        "round": 7300,
        "shares": {
          "P-cheap": 0.1475,
          "P-mid": 0.7775,
          "P-premium": 0.0308,
          "P-adv": 0.0375,
          "P-flaky": 0.0067
        }
      },
      {
        "round": 7500,
        "shares": {
          "P-cheap": 0.1402,
          "P-mid": 0.791,
          "P-premium": 0.027,
          "P-adv": 0.03,
          "P-flaky": 0.0118
        }
      },
      {
        "round": 7700,
        "shares": {
          "P-cheap": 0.1243,
          "P-mid": 0.8122,
          "P-premium": 0.0227,
          "P-adv": 0.0305,
          "P-flaky": 0.0103
        }
      },
      {
        "round": 7900,
        "shares": {
          "P-cheap": 0.1117,
          "P-mid": 0.8177,
          "P-premium": 0.0283,
          "P-adv": 0.0318,
          "P-flaky": 0.0105
        }
      },
      {
        "round": 8100,
        "shares": {
          "P-cheap": 0.1088,
          "P-mid": 0.8292,
          "P-premium": 0.0255,
          "P-adv": 0.028,
          "P-flaky": 0.0085
        }
      },
      {
        "round": 8300,
        "shares": {
          "P-cheap": 0.1118,
          "P-mid": 0.8163,
          "P-premium": 0.0285,
          "P-adv": 0.0355,
          "P-flaky": 0.0078
        }
      },
      {
        "round": 8500,
        "shares": {
          "P-cheap": 0.111,
          "P-mid": 0.8108,
          "P-premium": 0.0333,
          "P-adv": 0.0333,
          "P-flaky": 0.0115
        }
      },
      {
        "round": 8700,
        "shares": {
          "P-cheap": 0.1048,
          "P-mid": 0.8198,
          "P-premium": 0.0282,
          "P-adv": 0.0397,
          "P-flaky": 0.0075
        }
      },
      {
        "round": 8900,
        "shares": {
          "P-cheap": 0.11,
          "P-mid": 0.8093,
          "P-premium": 0.0333,
          "P-adv": 0.0382,
          "P-flaky": 0.0092
        }
      },
      {
        "round": 9100,
        "shares": {
          "P-cheap": 0.1213,
          "P-mid": 0.7937,
          "P-premium": 0.0273,
          "P-adv": 0.0473,
          "P-flaky": 0.0103
        }
      },
      {
        "round": 9300,
        "shares": {
          "P-cheap": 0.1157,
          "P-mid": 0.797,
          "P-premium": 0.0325,
          "P-adv": 0.0462,
          "P-flaky": 0.0087
        }
      },
      {
        "round": 9500,
        "shares": {
          "P-cheap": 0.1093,
          "P-mid": 0.8048,
          "P-premium": 0.0322,
          "P-adv": 0.0455,
          "P-flaky": 0.0082
        }
      },
      {
        "round": 9700,
        "shares": {
          "P-cheap": 0.105,
          "P-mid": 0.8098,
          "P-premium": 0.0282,
          "P-adv": 0.048,
          "P-flaky": 0.009
        }
      },
      {
        "round": 9900,
        "shares": {
          "P-cheap": 0.1213,
          "P-mid": 0.7905,
          "P-premium": 0.034,
          "P-adv": 0.0462,
          "P-flaky": 0.008
        }
      }
    ],
    "S3": [
      {
        "round": 100,
        "shares": {
          "P-cheap": 0.2043,
          "P-mid": 0.4757,
          "P-premium": 0.1018,
          "P-adv": 0.159,
          "P-flaky": 0.0592
        }
      },
      {
        "round": 300,
        "shares": {
          "P-cheap": 0.1845,
          "P-mid": 0.654,
          "P-premium": 0.0513,
          "P-adv": 0.1012,
          "P-flaky": 0.009
        }
      },
      {
        "round": 500,
        "shares": {
          "P-cheap": 0.1653,
          "P-mid": 0.704,
          "P-premium": 0.043,
          "P-adv": 0.0803,
          "P-flaky": 0.0073
        }
      },
      {
        "round": 700,
        "shares": {
          "P-cheap": 0.139,
          "P-mid": 0.744,
          "P-premium": 0.0422,
          "P-adv": 0.0662,
          "P-flaky": 0.0087
        }
      },
      {
        "round": 900,
        "shares": {
          "P-cheap": 0.1223,
          "P-mid": 0.7743,
          "P-premium": 0.0345,
          "P-adv": 0.0597,
          "P-flaky": 0.0092
        }
      },
      {
        "round": 1100,
        "shares": {
          "P-cheap": 0.1257,
          "P-mid": 0.7428,
          "P-premium": 0.078,
          "P-adv": 0.0428,
          "P-flaky": 0.0107
        }
      },
      {
        "round": 1300,
        "shares": {
          "P-cheap": 0.1025,
          "P-mid": 0.6027,
          "P-premium": 0.244,
          "P-adv": 0.0412,
          "P-flaky": 0.0097
        }
      },
      {
        "round": 1500,
        "shares": {
          "P-cheap": 0.0852,
          "P-mid": 0.52,
          "P-premium": 0.351,
          "P-adv": 0.036,
          "P-flaky": 0.0078
        }
      },
      {
        "round": 1700,
        "shares": {
          "P-cheap": 0.0695,
          "P-mid": 0.4405,
          "P-premium": 0.4498,
          "P-adv": 0.0303,
          "P-flaky": 0.0098
        }
      },
      {
        "round": 1900,
        "shares": {
          "P-cheap": 0.0723,
          "P-mid": 0.3608,
          "P-premium": 0.5322,
          "P-adv": 0.0268,
          "P-flaky": 0.0078
        }
      },
      {
        "round": 2100,
        "shares": {
          "P-cheap": 0.0607,
          "P-mid": 0.3037,
          "P-premium": 0.5978,
          "P-adv": 0.0297,
          "P-flaky": 0.0082
        }
      },
      {
        "round": 2300,
        "shares": {
          "P-cheap": 0.0607,
          "P-mid": 0.2782,
          "P-premium": 0.6275,
          "P-adv": 0.0248,
          "P-flaky": 0.0088
        }
      },
      {
        "round": 2500,
        "shares": {
          "P-cheap": 0.0568,
          "P-mid": 0.2408,
          "P-premium": 0.6633,
          "P-adv": 0.0318,
          "P-flaky": 0.0072
        }
      },
      {
        "round": 2700,
        "shares": {
          "P-cheap": 0.0565,
          "P-mid": 0.2253,
          "P-premium": 0.6797,
          "P-adv": 0.028,
          "P-flaky": 0.0105
        }
      },
      {
        "round": 2900,
        "shares": {
          "P-cheap": 0.0588,
          "P-mid": 0.211,
          "P-premium": 0.6912,
          "P-adv": 0.03,
          "P-flaky": 0.009
        }
      },
      {
        "round": 3100,
        "shares": {
          "P-cheap": 0.0503,
          "P-mid": 0.1987,
          "P-premium": 0.7142,
          "P-adv": 0.0277,
          "P-flaky": 0.0092
        }
      },
      {
        "round": 3300,
        "shares": {
          "P-cheap": 0.0458,
          "P-mid": 0.198,
          "P-premium": 0.7175,
          "P-adv": 0.0267,
          "P-flaky": 0.012
        }
      },
      {
        "round": 3500,
        "shares": {
          "P-cheap": 0.0587,
          "P-mid": 0.175,
          "P-premium": 0.7293,
          "P-adv": 0.027,
          "P-flaky": 0.01
        }
      },
      {
        "round": 3700,
        "shares": {
          "P-cheap": 0.0598,
          "P-mid": 0.1747,
          "P-premium": 0.7293,
          "P-adv": 0.0253,
          "P-flaky": 0.0108
        }
      },
      {
        "round": 3900,
        "shares": {
          "P-cheap": 0.054,
          "P-mid": 0.1657,
          "P-premium": 0.7425,
          "P-adv": 0.0305,
          "P-flaky": 0.0073
        }
      },
      {
        "round": 4100,
        "shares": {
          "P-cheap": 0.0508,
          "P-mid": 0.1788,
          "P-premium": 0.7205,
          "P-adv": 0.0398,
          "P-flaky": 0.01
        }
      },
      {
        "round": 4300,
        "shares": {
          "P-cheap": 0.0482,
          "P-mid": 0.2082,
          "P-premium": 0.699,
          "P-adv": 0.0347,
          "P-flaky": 0.01
        }
      },
      {
        "round": 4500,
        "shares": {
          "P-cheap": 0.053,
          "P-mid": 0.197,
          "P-premium": 0.7083,
          "P-adv": 0.0327,
          "P-flaky": 0.009
        }
      },
      {
        "round": 4700,
        "shares": {
          "P-cheap": 0.052,
          "P-mid": 0.1963,
          "P-premium": 0.7178,
          "P-adv": 0.026,
          "P-flaky": 0.0078
        }
      },
      {
        "round": 4900,
        "shares": {
          "P-cheap": 0.0517,
          "P-mid": 0.1915,
          "P-premium": 0.7165,
          "P-adv": 0.0308,
          "P-flaky": 0.0095
        }
      },
      {
        "round": 5100,
        "shares": {
          "P-cheap": 0.0607,
          "P-mid": 0.1763,
          "P-premium": 0.7237,
          "P-adv": 0.0322,
          "P-flaky": 0.0072
        }
      },
      {
        "round": 5300,
        "shares": {
          "P-cheap": 0.0607,
          "P-mid": 0.1948,
          "P-premium": 0.7065,
          "P-adv": 0.0298,
          "P-flaky": 0.0082
        }
      },
      {
        "round": 5500,
        "shares": {
          "P-cheap": 0.0557,
          "P-mid": 0.1823,
          "P-premium": 0.7178,
          "P-adv": 0.0357,
          "P-flaky": 0.0085
        }
      },
      {
        "round": 5700,
        "shares": {
          "P-cheap": 0.0535,
          "P-mid": 0.1858,
          "P-premium": 0.725,
          "P-adv": 0.0288,
          "P-flaky": 0.0068
        }
      },
      {
        "round": 5900,
        "shares": {
          "P-cheap": 0.0652,
          "P-mid": 0.1942,
          "P-premium": 0.7015,
          "P-adv": 0.033,
          "P-flaky": 0.0062
        }
      },
      {
        "round": 6100,
        "shares": {
          "P-cheap": 0.0563,
          "P-mid": 0.1862,
          "P-premium": 0.7237,
          "P-adv": 0.025,
          "P-flaky": 0.0088
        }
      },
      {
        "round": 6300,
        "shares": {
          "P-cheap": 0.0488,
          "P-mid": 0.1823,
          "P-premium": 0.7302,
          "P-adv": 0.0315,
          "P-flaky": 0.0072
        }
      },
      {
        "round": 6500,
        "shares": {
          "P-cheap": 0.0455,
          "P-mid": 0.2063,
          "P-premium": 0.7028,
          "P-adv": 0.036,
          "P-flaky": 0.0093
        }
      },
      {
        "round": 6700,
        "shares": {
          "P-cheap": 0.0648,
          "P-mid": 0.1992,
          "P-premium": 0.6952,
          "P-adv": 0.0337,
          "P-flaky": 0.0072
        }
      },
      {
        "round": 6900,
        "shares": {
          "P-cheap": 0.061,
          "P-mid": 0.2022,
          "P-premium": 0.6958,
          "P-adv": 0.0323,
          "P-flaky": 0.0087
        }
      },
      {
        "round": 7100,
        "shares": {
          "P-cheap": 0.052,
          "P-mid": 0.2065,
          "P-premium": 0.6945,
          "P-adv": 0.0392,
          "P-flaky": 0.0078
        }
      },
      {
        "round": 7300,
        "shares": {
          "P-cheap": 0.0503,
          "P-mid": 0.1935,
          "P-premium": 0.7167,
          "P-adv": 0.0322,
          "P-flaky": 0.0073
        }
      },
      {
        "round": 7500,
        "shares": {
          "P-cheap": 0.0512,
          "P-mid": 0.2103,
          "P-premium": 0.6977,
          "P-adv": 0.0288,
          "P-flaky": 0.012
        }
      },
      {
        "round": 7700,
        "shares": {
          "P-cheap": 0.051,
          "P-mid": 0.2105,
          "P-premium": 0.6983,
          "P-adv": 0.0328,
          "P-flaky": 0.0073
        }
      },
      {
        "round": 7900,
        "shares": {
          "P-cheap": 0.0548,
          "P-mid": 0.2045,
          "P-premium": 0.6978,
          "P-adv": 0.037,
          "P-flaky": 0.0058
        }
      },
      {
        "round": 8100,
        "shares": {
          "P-cheap": 0.056,
          "P-mid": 0.21,
          "P-premium": 0.6882,
          "P-adv": 0.0357,
          "P-flaky": 0.0102
        }
      },
      {
        "round": 8300,
        "shares": {
          "P-cheap": 0.064,
          "P-mid": 0.2003,
          "P-premium": 0.6923,
          "P-adv": 0.038,
          "P-flaky": 0.0053
        }
      },
      {
        "round": 8500,
        "shares": {
          "P-cheap": 0.0642,
          "P-mid": 0.2105,
          "P-premium": 0.6892,
          "P-adv": 0.0282,
          "P-flaky": 0.008
        }
      },
      {
        "round": 8700,
        "shares": {
          "P-cheap": 0.0622,
          "P-mid": 0.2072,
          "P-premium": 0.6918,
          "P-adv": 0.0347,
          "P-flaky": 0.0042
        }
      },
      {
        "round": 8900,
        "shares": {
          "P-cheap": 0.0527,
          "P-mid": 0.2052,
          "P-premium": 0.6955,
          "P-adv": 0.0357,
          "P-flaky": 0.011
        }
      },
      {
        "round": 9100,
        "shares": {
          "P-cheap": 0.0625,
          "P-mid": 0.1985,
          "P-premium": 0.6962,
          "P-adv": 0.0325,
          "P-flaky": 0.0103
        }
      },
      {
        "round": 9300,
        "shares": {
          "P-cheap": 0.0615,
          "P-mid": 0.1915,
          "P-premium": 0.7073,
          "P-adv": 0.0293,
          "P-flaky": 0.0103
        }
      },
      {
        "round": 9500,
        "shares": {
          "P-cheap": 0.0565,
          "P-mid": 0.1805,
          "P-premium": 0.7263,
          "P-adv": 0.0292,
          "P-flaky": 0.0075
        }
      },
      {
        "round": 9700,
        "shares": {
          "P-cheap": 0.0615,
          "P-mid": 0.1807,
          "P-premium": 0.7185,
          "P-adv": 0.0337,
          "P-flaky": 0.0057
        }
      },
      {
        "round": 9900,
        "shares": {
          "P-cheap": 0.0587,
          "P-mid": 0.1843,
          "P-premium": 0.7208,
          "P-adv": 0.0282,
          "P-flaky": 0.008
        }
      }
    ]
  },
  "roundExamples": [
    {
      "scenario": "S1",
      "round": 800,
      "label": "早期探索",
      "reason": "没有冲击，观察 posterior 还在收敛时的选择。",
      "taskType": "T3b",
      "chosen": "P-mid",
      "quality": 0.7,
      "cost": 0.002,
      "failure": false,
      "utility": 0.7,
      "reward": 0.489,
      "budget": 48.37,
      "lambdaNorm": 0.234,
      "candidates": [
        {
          "provider": "P-mid",
          "pulls": 462,
          "utility": 0.845,
          "cost": 0.002,
          "score": 0.6,
          "failRate": 0
        },
        {
          "provider": "P-cheap",
          "pulls": 229,
          "utility": 0.756,
          "cost": 0.0005,
          "score": 0.567,
          "failRate": 0
        },
        {
          "provider": "P-premium",
          "pulls": 47,
          "utility": 0.921,
          "cost": 0.01,
          "score": 0.471,
          "failRate": 0
        },
        {
          "provider": "P-adv",
          "pulls": 52,
          "utility": 0.666,
          "cost": 0.002,
          "score": 0.463,
          "failRate": 0
        },
        {
          "provider": "P-flaky",
          "pulls": 10,
          "utility": 0.043,
          "cost": 0.002,
          "score": -0.014,
          "failRate": 0.6
        }
      ]
    },
    {
      "scenario": "S1",
      "round": 2200,
      "label": "稳定前段",
      "reason": "P-mid 通常已经成为主力臂。",
      "taskType": "T3b",
      "chosen": "P-mid",
      "quality": 0.95,
      "cost": 0.002,
      "failure": false,
      "utility": 0.95,
      "reward": 0.675,
      "budget": 45.38,
      "lambdaNorm": 0.239,
      "candidates": [
        {
          "provider": "P-mid",
          "pulls": 1497,
          "utility": 0.827,
          "cost": 0.002,
          "score": 0.582,
          "failRate": 0
        },
        {
          "provider": "P-cheap",
          "pulls": 434,
          "utility": 0.705,
          "cost": 0.0005,
          "score": 0.525,
          "failRate": 0
        },
        {
          "provider": "P-adv",
          "pulls": 137,
          "utility": 0.675,
          "cost": 0.002,
          "score": 0.466,
          "failRate": 0
        },
        {
          "provider": "P-premium",
          "pulls": 109,
          "utility": 0.91,
          "cost": 0.01,
          "score": 0.454,
          "failRate": 0
        },
        {
          "provider": "P-flaky",
          "pulls": 23,
          "utility": 0.147,
          "cost": 0.002,
          "score": 0.064,
          "failRate": 0.522
        }
      ]
    },
    {
      "scenario": "S1",
      "round": 5000,
      "label": "中点对照",
      "reason": "和 S2/S3 的事件窗口做横向比较。",
      "taskType": "T3a",
      "chosen": "P-mid",
      "quality": 0.667,
      "cost": 0.002,
      "failure": false,
      "utility": 0.667,
      "reward": 0.456,
      "budget": 39.2,
      "lambdaNorm": 0.243,
      "candidates": [
        {
          "provider": "P-mid",
          "pulls": 3843,
          "utility": 0.819,
          "cost": 0.002,
          "score": 0.571,
          "failRate": 0
        },
        {
          "provider": "P-cheap",
          "pulls": 641,
          "utility": 0.689,
          "cost": 0.0005,
          "score": 0.509,
          "failRate": 0
        },
        {
          "provider": "P-premium",
          "pulls": 220,
          "utility": 0.908,
          "cost": 0.01,
          "score": 0.444,
          "failRate": 0
        },
        {
          "provider": "P-adv",
          "pulls": 245,
          "utility": 0.647,
          "cost": 0.002,
          "score": 0.441,
          "failRate": 0
        },
        {
          "provider": "P-flaky",
          "pulls": 51,
          "utility": 0.225,
          "cost": 0.002,
          "score": 0.122,
          "failRate": 0.451
        }
      ]
    },
    {
      "scenario": "S1",
      "round": 8500,
      "label": "后期稳定",
      "reason": "看长期预算压力下是否仍维持选择结构。",
      "taskType": "T3b",
      "chosen": "P-mid",
      "quality": 0.6,
      "cost": 0.002,
      "failure": false,
      "utility": 0.6,
      "reward": 0.404,
      "budget": 31.45,
      "lambdaNorm": 0.245,
      "candidates": [
        {
          "provider": "P-mid",
          "pulls": 6752,
          "utility": 0.817,
          "cost": 0.002,
          "score": 0.568,
          "failRate": 0
        },
        {
          "provider": "P-cheap",
          "pulls": 824,
          "utility": 0.674,
          "cost": 0.0005,
          "score": 0.497,
          "failRate": 0
        },
        {
          "provider": "P-adv",
          "pulls": 487,
          "utility": 0.674,
          "cost": 0.002,
          "score": 0.46,
          "failRate": 0
        },
        {
          "provider": "P-premium",
          "pulls": 348,
          "utility": 0.904,
          "cost": 0.01,
          "score": 0.438,
          "failRate": 0
        },
        {
          "provider": "P-flaky",
          "pulls": 89,
          "utility": 0.282,
          "cost": 0.002,
          "score": 0.164,
          "failRate": 0.416
        }
      ]
    },
    {
      "scenario": "S2",
      "round": 1200,
      "label": "故障前",
      "reason": "P-mid 尚未 outage，是正常市场对照点。",
      "taskType": "T3b",
      "chosen": "P-mid",
      "quality": 1,
      "cost": 0.002,
      "failure": false,
      "utility": 1,
      "reward": 0.718,
      "budget": 47.54,
      "lambdaNorm": 0.235,
      "candidates": [
        {
          "provider": "P-mid",
          "pulls": 720,
          "utility": 0.832,
          "cost": 0.002,
          "score": 0.59,
          "failRate": 0
        },
        {
          "provider": "P-cheap",
          "pulls": 330,
          "utility": 0.729,
          "cost": 0.0005,
          "score": 0.546,
          "failRate": 0
        },
        {
          "provider": "P-premium",
          "pulls": 69,
          "utility": 0.91,
          "cost": 0.01,
          "score": 0.461,
          "failRate": 0
        },
        {
          "provider": "P-adv",
          "pulls": 68,
          "utility": 0.65,
          "cost": 0.002,
          "score": 0.45,
          "failRate": 0
        },
        {
          "provider": "P-flaky",
          "pulls": 13,
          "utility": 0.071,
          "cost": 0.002,
          "score": 0.008,
          "failRate": 0.538
        }
      ]
    },
    {
      "scenario": "S2",
      "round": 3200,
      "label": "刚进入 outage",
      "reason": "P-mid 开始出现失败，策略还在确认信号。",
      "taskType": "T3b",
      "chosen": "P-mid",
      "quality": 1,
      "cost": 0.002,
      "failure": false,
      "utility": 1,
      "reward": 0.709,
      "budget": 43.1,
      "lambdaNorm": 0.243,
      "candidates": [
        {
          "provider": "P-mid",
          "pulls": 2211,
          "utility": 0.791,
          "cost": 0.002,
          "score": 0.55,
          "failRate": 0.018
        },
        {
          "provider": "P-cheap",
          "pulls": 578,
          "utility": 0.698,
          "cost": 0.0005,
          "score": 0.516,
          "failRate": 0
        },
        {
          "provider": "P-adv",
          "pulls": 208,
          "utility": 0.668,
          "cost": 0.002,
          "score": 0.457,
          "failRate": 0
        },
        {
          "provider": "P-premium",
          "pulls": 171,
          "utility": 0.91,
          "cost": 0.01,
          "score": 0.446,
          "failRate": 0
        },
        {
          "provider": "P-flaky",
          "pulls": 32,
          "utility": 0.184,
          "cost": 0.002,
          "score": 0.091,
          "failRate": 0.469
        }
      ]
    },
    {
      "scenario": "S2",
      "round": 4200,
      "label": "outage 中段",
      "reason": "迁移应该已经明显发生。",
      "taskType": "T3a",
      "chosen": "P-adv",
      "quality": 0,
      "cost": 0.002,
      "failure": false,
      "utility": 0,
      "reward": -0.051,
      "budget": 40.29,
      "lambdaNorm": 0.254,
      "candidates": [
        {
          "provider": "P-mid",
          "pulls": 2413,
          "utility": 0.759,
          "cost": 0.002,
          "score": 0.515,
          "failRate": 0.042
        },
        {
          "provider": "P-cheap",
          "pulls": 937,
          "utility": 0.688,
          "cost": 0.0005,
          "score": 0.5,
          "failRate": 0
        },
        {
          "provider": "P-adv",
          "pulls": 467,
          "utility": 0.656,
          "cost": 0.002,
          "score": 0.438,
          "failRate": 0
        },
        {
          "provider": "P-premium",
          "pulls": 339,
          "utility": 0.911,
          "cost": 0.01,
          "score": 0.425,
          "failRate": 0
        },
        {
          "provider": "P-flaky",
          "pulls": 44,
          "utility": 0.237,
          "cost": 0.002,
          "score": 0.126,
          "failRate": 0.432
        }
      ]
    },
    {
      "scenario": "S2",
      "round": 6200,
      "label": "恢复后",
      "reason": "P-mid 恢复后，策略开始回流但保留一些谨慎。",
      "taskType": "T1",
      "chosen": "P-cheap",
      "quality": 1,
      "cost": 0.0005,
      "failure": false,
      "utility": 1,
      "reward": 0.717,
      "budget": 34.44,
      "lambdaNorm": 0.27,
      "candidates": [
        {
          "provider": "P-mid",
          "pulls": 2638,
          "utility": 0.749,
          "cost": 0.002,
          "score": 0.493,
          "failRate": 0.05
        },
        {
          "provider": "P-cheap",
          "pulls": 1630,
          "utility": 0.678,
          "cost": 0.0005,
          "score": 0.482,
          "failRate": 0
        },
        {
          "provider": "P-adv",
          "pulls": 1172,
          "utility": 0.661,
          "cost": 0.002,
          "score": 0.428,
          "failRate": 0
        },
        {
          "provider": "P-premium",
          "pulls": 701,
          "utility": 0.902,
          "cost": 0.01,
          "score": 0.389,
          "failRate": 0
        },
        {
          "provider": "P-flaky",
          "pulls": 59,
          "utility": 0.197,
          "cost": 0.002,
          "score": 0.09,
          "failRate": 0.475
        }
      ]
    },
    {
      "scenario": "S3",
      "round": 800,
      "label": "促销前",
      "reason": "P-premium 仍然昂贵，只少量探索。",
      "taskType": "T3b",
      "chosen": "P-mid",
      "quality": 0.7,
      "cost": 0.002,
      "failure": false,
      "utility": 0.7,
      "reward": 0.489,
      "budget": 48.37,
      "lambdaNorm": 0.234,
      "candidates": [
        {
          "provider": "P-mid",
          "pulls": 462,
          "utility": 0.845,
          "cost": 0.002,
          "score": 0.6,
          "failRate": 0
        },
        {
          "provider": "P-cheap",
          "pulls": 229,
          "utility": 0.756,
          "cost": 0.0005,
          "score": 0.567,
          "failRate": 0
        },
        {
          "provider": "P-premium",
          "pulls": 47,
          "utility": 0.921,
          "cost": 0.01,
          "score": 0.471,
          "failRate": 0
        },
        {
          "provider": "P-adv",
          "pulls": 52,
          "utility": 0.666,
          "cost": 0.002,
          "score": 0.463,
          "failRate": 0
        },
        {
          "provider": "P-flaky",
          "pulls": 10,
          "utility": 0.043,
          "cost": 0.002,
          "score": -0.014,
          "failRate": 0.6
        }
      ]
    },
    {
      "scenario": "S3",
      "round": 1200,
      "label": "刚降价",
      "reason": "成本 posterior 开始看到价格变化。",
      "taskType": "T3b",
      "chosen": "P-premium",
      "quality": 1,
      "cost": 0.002,
      "failure": false,
      "utility": 1,
      "reward": 0.728,
      "budget": 47.68,
      "lambdaNorm": 0.227,
      "candidates": [
        {
          "provider": "P-mid",
          "pulls": 695,
          "utility": 0.836,
          "cost": 0.002,
          "score": 0.601,
          "failRate": 0
        },
        {
          "provider": "P-cheap",
          "pulls": 328,
          "utility": 0.729,
          "cost": 0.0005,
          "score": 0.552,
          "failRate": 0
        },
        {
          "provider": "P-premium",
          "pulls": 98,
          "utility": 0.874,
          "cost": 0.0062,
          "score": 0.536,
          "failRate": 0
        },
        {
          "provider": "P-adv",
          "pulls": 66,
          "utility": 0.65,
          "cost": 0.002,
          "score": 0.457,
          "failRate": 0
        },
        {
          "provider": "P-flaky",
          "pulls": 13,
          "utility": 0.071,
          "cost": 0.002,
          "score": 0.01,
          "failRate": 0.538
        }
      ]
    },
    {
      "scenario": "S3",
      "round": 2200,
      "label": "迁移期",
      "reason": "P-premium 的性价比优势开始主导。",
      "taskType": "T3b",
      "chosen": "P-premium",
      "quality": 0.6,
      "cost": 0.002,
      "failure": false,
      "utility": 0.6,
      "reward": 0.421,
      "budget": 45.82,
      "lambdaNorm": 0.224,
      "candidates": [
        {
          "provider": "P-premium",
          "pulls": 604,
          "utility": 0.887,
          "cost": 0.0027,
          "score": 0.628,
          "failRate": 0
        },
        {
          "provider": "P-mid",
          "pulls": 1049,
          "utility": 0.824,
          "cost": 0.002,
          "score": 0.594,
          "failRate": 0
        },
        {
          "provider": "P-cheap",
          "pulls": 422,
          "utility": 0.714,
          "cost": 0.0005,
          "score": 0.542,
          "failRate": 0
        },
        {
          "provider": "P-adv",
          "pulls": 103,
          "utility": 0.668,
          "cost": 0.002,
          "score": 0.473,
          "failRate": 0
        },
        {
          "provider": "P-flaky",
          "pulls": 22,
          "utility": 0.177,
          "cost": 0.002,
          "score": 0.092,
          "failRate": 0.5
        }
      ]
    },
    {
      "scenario": "S3",
      "round": 7000,
      "label": "利用期",
      "reason": "降价已被充分利用，premium share 保持高位。",
      "taskType": "T2",
      "chosen": "P-premium",
      "quality": 1,
      "cost": 0.002,
      "failure": false,
      "utility": 1,
      "reward": 0.728,
      "budget": 36.48,
      "lambdaNorm": 0.227,
      "candidates": [
        {
          "provider": "P-premium",
          "pulls": 4424,
          "utility": 0.869,
          "cost": 0.0021,
          "score": 0.625,
          "failRate": 0
        },
        {
          "provider": "P-mid",
          "pulls": 1637,
          "utility": 0.806,
          "cost": 0.002,
          "score": 0.578,
          "failRate": 0
        },
        {
          "provider": "P-cheap",
          "pulls": 592,
          "utility": 0.691,
          "cost": 0.0005,
          "score": 0.523,
          "failRate": 0
        },
        {
          "provider": "P-adv",
          "pulls": 276,
          "utility": 0.663,
          "cost": 0.002,
          "score": 0.467,
          "failRate": 0
        },
        {
          "provider": "P-flaky",
          "pulls": 71,
          "utility": 0.289,
          "cost": 0.002,
          "score": 0.178,
          "failRate": 0.423
        }
      ]
    }
  ],
  "ablations": [
    {
      "id": "noPayment",
      "component": "Payment-aware λ",
      "label": "预算压力",
      "impact": "预算权重消失，cum_PA 大幅坍塌。",
      "breaks": "不会根据钱包压力改变质量/成本权重。",
      "metric": "S1 regret +7222",
      "severity": 0.94
    },
    {
      "id": "noDiscount",
      "component": "Discount γ",
      "label": "证据衰减",
      "impact": "旧证据不衰减，冲击恢复更慢。",
      "breaks": "市场变了以后，旧 posterior 仍然压着新信号。",
      "metric": "S2 恢复约慢 35%",
      "severity": 0.54
    },
    {
      "id": "noContext",
      "component": "Context",
      "label": "任务上下文",
      "impact": "任务类型差异被抹平，机会利用变弱。",
      "breaks": "T1/T2/T3 的 provider 偏好被混成一个桶。",
      "metric": "S3 task split 变钝",
      "severity": 0.42
    },
    {
      "id": "noTS",
      "component": "Thompson sampling",
      "label": "探索机制",
      "impact": "均值接近，但种子方差显著放大。",
      "breaks": "早期偶然样本更容易把策略锁死。",
      "metric": "variance 5-9x",
      "severity": 0.38
    },
    {
      "id": "noCostPosterior",
      "component": "Cost posterior",
      "label": "成本后验",
      "impact": "S3 中几乎发现不了 premium 降价。",
      "breaks": "价格变化不会进入可学习信号。",
      "metric": "premium share 60% -> 4%",
      "severity": 0.78
    }
  ]
};

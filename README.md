# 大成·招行重点持营业绩速览网站

打开 `index.html` 即可查看页面。页面每天读取 `data/performance.json`，所以更新数据时只需要替换这个 JSON 文件。页面下方有微信文案板块，可直接复制粘贴。

## 用 CSV 更新数据

1. 按 `data/performance_template.csv` 的列格式准备 Wind 导出数据。
2. 在当前工作区运行：

```bash
python3 wind_daily_site/scripts/update_from_csv.py wind_daily_site/data/performance_template.csv --as-of 2026.6.29
```

## 同花顺连接检测

```bash
python3 wind_daily_site/scripts/check_10jqka.py
```

同花顺首页可以访问，但公开 HTML 里的行情区域通常先显示 `--`，真实行情由页面脚本动态加载；静态网站直接跨站读取也常受浏览器限制。建议把同花顺或 Wind 导出的最终数据转成 `data/performance.json`，页面会自动用 `asOf` 作为微信文案里的截至日期。

## 接入 Wind 的说明

Wind 官网入口是产品页面，不直接提供公开的基金和指数数据库接口。若电脑已安装 Wind 金融终端并开通 WindPy，可把 WindPy 查询结果先导出为同格式 CSV，再运行上面的脚本；若使用公司内部数据服务，也只要最终生成 `data/performance.json` 即可。

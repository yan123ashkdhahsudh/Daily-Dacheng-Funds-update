# 分享给别人并保持每日更新

## 推荐方式：GitHub Pages

1. 新建一个 GitHub 仓库。
2. 把 `wind_daily_site` 文件夹里的内容上传到仓库根目录。
3. 在仓库设置里打开 Pages，发布分支选 `main`，目录选 `/root`。
4. 打开 Actions 页面，确认 `Update performance data` 工作流已启用。
5. 进入这个工作流，点一次 `Run workflow`，先手动更新并验证。
6. 把 Pages 生成的网址发给别人。

工作流默认在北京时间周二到周六早上 9:30 左右运行，读取公开基金净值和指数历史行情，更新 `data/performance.json`。别人打开同一个网址时，页面会读取最新的数据文件，微信文案也会跟着更新。

## 如果放在公司服务器或内网

把整个 `wind_daily_site` 文件夹放到静态网站目录，然后每天早上定时运行：

```bash
python3 /网站路径/scripts/update_daily_data.py
```

## 手动指定某一天

```bash
python3 scripts/update_daily_data.py --date 2026-06-30
```

## 注意

基金数据通常在交易日晚间披露，早上读取的是上一交易日已披露的数据，不是实时行情。页面不需要一直连接同花顺实时刷新，只要 `data/performance.json` 每天被更新即可。

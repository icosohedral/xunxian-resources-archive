# 寻仙资源存档 · Cloudflare

正式站点：[https://xunxian.wiki/](https://xunxian.wiki/)

线上架构：

- Cloudflare Python Worker + FastAPI；
- Cloudflare D1 网页资源数据库；
- 独立 Cloudflare D1 今日来访数据库；
- Workers Static Assets；
- 自定义根域名 `xunxian.wiki`。

## 构建部署数据

```bash
cd apps/resource_viewer_cloudflare
uv run python scripts/build_web_database.py
```

构建脚本从本地只读的 `outputs/catalog.db` 生成压缩后的网页数据库和
Cloudflare Worker 所需的模板、配置模块，并将新版数据库与上一版本地快照比较：

- 首次构建或数据库结构改变时生成全量 SQL；
- 普通资料变化只生成受影响资源的增量 SQL；
- 没有数据变化时生成 `noop` 清单，部署时跳过 D1；
- `data/resource_web.deploy.json` 记录本次模式、变更数量和快照编号。

原始资料与完整构建数据库不会上传。增量 SQL 在执行前会检查远端快照，
若远端数据库不是预期的上一版，导入会失败并整体回滚。

## 本地验证

```bash
uv sync
npx wrangler d1 execute xunxian-resource-archive --local \
  --file=data/resource_web.sql
npx wrangler d1 execute xunxian-resource-visits --local \
  --file=../../schemas/visits.sql
uv run python scripts/deploy.py --data-only
uv run pywrangler dev
```

来访数据库只需在首次建立环境时初始化。

## 正式部署

```bash
uv run python scripts/deploy.py --remote
```

发布脚本读取部署清单：有数据差异时同步全量或增量 SQL，没有差异时只发布
Worker 和静态资源。可先使用 `--dry-run` 查看将执行的命令；也可用
`--data-only` 或 `--app-only` 单独发布。

当前网站版本为 `v1.0.4`（版本序列从 `v1.0.0` 开始）。访问统计按中国时区和匿名浏览器 ID 每日去重。

## 当前线上资源

- Worker：`xunxian-resource-archive`
- 资源数据库：`xunxian-resource-archive`
- 来访数据库：`xunxian-resource-visits`
- 资源索引：54,725 条
- 资源详情：54,725 条

部署后至少检查首页、静态资源、道具详情、宠物搜索、称号搜索和
`POST /api/visit`。Wrangler 发布结果中的版本 ID 只用于 Cloudflare
部署追踪，不作为网站展示版本。

# 批量导入接口说明

批量导入接口 `POST /v1/import/jobs` 单次最多支持 500 条记录。

推荐的 CSV 文件大小不超过 8MB；超过该大小时应拆分为多个批次。

接口返回 `job_id` 后，客户端应轮询 `/v1/import/jobs/{job_id}` 查询进度。

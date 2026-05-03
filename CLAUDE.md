# Workflow Requirements

## Commit Workflow

1. **每次代码改动后**：自动创建 commit（使用清晰的提交信息）
2. **每 5 个 commit**：暂停并请用户审核，等确认后再推送到 GitHub

## 审核流程

- 每完成 5 个 commit，通知用户进行审核
- 用户确认后，执行 `git push` 推送到 GitHub
- 如果用户有修改意见，在本地调整后再提交推送

## 注意事项

- commit 信息应清晰描述改动内容
- 推送前确保本地更改已提交
- 遵循 Git 最佳实践
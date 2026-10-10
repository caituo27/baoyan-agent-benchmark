# 运行并提交75题执行记录

对方只需看这一页。拉取本仓库代码后，在仓库根目录操作。需要macOS、Python 3.11+、Codex CLI 0.162.0及本人已登录的订阅账号；模型、版本不符时停止，不自动替换。

## 1. 运行

以Astra为例；跑Sol就将 `astra` 换成 `sol`。脚本自动选择缺题：Astra 32题，Sol 52题。

```sh
python3 scripts/community_run.py astra
python3 scripts/community_run.py astra --execute
```

第一条预览，第二条使用本人额度执行。负责操作的Codex只运行脚本，不读评分文件或替模型答题。正常暂停后，在原电脑执行同一命令并追加 `--resume`；不要删除失败记录重跑。

## 2. 生成记录

```sh
python3 scripts/community_run.py astra --submit
```

脚本校验并生成脱敏答卷、轨迹和逐题状态，放到统一的 `experiments/dev75-20261010/records/` 下，并打印本次新增目录。原始文件留在 `runs/`，不公开提交。

## 3. 提交PR

让Codex检查生成的公开文件，只提交打印出的新增目录，通过自己的fork向本仓库发PR。合并后记录就和已有答卷放在一起。`--submit` 本身只准备文件，不会自动推送；失败和未完成状态也须保留。

总入口是[75题执行记录](../experiments/dev75-20261010/README.md)。

可以直接发给对方Codex：

> 请按 docs/community-runs.md 运行我领取的Astra（或Sol）缺题。我授权使用本人订阅额度。完成后生成统一目录中的执行记录，检查公开副本，仅提交脚本输出的新目录并向原仓库发PR。不要覆盖旧答卷、删除失败、替换模型或改用API；原始ZIP保留并告诉我位置，不公开上传。

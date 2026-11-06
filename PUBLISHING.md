# 发布到 PyPI / GitHub

## 1. 本地构建

```powershell
cd plugins\gui-operator
python -m pip install build twine
python -m build
python -m twine check dist\*
```

产物：`dist\gui_operator_mcp-0.1.0-py3-none-any.whl` 和 sdist。

## 2. 试装

```powershell
python -m venv .verify
.\.verify\Scripts\python.exe -m pip install dist\*.whl
.\.verify\Scripts\gui-operator-mcp.exe
```

能启动并等待 stdin 就对了。

## 3. 发布

```powershell
python -m twine upload dist\*
```

需要 PyPI token，别写进仓库。

## 4. GitHub

```powershell
git init
git add .
git commit -m "gui-operator-mcp 0.1.0"
git tag v0.1.0
gh repo create gui-operator-mcp --public --source . --push
gh release create v0.1.0 dist\* --generate-notes
```

CI 已放在仓库根的 `.github/workflows/gui-operator.yml`，只在 `plugins/gui-operator/**` 变更时跑 Windows 测试。

## 5. 版本

- `pyproject.toml` 的 `version` 和 `gui_operator_mcp.__version__` 同步改；
- 破坏性变更升 minor，修 bug 升 patch；
- 每个版本在 `CHANGELOG.md` 写三行：新增、修复、已知问题。

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PY = REPO_ROOT / 'src' / 'wulu_geetest_bypass' / 'config.py'
MJS_SCRIPT = REPO_ROOT / 'scripts' / 'extract-config.mjs'


def fail(msg):
    print(f'[error] {msg}', file=sys.stderr)
    sys.exit(1)


def main():
    if not shutil.which('node'):
        fail("未在系统环境变量中找到 'node'，请先安装 Node.js")

    if not MJS_SCRIPT.exists():
        fail(f'找不到 Node 脚本: {MJS_SCRIPT}')

    print(f'正在执行 {MJS_SCRIPT.name} 提取极验动态参数...')
    try:
        result = subprocess.run(
            ['node', str(MJS_SCRIPT)],
            capture_output=True,
            text=True,
            check=True,
            encoding='utf-8',
        )
    except subprocess.CalledProcessError as e:
        fail(f'Node 脚本执行失败:\n{e.stderr}')

    try:
        vals = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        fail(f'无法解析 Node 脚本的 JSON 输出:\n{e}\n原始输出:\n{result.stdout}')

    if not CONFIG_PY.exists():
        fail(f'找不到目标配置文件: {CONFIG_PY}, 请先创建它')

    content = CONFIG_PY.read_text('utf-8')
    for py_var, new_val in vals.items():
        if py_var == 'static_ver':
            continue

        if isinstance(new_val, bool):
            literal = str(new_val)
            pattern = rf'({py_var}\s*=\s*)(True|False)'
        elif isinstance(new_val, str):
            literal = repr(new_val)
            pattern = rf"({py_var}\s*=\s*)(['\"]).*?\2"
        else:
            fail(f'字段 {py_var} 的值类型不支持: {type(new_val).__name__}')

        replacement = rf'\1{literal}'

        if not re.search(pattern, content):
            fail(f'变量 {py_var} 未在 config.py 中定义, 无法替换')
        content = re.sub(pattern, replacement, content)

    if content != CONFIG_PY.read_text('utf-8'):
        with open(CONFIG_PY, 'w', encoding='utf-8', newline='\n') as f:
            f.write(content)
        print('config.py updated')
    else:
        print('no changes')

    if 'GITHUB_OUTPUT' in os.environ:
        with open(os.environ['GITHUB_OUTPUT'], 'a') as f:
            f.write(f'GEETEST_VER={vals["static_ver"]}\n')


if __name__ == '__main__':
    main()

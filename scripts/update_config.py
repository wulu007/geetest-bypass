import os
import re
import shutil
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PY = REPO_ROOT / 'src' / 'wulu_geetest_bypass' / 'config.py'
MJS_SCRIPT = REPO_ROOT / 'scripts' / 'extract-config.mjs'

FIELD_MAP = {
    'biht': 'biht',
    'lib_key': 'lib_key',
    'lib_val': 'lib_val',
    'abo_key': 'abo_key',
    'abo_val': 'abo_val',
}


def main():
    if not shutil.which('node'):
        print("[error] 未在系统环境变量中找到 'node'，请先安装 Node.js")
        return

    if not MJS_SCRIPT.exists():
        print(f'[error] 找不到 Node 脚本: {MJS_SCRIPT}')
        return

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
        print(f'[error] Node 脚本执行失败:\n{e.stderr}')
        return

    vals = {}
    for line in result.stdout.strip().splitlines():
        if '=' not in line:
            continue
        k, v = line.split('=', 1)
        vals[k.strip()] = v.strip()

    if not CONFIG_PY.exists():
        print(f'[error] 找不到目标配置文件: {CONFIG_PY}，请先创建它')
        return

    origin_content = CONFIG_PY.read_text('utf-8')
    content = origin_content

    is_modified = False
    for out_key, py_var in FIELD_MAP.items():
        if out_key not in vals:
            print(f'[warn] 字段 {out_key} 未在 Node 输出中找到，跳过')
            continue

        new_val = vals[out_key]
        pattern = rf"({py_var}\s*=\s*)['\"].*?['\"]"
        replacement = rf"\1'{new_val}'"

        if not re.search(pattern, content):
            print(f'[warn] 变量 {py_var} 未在 config.py 中定义，无法替换')
            continue

        updated_content = re.sub(pattern, replacement, content)
        if updated_content != content:
            content = updated_content
            is_modified = True

    if is_modified:
        CONFIG_PY.write_text(content, 'utf-8')
        print('config.py updated')
    else:
        print('no changes')

    if 'GITHUB_OUTPUT' in os.environ:
        ver = vals.get('static_ver', '')
        if ver:
            with open(os.environ['GITHUB_OUTPUT'], 'a') as f:
                f.write(f'GEETEST_VER={ver}\n')


if __name__ == '__main__':
    main()

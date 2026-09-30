import json
import shutil
import tempfile
from pathlib import Path

# pyrefly: ignore [missing-import]
from hatchling.builders.hooks.plugin.interface import BuildHookInterface


class CompressJsonHook(BuildHookInterface):
    PLUGIN_NAME = 'custom'

    def initialize(self, version, build_data):
        root = Path(self.root)
        data_dir = root / 'src' / 'wulu_geetest_bypass' / 'data'
        if not data_dir.exists():
            return

        tmpdir = Path(tempfile.mkdtemp())
        self._tmpdir = tmpdir

        for src in data_dir.glob('*.json'):
            try:
                data = json.loads(src.read_text(encoding='utf-8'))
            except json.JSONDecodeError as e:
                raise RuntimeError(f'Invalid JSON: {src} -> {e}') from e

            minified = json.dumps(
                data,
                ensure_ascii=False,
                separators=(',', ':'),
            )

            tmp = tmpdir / src.name
            tmp.write_text(minified, encoding='utf-8')

            build_data['force_include'][str(tmp)] = (
                f'wulu_geetest_bypass/data/{src.name}'
            )

    def finalize(self, version, build_data, artifact_path):
        tmpdir = getattr(self, '_tmpdir', None)
        if tmpdir and tmpdir.exists():
            shutil.rmtree(tmpdir, ignore_errors=True)

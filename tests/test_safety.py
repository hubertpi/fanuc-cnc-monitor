import importlib.util
import json
import re
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]
WORKER = ROOT / "fanuc_monitor" / "worker"


def prepare_module():
    spec = importlib.util.spec_from_file_location("prepare", WORKER / "prepare_binding.py")
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def test_binding_restriction_fails_closed():
    module = prepare_module()
    source = '[DllImport("fw", EntryPoint="cnc_statinfo")] public static extern short cnc_statinfo();\n[DllImport("fw", EntryPoint="cnc_reset")] public static extern short cnc_reset();'
    result = module.restrict(source, {"cnc_statinfo"})
    assert "extern short cnc_reset" not in result
    with pytest.raises(ValueError): module.restrict(source, {"cnc_missing"})
    with pytest.raises(ValueError): module.restrict(source + '\n[DllImport("fw")] internal static extern short cnc_write();', {"cnc_statinfo"})
    with pytest.raises(ValueError): module.restrict(source.replace('EntryPoint="cnc_statinfo"', 'EntryPoint="cnc_reset"'), {"cnc_statinfo"})


def test_binding_selects_active_linux_abi_before_allowlist():
    module = prepare_module()
    source = '''#if (!ONO8D)
[DllImport("fw", EntryPoint="cnc_rdprgnum")] public static extern short cnc_rdprgnum();
#else
[DllImport("fw", EntryPoint="cnc_rdprgnumo8")] public static extern short cnc_rdprgnum();
#endif
'''
    result = module.restrict(source, {"cnc_rdprgnum"})
    assert "cnc_rdprgnumo8" not in result
    assert result.count("DllImport") == 1
    assert module.select_linux64("#if WIN64\nwrong\n#elif LINUX64\ncorrect\n#else\nwrong\n#endif\n") == "correct\n"
    with pytest.raises(ValueError): module.select_linux64("#if LINUX64 && UNKNOWN\na\n#endif\n")
    with pytest.raises(ValueError): module.select_linux64("#if LINUX64\na\n")


def test_binding_hash_is_portable_but_rejects_changed_source():
    import hashlib
    module = prepare_module()
    raw = b"line one\nline two\n"
    expected = hashlib.sha256(raw).hexdigest()
    assert module.verify_source(raw, expected) == raw.decode()
    assert module.verify_source(raw.replace(b"\n", b"\r\n"), expected) == raw.decode()
    with pytest.raises(ValueError): module.verify_source(raw + b"changed", expected)


def test_worker_calls_match_exact_read_session_allowlist():
    data = json.loads((WORKER / "allowlist.json").read_text())
    allow = set(data["read"] + data["session"])
    calls = set(re.findall(r'Focas\.(cnc_\w+)\s*\(', (WORKER / "Program.cs").read_text()))
    assert calls == allow
    assert not any(re.search(r'wr|upload|download|reset|start$|stop$', name) for name in allow)
    generated = WORKER / "RestrictedFocas.generated.cs"
    if generated.exists():
        declarations = set(re.findall(r'public static extern\s+\w+\s+(\w+)\s*\(', generated.read_text()))
        assert declarations == allow


def test_bundled_binding_generates_without_network(tmp_path, monkeypatch):
    module = prepare_module()
    import shutil
    import sys
    import urllib.request
    shutil.copytree(WORKER / 'upstream', tmp_path / 'upstream')
    for name in ('upstream.lock.json', 'allowlist.json'):
        shutil.copy2(WORKER / name, tmp_path / name)
    monkeypatch.setattr(module, 'HERE', tmp_path)
    monkeypatch.setattr(sys, 'argv', ['prepare_binding.py'])
    def no_network(*args, **kwargs):
        pytest.fail('Binding generation must not access the network')
    monkeypatch.setattr(urllib.request, 'urlopen', no_network)
    module.main()
    generated = (tmp_path / 'RestrictedFocas.generated.cs').read_text(encoding='utf-8')
    assert 'cnc_statinfo' in generated
    assert 'extern short cnc_reset(' not in generated


def test_no_control_topics_or_code_config():
    source = (ROOT / "fanuc_monitor/app/mqtt.py").read_text()
    assert '.subscribe("homeassistant/status"' in source
    assert source.count(".subscribe(") == 1
    assert "command_topic" not in source
    assert "eval(" not in (ROOT / "fanuc_monitor/app/main.py").read_text()


def test_addon_isolation_and_architecture():
    import yaml
    config = yaml.safe_load((ROOT / "fanuc_monitor/config.yaml").read_text())
    assert config["arch"] == ["amd64"]
    assert config["ingress"] is True and "ports" not in config
    assert not config.get("privileged") and not config.get("docker_api")
    assert config["options"]["hardware_testing_enabled"] is False
    assert config["map"] == [{"type": "share", "read_only": True}]

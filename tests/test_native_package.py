import hashlib
import json
from pathlib import Path
import pytest
from app.collector import CollectionError, native_ready

ROOT = Path(__file__).resolve().parents[1]


def test_bundled_library_integrity_and_architecture():
    library = native_ready({'hardware_testing_enabled': True})
    provenance = json.loads((library.parent / 'provenance.json').read_text())
    assert hashlib.sha256(library.read_bytes()).hexdigest() == provenance['sha256']
    assert provenance['commit'] in provenance['url']
    assert library.parent == ROOT / 'fanuc_monitor/native'


def test_bundle_does_not_bypass_hardware_gate():
    with pytest.raises(CollectionError, match='Hardware testing is disabled'):
        native_ready({})


def test_bad_explicit_override_does_not_fall_back_to_bundle():
    with pytest.raises(CollectionError, match='missing or override'):
        native_ready({'hardware_testing_enabled': True, 'native_library_sha256': 'invalid'})

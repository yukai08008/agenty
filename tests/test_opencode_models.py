import sys

import pytest

from agenty.runtime import ChannelMode, EvidenceLevel, RuntimeIdentity
from agenty.runtime.adapters import RuntimeModelAdapterError
from agenty.runtime.opencode import OpenCodeRuntimeAdapter
from agenty.runtime.opencode_models import (
    InvalidOpenCodeModelCatalog,
    OpenCodeModelCatalogParser,
)


def runtime() -> RuntimeIdentity:
    return RuntimeIdentity(
        runtime_id="local-opencode",
        runtime_kind="opencode",
        runtime_version="1.18.26",
        executable="/opt/homebrew/bin/opencode",
        channel=ChannelMode.TRANSIENT_PROCESS,
    )


def test_verbose_catalog_maps_models_and_variants_to_public_models():
    output = """provider/plain
{
  "id": "plain",
  "providerID": "provider",
  "name": "Plain Model",
  "variants": {}
}
provider/reasoner
{
  "id": "reasoner",
  "providerID": "provider",
  "name": "Reasoner",
  "variants": {"low": {}, "high": {}, "max": {}}
}
"""

    catalog = OpenCodeModelCatalogParser().parse(output, runtime())

    assert len(catalog.models) == 2
    assert catalog.models[0].model.qualified_id == "provider/plain"
    assert catalog.models[0].supported_efforts == ()
    assert catalog.models[1].supported_efforts == ("low", "high", "max")
    assert catalog.models[1].evidence is EvidenceLevel.PROBE_VERIFIED


@pytest.mark.parametrize(
    "output",
    [
        "",
        "provider/model\nnot-json",
        'other/model\n{"id":"model","providerID":"provider"}',
        'provider/model\n{"id":"model","providerID":"provider","variants":[]}',
    ],
)
def test_invalid_verbose_catalog_is_rejected(output):
    with pytest.raises(InvalidOpenCodeModelCatalog):
        OpenCodeModelCatalogParser().parse(output, runtime())


def test_opencode_adapter_probes_verbose_model_catalog(tmp_path):
    executable = tmp_path / "opencode"
    executable.write_text(
        f"#!{sys.executable}\n"
        "print('provider/reasoner')\n"
        "print('{\"id\":\"reasoner\",\"providerID\":\"provider\",'"
        "'\"name\":\"Reasoner\",\"variants\":{\"high\":{}}}')\n"
    )
    executable.chmod(0o755)
    identity = runtime().model_copy(update={"executable": str(executable)})

    catalog = OpenCodeRuntimeAdapter(
        str(executable)
    ).probe_model_catalog(identity)

    assert catalog.runtime == identity
    assert catalog.models[0].model.qualified_id == "provider/reasoner"
    assert catalog.models[0].supported_efforts == ("high",)


def test_opencode_adapter_wraps_invalid_model_catalog(tmp_path):
    executable = tmp_path / "opencode"
    executable.write_text(f"#!{sys.executable}\nprint('invalid')\n")
    executable.chmod(0o755)
    identity = runtime().model_copy(update={"executable": str(executable)})

    with pytest.raises(RuntimeModelAdapterError) as raised:
        OpenCodeRuntimeAdapter(str(executable)).probe_model_catalog(identity)

    assert raised.value.failure.code.value == "runtime_model_catalog_invalid"

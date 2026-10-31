from __future__ import annotations

import json

import pytest

from fram_eval.chaos.scene import CHAOS_MATH_V1, SCENE_SCHEMA_V1, SceneV1


def _scene() -> SceneV1:
    return SceneV1(
        system_key="aizawa",
        parameters={"a": 0.95, "b": 0.7, "dt": 0.01},
        initial_state=(0.1, 0.0, 0.0),
        steps=4096,
        burn_in=512,
        dt=0.01,
        seed=27,
        diagnostic_tolerances={"period_atol": 1e-8, "root_tolerance": 1e-12},
        rotational_encoding={
            "version": "RotationalEncodingV1",
            "angular_gain": 6.283185307179586,
            "radius_rule": "absolute_state",
            "pitch": 0.01,
        },
        complex_c=(-0.8, 0.156),
        complex_bounds=(-2.0, 1.0, -1.5, 1.5),
        complex_max_iter=256,
        camera={"position": [0.0, 1.0, 4.0], "fov": 42.0},
        colors={"clockwise": "#ff7a18", "counterclockwise": "#168cff"},
        density={"opacity": 0.72, "point_size": 1.5},
        title="Cathedral Organism",
        notes="A versioned reconstruction, not the missing original formula.",
    )


def test_scene_v1_json_round_trip_is_exact_and_canonical() -> None:
    scene = _scene()
    encoded = scene.to_json()
    restored = SceneV1.from_json(encoded)

    assert restored == scene
    assert restored.to_json() == encoded
    assert json.loads(encoded)["schema_version"] == SCENE_SCHEMA_V1
    assert json.loads(encoded)["math_version"] == CHAOS_MATH_V1


def test_scene_v1_detaches_mutable_input_mappings() -> None:
    parameters = {"r": 3.9}
    scene = SceneV1(
        system_key="logistic",
        parameters=parameters,
        initial_state=(0.2,),
        steps=128,
    )
    parameters["r"] = 3.2
    assert scene.parameters == {"r": 3.9}


def test_scene_v1_rejects_unknown_schema_and_fields() -> None:
    payload = _scene().to_dict()
    payload["schema_version"] = "fram-chaos-scene/v2"
    with pytest.raises(ValueError, match="unsupported scene schema"):
        SceneV1.from_dict(payload)

    payload = _scene().to_dict()
    payload["unversioned_ui_state"] = True
    with pytest.raises(ValueError, match="unknown SceneV1 fields"):
        SceneV1.from_dict(payload)

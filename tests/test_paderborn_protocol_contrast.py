from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from smartvalve.data.paderborn import (
    BEARING_METADATA,
    OPERATING_SETTINGS,
    PRIMARY_BEARING_CODES,
)
from smartvalve.data.paderborn_features import (
    MAIN_SIGNAL_FEATURE_FAMILIES,
    STRUCTURALLY_EXCLUDED_FILENAMES,
    main_signal_feature_family_names,
    main_signal_feature_names,
    parse_measurement_filename,
)
from smartvalve.experiments.paderborn_domain import build_paderborn_model_folds
from smartvalve.experiments.paderborn_protocol_contrast import (
    MODEL_NAMES,
    PROTOCOLS,
    attach_common_cells,
    build_classifier,
    build_protocol_model_folds,
    build_protocol_splits,
    ensemble_seed_predictions,
    generate_oof_predictions,
    paired_bearing_bootstrap,
    protocol_effect_table,
    protocol_rank_concordance,
    resolve_protocol_feature_names,
    score_oof_predictions,
)
from smartvalve.experiments.paderborn_sensor_audit import (
    bootstrap_sensor_family_fault_predictions,
    generate_bearing_reidentification_predictions,
    score_bearing_reidentification_predictions,
    score_sensor_family_fault_predictions,
    sensor_gap_differences,
)


def test_frozen_sensor_feature_families_are_disjoint_and_ordered() -> None:
    vibration = main_signal_feature_family_names("vibration")
    current = main_signal_feature_family_names("motor_current")
    fusion = main_signal_feature_family_names("fusion")

    assert MAIN_SIGNAL_FEATURE_FAMILIES == ("vibration", "motor_current", "fusion")
    assert len(vibration) == 24
    assert len(current) == 48
    assert len(fusion) == 72
    assert not set(vibration) & set(current)
    assert fusion == (*vibration, *current)
    with pytest.raises(ValueError, match="unknown"):
        main_signal_feature_family_names("target_selected")


@pytest.fixture(scope="module")
def feature_frame() -> pd.DataFrame:
    excluded = {
        (
            parse_measurement_filename(filename).bearing_code,
            parse_measurement_filename(filename).setting_code,
            parse_measurement_filename(filename).measurement_index,
        )
        for filename in STRUCTURALLY_EXCLUDED_FILENAMES
    }
    labels = {bearing.code: bearing.primary_label for bearing in BEARING_METADATA}
    records = []
    for bearing_code in PRIMARY_BEARING_CODES:
        for setting in OPERATING_SETTINGS:
            for measurement_index in range(1, 21):
                key = (bearing_code, setting.code, measurement_index)
                if key in excluded:
                    continue
                records.append(
                    {
                        "filename": f"{setting.code}_{bearing_code}_{measurement_index}.mat",
                        "bearing_code": bearing_code,
                        "setting_code": setting.code,
                        "measurement_index": measurement_index,
                        "truth": labels[bearing_code],
                    }
                )
    frame = pd.DataFrame(records)
    row_values = np.arange(len(frame), dtype=float)
    for feature_number, feature_name in enumerate(main_signal_feature_names(), start=1):
        frame[feature_name] = (row_values % (feature_number + 7)) / (feature_number + 1)
    return frame


def test_protocol_splits_cover_every_row_once_and_quarantine_cross_arms(
    feature_frame: pd.DataFrame,
) -> None:
    protocols = build_protocol_splits(feature_frame)

    assert tuple(protocols) == PROTOCOLS
    assert {name: len(splits) for name, splits in protocols.items()} == {
        "measurement_random": 6,
        "setting_holdout": 4,
        "identity_holdout": 6,
        "crossed_holdout": 24,
    }
    for splits in protocols.values():
        target_counts = np.zeros(len(feature_frame), dtype=int)
        for split in splits:
            target_counts[split.target_indices] += 1
        np.testing.assert_array_equal(target_counts, np.ones(len(feature_frame), dtype=int))

    random_split = protocols["measurement_random"][0]
    random_source = feature_frame.iloc[random_split.source_indices]
    random_target = feature_frame.iloc[random_split.target_indices]
    assert set(random_source["bearing_code"]) == set(random_target["bearing_code"])
    assert set(random_source["setting_code"]) == set(random_target["setting_code"])

    crossed = protocols["crossed_holdout"][0]
    source = feature_frame.iloc[crossed.source_indices]
    target = feature_frame.iloc[crossed.target_indices]
    quarantine = feature_frame.iloc[crossed.quarantine_indices]
    assert set(source["bearing_code"]).isdisjoint(target["bearing_code"])
    assert set(source["setting_code"]).isdisjoint(target["setting_code"])
    assert len(quarantine) > 0
    assert set(np.concatenate((crossed.source_indices, crossed.target_indices))).isdisjoint(
        crossed.quarantine_indices
    )


def test_common_cells_are_complete_and_reject_unknown_bearing(
    feature_frame: pd.DataFrame,
) -> None:
    attached = attach_common_cells(feature_frame)

    assert attached["evaluation_cell"].nunique() == 24
    assert attached.groupby("evaluation_cell")["truth"].nunique().eq(3).all()

    invalid = feature_frame.copy()
    invalid.loc[0, "bearing_code"] = "UNKNOWN"
    with pytest.raises(ValueError, match="absent"):
        attach_common_cells(invalid)


def test_neural_protocol_folds_are_source_local_and_crossed_parity(
    feature_frame: pd.DataFrame,
) -> None:
    protocol_folds = build_protocol_model_folds(feature_frame)
    prospective_crossed = build_paderborn_model_folds(feature_frame)

    assert {name: len(folds) for name, folds in protocol_folds.items()} == {
        "measurement_random": 6,
        "setting_holdout": 4,
        "identity_holdout": 6,
        "crossed_holdout": 24,
    }
    for folds in protocol_folds.values():
        for model_fold in folds:
            model_fold.fold.validate()
            assert model_fold.fold.held_factor == model_fold.protocol
            assert not set(model_fold.target_global_indices) & set(
                model_fold.quarantine_global_indices
            )

    for retrospective, prospective in zip(
        protocol_folds["crossed_holdout"], prospective_crossed, strict=True
    ):
        np.testing.assert_array_equal(
            retrospective.target_global_indices,
            prospective.target_global_indices,
        )
        np.testing.assert_array_equal(
            retrospective.quarantine_global_indices,
            prospective.quarantine_global_indices,
        )
        np.testing.assert_array_equal(
            retrospective.fold.nuisance_pairs,
            prospective.fold.nuisance_pairs,
        )
        np.testing.assert_array_equal(
            retrospective.fold.fault_pairs,
            prospective.fold.fault_pairs,
        )


def test_protocol_folds_accept_only_canonical_feature_subsets(
    feature_frame: pd.DataFrame,
) -> None:
    vibration = main_signal_feature_family_names("vibration")
    folds = build_protocol_model_folds(feature_frame, feature_names=vibration)

    assert all(
        model_fold.fold.features.shape[1] == 24
        for protocol_folds in folds.values()
        for model_fold in protocol_folds
    )
    assert all(
        model_fold.fold.feature_names == vibration
        for protocol_folds in folds.values()
        for model_fold in protocol_folds
    )
    assert resolve_protocol_feature_names(feature_frame, vibration) == vibration
    with pytest.raises(ValueError, match="order"):
        resolve_protocol_feature_names(feature_frame, tuple(reversed(vibration)))
    with pytest.raises(ValueError, match="duplicate"):
        resolve_protocol_feature_names(feature_frame, (vibration[0], vibration[0]))
    with pytest.raises(ValueError, match="unknown"):
        resolve_protocol_feature_names(feature_frame, ("target__chosen",))


@pytest.mark.parametrize("name", MODEL_NAMES)
def test_frozen_classifier_suite_fits_without_target_configuration(name: str) -> None:
    features = np.asarray(
        [
            [-2.0, -1.0],
            [-1.8, -0.8],
            [-1.6, -1.2],
            [0.0, 2.0],
            [0.2, 1.8],
            [-0.2, 2.2],
            [2.0, -1.0],
            [1.8, -0.8],
            [2.2, -1.2],
        ]
    )
    labels = np.asarray(["healthy"] * 3 + ["outer"] * 3 + ["inner"] * 3)

    classifier = build_classifier(name)
    classifier.fit(features, labels)
    predictions = classifier.predict(features)

    assert len(predictions) == len(labels)
    assert set(predictions).issubset(set(labels))


def test_unknown_classifier_is_rejected() -> None:
    with pytest.raises(ValueError, match="unknown"):
        build_classifier("target_tuned_model")


@pytest.fixture(scope="module")
def dummy_oof(feature_frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    return generate_oof_predictions(feature_frame, model_names=("dummy_prior",))


def test_oof_generation_and_common_cell_scoring_are_complete(
    feature_frame: pd.DataFrame,
    dummy_oof: tuple[pd.DataFrame, pd.DataFrame],
) -> None:
    predictions, fit_log = dummy_oof

    assert len(predictions) == len(feature_frame) * len(PROTOCOLS)
    assert len(fit_log) == 40
    assert predictions.groupby("protocol")["row_index"].nunique().eq(len(feature_frame)).all()

    aggregate, cells = score_oof_predictions(predictions)
    assert len(aggregate) == len(PROTOCOLS)
    assert len(cells) == len(PROTOCOLS) * 24
    assert aggregate["row_count"].eq(len(feature_frame)).all()
    assert aggregate["rank_pooled_macro_f1"].eq(1.0).all()


def test_oof_generation_accepts_frozen_sensor_family(
    feature_frame: pd.DataFrame,
) -> None:
    predictions, fit_log = generate_oof_predictions(
        feature_frame,
        model_names=("dummy_prior",),
        feature_names=main_signal_feature_family_names("motor_current"),
    )

    assert len(predictions) == len(feature_frame) * len(PROTOCOLS)
    assert len(fit_log) == 40


def _synthetic_aggregate() -> pd.DataFrame:
    orders = {
        "measurement_random": [0.9, 0.8, 0.7],
        "setting_holdout": [0.8, 0.9, 0.7],
        "identity_holdout": [0.7, 0.8, 0.9],
        "crossed_holdout": [0.6, 0.8, 0.7],
    }
    return pd.DataFrame(
        {
            "protocol": protocol,
            "method": method,
            "pooled_macro_f1": values[index],
            "mean_cell_macro_f1": values[index] - 0.01,
        }
        for protocol, values in orders.items()
        for index, method in enumerate(("a", "b", "c"))
    )


def test_rank_concordance_covers_every_protocol_pair() -> None:
    concordance = protocol_rank_concordance(_synthetic_aggregate())

    assert len(concordance) == 12
    assert concordance["method_count"].eq(3).all()
    assert concordance["kendall_tau"].between(-1.0, 1.0).all()


def _synthetic_predictions() -> pd.DataFrame:
    records = []
    labels = ("healthy", "outer", "inner")
    for protocol in PROTOCOLS:
        for method in ("a", "b"):
            for identity in range(6):
                for setting in range(4):
                    cell = f"identity={identity}|setting={setting}"
                    for label_number, truth in enumerate(labels):
                        prediction = truth
                        if protocol == "crossed_holdout" and truth == "inner":
                            prediction = "outer"
                        if method == "b" and protocol == "identity_holdout" and truth == "outer":
                            prediction = "healthy"
                        records.append(
                            {
                                "protocol": protocol,
                                "method": method,
                                "row_index": identity * 12 + setting * 3 + label_number,
                                "bearing_code": f"bearing-{truth}",
                                "truth": truth,
                                "prediction": prediction,
                                "evaluation_cell": cell,
                            }
                        )
    return pd.DataFrame(records)


def test_paired_bootstrap_is_bearing_level_and_deterministic() -> None:
    predictions = _synthetic_predictions()

    first_summary, first_draws, first_plan = paired_bearing_bootstrap(
        predictions,
        draws=17,
    )
    second_summary, second_draws, second_plan = paired_bearing_bootstrap(
        predictions,
        draws=17,
    )

    pd.testing.assert_frame_equal(first_summary, second_summary)
    pd.testing.assert_frame_equal(first_draws, second_draws)
    pd.testing.assert_frame_equal(first_plan, second_plan)
    assert len(first_summary) == 6
    assert len(first_draws) == 6 * 17
    assert first_plan.shape == (17, 3)
    assert first_plan.sum(axis=1).eq(3).all()
    assert first_summary["resampling_unit"].eq("bearing_code_stratified_by_truth").all()


def test_seed_ensemble_and_protocol_effects_preserve_common_rows() -> None:
    base = _synthetic_predictions()
    seeded = []
    for seed in (11, 23):
        rows = base.copy()
        rows["seed"] = seed
        rows["fold_id"] = rows["evaluation_cell"]
        rows["filename"] = rows["row_index"].astype(str) + ".mat"
        rows["setting_code"] = rows["evaluation_cell"].str.split("setting=").str[-1]
        rows["measurement_index"] = 1
        rows["identity_fold_id"] = rows["evaluation_cell"].str.split("|").str[0]
        for label in ("healthy", "outer", "inner"):
            rows[f"probability_{label}"] = (rows["prediction"] == label).astype(float)
        seeded.append(rows)

    ensemble = ensemble_seed_predictions(pd.concat(seeded), expected_seeds=(11, 23))
    aggregate, _ = score_oof_predictions(ensemble)
    effects = protocol_effect_table(aggregate)

    assert len(ensemble) == len(base)
    assert len(effects) == 3 * 2 * 5
    assert set(effects["reference_protocol"]) == {"crossed_holdout"}
    assert ensemble["prediction"].equals(
        ensemble[["probability_healthy", "probability_outer", "probability_inner"]]
        .idxmax(axis=1)
        .str.removeprefix("probability_")
    )


def test_scoring_rejects_missing_columns() -> None:
    with pytest.raises(ValueError, match="missing columns"):
        score_oof_predictions(pd.DataFrame({"truth": ["healthy"]}))


def test_bootstrap_rejects_nonpositive_draw_count() -> None:
    with pytest.raises(ValueError, match="positive"):
        paired_bearing_bootstrap(_synthetic_predictions(), draws=0)


def test_sensor_family_scoring_and_shared_bootstrap_are_complete() -> None:
    base = _synthetic_predictions()
    families = []
    for family in MAIN_SIGNAL_FEATURE_FAMILIES:
        rows = base.copy()
        rows.insert(0, "feature_family", family)
        if family == "motor_current":
            mask = (rows["protocol"] == "measurement_random") & (
                rows["truth"] == "outer"
            )
            rows.loc[mask, "prediction"] = "healthy"
        families.append(rows)
    predictions = pd.concat(families, ignore_index=True)

    aggregate, cells, effects, concordance = score_sensor_family_fault_predictions(
        predictions
    )
    summary, draws, plan = bootstrap_sensor_family_fault_predictions(
        predictions,
        draws=19,
    )
    differences, difference_draws = sensor_gap_differences(summary, draws)

    assert len(aggregate) == 3 * 4 * 2
    assert len(cells) == 3 * 4 * 2 * 24
    assert len(effects) == 3 * 3 * 2 * 5
    assert len(concordance) == 3 * 12
    assert len(summary) == 3 * 3 * 2
    assert len(draws) == 3 * 3 * 2 * 19
    assert len(plan) == 19
    assert len(differences) == 3 * 2
    assert len(difference_draws) == 3 * 2 * 19
    row = differences.loc[
        (differences["left_feature_family"] == "vibration")
        & (differences["right_feature_family"] == "motor_current")
        & (differences["method"] == "a")
    ].iloc[0]
    assert row["gap_difference_left_minus_right"] > 0


def test_bearing_reidentification_is_setting_oof(
    feature_frame: pd.DataFrame,
) -> None:
    predictions, fits = generate_bearing_reidentification_predictions(
        feature_frame,
        model_names=("dummy_prior",),
    )
    scores = score_bearing_reidentification_predictions(predictions)

    assert len(predictions) == len(feature_frame) * 3
    assert len(fits) == 3 * 4
    assert len(scores) == 3
    assert scores["bearing_class_count"].eq(feature_frame["bearing_code"].nunique()).all()
    assert predictions.groupby(["feature_family", "method"])["row_index"].nunique().eq(
        len(feature_frame)
    ).all()
